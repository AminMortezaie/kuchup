from __future__ import annotations

from tests.helpers.http_mock import MockResponse

from relocation_jobs.scrape.boards.join import fetch_join_job_detail


def test_fetch_join_job_detail_reads_next_data(monkeypatch):
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"job":{"description":"<p>Build APIs. Visa sponsorship available.</p>","location":{"name":"Berlin"}}}}}
    </script>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        return MockResponse(text=html)

    monkeypatch.setattr("relocation_jobs.scrape.boards.join.requests.get", fake_get)
    text, location = fetch_join_job_detail(
        "https://join.com/companies/acme/backend-engineer-123"
    )
    assert "Build APIs" in text
    assert location == "Berlin"
