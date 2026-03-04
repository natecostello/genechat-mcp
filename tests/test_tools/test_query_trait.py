"""Tests for query_trait tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_trait import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_trait"].fn


class TestQueryTrait:
    def test_no_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_category_nutrigenomics(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="nutrigenomics")

        assert "Nutrigenomics" in result
        assert "NOTE:" in result

    def test_category_exercise(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="exercise")

        assert "Exercise" in result
        assert "ACTN3" in result or "COL1A1" in result or "exercise" in result.lower()

    def test_category_sleep(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="sleep")

        assert "Sleep" in result

    def test_category_skin(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="skin")

        assert "Skin" in result

    def test_category_vitamins(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="vitamins")

        assert "Vitamins" in result

    def test_unknown_category(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="nonexistent_category")
        assert "No trait variants found" in result

    def test_gene_filter(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="MTHFR")

        assert "MTHFR" in result

    def test_specific_trait(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(trait="Caffeine metabolism")

        assert "Caffeine" in result or "CYP1A2" in result

    def test_with_variant_found(self, mock_engine, test_db, test_config):
        """When VCF returns a variant, genotype should appear in output."""
        from tests.conftest import SAMPLE_VARIANT_MTHFR

        mock_engine.query_region.return_value = [SAMPLE_VARIANT_MTHFR]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="MTHFR")

        assert "G/A" in result
        assert "heterozygous" in result

    def test_disclaimer_present(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(category="metabolism")
        assert "NOTE:" in result
        assert "not a medical diagnosis" in result
