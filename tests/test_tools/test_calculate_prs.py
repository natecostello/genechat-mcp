"""Tests for calculate_prs tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.calculate_prs import register


def _setup_tool(mock_engines, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engines, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["calculate_prs"].fn


class TestCalculatePrs:
    def test_no_input(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_unknown_trait(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="nonexistent disease")
        assert "No PRS data found" in result

    def test_available_traits_listed(
        self, mock_engine, mock_engines, test_db, test_config
    ):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="nonexistent disease")
        assert "Currently available" in result

    def test_cad_prs_by_trait(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="coronary artery disease")

        assert "Polygenic Risk Score" in result
        assert "coronary" in result.lower() or "Coronary" in result
        assert "Raw score" in result
        assert "Variants scored" in result

    def test_bmi_prs_by_trait(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="body mass index")

        assert "Polygenic Risk Score" in result
        assert "bmi" in result.lower() or "body mass" in result.lower()

    def test_prs_by_id(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(prs_id="PGS000010")

        assert "PGS000010" in result
        assert "Polygenic Risk Score" in result

    def test_caveats_included(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="coronary artery disease")

        assert "Caveats" in result
        assert "ancestry" in result.lower()
        assert "one factor among many" in result

    def test_disclaimer_present(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_region.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="coronary artery disease")

        assert "NOTE:" in result
        assert "not a medical diagnosis" in result

    def test_with_variant_found(self, mock_engine, mock_engines, test_db, test_config):
        """When VCF returns a variant with matching effect allele, score should be non-zero."""
        sample_variant = {
            "chrom": "chr9",
            "pos": 22125503,
            "rsid": "rs1333049",
            "ref": "C",
            "alt": "G",
            "genotype": {"display": "G/G", "zygosity": "homozygous_alt"},
            "annotation": {},
            "clinvar": {},
            "population_freq": {"global": 0.47, "popmax": 0.52},
        }
        mock_engine.query_region.return_value = [sample_variant]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(trait="coronary artery disease")

        assert "Polygenic Risk Score" in result
