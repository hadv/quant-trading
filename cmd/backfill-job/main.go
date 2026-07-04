package main

import (
	"context"
	"os"

	"github.com/hadv/quant-trading/internal/infrastructure/api"
	"github.com/hadv/quant-trading/internal/infrastructure/database"
	"github.com/hadv/quant-trading/internal/infrastructure/telemetry"
	"github.com/hadv/quant-trading/internal/usecase"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/exp/slog"
)

func main() {
	telemetry.InitObservability()

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

	apiClient := api.NewMarketClient(5)
	dbRepo := database.NewPgRepository(dbPool)
	service := usecase.NewBackfillService(apiClient, dbRepo)

	tickers := []string{"AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"}
	
	slog.Info("🚀 BẮT ĐẦU CHẠY BACKFILL SERVICE...")
	service.RunWorkerPool(tickers, 3)
	slog.Info("🏁 ĐÃ HOÀN TẤT TOÀN BỘ JOB")
}
