"""Lightweight progress reporting for long-running operations.

No external dependencies. Print-based, TTY-aware.
"""

import sys
import time


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable duration."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m"


def format_eta(elapsed: float, done: int, total: int) -> str:
    """Estimate remaining time based on progress so far."""
    if done <= 0 or total <= 0 or elapsed <= 0:
        return ""
    remaining = (elapsed / done) * (total - done)
    return format_elapsed(remaining)


def format_size(nbytes: int) -> str:
    """Format byte count as human-readable size."""
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.0f} KB"
    if nbytes < 1024 * 1024 * 1024:
        return f"{nbytes / 1024 / 1024:.1f} MB"
    return f"{nbytes / 1024 / 1024 / 1024:.1f} GB"


def format_speed(nbytes: int, seconds: float) -> str:
    """Format download speed."""
    if seconds <= 0:
        return ""
    bps = nbytes / seconds
    if bps < 1024 * 1024:
        return f"{bps / 1024:.0f} KB/s"
    return f"{bps / 1024 / 1024:.1f} MB/s"


class ProgressLine:
    """Print-based progress reporter for long operations.

    On TTY: uses \\r to overwrite the same line.
    On non-TTY: prints a new line every `report_pct` percent (or every
    `report_interval` seconds for indeterminate progress).
    """

    def __init__(
        self,
        label: str,
        total: int | None = None,
        file=None,
        report_pct: int = 10,
        report_interval: float = 30.0,
    ):
        self._label = label
        self._total = total
        self._file = file or sys.stderr
        self._is_tty = hasattr(self._file, "isatty") and self._file.isatty()
        self._start = time.monotonic()
        self._last_report_pct = -1
        self._last_report_time = self._start
        self._report_pct = report_pct
        self._report_interval = report_interval

    def update(self, current: int, suffix: str = "") -> None:
        """Report progress. Call frequently; output is throttled."""
        elapsed = time.monotonic() - self._start
        elapsed_str = format_elapsed(elapsed)

        if self._total and self._total > 0:
            pct = int(100 * current / self._total)
            eta = format_eta(elapsed, current, self._total)
            eta_str = f", ~{eta} remaining" if eta else ""
            line = f"  {self._label}: {current:,}/{self._total:,} ({pct}%) — {elapsed_str}{eta_str}"
        else:
            line = f"  {self._label}: {current:,} — {elapsed_str}"

        if suffix:
            line = f"{line} {suffix}"

        if self._is_tty:
            print(f"\r{line}", end="", file=self._file, flush=True)
        else:
            now = time.monotonic()
            should_report = False
            if self._total and self._total > 0:
                pct = int(100 * current / self._total)
                bucket = pct // self._report_pct
                if bucket > self._last_report_pct:
                    self._last_report_pct = bucket
                    should_report = True
            elif now - self._last_report_time >= self._report_interval:
                should_report = True

            if should_report:
                self._last_report_time = now
                print(line, file=self._file)

    def done(self, message: str = "") -> None:
        """Print final line with total elapsed time."""
        elapsed = format_elapsed(time.monotonic() - self._start)
        line = f"  {self._label}: {message} ({elapsed})" if message else f"  {self._label}: done ({elapsed})"
        if self._is_tty:
            print(f"\r{line}", file=self._file)
        else:
            print(line, file=self._file)
