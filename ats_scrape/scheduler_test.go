package atsscrape

import (
	"io"
	"os"
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

func TestAttachedRun(t *testing.T) {
	t.Setenv("FETCH_RUN_ID", "42")
	t.Setenv("FETCH_SCHEDULE_COUNTRIES", " UK ")
	runID, country, ok := attachedRun()
	if !ok || runID != 42 || country != "uk" {
		t.Fatalf("attached=%d %s %v", runID, country, ok)
	}
	t.Setenv("FETCH_SCHEDULE_COUNTRIES", "uk,nl")
	if _, _, ok := attachedRun(); ok {
		t.Fatal("multi-country attach must not attach")
	}
	t.Setenv("FETCH_RUN_ID", "")
	if _, _, ok := attachedRun(); ok {
		t.Fatal("empty run id must not attach")
	}
}

func TestResultStatusesDistinct(t *testing.T) {
	if resultOK == resultEmpty || resultOK == resultError {
		t.Fatal("status constants must differ")
	}
}

func TestSignalCompanyReady(t *testing.T) {
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	old := os.Stdout
	os.Stdout = writer
	signalCompanyReady(42)
	writer.Close()
	os.Stdout = old
	body, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "FETCH_READY 42\n" {
		t.Fatalf("signal=%q", body)
	}
}
