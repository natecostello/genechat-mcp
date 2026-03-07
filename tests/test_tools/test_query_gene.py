"""Tests for query_gene tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_gene import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_gene"].fn


def _make_variant(
    rsid=None,
    chrom="chr12",
    pos=21178700,
    ref="A",
    alt="G",
    gene="SLCO1B1",
    effect="missense_variant",
    impact="MODERATE",
    clinvar_sig=None,
    clinvar_cond=None,
    af=None,
    af_popmax=None,
    zygosity="heterozygous",
):
    """Build a variant dict for testing."""
    display = f"{ref}/{alt}" if zygosity == "heterozygous" else f"{alt}/{alt}"
    if zygosity == "homozygous_ref":
        display = f"{ref}/{ref}"
    v = {
        "chrom": chrom,
        "pos": pos,
        "rsid": rsid,
        "ref": ref,
        "alt": alt,
        "genotype": {"display": display, "zygosity": zygosity},
        "annotation": {
            "gene": gene,
            "effect": effect,
            "impact": impact,
        }
        if impact
        else {},
        "clinvar": {},
        "population_freq": {},
    }
    if clinvar_sig:
        v["clinvar"] = {"significance": clinvar_sig}
        if clinvar_cond:
            v["clinvar"]["condition"] = clinvar_cond
    if af is not None:
        v["population_freq"]["global"] = af
    if af_popmax is not None:
        v["population_freq"]["popmax"] = af_popmax
    return v


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
        result = fn(gene="SLCO1B1", smart_filter=False)

        assert "rs4149056" in result  # annotated
        assert "rs99999" in result  # unannotated
        assert "missense_variant" in result  # from annotated variant


class TestSmartFilter:
    def test_common_benign_suppressed(self, mock_engine, test_db, test_config):
        """Common variant (AF>0.05) with no ClinVar should be suppressed."""
        common = _make_variant(
            rsid="rs100001", af=0.15, af_popmax=0.20, impact="MODERATE"
        )
        rare = _make_variant(rsid="rs100002", af=0.001, impact="MODERATE", pos=21178800)
        mock_engine.query_region.return_value = [common, rare]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100001" not in result
        assert "rs100002" in result
        assert "suppressed by smart filter" in result

    def test_rare_variant_kept(self, mock_engine, test_db, test_config):
        """Rare variant (AF<0.05) should not be suppressed."""
        rare = _make_variant(rsid="rs100003", af=0.01, impact="MODERATE")
        mock_engine.query_region.return_value = [rare]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100003" in result

    def test_high_impact_never_suppressed(self, mock_engine, test_db, test_config):
        """HIGH impact variants should never be suppressed regardless of AF."""
        high_common = _make_variant(
            rsid="rs100004", af=0.15, impact="HIGH", effect="stop_gained"
        )
        mock_engine.query_region.return_value = [high_common]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100004" in result

    def test_clinvar_pathogenic_never_suppressed(
        self, mock_engine, test_db, test_config
    ):
        """ClinVar Pathogenic variants should never be suppressed."""
        pathogenic = _make_variant(
            rsid="rs100005",
            af=0.10,
            impact="MODERATE",
            clinvar_sig="Pathogenic",
            clinvar_cond="Some disease",
        )
        mock_engine.query_region.return_value = [pathogenic]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100005" in result

    def test_clinvar_risk_factor_never_suppressed(
        self, mock_engine, test_db, test_config
    ):
        """ClinVar risk_factor variants should never be suppressed."""
        risk = _make_variant(
            rsid="rs100006",
            af=0.30,
            impact="MODERATE",
            clinvar_sig="risk factor",
        )
        mock_engine.query_region.return_value = [risk]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100006" in result

    def test_clinvar_drug_response_never_suppressed(
        self, mock_engine, test_db, test_config
    ):
        """ClinVar drug_response variants should never be suppressed."""
        drug_resp = _make_variant(
            rsid="rs100007",
            af=0.20,
            impact="MODERATE",
            clinvar_sig="drug response",
        )
        mock_engine.query_region.return_value = [drug_resp]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100007" in result

    def test_no_af_clinvar_only_fallback(self, mock_engine, test_db, test_config):
        """Without AF data, suppress by ClinVar-only: no ClinVar → suppress."""
        no_af_no_clin = _make_variant(
            rsid="rs100008", impact="MODERATE"
        )  # no AF, no ClinVar
        no_af_with_clin = _make_variant(
            rsid="rs100009",
            impact="MODERATE",
            clinvar_sig="Pathogenic",
            pos=21178800,
        )
        mock_engine.query_region.return_value = [no_af_no_clin, no_af_with_clin]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100008" not in result
        assert "rs100009" in result
        assert "filtered by ClinVar only" in result

    def test_smart_filter_false_shows_all(self, mock_engine, test_db, test_config):
        """smart_filter=false should show all variants without suppression."""
        common = _make_variant(rsid="rs100010", af=0.15, impact="MODERATE")
        mock_engine.query_region.return_value = [common]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=False)

        assert "rs100010" in result
        assert "suppressed" not in result

    def test_known_pgx_rsid_never_suppressed(self, mock_engine, test_db, test_config):
        """Known PGx rsIDs should never be suppressed even if common."""
        # rs4149056 is a known PGx variant for SLCO1B1
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        # Override AF to be high — should still not be suppressed
        v = dict(SAMPLE_VARIANT_SLCO1B1)
        v["population_freq"] = {"global": 0.20, "popmax": 0.30}
        mock_engine.query_region.return_value = [v]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs4149056" in result

    def test_clinvar_benign_common_suppressed(self, mock_engine, test_db, test_config):
        """Common variant with ClinVar Benign should be suppressed."""
        benign = _make_variant(
            rsid="rs100011",
            af=0.15,
            impact="MODERATE",
            clinvar_sig="Benign",
        )
        mock_engine.query_region.return_value = [benign]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="SLCO1B1", smart_filter=True)

        assert "rs100011" not in result
        assert "suppressed by smart filter" in result
