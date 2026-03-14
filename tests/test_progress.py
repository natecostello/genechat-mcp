"""Tests for genechat.progress (lightweight progress reporting)."""

import io

from genechat.progress import (
    ProgressLine,
    format_elapsed,
    format_eta,
    format_size,
    format_speed,
)


class TestFormatElapsed:
    def test_seconds(self):
        assert format_elapsed(5) == "5s"

    def test_minutes(self):
        assert format_elapsed(125) == "2m 05s"

    def test_hours(self):
        assert format_elapsed(3725) == "1h 02m"

    def test_zero(self):
        assert format_elapsed(0) == "0s"


class TestFormatEta:
    def test_calculates_remaining(self):
        # 50% done in 10 seconds → 10s remaining
        eta = format_eta(10.0, 50, 100)
        assert eta == "10s"

    def test_returns_empty_for_zero_progress(self):
        assert format_eta(10.0, 0, 100) == ""

    def test_returns_empty_for_zero_total(self):
        assert format_eta(10.0, 50, 0) == ""


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2 KB"

    def test_megabytes(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(3 * 1024 * 1024 * 1024) == "3.0 GB"


class TestFormatSpeed:
    def test_kb_per_sec(self):
        result = format_speed(512 * 1024, 1.0)
        assert "KB/s" in result

    def test_mb_per_sec(self):
        result = format_speed(10 * 1024 * 1024, 1.0)
        assert "MB/s" in result

    def test_zero_seconds(self):
        assert format_speed(1024, 0.0) == ""


class TestProgressLine:
    def test_done_prints_final_line(self):
        buf = io.StringIO()
        buf.isatty = lambda: False  # type: ignore[attr-defined]
        p = ProgressLine("test", file=buf)
        p.done("finished")
        output = buf.getvalue()
        assert "test" in output
        assert "finished" in output

    def test_update_with_total_computes_pct(self):
        buf = io.StringIO()
        buf.isatty = lambda: False  # type: ignore[attr-defined]
        # report_pct=50 means output at 0%, 50%, 100%
        p = ProgressLine("test", total=100, file=buf, report_pct=50)
        p.update(0)
        p.update(50)
        p.update(100)
        output = buf.getvalue()
        assert "50%" in output or "100%" in output

    def test_update_without_total_uses_interval(self):
        buf = io.StringIO()
        buf.isatty = lambda: False  # type: ignore[attr-defined]
        # Very short interval for testing
        p = ProgressLine("test", file=buf, report_interval=0.001)
        import time

        p.update(1000)
        time.sleep(0.01)
        p.update(2000)
        output = buf.getvalue()
        assert "test" in output
