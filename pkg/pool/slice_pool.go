package pool

import (
	"sync"

	"github.com/hadv/quant-trading/internal/domain"
)

var CandleSlicePool = sync.Pool{
	New: func() any {
		slice := make([]domain.Candle, 0, 4000)
		return &slice
	},
}
