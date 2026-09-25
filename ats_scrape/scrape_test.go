package atsscrape

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func testClient(t *testing.T, f roundTripFunc) *http.Client {
	t.Helper()
	return &http.Client{Transport: f}
}

func jsonBody(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     make(http.Header),
	}
}

func TestGreenhouseParsesJobs(t *testing.T) {
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		if req.URL.Host != "boards-api.greenhouse.io" || !strings.Contains(req.URL.Path, "/acmebackend/jobs") {
			t.Fatalf("unexpected url %s", req.URL)
		}
		return jsonBody(200, `{"jobs":[
			{"title":"Senior Backend Engineer","absolute_url":"https://boards.greenhouse.io/acmebackend/jobs/1","location":{"name":"London"}},
			{"title":"","absolute_url":"https://boards.greenhouse.io/acmebackend/jobs/2"}
		]}`), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType: "greenhouse",
		ATSURL:  "https://boards.greenhouse.io/acmebackend",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 1 || jobs[0].Title != "Senior Backend Engineer" || jobs[0].Location != "London" {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestLeverUsesEUHost(t *testing.T) {
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		if req.URL.Host != "jobs.eu.lever.co" {
			t.Fatalf("host %s", req.URL.Host)
		}
		return jsonBody(200, `[{"text":"Platform Engineer","hostedUrl":"https://jobs.eu.lever.co/tomtom/platform","categories":{"location":"Amsterdam"},"descriptionPlain":"Build APIs."}]`), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType: "lever_eu",
		ATSURL:  "https://jobs.eu.lever.co/tomtom",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 1 || jobs[0].DescriptionText != "Build APIs." || jobs[0].Location != "Amsterdam" {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestAshbySecondaryLocations(t *testing.T) {
	jobs := parseAshbyJobs(map[string]any{
		"jobs": []any{map[string]any{
			"title":    "Software Engineer",
			"jobUrl":   "https://jobs.ashbyhq.com/acme/abcd",
			"location": "Georgia",
			"secondaryLocations": []any{map[string]any{
				"location": "Armenia",
				"address": map[string]any{
					"postalAddress": map[string]any{
						"addressCountry":  "Armenia",
						"addressLocality": "Yerevan",
					},
				},
			}},
		}},
	}, "https://jobs.ashbyhq.com/acme")
	if len(jobs) != 1 || jobs[0].Location != "Georgia" {
		t.Fatalf("jobs = %#v", jobs)
	}
	joined := strings.Join(jobs[0].Locations, ",")
	if !strings.Contains(joined, "Yerevan") || !strings.Contains(joined, "Armenia") {
		t.Fatalf("locations = %#v", jobs[0].Locations)
	}
}

func TestGenericListingHTML(t *testing.T) {
	page := `<html><body>
	  <a href="/jobs/backend-engineer">Backend Engineer</a>
	  <a href="/jobs/data-scientist">Data Scientist</a>
	</body></html>`
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		return jsonBody(200, page), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType:    "generic",
		CareersURL: "https://careers.example.com/",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 2 || jobs[0].URL != "https://careers.example.com/jobs/backend-engineer" {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestKakeCardLocations(t *testing.T) {
	page := `<div>
	  <a href="/jobs/senior-backend-engineer-go-39007733f3d6">Senior Backend Engineer (Go)</a>
	  <span>Timezone: <strong>GMT-5</strong></span>
	</div>
	<a href="/jobs/senior-backend-engineer-go-39007733f3d6">Senior Backend Engineer (Go)</a>`
	jobs := parseKakeHTML(page)
	if len(jobs) != 1 || jobs[0].Location != "Remote, GMT-5" || jobs[0].Employer != "Kake" {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestWorkablePost(t *testing.T) {
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		if req.Method != http.MethodPost || !strings.Contains(req.URL.Path, "/accounts/acme/jobs") {
			t.Fatalf("request %s %s", req.Method, req.URL)
		}
		return jsonBody(200, `{"results":[{"title":"Backend Software Engineer","shortcode":"ABC123","location":{"city":"Amsterdam","region":"North Holland","country":"Netherlands"}}]}`), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType: "workable",
		ATSURL:  "https://apply.workable.com/acme/",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 1 || jobs[0].URL != "https://apply.workable.com/acme/j/ABC123/" || !strings.Contains(jobs[0].Location, "Amsterdam") {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestPersonioXMLDescriptions(t *testing.T) {
	xml := `<?xml version="1.0" encoding="UTF-8"?><workzag><position><id>54321</id><name>Platform Engineer</name><office>Munich</office><jobDescriptions><jobDescription><name>Your mission</name><value><![CDATA[<p>Build APIs</p>]]></value></jobDescription></jobDescriptions></position></workzag>`
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		if !strings.HasSuffix(req.URL.Path, "/xml") {
			t.Fatalf("url %s", req.URL)
		}
		return jsonBody(200, xml), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType: "personio",
		ATSURL:  "https://acme.jobs.personio.de/",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 1 || !strings.Contains(jobs[0].DescriptionText, "Build APIs") || jobs[0].Location != "Munich" {
		t.Fatalf("jobs = %#v", jobs)
	}
}

func TestUnsupportedATS(t *testing.T) {
	_, err := Scrape(context.Background(), testClient(t, func(req *http.Request) (*http.Response, error) {
		t.Fatal("should not fetch")
		return nil, nil
	}), Request{ATSType: "hibob", ATSURL: "https://example.com/jobs"})
	if err != ErrUnsupported {
		t.Fatalf("err = %v", err)
	}
}

func TestOversizedResponse(t *testing.T) {
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		return jsonBody(200, strings.Repeat("x", (8<<20)+1)), nil
	})
	_, err := Scrape(context.Background(), client, Request{
		ATSType: "greenhouse",
		ATSURL:  "https://boards.greenhouse.io/acmebackend",
	})
	if err == nil || !strings.Contains(err.Error(), "exceeds 8 MiB") {
		t.Fatalf("err = %v", err)
	}
}

func TestRecruiteeOffers(t *testing.T) {
	client := testClient(t, func(req *http.Request) (*http.Response, error) {
		if req.URL.String() != "https://acme.recruitee.com/api/offers/" {
			t.Fatalf("url %s", req.URL)
		}
		return jsonBody(200, `{"offers":[{"title":"Backend Developer","careers_url":"https://acme.recruitee.com/o/backend","location":"Amsterdam"}]}`), nil
	})
	jobs, err := Scrape(context.Background(), client, Request{
		ATSType: "recruitee",
		ATSURL:  "https://acme.recruitee.com/",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) != 1 || jobs[0].Location != "Amsterdam" {
		t.Fatalf("jobs = %#v", jobs)
	}
}
