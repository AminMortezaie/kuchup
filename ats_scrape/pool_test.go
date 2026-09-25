package atsscrape

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestHTTPPoolLimitsConcurrentRequests(t *testing.T) {
	var inFlight atomic.Int32
	var peak atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		current := inFlight.Add(1)
		for {
			old := peak.Load()
			if current <= old || peak.CompareAndSwap(old, current) {
				break
			}
		}
		time.Sleep(20 * time.Millisecond)
		inFlight.Add(-1)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	pool := NewHTTPPool(2, time.Second)
	done := make(chan struct{}, 6)
	for i := 0; i < 6; i++ {
		go func() {
			req, err := http.NewRequestWithContext(context.Background(), http.MethodGet, server.URL, nil)
			if err != nil {
				t.Error(err)
				done <- struct{}{}
				return
			}
			res, err := pool.Do(req)
			if err != nil {
				t.Error(err)
			} else {
				res.Body.Close()
			}
			done <- struct{}{}
		}()
	}
	for i := 0; i < 6; i++ {
		<-done
	}
	if peak.Load() > 2 {
		t.Fatalf("peak concurrency = %d, want <= 2", peak.Load())
	}
}

func TestPoolSizeCeiling(t *testing.T) {
	t.Setenv("FETCH_HTTP_POOL_SIZE", "99")
	if got := poolSize(); got != maxPoolSize {
		t.Fatalf("poolSize() = %d, want %d", got, maxPoolSize)
	}
}
