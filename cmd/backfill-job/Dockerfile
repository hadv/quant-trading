FROM golang:1.26-alpine AS builder
RUN apk update && apk add --no-cache git ca-certificates tzdata
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o /bin/backfill-job ./cmd/backfill-job/main.go

FROM alpine:3.18
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
ENV TZ=Asia/Ho_Chi_Minh
COPY --from=builder /bin/backfill-job /app/backfill-job
RUN adduser -D -g '' quantuser
USER quantuser
WORKDIR /app
ENTRYPOINT ["/app/backfill-job"]
