from __future__ import annotations

from tests.helpers.http_mock import MockResponse

from relocation_jobs.scrape.job_text import fetch_job_detail


def test_fetch_job_detail_rejects_page_chrome(monkeypatch):
    html = """
    <html><body>
      <header>Skip to main content</header>
      <p>Only necessary cookies. Manage cookie preferences. Accept all.</p>
      <p>We are looking for a backend engineer with five years of experience
      building APIs and owning production systems day to day.</p>
      <p>Your profile includes Python, Postgres, and distributed systems work.</p>
      <footer>Powered by Personio. Back to all jobs.</footer>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        return MockResponse(text=html)

    monkeypatch.setattr("relocation_jobs.scrape.job_text.requests.get", fake_get)
    result = fetch_job_detail("https://jobs.example.com/role", "generic")
    assert result.text == ""


def test_fetch_job_detail_keeps_article_body(monkeypatch):
    html = """
    <html><body>
      <nav>All jobs. Cookie preferences.</nav>
      <article>
        <h2>About the role</h2>
        <p>We are looking for a backend engineer with five years of experience
        building APIs and owning production systems day to day across our lending
        platform in Berlin, including on-call ownership and design reviews.</p>
        <p>Your profile includes Python, Postgres, and distributed systems work
        across several product teams, plus a track record of shipping well-tested
        services used by millions of customers every week.</p>
      </article>
      <footer>Powered by Personio</footer>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        return MockResponse(text=html)

    monkeypatch.setattr("relocation_jobs.scrape.job_text.requests.get", fake_get)
    result = fetch_job_detail("https://jobs.example.com/role", "generic")
    assert "We are looking for a backend engineer" in result.text
    assert "Skip to main content" not in result.text
    assert "Powered by Personio" not in result.text


def test_fetch_job_detail_strips_leftover_ats_chrome(monkeypatch):
    html = """
    <html><body>
      <main>
        <p>Skip to main content. Back to all jobs. Apply for this job.</p>
        <p>We are looking for a backend engineer with five years of experience
        building APIs and owning production systems day to day across our lending
        platform in Berlin, including on-call ownership and design reviews.</p>
        <p>Your profile includes Python, Postgres, and distributed systems work
        across several product teams, plus a track record of shipping well-tested
        services used by millions of customers every week.</p>
      </main>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        return MockResponse(text=html)

    monkeypatch.setattr("relocation_jobs.scrape.job_text.requests.get", fake_get)
    result = fetch_job_detail("https://acme.jobs.personio.de/job/1", "generic")
    assert "We are looking for a backend engineer" in result.text
    assert "Skip to main content" not in result.text
    assert "Apply for this job" not in result.text
