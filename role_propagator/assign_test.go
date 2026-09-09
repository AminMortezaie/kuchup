package rolepropagator

import (
	"testing"
)

func TestReconcileKeepsStickyWhenNewerCompaniesAppear(t *testing.T) {
	cap := 2
	rows := ReconcileSticky(
		[]Opportunity{
			{Country: "germany", CompanyName: "StepStone", NewestFetched: "2026-01-01", Engaged: true},
			{Country: "germany", CompanyName: "OldCo", NewestFetched: "2026-01-02", Engaged: false},
		},
		[]Candidate{
			{Country: "germany", CompanyName: "FlicksBoss", NewestFetched: "2026-08-01", OpenJobCount: 5},
			{Country: "germany", CompanyName: "RedCare", NewestFetched: "2026-07-01", OpenJobCount: 4},
			{Country: "germany", CompanyName: "StepStone", NewestFetched: "2026-06-01", OpenJobCount: 3},
			{Country: "germany", CompanyName: "OldCo", NewestFetched: "2026-05-01", OpenJobCount: 2},
		},
		map[string]bool{"germany": true},
		&cap,
	)
	names := map[string]bool{}
	for _, r := range rows {
		names[r.CompanyName] = true
	}
	if !names["StepStone"] || !names["OldCo"] || names["FlicksBoss"] || len(rows) != 2 {
		t.Fatalf("got %#v", rows)
	}
}

func TestReconcileFillsVacantWithNewestOpen(t *testing.T) {
	cap := 2
	rows := ReconcileSticky(
		[]Opportunity{
			{Country: "germany", CompanyName: "StepStone", NewestFetched: "2026-01-01", Engaged: true},
		},
		[]Candidate{
			{Country: "germany", CompanyName: "FlicksBoss", NewestFetched: "2026-08-01", OpenJobCount: 5},
			{Country: "germany", CompanyName: "StepStone", NewestFetched: "2026-06-01", OpenJobCount: 3},
		},
		map[string]bool{"germany": true},
		&cap,
	)
	names := map[string]bool{}
	for _, r := range rows {
		names[r.CompanyName] = true
	}
	if !names["StepStone"] || !names["FlicksBoss"] || len(rows) != 2 {
		t.Fatalf("got %#v", rows)
	}
}

func TestReconcileDropsEmptyUnengagedButKeepsEngaged(t *testing.T) {
	cap := 2
	rows := ReconcileSticky(
		[]Opportunity{
			{Country: "germany", CompanyName: "Empty", Engaged: false},
			{Country: "germany", CompanyName: "Saved", Engaged: true},
		},
		[]Candidate{
			{Country: "germany", CompanyName: "Fresh", NewestFetched: "2026-08-01", OpenJobCount: 4},
		},
		map[string]bool{"germany": true},
		&cap,
	)
	names := map[string]bool{}
	for _, r := range rows {
		names[r.CompanyName] = true
	}
	if !names["Saved"] || !names["Fresh"] || names["Empty"] {
		t.Fatalf("got %#v", rows)
	}
}

func TestPickJobsCapsAtThreeAndKeepsStickyCap(t *testing.T) {
	jobs := []Job{
		{Key: "a", URL: "u/a", Title: "A"},
		{Key: "b", URL: "u/b", Title: "B"},
		{Key: "c", URL: "u/c", Title: "C"},
		{Key: "d", URL: "u/d", Title: "D"},
	}
	picked := PickJobs(jobs, map[string]bool{}, map[string]bool{}, 3)
	if len(picked) != 3 || picked[0].Key != "a" || picked[2].Key != "c" {
		t.Fatalf("got %#v", picked)
	}
	cap := 10
	ranked := make([]Candidate, 0, 12)
	for i := 0; i < 12; i++ {
		ranked = append(ranked, Candidate{
			Country: "germany", CompanyName: string(rune('A' + i)), NewestFetched: "2026-08-01", OpenJobCount: 1,
		})
	}
	rows := ReconcileSticky(nil, ranked, map[string]bool{"germany": true}, &cap)
	if len(rows) != 10 {
		t.Fatalf("cap: got %d", len(rows))
	}
}

func TestPickReplacementSkipsAssigned(t *testing.T) {
	jobs := []Job{{Key: "a"}, {Key: "b"}, {Key: "c"}}
	got := PickReplacement(jobs, map[string]bool{"a": true, "b": true})
	if got == nil || got.Key != "c" {
		t.Fatalf("got %#v", got)
	}
}
