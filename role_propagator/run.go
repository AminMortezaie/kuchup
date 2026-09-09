package rolepropagator

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

type message struct {
	Type         string `json:"type"`
	UserID       int    `json:"user_id"`
	Country      string `json:"country"`
	CompanyName  string `json:"company_name"`
	SourceJobKey string `json:"source_job_key"`
}

func Main() {
	once := flag.Bool("once", false, "process one SQS poll batch and exit")
	userID := flag.Int("user", 0, "reconcile one user and exit")
	country := flag.String("country", "", "reconcile users targeting this country and exit")
	replace := flag.Bool("replace", false, "insert one replacement assignment")
	company := flag.String("company", "", "company for --replace")
	sourceKey := flag.String("source-job-key", "", "consumed job key for --replace")
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

	switch {
	case *replace:
		if *userID == 0 || strings.TrimSpace(*country) == "" || strings.TrimSpace(*company) == "" {
			log.Fatal("--replace requires --user --country --company")
		}
		if err := reconcileReplace(ctx, store, *userID, *country, *company, *sourceKey); err != nil {
			log.Fatal(err)
		}
	case *userID > 0:
		if err := reconcileUser(ctx, store, *userID); err != nil {
			log.Fatal(err)
		}
	case strings.TrimSpace(*country) != "":
		if err := reconcileCountry(ctx, store, *country); err != nil {
			log.Fatal(err)
		}
	default:
		if err := pollLoop(ctx, store, *once, *wait, *maxMsg, *sleep); err != nil {
			log.Fatal(err)
		}
	}
}

func pollLoop(ctx context.Context, store *Store, once bool, wait, maxMsg int, sleep float64) error {
	queueURL := strings.TrimSpace(os.Getenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL"))
	if queueURL == "" {
		return fmt.Errorf("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL is not set")
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
			VisibilityTimeout:   60,
		})
		if err != nil {
			return err
		}
		errors := 0
		for _, raw := range out.Messages {
			var msg message
			if err := json.Unmarshal([]byte(aws.ToString(raw.Body)), &msg); err != nil {
				log.Printf("bad message: %v", err)
				errors++
				continue
			}
			if err := handle(ctx, store, msg); err != nil {
				log.Printf("job failed type=%s user=%d: %v", msg.Type, msg.UserID, err)
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

func handle(ctx context.Context, store *Store, msg message) error {
	switch strings.ToLower(strings.TrimSpace(msg.Type)) {
	case "user":
		return reconcileUser(ctx, store, msg.UserID)
	case "country":
		return reconcileCountry(ctx, store, msg.Country)
	case "replace":
		return reconcileReplace(ctx, store, msg.UserID, msg.Country, msg.CompanyName, msg.SourceJobKey)
	default:
		return fmt.Errorf("unknown type %q", msg.Type)
	}
}

func reconcileUser(ctx context.Context, store *Store, userID int) error {
	user, err := store.LoadUser(ctx, userID)
	if err != nil {
		return err
	}
	countries, err := store.PrefsCountries(ctx, userID)
	if err != nil {
		return err
	}
	prefs := map[string]bool{}
	for _, c := range countries {
		prefs[c] = true
	}
	candidates, err := store.ListCandidates(ctx, countries)
	if err != nil {
		return err
	}
	existing, err := store.ListOpportunities(ctx, userID)
	if err != nil {
		return err
	}
	var capPtr *int
	if !user.Unlimited() {
		n := envInt("FREE_BOARD_COMPANY_CAP", 10)
		capPtr = &n
	}
	slots := ReconcileSticky(existing, candidates, prefs, capPtr)
	if err := store.ReplaceOpportunities(ctx, userID, slots); err != nil {
		return err
	}
	if user.Unlimited() {
		return nil
	}
	perCompany := envInt("FREE_JOBS_PER_COMPANY", 3)
	period := periodKey()
	for _, slot := range slots {
		jobs, err := store.ListJobs(ctx, slot.Country, slot.CompanyName)
		if err != nil {
			return err
		}
		assigned, consumed, err := store.AssignmentMaps(ctx, userID, period, slot.Country, slot.CompanyName)
		if err != nil {
			return err
		}
		for _, job := range PickJobs(jobs, assigned, consumed, perCompany) {
			if err := store.InsertAssignment(ctx, userID, period, slot.Country, slot.CompanyName, job); err != nil {
				return err
			}
		}
	}
	return nil
}

func reconcileCountry(ctx context.Context, store *Store, country string) error {
	ids, err := store.UserIDsForCountry(ctx, country)
	if err != nil {
		return err
	}
	for _, id := range ids {
		if err := reconcileUser(ctx, store, id); err != nil {
			log.Printf("user %d: %v", id, err)
		}
	}
	return nil
}

func reconcileReplace(ctx context.Context, store *Store, userID int, country, company, _ string) error {
	user, err := store.LoadUser(ctx, userID)
	if err != nil {
		return err
	}
	if user.Unlimited() {
		return nil
	}
	jobs, err := store.ListJobs(ctx, country, company)
	if err != nil {
		return err
	}
	assigned, _, err := store.AssignmentMaps(ctx, userID, periodKey(), country, company)
	if err != nil {
		return err
	}
	job := PickReplacement(jobs, assigned)
	if job == nil {
		return fmt.Errorf("no replacement for user %d %s/%s", userID, country, company)
	}
	return store.InsertAssignment(ctx, userID, periodKey(), country, company, *job)
}
