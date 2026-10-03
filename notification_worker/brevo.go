package notificationworker

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

func brevoConfigured() bool {
	return strings.TrimSpace(os.Getenv("BREVO_API_KEY")) != "" &&
		strings.TrimSpace(os.Getenv("BREVO_FROM_EMAIL")) != ""
}

func sendTransactionalEmail(ctx context.Context, to, subject, text string) error {
	apiKey := strings.TrimSpace(os.Getenv("BREVO_API_KEY"))
	fromEmail := strings.TrimSpace(os.Getenv("BREVO_FROM_EMAIL"))
	if apiKey == "" || fromEmail == "" {
		return fmt.Errorf("brevo not configured")
	}
	recipient := strings.TrimSpace(to)
	if recipient == "" {
		return fmt.Errorf("empty recipient")
	}
	fromName := strings.TrimSpace(os.Getenv("BREVO_FROM_NAME"))
	if fromName == "" {
		fromName = "Kuchup"
	}
	body, err := json.Marshal(map[string]any{
		"sender": map[string]string{"name": fromName, "email": fromEmail},
		"to":     []map[string]string{{"email": recipient}},
		"subject": subject,
		"textContent": text,
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.brevo.com/v3/smtp/email", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("accept", "application/json")
	req.Header.Set("content-type", "application/json")
	req.Header.Set("api-key", apiKey)
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("brevo status %d", resp.StatusCode)
	}
	return nil
}
