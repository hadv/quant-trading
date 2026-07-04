package telemetry

import (
	"context"
	"os"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/trace"
	"golang.org/x/exp/slog"
)

var (
	Meter           = otel.Meter("quant-backfill")
	Tracer          = otel.Tracer("quant-backfill")
	ApiRetryCounter metric.Int64Counter
)

type OTelLogHandler struct {
	slog.Handler
}

func (h *OTelLogHandler) Handle(ctx context.Context, r slog.Record) error {
	spanCtx := trace.SpanContextFromContext(ctx)
	if spanCtx.HasTraceID() {
		r.AddAttrs(
			slog.String("trace_id", spanCtx.TraceID().String()),
			slog.String("span_id", spanCtx.SpanID().String()),
		)
	}
	return h.Handler.Handle(ctx, r)
}

func InitObservability() {
	var err error
	ApiRetryCounter, err = Meter.Int64Counter(
		"api_fetch_retries_total",
		metric.WithDescription("Total API retries"),
	)
	if err != nil {
		panic(err)
	}

	jsonHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	slog.SetDefault(slog.New(&OTelLogHandler{Handler: jsonHandler}))
}
