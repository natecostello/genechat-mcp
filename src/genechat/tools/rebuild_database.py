"""Rebuild the GeneChat lookup database from seed data."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_lookup_db.py"


def register(mcp, engine, db, config):
    @mcp.tool()
    def rebuild_database() -> str:
        """Rebuild the GeneChat SQLite lookup database from existing seed TSVs.

        This rebuilds the SQLite database from the TSV files already in data/seed/.
        It does NOT fetch new data from APIs (no network calls).

        For a full rebuild that fetches from CPIC, PGS Catalog, and HGNC, run
        manually: `uv run python scripts/build_seed_data.py`

        After completion, the MCP server should be restarted to pick up the new data.
        """
        if not BUILD_SCRIPT.exists():
            return f"Build script not found at {BUILD_SCRIPT}"

        try:
            result = subprocess.run(
                [sys.executable, str(BUILD_SCRIPT)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout (local only, should be fast)
            )
        except subprocess.TimeoutExpired:
            return (
                "## Database Rebuild Timed Out\n\n"
                "The build exceeded the 2-minute timeout.\n\n"
                "Try running manually: `uv run python scripts/build_lookup_db.py`"
            )
        except OSError as e:
            return f"## Database Rebuild Failed\n\nError launching build script: {e}"

        if result.returncode == 0:
            output = result.stdout.strip()
            return (
                f"## Database Rebuilt Successfully\n\n"
                f"```\n{output}\n```\n\n"
                f"**Important:** The LookupDB is cached in memory. "
                f"Restart the MCP server to load the updated database."
            )
        else:
            stderr = result.stderr[:1000] if result.stderr else ""
            stdout_tail = result.stdout[-500:] if result.stdout else ""
            return (
                f"## Database Rebuild Failed\n\n"
                f"Exit code: {result.returncode}\n\n"
                f"```\n{stdout_tail}\n```\n\n"
                + (f"Errors:\n```\n{stderr}\n```\n\n" if stderr else "")
                + "Try running manually: `uv run python scripts/build_lookup_db.py`"
            )
