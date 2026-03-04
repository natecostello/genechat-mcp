"""Tests for add_trait_variant tool."""

from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from genechat.tools.add_trait_variant import register


def _make_trait_metadata(tmp_path):
    """Create a minimal trait_metadata.tsv in tmp_path."""
    content = (
        "rsid\tgene\ttrait_category\ttrait\tref\talt\t"
        "effect_allele\teffect_description\tevidence_level\tpmid\n"
        "rs9939609\tFTO\tnutrigenomics\tObesity susceptibility\tT\tA\tA\t"
        "Each A allele increases BMI\tstrong\t17434869\n"
    )
    path = tmp_path / "trait_metadata.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _make_gene_lists(tmp_path):
    """Create a minimal gene_lists.tsv in tmp_path."""
    content = "symbol\tcategory\nFTO\ttrait\n"
    path = tmp_path / "gene_lists.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _setup_tool(mock_engine, test_db, test_config, tmp_path):
    """Register the tool with file paths patched to tmp_path."""
    _make_trait_metadata(tmp_path)
    _make_gene_lists(tmp_path)
    mcp = FastMCP("test")
    with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
        register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["add_trait_variant"].fn


class TestAddTraitVariant:
    def test_successful_add(self, mock_engine, test_db, test_config, tmp_path):
        _make_trait_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_trait_variant"].fn
            result = fn(
                rsid="rs7501331",
                gene="BCMO1",
                trait_category="vitamins",
                trait="Beta-carotene conversion",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="T allele reduces beta-carotene conversion",
                evidence_level="moderate",
                pmid="21878437",
            )

        assert "Trait Variant Added" in result
        assert "rs7501331" in result
        assert "BCMO1" in result
        assert "vitamins" in result
        assert "rebuild_database" in result.lower()

        # Verify file was written
        content = (tmp_path / "trait_metadata.tsv").read_text(encoding="utf-8")
        assert "rs7501331" in content
        assert "BCMO1" in content

    def test_gene_added_to_gene_lists(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_trait_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_trait_variant"].fn
            fn(
                rsid="rs7501331",
                gene="BCMO1",
                trait_category="vitamins",
                trait="Beta-carotene conversion",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="T allele reduces conversion",
                evidence_level="moderate",
                pmid="21878437",
            )

        gene_lists = (tmp_path / "gene_lists.tsv").read_text(encoding="utf-8")
        assert "BCMO1\ttrait" in gene_lists

    def test_existing_gene_not_duplicated(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_trait_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_trait_variant"].fn
            fn(
                rsid="rs999999",
                gene="FTO",
                trait_category="nutrigenomics",
                trait="Something new",
                ref="A",
                alt="G",
                effect_allele="G",
                effect_description="Some effect",
                evidence_level="preliminary",
                pmid="12345678",
            )

        gene_lists = (tmp_path / "gene_lists.tsv").read_text(encoding="utf-8")
        assert gene_lists.count("FTO") == 1

    def test_invalid_rsid(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            result = fn(
                rsid="invalid",
                gene="BCMO1",
                trait_category="vitamins",
                trait="Test",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="Test effect",
                evidence_level="moderate",
                pmid="12345",
            )
        assert "Invalid rsID" in result

    def test_invalid_category(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            result = fn(
                rsid="rs123456",
                gene="BCMO1",
                trait_category="invalid_category",
                trait="Test",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="Test",
                evidence_level="moderate",
                pmid="12345",
            )
        assert "Invalid trait_category" in result

    def test_invalid_evidence_level(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            result = fn(
                rsid="rs123456",
                gene="BCMO1",
                trait_category="vitamins",
                trait="Test",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="Test",
                evidence_level="very_strong",
                pmid="12345",
            )
        assert "Invalid evidence_level" in result

    def test_invalid_effect_allele(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            result = fn(
                rsid="rs123456",
                gene="BCMO1",
                trait_category="vitamins",
                trait="Test",
                ref="C",
                alt="T",
                effect_allele="G",
                effect_description="Test",
                evidence_level="moderate",
                pmid="12345",
            )
        assert "effect_allele" in result
        assert "must be either" in result

    def test_duplicate_rsid_rejected(self, mock_engine, test_db, test_config, tmp_path):
        _make_trait_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_trait_variant"].fn
            result = fn(
                rsid="rs9939609",
                gene="FTO",
                trait_category="nutrigenomics",
                trait="Obesity",
                ref="T",
                alt="A",
                effect_allele="A",
                effect_description="Already exists",
                evidence_level="strong",
                pmid="17434869",
            )
        assert "already exists" in result

    def test_empty_gene_rejected(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_trait_variant.CURATED_DIR", tmp_path):
            result = fn(
                rsid="rs123456",
                gene="",
                trait_category="vitamins",
                trait="Test",
                ref="C",
                alt="T",
                effect_allele="T",
                effect_description="Test",
                evidence_level="moderate",
                pmid="12345",
            )
        assert "cannot be empty" in result
