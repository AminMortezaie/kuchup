package opsagent

import (
	"context"
	"flag"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

func Main() {
	once := flag.Bool("once", false, "collect one interval and exit")
	interval := flag.Duration("interval", envDuration("OPS_METRICS_INTERVAL", time.Minute), "scrape interval")
	procRoot := flag.String("proc-root", envString("OPS_PROC_ROOT", "/host/proc"), "host /proc mount")
	hostRoot := flag.String("host-root", envString("OPS_HOST_ROOT", "/host/root"), "host filesystem root for disk stats")
	healthURL := flag.String("health-url", envString("OPS_HEALTH_URL", "http://127.0.0.1:10000/api/health"), "panel health probe URL")
	instance := flag.String("instance", envString("OPS_INSTANCE", "kuchup-ec2"), "Prometheus instance label")
	dockerSocket := flag.String("docker-socket", envString("OPS_DOCKER_SOCKET", "/var/run/docker.sock"), "docker unix socket")
	containerList := flag.String("containers", envString("OPS_CONTAINER_NAMES", ""), "comma-separated docker names (default built-in list)")
	flag.Parse()

	names := defaultContainerNames()
	if strings.TrimSpace(*containerList) != "" {
		names = nil
		for _, part := range strings.Split(*containerList, ",") {
			part = strings.TrimSpace(part)
			if part != "" {
				names = append(names, part)
			}
		}
	}

	ctx := context.Background()
	var store *Store
	if url := strings.TrimSpace(os.Getenv("DATABASE_URL")); url != "" {
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
		host, err := hostSamples(*procRoot, *hostRoot, *instance)
		if err != nil {
			log.Printf("host metrics: %v", err)
		} else {
			batch = append(batch, host...)
		}
		docker, err := dockerSamples(ctx, *dockerSocket, names, *instance)
		if err != nil {
			log.Printf("docker metrics: %v", err)
		} else {
			batch = append(batch, docker...)
		}
		probe := probeSample(ctx, *healthURL, *instance)
		batch = append(batch, probe)
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
	ticker := time.NewTicker(*interval)
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
	if sec, err := strconv.Atoi(raw); err == nil && sec > 0 {
		return time.Duration(sec) * time.Second
	}
	return fallback
}
