package notificationworker

import "testing"

func TestNewJobsNotificationBody(t *testing.T) {
	if newJobsNotificationBody(1) != "1 new job found!" {
		t.Fatal("singular")
	}
	if newJobsNotificationBody(7) != "7 new jobs found!" {
		t.Fatal("plural")
	}
}
