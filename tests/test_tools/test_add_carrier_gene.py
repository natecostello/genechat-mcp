"""Tests for add_carrier_gene tool."""

from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from genechat.tools.add_carrier_gene import register


def _make_carrier_metadata(tmp_path):
    """Create a minimal carrier_metadata.tsv in tmp_path."""
    content = (
        "gene\tcondition_name\tinheritance\tcarrier_frequency\tacmg_recommended\n"
        "CFTR\tCystic fibrosis\tAR\t1 in 25 (European)\t1\n"
    )
    path = tmp_path / "carrier_metadata.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _make_gene_lists(tmp_path):
    """Create a minimal gene_lists.tsv in tmp_path."""
    content = "symbol\tcategory\nCFTR\tcarrier\n"
    path = tmp_path / "gene_lists.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _setup_tool(mock_engine, test_db, test_config, tmp_path):
    """Register the tool with file paths patched to tmp_path."""
    _make_carrier_metadata(tmp_path)
    _make_gene_lists(tmp_path)
    mcp = FastMCP("test")
    with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
        register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["add_carrier_gene"].fn


class TestAddCarrierGene:
    def test_successful_add(self, mock_engine, test_db, test_config, tmp_path):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            result = fn(
                gene="SLC22A5",
                condition="Systemic primary carnitine deficiency",
                inheritance="AR",
                carrier_frequency="1 in 100",
                acmg_recommended=False,
            )

        assert "Carrier Gene Added" in result
        assert "SLC22A5" in result
        assert "carnitine" in result.lower()
        assert "rebuild_database" in result.lower()

        # Verify file was written
        content = (tmp_path / "carrier_metadata.tsv").read_text(encoding="utf-8")
        assert "SLC22A5" in content
        assert "carnitine" in content.lower()

    def test_gene_added_to_gene_lists(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            fn(
                gene="NEWGENE",
                condition="New condition",
                inheritance="AR",
            )

        gene_lists = (tmp_path / "gene_lists.tsv").read_text(encoding="utf-8")
        assert "NEWGENE\tcarrier" in gene_lists

    def test_duplicate_gene_rejected(self, mock_engine, test_db, test_config, tmp_path):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            # Try to add CFTR which already exists
            result = fn(
                gene="CFTR",
                condition="Another CF entry",
                inheritance="AR",
            )

        assert "already exists" in result

    def test_invalid_inheritance(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            result = fn(
                gene="NEWGENE",
                condition="Some condition",
                inheritance="XR",
            )
        assert "Invalid inheritance" in result

    def test_empty_gene_rejected(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            result = fn(
                gene="",
                condition="Some condition",
                inheritance="AR",
            )
        assert "cannot be empty" in result

    def test_empty_condition_rejected(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            result = fn(
                gene="NEWGENE",
                condition="",
                inheritance="AR",
            )
        assert "cannot be empty" in result

    def test_acmg_recommended_true(self, mock_engine, test_db, test_config, tmp_path):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            result = fn(
                gene="NEWGENE",
                condition="Important condition",
                inheritance="AD",
                acmg_recommended=True,
            )

        assert "ACMG recommended: Yes" in result
        content = (tmp_path / "carrier_metadata.tsv").read_text(encoding="utf-8")
        # Last row should have 1 for acmg_recommended
        last_line = content.strip().split("\n")[-1]
        assert last_line.endswith("\t1")

    def test_default_carrier_frequency(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            fn(
                gene="NEWGENE",
                condition="Some condition",
                inheritance="AR",
            )

        content = (tmp_path / "carrier_metadata.tsv").read_text(encoding="utf-8")
        assert ".\t0" in content  # default frequency "." and acmg_recommended 0

    def test_x_linked_inheritance(self, mock_engine, test_db, test_config, tmp_path):
        _make_carrier_metadata(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with patch("genechat.tools.add_carrier_gene.CURATED_DIR", tmp_path):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_carrier_gene"].fn
            result = fn(
                gene="NEWXGENE",
                condition="X-linked condition",
                inheritance="X-linked",
            )

        assert "Carrier Gene Added" in result
        assert "X-linked" in result
