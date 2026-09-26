package opsagent

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

type Store struct {
	conn *pgx.Conn
}

func OpenStore(ctx context.Context) (*Store, error) {
	url := strings.TrimSpace(os.Getenv("DATABASE_URL"))
	if url == "" {
		return nil, fmt.Errorf("DATABASE_URL is empty")
	}
	conn, err := pgx.Connect(ctx, url)
	if err != nil {
		return nil, err
	}
	return &Store{conn: conn}, nil
}

func (s *Store) Close(ctx context.Context) {
	_ = s.conn.Close(ctx)
}

func (s *Store) InsertSamples(ctx context.Context, samples []Sample) error {
	if len(samples) == 0 {
		return nil
	}
	batch := &pgx.Batch{}
	for _, sample := range samples {
		at := sample.At
		if at.IsZero() {
			at = time.Now().UTC()
		}
		labels := sample.Labels
		if labels == nil {
			labels = map[string]string{}
		}
		payload, err := json.Marshal(labels)
		if err != nil {
			return err
		}
		batch.Queue(
			`INSERT INTO ops_metric_samples (recorded_at, metric, labels, value)
			 VALUES ($1, $2, $3::jsonb, $4)`,
			at, sample.Metric, string(payload), sample.Value,
		)
	}
	br := s.conn.SendBatch(ctx, batch)
	defer br.Close()
	for range samples {
		if _, err := br.Exec(); err != nil {
			return err
		}
	}
	return br.Close()
}
