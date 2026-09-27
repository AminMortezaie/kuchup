# syntax=docker/dockerfile:1
# Build from repo root: docker build -f apps/ops-agent/Dockerfile .
FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY ops_agent ./ops_agent
COPY apps/ops-agent ./apps/ops-agent
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /ops-agent ./apps/ops-agent

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=build /ops-agent /usr/local/bin/ops-agent
ENTRYPOINT ["ops-agent"]
