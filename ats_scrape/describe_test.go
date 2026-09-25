package atsscrape

import "testing"

func TestDescriptionURL(t *testing.T) {
	gh := descriptionURLs("greenhouse", "", "https://boards.greenhouse.io/gitlab/jobs/123")
	if len(gh) != 1 || gh[0] != "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs/123" {
		t.Fatal(gh)
	}
	branded := descriptionURLs("greenhouse", "https://boards.greenhouse.io/hellofresh", "https://careers.hellofresh.com/global/en/job/8161377?gh_jid=8161377")
	if len(branded) != 1 || branded[0] != "https://boards-api.greenhouse.io/v1/boards/hellofresh/jobs/8161377" {
		t.Fatal(branded)
	}
	eu := descriptionURLs("greenhouse_eu", "https://boards.eu.greenhouse.io/superchat", "https://job-boards.eu.greenhouse.io/superchat/jobs/4195554101")
	if len(eu) != 1 || eu[0] != "https://boards-api.greenhouse.io/v1/boards/superchat/jobs/4195554101" {
		t.Fatal(eu)
	}
	sr := descriptionURLs("smartrecruiters", "", "https://jobs.smartrecruiters.com/AboutYou/743999123")
	if len(sr) != 1 || sr[0] != "https://api.smartrecruiters.com/v1/companies/AboutYou/postings/743999123" {
		t.Fatal(sr)
	}
	if descriptionURLs("lever", "", "https://jobs.lever.co/acme/11111111-1111-1111-1111-111111111111") != nil {
		t.Fatal("lever list already carries descriptionPlain")
	}
}
