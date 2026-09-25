package atsscrape

import (
	"context"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/url"
	"regexp"
	"strings"

	xhtml "golang.org/x/net/html"
)

func fetchApplyToJob(ctx context.Context, client getter, req Request) ([]Job, error) {
	page := req.boardURL()
	if page == "" {
		page = strings.TrimSpace(req.CareersURL)
	}
	res, err := getURL(ctx, client, page, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	doc, err := htmlParse(res.Body)
	if err != nil {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	var walk func(*xhtml.Node)
	walk = func(n *xhtml.Node) {
		if n.Type == xhtml.ElementNode && n.Data == "a" {
			href := strings.TrimSpace(attr(n, "href"))
			if strings.Contains(href, "/apply/") {
				slug := strings.Trim(strings.TrimRight(href, "/"), "/")
				parts := strings.Split(slug, "/")
				slug = parts[len(parts)-1]
				lower := strings.ToLower(slug)
				if slug != "" && lower != "apply" && lower != "jobs" {
					full := resolveRef(page, href)
					if _, ok := seen[full]; !ok {
						title := normalizeSpace(elementText(n))
						if len(title) >= 3 {
							seen[full] = struct{}{}
							if job, ok := listingJob(title, full, "", "", "", nil); ok {
								jobs = append(jobs, job)
							}
						}
					}
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(doc)
	return jobs, nil
}

var (
	deelPatternEscaped = regexp.MustCompile(`(?i)\\"id\\":\\"([a-f0-9-]+)\\",\\"jobId\\":\\"[a-f0-9-]+\\",\\"title\\":\\"((?:\\\\.|[^\\"])*)\\"`)
	deelPatternPlain   = regexp.MustCompile(`(?i)"id":"([a-f0-9-]+)","jobId":"[a-f0-9-]+","title":"((?:\\.|[^"\\])*)"`)
	deelSlugRE         = regexp.MustCompile(`(?i)jobs\.deel\.com/([a-zA-Z0-9_-]+)`)
	deelSkipSlugs      = map[string]struct{}{"embed": {}, "jobs": {}, "job-details": {}}
)

func fetchDeel(ctx context.Context, client getter, req Request) ([]Job, error) {
	source := req.boardURL()
	if source == "" {
		source = strings.TrimSpace(req.CareersURL)
	}
	fetchURL := deelBoardURL(source)
	if fetchURL == "" {
		return []Job{}, nil
	}
	slug := lastSlug(fetchURL)
	if m := deelSlugRE.FindStringSubmatch(fetchURL); m != nil {
		slug = m[1]
	}
	res, err := getURL(ctx, client, fetchURL, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	return parseDeelJobs(string(res.Body), slug), nil
}

func deelBoardURL(raw string) string {
	m := deelSlugRE.FindStringSubmatch(raw)
	if m == nil {
		return ""
	}
	if _, skip := deelSkipSlugs[strings.ToLower(m[1])]; skip {
		return ""
	}
	parsed, err := url.Parse(raw)
	board := "https://jobs.deel.com/" + m[1]
	if err == nil && parsed.RawQuery != "" {
		board += "?" + parsed.RawQuery
	}
	return board
}

func parseDeelJobs(page, slug string) []Job {
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	for _, pattern := range []*regexp.Regexp{deelPatternEscaped, deelPatternPlain} {
		for _, match := range pattern.FindAllStringSubmatch(page, -1) {
			title := strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(match[2], `\"`, `"`), `\\`, `\`))
			if match[1] == "" || title == "" {
				continue
			}
			rawURL := fmt.Sprintf("https://jobs.deel.com/%s/job-details/%s/overview", slug, match[1])
			if _, ok := seen[rawURL]; ok {
				continue
			}
			seen[rawURL] = struct{}{}
			if job, ok := listingJob(title, rawURL, "", "", "", nil); ok {
				jobs = append(jobs, job)
			}
		}
		if len(jobs) > 0 {
			break
		}
	}
	return jobs
}

var nextDataRE = regexp.MustCompile(`(?s)<script id="__NEXT_DATA__"[^>]*>(.*?)</script>`)

func fetchEPAM(ctx context.Context, client getter, req Request) ([]Job, error) {
	board := strings.TrimRight(req.boardURL(), "/")
	if board == "" {
		board = "https://careers.epam.com"
	}
	res, err := getURL(ctx, client, board+"/", nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	match := nextDataRE.FindSubmatch(res.Body)
	if match == nil {
		return []Job{}, nil
	}
	payload, err := decodeJSON(match[1])
	if err != nil {
		return []Job{}, nil
	}
	jobsNode := asMap(asMap(asMap(asMap(payload)["props"])["pageProps"])["initialJobs"])
	jobs := make([]Job, 0)
	for _, row := range asList(jobsNode["jobs"]) {
		item := asMap(row)
		seo := asMap(item["seo"])
		title := asString(item["name"])
		if title == "" {
			title = asString(seo["title"])
		}
		title = regexp.MustCompile(`(?i)^Careers for\s+`).ReplaceAllString(title, "")
		title = regexp.MustCompile(`\s*\|.*$`).ReplaceAllString(title, "")
		title = strings.TrimSpace(title)
		path := asString(seo["url"])
		if path == "" {
			continue
		}
		job, ok := listingJob(title, resolveRef("https://careers.epam.com", path), "", "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

var joinSlugRE = regexp.MustCompile(`(?i)join\.com/companies/([a-zA-Z0-9_-]+)`)

func fetchJoin(ctx context.Context, client getter, req Request) ([]Job, error) {
	source := req.boardURL()
	if source == "" {
		source = strings.TrimSpace(req.CareersURL)
	}
	m := joinSlugRE.FindStringSubmatch(source)
	if m == nil || strings.EqualFold(m[1], "embed") || strings.EqualFold(m[1], "jobs") {
		return []Job{}, nil
	}
	pageURL := "https://join.com/companies/" + m[1]
	slug := m[1]
	res, err := getURL(ctx, client, pageURL, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	slugFromPage, companyID, items := parseJoinNextData(res.Body)
	if slugFromPage != "" {
		slug = slugFromPage
	}
	if companyID != "" {
		api := fmt.Sprintf("https://join.com/api/public/companies/%s/jobs?page=1&pageSize=50", companyID)
		apiRes, apiErr := getURL(ctx, client, api, map[string]string{"Accept": "application/json"})
		if apiErr == nil && apiRes.ok() {
			if payload, err := asJSONMap(apiRes.Body); err == nil {
				if apiItems := asList(payload["items"]); len(apiItems) > 0 {
					items = apiItems
				}
			}
		}
	}
	return joinJobs(items, slug), nil
}

func parseJoinNextData(body []byte) (string, string, []any) {
	match := nextDataRE.FindSubmatch(body)
	if match == nil {
		return "", "", nil
	}
	payload, err := decodeJSON(match[1])
	if err != nil {
		return "", "", nil
	}
	state := asMap(asMap(asMap(asMap(payload)["props"])["pageProps"])["initialState"])
	company := asMap(state["company"])
	jobs := asMap(state["jobs"])
	return asString(company["domain"]), asString(company["id"]), asList(jobs["items"])
}

func joinJobs(items []any, slug string) []Job {
	base := "https://join.com/companies/" + slug
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	for _, row := range items {
		item := asMap(row)
		idParam := asString(item["idParam"])
		rawURL := base + "/" + idParam
		if _, ok := seen[rawURL]; ok {
			continue
		}
		seen[rawURL] = struct{}{}
		job, ok := listingJob(asString(item["title"]), rawURL, "", "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func fetchRSS(ctx context.Context, client getter, req Request) ([]Job, error) {
	res, err := getURL(ctx, client, req.boardURL(), nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	return parseRSSItems(string(res.Body), func(item xmlItem) (Job, bool) {
		return listingJob(item.Title, item.Link, "", "", "", nil)
	})
}

const defaultRemoteDXB = "https://www.remotedxb.com/rss"

func fetchRemoteDXB(ctx context.Context, client getter, req Request) ([]Job, error) {
	feed := defaultRemoteDXB
	raw := strings.ToLower(req.boardURL())
	if raw != "" && strings.Contains(raw, "remotedxb.com") && strings.Contains(raw, "/rss") {
		feed = defaultRemoteDXB
	}
	res, err := getURL(ctx, client, feed, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	allowed := map[string]struct{}{
		"information technology":       {},
		"engineering & architecture":   {},
		"engineering and architecture": {},
	}
	return parseRSSItems(string(res.Body), func(item xmlItem) (Job, bool) {
		if item.Category != "" {
			if _, ok := allowed[strings.ToLower(item.Category)]; !ok {
				return Job{}, false
			}
		}
		employer := item.Company
		return listingJob(item.Title, item.Link, "Completely Remote", employer, plainText(item.Description), nil)
	})
}

type xmlItem struct {
	Title       string
	Link        string
	Description string
	Category    string
	Company     string
}

func parseRSSItems(feed string, build func(xmlItem) (Job, bool)) ([]Job, error) {
	text := strings.TrimSpace(stripBOM(feed))
	if i := strings.Index(text, "<?xml"); i > 0 {
		text = text[i:]
	}
	if text == "" {
		return []Job{}, nil
	}
	dec := xml.NewDecoder(strings.NewReader(text))
	jobs := make([]Job, 0)
	var current *xmlItem
	var field string
	for {
		tok, err := dec.Token()
		if err != nil {
			if err == io.EOF {
				break
			}
			return nil, err
		}
		switch t := tok.(type) {
		case xml.StartElement:
			name := t.Name.Local
			if name == "item" {
				current = &xmlItem{}
				field = ""
				continue
			}
			if current != nil {
				field = name
			}
		case xml.EndElement:
			if t.Name.Local == "item" && current != nil {
				if job, ok := build(*current); ok {
					jobs = append(jobs, job)
				}
				current = nil
			}
			field = ""
		case xml.CharData:
			if current == nil || field == "" {
				continue
			}
			value := strings.TrimSpace(string(t))
			if value == "" {
				continue
			}
			switch field {
			case "title":
				current.Title = value
			case "link":
				current.Link = value
			case "description":
				current.Description = value
			case "category":
				if current.Category == "" {
					current.Category = value
				}
			case "companyName":
				current.Company = value
			}
		}
	}
	return jobs, nil
}

var (
	kakeAnchorRE = regexp.MustCompile(`(?i)<a\b[^>]*\bhref="(?P<href>(?:https?://(?:www\.)?kake\.co)?/jobs/(?P<slug>[a-z0-9][a-z0-9-]{3,}))"[^>]*>(?P<title>[^<]+)</a>`)
	kakeTZRE     = regexp.MustCompile(`(?i)Timezone:\s*(GMT[+-]\d+)`)
	kakeSVGRE    = regexp.MustCompile(`(?is)<svg\b[^>]*>.*?</svg>`)
)

func fetchKake(ctx context.Context, client getter, req Request) ([]Job, error) {
	res, err := getURL(ctx, client, "https://kake.co/jobs", nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	return parseKakeHTML(string(res.Body)), nil
}

func parseKakeHTML(page string) []Job {
	matches := kakeAnchorRE.FindAllStringSubmatchIndex(page, -1)
	names := kakeAnchorRE.SubexpNames()
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	for i, match := range matches {
		href := subexp(page, match, names, "href")
		title := normalizeSpace(html.UnescapeString(subexp(page, match, names, "title")))
		rawURL := kakeJobURL(href)
		if title == "" {
			continue
		}
		if _, ok := seen[rawURL]; ok {
			continue
		}
		seen[rawURL] = struct{}{}
		end := len(page)
		if i+1 < len(matches) {
			end = matches[i+1][0]
		}
		cardEnd := match[1] + 8000
		if cardEnd < end {
			end = cardEnd
		}
		if end < match[1] {
			end = match[1]
		}
		location := "Remote"
		if tz := kakeTZRE.FindStringSubmatch(plainText(kakeSVGRE.ReplaceAllString(page[match[1]:end], " "))); tz != nil {
			location = "Remote, " + strings.ToUpper(tz[1])
		}
		job, ok := listingJob(title, rawURL, location, "Kake", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func subexp(text string, match []int, names []string, name string) string {
	for i, item := range names {
		if item == name && match[2*i] >= 0 {
			return text[match[2*i]:match[2*i+1]]
		}
	}
	return ""
}

func kakeJobURL(href string) string {
	path := href
	if strings.Contains(href, "://") {
		if parsed, err := url.Parse(href); err == nil {
			path = parsed.Path
		}
	} else if i := strings.IndexByte(path, '?'); i >= 0 {
		path = path[:i]
	}
	parts := strings.Split(strings.Trim(path, "/"), "/")
	return "https://kake.co/jobs/" + parts[len(parts)-1]
}

var movingCareerRE = regexp.MustCompile(`(?i)/careers/[a-z0-9-]+`)
var projectAIDRE = regexp.MustCompile(`/careers/(\d{6,})`)

func fetchMovingImage(ctx context.Context, client getter, req Request) ([]Job, error) {
	base := strings.Split(req.boardURL(), "#")[0]
	base = strings.TrimRight(base, "/")
	if base == "" {
		base = "https://www.movingimage.com/careers"
	}
	res, err := getURL(ctx, client, base, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	doc, err := htmlParse(res.Body)
	if err != nil {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	var walk func(*xhtml.Node)
	walk = func(n *xhtml.Node) {
		if n.Type == xhtml.ElementNode && n.Data == "a" {
			href := strings.TrimSpace(attr(n, "href"))
			if movingCareerRE.MatchString(href) {
				full := resolveRef(base+"/", href)
				if _, ok := seen[full]; !ok && !strings.HasSuffix(strings.TrimRight(full, "/"), "/careers") {
					seen[full] = struct{}{}
					title := pageH1(ctx, client, full)
					if title == "" {
						slug := strings.TrimRight(full, "/")
						parts := strings.Split(slug, "/")
						title = titleWords(strings.ReplaceAll(parts[len(parts)-1], "-", " "))
					}
					if job, ok := listingJob(title, full, "", "", "", nil); ok {
						jobs = append(jobs, job)
					}
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(doc)
	return jobs, nil
}

func fetchProjectA(ctx context.Context, client getter, req Request) ([]Job, error) {
	board := strings.Split(req.boardURL(), "#")[0]
	board = strings.TrimRight(board, "/")
	if board == "" {
		board = "https://www.project-a.vc/careers"
	}
	res, err := getURL(ctx, client, board, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	ids := projectAIDRE.FindAllStringSubmatch(string(res.Body), -1)
	seen := map[string]struct{}{}
	jobs := make([]Job, 0)
	for _, match := range ids {
		if _, ok := seen[match[1]]; ok {
			continue
		}
		seen[match[1]] = struct{}{}
		jobURL := "https://www.project-a.vc/careers/" + match[1]
		title := pageH1(ctx, client, jobURL)
		if job, ok := listingJob(title, jobURL, "", "", "", nil); ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func pageH1(ctx context.Context, client getter, rawURL string) string {
	res, err := getURL(ctx, client, rawURL, nil)
	if err != nil || !res.ok() {
		return ""
	}
	doc, err := htmlParse(res.Body)
	if err != nil {
		return ""
	}
	if h1 := findTag(doc, "h1"); h1 != nil {
		return normalizeSpace(elementText(h1))
	}
	return ""
}

var successFactorsRE = regexp.MustCompile(`data-url\s*=\s*"(/en-[a-z]{2}/api/job/getjobs[^"]*)"`)

func fetchSuccessFactors(ctx context.Context, client getter, req Request) ([]Job, error) {
	careers := strings.TrimSpace(req.CareersURL)
	if careers == "" {
		careers = req.boardURL()
	}
	if careers == "" {
		return []Job{}, nil
	}
	res, err := getURL(ctx, client, careers, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	m := successFactorsRE.FindSubmatch(res.Body)
	if m == nil {
		return []Job{}, nil
	}
	domain := careers
	if i := strings.Index(careers, "/en-"); i >= 0 {
		domain = careers[:i]
	}
	apiRes, err := getURL(ctx, client, domain+string(m[1]), map[string]string{"Accept": "application/json"})
	if err != nil {
		return nil, err
	}
	if err := apiRes.requireOK(); err != nil {
		return nil, err
	}
	payload, err := asJSONMap(apiRes.Body)
	if err != nil {
		return nil, err
	}
	base := strings.TrimRight(careers, "/")
	jobs := make([]Job, 0)
	for _, row := range asList(payload["items"]) {
		item := asMap(row)
		href := asString(item["href"])
		jobURL := href
		if href != "" && !strings.HasPrefix(href, "http") {
			jobURL = base + "/" + strings.TrimLeft(href, "/")
		}
		job, ok := listingJob(asString(item["headline"]), jobURL, asString(item["location"]), "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func fetchPersonio(ctx context.Context, client getter, req Request) ([]Job, error) {
	board := req.boardURL()
	if strings.Contains(board, "personio.com/api/careers/jobs") {
		return personioComAPI(ctx, client, board)
	}
	parsed, err := url.Parse(board)
	if err != nil || parsed.Host == "" {
		return []Job{}, nil
	}
	base := "https://" + parsed.Host
	jobs, err := personioXML(ctx, client, base)
	if err != nil {
		return nil, err
	}
	if len(jobs) > 0 {
		return jobs, nil
	}
	return personioHTML(ctx, client, base)
}

func personioComAPI(ctx context.Context, client getter, board string) ([]Job, error) {
	res, err := getURL(ctx, client, strings.TrimRight(board, "/"), map[string]string{"Accept": "application/json"})
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	rows, err := asJSONList(res.Body)
	if err != nil {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	for _, row := range rows {
		item := asMap(row)
		title := asString(item["name"])
		if title == "" {
			title = asString(item["title"])
		}
		jobID := asString(item["id"])
		job, ok := listingJob(title, "https://www.personio.com/careers/"+jobID+"/", "", "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func personioXML(ctx context.Context, client getter, base string) ([]Job, error) {
	res, err := getURL(ctx, client, base+"/xml", nil)
	if err != nil {
		return nil, err
	}
	body := strings.TrimLeft(string(res.Body), " \n\r\t")
	if !res.ok() || len(res.Body) < 50 || !(strings.HasPrefix(body, "<?xml") || strings.HasPrefix(body, "<workzag")) {
		return []Job{}, nil
	}
	cleaned := escapeBareAmp(string(res.Body))
	var doc personioDoc
	if err := xml.Unmarshal([]byte(cleaned), &doc); err != nil {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	for _, pos := range doc.Positions {
		parts := make([]string, 0)
		for _, desc := range pos.Descriptions.Items {
			value := strings.TrimSpace(desc.Value)
			if value == "" {
				continue
			}
			if name := strings.TrimSpace(desc.Name); name != "" {
				parts = append(parts, "<h3>"+name+"</h3>")
			}
			parts = append(parts, value)
		}
		job, ok := listingJob(pos.Name, base+"/job/"+strings.TrimSpace(pos.ID), pos.Office, "", strings.Join(parts, "\n"), nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs, nil
}

func escapeBareAmp(text string) string {
	var b strings.Builder
	b.Grow(len(text))
	for i := 0; i < len(text); i++ {
		if text[i] != '&' {
			b.WriteByte(text[i])
			continue
		}
		if entityLen(text[i:]) > 0 {
			b.WriteByte('&')
			continue
		}
		b.WriteString("&amp;")
	}
	return b.String()
}

func entityLen(rest string) int {
	for _, entity := range []string{"&amp;", "&lt;", "&gt;", "&quot;", "&apos;"} {
		if strings.HasPrefix(rest, entity) {
			return len(entity)
		}
	}
	if strings.HasPrefix(rest, "&#x") || strings.HasPrefix(rest, "&#X") {
		end := 3
		for end < len(rest) && isHex(rest[end]) {
			end++
		}
		if end > 3 && end < len(rest) && rest[end] == ';' {
			return end + 1
		}
	}
	if strings.HasPrefix(rest, "&#") {
		end := 2
		for end < len(rest) && rest[end] >= '0' && rest[end] <= '9' {
			end++
		}
		if end > 2 && end < len(rest) && rest[end] == ';' {
			return end + 1
		}
	}
	return 0
}

func isHex(b byte) bool {
	return (b >= '0' && b <= '9') || (b >= 'a' && b <= 'f') || (b >= 'A' && b <= 'F')
}

type personioDoc struct {
	XMLName   xml.Name `xml:"workzag"`
	Positions []struct {
		ID           string `xml:"id"`
		Name         string `xml:"name"`
		Office       string `xml:"office"`
		Descriptions struct {
			Items []struct {
				Name  string `xml:"name"`
				Value string `xml:"value"`
			} `xml:"jobDescription"`
		} `xml:"jobDescriptions"`
	} `xml:"position"`
}

func personioHTML(ctx context.Context, client getter, base string) ([]Job, error) {
	res, err := getURL(ctx, client, base+"/", nil)
	if err != nil || !res.ok() {
		return []Job{}, nil
	}
	doc, err := htmlParse(res.Body)
	if err != nil {
		return []Job{}, nil
	}
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	var walk func(*xhtml.Node)
	walk = func(n *xhtml.Node) {
		if n.Type == xhtml.ElementNode && n.Data == "a" {
			href := attr(n, "href")
			if strings.Contains(href, "/job/") {
				full := resolveRef(base+"/", href)
				if _, ok := seen[full]; !ok {
					title := normalizeSpace(elementText(n))
					if h3 := findTag(n, "h3"); h3 != nil {
						title = normalizeSpace(elementText(h3))
					} else if prev := previousH3(n); prev != nil {
						title = normalizeSpace(elementText(prev))
					}
					if len(title) >= 3 {
						seen[full] = struct{}{}
						if job, ok := listingJob(title, full, "", "", "", nil); ok {
							jobs = append(jobs, job)
						}
					}
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(doc)
	return jobs, nil
}

func fetchTeamtailor(ctx context.Context, client getter, req Request) ([]Job, error) {
	board := req.boardURL()
	careers := strings.TrimSpace(req.CareersURL)
	if careers == "" {
		careers = board
	}
	if board != "" && !strings.HasPrefix(board, "http") {
		if jobs := teamtailorAPI(ctx, client, board, careers); len(jobs) > 0 {
			return jobs, nil
		}
	}
	return teamtailorHTML(ctx, client, teamtailorBoardURL(board, careers))
}

func teamtailorBoardURL(apiOrURL, careers string) string {
	if strings.HasPrefix(apiOrURL, "http") {
		return strings.TrimRight(apiOrURL, "/")
	}
	board := strings.TrimRight(careers, "/")
	if strings.Contains(board, ".teamtailor.com") && !strings.HasSuffix(strings.Split(board, "?")[0], "/jobs") {
		base := strings.Split(board, "?")[0]
		if !strings.Contains(base, "/jobs") {
			return base + "/jobs"
		}
		return base
	}
	return board
}

func teamtailorAPI(ctx context.Context, client getter, apiKey, careers string) []Job {
	headers := map[string]string{
		"Authorization": "Token token=" + apiKey,
		"Accept":        "application/vnd.api+json",
	}
	for _, version := range []string{"20240404", "20210218", "20161108"} {
		jobs := []any{}
		included := []any{}
		next := "https://api.teamtailor.com/v1/jobs?include=department,locations&page[size]=30&filter[feed]=public"
		hdrs := map[string]string{"X-Api-Version": version}
		for key, value := range headers {
			hdrs[key] = value
		}
		ok := true
		for next != "" {
			res, err := getURL(ctx, client, next, hdrs)
			if err != nil {
				ok = false
				break
			}
			if res.Status == 406 && version != "20161108" {
				ok = false
				break
			}
			if !res.ok() {
				ok = false
				break
			}
			payload, err := asJSONMap(res.Body)
			if err != nil {
				ok = false
				break
			}
			jobs = append(jobs, asList(payload["data"])...)
			included = append(included, asList(payload["included"])...)
			next = asString(asMap(payload["links"])["next"])
		}
		if ok && len(jobs) > 0 {
			if out := teamtailorJobs(jobs, included, careers); len(out) > 0 {
				return out
			}
		}
	}
	fallback := "https://api.teamtailor.com/v1/jobs?api_key=" + url.QueryEscape(apiKey) + "&page[size]=30&filter[feed]=public"
	res, err := getURL(ctx, client, fallback, map[string]string{"X-Api-Version": "20210218"})
	if err != nil || !res.ok() {
		return nil
	}
	payload, err := asJSONMap(res.Body)
	if err != nil {
		return nil
	}
	return teamtailorJobs(asList(payload["data"]), asList(payload["included"]), careers)
}

func teamtailorJobs(rows, included []any, careers string) []Job {
	locs := map[string]string{}
	for _, row := range included {
		item := asMap(row)
		if asString(item["type"]) != "locations" {
			continue
		}
		attrs := asMap(item["attributes"])
		locs[asString(item["id"])] = joinUnique(asString(attrs["city"]), asString(attrs["country"]), asString(attrs["name"]))
	}
	jobs := make([]Job, 0)
	for _, row := range rows {
		item := asMap(row)
		attrs := asMap(item["attributes"])
		title := asString(attrs["title"])
		refs := asList(asMap(asMap(asMap(item["relationships"])["locations"])["data"])["data"])
		if refs == nil {
			refs = asList(asMap(asMap(item["relationships"])["locations"])["data"])
		}
		labels := []string{}
		for _, ref := range refs {
			id := asString(asMap(ref)["id"])
			if label := locs[id]; label != "" {
				labels = append(labels, label)
			}
		}
		location := ""
		if len(labels) == 1 {
			location = labels[0]
		}
		rawURL := asString(asMap(item["links"])["careersite-job-url"])
		if rawURL == "" {
			rawURL = careers
		}
		job, ok := listingJob(title, rawURL, location, "", asString(attrs["body"]), labels)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func teamtailorHTML(ctx context.Context, client getter, board string) ([]Job, error) {
	if board != "" && !strings.HasSuffix(strings.TrimRight(board, "/"), "/jobs") {
		board = strings.TrimRight(board, "/") + "/jobs"
	}
	merged := map[string]string{}
	order := []string{}
	for page := 1; page <= 25; page++ {
		pageURL := board
		if page > 1 {
			pageURL = board + "?page=" + fmt.Sprint(page)
		}
		res, err := getURL(ctx, client, pageURL, nil)
		if err != nil || !res.ok() {
			if page == 1 {
				return []Job{}, nil
			}
			break
		}
		batch := collectListingLinks(string(res.Body), board)
		added := 0
		for _, item := range batch {
			if _, ok := merged[item.url]; ok {
				continue
			}
			merged[item.url] = item.title
			order = append(order, item.url)
			added++
		}
		if added == 0 {
			break
		}
	}
	if len(order) == 0 {
		return []Job{}, nil
	}
	links := make([]listingLink, 0, len(order))
	for _, rawURL := range order {
		links = append(links, listingLink{url: rawURL, title: merged[rawURL]})
	}
	return jobsFromCollected(ctx, client, links), nil
}

func jobsFromCollected(ctx context.Context, client getter, links []listingLink) []Job {
	jobs := make([]Job, 0, len(links))
	for _, item := range links {
		title := normalizeSpace(item.title)
		if needsDetailTitle(item.title) {
			if detail := fetchDetailTitle(ctx, client, item.url); detail != "" {
				title = detail
			}
		}
		if len(title) < 5 || len(title) > 150 || junkTitleRE.MatchString(title) {
			continue
		}
		if job, ok := listingJob(title, item.url, "", "", "", nil); ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

func htmlParse(body []byte) (*xhtml.Node, error) {
	return xhtml.Parse(strings.NewReader(string(body)))
}

func previousH3(n *xhtml.Node) *xhtml.Node {
	for prev := n.PrevSibling; prev != nil; prev = prev.PrevSibling {
		if prev.Type == xhtml.ElementNode && prev.Data == "h3" {
			return prev
		}
		if found := findTag(prev, "h3"); found != nil {
			return found
		}
	}
	return nil
}

func titleWords(text string) string {
	parts := strings.Fields(text)
	for i, part := range parts {
		parts[i] = strings.ToUpper(part[:1]) + strings.ToLower(part[1:])
	}
	return strings.Join(parts, " ")
}
