# syntax=docker/dockerfile:1
# Build from repo root: docker build -f apps/notification-worker/Dockerfile .
FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY notification_worker ./notification_worker
COPY apps/notification-worker ./apps/notification-worker
RUN CGO_ENABLED=0 go build -o /notification-worker ./apps/notification-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=build /notification-worker /usr/local/bin/notification-worker
ENTRYPOINT ["notification-worker"]
