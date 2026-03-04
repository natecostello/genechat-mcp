"""Tests for genome_summary tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.genome_summary import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["genome_summary"].fn


class TestGenomeSummary:
    def test_basic_summary(self, mock_engine, test_db, test_config):
        mock_engine.stats.return_value = {
            "total_variants": 5000,
            "SNPs": 4000,
            "indels": 1000,
        }
        mock_engine.query_clinvar.return_value = []
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "Genome Summary" in result
        assert "GRCh38" in result

    def test_variant_counts(self, mock_engine, test_db, test_config):
        mock_engine.stats.return_value = {
            "total_variants": 5000,
            "SNPs": 4000,
            "indels": 1000,
        }
        mock_engine.query_clinvar.return_value = []
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "Variant Counts" in result
        assert "5,000" in result

    def test_clinvar_pathogenic(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.stats.return_value = {"total_variants": 100}
        mock_engine.query_clinvar.return_value = [SAMPLE_VARIANT_CFTR]
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "Pathogenic" in result
        assert "1" in result
        assert "CFTR" in result

    def test_pgx_section(self, mock_engine, test_db, test_config):
        mock_engine.stats.return_value = {"total_variants": 100}
        mock_engine.query_clinvar.return_value = []
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "Pharmacogenomics Quick Check" in result

    def test_pgx_nonref_found(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.stats.return_value = {"total_variants": 100}
        mock_engine.query_clinvar.return_value = []
        # Return a non-ref variant for PGx queries
        mock_engine.query_region.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "non-reference variant" in result

    def test_tool_suggestions(self, mock_engine, test_db, test_config):
        mock_engine.stats.return_value = {"total_variants": 100}
        mock_engine.query_clinvar.return_value = []
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()

        assert "query_pgx" in result
        assert "query_variant" in result
