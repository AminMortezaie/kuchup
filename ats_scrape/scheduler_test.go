package atsscrape

import (
	"testing"
)

func TestScheduleEnabled(t *testing.T) {
	t.Setenv("FETCH_SCHEDULE_ENABLED", "1")
	if !scheduleEnabled() {
		t.Fatal("expected enabled")
	}
	t.Setenv("FETCH_SCHEDULE_ENABLED", "0")
	if scheduleEnabled() {
		t.Fatal("expected disabled")
	}
}

func TestScheduleCountriesFromEnv(t *testing.T) {
	t.Setenv("FETCH_SCHEDULE_COUNTRIES", " uk , nl , uk ")
	countries, err := scheduleCountries(t.Context(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(countries) != 2 || countries[0] != "uk" || countries[1] != "nl" {
		t.Fatalf("countries=%v", countries)
	}
}

func TestResultStatusesDistinct(t *testing.T) {
	if resultOK == resultEmpty || resultOK == resultError {
		t.Fatal("status constants must differ")
	}
}
