package atsscrape

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const userAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

func defaultHeaders() map[string]string {
	return map[string]string{
		"User-Agent":      userAgent,
		"Accept-Language": "en-US,en;q=0.9",
	}
}

type response struct {
	Status int
	Body   []byte
	Final  string
}

func (r response) ok() bool {
	return r.Status >= 200 && r.Status < 300
}

func (r response) requireOK() error {
	if r.ok() {
		return nil
	}
	return fmt.Errorf("http %d", r.Status)
}

type getter interface {
	Do(req *http.Request) (*http.Response, error)
}

func doRequest(ctx context.Context, client getter, method, rawURL string, body []byte, headers map[string]string) (response, error) {
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, rawURL, reader)
	if err != nil {
		return response{}, err
	}
	for key, value := range defaultHeaders() {
		req.Header.Set(key, value)
	}
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	if body != nil && req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", "application/json")
	}
	res, err := client.Do(req)
	if err != nil {
		return response{}, err
	}
	defer res.Body.Close()
	payload, err := io.ReadAll(io.LimitReader(res.Body, 32<<20))
	if err != nil {
		return response{}, err
	}
	final := rawURL
	if res.Request != nil && res.Request.URL != nil {
		final = res.Request.URL.String()
	}
	return response{Status: res.StatusCode, Body: payload, Final: final}, nil
}

func getURL(ctx context.Context, client getter, rawURL string, headers map[string]string) (response, error) {
	return doRequest(ctx, client, http.MethodGet, rawURL, nil, headers)
}

func postJSON(ctx context.Context, client getter, rawURL string, payload any, headers map[string]string) (response, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return response{}, err
	}
	return doRequest(ctx, client, http.MethodPost, rawURL, body, headers)
}

func decodeJSON(body []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var payload any
	if err := dec.Decode(&payload); err != nil {
		return nil, err
	}
	return normalizeJSON(payload), nil
}

func normalizeJSON(v any) any {
	switch t := v.(type) {
	case json.Number:
		return jsonNumber(t.String())
	case map[string]any:
		for key, value := range t {
			t[key] = normalizeJSON(value)
		}
		return t
	case []any:
		for i, value := range t {
			t[i] = normalizeJSON(value)
		}
		return t
	default:
		return v
	}
}

func asJSONMap(body []byte) (map[string]any, error) {
	payload, err := decodeJSON(body)
	if err != nil {
		return nil, err
	}
	m, ok := payload.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected json object")
	}
	return m, nil
}

func asJSONList(body []byte) ([]any, error) {
	payload, err := decodeJSON(body)
	if err != nil {
		return nil, err
	}
	list, ok := payload.([]any)
	if !ok {
		return nil, fmt.Errorf("expected json array")
	}
	return list, nil
}

func stripBOM(text string) string {
	return strings.TrimPrefix(text, "\ufeff")
}
