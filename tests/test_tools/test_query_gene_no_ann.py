"""Tests for query_gene with unannotated variants (no SnpEff ANN field)."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_gene import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_gene"].fn


# Variant with no annotation at all (e.g. from Python-only GIAB setup)
UNANNOTATED_VARIANT = {
    "chrom": "chr12",
    "pos": 21178615,
    "rsid": "rs4149056",
    "ref": "T",
    "alt": "C",
    "genotype": {"display": "T/C", "zygosity": "heterozygous"},
    "annotation": {},
    "clinvar": {
        "significance": "drug response",
        "condition": "Simvastatin response",
        "review_status": "criteria provided, multiple submitters, no conflicts",
    },
    "population_freq": {},
}

# Variant with empty impact (edge case)
EMPTY_IMPACT_VARIANT = {
    "chrom": "chr1",
    "pos": 11796321,
    "rsid": "rs1801133",
    "ref": "G",
    "alt": "A",
    "genotype": {"display": "G/A", "zygosity": "heterozygous"},
    "annotation": {"gene": "MTHFR", "impact": ""},
    "clinvar": {},
    "population_freq": {},
}


class TestQueryGeneNoAnnotation:
    def test_unannotated_variants_pass_through(self, mock_engine, test_db, test_config):
        """Variants with no annotation should pass through the impact filter."""
        mock_engine.query_region.return_value = [UNANNOTATED_VARIANT]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1")

        assert "rs4149056" in result
        assert "T/C" in result

    def test_unannotated_table_shows_dots(self, mock_engine, test_db, test_config):
        """Table should show '.' for missing effect and impact fields."""
        mock_engine.query_region.return_value = [UNANNOTATED_VARIANT]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1")

        # The table row should contain dots for effect and impact
        lines = result.split("\n")
        # Find data rows (start with "| rs" followed by a digit, not "| rsID")
        data_lines = [
            line
            for line in lines
            if line.startswith("| rs") and not line.startswith("| rsID")
        ]
        assert len(data_lines) == 1
        cells = [c.strip() for c in data_lines[0].split("|")]
        # cells: ['', 'rs4149056', 'chr12:21178615', 'T/C', '.', '.', 'drug response', '']
        assert cells[4] == "."  # effect
        assert cells[5] == "."  # impact

    def test_empty_impact_passes_through(self, mock_engine, test_db, test_config):
        """Variants with empty impact string should pass through the filter."""
        mock_engine.query_region.return_value = [EMPTY_IMPACT_VARIANT]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="MTHFR")

        assert "rs1801133" in result

    def test_annotated_filtered_unannotated_kept(
        self, mock_engine, test_db, test_config
    ):
        """Annotated variants with wrong impact are filtered; unannotated are kept."""
        low_impact_variant = {
            "chrom": "chr12",
            "pos": 21178700,
            "rsid": None,
            "ref": "A",
            "alt": "G",
            "genotype": {"display": "A/G", "zygosity": "heterozygous"},
            "annotation": {
                "gene": "SLCO1B1",
                "effect": "synonymous_variant",
                "impact": "LOW",
            },
            "clinvar": {},
            "population_freq": {},
        }
        mock_engine.query_region.return_value = [
            UNANNOTATED_VARIANT,
            low_impact_variant,
        ]
        fn = _setup_tool(mock_engine, test_db, test_config)
        # Default filter is HIGH,MODERATE — LOW should be excluded, unannotated kept
        result = fn(gene="SLCO1B1")

        assert "rs4149056" in result  # unannotated, kept
        assert "synonymous_variant" not in result  # LOW impact, filtered out
