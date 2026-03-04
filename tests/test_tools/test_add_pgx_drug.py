"""Tests for add_pgx_drug tool."""

from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from genechat.tools.add_pgx_drug import register


def _make_pgx_drugs(tmp_path):
    """Create a minimal pgx_drugs.tsv in tmp_path."""
    content = (
        "drug_name\tdrug_aliases\tgene\tguideline_source\tguideline_url\tclinical_summary\n"
        "simvastatin\tzocor\tSLCO1B1\tCPIC\thttps://cpicpgx.org/test\tSLCO1B1 summary.\n"
    )
    path = tmp_path / "pgx_drugs.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _make_gene_lists(tmp_path):
    """Create a minimal gene_lists.tsv in tmp_path."""
    content = "symbol\tcategory\nSLCO1B1\tpgx\n"
    path = tmp_path / "gene_lists.tsv"
    path.write_text(content, encoding="utf-8")
    return path


def _setup_tool(mock_engine, test_db, test_config, tmp_path):
    """Register the tool with file paths patched to tmp_path."""
    _make_pgx_drugs(tmp_path)
    _make_gene_lists(tmp_path)
    seed_dir = tmp_path
    curated_dir = tmp_path
    mcp = FastMCP("test")
    with (
        patch("genechat.tools.add_pgx_drug.SEED_DIR", seed_dir),
        patch("genechat.tools.add_pgx_drug.CURATED_DIR", curated_dir),
    ):
        register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["add_pgx_drug"].fn


class TestAddPgxDrug:
    def test_successful_add(self, mock_engine, test_db, test_config, tmp_path):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            result = fn(
                drug_name="pantoprazole",
                gene="CYP2C19",
                guideline_source="CPIC",
                drug_aliases="protonix",
                guideline_url="https://cpicpgx.org/guidelines/ppi",
                clinical_summary="CYP2C19 affects metabolism.",
            )

        assert "PGx Drug-Gene Pair Added" in result
        assert "pantoprazole" in result
        assert "CYP2C19" in result
        assert "rebuild_database" in result.lower()

        # Verify file was written
        content = (tmp_path / "pgx_drugs.tsv").read_text(encoding="utf-8")
        assert "pantoprazole" in content
        assert "CYP2C19" in content
        assert "protonix" in content

    def test_gene_added_to_gene_lists(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            fn(
                drug_name="newdrug",
                gene="NEWPGXGENE",
            )

        gene_lists = (tmp_path / "gene_lists.tsv").read_text(encoding="utf-8")
        assert "NEWPGXGENE\tpgx" in gene_lists

    def test_existing_gene_not_duplicated(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            fn(
                drug_name="newdrug",
                gene="SLCO1B1",
            )

        gene_lists = (tmp_path / "gene_lists.tsv").read_text(encoding="utf-8")
        assert gene_lists.count("SLCO1B1") == 1

    def test_duplicate_drug_gene_rejected(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            result = fn(
                drug_name="simvastatin",
                gene="SLCO1B1",
            )

        assert "already exists" in result

    def test_duplicate_case_insensitive(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            result = fn(
                drug_name="Simvastatin",
                gene="slco1b1",
            )

        assert "already exists" in result

    def test_empty_drug_name_rejected(
        self, mock_engine, test_db, test_config, tmp_path
    ):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            result = fn(
                drug_name="",
                gene="CYP2C19",
            )
        assert "cannot be empty" in result

    def test_empty_gene_rejected(self, mock_engine, test_db, test_config, tmp_path):
        fn = _setup_tool(mock_engine, test_db, test_config, tmp_path)
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            result = fn(
                drug_name="newdrug",
                gene="",
            )
        assert "cannot be empty" in result

    def test_defaults_applied(self, mock_engine, test_db, test_config, tmp_path):
        _make_pgx_drugs(tmp_path)
        _make_gene_lists(tmp_path)
        mcp = FastMCP("test")
        with (
            patch("genechat.tools.add_pgx_drug.SEED_DIR", tmp_path),
            patch("genechat.tools.add_pgx_drug.CURATED_DIR", tmp_path),
        ):
            register(mcp, mock_engine, test_db, test_config)
            fn = mcp._tool_manager._tools["add_pgx_drug"].fn
            result = fn(
                drug_name="newdrug",
                gene="CYP2C19",
            )

        assert "CPIC" in result  # default guideline_source
        content = (tmp_path / "pgx_drugs.tsv").read_text(encoding="utf-8")
        last_line = content.strip().split("\n")[-1]
        assert "newdrug" in last_line
        assert "CPIC" in last_line
