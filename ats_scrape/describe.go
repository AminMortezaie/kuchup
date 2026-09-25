package atsscrape

import (
	"context"
	"encoding/json"
	"html"
	"os"
	"regexp"
	"strings"
	"sync"
	"time"
)

var (
	greenhouseJobURL   = regexp.MustCompile(`(?i)greenhouse\.io/(?:embed/job_board/)?([^/?#]+)/jobs/(\d+)`)
	greenhouseSlug     = regexp.MustCompile(`(?i)greenhouse\.io/(?:embed/job_board/)?([^/?#]+)`)
	greenhouseJID      = regexp.MustCompile(`[?&]gh_jid=(\d+)`)
	smartRecruitersURL = regexp.MustCompile(`(?i)smartrecruiters\.com/(?:v1/companies/)?([A-Za-z0-9_-]+)(?:/postings)?/(\d+)`)
	htmlTagRE          = regexp.MustCompile(`(?s)<[^>]*>`)
)

type describeRequest struct {
	ATSType  string `json:"ats_type"`
	BoardURL string `json:"board_url"`
	URL      string `json:"url"`
}

type describeResult struct {
	URL             string `json:"url"`
	DescriptionText string `json:"description_text"`
}

func RunDescribe() int {
	var requests []describeRequest
	if err := json.NewDecoder(os.Stdin).Decode(&requests); err != nil {
		return 1
	}
	ctx := context.Background()
	pool := NewHTTPPool(16, 30*time.Second)
	jobs := make([]Job, len(requests))
	groups := map[string][]int{}
	for i, req := range requests {
		jobs[i] = Job{URL: req.URL}
		key := req.ATSType + "\n" + req.BoardURL
		groups[key] = append(groups[key], i)
	}
	var wg sync.WaitGroup
	for key, idxs := range groups {
		ats, board, _ := strings.Cut(key, "\n")
		subset := make([]Job, len(idxs))
		for n, i := range idxs {
			subset[n] = jobs[i]
		}
		wg.Add(1)
		go func(ats, board string, subset []Job, idxs []int) {
			defer wg.Done()
			fillDescriptions(ctx, pool, ats, board, subset)
			for n, i := range idxs {
				jobs[i].DescriptionText = subset[n].DescriptionText
			}
		}(ats, board, subset, idxs)
	}
	wg.Wait()
	out := make([]describeResult, 0)
	for _, job := range jobs {
		if strings.TrimSpace(job.DescriptionText) == "" {
			continue
		}
		out = append(out, describeResult{URL: job.URL, DescriptionText: job.DescriptionText})
	}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		return 1
	}
	return 0
}

func fillDescriptions(ctx context.Context, client getter, ats, boardURL string, jobs []Job) {
	var wg sync.WaitGroup
	for i := range jobs {
		if strings.TrimSpace(jobs[i].DescriptionText) != "" || strings.TrimSpace(jobs[i].URL) == "" {
			continue
		}
		details := descriptionURLs(ats, boardURL, jobs[i].URL)
		if len(details) == 0 {
			continue
		}
		wg.Add(1)
		go func(i int, details []string) {
			defer wg.Done()
			for _, detail := range details {
				if text := fetchDescription(ctx, client, ats, detail); text != "" {
					jobs[i].DescriptionText = text
					return
				}
			}
		}(i, details)
	}
	wg.Wait()
}

func descriptionURLs(ats, boardURL, jobURL string) []string {
	ats = strings.ToLower(strings.TrimSpace(ats))
	switch ats {
	case "greenhouse", "greenhouse_eu":
		return greenhouseDetailURLs(ats, boardURL, jobURL)
	case "smartrecruiters":
		match := smartRecruitersURL.FindStringSubmatch(jobURL)
		if match == nil {
			return nil
		}
		return []string{"https://api.smartrecruiters.com/v1/companies/" + match[1] + "/postings/" + match[2]}
	default:
		return nil
	}
}

func greenhouseDetailURLs(ats, boardURL, jobURL string) []string {
	slug, id := "", ""
	if match := greenhouseJobURL.FindStringSubmatch(jobURL); match != nil && match[1] != "embed" && match[1] != "jobs" {
		slug, id = match[1], match[2]
	}
	if id == "" {
		if match := greenhouseJID.FindStringSubmatch(jobURL); match != nil {
			id = match[1]
		}
	}
	if slug == "" {
		if match := greenhouseSlug.FindStringSubmatch(boardURL); match != nil && match[1] != "embed" && match[1] != "jobs" {
			slug = match[1]
		}
	}
	if slug == "" || id == "" {
		return nil
	}
	hosts := []string{"boards-api.greenhouse.io"}
	blob := strings.ToLower(boardURL + " " + jobURL)
	if ats == "greenhouse_eu" || strings.Contains(blob, "eu.greenhouse") {
		hosts = append([]string{"boards-api.greenhouse.io"}, hosts...)
	}
	out := make([]string, 0, len(hosts))
	seen := map[string]struct{}{}
	for _, host := range hosts {
		raw := "https://" + host + "/v1/boards/" + slug + "/jobs/" + id
		if _, ok := seen[raw]; ok {
			continue
		}
		seen[raw] = struct{}{}
		out = append(out, raw)
	}
	return out
}

func fetchDescription(ctx context.Context, client getter, ats, detail string) string {
	res, err := getURL(ctx, client, detail, nil)
	if err != nil || !res.ok() {
		return ""
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return ""
	}
	switch strings.ToLower(strings.TrimSpace(ats)) {
	case "smartrecruiters":
		return smartRecruitersText(payload)
	default:
		return strings.TrimSpace(html.UnescapeString(asString(payload["content"])))
	}
}

func smartRecruitersText(payload map[string]any) string {
	jobAd := asMap(payload["jobAd"])
	sections := asMap(jobAd["sections"])
	var parts []string
	for _, key := range []string{"companyDescription", "jobDescription", "qualifications", "additionalInformation"} {
		section := asMap(sections[key])
		text := strings.TrimSpace(htmlTagRE.ReplaceAllString(asString(section["text"]), " "))
		if text != "" {
			parts = append(parts, text)
		}
	}
	return strings.TrimSpace(strings.Join(parts, "\n"))
}
