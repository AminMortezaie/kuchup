package atsscrape

import (
	"context"
	"net/http"
	"sync"
	"time"
)

const maxPoolSize = 16

type HTTPPool struct {
	sem    chan struct{}
	client *http.Client
}

func NewHTTPPool(size int, timeout time.Duration) *HTTPPool {
	if size < 1 {
		size = 1
	}
	if size > maxPoolSize {
		size = maxPoolSize
	}
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	return &HTTPPool{
		sem: make(chan struct{}, size),
		client: &http.Client{
			Timeout: timeout,
		},
	}
}

func (p *HTTPPool) Do(req *http.Request) (*http.Response, error) {
	p.sem <- struct{}{}
	defer func() { <-p.sem }()
	return p.client.Do(req)
}

func (p *HTTPPool) RunGroup(ctx context.Context, tasks []func(context.Context, getter) error) error {
	if len(tasks) == 0 {
		return nil
	}
	errCh := make(chan error, len(tasks))
	var wg sync.WaitGroup
	for _, task := range tasks {
		task := task
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := task(ctx, p); err != nil {
				errCh <- err
			}
		}()
	}
	wg.Wait()
	close(errCh)
	for err := range errCh {
		if err != nil {
			return err
		}
	}
	return nil
}
