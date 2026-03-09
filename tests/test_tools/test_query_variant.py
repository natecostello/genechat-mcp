"""Tests for query_variant tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_variant import register


def _setup_tool(mock_engines, test_db, test_config):
    """Register the tool and return the FastMCP app."""
    mcp = FastMCP("test")
    register(mcp, mock_engines, test_db, test_config)
    # Get the registered tool function
    tools = mcp._tool_manager._tools
    return tools["query_variant"].fn


class TestQueryVariant:
    def test_rsid_found(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs4149056")

        assert "rs4149056" in result
        assert "T/C" in result
        assert "heterozygous" in result
        assert "SLCO1B1" in result
        assert "missense_variant" in result
        assert "NOTE:" in result  # disclaimer

    def test_rsid_not_found(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_rsid.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs9999999")

        assert "No variant found" in result

    def test_no_input(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_position_lookup(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_region.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(position="chr12:21178615")

        assert "rs4149056" in result


class TestQueryVariantClinvar:
    def test_clinvar_shown(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs113993960")

        assert "Pathogenic" in result
        assert "Cystic fibrosis" in result
