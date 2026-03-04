"""Tests for query_gene tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_gene import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_gene"].fn


class TestQueryGene:
    def test_gene_with_variants(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_region.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1")

        assert "SLCO1B1" in result
        assert "rs4149056" in result

    def test_unknown_gene(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="FAKEGENE123")
        assert "not found" in result

    def test_no_variants(self, mock_engine, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="BRCA1")
        assert "No" in result
        assert "variants found" in result.lower() or "impact" in result.lower()

    def test_mixed_annotated_and_unannotated(self, mock_engine, test_db, test_config):
        """Both annotated and unannotated variants appear in results."""
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        unannotated = {
            "chrom": "chr12",
            "pos": 21178700,
            "rsid": "rs99999",
            "ref": "A",
            "alt": "G",
            "genotype": {"display": "A/G", "zygosity": "heterozygous"},
            "annotation": {},
            "clinvar": {},
            "population_freq": {},
        }
        mock_engine.query_region.return_value = [SAMPLE_VARIANT_SLCO1B1, unannotated]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1")

        assert "rs4149056" in result  # annotated
        assert "rs99999" in result  # unannotated
        assert "missense_variant" in result  # from annotated variant
