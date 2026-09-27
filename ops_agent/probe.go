package opsagent

import (
	"context"
	"net/http"
	"strings"
	"time"
)

func probeSample(ctx context.Context, healthURL, instance string) Sample {
	labels := map[string]string{
		"instance": instance,
		"job":      "integrations/blackbox",
	}
	val := 0.0
	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, strings.TrimSpace(healthURL), nil)
	if err == nil {
		resp, err := client.Do(req)
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				val = 1
			}
		}
	}
	return Sample{Metric: "probe_success", Labels: labels, Value: val}
}
