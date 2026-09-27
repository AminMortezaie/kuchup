package opsagent

import (
	"testing"
)

func TestProbeSuccessLabels(t *testing.T) {
	s := probeSample(t.Context(), "http://127.0.0.1:9/not-running", "kuchup-ec2")
	if s.Metric != "probe_success" {
		t.Fatalf("metric=%q", s.Metric)
	}
	if s.Labels["job"] != "integrations/blackbox" {
		t.Fatalf("job=%q", s.Labels["job"])
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
	body := samplesToWriteRequest(samples)
	if len(body) < 8 {
		t.Fatalf("write request too short: %d bytes", len(body))
	}
}
