//go:build linux

package opsagent

import "testing"

func TestHostMetricNames(t *testing.T) {
	samples, err := hostSamples("/proc", "/", "kuchup-ec2")
	if err != nil {
		t.Fatalf("hostSamples: %v", err)
	}
	want := map[string]bool{
		"node_memory_MemAvailable_bytes": true,
		"node_filesystem_avail_bytes":    true,
		"node_filesystem_size_bytes":     true,
		"node_load1":                     true,
	}
	for _, s := range samples {
		if !want[s.Metric] {
			t.Fatalf("unexpected host metric %q", s.Metric)
		}
		delete(want, s.Metric)
	}
	if len(want) != 0 {
		t.Fatalf("missing host metrics: %v", want)
	}
}

func TestMeminfoParse(t *testing.T) {
	_, err := memAvailableBytes("/proc")
	if err != nil {
		t.Fatalf("meminfo: %v", err)
	}
}
