package opsagent

import (
	"context"
	"flag"
	"log"
	"os"
	"strings"
	"time"
)

func Main() {
	once := flag.Bool("once", false, "collect one interval and exit")
	flag.Parse()

	interval := envDuration("OPS_METRICS_INTERVAL", time.Minute)
	procRoot := envString("OPS_PROC_ROOT", "/host/proc")
	hostRoot := envString("OPS_HOST_ROOT", "/host/root")
	healthURL := envString("OPS_HEALTH_URL", "http://127.0.0.1:10000/api/health")
	instance := envString("OPS_INSTANCE", "kuchup-ec2")
	dockerSocket := envString("OPS_DOCKER_SOCKET", "/var/run/docker.sock")
	names := defaultContainerNames()

	ctx := context.Background()
	var store *Store
	if strings.TrimSpace(os.Getenv("DATABASE_URL")) != "" {
		var err error
		store, err = OpenStore(ctx)
		if err != nil {
			log.Fatalf("postgres: %v", err)
		}
		defer store.Close(ctx)
	}
	remote, remoteOK := RemoteConfigFromEnv()
	if !remoteOK {
		log.Print("Grafana Cloud remote_write disabled — set GRAFANA_CLOUD_PROMETHEUS_URL, GRAFANA_CLOUD_PROMETHEUS_USER, GRAFANA_CLOUD_API_TOKEN")
	}

	collect := func() {
		now := time.Now().UTC()
		var batch []Sample
		host, err := hostSamples(procRoot, hostRoot, instance)
		if err != nil {
			log.Printf("host metrics: %v", err)
		} else {
			batch = append(batch, host...)
		}
		docker, err := dockerSamples(ctx, dockerSocket, names, instance)
		if err != nil {
			log.Printf("docker metrics: %v", err)
		} else {
			batch = append(batch, docker...)
		}
		batch = append(batch, probeSample(ctx, healthURL, instance))
		for i := range batch {
			batch[i].At = now
		}
		if store != nil {
			if err := store.InsertSamples(ctx, batch); err != nil {
				log.Printf("postgres insert: %v", err)
			}
		}
		if remoteOK {
			if err := RemoteWrite(ctx, remote, batch); err != nil {
				log.Printf("remote_write: %v", err)
			}
		}
		log.Printf("collected samples=%d", len(batch))
	}

	collect()
	if *once {
		return
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		collect()
	}
}

func envString(key, fallback string) string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v
}

func envDuration(key string, fallback time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	if d, err := time.ParseDuration(raw); err == nil {
		return d
	}
	return fallback
}
