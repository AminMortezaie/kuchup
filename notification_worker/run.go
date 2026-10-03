package notificationworker

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

type waveMessage struct {
	Type       string `json:"type"`
	Country    string `json:"country"`
	FetchRunID int    `json:"fetch_run_id"`
}

func Main() {
	once := flag.Bool("once", false, "process one SQS poll batch and exit")
	country := flag.String("country", "", "process one country wave and exit")
	fetchRunID := flag.Int("fetch-run-id", 0, "fetch run id for --country")
	wait := flag.Int("wait-seconds", 10, "SQS long-poll wait")
	maxMsg := flag.Int("max-messages", 5, "SQS receive batch size")
	sleep := flag.Float64("sleep-seconds", 1, "sleep between polls")
	flag.Parse()

	ctx := context.Background()
	store, err := OpenStore(ctx)
	if err != nil {
		log.Fatal(err)
	}
	defer store.Close(ctx)

	if strings.TrimSpace(*country) != "" {
		if *fetchRunID <= 0 {
			log.Fatal("--country requires --fetch-run-id")
		}
		if err := ProcessCountryWave(ctx, store, *country, *fetchRunID); err != nil {
			log.Fatal(err)
		}
		return
	}

	if err := pollLoop(ctx, store, *once, *wait, *maxMsg, *sleep); err != nil {
		log.Fatal(err)
	}
}

func pollLoop(ctx context.Context, store *Store, once bool, wait, maxMsg int, sleep float64) error {
	queueURL := strings.TrimSpace(os.Getenv("SQS_JOB_NOTIFY_QUEUE_URL"))
	if queueURL == "" {
		return fmt.Errorf("SQS_JOB_NOTIFY_QUEUE_URL is not set")
	}
	cfg, err := config.LoadDefaultConfig(ctx, config.WithRegion(strings.TrimSpace(os.Getenv("AWS_REGION"))))
	if err != nil {
		return err
	}
	if cfg.Region == "" {
		cfg.Region = "eu-central-1"
	}
	client := sqs.NewFromConfig(cfg)
	for {
		out, err := client.ReceiveMessage(ctx, &sqs.ReceiveMessageInput{
			QueueUrl:            aws.String(queueURL),
			MaxNumberOfMessages: int32(max(1, min(maxMsg, 10))),
			WaitTimeSeconds:     int32(max(0, min(wait, 20))),
			VisibilityTimeout:   120,
		})
		if err != nil {
			return err
		}
		errors := 0
		for _, raw := range out.Messages {
			var msg waveMessage
			if err := json.Unmarshal([]byte(aws.ToString(raw.Body)), &msg); err != nil {
				log.Printf("bad message: %v", err)
				errors++
				continue
			}
			if err := handle(ctx, store, msg); err != nil {
				log.Printf("job failed country=%s fetch_run_id=%d: %v", msg.Country, msg.FetchRunID, err)
				errors++
				continue
			}
			if _, err := client.DeleteMessage(ctx, &sqs.DeleteMessageInput{
				QueueUrl:      aws.String(queueURL),
				ReceiptHandle: raw.ReceiptHandle,
			}); err != nil {
				log.Printf("delete failed: %v", err)
				errors++
			}
		}
		log.Printf("poll received=%d errors=%d", len(out.Messages), errors)
		if once {
			if errors > 0 {
				return fmt.Errorf("poll errors=%d", errors)
			}
			return nil
		}
		time.Sleep(time.Duration(sleep * float64(time.Second)))
	}
}

func handle(ctx context.Context, store *Store, msg waveMessage) error {
	if strings.ToLower(strings.TrimSpace(msg.Type)) != "country_wave" {
		return fmt.Errorf("unknown type %q", msg.Type)
	}
	return ProcessCountryWave(ctx, store, msg.Country, msg.FetchRunID)
}
