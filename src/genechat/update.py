"""Check for newer versions of reference databases.

Uses HTTP HEAD requests to compare Last-Modified dates against installed versions.
No downloads — just version checking. Use download.py for actual downloads.
"""

from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

from genechat.download import CLINVAR_URL

# Sources we can check programmatically
CHECKABLE_SOURCES = {
    "clinvar": CLINVAR_URL,
}


def check_clinvar_version() -> str | None:
    """Check the latest ClinVar version via HTTP HEAD. Returns ISO date or None."""
    try:
        req = Request(
            CLINVAR_URL, method="HEAD", headers={"User-Agent": "genechat/0.1"}
        )
        with urlopen(req, timeout=15) as resp:
            last_modified = resp.headers.get("Last-Modified")
            if last_modified:
                dt = parsedate_to_datetime(last_modified)
                return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def _is_newer(latest: str, installed: str) -> bool:
    """Compare version strings safely.

    Only treats both as comparable if they look like ISO dates (YYYY-MM-DD).
    Non-date strings like 'unknown' or 'GRCh38.p14' are always considered stale
    (returns True), since we can't reliably compare them.
    """
    import re

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if date_re.match(latest) and date_re.match(installed):
        return latest > installed
    # If installed version is non-date (e.g. "unknown"), treat as stale
    if not date_re.match(installed):
        return True
    # Latest is non-date but installed is a date — can't compare, assume stale
    return True


def format_status_table(
    installed: dict[str, dict], latest: dict[str, str | None]
) -> str:
    """Format a version comparison table.

    Args:
        installed: {source: {version, updated_at, status}} from patch_metadata
        latest: {source: latest_version_string_or_None}
    """
    lines = []
    lines.append(
        f"{'Source':<12} {'Installed':<20} {'Latest Available':<20} {'Status'}"
    )
    lines.append("-" * 75)

    all_sources = ["snpeff", "clinvar", "gnomad", "dbsnp"]
    for source in all_sources:
        meta = installed.get(source, {})
        inst_ver = meta.get("version", "not installed")
        inst_date = meta.get("updated_at", "")
        if inst_date and inst_ver != "not installed":
            inst_display = f"{inst_ver} ({inst_date})"
        else:
            inst_display = inst_ver

        latest_ver = latest.get(source)
        if latest_ver is None:
            latest_display = "—"
            status = (
                "check unavailable" if inst_ver != "not installed" else "not installed"
            )
        elif inst_ver == "not installed":
            status = "not installed"
            latest_display = latest_ver
        elif latest_ver != inst_ver and _is_newer(latest_ver, inst_ver):
            status = "update available"
            latest_display = latest_ver
        else:
            status = "up to date"
            latest_display = latest_ver

        lines.append(f"{source:<12} {inst_display:<20} {latest_display:<20} {status}")

    return "\n".join(lines)


def check_all_versions() -> dict[str, str | None]:
    """Check latest versions for all sources. Returns {source: version_or_None}."""
    results: dict[str, str | None] = {}

    print("Checking for newer reference versions...")
    results["clinvar"] = check_clinvar_version()
    # gnomAD, SnpEff, dbSNP: no simple programmatic check
    results["gnomad"] = None
    results["snpeff"] = None
    results["dbsnp"] = None

    return results
