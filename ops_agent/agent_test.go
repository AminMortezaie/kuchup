package opsagent

import (
	"testing"
)

func TestDashboardMetricNames(t *testing.T) {
	want := map[string]bool{
		"node_memory_MemAvailable_bytes":    true,
		"node_filesystem_avail_bytes":       true,
		"node_filesystem_size_bytes":        true,
		"node_load1":                        true,
		"container_memory_usage_bytes":      true,
		"container_cpu_usage_seconds_total": true,
		"probe_success":                     true,
	}
	for _, name := range dashboardSeries() {
		if !want[name] {
			t.Fatalf("unexpected dashboard metric %q", name)
		}
		delete(want, name)
	}
	if len(want) != 0 {
		t.Fatalf("missing dashboard metrics: %v", want)
	}
}

func TestProbeSuccessLabels(t *testing.T) {
	s := probeSample(t.Context(), "http://127.0.0.1:9/not-running", "kuchup-ec2")
	if s.Metric != "probe_success" {
		t.Fatalf("metric=%q", s.Metric)
	}
	if s.Labels["job"] != "integrations/blackbox" {
		t.Fatalf("job=%q", s.Labels["job"])
	}
}

func TestMeminfoParse(t *testing.T) {
	_, err := memAvailableBytes("/proc")
	if err != nil {
		t.Fatalf("meminfo: %v", err)
	}
}

func TestRemoteWritePayload(t *testing.T) {
	samples := []Sample{
		{
			Metric: "probe_success",
			Labels: map[string]string{"job": "integrations/blackbox", "instance": "kuchup-ec2"},
			Value:  1,
		},
	}
	series := samplesToTimeSeries(samples)
	if len(series) != 1 || len(series[0].Labels) < 2 {
		t.Fatalf("series=%+v", series)
	}
}
