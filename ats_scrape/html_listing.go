package atsscrape

import (
	"context"
	"net/url"
	"regexp"
	"strings"

	"golang.org/x/net/html"
)

var (
	jobDetailPathRE = regexp.MustCompile(`(?i)/job[s]?/`)
	listingNoiseRE  = regexp.MustCompile(`(?i)/jobs/show_more\b`)
	junkTitleRE     = regexp.MustCompile(`(?i)^(show\s+\d+\s+more|load\s+more|view\s+all(\s+jobs)?|see\s+all(\s+jobs)?)$`)
	titleCutRE      = regexp.MustCompile(`(?i)\s+(?:was du mitbringst|view job|view role|view position|apply now|i'm interested)\b`)
	ogTitleRE       = regexp.MustCompile(`(?i)\s*[-|–]\s*[^-|–]+ careers\s*$`)
)

var genericLinkLabels = map[string]struct{}{
	"view job": {}, "view role": {}, "view position": {}, "see job": {}, "see role": {},
	"apply": {}, "apply now": {}, "read more": {}, "learn more": {}, "details": {},
}

var careersIndexSegments = map[string]struct{}{
	"careers": {}, "jobs": {}, "job-openings": {}, "vacancies": {}, "vacatures": {},
}

func jobsFromListingHTML(ctx context.Context, client getter, pageHTML, pageURL string) []Job {
	candidates := collectListingLinks(pageHTML, pageURL)
	jobs := make([]Job, 0, len(candidates))
	for _, item := range candidates {
		if listingNoiseRE.MatchString(item.url) {
			continue
		}
		title := normalizeSpace(item.title)
		if needsDetailTitle(item.title) && client != nil {
			if detail := fetchDetailTitle(ctx, client, item.url); detail != "" {
				title = detail
			}
		}
		if len(title) < 5 || len(title) > 150 || junkTitleRE.MatchString(title) {
			continue
		}
		job, ok := listingJob(title, item.url, "", "", "", nil)
		if ok {
			jobs = append(jobs, job)
		}
	}
	return jobs
}

type listingLink struct {
	url   string
	title string
}

func collectListingLinks(pageHTML, pageURL string) []listingLink {
	doc, err := html.Parse(strings.NewReader(pageHTML))
	if err != nil {
		return nil
	}
	found := map[string]string{}
	order := []string{}
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "a" {
			href := attr(n, "href")
			if href != "" {
				full := resolveRef(pageURL, href)
				if strings.TrimRight(full, "/") != strings.TrimRight(pageURL, "/") &&
					!listingNoiseRE.MatchString(full) &&
					isJobDetailURL(full) {
					guess := titleFromAnchor(n)
					if !junkTitleRE.MatchString(normalizeSpace(guess)) {
						prev, ok := found[full]
						if !ok {
							order = append(order, full)
						}
						if !ok || len(guess) > len(prev) {
							found[full] = guess
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
	out := make([]listingLink, 0, len(order))
	for _, rawURL := range order {
		out = append(out, listingLink{url: rawURL, title: found[rawURL]})
	}
	return out
}

func isJobDetailURL(raw string) bool {
	return jobDetailPathRE.MatchString(raw) || isCareersDetailURL(raw)
}

func isCareersDetailURL(raw string) bool {
	parsed, err := url.Parse(raw)
	if err != nil {
		return false
	}
	parts := make([]string, 0)
	for _, part := range strings.Split(parsed.Path, "/") {
		if part != "" {
			parts = append(parts, part)
		}
	}
	if len(parts) < 2 {
		return false
	}
	if _, ok := careersIndexSegments[strings.ToLower(parts[0])]; !ok {
		return false
	}
	slug := strings.TrimSuffix(strings.ToLower(parts[len(parts)-1]), ".html")
	if _, index := careersIndexSegments[slug]; index || slug == "" {
		return false
	}
	if len(parts) == 2 {
		switch slug {
		case "en", "nl", "de", "fr", "es", "it":
			return false
		}
	}
	return true
}

func titleFromAnchor(a *html.Node) string {
	for _, tag := range []string{"h3", "h2", "h1"} {
		if heading := findTag(a, tag); heading != nil {
			title := cleanListingTitle(elementText(heading))
			if len(title) >= 5 {
				return title
			}
		}
	}
	title := cleanListingTitle(elementText(a))
	lower := strings.ToLower(title)
	if _, generic := genericLinkLabels[lower]; !generic && len(title) >= 5 && len(title) <= 90 && !strings.Contains(lower, "job family") {
		return title
	}
	node := a.Parent
	for i := 0; i < 4 && node != nil; i++ {
		for _, tag := range []string{"h1", "h2", "h3"} {
			if heading := findTag(node, tag); heading != nil {
				found := cleanListingTitle(elementText(heading))
				if len(found) >= 5 {
					return found
				}
			}
		}
		node = node.Parent
	}
	if _, generic := genericLinkLabels[lower]; !generic && len(title) >= 5 {
		if len(title) > 90 {
			return title[:90]
		}
		return title
	}
	return ""
}

func needsDetailTitle(guess string) bool {
	text := strings.ToLower(normalizeSpace(guess))
	if text == "" {
		return true
	}
	if _, generic := genericLinkLabels[text]; generic || len(text) < 5 {
		return true
	}
	if strings.Contains(text, "job family") && len(guess) > 80 {
		return true
	}
	return false
}

func cleanListingTitle(title string) string {
	parts := titleCutRE.Split(normalizeSpace(title), 2)
	text := strings.Trim(parts[0], " -–·|,")
	if len(text) > 150 {
		return text[:150]
	}
	return text
}

func fetchDetailTitle(ctx context.Context, client getter, rawURL string) string {
	res, err := getURL(ctx, client, rawURL, nil)
	if err != nil || res.Status >= 400 {
		return ""
	}
	doc, err := html.Parse(strings.NewReader(string(res.Body)))
	if err != nil {
		return ""
	}
	if h1 := findTag(doc, "h1"); h1 != nil {
		if title := normalizeSpace(elementText(h1)); title != "" {
			if len(title) > 150 {
				return title[:150]
			}
			return title
		}
	}
	if content := metaContent(doc, "og:title"); content != "" {
		title := ogTitleRE.ReplaceAllString(normalizeSpace(content), "")
		if len(title) > 150 {
			return title[:150]
		}
		return title
	}
	return ""
}

func metaContent(n *html.Node, property string) string {
	var content string
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if content != "" {
			return
		}
		if n.Type == html.ElementNode && n.Data == "meta" && strings.EqualFold(attr(n, "property"), property) {
			content = attr(n, "content")
			return
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(n)
	return content
}

func findTag(n *html.Node, tag string) *html.Node {
	var found *html.Node
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if found != nil {
			return
		}
		if n.Type == html.ElementNode && n.Data == tag {
			found = n
			return
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(n)
	return found
}

func elementText(n *html.Node) string {
	var b strings.Builder
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.TextNode {
			b.WriteString(n.Data)
			b.WriteByte(' ')
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(n)
	return b.String()
}

func attr(n *html.Node, key string) string {
	for _, item := range n.Attr {
		if strings.EqualFold(item.Key, key) {
			return item.Val
		}
	}
	return ""
}

func resolveRef(base, href string) string {
	bu, err := url.Parse(base)
	if err != nil {
		return strings.TrimSpace(href)
	}
	ru, err := url.Parse(strings.TrimSpace(href))
	if err != nil {
		return strings.TrimSpace(href)
	}
	return bu.ResolveReference(ru).String()
}

func fetchGeneric(ctx context.Context, client getter, req Request) ([]Job, error) {
	page := req.pageURL()
	if page == "" {
		return []Job{}, nil
	}
	res, err := getURL(ctx, client, page, nil)
	if err != nil || !res.ok() {
		return []Job{}, nil
	}
	return jobsFromListingHTML(ctx, client, string(res.Body), page), nil
}
