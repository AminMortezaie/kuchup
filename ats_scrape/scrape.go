package atsscrape

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"time"
)

var ErrUnsupported = errors.New("unsupported ats")

type Request struct {
	ATSType    string `json:"ats_type"`
	ATSURL     string `json:"ats_url"`
	CareersURL string `json:"careers_url"`
	Name       string `json:"name"`
}

func (r Request) boardURL() string {
	if url := strings.TrimSpace(r.ATSURL); url != "" {
		return url
	}
	return strings.TrimSpace(r.CareersURL)
}

func (r Request) pageURL() string {
	raw := strings.TrimSpace(r.CareersURL)
	if raw == "" {
		raw = strings.TrimSpace(r.ATSURL)
	}
	if i := strings.IndexByte(raw, '#'); i >= 0 {
		raw = raw[:i]
	}
	return strings.TrimSpace(raw)
}

type fetchFunc func(context.Context, getter, Request) ([]Job, error)

func fetchers() map[string]fetchFunc {
	return map[string]fetchFunc{
		"ashby":           fetchAshby,
		"applytojob":      fetchApplyToJob,
		"bamboohr":        fetchBamboo,
		"bol":             fetchBol,
		"deel":            fetchDeel,
		"epam":            fetchEPAM,
		"greenhouse":      fetchGreenhouse,
		"greenhouse_eu":   fetchGreenhouse,
		"hirehive":        fetchHireHive,
		"job_shop":        fetchJobShop,
		"joblet":          fetchJoblet,
		"join":            fetchJoin,
		"kake":            fetchKake,
		"lever":           fetchLever,
		"lever_eu":        fetchLever,
		"movingimage":     fetchMovingImage,
		"personio":        fetchPersonio,
		"pinpointhq":      fetchPinpoint,
		"project_a":       fetchProjectA,
		"recruitee":       fetchRecruitee,
		"remotedxb":       fetchRemoteDXB,
		"remoteok":        fetchRemoteOK,
		"rss":             fetchRSS,
		"smartrecruiters": fetchSmartRecruiters,
		"successfactors":  fetchSuccessFactors,
		"teamtailor":      fetchTeamtailor,
		"workable":        fetchWorkable,
		"workday":         fetchWorkday,
		"generic":         fetchGeneric,
	}
}

func Scrape(ctx context.Context, client getter, req Request) ([]Job, error) {
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	ats := strings.ToLower(strings.TrimSpace(req.ATSType))
	if ats == "" {
		ats = "generic"
	}
	fn, ok := fetchers()[ats]
	if !ok {
		return nil, ErrUnsupported
	}
	jobs, err := fn(ctx, client, req)
	if err != nil {
		return nil, err
	}
	if jobs == nil {
		jobs = []Job{}
	}
	return jobs, nil
}
