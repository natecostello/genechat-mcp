"""Tests for the genechat CLI (init subcommand)."""

from genechat.cli import main


def test_init_missing_vcf(tmp_path, capsys):
    """init fails when VCF does not exist."""
    try:
        main(["init", str(tmp_path / "nonexistent.vcf.gz")])
    except SystemExit as e:
        assert e.code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_init_missing_index(tmp_path, capsys):
    """init fails when VCF exists but index is missing."""
    vcf = tmp_path / "test.vcf.gz"
    vcf.write_bytes(b"fake")
    try:
        main(["init", str(vcf)])
    except SystemExit as e:
        assert e.code == 1
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

    main(["init", str(vcf)])

    config_path = config_dir / "config.toml"
    assert config_path.exists()


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
