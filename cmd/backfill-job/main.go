package main

import (
	"context"
	"os"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/internal/infrastructure/api"
	"github.com/hadv/quant-trading/internal/infrastructure/database"
	"github.com/hadv/quant-trading/internal/infrastructure/telemetry"
	"github.com/hadv/quant-trading/internal/usecase"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/exp/slog"
)

func main() {
	ctx := context.Background()
	shutdown, err := telemetry.InitObservability(ctx)
	if err != nil {
		slog.Error("Failed to initialize observability", "error", err)
		os.Exit(1)
	}
	defer func() {
		if err := shutdown(context.Background()); err != nil {
			slog.Error("Failed to shutdown observability", "error", err)
		}
	}()

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://user:pass@localhost:5432/quantdb"
	}

	dbPool, err := pgxpool.New(context.Background(), dbURL)
	if err != nil {
		slog.Error("Không thể kết nối Database", slog.String("error", err.Error()))
		os.Exit(1)
	}
	defer dbPool.Close()

	var apiClient domain.IMarketClient
	useMock := os.Getenv("USE_MOCK_API")
	if useMock == "true" || useMock == "" { // Default to mock for now
		mockData := map[string][]domain.Candle{
			"AAPL": {
				{Ticker: "AAPL", Open: 150.0, Close: 154.0, Volume: 1000, Date: "2010-01-04"},
				{Ticker: "AAPL", Open: 154.0, Close: 157.0, Volume: 1200, Date: "2010-01-05"},
			},
		}
		apiClient = api.NewMockMarketClient(mockData)
		slog.Info("Sử dụng MockMarketClient")
	} else {
		baseURL := os.Getenv("MARKET_API_URL")
		apiKey := os.Getenv("MARKET_API_KEY")
		if baseURL == "" {
			baseURL = "https://api.example.com"
		}
		apiClient = api.NewMarketClient(baseURL, apiKey, 5)
		slog.Info("Sử dụng RealMarketClient")
	}

	dbRepo := database.NewPgRepository(dbPool)
	service := usecase.NewBackfillService(apiClient, dbRepo)

	tickers := []string{"AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"}
	
	slog.Info("🚀 BẮT ĐẦU CHẠY BACKFILL SERVICE...")
	service.RunWorkerPool(tickers, 3)
	slog.Info("🏁 ĐÃ HOÀN TẤT TOÀN BỘ JOB")
}
