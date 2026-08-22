package usecase

import (
	"context"
	"sync"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/pkg/pool"

	"log/slog"
)

type BackfillService struct {
	apiClient domain.IMarketClient
	dbRepo    domain.IDatabase
}

func NewBackfillService(api domain.IMarketClient, db domain.IDatabase) *BackfillService {
	return &BackfillService{apiClient: api, dbRepo: db}
}

type FetchResult struct {
	Ticker     string
	CandlesPtr *[]domain.Candle
	Error      error
}

func (s *BackfillService) RunWorkerPool(tickers []string, numWorkers int) {
	fetchJobs := make(chan string, len(tickers))
	insertJobs := make(chan FetchResult, numWorkers*2)

	var fetchWg sync.WaitGroup
	var insertWg sync.WaitGroup

	numInserters := numWorkers

	// 1. Khởi chạy Inserter Pool (Ghi DB gom nhóm)
	for i := 0; i < numInserters; i++ {
		insertWg.Add(1)
		go func() {
			defer insertWg.Done()
			ctx := context.Background()

			batchCandles := make([]domain.Candle, 0, 5000)
			batchPointers := make([]*[]domain.Candle, 0)
			
			// Ticker để xả buffer mỗi 1 giây (nếu chưa gom đủ 5000 nến)
			ticker := time.NewTicker(1 * time.Second)
			defer ticker.Stop()

			flush := func() {
				if len(batchCandles) > 0 {
					if err := s.dbRepo.SaveCandlesAndEvents(ctx, batchCandles); err != nil {
						slog.ErrorContext(ctx, "Lưu Database thất bại (Batch)", slog.String("err", err.Error()))
					} else {
						slog.InfoContext(ctx, "Backfill Batch thành công", slog.Int("records", len(batchCandles)))
					}
				}
				
				// Trả các slice gốc về Pool sau khi đã ghi DB xong
				for _, ptr := range batchPointers {
					pool.CandleSlicePool.Put(ptr)
				}
				
				batchCandles = batchCandles[:0]
				batchPointers = batchPointers[:0]
			}

			for {
				select {
				case result, ok := <-insertJobs:
					if !ok {
						// Khi channel bị đóng, xả nốt những dữ liệu còn sót lại trong buffer rồi thoát
						flush()
						return
					}

					if result.Error != nil {
						slog.ErrorContext(ctx, "Fetch thất bại", slog.String("ticker", result.Ticker), slog.String("err", result.Error.Error()))
						pool.CandleSlicePool.Put(result.CandlesPtr)
						continue
					}

					candles := *result.CandlesPtr
					if len(candles) > 0 {
						batchCandles = append(batchCandles, candles...)
						batchPointers = append(batchPointers, result.CandlesPtr)
						
						// Xả xuống DB nếu đủ số lượng
						if len(batchCandles) >= 5000 {
							flush()
						}
					} else {
						// Bỏ qua nến rỗng, trả luôn về pool
						pool.CandleSlicePool.Put(result.CandlesPtr)
					}

				case <-ticker.C:
					// Xả theo chu kỳ thời gian
					flush()
				}
			}
		}()
	}

	// 2. Khởi chạy Fetcher Pool
	for w := 0; w < numWorkers; w++ {
		fetchWg.Add(1)
		go func() {
			defer fetchWg.Done()
			ctx := context.Background()

			for ticker := range fetchJobs {
				candlesPtr := pool.CandleSlicePool.Get().(*[]domain.Candle)
				candles := (*candlesPtr)[:0]

				err := s.apiClient.FetchHistoricalData(ctx, ticker, &candles)
				*candlesPtr = candles

				insertJobs <- FetchResult{
					Ticker:     ticker,
					CandlesPtr: candlesPtr,
					Error:      err,
				}

				time.Sleep(500 * time.Millisecond)
			}
		}()
	}

	// 3. Truyền job vào queue
	for _, t := range tickers {
		fetchJobs <- t
	}
	close(fetchJobs)

	fetchWg.Wait()
	close(insertJobs)
	insertWg.Wait()
}
