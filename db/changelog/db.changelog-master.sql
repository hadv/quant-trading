-- liquibase formatted sql

-- changeset hadv:1
CREATE TABLE daily_candles (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open_price NUMERIC(15, 4),
    high_price NUMERIC(15, 4),
    low_price NUMERIC(15, 4),
    close_price NUMERIC(15, 4),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, trade_date)
);

-- changeset hadv:2
CREATE TABLE outbox_events (
    event_id UUID PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
