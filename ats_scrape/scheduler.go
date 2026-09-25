package atsscrape

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

const defaultScheduleHours = 6.0

func RunScheduler() int {
	once := flag.Bool("once", false, "run one fetch cycle and exit")
	flag.Parse()

	ctx := context.Background()
	store, err := OpenStore(ctx)
	if err != nil {
		log.Printf("scheduler: %v", err)
		return 1
	}
	defer store.Close()

	if err := store.ReapStaleRunningRuns(ctx, countryTimeout()); err != nil {
		log.Printf("scheduler: stale run reap: %v", err)
	}

	if !scheduleEnabled() {
		log.Print("FETCH_SCHEDULE_ENABLED is off")
		return 1
	}

	runCycle := func() {
		if err := runFetchCycle(ctx, store); err != nil {
			log.Printf("scheduler: cycle failed: %v", err)
		}
	}

	if *once {
		if err := runFetchCycle(ctx, store); err != nil {
			log.Printf("scheduler: cycle failed: %v", err)
			return 1
		}
		return 0
	}

	interval := time.Duration(scheduleIntervalHours()*3600) * time.Second
	log.Printf("fetch scheduler started (interval=%s pool=%d)", interval, poolSize())
	for {
		runCycle()
		time.Sleep(interval)
	}
}

func scheduleEnabled() bool {
	raw := strings.ToLower(strings.TrimSpace(os.Getenv("FETCH_SCHEDULE_ENABLED")))
	return raw != "" && raw != "0" && raw != "false" && raw != "no"
}

func scheduleIntervalHours() float64 {
	raw := strings.TrimSpace(os.Getenv("FETCH_SCHEDULE_INTERVAL_HOURS"))
	if raw == "" {
		return defaultScheduleHours
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || value < 0.25 {
		return defaultScheduleHours
	}
	return value
}

func poolSize() int {
	raw := strings.TrimSpace(os.Getenv("FETCH_HTTP_POOL_SIZE"))
	if raw == "" {
		return 4
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 1 {
		return 4
	}
	if n > maxPoolSize {
		return maxPoolSize
	}
	return n
}

func scheduleCountries(ctx context.Context, store *Store) ([]string, error) {
	raw := strings.TrimSpace(os.Getenv("FETCH_SCHEDULE_COUNTRIES"))
	if raw != "" {
		seen := map[string]struct{}{}
		out := make([]string, 0)
		for _, part := range strings.Split(raw, ",") {
			key := strings.ToLower(strings.TrimSpace(part))
			if key == "" {
				continue
			}
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			out = append(out, key)
		}
		if len(out) == 0 {
			return nil, fmt.Errorf("FETCH_SCHEDULE_COUNTRIES is empty")
		}
		return out, nil
	}
	return store.DefaultCountries(ctx)
}

func attachedRun() (int64, string, bool) {
	raw := strings.TrimSpace(os.Getenv("FETCH_RUN_ID"))
	if raw == "" {
		return 0, "", false
	}
	runID, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || runID <= 0 {
		return 0, "", false
	}
	country := strings.ToLower(strings.TrimSpace(os.Getenv("FETCH_SCHEDULE_COUNTRIES")))
	if country == "" || strings.Contains(country, ",") {
		return 0, "", false
	}
	return runID, country, true
}

func runFetchCycle(ctx context.Context, store *Store) error {
	if runID, country, ok := attachedRun(); ok {
		return runAttached(ctx, store, runID, country)
	}
	if running, err := store.FetchIsRunning(ctx); err != nil {
		return err
	} else if running {
		log.Print("scheduled fetch skipped: another fetch is already running")
		return nil
	}

	userID, err := store.ResolveSchedulerUserID(ctx)
	if err != nil {
		return err
	}
	countries, err := scheduleCountries(ctx, store)
	if err != nil {
		return err
	}
	workers := poolSize()
	httpPool := NewHTTPPool(workers, 30*time.Second)

	log.Printf("scheduled fetch cycle starting countries=%d pool=%d", len(countries), workers)

	for _, country := range countries {
		if running, err := store.FetchIsRunning(ctx); err != nil {
			return err
		} else if running {
			log.Printf("scheduled fetch stopped: fetch became busy at %s", country)
			break
		}
		if err := runCountry(ctx, store, httpPool, userID, country, workers); err != nil {
			log.Printf("scheduled fetch could not finish %s: %v", country, err)
			continue
		}
		log.Printf("scheduled country fetch finished country=%s", country)
	}
	return nil
}

func countryTimeout() time.Duration {
	raw := strings.TrimSpace(os.Getenv("FETCH_COUNTRY_TIMEOUT_SECONDS"))
	if raw == "" {
		return 2700 * time.Second
	}
	seconds, err := strconv.Atoi(raw)
	if err != nil || seconds < 60 {
		return 2700 * time.Second
	}
	return time.Duration(seconds) * time.Second
}

func runCountry(ctx context.Context, store *Store, httpPool *HTTPPool, userID int64, countryKey string, workers int) error {
	companies, err := store.ListHTTPCompanies(ctx, countryKey)
	if err != nil {
		return err
	}
	if len(companies) == 0 {
		return fmt.Errorf("no HTTP companies for %s", countryKey)
	}

	runID, err := store.CreateFetchRun(ctx, userID, countryKey, workers)
	if err != nil {
		return err
	}
	return fetchCompanies(ctx, store, httpPool, runID, companies)
}

func runAttached(ctx context.Context, store *Store, runID int64, countryKey string) error {
	companies, err := store.ListHTTPCompanies(ctx, countryKey)
	if err != nil {
		return err
	}
	if ats := strings.TrimSpace(os.Getenv("FETCH_ATS_TYPE")); ats != "" {
		matched := make([]WorkCompany, 0, len(companies))
		for _, company := range companies {
			if strings.EqualFold(company.ATSType, ats) {
				matched = append(matched, company)
			}
		}
		companies = matched
	}
	if len(companies) == 0 {
		_ = store.FailRun(ctx, runID, "no HTTP companies for "+countryKey)
		return fmt.Errorf("no HTTP companies for %s", countryKey)
	}
	return fetchCompanies(ctx, store, NewHTTPPool(poolSize(), 30*time.Second), runID, companies)
}

func fetchCompanies(ctx context.Context, store *Store, httpPool *HTTPPool, runID int64, companies []WorkCompany) (err error) {
	runClosed := false
	defer func() {
		if runClosed {
			return
		}
		msg := "country fetch interrupted"
		if err != nil {
			msg = err.Error()
		}
		if failErr := store.FailRun(ctx, runID, msg); failErr != nil {
			log.Printf("scheduler: failed to close run %d: %v", runID, failErr)
		}
	}()

	if err = store.InsertWorkRows(ctx, runID, companies); err != nil {
		return err
	}
	total := len(companies)
	if err = store.UpdateProgress(ctx, runID, 0, total, "", "fetching"); err != nil {
		return err
	}

	var done atomic.Int32
	var wg sync.WaitGroup
	errCh := make(chan error, total)

	for _, company := range companies {
		company := company
		wg.Add(1)
		go func() {
			defer wg.Done()
			if scrapeErr := scrapeCompany(ctx, store, httpPool, runID, company); scrapeErr != nil {
				errCh <- scrapeErr
			}
			current := int(done.Add(1))
			_ = store.UpdateProgress(ctx, runID, current, total, company.Name, "fetching")
		}()
	}
	wg.Wait()
	close(errCh)
	for companyErr := range errCh {
		log.Printf("company scrape error run=%d: %v", runID, companyErr)
		if err == nil {
			err = companyErr
		}
	}
	if err != nil {
		return err
	}

	finished := int(done.Load())
	if failErr := store.FinalizeRun(ctx, runID, finished, total); failErr != nil {
		return failErr
	}
	runClosed = true
	return nil
}

func signalCompanyReady(id int64) {
	if id <= 0 {
		return
	}
	fmt.Fprintf(os.Stdout, "FETCH_READY %d\n", id)
	_ = os.Stdout.Sync()
}

func scrapeCompany(ctx context.Context, store *Store, httpPool *HTTPPool, runID int64, company WorkCompany) error {
	req := Request{
		ATSType:    company.ATSType,
		ATSURL:     company.ATSURL,
		CareersURL: company.CareersURL,
		Name:       company.Name,
	}
	jobs, scrapeErr := Scrape(ctx, httpPool, req)
	var id int64
	var err error
	switch {
	case scrapeErr != nil:
		id, err = store.InsertResult(ctx, runID, company.ID, resultError, scrapeErr.Error(), nil)
	case len(jobs) == 0:
		id, err = store.InsertResult(ctx, runID, company.ID, resultEmpty, "", jobs)
	default:
		id, err = store.InsertResult(ctx, runID, company.ID, resultOK, "", jobs)
	}
	if err != nil {
		return err
	}
	signalCompanyReady(id)
	return nil
}
