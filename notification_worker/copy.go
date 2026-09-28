package notificationworker

import "fmt"

func newJobsNotificationBody(count int) string {
	if count == 1 {
		return "1 new job found!"
	}
	return fmt.Sprintf("%d new jobs found!", count)
}

func newJobsEmailSubject(count int) string {
	if count == 1 {
		return "1 new job on your Kuchup board"
	}
	return fmt.Sprintf("%d new jobs on your Kuchup board", count)
}
