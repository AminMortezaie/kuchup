package opsagent

import (
	"time"

	"github.com/prometheus/prometheus/prompb"
)

type Sample struct {
	Metric string
	Labels map[string]string
	Value  float64
	At     time.Time
}

func (s Sample) PrometheusName() string {
	return s.Metric
}

func dashboardSeries() []string {
	return []string{
		"node_memory_MemAvailable_bytes",
		"node_filesystem_avail_bytes",
		"node_filesystem_size_bytes",
		"node_load1",
		"container_memory_usage_bytes",
		"container_cpu_usage_seconds_total",
		"probe_success",
	}
}

func labelSet(name string, extra map[string]string) map[string]string {
	out := map[string]string{"__name__": name}
	for k, v := range extra {
		out[k] = v
	}
	return out
}

func (s Sample) timeSeries() prompb.TimeSeries {
	labels := make([]prompb.Label, 0, len(s.Labels)+1)
	if _, ok := s.Labels["__name__"]; !ok {
		labels = append(labels, prompb.Label{Name: "__name__", Value: s.Metric})
	}
	for k, v := range s.Labels {
		if k == "__name__" {
			continue
		}
		labels = append(labels, prompb.Label{Name: k, Value: v})
	}
	ts := s.At
	if ts.IsZero() {
		ts = time.Now().UTC()
	}
	ms := ts.UnixMilli()
	return prompb.TimeSeries{
		Labels: labels,
		Samples: []prompb.Sample{
			{Value: s.Value, Timestamp: ms},
		},
	}
}

func samplesToTimeSeries(samples []Sample) []prompb.TimeSeries {
	out := make([]prompb.TimeSeries, len(samples))
	for i := range samples {
		out[i] = samples[i].timeSeries()
	}
	return out
}
