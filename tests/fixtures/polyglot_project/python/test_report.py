from report import report_title


def test_report_title() -> None:
    assert report_title() == "Portfolio report"
