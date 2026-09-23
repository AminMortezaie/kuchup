package atsscrape

import (
	"html"
	"regexp"
)

var tagRE = regexp.MustCompile(`<[^>]+>`)

func plainText(raw string) string {
	text := html.UnescapeString(raw)
	text = tagRE.ReplaceAllString(text, " ")
	return normalizeSpace(text)
}
