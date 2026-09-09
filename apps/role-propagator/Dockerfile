# syntax=docker/dockerfile:1
# Build from repo root: docker build -f apps/role-propagator/Dockerfile .
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY role_propagator ./role_propagator
COPY apps/role-propagator ./apps/role-propagator
RUN CGO_ENABLED=0 go build -o /role-propagator ./apps/role-propagator

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=build /role-propagator /usr/local/bin/role-propagator
ENTRYPOINT ["role-propagator"]
