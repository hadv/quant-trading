package usecase

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
)

// MockMarketClient implements domain.IMarketClient
type MockMarketClient struct {
	FetchFunc      func(ctx context.Context, ticker string, dest *[]domain.Candle) error
	FetchCallCount int32
}

func (m *MockMarketClient) FetchHistoricalData(ctx context.Context, ticker string, dest *[]domain.Candle) error {
	atomic.AddInt32(&m.FetchCallCount, 1)
	if m.FetchFunc != nil {
		return m.FetchFunc(ctx, ticker, dest)
	}
	// Default mock behavior
	*dest = append(*dest, domain.Candle{Ticker: ticker, Close: 100.0})
	return nil
}

// MockDatabase implements domain.IDatabase
type MockDatabase struct {
	SaveFunc      func(ctx context.Context, candles []domain.Candle) error
	SaveCallCount int32
	mu            sync.Mutex
	SavedCandles  [][]domain.Candle
}

func (m *MockDatabase) SaveCandlesAndEvents(ctx context.Context, candles []domain.Candle) error {
	atomic.AddInt32(&m.SaveCallCount, 1)

	// Copy candles to verify later (since underlying slice is reused from pool)
	cpy := make([]domain.Candle, len(candles))
	copy(cpy, candles)

	m.mu.Lock()
	m.SavedCandles = append(m.SavedCandles, cpy)
	m.mu.Unlock()

	if m.SaveFunc != nil {
		return m.SaveFunc(ctx, candles)
	}
	return nil
}

func getTotalSavedCandles(db *MockDatabase) int {
	db.mu.Lock()
	defer db.mu.Unlock()
	total := 0
	for _, batch := range db.SavedCandles {
		total += len(batch)
	}
	return total
}

func TestRunWorkerPool_Success(t *testing.T) {
	mockAPI := &MockMarketClient{}
	mockDB := &MockDatabase{}
	service := NewBackfillService(mockAPI, mockDB)

	tickers := []string{"AAPL", "GOOGL", "MSFT"}
	numWorkers := 2

	start := time.Now()
	service.RunWorkerPool(tickers, numWorkers)
	elapsed := time.Since(start)

	if elapsed < 500*time.Millisecond {
		t.Errorf("Expected execution time to be at least 500ms, got %v", elapsed)
	}

	if atomic.LoadInt32(&mockAPI.FetchCallCount) != 3 {
		t.Errorf("Expected 3 API calls, got %d", mockAPI.FetchCallCount)
	}

	totalCandles := getTotalSavedCandles(mockDB)
	if totalCandles != 3 {
		t.Errorf("Expected exactly 3 candles to be saved across all batches, got %d", totalCandles)
	}
}

func TestRunWorkerPool_FetchError(t *testing.T) {
	mockAPI := &MockMarketClient{
		FetchFunc: func(ctx context.Context, ticker string, dest *[]domain.Candle) error {
			if ticker == "ERROR" {
				return errors.New("simulated API error")
			}
			*dest = append(*dest, domain.Candle{Ticker: ticker, Close: 100.0})
			return nil
		},
	}
	mockDB := &MockDatabase{}
	service := NewBackfillService(mockAPI, mockDB)

	tickers := []string{"AAPL", "ERROR", "MSFT"}
	numWorkers := 2

	service.RunWorkerPool(tickers, numWorkers)

	if atomic.LoadInt32(&mockAPI.FetchCallCount) != 3 {
		t.Errorf("Expected 3 API calls, got %d", mockAPI.FetchCallCount)
	}

	totalCandles := getTotalSavedCandles(mockDB)
	if totalCandles != 2 {
		t.Errorf("Expected exactly 2 candles to be saved across all batches (ERROR was dropped), got %d", totalCandles)
	}
}

func TestRunWorkerPool_EmptyCandles(t *testing.T) {
	mockAPI := &MockMarketClient{
		FetchFunc: func(ctx context.Context, ticker string, dest *[]domain.Candle) error {
			if ticker == "EMPTY" {
				return nil // no error but no candles added to dest
			}
			*dest = append(*dest, domain.Candle{Ticker: ticker, Close: 100.0})
			return nil
		},
	}
	mockDB := &MockDatabase{}
	service := NewBackfillService(mockAPI, mockDB)

	tickers := []string{"EMPTY", "MSFT"}
	numWorkers := 2

	service.RunWorkerPool(tickers, numWorkers)

	if atomic.LoadInt32(&mockAPI.FetchCallCount) != 2 {
		t.Errorf("Expected 2 API calls, got %d", mockAPI.FetchCallCount)
	}

	totalCandles := getTotalSavedCandles(mockDB)
	if totalCandles != 1 {
		t.Errorf("Expected exactly 1 candle to be saved across all batches, got %d", totalCandles)
	}
}

func BenchmarkRunWorkerPool(b *testing.B) {
	mockAPI := &MockMarketClient{
		FetchFunc: func(ctx context.Context, ticker string, dest *[]domain.Candle) error {
			time.Sleep(50 * time.Millisecond)
			*dest = make([]domain.Candle, 1000)
			return nil
		},
	}
	
	mockDB := &MockDatabase{
		SaveFunc: func(ctx context.Context, candles []domain.Candle) error {
			time.Sleep(100 * time.Millisecond)
			return nil
		},
	}
	
	service := NewBackfillService(mockAPI, mockDB)

	var tickers []string
	for i := 0; i < 20; i++ {
		tickers = append(tickers, "TICKER")
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.RunWorkerPool(tickers, 5)
	}
}
