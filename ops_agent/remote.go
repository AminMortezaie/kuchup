package opsagent

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gogo/protobuf/proto"
	"github.com/golang/snappy"
	"github.com/prometheus/prometheus/prompb"
)

type RemoteConfig struct {
	URL   string
	User  string
	Token string
}

func RemoteConfigFromEnv() (RemoteConfig, bool) {
	url := strings.TrimSpace(os.Getenv("GRAFANA_CLOUD_PROMETHEUS_URL"))
	user := strings.TrimSpace(os.Getenv("GRAFANA_CLOUD_PROMETHEUS_USER"))
	token := strings.TrimSpace(os.Getenv("GRAFANA_CLOUD_API_TOKEN"))
	if url == "" || user == "" || token == "" {
		return RemoteConfig{}, false
	}
	return RemoteConfig{URL: url, User: user, Token: token}, true
}

func RemoteWrite(ctx context.Context, cfg RemoteConfig, samples []Sample) error {
	if len(samples) == 0 {
		return nil
	}
	body, err := proto.Marshal(&prompb.WriteRequest{Timeseries: samplesToTimeSeries(samples)})
	if err != nil {
		return err
	}
	compressed := snappy.Encode(nil, body)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.URL, bytes.NewReader(compressed))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Encoding", "snappy")
	req.Header.Set("Content-Type", "application/x-protobuf")
	req.Header.Set("X-Prometheus-Remote-Write-Version", "0.1.0")
	req.SetBasicAuth(cfg.User, cfg.Token)
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode/100 != 2 {
		slurp, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("remote_write status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(slurp)))
	}
	return nil
}
