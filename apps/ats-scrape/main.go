package main

import (
	"os"

	atsscrape "kuchup/ats_scrape"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "describe" {
		os.Exit(atsscrape.RunDescribe())
	}
	os.Exit(atsscrape.RunScheduler())
}
