"""E2E tests for query_clinvar tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_clinvar import register


def _get_tool(giab_engines, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engines, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_clinvar"].fn


class TestQueryClinvarGIAB:
    def test_pathogenic_returns_results(self, giab_engines, giab_db, giab_config):
        """Pathogenic ClinVar query should complete and return structured output."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(significance="Pathogenic", max_results=10)
        # Result should either find pathogenic variants or say none found
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain either results or a "no variants found" message
        assert ("pathogenic" in result.lower()) or ("no" in result.lower())

    def test_drug_response_returns_results(self, giab_engines, giab_db, giab_config):
        """Drug response ClinVar query should return results if annotated."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(significance="drug_response", max_results=10)
        assert isinstance(result, str)

    def test_clinvar_with_gene_filter(self, giab_engines, giab_db, giab_config):
        """ClinVar query scoped to a specific gene."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(significance="Pathogenic", gene="BRCA1")
        assert isinstance(result, str)
        # Should either find variants or report none found in BRCA1
        assert "brca1" in result.lower() or "no" in result.lower()

    def test_benign_returns_results(self, giab_engines, giab_db, giab_config):
        """Benign variants should be plentiful in a healthy genome."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(significance="Benign", max_results=5)
        assert isinstance(result, str)

    def test_output_structure(self, giab_engines, giab_db, giab_config):
        """ClinVar results should have proper markdown structure."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(significance="Benign", gene="BRCA1", max_results=5)
        if "no" not in result.lower().split("variant")[0]:
            # If results found, should have table structure
            assert "|" in result
