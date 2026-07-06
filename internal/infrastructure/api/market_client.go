package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"math/rand"
	"net/http"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/internal/infrastructure/telemetry"
	"github.com/hadv/quant-trading/pkg/transform"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"golang.org/x/exp/slog"
)

type MarketClient struct {
	maxRetries int
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

func NewMarketClient(baseURL, apiKey string, retries int) *MarketClient {
	rand.Seed(time.Now().UnixNano())
	return &MarketClient{
		maxRetries: retries,
		baseURL:    baseURL,
		apiKey:     apiKey,
		httpClient: &http.Client{Timeout: 15 * time.Second},
	}
}

func (c *MarketClient) FetchHistoricalData(ctx context.Context, ticker string, dest *[]domain.Candle) error {
	ctx, span := telemetry.Tracer.Start(ctx, "FetchAPI")
	defer span.End()

	baseDelay := 2 * time.Second
	maxDelay := 60 * time.Second

	for attempt := 0; attempt < c.maxRetries; attempt++ {
		err := c.doFetch(ctx, ticker, dest)
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

func (c *MarketClient) doFetch(ctx context.Context, ticker string, dest *[]domain.Candle) error {
	reqURL := fmt.Sprintf("%s/historical?ticker=%s", c.baseURL, ticker)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("http request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	// Fetch raw DTOs
	var rawCandles []CandleDTO
	if err := json.Unmarshal(body, &rawCandles); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	// Transform raw API data into domain.Candle using the generic framework
	candles, err := transform.MapList(rawCandles, CandleMapper(ticker))
	if err != nil {
		return fmt.Errorf("failed to transform candles: %w", err)
	}

	*dest = append(*dest, candles...)

	return nil
}
