from pathlib import Path


def test_position_more_btn_contains_its_label():
    styles = Path("relocation_jobs/static/styles.css").read_text(encoding="utf-8")
    more = styles.split(".position-more-btn {", 1)[1].split("}", 1)[0]
    assert "position: relative" in more
