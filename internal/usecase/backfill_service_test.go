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

func TestRunWorkerPool_Success(t *testing.T) {
	mockAPI := &MockMarketClient{}
	mockDB := &MockDatabase{}
	service := NewBackfillService(mockAPI, mockDB)

	tickers := []string{"AAPL", "GOOGL", "MSFT"}
	numWorkers := 2

	// Capture execution time
	start := time.Now()
	service.RunWorkerPool(tickers, numWorkers)
	elapsed := time.Since(start)

	// In the worst case, 3 tickers with 2 workers:
	// Wait time should be at least 500ms (1 batch for sleep)
	if elapsed < 500*time.Millisecond {
		t.Errorf("Expected execution time to be at least 500ms, got %v", elapsed)
	}

	if atomic.LoadInt32(&mockAPI.FetchCallCount) != 3 {
		t.Errorf("Expected 3 API calls, got %d", mockAPI.FetchCallCount)
	}

	if atomic.LoadInt32(&mockDB.SaveCallCount) != 3 {
		t.Errorf("Expected 3 DB saves, got %d", mockDB.SaveCallCount)
	}

	mockDB.mu.Lock()
	defer mockDB.mu.Unlock()
	if len(mockDB.SavedCandles) != 3 {
		t.Errorf("Expected 3 batches of saved candles, got %d", len(mockDB.SavedCandles))
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

	// Because "ERROR" fails at fetch, DB should only be called twice.
	if atomic.LoadInt32(&mockDB.SaveCallCount) != 2 {
		t.Errorf("Expected 2 DB saves, got %d", mockDB.SaveCallCount)
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

	// API fetched twice
	if atomic.LoadInt32(&mockAPI.FetchCallCount) != 2 {
		t.Errorf("Expected 2 API calls, got %d", mockAPI.FetchCallCount)
	}

	// DB should only be called once because EMPTY has length 0
	if atomic.LoadInt32(&mockDB.SaveCallCount) != 1 {
		t.Errorf("Expected 1 DB save, got %d", mockDB.SaveCallCount)
	}
}

func BenchmarkRunWorkerPool(b *testing.B) {
	// Giả lập Client API mất 50ms để tải dữ liệu mạng
	mockAPI := &MockMarketClient{
		FetchFunc: func(ctx context.Context, ticker string, dest *[]domain.Candle) error {
			time.Sleep(50 * time.Millisecond)
			*dest = make([]domain.Candle, 1000) // Giả lập trả về 1000 nến
			return nil
		},
	}
	
	// Giả lập Database mất 100ms để thực hiện lưu bulk insert
	mockDB := &MockDatabase{
		SaveFunc: func(ctx context.Context, candles []domain.Candle) error {
			time.Sleep(100 * time.Millisecond)
			return nil
		},
	}
	
	service := NewBackfillService(mockAPI, mockDB)

	// Chuẩn bị 20 tickers cho mỗi lượt benchmark
	var tickers []string
	for i := 0; i < 20; i++ {
		tickers = append(tickers, "TICKER")
	}

	// Disable log cho benchmark để tránh I/O bottleneck ra stdout
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Benchmark với 5 workers
		service.RunWorkerPool(tickers, 5)
	}
}
