package atsscrape

import (
	"html"
	"math"
	"regexp"
	"strconv"
	"strings"
)

type Job struct {
	Title           string   `json:"title"`
	URL             string   `json:"url"`
	Location        string   `json:"location,omitempty"`
	Locations       []string `json:"locations,omitempty"`
	Employer        string   `json:"employer,omitempty"`
	DescriptionText string   `json:"description_text,omitempty"`
}

func listingJob(title, rawURL, location, employer, description string, locations []string) (Job, bool) {
	title = strings.TrimSpace(title)
	rawURL = strings.TrimSpace(rawURL)
	if title == "" || rawURL == "" {
		return Job{}, false
	}
	job := Job{Title: title, URL: rawURL}
	if location = strings.TrimSpace(location); location != "" {
		job.Location = location
	}
	if len(locations) > 0 {
		job.Locations = locations
	}
	if employer = strings.TrimSpace(employer); employer != "" {
		job.Employer = employer
	}
	if description = strings.TrimSpace(description); description != "" {
		job.DescriptionText = description
	}
	return job, true
}

func joinUnique(parts ...string) string {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if _, ok := seen[part]; ok {
			continue
		}
		seen[part] = struct{}{}
		out = append(out, part)
	}
	return strings.Join(out, ", ")
}

func asString(v any) string {
	switch t := v.(type) {
	case string:
		return strings.TrimSpace(t)
	case jsonNumber:
		return strings.TrimSpace(string(t))
	case float64:
		if math.IsNaN(t) || math.IsInf(t, 0) {
			return ""
		}
		if t == math.Trunc(t) {
			return strconv.FormatInt(int64(t), 10)
		}
		return strconv.FormatFloat(t, 'f', -1, 64)
	case int:
		return strconv.Itoa(t)
	case int64:
		return strconv.FormatInt(t, 10)
	default:
		return ""
	}
}

type jsonNumber string

func asMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	return m
}

func asList(v any) []any {
	l, _ := v.([]any)
	return l
}

func lastSlug(raw string) string {
	raw = strings.TrimSpace(raw)
	raw = strings.TrimRight(raw, "/")
	if raw == "" {
		return ""
	}
	parts := strings.Split(raw, "/")
	slug := parts[len(parts)-1]
	if i := strings.IndexByte(slug, '?'); i >= 0 {
		slug = slug[:i]
	}
	return slug
}

var tagRE = regexp.MustCompile(`<[^>]+>`)

func plainText(raw string) string {
	text := html.UnescapeString(raw)
	text = tagRE.ReplaceAllString(text, " ")
	return normalizeSpace(text)
}

func normalizeSpace(text string) string {
	return strings.Join(strings.Fields(text), " ")
}
