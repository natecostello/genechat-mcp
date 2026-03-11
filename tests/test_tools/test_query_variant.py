"""Tests for query_variant tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_variant import register


def _setup_tool(mock_engines, test_db, test_config):
    """Register the tool and return the FastMCP app."""
    mcp = FastMCP("test")
    register(mcp, mock_engines, test_db, test_config)
    # Get the registered tool function
    tools = mcp._tool_manager._tools
    return tools["query_variant"].fn


class TestQueryVariant:
    def test_rsid_found(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs4149056")

        assert "rs4149056" in result
        assert "T/C" in result
        assert "heterozygous" in result
        assert "SLCO1B1" in result
        assert "missense_variant" in result
        assert "NOTE:" in result  # disclaimer

    def test_rsid_not_found(self, mock_engine, mock_engines, test_db, test_config):
        mock_engine.query_rsid.return_value = []
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs9999999")

        assert "No variant found" in result

    def test_no_input(self, mock_engine, mock_engines, test_db, test_config):
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_position_lookup(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_region.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(position="chr12:21178615")

        assert "rs4149056" in result


class TestQueryVariantGenome2:
    """Tests for genome2 paired query feature."""

    def test_genome2_happy_path(
        self, mock_engine, mock_engine2, mock_engines_multi, test_db, test_config_multi
    ):
        from tests.conftest import SAMPLE_VARIANT_CFTR, SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        mock_engine2.query_rsid.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn(rsid="rs4149056", genome="default", genome2="partner")

        # Both genomes' results should appear
        assert "rs4149056" in result
        assert "default" in result
        assert "partner" in result
        # Genome1 variant details
        assert "T/C" in result
        assert "SLCO1B1" in result
        # Genome2 variant details
        assert "CFTR" in result
        assert "NOTE:" in result  # disclaimer

    def test_genome2_not_found_in_second(
        self, mock_engine, mock_engine2, mock_engines_multi, test_db, test_config_multi
    ):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        mock_engine2.query_rsid.return_value = []
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn(rsid="rs4149056", genome="default", genome2="partner")

        assert "rs4149056" in result
        assert "SLCO1B1" in result
        assert "partner" in result
        assert "homozygous reference" in result or "not covered" in result

    def test_genome2_unknown_label(
        self, mock_engine, mock_engines_multi, test_db, test_config_multi
    ):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn(rsid="rs4149056", genome="default", genome2="nonexistent")

        assert "Unknown genome" in result
        assert "nonexistent" in result
        assert "SLCO1B1" in result  # Genome1 still shows

    def test_genome2_genome1_empty_genome2_has_results(
        self, mock_engine, mock_engine2, mock_engines_multi, test_db, test_config_multi
    ):
        """When genome1 has no variant but genome2 does, both results should appear."""
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_rsid.return_value = []
        mock_engine2.query_rsid.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn(rsid="rs113993960", genome="default", genome2="partner")

        # Genome1 should show "not found" message (not early-return)
        assert "not covered" in result or "homozygous reference" in result
        # Genome2 should still show its results
        assert "CFTR" in result
        assert "partner" in result
        assert "NOTE:" in result  # disclaimer

    def test_genome2_engine_error(
        self, mock_engine, mock_engine2, mock_engines_multi, test_db, test_config_multi
    ):
        from genechat.vcf_engine import VCFEngineError
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_SLCO1B1]
        mock_engine2.query_rsid.side_effect = VCFEngineError("VCF read error")
        fn = _setup_tool(mock_engines_multi, test_db, test_config_multi)
        result = fn(rsid="rs4149056", genome="default", genome2="partner")

        assert "SLCO1B1" in result  # Genome1 still shows
        assert "error" in result.lower()
        assert "partner" in result


class TestQueryVariantClinvar:
    def test_clinvar_shown(self, mock_engine, mock_engines, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_rsid.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engines, test_db, test_config)
        result = fn(rsid="rs113993960")

        assert "Pathogenic" in result
        assert "Cystic fibrosis" in result
