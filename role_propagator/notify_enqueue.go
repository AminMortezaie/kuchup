package rolepropagator

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"strconv"
	"strings"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

type notifyWaveMessage struct {
	Type        string `json:"type"`
	Country     string `json:"country"`
	FetchRunID  int    `json:"fetch_run_id"`
}

func enqueueNotifyCountryWave(ctx context.Context, country string, fetchRunID int) {
	if fetchRunID <= 0 {
		return
	}
	country = strings.ToLower(strings.TrimSpace(country))
	if country == "" {
		return
	}
	queueURL := strings.TrimSpace(os.Getenv("SQS_JOB_NOTIFY_QUEUE_URL"))
	if queueURL != "" {
		if err := sendNotifySQS(ctx, queueURL, country, fetchRunID); err != nil {
			log.Printf("notify enqueue sqs failed country=%s fetch_run_id=%d: %v", country, fetchRunID, err)
		}
		return
	}
	bin := strings.TrimSpace(os.Getenv("NOTIFICATION_WORKER_BIN"))
	if bin == "" {
		return
	}
	cmd := exec.CommandContext(ctx, bin, "--country", country, "--fetch-run-id", strconv.Itoa(fetchRunID))
	if out, err := cmd.CombinedOutput(); err != nil {
		log.Printf("notify worker bin failed: %v %s", err, strings.TrimSpace(string(out)))
	}
}

func sendNotifySQS(ctx context.Context, queueURL, country string, fetchRunID int) error {
	payload, err := json.Marshal(notifyWaveMessage{
		Type:       "country_wave",
		Country:    country,
		FetchRunID: fetchRunID,
	})
	if err != nil {
		return err
	}
	cfg, err := config.LoadDefaultConfig(ctx, config.WithRegion(strings.TrimSpace(os.Getenv("AWS_REGION"))))
	if err != nil {
		return err
	}
	if cfg.Region == "" {
		cfg.Region = "eu-central-1"
	}
	client := sqs.NewFromConfig(cfg)
	_, err = client.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:    aws.String(queueURL),
		MessageBody: aws.String(string(payload)),
	})
	return err
}
