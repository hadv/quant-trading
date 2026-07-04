package database

import (
	"context"
	"encoding/json"
	"time"

	"github.com/hadv/quant-trading/internal/domain"
	"github.com/hadv/quant-trading/internal/infrastructure/telemetry"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PgRepository struct {
	db *pgxpool.Pool
}

func NewPgRepository(db *pgxpool.Pool) *PgRepository {
	return &PgRepository{db: db}
}

func (r *PgRepository) SaveCandlesAndEvents(ctx context.Context, candles []domain.Candle) error {
	ctx, span := telemetry.Tracer.Start(ctx, "SaveBatch_Tx")
	defer span.End()

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	batch := &pgx.Batch{}

	for _, c := range candles {
		batch.Queue(
			`INSERT INTO daily_candles (ticker, trade_date, open_price, high_price, low_price, close_price, volume) 
			 VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
			c.Ticker, c.Date, c.Open, c.High, c.Low, c.Close, c.Volume,
		)

		payloadJSON, _ := json.Marshal(c)
		eventTime, _ := time.Parse("2006-01-02", c.Date)

		batch.Queue(
			`INSERT INTO outbox_events (event_id, aggregate_type, aggregate_id, event_type, timestamp, payload) 
			 VALUES ($1, $2, $3, $4, $5, $6)`,
			uuid.New().String(), "Ticker", "TICKER_"+c.Ticker, "DailyCandleClosed", eventTime, payloadJSON,
		)
	}

	if err := tx.SendBatch(ctx, batch).Close(); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
