"""E2E tests for query_pgx tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_pgx import register


def _get_tool(giab_engines, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engines, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_pgx"].fn


class TestQueryPgxGIAB:
    def test_simvastatin_slco1b1(self, giab_engines, giab_db, giab_config):
        """Simvastatin query should show SLCO1B1 with ref genotype."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(drug="simvastatin")
        assert "SLCO1B1" in result
        assert "simvastatin" in result.lower() or "Simvastatin" in result

    def test_warfarin_vkorc1(self, giab_engines, giab_db, giab_config):
        """Warfarin query should show VKORC1 and CYP2C9."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(drug="warfarin")
        assert "VKORC1" in result or "CYP2C9" in result
        assert "warfarin" in result.lower() or "Warfarin" in result

    def test_codeine_cyp2d6(self, giab_engines, giab_db, giab_config):
        """Codeine query should show CYP2D6 variants."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(drug="codeine")
        assert "CYP2D6" in result

    def test_gene_lookup(self, giab_engines, giab_db, giab_config):
        """Query by gene should return drug entries."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(gene="CYP2D6")
        assert "CYP2D6" in result
        # Should mention at least one drug
        assert any(
            drug in result.lower()
            for drug in [
                "codeine",
                "tramadol",
                "tamoxifen",
                "ondansetron",
                "metoprolol",
            ]
        )

    def test_unknown_drug(self, giab_engines, giab_db, giab_config):
        """Unknown drug should return helpful message."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(drug="fakedrugxyz")
        assert (
            "no pharmacogenomic data" in result.lower() or "not found" in result.lower()
        )

    def test_pgx_output_has_genotypes(self, giab_engines, giab_db, giab_config):
        """PGx output should include actual genotype data."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(drug="simvastatin")
        # Should contain genotype display (e.g., "ref", "het", or allele display)
        assert "ref" in result.lower() or "/" in result
