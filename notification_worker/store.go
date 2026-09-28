package notificationworker

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

type Store struct {
	conn *pgx.Conn
}

type NotifyUser struct {
	ID    int
	Email string
}

type PushSubscription struct {
	Endpoint string
	P256dh   string
	Auth     string
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

func (s *Store) CountWaveJobsForUser(ctx context.Context, userID, fetchRunID int) (int, error) {
	var n int
	err := s.conn.QueryRow(ctx, `
		SELECT COUNT(DISTINCT w.job_key)
		FROM fetch_wave_new_jobs w
		INNER JOIN user_opportunities uo
		  ON uo.user_id = $1
		 AND uo.country = w.country
		 AND lower(uo.company_name) = lower(w.company_name)
		WHERE w.fetch_run_id = $2
	`, userID, fetchRunID).Scan(&n)
	return n, err
}

func (s *Store) WaveAlreadyNotified(ctx context.Context, userID, fetchRunID int) (bool, error) {
	var one int
	err := s.conn.QueryRow(ctx, `
		SELECT 1 FROM fetch_wave_push_sent
		WHERE user_id = $1 AND fetch_run_id = $2
	`, userID, fetchRunID).Scan(&one)
	if err == pgx.ErrNoRows {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

func (s *Store) MarkWaveNotified(ctx context.Context, userID, fetchRunID int) error {
	now := time.Now().UTC().Truncate(time.Second).Format("2006-01-02T15:04:05+00:00")
	_, err := s.conn.Exec(ctx, `
		INSERT INTO fetch_wave_push_sent (user_id, fetch_run_id, sent_at)
		VALUES ($1, $2, $3)
	`, userID, fetchRunID, now)
	return err
}

func (s *Store) ListFullPlanNotifyUsers(ctx context.Context) ([]NotifyUser, error) {
	rows, err := s.conn.Query(ctx, `
		SELECT DISTINCT u.id, COALESCE(u.email, '')
		FROM users u
		WHERE lower(COALESCE(u.plan, 'free')) IN ('full', 'grandfathered')
		  AND (
		    COALESCE(u.email, '') <> ''
		    OR EXISTS (SELECT 1 FROM web_push_subscriptions s WHERE s.user_id = u.id)
		  )
		ORDER BY u.id ASC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []NotifyUser
	for rows.Next() {
		var u NotifyUser
		if err := rows.Scan(&u.ID, &u.Email); err != nil {
			return nil, err
		}
		out = append(out, u)
	}
	return out, rows.Err()
}

func (s *Store) ListPushSubscriptions(ctx context.Context, userID int) ([]PushSubscription, error) {
	rows, err := s.conn.Query(ctx, `
		SELECT endpoint, p256dh, auth
		FROM web_push_subscriptions
		WHERE user_id = $1
		ORDER BY updated_at DESC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []PushSubscription
	for rows.Next() {
		var sub PushSubscription
		if err := rows.Scan(&sub.Endpoint, &sub.P256dh, &sub.Auth); err != nil {
			return nil, err
		}
		out = append(out, sub)
	}
	return out, rows.Err()
}

func (s *Store) DeletePushSubscription(ctx context.Context, endpoint string) error {
	endpoint = strings.TrimSpace(endpoint)
	if endpoint == "" {
		return nil
	}
	_, err := s.conn.Exec(ctx, `DELETE FROM web_push_subscriptions WHERE endpoint = $1`, endpoint)
	return err
}
