package notificationworker

import (
	"context"
	"log"
	"os"
	"strings"
)

const pushTitle = "Kuchup"

func panelBaseURL() string {
	base := strings.TrimSpace(os.Getenv("PANEL_PUBLIC_BASE_URL"))
	if base == "" {
		base = strings.TrimSpace(os.Getenv("PUBLIC_SITE_URL"))
	}
	if base == "" {
		base = "https://kuchup.com"
	}
	return strings.TrimRight(base, "/")
}

func ProcessCountryWave(ctx context.Context, store *Store, country string, fetchRunID int) error {
	if fetchRunID <= 0 {
		return nil
	}
	country = strings.ToLower(strings.TrimSpace(country))
	users, err := store.ListFullPlanNotifyUsers(ctx)
	if err != nil {
		return err
	}
	for _, user := range users {
		if err := notifyUserWave(ctx, store, user, country, fetchRunID); err != nil {
			log.Printf("notify user %d: %v", user.ID, err)
		}
	}
	return nil
}

func notifyUserWave(ctx context.Context, store *Store, user NotifyUser, country string, fetchRunID int) error {
	count, err := store.CountWaveJobsForUser(ctx, user.ID, country, fetchRunID)
	if err != nil {
		return err
	}
	if count <= 0 {
		return nil
	}
	already, err := store.WaveAlreadyNotified(ctx, user.ID, fetchRunID)
	if err != nil {
		return err
	}
	if already {
		return nil
	}
	body := newJobsNotificationBody(count)
	delivered := false

	if vapidConfigured() {
		subs, err := store.ListPushSubscriptions(ctx, user.ID)
		if err != nil {
			return err
		}
		for _, sub := range subs {
			status, err := sendWebPush(sub, pushTitle, body)
			if err != nil {
				log.Printf("web push user=%d endpoint=%s: %v", user.ID, sub.Endpoint, err)
				continue
			}
			if status == 410 {
				_ = store.DeletePushSubscription(ctx, sub.Endpoint)
				continue
			}
			if status >= 200 && status < 300 {
				delivered = true
			}
		}
	}

	email := strings.TrimSpace(user.Email)
	if email != "" && brevoConfigured() {
		subject := newJobsEmailSubject(count)
		text := body + "\n\nOpen your board: " + panelBaseURL() + "/panel"
		if err := sendTransactionalEmail(ctx, email, subject, text); err != nil {
			log.Printf("email user=%d: %v", user.ID, err)
		} else {
			delivered = true
		}
	}

	if delivered {
		return store.MarkWaveNotified(ctx, user.ID, fetchRunID)
	}
	return nil
}
