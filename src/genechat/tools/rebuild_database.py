"""Rebuild the GeneChat lookup database from seed data."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_seed_data.py"


def register(mcp, engine, db, config):
    @mcp.tool()
    def rebuild_database() -> str:
        """Rebuild the GeneChat lookup database from curated seed data.

        This runs the full build pipeline:
        1. Fetches gene coordinates from HGNC/Ensembl
        2. Fetches variant coordinates from Ensembl
        3. Fetches PRS variant coordinates from Ensembl
        4. Copies carrier metadata
        5. Rebuilds the SQLite lookup database

        Requires internet access for Ensembl API calls. May take a few minutes.
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
                timeout=600,  # 10 minute timeout
            )
        except subprocess.TimeoutExpired:
            return (
                "## Database Rebuild Timed Out\n\n"
                "The build pipeline exceeded the 10-minute timeout. "
                "This can happen if the Ensembl API is slow or unreachable.\n\n"
                "Try running manually: `uv run python scripts/build_seed_data.py`"
            )
        except OSError as e:
            return f"## Database Rebuild Failed\n\nError launching build script: {e}"

        if result.returncode == 0:
            # Extract summary from output (last few lines usually have row counts)
            output_lines = result.stdout.strip().split("\n")
            # Get the summary section (after "Pipeline complete!")
            summary_lines = []
            in_summary = False
            for line in output_lines:
                if "Pipeline complete" in line:
                    in_summary = True
                if in_summary:
                    summary_lines.append(line)

            summary = (
                "\n".join(summary_lines) if summary_lines else result.stdout[-500:]
            )

            return (
                f"## Database Rebuilt Successfully\n\n"
                f"```\n{summary}\n```\n\n"
                f"**Important:** The LookupDB is cached in memory. "
                f"Restart the MCP server to load the updated database."
            )
        else:
            # Include stderr for diagnosis, truncated if too long
            stderr = result.stderr[:1000] if result.stderr else ""
            stdout_tail = result.stdout[-500:] if result.stdout else ""
            return (
                f"## Database Rebuild Failed\n\n"
                f"Exit code: {result.returncode}\n\n"
                f"```\n{stdout_tail}\n```\n\n"
                + (f"Errors:\n```\n{stderr}\n```\n\n" if stderr else "")
                + "Try running manually: `uv run python scripts/build_seed_data.py`"
            )
