package usecase

import (
	"context"
	"sync"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/pkg/pool"

	"golang.org/x/exp/slog"
)

type BackfillService struct {
	apiClient domain.IMarketClient
	dbRepo    domain.IDatabase
}

func NewBackfillService(api domain.IMarketClient, db domain.IDatabase) *BackfillService {
	return &BackfillService{apiClient: api, dbRepo: db}
}

func (s *BackfillService) processSingleTicker(ctx context.Context, ticker string) error {
	candlesPtr := pool.CandleSlicePool.Get().(*[]domain.Candle)
	candles := (*candlesPtr)[:0]
	defer pool.CandleSlicePool.Put(candlesPtr)

	if err := s.apiClient.FetchHistoricalData(ctx, ticker, &candles); err != nil {
		return err
	}
	if len(candles) == 0 {
		return nil
	}
	if err := s.dbRepo.SaveCandlesAndEvents(ctx, candles); err != nil {
		return err
	}

	slog.InfoContext(ctx, "Backfill thành công", slog.String("ticker", ticker), slog.Int("records", len(candles)))
	return nil
}

func (s *BackfillService) RunWorkerPool(tickers []string, numWorkers int) {
	jobs := make(chan string, len(tickers))
	var wg sync.WaitGroup

	for w := 1; w <= numWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ctx := context.Background()
			
			for ticker := range jobs {
				if err := s.processSingleTicker(ctx, ticker); err != nil {
					slog.ErrorContext(ctx, "Worker thất bại", slog.String("ticker", ticker), slog.String("err", err.Error()))
				}
				time.Sleep(500 * time.Millisecond) // Global API rate limit
			}
		}()
	}

	for _, t := range tickers {
		jobs <- t
	}
	close(jobs)
	wg.Wait()
}
