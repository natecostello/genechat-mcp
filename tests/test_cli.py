"""Tests for the genechat CLI (init subcommand)."""

import pytest

from genechat.cli import main


def test_init_missing_vcf(tmp_path, capsys):
    """init fails when VCF does not exist."""
    with pytest.raises(SystemExit) as exc_info:
        main(["init", str(tmp_path / "nonexistent.vcf.gz")])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_init_missing_index(tmp_path, capsys):
    """init fails when VCF exists but index is missing."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    with pytest.raises(SystemExit) as exc_info:
        main(["init", str(vcf)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No index file" in captured.err


def test_init_writes_config(tmp_path, capsys, monkeypatch):
    """init writes config.toml with correct content and permissions."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    tbi = tmp_path / "test.vcf.gz.tbi"
    tbi.write_bytes(b"fake")

    config_dir = tmp_path / "config"
    monkeypatch.setattr("genechat.cli.user_config_dir", lambda _app: str(config_dir))

    # Mock pysam.VariantFile so we don't need a real VCF
    import unittest.mock

    mock_vf = unittest.mock.MagicMock()
    mock_vf.__enter__ = lambda s: s
    mock_vf.__exit__ = lambda s, *a: None
    monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

    # Stub out the DB existence check to avoid importing build_db
    monkeypatch.setattr(
        "genechat.cli.resources.files",
        lambda _pkg: tmp_path / "pkg",
    )
    # Create a fake lookup_tables.db so init skips build_db
    pkg_data = tmp_path / "pkg" / "data"
    pkg_data.mkdir(parents=True)
    (pkg_data / "lookup_tables.db").write_bytes(b"fake")

    main(["init", str(vcf)])

    captured = capsys.readouterr()
    config_path = config_dir / "config.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert str(vcf.resolve()) in content

    # Check permissions (owner read/write only)
    mode = config_path.stat().st_mode & 0o777
    assert mode == 0o600

    # Check MCP config JSON is printed
    assert "mcpServers" in captured.out
    assert "genechat" in captured.out


def test_init_accepts_csi_index(tmp_path, capsys, monkeypatch):
    """init accepts .csi index as alternative to .tbi."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    csi = tmp_path / "test.vcf.gz.csi"
    csi.write_bytes(b"fake")

    config_dir = tmp_path / "config"
    monkeypatch.setattr("genechat.cli.user_config_dir", lambda _app: str(config_dir))
    monkeypatch.setattr("genechat.cli.resources.files", lambda _pkg: tmp_path / "pkg")
    pkg_data = tmp_path / "pkg" / "data"
    pkg_data.mkdir(parents=True)
    (pkg_data / "lookup_tables.db").write_bytes(b"fake")

    # Mock pysam.VariantFile
    import unittest.mock

    mock_vf = unittest.mock.MagicMock()
    mock_vf.__enter__ = lambda s: s
    mock_vf.__exit__ = lambda s, *a: None
    monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

    main(["init", str(vcf)])

    config_path = config_dir / "config.toml"
    assert config_path.exists()


def test_init_invalid_vcf(tmp_path, capsys, monkeypatch):
    """init fails when VCF exists with index but cannot be opened by pysam."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"not a real vcf")
    tbi = tmp_path / "test.vcf.gz.tbi"
    tbi.write_bytes(b"fake")

    # pysam.VariantFile will raise on invalid data
    monkeypatch.setattr(
        "pysam.VariantFile",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("not a valid VCF")),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["init", str(vcf)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Cannot read VCF" in captured.err


def test_init_auto_builds_lookup_db(tmp_path, capsys, monkeypatch):
    """init auto-builds lookup_tables.db when missing in a source checkout."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    tbi = tmp_path / "test.vcf.gz.tbi"
    tbi.write_bytes(b"fake")

    config_dir = tmp_path / "config"
    monkeypatch.setattr("genechat.cli.user_config_dir", lambda _app: str(config_dir))

    import unittest.mock

    mock_vf = unittest.mock.MagicMock()
    mock_vf.__enter__ = lambda s: s
    mock_vf.__exit__ = lambda s, *a: None
    monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

    # Set up a fake source checkout with build_lookup_db.py and seed dir
    fake_root = tmp_path / "repo"
    seed = fake_root / "data" / "seed"
    seed.mkdir(parents=True)
    # Create all required seed TSVs
    for tsv in ["genes_grch38.tsv", "pgx_drugs.tsv", "pgx_variants.tsv", "prs_weights.tsv"]:
        (seed / tsv).write_text("col1\tcol2\n")
    build_script = fake_root / "scripts" / "build_lookup_db.py"
    build_script.parent.mkdir(parents=True)
    build_script.write_text(
        "def build_db(seed_dir=None, db_path=None):\n"
        "    db_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    db_path.write_bytes(b'built')\n"
    )

    monkeypatch.setattr("genechat.cli._find_project_root", lambda: fake_root)

    # Point resources.files to a dir without lookup_tables.db
    pkg_dir = tmp_path / "pkg"
    (pkg_dir / "data").mkdir(parents=True)
    monkeypatch.setattr("genechat.cli.resources.files", lambda _pkg: pkg_dir)

    main(["init", str(vcf)])

    captured = capsys.readouterr()
    assert "Building lookup_tables.db" in captured.out
    # DB was created by the fake build_db
    assert (pkg_dir / "data" / "lookup_tables.db").exists()
    # Config should have been written successfully
    assert (config_dir / "config.toml").exists()


def test_init_missing_lookup_db_no_source_checkout(tmp_path, capsys, monkeypatch):
    """init exits with error when lookup_tables.db is missing and not in source checkout."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    tbi = tmp_path / "test.vcf.gz.tbi"
    tbi.write_bytes(b"fake")

    config_dir = tmp_path / "config"
    monkeypatch.setattr("genechat.cli.user_config_dir", lambda _app: str(config_dir))

    import unittest.mock

    mock_vf = unittest.mock.MagicMock()
    mock_vf.__enter__ = lambda s: s
    mock_vf.__exit__ = lambda s, *a: None
    monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

    # Simulate installed package mode: no source checkout
    monkeypatch.setattr("genechat.cli._find_project_root", lambda: None)

    # Point resources.files to a dir without lookup_tables.db
    monkeypatch.setattr("genechat.cli.resources.files", lambda _pkg: tmp_path / "pkg")
    (tmp_path / "pkg" / "data").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        main(["init", str(vcf)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "lookup_tables.db not found" in captured.err
    assert "Reinstall genechat" in captured.err
    # Config should NOT have been written
    assert not (config_dir / "config.toml").exists()


def test_no_subcommand_invokes_serve(monkeypatch):
    """Running genechat with no args calls run_server."""
    called = []
    monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
    main([])
    assert called == [True]


def test_serve_subcommand_invokes_serve(monkeypatch):
    """Running genechat serve calls run_server."""
    called = []
    monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
    main(["serve"])
    assert called == [True]
