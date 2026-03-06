"""Tests for compile_findings tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.compile_findings import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["compile_findings"].fn


class TestCompileFindings:
    def test_variant_report(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs4149056")

        assert "Genomic Findings Summary" in result
        assert "rs4149056" in result
        assert "T/C" in result
        assert "SLCO1B1" in result
        assert "informational only" in result

    def test_gene_report(self, mock_engine, test_db, test_config):
        mock_engine.query_rsids.return_value = {}
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1")

        assert "Gene Summaries" in result
        assert "SLCO1B1" in result

    def test_empty_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_variant_not_found(self, mock_engine, test_db, test_config):
        mock_engine.query_rsids.return_value = {
            "rs9999999": [],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs9999999")

        assert "Not found" in result

    def test_combined_report(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs4149056", genes="CYP2D6")

        assert "Variant Details" in result
        assert "Gene Summaries" in result


class TestCompileFindingsPgxDetail:
    def test_pgx_variant_table_in_gene_summary(self, mock_engine, test_db, test_config):
        """Gene summary for PGx gene should include variant-level genotype table."""
        # Mock the VCF query for PGx variant positions
        mock_engine.query_rsids.return_value = {}
        mock_engine.query_region.return_value = [
            {
                "genotype": {"display": "T/C", "zygosity": "heterozygous"},
                "chrom": "chr12",
                "pos": 21178615,
                "rsid": "rs4149056",
                "ref": "T",
                "alt": "C",
                "annotation": {},
                "clinvar": {},
                "population_freq": {},
            }
        ]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1")

        assert "PGx Variants" in result
        assert "Star Allele" in result
        assert "Your Genotype" in result
        assert "Function Impact" in result

    def test_pgx_variant_shows_genotype(self, mock_engine, test_db, test_config):
        """PGx variant table should show actual genotype from VCF."""
        mock_engine.query_rsids.return_value = {}
        mock_engine.query_region.return_value = [
            {
                "genotype": {"display": "C/T", "zygosity": "heterozygous"},
                "chrom": "chr22",
                "pos": 42128945,
                "rsid": "rs3892097",
                "ref": "C",
                "alt": "T",
                "annotation": {},
                "clinvar": {},
                "population_freq": {},
            }
        ]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="CYP2D6")

        assert "CYP2D6 PGx Variants" in result
        assert "het" in result

    def test_no_pgx_when_disabled(self, mock_engine, test_db, test_config):
        """include_pgx=False should omit PGx section."""
        mock_engine.query_rsids.return_value = {}
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1", include_pgx=False)

        assert "PGx Variants" not in result
        assert "PGx drugs" not in result
