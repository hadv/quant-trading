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

	// 1. Khởi chạy Inserter Pool
	for i := 0; i < numInserters; i++ {
		insertWg.Add(1)
		go func() {
			defer insertWg.Done()
			ctx := context.Background()

			for result := range insertJobs {
				// Dù thành công hay lỗi, Inserter LUÔN phải trả slice lại cho pool
				if result.Error != nil {
					slog.ErrorContext(ctx, "Fetch thất bại", slog.String("ticker", result.Ticker), slog.String("err", result.Error.Error()))
					pool.CandleSlicePool.Put(result.CandlesPtr)
					continue
				}

				candles := *result.CandlesPtr
				if len(candles) > 0 {
					if err := s.dbRepo.SaveCandlesAndEvents(ctx, candles); err != nil {
						slog.ErrorContext(ctx, "Lưu Database thất bại", slog.String("ticker", result.Ticker), slog.String("err", err.Error()))
					} else {
						slog.InfoContext(ctx, "Backfill thành công", slog.String("ticker", result.Ticker), slog.Int("records", len(candles)))
					}
				}

				pool.CandleSlicePool.Put(result.CandlesPtr)
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

				time.Sleep(500 * time.Millisecond) // Global API rate limit
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
