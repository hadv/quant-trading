package api

import (
	"context"
	"fmt"
	"math"
	"math/rand"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/internal/infrastructure/telemetry"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"golang.org/x/exp/slog"
)

type MarketClient struct {
	maxRetries int
}

func NewMarketClient(retries int) *MarketClient {
	rand.Seed(time.Now().UnixNano())
	return &MarketClient{maxRetries: retries}
}

func (c *MarketClient) FetchHistoricalData(ctx context.Context, ticker string, dest *[]domain.Candle) error {
	ctx, span := telemetry.Tracer.Start(ctx, "FetchAPI")
	defer span.End()

	baseDelay := 2 * time.Second
	maxDelay := 60 * time.Second

	for attempt := 0; attempt < c.maxRetries; attempt++ {
		err := c.doFetch(ticker, dest)
		if err == nil {
			return nil
		}

		telemetry.ApiRetryCounter.Add(ctx, 1, metric.WithAttributes(
			attribute.String("ticker", ticker),
			attribute.Int("attempt", attempt+1),
		))

		if attempt == c.maxRetries-1 {
			return fmt.Errorf("thất bại sau %d lần: %w", c.maxRetries, err)
		}

		backoff := float64(baseDelay) * math.Pow(2, float64(attempt))
		if backoff > float64(maxDelay) {
			backoff = float64(maxDelay)
		}
		waitDuration := time.Duration(backoff + (rand.Float64() * backoff * 0.5))

		slog.WarnContext(ctx, "Lỗi API, đang chờ thử lại",
			slog.String("ticker", ticker),
			slog.String("error", err.Error()),
			slog.String("wait", waitDuration.String()),
		)
		time.Sleep(waitDuration)
	}
	return fmt.Errorf("unknown error")
}

func (c *MarketClient) doFetch(ticker string, dest *[]domain.Candle) error {
	// Giả lập Dữ liệu - Điểm này bạn sẽ call thư viện HTTP
	*dest = append(*dest, domain.Candle{Ticker: ticker, Open: 150.0, Close: 154.0, Volume: 1000, Date: "2010-01-04"})
	*dest = append(*dest, domain.Candle{Ticker: ticker, Open: 154.0, Close: 157.0, Volume: 1200, Date: "2010-01-05"})
	return nil
}
