from relocation_jobs.team_docs.markdown import render_markdown


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
