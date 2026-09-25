package main

import (
	"os"

	atsscrape "kuchup/ats_scrape"
)

func main() {
	os.Exit(atsscrape.RunScheduler())
}
