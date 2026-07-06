package api

import (
	"context"

	"github.com/hadv/quant-trading/internal/domain"
)

type MockMarketClient struct {
	MockData map[string][]domain.Candle
}

func NewMockMarketClient(data map[string][]domain.Candle) *MockMarketClient {
	if data == nil {
		data = make(map[string][]domain.Candle)
	}
	return &MockMarketClient{MockData: data}
}

func (m *MockMarketClient) FetchHistoricalData(ctx context.Context, ticker string, dest *[]domain.Candle) error {
	if data, exists := m.MockData[ticker]; exists {
		*dest = append(*dest, data...)
	}
	return nil
}
