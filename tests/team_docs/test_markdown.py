from relocation_jobs.team_docs.markdown import drop_matching_lead_h1, render_markdown


def test_renders_article_blocks():
    html = render_markdown(
        "# Title\n\nIntro line\nkeeps going\n\n"
        "## Next\n\n- one\n- two\n\n1. first\n\n> quoted **bold**\n\n---\n"
    )
    assert html.startswith("<h1>Title</h1><p>Intro line keeps going</p><h2>Next</h2>")
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<ol><li>first</li></ol>" in html
    assert "<blockquote><p>quoted <strong>bold</strong></p></blockquote><hr>" in html


def test_escapes_raw_html_and_unsafe_links():
    html = render_markdown(
        "<script>alert(1)</script>\n\n"
        '<img src=x onerror="alert(1)">\n\n'
        "[bad](javascript:alert(1))\n\n"
        "[ok](https://kuchup.com/a)\n\n"
        "[mail](mailto:ops@kuchup.com)\n\n"
        "[local](/admin)\n\n"
        "[scheme](data:text/html,hi)\n"
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert "javascript:" not in html
    assert "data:" not in html
    assert "&lt;img" in html
    assert html.count("<a ") == 3
    assert 'href="https://kuchup.com/a"' in html
    assert 'href="mailto:ops@kuchup.com"' in html
    assert 'href="/admin"' in html
    assert "&lt;script&gt;" in html


def test_fenced_code_and_inline_code_are_literal():
    html = render_markdown("Use `team_docs` and **bold**.\n\n```\n<script>alert(1)</script>\n```\n")
    assert "<code>team_docs</code>" in html
    assert "<strong>bold</strong>" in html
    assert "<pre><code>&lt;script&gt;alert(1)&lt;/script&gt;</code></pre>" in html
    assert "<script>" not in html


def test_emphasis_does_not_eat_snake_case():
    html = render_markdown("Keep team_docs and a_b_c, plus *note*.")
    assert "team_docs" in html
    assert "a_b_c" in html
    assert "<em>note</em>" in html
    assert "<em>docs</em>" not in html


def test_empty_markdown():
    assert render_markdown(None) == ""
    assert render_markdown("   \n") == ""


def test_renders_gfm_tables_with_alignment():
    html = render_markdown(
        "| Measure | Snapshot |\n"
        "| --- | ---: |\n"
        "| Companies | Approximately 418 |\n"
        "| Roles | **1,453** |\n\n"
        "After table.\n"
    )
    assert "<table><thead><tr><th>Measure</th><th align=\"right\">Snapshot</th></tr></thead>" in html
    assert "<tbody><tr><td>Companies</td><td align=\"right\">Approximately 418</td></tr>" in html
    assert "<td align=\"right\"><strong>1,453</strong></td>" in html
    assert html.endswith("<p>After table.</p>")


def test_drops_lead_h1_when_it_matches_title():
    html = drop_matching_lead_h1(
        render_markdown("# Admin audit snapshot — 2026-09-17\n\n## Purpose\n\nBody.\n"),
        "Admin audit snapshot — 2026-09-17",
    )
    assert not html.startswith("<h1>")
    assert html.startswith("<h2>Purpose</h2><p>Body.</p>")
    kept = drop_matching_lead_h1(render_markdown("# Other\n\nBody.\n"), "Admin audit snapshot — 2026-09-17")
    assert kept.startswith("<h1>Other</h1>")
