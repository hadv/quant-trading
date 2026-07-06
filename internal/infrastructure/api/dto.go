package api

import "github.com/hadv/quant-trading/internal/domain"

// CandleDTO represents the structure of a candle returned by the external API.
type CandleDTO struct {
	Date   string  `json:"date"`
	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume int64   `json:"volume"`
}

// CandleMapper returns a mapping function that converts a CandleDTO to a domain.Candle.
// We use a closure here so we can inject the 'ticker' which isn't present in the DTO.
func CandleMapper(ticker string) func(CandleDTO) (domain.Candle, error) {
	return func(dto CandleDTO) (domain.Candle, error) {
		return domain.Candle{
			Ticker: ticker,
			Open:   dto.Open,
			High:   dto.High,
			Low:    dto.Low,
			Close:  dto.Close,
			Volume: dto.Volume,
			Date:   dto.Date,
		}, nil
	}
}
