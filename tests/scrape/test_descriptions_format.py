from __future__ import annotations

from relocation_jobs.scrape.descriptions import (
    format_job_description,
    html_job_body,
    html_to_readable,
    looks_like_html,
    looks_like_page_chrome,
    sanitize_job_description_html,
)


SAMPLE_HTML = """
<p><img src="https://example.com/hero.jpg" alt="hero"></p>
<h3>The Opportunity</h3>
<p>At NavVis, we build cutting-edge technology across industries.</p>
<ul>
  <li>Design developer tooling</li>
  <li>Improve the inner loop end to end</li>
</ul>
<p><strong>This is not a DevOps role.</strong></p>
"""


def test_looks_like_html_detects_markup():
    assert looks_like_html(SAMPLE_HTML) is True
    assert looks_like_html("Plain text only.") is False


def test_html_to_readable_preserves_structure_without_tags():
    readable = html_to_readable(SAMPLE_HTML)
    assert "The Opportunity" in readable
    assert "cutting-edge technology" in readable
    assert "• Design developer tooling" in readable
    assert "<p>" not in readable


def test_sanitize_job_description_html_strips_images_and_attributes():
    html = sanitize_job_description_html(SAMPLE_HTML)
    assert "<img" not in html
    assert 'data-contrast="auto"' not in html
    assert "<h3>" in html
    assert "<ul>" in html
    assert "<li>Design developer tooling</li>" in html


def test_sanitize_job_description_html_drops_comments():
    html = sanitize_job_description_html("<div><!--block-->Hello</div>")
    assert "block" not in html
    assert "Hello" in html


def test_format_job_description_returns_readable_and_display_html():
    readable, display_html = format_job_description(SAMPLE_HTML)
    assert readable
    assert display_html
    assert "<h3>" in display_html
    assert "<img" not in display_html


def test_looks_like_page_chrome_requires_two_markers():
    assert looks_like_page_chrome("We offer visa sponsorship.") is False
    assert looks_like_page_chrome(
        "Skip to main content. Powered by Personio. Back to all jobs."
    ) is True


def test_html_job_body_keeps_article_and_drops_nav():
    html = """
    <html><body>
      <nav>All jobs</nav>
      <article>
        <h2>About the role</h2>
        <p>Build APIs in Go for our lending platform and own production.</p>
        <p>We are looking for engineers who write tests and ship weekly.</p>
      </article>
      <footer>Powered by Greenhouse</footer>
    </body></html>
    """
    text = html_job_body(html)
    assert "Build APIs in Go" in text
    assert "All jobs" not in text
    assert "Powered by Greenhouse" not in text


def test_format_job_description_drops_unrecoverable_chrome():
    raw = (
        "Apply as a Backend Engineer at N26. Compare personal plans. "
        "Standard Bank for free. Smart Bank with more control."
    )
    readable, display_html = format_job_description(raw)
    assert readable == ""
    assert display_html == ""
    cookie = (
        "Senior Golang Developer. This website uses cookies to ensure you get "
        "the best experience. Leaseweb and our selected partners use cookies."
    )
    readable, display_html = format_job_description(cookie)
    assert readable == ""
    assert display_html == ""
    german = (
        "Wir verwenden Cookies, um Ihnen die bestmögliche Erfahrung "
        "mit der Website bieten zu können."
    )
    readable, display_html = format_job_description(german)
    assert readable == ""
    assert display_html == ""


def test_format_job_description_strips_personio_chrome():
    raw = (
        "Skip to main content. Back to all jobs. Apply for this job. "
        "These tasks are waiting for you. You'll be a core contributor "
        "to the admin experience team."
    )
    readable, display_html = format_job_description(raw)
    assert "These tasks are waiting for you" in readable
    assert "Skip to main content" not in readable
    assert "Back to all jobs" not in readable
    assert display_html


def test_format_job_description_strips_single_skip_marker():
    raw = (
        "Senior Platform Engineer at Synopsys Skip to main content "
        "We are looking for an engineer who has owned production systems "
        "and can drive observability across the platform."
    )
    readable, _ = format_job_description(raw)
    assert "We are looking for an engineer" in readable
    assert "Skip to main content" not in readable


def test_format_job_description_recovers_sumup_careers_page():
    raw = (
        "Senior Backend Engineer - MarTech in Berlin, Germany | Careers at SumUp "
        "• • • EN• ES Back to all jobs LoadingApply now About the team: "
        "The MarTech team builds marketing systems. What you’ll do: Build APIs. "
        "Job Application Tip We recognise that candidates feel they need to meet "
        "100% of the job criteria. • About • Contact Cookie Policy"
    )
    readable, _ = format_job_description(raw)
    assert "The MarTech team builds marketing systems" in readable
    assert "LoadingApply now" not in readable
    assert "Cookie Policy" not in readable
    assert "Back to all jobs" not in readable
