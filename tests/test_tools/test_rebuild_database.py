"""Tests for rebuild_database tool."""

from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP

from genechat.tools.rebuild_database import register


def _setup_tool(mock_engine, test_db, test_config):
    """Register the tool and return the function."""
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["rebuild_database"].fn


class TestRebuildDatabase:
    def test_successful_rebuild(self, mock_engine, test_db, test_config):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Building GeneChat lookup database...\n"
            "  genes: 19345 rows loaded from genes_grch38.tsv\n"
            "  pgx_drugs: 22 rows loaded from pgx_drugs.tsv\n"
            "  trait_variants: 40 rows loaded from trait_variants.tsv\n"
            "Done."
        )
        mock_result.stderr = ""

        with patch(
            "genechat.tools.rebuild_database.subprocess.run", return_value=mock_result
        ):
            fn = _setup_tool(mock_engine, test_db, test_config)
            result = fn()

        assert "Rebuilt Successfully" in result
        assert "genes" in result
        assert "Restart" in result or "restart" in result

    def test_failed_rebuild(self, mock_engine, test_db, test_config):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Pipeline failed at step 2"
        mock_result.stderr = "ConnectionError: Ensembl API unreachable"

        with patch(
            "genechat.tools.rebuild_database.subprocess.run", return_value=mock_result
        ):
            fn = _setup_tool(mock_engine, test_db, test_config)
            result = fn()

        assert "Failed" in result
        assert "Exit code: 1" in result

    def test_timeout(self, mock_engine, test_db, test_config):
        import subprocess

        with patch(
            "genechat.tools.rebuild_database.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=600),
        ):
            fn = _setup_tool(mock_engine, test_db, test_config)
            result = fn()

        assert "Timed Out" in result
        assert "2-minute" in result

    def test_missing_script(self, mock_engine, test_db, test_config):
        from pathlib import Path

        fake_path = Path("/nonexistent/scripts/build_lookup_db.py")
        with patch("genechat.tools.rebuild_database.BUILD_SCRIPT", fake_path):
            mcp = FastMCP("test")
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["rebuild_database"].fn
            result = fn()

        assert "not found" in result

    def test_os_error(self, mock_engine, test_db, test_config):
        with patch(
            "genechat.tools.rebuild_database.subprocess.run",
            side_effect=OSError("Permission denied"),
        ):
            fn = _setup_tool(mock_engine, test_db, test_config)
            result = fn()

        assert "Failed" in result
        assert "Permission denied" in result

    def test_stderr_included_on_failure(self, mock_engine, test_db, test_config):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Some output"
        mock_result.stderr = "Detailed error message here"

        with patch(
            "genechat.tools.rebuild_database.subprocess.run", return_value=mock_result
        ):
            fn = _setup_tool(mock_engine, test_db, test_config)
            result = fn()

        assert "Detailed error message" in result
