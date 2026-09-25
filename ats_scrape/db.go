package atsscrape

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct {
	pool *pgxpool.Pool
}

func OpenStore(ctx context.Context) (*Store, error) {
	dsn := strings.TrimSpace(os.Getenv("DATABASE_URL"))
	if dsn == "" {
		return nil, errors.New("DATABASE_URL is required")
	}
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	store := &Store{pool: pool}
	if err := store.EnsureSchema(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("schema: %w", err)
	}
	return store, nil
}

func (s *Store) Close() {
	if s != nil && s.pool != nil {
		s.pool.Close()
	}
}

func (s *Store) EnsureSchema(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS fetch_http_work (
			id SERIAL PRIMARY KEY,
			fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id) ON DELETE CASCADE,
			company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
			country_key TEXT NOT NULL,
			name TEXT NOT NULL,
			ats_type TEXT NOT NULL DEFAULT '',
			ats_url TEXT NOT NULL DEFAULT '',
			careers_url TEXT NOT NULL DEFAULT '',
			UNIQUE (fetch_run_id, company_id)
		);
		CREATE INDEX IF NOT EXISTS idx_fetch_http_work_run
			ON fetch_http_work(fetch_run_id);
		CREATE TABLE IF NOT EXISTS fetch_http_results (
			id SERIAL PRIMARY KEY,
			fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id) ON DELETE CASCADE,
			company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
			status TEXT NOT NULL,
			error TEXT,
			jobs_json TEXT,
			fetched_at TEXT NOT NULL,
			merge_processed_at TEXT,
			UNIQUE (fetch_run_id, company_id)
		);
		CREATE INDEX IF NOT EXISTS idx_fetch_http_results_pending
			ON fetch_http_results(merge_processed_at, id);
	`)
	return err
}

func (s *Store) ReapStaleRunningRuns(ctx context.Context, maxAge time.Duration) error {
	if maxAge <= 0 {
		return nil
	}
	seconds := int(maxAge.Seconds())
	if seconds < 1 {
		seconds = 1
	}
	finished := time.Now().UTC().Format(time.RFC3339)
	_, err := s.pool.Exec(ctx, `
		UPDATE fetch_runs
		SET status = 'failed',
		    finished_at = $1,
		    exit_code = 1,
		    result_line = COALESCE(result_line, 'Fetch timed out (stale running reap)')
		WHERE status = 'running'
		  AND trim(started_at) != ''
		  AND started_at::timestamptz < (NOW() AT TIME ZONE 'UTC') - ($2 * INTERVAL '1 second')
	`, finished, seconds)
	return err
}

func (s *Store) FetchIsRunning(ctx context.Context) (bool, error) {
	var id int64
	err := s.pool.QueryRow(ctx, `
		SELECT id FROM fetch_runs WHERE status = 'running' ORDER BY id DESC LIMIT 1
	`).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return id > 0, nil
}

func (s *Store) ResolveSchedulerUserID(ctx context.Context) (int64, error) {
	var id int64
	err := s.pool.QueryRow(ctx, `
		SELECT id FROM users WHERE is_admin = 1 ORDER BY id ASC LIMIT 1
	`).Scan(&id)
	if err == nil {
		return id, nil
	}
	admin := strings.TrimSpace(os.Getenv("PANEL_ADMIN_USER"))
	if admin == "" {
		admin = "admin"
	}
	err = s.pool.QueryRow(ctx, `SELECT id FROM users WHERE lower(username) = lower($1) LIMIT 1`, admin).Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("scheduler admin user not found")
	}
	return id, nil
}

func (s *Store) DefaultCountries(ctx context.Context) ([]string, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT lower(trim(country)) AS country
		FROM companies
		WHERE trim(country) != ''
		ORDER BY country
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]string, 0)
	for rows.Next() {
		var country string
		if err := rows.Scan(&country); err != nil {
			return nil, err
		}
		if country != "" {
			out = append(out, country)
		}
	}
	return out, rows.Err()
}

type WorkCompany struct {
	ID         int64
	CountryKey string
	Name       string
	ATSType    string
	ATSURL     string
	CareersURL string
}

func (s *Store) ListHTTPCompanies(ctx context.Context, countryKey string) ([]WorkCompany, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT c.id, c.country, c.name, COALESCE(c.ats_type, ''), COALESCE(c.ats_url, ''), COALESCE(c.careers_url, '')
		FROM companies c
		WHERE lower(c.country) = lower($1)
		  AND lower(COALESCE(c.ats_type, '')) NOT IN ('atlassian', 'hibob', 'jibe', 'sourced')
		ORDER BY c.name
	`, countryKey)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]WorkCompany, 0)
	for rows.Next() {
		var row WorkCompany
		if err := rows.Scan(&row.ID, &row.CountryKey, &row.Name, &row.ATSType, &row.ATSURL, &row.CareersURL); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func countryArchiveFilename(countryKey string) string {
	key := strings.ToLower(strings.TrimSpace(countryKey))
	if key == "" {
		return ""
	}
	return key + "_companies.json"
}

func (s *Store) CreateFetchRun(ctx context.Context, userID int64, countryKey string, concurrency int) (int64, error) {
	started := time.Now().UTC().Format(time.RFC3339)
	fileName := countryArchiveFilename(countryKey)
	progress := `{"current":0,"total":0,"company":null,"status":""}`
	var runID int64
	err := s.pool.QueryRow(ctx, `
		INSERT INTO fetch_runs (
			user_id, country, company_name, scope, status,
			ats_type, file_name, started_at, finished_at,
			concurrency, new_jobs, progress_json, activity_json,
			activity_log_json, log_json
		) VALUES (
			$1, $2, NULL, 'country', 'running',
			NULL, $3, $4, '',
			$5, 0, $6, '{"message":"","detail":""}',
			'[]', '[]'
		)
		RETURNING id
	`, userID, countryKey, fileName, started, concurrency, progress).Scan(&runID)
	return runID, err
}

func (s *Store) InsertWorkRows(ctx context.Context, runID int64, companies []WorkCompany) error {
	if len(companies) == 0 {
		return nil
	}
	batch := &pgx.Batch{}
	for _, company := range companies {
		batch.Queue(`
			INSERT INTO fetch_http_work (
				fetch_run_id, company_id, country_key, name, ats_type, ats_url, careers_url
			) VALUES ($1, $2, $3, $4, $5, $6, $7)
			ON CONFLICT (fetch_run_id, company_id) DO NOTHING
		`, runID, company.ID, company.CountryKey, company.Name, company.ATSType, company.ATSURL, company.CareersURL)
	}
	br := s.pool.SendBatch(ctx, batch)
	defer br.Close()
	for range companies {
		if _, err := br.Exec(); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) UpdateProgress(ctx context.Context, runID int64, current, total int, company, status string) error {
	progress, err := json.Marshal(map[string]any{
		"current": current,
		"total":   total,
		"company": company,
		"status":  status,
	})
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(ctx, `
		UPDATE fetch_runs
		SET progress_json = $2,
		    companies_done = $3,
		    companies_total = $4
		WHERE id = $1 AND status = 'running'
	`, runID, string(progress), current, total)
	return err
}

type resultStatus string

const (
	resultOK    resultStatus = "ok"
	resultEmpty resultStatus = "empty"
	resultError resultStatus = "error"
)

func (s *Store) InsertResult(ctx context.Context, runID, companyID int64, status resultStatus, errText string, jobs []Job) error {
	fetchedAt := time.Now().UTC().Format(time.RFC3339)
	var jobsJSON *string
	if status == resultOK || status == resultEmpty {
		raw, err := json.Marshal(jobs)
		if err != nil {
			return err
		}
		text := string(raw)
		jobsJSON = &text
	}
	var errPtr *string
	if status == resultError {
		text := strings.TrimSpace(errText)
		if text != "" {
			errPtr = &text
		}
	}
	_, err := s.pool.Exec(ctx, `
		INSERT INTO fetch_http_results (
			fetch_run_id, company_id, status, error, jobs_json, fetched_at
		) VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (fetch_run_id, company_id) DO UPDATE SET
			status = EXCLUDED.status,
			error = EXCLUDED.error,
			jobs_json = EXCLUDED.jobs_json,
			fetched_at = EXCLUDED.fetched_at,
			merge_processed_at = NULL
	`, runID, companyID, string(status), errPtr, jobsJSON, fetchedAt)
	return err
}

func (s *Store) FinalizeRun(ctx context.Context, runID int64, companiesDone, companiesTotal int) error {
	finished := time.Now().UTC().Format(time.RFC3339)
	resultLine := fmt.Sprintf("HTTP fetch complete for %d companies (merge pending)", companiesDone)
	_, err := s.pool.Exec(ctx, `
		UPDATE fetch_runs
		SET status = 'done',
		    finished_at = $2,
		    exit_code = 0,
		    cancelled = 0,
		    companies_done = $3,
		    companies_total = $4,
		    result_line = $5,
		    cancel_requested = 0
		WHERE id = $1 AND status = 'running'
	`, runID, finished, companiesDone, companiesTotal, resultLine)
	return err
}

func (s *Store) FailRun(ctx context.Context, runID int64, message string) error {
	finished := time.Now().UTC().Format(time.RFC3339)
	line := strings.TrimSpace(message)
	if line == "" {
		line = "HTTP country fetch failed"
	}
	_, err := s.pool.Exec(ctx, `
		UPDATE fetch_runs
		SET status = 'failed',
		    finished_at = $2,
		    exit_code = 1,
		    cancelled = 0,
		    result_line = $3,
		    cancel_requested = 0
		WHERE id = $1 AND status = 'running'
	`, runID, finished, line)
	return err
}
