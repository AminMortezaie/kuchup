package atsscrape

import (
	"context"
	"net/url"
	"regexp"
	"strconv"
	"strings"
)

const jobShopSearchURL = "https://api.my-job-shop.com/api/typesense/multi_search"

var jobShopNuxtRE = regexp.MustCompile(`(?s)<script type="application/json"[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>`)

func fetchJobShop(ctx context.Context, client getter, req Request) ([]Job, error) {
	careers := strings.TrimSpace(req.CareersURL)
	if careers == "" {
		careers = req.boardURL()
	}
	pageURL := strings.Split(careers, "#")[0]
	pageURL = strings.TrimSpace(pageURL)
	if pageURL == "" {
		pageURL = careers
	}
	if !strings.Contains(pageURL, "/search") {
		pageURL = strings.TrimRight(pageURL, "/") + "/search"
	}
	res, err := getURL(ctx, client, pageURL, nil)
	if err != nil {
		return nil, err
	}
	if err := res.requireOK(); err != nil {
		return nil, err
	}
	apiKey, tenantID, vanity := parseJobShopConfig(string(res.Body), careers)
	if apiKey == "" || tenantID == "" || vanity == "" {
		return []Job{}, nil
	}
	headers := map[string]string{
		"X-TYPESENSE-API-KEY": apiKey,
		"Content-Type":        "application/json",
	}
	jobs := make([]Job, 0)
	seen := map[string]struct{}{}
	page := 1
	perPage := 100
	total := -1
	for {
		res, err := postJSON(ctx, client, jobShopSearchURL, map[string]any{
			"searches": []any{map[string]any{
				"collection": "offers",
				"q":          "*",
				"query_by":   "title",
				"per_page":   perPage,
				"page":       page,
				"filter_by":  "tenant_id:=" + tenantID + "&&backoffice_vanity:=" + vanity + "&&status:=ACTIVE",
			}},
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
		results := asList(payload["results"])
		result := map[string]any{}
		if len(results) > 0 {
			result = asMap(results[0])
		}
		if total < 0 {
			total = atoi(asString(result["found"]))
		}
		for _, hit := range asList(result["hits"]) {
			doc := asMap(asMap(hit)["document"])
			if doc == nil {
				doc = asMap(hit)
			}
			title := asString(doc["title"])
			rawURL := asString(doc["url"])
			key := strings.ToLower(title) + "\n" + rawURL
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			job, ok := listingJob(title, rawURL, "", "", "", nil)
			if ok {
				jobs = append(jobs, job)
			}
		}
		if page*perPage >= total || len(asList(result["hits"])) == 0 {
			break
		}
		page++
	}
	return jobs, nil
}

func parseJobShopConfig(pageHTML, careers string) (string, string, string) {
	match := jobShopNuxtRE.FindStringSubmatch(pageHTML)
	if match == nil {
		return "", "", ""
	}
	payload, err := decodeJSON([]byte(match[1]))
	data, ok := payload.([]any)
	if err != nil || !ok {
		return "", "", ""
	}
	root := asMap(resolveNuxtNode(data, 1, map[int]struct{}{}))
	if root == nil {
		return "", "", ""
	}
	store := asMap(resolveNuxtScalar(data, root["data"]))
	if store == nil {
		return "", "", ""
	}
	jobShop := asMap(resolveNuxtScalar(data, store["jobShopData"]))
	if jobShop == nil {
		return "", "", ""
	}
	jobShopID := strings.TrimSpace(asString(resolveNuxtScalar(data, jobShop["jobShopId"])))
	vanity := strings.TrimSpace(asString(resolveNuxtScalar(data, jobShop["jobShopCompanyVanity"])))
	if jobShopID == "" || vanity == "" {
		return "", "", ""
	}
	apiKey := resolveNuxtScalar(data, firstPresent(store, "typesenseApiKey-"+jobShopID+"-"+vanity, "typesenseApiKey-"+jobShopID))
	if asString(apiKey) == "" {
		for key, value := range store {
			if strings.HasPrefix(key, "typesenseApiKey-") {
				resolved := resolveNuxtScalar(data, value)
				if text := asString(resolved); len(text) > 20 {
					apiKey = resolved
					break
				}
			}
		}
	}
	key := asString(apiKey)
	if key == "" {
		return "", "", ""
	}
	parsed, _ := url.Parse(careers)
	host := strings.ToLower(parsed.Hostname())
	host = strings.TrimPrefix(host, "www.")
	tenantID := ""
	if m := regexp.MustCompile(`^careers\.([a-z0-9-]+)\.`).FindStringSubmatch(host); m != nil {
		tenantID = m[1]
	}
	if tenantID == "" {
		parts := strings.Split(vanity, "-")
		if len(parts) > 1 {
			tenantID = strings.Join(parts[:len(parts)-1], "-")
		}
	}
	if tenantID == "" {
		return "", "", ""
	}
	return key, tenantID, vanity
}

func firstPresent(store map[string]any, keys ...string) any {
	for _, key := range keys {
		if value, ok := store[key]; ok && value != nil {
			return value
		}
	}
	return nil
}

func resolveNuxtScalar(data []any, value any) any {
	if idx, ok := asIndex(value); ok {
		resolved := resolveNuxtNode(data, idx, map[int]struct{}{})
		if _, still := asIndex(resolved); still {
			return resolveNuxtScalar(data, resolved)
		}
		return resolved
	}
	return value
}

func resolveNuxtNode(data []any, idx any, resolving map[int]struct{}) any {
	index, ok := asIndex(idx)
	if !ok || index < 0 || index >= len(data) {
		return idx
	}
	if _, loop := resolving[index]; loop {
		return nil
	}
	resolving[index] = struct{}{}
	val := data[index]
	list, isList := val.([]any)
	if isList && len(list) >= 2 {
		kind := asString(list[0])
		if kind == "ShallowReactive" || kind == "Reactive" {
			return resolveNuxtNode(data, list[1], resolving)
		}
	}
	if isList && len(list) >= 3 {
		if marker, ok := list[0].(string); ok && marker == "" {
			out := map[string]any{}
			for pos := 1; pos+1 < len(list); pos += 2 {
				key := resolveNuxtNode(data, list[pos], resolving)
				item := resolveNuxtNode(data, list[pos+1], resolving)
				if text, ok := key.(string); ok {
					out[text] = item
				}
			}
			return out
		}
	}
	if isList {
		out := make([]any, 0, len(list))
		for _, item := range list {
			out = append(out, resolveNuxtNode(data, item, resolving))
		}
		return out
	}
	return val
}

func asIndex(v any) (int, bool) {
	switch t := v.(type) {
	case int:
		return t, true
	case jsonNumber:
		n, err := strconv.Atoi(string(t))
		if err != nil {
			return 0, false
		}
		return n, true
	case float64:
		return int(t), true
	default:
		return 0, false
	}
}
