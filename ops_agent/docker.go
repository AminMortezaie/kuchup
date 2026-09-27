package opsagent

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"
)

type dockerStats struct {
	MemoryStats struct {
		Usage uint64 `json:"usage"`
	} `json:"memory_stats"`
	CPUStats struct {
		CPUUsage struct {
			TotalUsage uint64 `json:"total_usage"`
		} `json:"cpu_usage"`
	} `json:"cpu_stats"`
}

func dockerSamples(ctx context.Context, socket string, names []string, instance string) ([]Sample, error) {
	if strings.TrimSpace(socket) == "" {
		socket = "/var/run/docker.sock"
	}
	client := &http.Client{
		Transport: &http.Transport{
			DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
				return net.Dial("unix", socket)
			},
		},
		Timeout: 15 * time.Second,
	}
	byName, err := dockerRunningIDs(ctx, client)
	if err != nil {
		return nil, err
	}
	var out []Sample
	for _, want := range names {
		want = strings.TrimPrefix(strings.TrimSpace(want), "/")
		if want == "" {
			continue
		}
		id, ok := byName[want]
		if !ok {
			continue
		}
		stats, err := dockerOneShotStats(ctx, client, id)
		if err != nil {
			continue
		}
		labels := map[string]string{
			"name":     want,
			"instance": instance,
			"job":      "integrations/cadvisor",
		}
		out = append(out,
			Sample{Metric: "container_memory_usage_bytes", Labels: copyLabels(labels), Value: float64(stats.MemoryStats.Usage)},
			Sample{Metric: "container_cpu_usage_seconds_total", Labels: copyLabels(labels), Value: float64(stats.CPUStats.CPUUsage.TotalUsage) / 1e9},
		)
	}
	return out, nil
}

type dockerContainer struct {
	ID    string   `json:"Id"`
	Names []string `json:"Names"`
}

func dockerRunningIDs(ctx context.Context, client *http.Client) (map[string]string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "http://docker/v1.44/containers/json", nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("containers/json: %s", strings.TrimSpace(string(body)))
	}
	var list []dockerContainer
	if err := json.NewDecoder(resp.Body).Decode(&list); err != nil {
		return nil, err
	}
	out := make(map[string]string, len(list))
	for _, c := range list {
		for _, n := range c.Names {
			out[strings.TrimPrefix(n, "/")] = c.ID
		}
	}
	return out, nil
}

func dockerOneShotStats(ctx context.Context, client *http.Client, id string) (*dockerStats, error) {
	url := fmt.Sprintf("http://docker/v1.44/containers/%s/stats?stream=false", id)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("stats: %s", strings.TrimSpace(string(body)))
	}
	var stats dockerStats
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		return nil, err
	}
	return &stats, nil
}

func defaultContainerNames() []string {
	return []string{
		"relocation-panel",
		"relocation-fetch-worker",
		"relocation-fetch-merge",
		"relocation-mcp",
		"relocation-caddy",
		"relocation-role-propagator",
		"relocation-playwright-worker",
		"relocation-ops-agent",
		"relocation-redis",
		"pg",
	}
}
