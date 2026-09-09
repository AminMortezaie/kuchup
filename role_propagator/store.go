package rolepropagator

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

const defaultCountry = "germany"

type Store struct {
	conn *pgx.Conn
}

type UserRow struct {
	ID       int
	Username string
	Email    string
	Plan     string
	IsAdmin  bool
}

func envInt(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 1 {
		return fallback
	}
	return n
}

func utcNow() string {
	return time.Now().UTC().Truncate(time.Second).Format("2006-01-02T15:04:05+00:00")
}

func periodKey() string {
	return time.Now().UTC().Format("2006-01")
}

func parseCountryList(raw string) []string {
	var data []any
	if err := json.Unmarshal([]byte(strings.TrimSpace(raw)), &data); err != nil {
		return nil
	}
	out := make([]string, 0, len(data))
	seen := map[string]bool{}
	for _, item := range data {
		v := strings.ToLower(strings.TrimSpace(fmt.Sprint(item)))
		if v == "" || seen[v] {
			continue
		}
		seen[v] = true
		out = append(out, v)
	}
	return out
}

func adminEmails() map[string]bool {
	out := map[string]bool{}
	for _, part := range strings.Split(os.Getenv("PANEL_ADMIN_EMAILS"), ",") {
		e := strings.ToLower(strings.TrimSpace(part))
		if e != "" {
			out[e] = true
		}
	}
	return out
}

func adminUsername() string {
	name := strings.ToLower(strings.TrimSpace(os.Getenv("PANEL_ADMIN_USER")))
	if name == "" {
		return "admin"
	}
	return name
}

func (u UserRow) Admin() bool {
	if u.IsAdmin {
		return true
	}
	if adminEmails()[strings.ToLower(strings.TrimSpace(u.Email))] {
		return true
	}
	return strings.ToLower(strings.TrimSpace(u.Username)) == adminUsername()
}

func (u UserRow) Unlimited() bool {
	if u.Admin() {
		return true
	}
	plan := strings.ToLower(strings.TrimSpace(u.Plan))
	if plan == "" {
		plan = "free"
	}
	return plan == "full" || plan == "grandfathered"
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

func (s *Store) LoadUser(ctx context.Context, userID int) (UserRow, error) {
	var u UserRow
	var adminInt int
	err := s.conn.QueryRow(ctx, `
		SELECT id, COALESCE(username, ''), COALESCE(email, ''), COALESCE(plan, 'free'), COALESCE(is_admin, 0)
		FROM users WHERE id = $1
	`, userID).Scan(&u.ID, &u.Username, &u.Email, &u.Plan, &adminInt)
	if err != nil {
		return u, err
	}
	u.IsAdmin = adminInt != 0
	return u, nil
}

func (s *Store) PrefsCountries(ctx context.Context, userID int) ([]string, error) {
	var raw *string
	err := s.conn.QueryRow(ctx, `
		SELECT target_countries_json FROM user_preferences WHERE user_id = $1
	`, userID).Scan(&raw)
	if err == pgx.ErrNoRows {
		return []string{defaultCountry}, nil
	}
	if err != nil {
		return nil, err
	}
	var countries []string
	if raw != nil {
		countries = parseCountryList(*raw)
	}
	if len(countries) == 0 {
		return []string{defaultCountry}, nil
	}
	return countries, nil
}

func (s *Store) ListCandidates(ctx context.Context, countries []string) ([]Candidate, error) {
	if len(countries) == 0 {
		return nil, nil
	}
	rows, err := s.conn.Query(ctx, `
		SELECT c.country, c.name AS company_name,
		       COALESCE(MAX(mj.fetched), c.updated, '') AS newest_fetched,
		       COUNT(mj.id) AS open_job_count
		FROM companies c
		LEFT JOIN matching_jobs mj ON mj.company_id = c.id
		WHERE c.country = ANY($1)
		GROUP BY c.id, c.country, c.name, c.updated
		ORDER BY newest_fetched DESC, c.name ASC
	`, countries)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Candidate
	for rows.Next() {
		var c Candidate
		if err := rows.Scan(&c.Country, &c.CompanyName, &c.NewestFetched, &c.OpenJobCount); err != nil {
			return nil, err
		}
		c.Country = strings.ToLower(strings.TrimSpace(c.Country))
		c.CompanyName = strings.TrimSpace(c.CompanyName)
		c.NewestFetched = strings.TrimSpace(c.NewestFetched)
		if c.CompanyName == "" {
			continue
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

func (s *Store) ListOpportunities(ctx context.Context, userID int) ([]Opportunity, error) {
	rows, err := s.conn.Query(ctx, `
		SELECT country, company_name, newest_fetched, COALESCE(engaged, 0)
		FROM user_opportunities WHERE user_id = $1
		ORDER BY newest_fetched DESC, company_name ASC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Opportunity
	for rows.Next() {
		var r Opportunity
		var engaged int
		if err := rows.Scan(&r.Country, &r.CompanyName, &r.NewestFetched, &engaged); err != nil {
			return nil, err
		}
		r.Country = strings.ToLower(strings.TrimSpace(r.Country))
		r.CompanyName = strings.TrimSpace(r.CompanyName)
		r.NewestFetched = strings.TrimSpace(r.NewestFetched)
		r.Engaged = engaged != 0
		if r.CompanyName == "" {
			continue
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) ReplaceOpportunities(ctx context.Context, userID int, rows []Opportunity) error {
	now := utcNow()
	tx, err := s.conn.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `DELETE FROM user_opportunities WHERE user_id = $1`, userID); err != nil {
		return err
	}
	for _, row := range rows {
		engaged := 0
		if row.Engaged {
			engaged = 1
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO user_opportunities (
				user_id, country, company_name, newest_fetched, updated_at, revealed_job_count, engaged
			) VALUES ($1, $2, $3, $4, $5, 0, $6)
		`, userID, row.Country, row.CompanyName, row.NewestFetched, now, engaged); err != nil {
			return err
		}
	}
	if _, err := tx.Exec(ctx, `
		UPDATE user_preferences SET opportunities_refreshed_at = $1 WHERE user_id = $2
	`, now, userID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (s *Store) ListJobs(ctx context.Context, country, company string) ([]Job, error) {
	rows, err := s.conn.Query(ctx, `
		SELECT COALESCE(mj.idempotency_key, ''), COALESCE(mj.url, ''), COALESCE(mj.title, '')
		FROM companies c
		JOIN matching_jobs mj ON mj.company_id = c.id
		WHERE c.country = $1 AND lower(c.name) = lower($2)
		ORDER BY mj.fetched DESC, mj.title ASC
	`, strings.ToLower(strings.TrimSpace(country)), strings.TrimSpace(company))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Job
	for rows.Next() {
		var j Job
		if err := rows.Scan(&j.Key, &j.URL, &j.Title); err != nil {
			return nil, err
		}
		j.Key = strings.TrimSpace(j.Key)
		j.URL = strings.TrimSpace(j.URL)
		j.Title = strings.TrimSpace(j.Title)
		out = append(out, j)
	}
	return out, rows.Err()
}

func (s *Store) AssignmentMaps(ctx context.Context, userID int, period, country, company string) (assigned, consumed map[string]bool, err error) {
	assigned = map[string]bool{}
	consumed = map[string]bool{}
	rows, err := s.conn.Query(ctx, `
		SELECT job_key, consumed_at
		FROM position_broadcast_assignments
		WHERE user_id = $1 AND period_key = $2 AND country = $3 AND lower(company_name) = lower($4)
	`, userID, period, strings.ToLower(strings.TrimSpace(country)), strings.TrimSpace(company))
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var key string
		var consumedAt *string
		if err := rows.Scan(&key, &consumedAt); err != nil {
			return nil, nil, err
		}
		key = strings.TrimSpace(key)
		if key == "" {
			continue
		}
		assigned[key] = true
		if consumedAt != nil && strings.TrimSpace(*consumedAt) != "" {
			consumed[key] = true
		}
	}
	return assigned, consumed, rows.Err()
}

func (s *Store) InsertAssignment(ctx context.Context, userID int, period, country, company string, job Job) error {
	_, err := s.conn.Exec(ctx, `
		INSERT INTO position_broadcast_assignments (
			user_id, period_key, country, company_name, job_key, job_url, job_title, assigned_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT DO NOTHING
	`, userID, period, strings.ToLower(strings.TrimSpace(country)), strings.TrimSpace(company),
		job.Key, job.URL, job.Title, utcNow())
	return err
}

func (s *Store) UserIDsForCountry(ctx context.Context, country string) ([]int, error) {
	key := strings.ToLower(strings.TrimSpace(country))
	if key == "" {
		return nil, nil
	}
	rows, err := s.conn.Query(ctx, `
		SELECT u.id, p.target_countries_json
		FROM users u
		LEFT JOIN user_preferences p ON p.user_id = u.id
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []int
	for rows.Next() {
		var id int
		var raw *string
		if err := rows.Scan(&id, &raw); err != nil {
			return nil, err
		}
		countries := []string{defaultCountry}
		if raw != nil {
			parsed := parseCountryList(*raw)
			if len(parsed) > 0 {
				countries = parsed
			}
		}
		for _, c := range countries {
			if c == key {
				out = append(out, id)
				break
			}
		}
	}
	return out, rows.Err()
}
