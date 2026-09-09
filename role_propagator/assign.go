package rolepropagator

import (
	"sort"
	"strings"
)

type Candidate struct {
	Country       string
	CompanyName   string
	NewestFetched string
	OpenJobCount  int
}

type Opportunity struct {
	Country       string
	CompanyName   string
	NewestFetched string
	Engaged       bool
}

type Job struct {
	Key   string
	URL   string
	Title string
}

func companyKey(country, name string) [2]string {
	return [2]string{strings.ToLower(strings.TrimSpace(country)), strings.ToLower(strings.TrimSpace(name))}
}

func ReconcileSticky(existing []Opportunity, rankedOpen []Candidate, prefsCountries map[string]bool, cap *int) []Opportunity {
	byOpen := map[[2]string]Candidate{}
	for _, c := range rankedOpen {
		if c.OpenJobCount <= 0 {
			continue
		}
		key := companyKey(c.Country, c.CompanyName)
		if !prefsCountries[key[0]] {
			continue
		}
		byOpen[key] = c
	}
	kept := make([]Opportunity, 0, len(existing))
	keptKeys := map[[2]string]bool{}
	for _, row := range existing {
		key := companyKey(row.Country, row.CompanyName)
		if !prefsCountries[key[0]] {
			continue
		}
		if !row.Engaged {
			if _, ok := byOpen[key]; !ok {
				continue
			}
		}
		kept = append(kept, row)
		keptKeys[key] = true
	}
	if cap != nil && len(kept) > *cap {
		sort.Slice(kept, func(i, j int) bool {
			if kept[i].Engaged != kept[j].Engaged {
				return kept[i].Engaged
			}
			if kept[i].NewestFetched != kept[j].NewestFetched {
				return kept[i].NewestFetched > kept[j].NewestFetched
			}
			return strings.ToLower(kept[i].CompanyName) > strings.ToLower(kept[j].CompanyName)
		})
		kept = kept[:*cap]
		keptKeys = map[[2]string]bool{}
		for _, r := range kept {
			keptKeys[companyKey(r.Country, r.CompanyName)] = true
		}
	}
	ranked := make([]Candidate, 0, len(byOpen))
	for _, c := range byOpen {
		ranked = append(ranked, c)
	}
	sort.Slice(ranked, func(i, j int) bool {
		if ranked[i].NewestFetched != ranked[j].NewestFetched {
			return ranked[i].NewestFetched > ranked[j].NewestFetched
		}
		return strings.ToLower(ranked[i].CompanyName) > strings.ToLower(ranked[j].CompanyName)
	})
	for _, candidate := range ranked {
		if cap != nil && len(kept) >= *cap {
			break
		}
		key := companyKey(candidate.Country, candidate.CompanyName)
		if keptKeys[key] {
			continue
		}
		kept = append(kept, Opportunity{
			Country:       candidate.Country,
			CompanyName:   candidate.CompanyName,
			NewestFetched: candidate.NewestFetched,
		})
		keptKeys[key] = true
	}
	out := make([]Opportunity, 0, len(kept))
	for _, row := range kept {
		key := companyKey(row.Country, row.CompanyName)
		newest := row.NewestFetched
		if c, ok := byOpen[key]; ok && c.NewestFetched != "" {
			newest = c.NewestFetched
		}
		out = append(out, Opportunity{
			Country:       row.Country,
			CompanyName:   row.CompanyName,
			NewestFetched: newest,
			Engaged:       row.Engaged,
		})
	}
	return out
}

func PickJobs(jobs []Job, assigned, consumed map[string]bool, activeTarget int) []Job {
	target := activeTarget - len(consumed)
	if target < 0 {
		target = 0
	}
	active := 0
	for _, job := range jobs {
		if job.Key != "" && assigned[job.Key] && !consumed[job.Key] {
			active++
		}
	}
	var out []Job
	for _, job := range jobs {
		if active >= target {
			break
		}
		if job.Key == "" || assigned[job.Key] {
			continue
		}
		out = append(out, job)
		assigned[job.Key] = true
		active++
	}
	return out
}

func PickReplacement(jobs []Job, assigned map[string]bool) *Job {
	for i := range jobs {
		if jobs[i].Key == "" || assigned[jobs[i].Key] {
			continue
		}
		return &jobs[i]
	}
	return nil
}
