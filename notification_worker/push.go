package notificationworker

import (
	"encoding/json"
	"os"
	"strings"

	webpush "github.com/SherClockHolmes/webpush-go"
)

func vapidConfigured() bool {
	return strings.TrimSpace(os.Getenv("VAPID_PUBLIC_KEY")) != "" &&
		strings.TrimSpace(os.Getenv("VAPID_PRIVATE_KEY")) != ""
}

func vapidSubject() string {
	subject := strings.TrimSpace(os.Getenv("VAPID_SUBJECT"))
	if subject == "" {
		return "mailto:hello@kuchup.com"
	}
	return subject
}

func sendWebPush(sub PushSubscription, title, body string) (status int, err error) {
	if !vapidConfigured() {
		return 0, nil
	}
	payload, err := json.Marshal(map[string]string{"title": title, "body": body})
	if err != nil {
		return 0, err
	}
	resp, err := webpush.SendNotification(payload, &webpush.Subscription{
		Endpoint: sub.Endpoint,
		Keys: webpush.Keys{
			P256dh: sub.P256dh,
			Auth:   sub.Auth,
		},
	}, &webpush.Options{
		VAPIDPublicKey:  strings.TrimSpace(os.Getenv("VAPID_PUBLIC_KEY")),
		VAPIDPrivateKey: strings.TrimSpace(os.Getenv("VAPID_PRIVATE_KEY")),
		Subscriber:      vapidSubject(),
		TTL:             86400,
	})
	if err != nil {
		return 0, err
	}
	if resp != nil {
		defer resp.Body.Close()
		return resp.StatusCode, nil
	}
	return 0, nil
}
