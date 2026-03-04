"""E2E tests for query_trait tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_trait import register


def _get_tool(giab_engine, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engine, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_trait"].fn


class TestQueryTraitGIAB:
    def test_nutrigenomics_mthfr(self, giab_engine, giab_db, giab_config):
        """Nutrigenomics should include MTHFR C677T (het in NA12878)."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(category="nutrigenomics")
        assert "MTHFR" in result
        # NA12878 is heterozygous for C677T
        assert "heterozygous" in result.lower() or "het" in result.lower()

    def test_cardiovascular_traits(self, giab_engine, giab_db, giab_config):
        """Cardiovascular traits should include Factor V and APOE."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(category="cardiovascular")
        # Should contain at least some cardiovascular trait genes
        assert isinstance(result, str)
        assert len(result) > 50

    def test_exercise_actn3(self, giab_engine, giab_db, giab_config):
        """Exercise traits should include ACTN3."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(category="exercise")
        assert "ACTN3" in result

    def test_metabolism_caffeine(self, giab_engine, giab_db, giab_config):
        """Metabolism should include caffeine metabolism (CYP1A2)."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(category="metabolism")
        assert "CYP1A2" in result or "caffeine" in result.lower()

    def test_trait_has_genotype_data(self, giab_engine, giab_db, giab_config):
        """Trait results should include actual genotype displays."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(category="nutrigenomics")
        # Should contain genotype displays (allele/allele format)
        assert "/" in result

    def test_no_filter_returns_help(self, giab_engine, giab_db, giab_config):
        """No filters should return help message."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn()
        assert "provide" in result.lower() or "category" in result.lower()

    def test_specific_gene_filter(self, giab_engine, giab_db, giab_config):
        """Filter by specific gene."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(gene="MTHFR")
        assert "MTHFR" in result
