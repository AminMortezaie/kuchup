package atsscrape

import (
	"context"
	"fmt"
	"net/url"
	"regexp"
	"strings"
)

func fetchGreenhouse(ctx context.Context, client getter, req Request) ([]Job, error) {
	slug := lastSlug(req.boardURL())
	if slug == "" || slug == "embed" || slug == "jobs" {
		return []Job{}, nil
	}
	api := "https://boards-api.greenhouse.io/v1/boards/" + url.PathEscape(slug) + "/jobs"
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range asList(payload["jobs"]) {
		item := asMap(row)
		location := ""
		if loc := asMap(item["location"]); loc != nil {
			location = asString(loc["name"])
		}
		job, ok := listingJob(asString(item["title"]), asString(item["absolute_url"]), location, "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func fetchLever(ctx context.Context, client getter, req Request) ([]Job, error) {
	board := req.boardURL()
	slug := lastSlug(board)
	if slug == "" {
		return []Job{}, nil
	}
	host := "api.lever.co"
	if strings.Contains(board, "eu.lever") {
		host = "jobs.eu.lever.co"
	}
	api := fmt.Sprintf("https://%s/v0/postings/%s?mode=json", host, url.PathEscape(slug))
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	rows, err := asJSONList(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range rows {
		item := asMap(row)
		location := asString(asMap(item["categories"])["location"])
		rawURL := asString(item["hostedUrl"])
		if rawURL == "" {
			rawURL = board
		}
		job, ok := listingJob(asString(item["text"]), rawURL, location, "", asString(item["descriptionPlain"]), nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func fetchAshby(ctx context.Context, client getter, req Request) ([]Job, error) {
	slug := lastSlug(req.boardURL())
	if slug == "" {
		return []Job{}, nil
	}
	api := "https://api.ashbyhq.com/posting-api/job-board/" + url.PathEscape(slug)
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	return parseAshbyJobs(payload, req.boardURL()), nil
}

func parseAshbyJobs(payload map[string]any, atsURL string) []Job {
	jobs := make([]Job, 0)
	for _, row := range asList(payload["jobs"]) {
		item := asMap(row)
		rawURL := asString(item["jobUrl"])
		if rawURL == "" {
			rawURL = atsURL
		}
		labels := ashbyLocationLabels(item)
		location := ""
		if len(labels) > 0 {
			location = labels[0]
		}
		job, ok := listingJob(asString(item["title"]), rawURL, location, "", "", labels)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func ashbyLocationLabel(row map[string]any) string {
	location := row["location"]
	if location == nil {
		location = row["locationName"]
	}
	switch v := location.(type) {
	case string:
		return strings.TrimSpace(v)
	case map[string]any:
		if name := asString(v["name"]); name != "" {
			return name
		}
		return asString(v["city"])
	default:
		return ""
	}
}

func ashbyLocationLabels(row map[string]any) []string {
	labels := []string{}
	seen := map[string]struct{}{}
	add := func(text string) {
		text = strings.TrimSpace(text)
		if text == "" {
			return
		}
		key := strings.ToLower(text)
		if _, ok := seen[key]; ok {
			return
		}
		seen[key] = struct{}{}
		labels = append(labels, text)
	}
	add(ashbyLocationLabel(row))
	for _, item := range asList(row["secondaryLocations"]) {
		switch v := item.(type) {
		case map[string]any:
			add(ashbyLocationLabel(v))
			address := asMap(v["address"])
			postal := asMap(address["postalAddress"])
			if postal == nil {
				postal = address
			}
			add(asString(postal["addressLocality"]))
			add(asString(postal["addressCountry"]))
		default:
			add(asString(item))
		}
	}
	if len(labels) == 0 {
		return nil
	}
	return labels
}

func fetchRecruitee(ctx context.Context, client getter, req Request) ([]Job, error) {
	api := recruiteeOffersURL(req.boardURL())
	if api == "" {
		return []Job{}, nil
	}
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range asList(payload["offers"]) {
		item := asMap(row)
		rawURL := asString(item["careers_url"])
		if rawURL == "" {
			rawURL = req.boardURL()
		}
		job, ok := listingJob(asString(item["title"]), rawURL, recruiteeLocation(item), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func recruiteeOffersURL(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	if !strings.Contains(raw, "://") && !strings.Contains(raw, ".") {
		return "https://" + raw + ".recruitee.com/api/offers/"
	}
	if !strings.Contains(raw, "://") {
		raw = "https://" + raw
	}
	parsed, err := url.Parse(raw)
	if err != nil || parsed.Hostname() == "" {
		return ""
	}
	host := strings.ToLower(parsed.Hostname())
	if strings.HasSuffix(host, ".recruitee.com") {
		slug := strings.Split(host, ".")[0]
		if slug == "" || slug == "www" || slug == "api" || slug == "careers" || slug == "app" {
			return ""
		}
		return "https://" + slug + ".recruitee.com/api/offers/"
	}
	scheme := parsed.Scheme
	if scheme == "" {
		scheme = "https"
	}
	return scheme + "://" + host + "/api/offers/"
}

func recruiteeLocation(offer map[string]any) string {
	if location := asString(offer["location"]); location != "" {
		return location
	}
	return joinUnique(asString(offer["city"]), asString(offer["country"]))
}

var smartRecruitersIDPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)`),
	regexp.MustCompile(`(?i)careers\.smartrecruiters\.com/([A-Za-z0-9_-]+)`),
	regexp.MustCompile(`(?i)jobs\.smartrecruiters\.com/oneclick-ui/company/([A-Za-z0-9_-]+)`),
	regexp.MustCompile(`(?i)jobs\.smartrecruiters\.com/([A-Za-z0-9_-]+)`),
}

func smartRecruitersCompanyID(raw string) string {
	cleaned := strings.Split(raw, "?")[0]
	cleaned = strings.TrimRight(cleaned, "/")
	for _, pattern := range smartRecruitersIDPatterns {
		if m := pattern.FindStringSubmatch(cleaned); m != nil {
			return m[1]
		}
	}
	parts := strings.Split(cleaned, "/")
	slug := parts[len(parts)-1]
	if slug == "" || strings.EqualFold(slug, "postings") {
		return ""
	}
	return slug
}

func fetchSmartRecruiters(ctx context.Context, client getter, req Request) ([]Job, error) {
	companyID := smartRecruitersCompanyID(req.boardURL())
	if companyID == "" {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	offset := 0
	for {
		api := fmt.Sprintf(
			"https://api.smartrecruiters.com/v1/companies/%s/postings?limit=100&offset=%d&include=locations",
			url.PathEscape(companyID),
			offset,
		)
		res, err := getURL(ctx, client, api, nil)
		if err != nil {
			return nil, err
		}
		if err := res.requireOK(); err != nil {
			return nil, err
		}
		payload, err := asJSONMap(res.Body)
		if err != nil {
			return nil, err
		}
		content := asList(payload["content"])
		for _, row := range content {
			item := asMap(row)
			jobID := asString(item["id"])
			jobURL := fmt.Sprintf("https://jobs.smartrecruiters.com/%s/%s", companyID, jobID)
			job, ok := listingJob(asString(item["name"]), jobURL, smartRecruitersLocation(asMap(item["location"])), "", "", nil)
			if ok {
				jobs = append(jobs, job)
			}
		}
		offset += len(content)
		total := offset
		if raw := asString(payload["totalFound"]); raw != "" {
			fmt.Sscanf(raw, "%d", &total)
		}
		if len(content) == 0 || offset >= total {
			break
		}
	}
	return jobs, nil
}

func smartRecruitersLocation(raw map[string]any) string {
	if raw == nil {
		return ""
	}
	if full := asString(raw["fullLocation"]); full != "" {
		return full
	}
	if full := asString(raw["full_location"]); full != "" {
		return full
	}
	return joinUnique(asString(raw["city"]), asString(raw["country"]))
}

var workableSlugRE = regexp.MustCompile(`(?i)apply\.workable\.com/(?:api/v\d+/accounts/)?([a-z0-9-]+)`)

func fetchWorkable(ctx context.Context, client getter, req Request) ([]Job, error) {
	m := workableSlugRE.FindStringSubmatch(req.boardURL())
	if m == nil || strings.EqualFold(m[1], "api") {
		return []Job{}, nil
	}
	slug := m[1]
	api := "https://apply.workable.com/api/v2/accounts/" + slug + "/jobs"
	res, err := postJSON(ctx, client, api, map[string]any{
		"query":      "",
		"location":   []any{},
		"department": []any{},
		"worktype":   []any{},
		"remote":     []any{},
	}, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range asList(payload["results"]) {
		item := asMap(row)
		shortcode := asString(item["shortcode"])
		jobURL := fmt.Sprintf("https://apply.workable.com/%s/j/%s/", slug, shortcode)
		job, ok := listingJob(asString(item["title"]), jobURL, workableLocation(asMap(item["location"])), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func workableLocation(raw map[string]any) string {
	if raw == nil {
		return ""
	}
	return joinUnique(asString(raw["city"]), asString(raw["region"]), asString(raw["country"]))
}

var pinpointSlugRE = regexp.MustCompile(`(?i)https?://([a-z0-9-]+)\.pinpointhq\.com`)

func fetchPinpoint(ctx context.Context, client getter, req Request) ([]Job, error) {
	m := pinpointSlugRE.FindStringSubmatch(req.boardURL())
	if m == nil {
		return []Job{}, nil
	}
	api := "https://" + m[1] + ".pinpointhq.com/postings.json"
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range asList(payload["data"]) {
		item := asMap(row)
		job, ok := listingJob(asString(item["title"]), asString(item["url"]), pinpointLocation(item), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func pinpointLocation(posting map[string]any) string {
	loc := asMap(posting["location"])
	if loc == nil {
		return ""
	}
	parts := []string{}
	seen := map[string]struct{}{}
	for _, raw := range []string{asString(loc["city"]), asString(loc["province"])} {
		if raw == "" || !hasAlnum(raw) {
			continue
		}
		key := strings.ToLower(raw)
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		parts = append(parts, raw)
	}
	return strings.Join(parts, ", ")
}

func hasAlnum(text string) bool {
	for _, r := range text {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			return true
		}
	}
	return false
}

func fetchBamboo(ctx context.Context, client getter, req Request) ([]Job, error) {
	raw := strings.TrimRight(req.boardURL(), "/")
	if raw == "" {
		return []Job{}, nil
	}
	if !strings.HasSuffix(raw, "/list") {
		if strings.HasSuffix(raw, "/careers") {
			raw += "/list"
		} else {
			raw += "/careers/list"
		}
	}
	res, err := getURL(ctx, client, raw, map[string]string{"Accept": "application/json"})
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	base := strings.TrimSuffix(raw, "/list")
	jobs := make([]Job, 0)
	for _, row := range asList(payload["result"]) {
		item := asMap(row)
		jobID := asString(item["id"])
		job, ok := listingJob(asString(item["jobOpeningName"]), base+"/"+jobID, bambooLocation(asMap(item["location"])), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func bambooLocation(raw map[string]any) string {
	if raw == nil {
		return ""
	}
	return joinUnique(asString(raw["city"]), asString(raw["region"]), asString(raw["country"]))
}

func fetchHireHive(ctx context.Context, client getter, req Request) ([]Job, error) {
	base := strings.TrimRight(req.boardURL(), "/")
	api := base
	if !strings.HasSuffix(base, "/api/v1/jobs") {
		api = base + "/api/v1/jobs"
	}
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil, err
	}
	jobs := make([]Job, 0)
	for _, row := range asList(payload["jobs"]) {
		item := asMap(row)
		rawURL := asString(item["hostedUrl"])
		if rawURL == "" {
			rawURL = base
		}
		job, ok := listingJob(asString(item["title"]), rawURL, "", "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

const defaultRemoteOK = "https://remoteok.com/api?tags=dev"

var remoteOKDevTags = map[string]struct{}{
	"dev": {}, "engineering": {}, "software": {}, "engineer": {}, "backend": {},
	"frontend": {}, "fullstack": {}, "full-stack": {}, "devops": {}, "sre": {},
	"golang": {}, "python": {}, "java": {}, "javascript": {}, "typescript": {},
	"kotlin": {}, "rust": {}, "api": {}, "infra": {}, "infrastructure": {}, "platform": {},
}

func fetchRemoteOK(ctx context.Context, client getter, req Request) ([]Job, error) {
	api := remoteOKURL(req.boardURL())
	res, err := getURL(ctx, client, api, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	rows, err := asJSONList(res.Body)
	if err != nil {
		return nil, err
	}
	return parseRemoteOK(rows, api), nil
}

func remoteOKURL(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return defaultRemoteOK
	}
	parsed, err := url.Parse(raw)
	if err != nil || parsed.Scheme == "" {
		return defaultRemoteOK
	}
	path := strings.TrimRight(parsed.Path, "/")
	if path == "" || path == "/api" {
		if parsed.RawQuery != "" {
			return "https://remoteok.com/api?" + parsed.RawQuery
		}
		return "https://remoteok.com/api"
	}
	if strings.Contains(strings.ToLower(parsed.Host), "remoteok.com") {
		return raw
	}
	return defaultRemoteOK
}

func parseRemoteOK(rows []any, boardURL string) []Job {
	wanted := remoteOKTags(boardURL)
	jobs := make([]Job, 0)
	for _, row := range rows {
		item := asMap(row)
		if item == nil {
			continue
		}
		if _, legal := item["legal"]; legal {
			continue
		}
		if _, updated := item["last_updated"]; updated {
			if _, hasPosition := item["position"]; !hasPosition {
				continue
			}
		}
		title := asString(item["position"])
		if title == "" {
			title = asString(item["title"])
		}
		rawURL := asString(item["url"])
		if rawURL == "" {
			rawURL = asString(item["apply_url"])
		}
		employer := asString(item["company"])
		if !remoteOKTagsMatch(asList(item["tags"]), wanted) {
			continue
		}
		location := strings.TrimRight(asString(item["location"]), ",")
		job, ok := listingJob(title, rawURL, location, employer, plainText(asString(item["description"])), nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func remoteOKTags(raw string) map[string]struct{} {
	parsed, err := url.Parse(remoteOKURL(raw))
	if err != nil {
		return nil
	}
	query := parsed.Query()
	tags := map[string]struct{}{}
	for _, key := range []string{"tag", "tags"} {
		for _, value := range query[key] {
			for _, part := range strings.Split(value, ",") {
				tag := strings.ToLower(strings.TrimSpace(part))
				if tag != "" {
					tags[tag] = struct{}{}
				}
			}
		}
	}
	return tags
}

func remoteOKTagsMatch(jobTags []any, wanted map[string]struct{}) bool {
	if len(wanted) == 0 {
		return true
	}
	have := map[string]struct{}{}
	for _, tag := range jobTags {
		text := strings.ToLower(strings.TrimSpace(asString(tag)))
		if text != "" {
			have[text] = struct{}{}
		}
	}
	for tag := range have {
		if _, ok := wanted[tag]; ok {
			return true
		}
	}
	devOnly := true
	for tag := range wanted {
		if _, ok := remoteOKDevTags[tag]; !ok {
			devOnly = false
			break
		}
	}
	if !devOnly {
		return false
	}
	for tag := range have {
		if _, ok := remoteOKDevTags[tag]; ok {
			return true
		}
	}
	return false
}

const bolCareersAPI = "https://careers.bol.com/api/v1/jobs/"

func fetchBol(ctx context.Context, client getter, req Request) ([]Job, error) {
	careers := strings.TrimSpace(req.CareersURL)
	if careers == "" {
		careers = req.boardURL()
	}
	prefix := "https://careers.bol.com/en/jobs"
	if parsed, err := url.Parse(careers); err == nil && strings.HasPrefix(strings.ToLower(parsed.Path), "/nl/") {
		prefix = "https://careers.bol.com/nl/vacatures"
	}
	headers := map[string]string{
		"Accept":       "application/json",
		"Content-Type": "application/json",
		"Referer":      careers,
	}
	if headers["Referer"] == "" {
		headers["Referer"] = "https://careers.bol.com/en/jobs/"
	}
	jobs := make([]Job, 0)
	total := 0
	for page := 1; page <= 100; page++ {
		res, err := postJSON(ctx, client, bolCareersAPI, map[string]any{
			"page":              page,
			"jobFamily":         []any{},
			"expertise":         []any{},
			"yearsOfExperience": []any{},
			"educationLevel":    []any{},
			"language":          []any{},
		}, headers)
		if err != nil {
			return nil, err
		}
		if err := res.requireOK(); err != nil {
			return nil, err
		}
		payload, err := asJSONMap(res.Body)
		if err != nil {
			return nil, err
		}
		if success, ok := payload["success"].(bool); ok && !success {
			break
		}
		batch := parseBolHits(payload, prefix)
		if len(batch) == 0 {
			break
		}
		jobs = append(jobs, batch...)
		if total == 0 {
			total = bolTotal(payload)
		}
		if total > 0 && len(jobs) >= total {
			break
		}
		if len(batch) < 10 {
			break
		}
	}
	return jobs, nil
}

func parseBolHits(data map[string]any, prefix string) []Job {
	hits := asList(asMap(data["hits"])["hits"])
	if hits == nil {
		hits = asList(asMap(asMap(data["results"])["hits"])["hits"])
	}
	jobs := make([]Job, 0)
	base := strings.TrimRight(prefix, "/")
	for _, hit := range hits {
		src := asMap(asMap(hit)["_source"])
		title := asString(src["title"])
		if title == "" {
			title = asString(src["publicatienaam"])
		}
		if title == "" {
			title = asString(src["post_title"])
		}
		if title == "" {
			continue
		}
		jobURL := base + "/"
		if id := asString(src["id"]); id != "" {
			jobURL = base + "/_/" + id + "/"
		} else if slug := asString(src["slug"]); strings.HasPrefix(slug, "/") {
			jobURL = "https://careers.bol.com" + slug
		} else if slug != "" {
			jobURL = slug
		}
		job, ok := listingJob(title, jobURL, bolOffice(src["office"]), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func bolOffice(raw any) string {
	switch v := raw.(type) {
	case map[string]any:
		if label := asString(v["label"]); label != "" {
			return label
		}
		return asString(v["name"])
	case string:
		return strings.TrimSpace(v)
	default:
		return ""
	}
}

func bolTotal(data map[string]any) int {
	total := asMap(data["hits"])["total"]
	switch v := total.(type) {
	case map[string]any:
		return atoi(asString(v["value"]))
	default:
		if text := asString(total); text != "" {
			return atoi(text)
		}
	}
	legacy := asMap(asMap(asMap(data["results"])["hits"])["total"])
	if legacy != nil {
		return atoi(asString(legacy["value"]))
	}
	return 0
}

func atoi(raw string) int {
	n := 0
	fmt.Sscanf(strings.TrimSpace(raw), "%d", &n)
	return n
}

func fetchWorkday(ctx context.Context, client getter, req Request) ([]Job, error) {
	api, base := workdayAPIAndBase(req.boardURL())
	if api == "" || base == "" {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	offset := 0
	limit := 20
	total := -1
	for offset <= 2000 {
		res, err := postJSON(ctx, client, api, map[string]any{
			"appliedFacets": map[string]any{},
			"limit":         limit,
			"offset":        offset,
			"searchText":    "",
		}, map[string]string{"Content-Type": "application/json"})
		if err != nil {
			return nil, err
		}
		if err := res.requireOK(); err != nil {
			return nil, err
		}
		payload, err := asJSONMap(res.Body)
		if err != nil {
			return nil, err
		}
		postings := asList(payload["jobPostings"])
		if total < 0 {
			total = len(postings)
			if raw := asString(payload["total"]); raw != "" {
				total = atoi(raw)
			}
		}
		for _, row := range postings {
			item := asMap(row)
			path := asString(item["externalPath"])
			title := asString(item["title"])
			location := asString(item["locationsText"])
			if location == "" {
				location = asString(item["location"])
			}
			job, ok := listingJob(title, strings.TrimRight(base, "/")+path, location, "", "", nil)
			if ok {
				jobs = append(jobs, job)
			}
		}
		offset += limit
		if len(postings) == 0 || offset >= total {
			break
		}
	}
	return jobs, nil
}

func workdayAPIAndBase(raw string) (string, string) {
	api := strings.TrimRight(strings.Split(strings.Split(raw, "|")[0], "?")[0], "/")
	if strings.Contains(raw, "|") {
		parts := strings.SplitN(raw, "|", 2)
		return api, strings.TrimSpace(parts[1])
	}
	re := regexp.MustCompile(`^(https://[^/]+)/wday/cxs/([^/]+)/([^/]+)/jobs`)
	m := re.FindStringSubmatch(api)
	if m == nil {
		return api, ""
	}
	host := strings.TrimPrefix(strings.TrimPrefix(m[1], "https://"), "http://")
	if strings.Contains(host, "myworkdaysite") {
		return api, fmt.Sprintf("https://%s/en-US/%s/%s", host, m[2], m[3])
	}
	return api, fmt.Sprintf("https://%s/en-US/%s", host, m[3])
}

var jobletQueries = []string{
	"software engineer",
	"frontend",
	"full stack",
	"devops",
	"platform engineer",
	"data engineer",
	"machine learning",
	"typescript",
	"staff engineer",
	"principal engineer",
}

func fetchJoblet(ctx context.Context, client getter, req Request) ([]Job, error) {
	referer := jobletBoardURL(req.boardURL())
	headers := map[string]string{
		"Accept":  "application/json",
		"Origin":  "https://joblet.ai",
		"Referer": referer,
	}
	byURL := map[string]Job{}
	order := []string{}
	for _, query := range jobletQueries {
		api := "https://joblet.ai/api/search?" + url.Values{
			"q":        {query},
			"location": {"Remote"},
			"page":     {"1"},
		}.Encode()
		res, err := getURL(ctx, client, api, headers)
		if err != nil {
			return nil, err
		}
		if err := res.requireOK(); err != nil {
			return nil, err
		}
		payload, err := decodeJSON(res.Body)
		if err != nil {
			return nil, err
		}
		for _, job := range parseJoblet(payload) {
			if _, ok := byURL[job.URL]; ok {
				continue
			}
			byURL[job.URL] = job
			order = append(order, job.URL)
		}
	}
	jobs := make([]Job, 0, len(order))
	for _, rawURL := range order {
		jobs = append(jobs, byURL[rawURL])
	}
	return jobs, nil
}

func jobletBoardURL(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "https://joblet.ai/jobs?employmentType=Remote"
	}
	parsed, err := url.Parse(raw)
	if err != nil || !strings.Contains(strings.ToLower(parsed.Host), "joblet.ai") {
		return "https://joblet.ai/jobs?employmentType=Remote"
	}
	query := parsed.Query()
	if _, ok := query["employmentType"]; !ok {
		query.Set("employmentType", "Remote")
	}
	path := parsed.Path
	if path == "" {
		path = "/jobs"
	}
	scheme := parsed.Scheme
	if scheme == "" {
		scheme = "https"
	}
	return scheme + "://" + parsed.Host + path + "?" + query.Encode()
}

func parseJoblet(payload any) []Job {
	root := asMap(payload)
	if root == nil {
		return nil
	}
	data := root
	if nested := asMap(root["data"]); nested != nil {
		data = nested
	}
	jobs := make([]Job, 0)
	for _, row := range asList(data["jobs"]) {
		item := asMap(row)
		if item == nil || !jobletRemote(item) {
			continue
		}
		rawURL := jobletURL(item)
		job, ok := listingJob(
			asString(item["title"]),
			rawURL,
			jobletLocation(item),
			jobletEmployer(item),
			plainText(asString(item["description"])),
			nil,
		)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func jobletRemote(row map[string]any) bool {
	if remote, ok := row["isRemote"].(bool); ok && remote {
		return true
	}
	for _, item := range asList(row["employmentType"]) {
		if strings.EqualFold(asString(item), "remote") {
			return true
		}
	}
	return strings.Contains(strings.ToLower(asString(row["location"])), "remote")
}

func jobletEmployer(row map[string]any) string {
	switch v := row["company"].(type) {
	case map[string]any:
		return asString(v["name"])
	case string:
		return strings.TrimSpace(v)
	default:
		return ""
	}
}

func jobletURL(row map[string]any) string {
	slug := asString(row["slug"])
	if slug == "" {
		slug = asString(row["url_slug"])
	}
	if slug != "" {
		return "https://joblet.ai/jobs/" + strings.TrimLeft(slug, "/")
	}
	if raw := asString(row["applyUrl"]); raw != "" {
		return raw
	}
	return asString(row["url"])
}

func jobletLocation(row map[string]any) string {
	if location := asString(row["location"]); location != "" {
		return location
	}
	return "Remote"
}
