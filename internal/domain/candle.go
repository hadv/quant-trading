package domain

import "context"

type Candle struct {
	Ticker string  `json:"ticker"`
	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume int64   `json:"volume"`
	Date   string  `json:"date"`
}

type IMarketClient interface {
	FetchHistoricalData(ctx context.Context, ticker string, dest *[]Candle) error
}

type IDatabase interface {
	SaveCandlesAndEvents(ctx context.Context, candles []Candle) error
}
