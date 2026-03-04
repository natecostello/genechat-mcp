"""Tests for query_carrier tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_carrier import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_carrier"].fn


class TestQueryCarrier:
    def test_carrier_positive(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_clinvar.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(acmg_only=False)

        assert "Carrier Screening Results" in result
        assert "Carrier Positive" in result
        assert "NOTE:" in result

    def test_no_pathogenic_variants(self, mock_engine, test_db, test_config):
        mock_engine.query_clinvar.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(acmg_only=False)

        assert "No Pathogenic Variants Found" in result
        assert "does not guarantee" in result
        assert "NOTE:" in result

    def test_acmg_only(self, mock_engine, test_db, test_config):
        mock_engine.query_clinvar.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(acmg_only=True)

        assert "ACMG" in result

    def test_condition_filter(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_clinvar.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(condition="cystic fibrosis", acmg_only=False)

        assert "Carrier Screening Results" in result

    def test_unknown_condition(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(condition="fakecondition999", acmg_only=False)

        assert "No carrier genes found" in result

    def test_genes_screened_count(self, mock_engine, test_db, test_config):
        mock_engine.query_clinvar.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(acmg_only=False)

        assert "Genes screened:" in result

    def test_disclaimer_present(self, mock_engine, test_db, test_config):
        mock_engine.query_clinvar.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(acmg_only=False)

        assert "non-carrier status" in result
        assert "genetic counseling" in result
