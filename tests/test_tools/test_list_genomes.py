"""Tests for list_genomes tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.list_genomes import register


def _setup_tool(mock_engines, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engines, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["list_genomes"].fn


class TestListGenomes:
    def test_single_genome(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn()

        assert "1 genome(s) registered" in result
        assert "default" in result
        assert "automatically" in result  # single-genome hint

    def test_multi_genome(
        self, mock_engine, mock_engine2, mock_engines_multi, test_db, test_config_multi
    ):
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn()

        assert "2 genome(s) registered" in result
        assert "default" in result
        assert "partner" in result
        assert 'genome="<label>"' in result  # multi-genome hint

    def test_no_genomes(self, test_db, test_config):
        fn = _setup_tool({}, test_db, test_config)
        result = fn()

        assert "No genomes registered" in result

    def test_shows_build(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn()

        assert "GRCh38" in result
