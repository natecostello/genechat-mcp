"""Tests for the genechat CLI subcommands."""

import importlib.resources as _real_resources
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from genechat.cli import (
    ExitCode,
    _ensure_lookup_db,
    _freshness_indicator,
    _patch_db_path_for,
    _resolve_stale_layers,
    _validate_vcf,
    app,
    main,
)
from genechat.config import AppConfig, GenomeConfig


@pytest.fixture
def cli():
    return CliRunner()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class _FakeStdin:
    """Stub stdin with configurable isatty()."""

    def __init__(self, *, tty: bool):
        self._tty = tty

    def isatty(self):
        return self._tty


class TestRouting:
    def test_no_subcommand_shows_help_when_tty(self, monkeypatch, capsys):
        """No subcommand in interactive terminal shows help, not server."""
        monkeypatch.setattr("sys.stdin", _FakeStdin(tty=True))
        # main() returns normally here: standalone_mode=False makes Click catch
        # typer.Exit(code=0) internally and return 0, which skips sys.exit().
        main([])
        out = capsys.readouterr().out
        assert "genechat init" in out
        assert "Quick start" in out

    def test_no_subcommand_invokes_serve_when_piped(self, cli, monkeypatch):
        """No subcommand with piped stdin starts the server."""
        called = []
        monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
        result = cli.invoke(app, [])
        assert result.exit_code == 0
        assert called == [True]

    def test_serve_subcommand_invokes_serve(self, cli, monkeypatch):
        called = []
        monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
        result = cli.invoke(app, ["serve"])
        assert result.exit_code == 0
        assert called == [True]


# ---------------------------------------------------------------------------
# _validate_vcf
# ---------------------------------------------------------------------------


def _mock_pysam_ok(monkeypatch):
    """Helper: make pysam.VariantFile succeed."""
    mock_vf = MagicMock()
    mock_vf.__enter__ = lambda s: s
    mock_vf.__exit__ = lambda s, *a: None
    monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)


class TestValidateVcf:
    def test_missing_file(self, tmp_path, capsys):
        assert _validate_vcf(tmp_path / "missing.vcf.gz") is False
        assert "not found" in capsys.readouterr().err

    def test_auto_creates_index(self, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        monkeypatch.setattr("pysam.tabix_index", lambda *a, **kw: None)
        _mock_pysam_ok(monkeypatch)
        assert _validate_vcf(vcf) is True

    def test_index_creation_fails(self, tmp_path, capsys, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        def bad_tabix(*a, **kw):
            raise Exception("bad file")

        monkeypatch.setattr("pysam.tabix_index", bad_tabix)
        assert _validate_vcf(vcf) is False
        assert "Cannot create index" in capsys.readouterr().err

    def test_with_existing_tbi(self, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")
        _mock_pysam_ok(monkeypatch)
        assert _validate_vcf(vcf) is True

    def test_with_existing_csi(self, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.csi").write_bytes(b"fake")
        _mock_pysam_ok(monkeypatch)
        assert _validate_vcf(vcf) is True

    def test_invalid_vcf(self, tmp_path, capsys, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"not a real vcf")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        def bad_vf(*a, **kw):
            raise ValueError("not a valid VCF")

        monkeypatch.setattr("pysam.VariantFile", bad_vf)
        assert _validate_vcf(vcf) is False
        assert "Cannot read VCF" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _patch_db_path_for
# ---------------------------------------------------------------------------


class TestPatchDbPathFor:
    def test_convention_from_vcf(self):
        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), GenomeConfig())
        assert result == Path("/data/sample.patch.db")

    def test_from_genome_config(self):
        genome_cfg = GenomeConfig(patch_db="/custom/path.db")
        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), genome_cfg)
        assert result == Path("/custom/path.db")

    def test_falls_back_to_convention(self):
        """Falls back to VCF stem convention when no patch_db configured."""
        genome_cfg = GenomeConfig()
        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), genome_cfg)
        assert result == Path("/data/sample.patch.db")


# ---------------------------------------------------------------------------
# genechat add
# ---------------------------------------------------------------------------


class TestAdd:
    def test_add_missing_vcf(self, cli):
        result = cli.invoke(app, ["add", "/nonexistent/file.vcf.gz"])
        assert result.exit_code == ExitCode.VCF_ERROR
        assert "not found" in result.output

    def test_add_writes_config(self, cli, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        result = cli.invoke(app, ["add", str(vcf)])

        config_path = config_dir / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        assert str(vcf.resolve()) in content
        assert "VCF registered" in result.output
        assert "'default'" in result.output

        # Check permissions (owner read/write only)
        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_add_with_label(self, cli, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        result = cli.invoke(app, ["add", str(vcf), "--label", "nate"])

        config_path = config_dir / "config.toml"
        content = config_path.read_text()
        assert "[genomes.nate]" in content
        assert "'nate'" in result.output


# ---------------------------------------------------------------------------
# genechat init
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_missing_vcf(self, cli):
        result = cli.invoke(app, ["init", "/nonexistent/file.vcf.gz"])
        assert result.exit_code == ExitCode.VCF_ERROR
        assert "not found" in result.output

    def test_init_full_pipeline(self, cli, tmp_path, monkeypatch):
        """init runs: validate -> config -> lookup_db -> annotate -> print MCP config."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: True)
        annotate_calls = []
        monkeypatch.setattr(
            "genechat.cli._run_annotate", lambda **kw: annotate_calls.append(kw)
        )

        result = cli.invoke(app, ["init", str(vcf)])

        assert result.exit_code == 0
        assert "GeneChat Setup" in result.output
        assert "mcpServers" in result.output
        assert (config_dir / "config.toml").exists()
        assert len(annotate_calls) == 1, "init must delegate to _run_annotate"

    def test_init_gwas_flag(self, cli, tmp_path, monkeypatch):
        """--gwas calls _run_install and suppresses the hint."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)
        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: True)
        monkeypatch.setattr("genechat.cli._run_annotate", lambda **kw: None)

        install_calls = []
        monkeypatch.setattr(
            "genechat.cli._run_install",
            lambda **kw: install_calls.append(kw),
        )

        result = cli.invoke(app, ["init", str(vcf), "--gwas"])

        assert result.exit_code == 0
        assert install_calls, "_run_install was not called"
        assert install_calls[0]["gwas"] is True
        assert "Optional: Enable GWAS" not in result.output

    def test_init_gnomad_passes_flag_to_annotate(self, cli, tmp_path, monkeypatch):
        """--gnomad passes through to _run_annotate (no special init handling)."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)
        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: True)

        annotate_calls = []
        monkeypatch.setattr(
            "genechat.cli._run_annotate",
            lambda **kw: annotate_calls.append(kw),
        )

        result = cli.invoke(app, ["init", str(vcf), "--gnomad"])

        assert result.exit_code == 0
        assert len(annotate_calls) == 1
        assert annotate_calls[0]["gnomad"] is True

    def test_init_missing_lookup_db(self, cli, tmp_path, monkeypatch):
        """init exits when _ensure_lookup_db fails."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)
        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: False)

        result = cli.invoke(app, ["init", str(vcf)])
        assert result.exit_code == ExitCode.CONFIG_ERROR


# ---------------------------------------------------------------------------
# genechat install
# ---------------------------------------------------------------------------


class TestInstall:
    def test_no_flags_shows_available(self, cli, monkeypatch):
        """install with no flags lists available databases."""
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        result = cli.invoke(app, ["install"])
        assert result.exit_code == 0
        assert "--gwas" in result.output
        assert "--seeds" in result.output
        assert "Available databases" in result.output

    def test_gwas_flag(self, cli, monkeypatch):
        """--gwas installs the GWAS Catalog."""
        calls = []
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        monkeypatch.setattr("genechat.gwas.gwas_installed", lambda: False)
        monkeypatch.setattr(
            "genechat.cli._download_and_build_gwas",
            lambda **kw: calls.append("gwas"),
        )
        result = cli.invoke(app, ["install", "--gwas"])
        assert result.exit_code == 0
        assert "gwas" in calls

    def test_gwas_skips_when_installed(self, cli, monkeypatch):
        """--gwas without --force skips when already installed."""
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        monkeypatch.setattr("genechat.gwas.gwas_installed", lambda: True)
        result = cli.invoke(app, ["install", "--gwas"])
        assert result.exit_code == 0
        assert "already installed" in result.output

    def test_gwas_force_rebuilds(self, cli, monkeypatch):
        """--gwas --force rebuilds even when already installed."""
        calls = []
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        monkeypatch.setattr("genechat.gwas.gwas_installed", lambda: True)
        monkeypatch.setattr(
            "genechat.cli._download_and_build_gwas",
            lambda **kw: calls.append(kw),
        )
        result = cli.invoke(app, ["install", "--gwas", "--force"])
        assert result.exit_code == 0
        assert len(calls) == 1
        assert calls[0].get("force") is True


# ---------------------------------------------------------------------------
# genechat annotate
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_no_vcf_registered(self, cli, monkeypatch):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        result = cli.invoke(app, ["annotate"])
        assert result.exit_code == ExitCode.CONFIG_ERROR
        assert "No VCF registered" in result.output

    def test_shows_usage_no_action_flags(self, cli, tmp_path, monkeypatch):
        """annotate with no action flags (clinvar/snpeff/etc) shows usage guidance."""
        # Create a fake patch.db so it's not a first run
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_db = tmp_path / "test.patch.db"
        patch_db.write_bytes(b"fake")

        config = AppConfig(
            genomes={
                "personal": {
                    "vcf_path": str(vcf),
                    "patch_db": str(patch_db),
                }
            }
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        result = cli.invoke(app, ["annotate", "--genome", "personal"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "personal" in result.output
        assert "status" in result.output.lower()

    def test_annotate_dbsnp_calls_bcftools(self, tmp_path, monkeypatch, capsys):
        """_annotate_dbsnp invokes bcftools with correct args and updates metadata."""
        from genechat.cli import _annotate_dbsnp
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        # Populate a variant without rsID
        snpeff_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1||\n"
        ]
        patch.populate_from_snpeff_stream(iter(snpeff_lines))

        # Mock dbsnp_path and _dbsnp_version
        fake_dbsnp = tmp_path / "dbsnp_chrfixed.vcf.gz"
        fake_dbsnp.write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.dbsnp_path", lambda: fake_dbsnp)
        monkeypatch.setattr("genechat.cli._dbsnp_version", lambda _path: "Build 156")

        popen_calls = []
        fake_vcf = tmp_path / "raw.vcf.gz"
        fake_vcf.write_bytes(b"fake")

        # Mock Popen to return dbSNP-annotated VCF lines
        class MockStdout:
            """Iterable stdout mock with close() support."""

            def __init__(self, lines):
                self._iter = iter(lines)

            def __iter__(self):
                return self._iter

            def __next__(self):
                return next(self._iter)

            def close(self):
                pass

        class MockProc:
            def __init__(self, cmd, **kw):
                popen_calls.append(cmd)
                self.stdout = MockStdout(
                    ["chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t.\tGT\t0/1\n"]
                )
                self.returncode = 0

            def wait(self):
                return 0

            def poll(self):
                return 0

        monkeypatch.setattr("genechat.cli.subprocess.Popen", MockProc)

        _annotate_dbsnp(patch, fake_vcf, step=1, total=1, is_update=False)

        # Verify bcftools was called with -c ID
        assert len(popen_calls) == 1
        cmd = popen_calls[0]
        assert "bcftools" in cmd[0]
        assert "-c" in cmd
        assert "ID" in cmd

        # Verify rsID was written to patch.db
        ann = patch.get_annotation("chr12", 21178615, "T", "C")
        assert ann["rsid"] == "rs4149056"
        assert ann["rsid_source"] == "dbsnp"

        # Verify metadata was set
        meta = patch.get_metadata()
        assert meta["dbsnp"]["version"] == "Build 156"
        assert meta["dbsnp"]["status"] == "complete"

        patch.close()

    def test_annotate_dbsnp_failure_sets_metadata(self, tmp_path, monkeypatch, capsys):
        """_annotate_dbsnp sets metadata to 'failed' on bcftools failure."""
        from genechat.cli import _annotate_dbsnp
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        snpeff_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1||\n"
        ]
        patch.populate_from_snpeff_stream(iter(snpeff_lines))

        fake_dbsnp = tmp_path / "dbsnp_chrfixed.vcf.gz"
        fake_dbsnp.write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.dbsnp_path", lambda: fake_dbsnp)
        monkeypatch.setattr("genechat.cli._dbsnp_version", lambda _path: "Build 156")

        fake_vcf = tmp_path / "raw.vcf.gz"
        fake_vcf.write_bytes(b"fake")

        class MockStdout:
            def __iter__(self):
                return iter([])

            def close(self):
                pass

        class MockProc:
            def __init__(self, cmd, **kw):
                self.stdout = MockStdout()
                self.returncode = 1

            def wait(self):
                return 1

            def poll(self):
                return 1

        monkeypatch.setattr("genechat.cli.subprocess.Popen", MockProc)

        with pytest.raises(RuntimeError, match="failed with exit code 1"):
            _annotate_dbsnp(patch, fake_vcf, step=1, total=1, is_update=False)

        meta = patch.get_metadata()
        assert meta["dbsnp"]["status"] == "failed"

        patch.close()

    def test_annotate_gnomad_incremental_when_not_installed(
        self, cli, tmp_path, monkeypatch
    ):
        """annotate --gnomad uses incremental mode when gnomAD files aren't present."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        annotate_calls = []

        def mock_annotate_gnomad(
            patch, vcf_path, step, total, is_update, incremental=False, **kwargs
        ):
            annotate_calls.append({"incremental": incremental})

        monkeypatch.setattr("genechat.cli._annotate_gnomad", mock_annotate_gnomad)
        # Skip snpeff and clinvar
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: False)

        result = cli.invoke(app, ["annotate", "--gnomad"])

        assert result.exit_code == 0
        assert len(annotate_calls) == 1
        assert annotate_calls[0]["incremental"] is True

    def test_annotate_gnomad_not_incremental_when_installed(
        self, cli, tmp_path, monkeypatch
    ):
        """annotate --gnomad uses normal mode when gnomAD files are present."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: True)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        annotate_calls = []

        def mock_annotate_gnomad(
            patch, vcf_path, step, total, is_update, incremental=False, **kwargs
        ):
            annotate_calls.append({"incremental": incremental})

        monkeypatch.setattr("genechat.cli._annotate_gnomad", mock_annotate_gnomad)
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: False)

        result = cli.invoke(app, ["annotate", "--gnomad"])

        assert result.exit_code == 0
        assert len(annotate_calls) == 1
        assert annotate_calls[0]["incremental"] is False

    def test_annotate_stale_enables_outdated_layers(self, cli, tmp_path, monkeypatch):
        """annotate --stale checks versions and enables stale layers."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-01-01", "complete")
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Mock check_all_versions to return a newer ClinVar
        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {
                "clinvar": "2025-06-15",
                "gnomad": None,
                "snpeff": None,
                "dbsnp": None,
            },
        )

        annotate_calls = []

        def mock_annotate_clinvar(patch, vcf_path, step, total, is_update, **kwargs):
            annotate_calls.append("clinvar")

        monkeypatch.setattr("genechat.cli._annotate_clinvar", mock_annotate_clinvar)
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: False)

        result = cli.invoke(app, ["annotate", "--stale"])

        assert result.exit_code == 0
        assert "Stale layers detected: clinvar" in result.output
        assert "clinvar" in annotate_calls

    def test_annotate_stale_all_up_to_date(self, cli, tmp_path, monkeypatch):
        """annotate --stale with no stale layers shows up-to-date message."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-06-15", "complete")
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)

        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {
                "clinvar": "2025-06-15",
                "gnomad": None,
                "snpeff": None,
                "dbsnp": None,
            },
        )

        result = cli.invoke(app, ["annotate", "--stale"])

        assert result.exit_code == 0
        assert "up to date" in result.output

    def test_init_fast_passes_flag(self, cli, tmp_path, monkeypatch):
        """init --fast passes fast=True to _run_annotate."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)
        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: True)

        annotate_calls = []
        monkeypatch.setattr(
            "genechat.cli._run_annotate",
            lambda **kw: annotate_calls.append(kw),
        )

        result = cli.invoke(app, ["init", str(vcf), "--fast"])

        assert result.exit_code == 0
        assert len(annotate_calls) == 1
        assert annotate_calls[0]["fast"] is True

    def test_annotate_fast_predownloads_gnomad(self, cli, tmp_path, monkeypatch):
        """annotate --gnomad --fast pre-downloads all gnomAD then uses non-incremental."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # gnomad_installed: False initially, then True after download_gnomad
        gnomad_state = {"installed": False}

        def mock_gnomad_installed():
            return gnomad_state["installed"]

        monkeypatch.setattr("genechat.download.gnomad_installed", mock_gnomad_installed)

        download_gnomad_calls = []

        def mock_download_gnomad(**kw):
            gnomad_state["installed"] = True
            download_gnomad_calls.append(True)
            return tmp_path / "gnomad"

        monkeypatch.setattr("genechat.download.download_gnomad", mock_download_gnomad)

        annotate_gnomad_calls = []

        def mock_annotate_gnomad(
            patch, vcf_path, step, total, is_update, incremental=False, **kwargs
        ):
            annotate_gnomad_calls.append({"incremental": incremental})

        monkeypatch.setattr("genechat.cli._annotate_gnomad", mock_annotate_gnomad)
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: False)

        result = cli.invoke(app, ["annotate", "--gnomad", "--fast"])

        assert result.exit_code == 0
        assert len(download_gnomad_calls) == 1, "download_gnomad should be called"
        assert len(annotate_gnomad_calls) == 1
        assert annotate_gnomad_calls[0]["incremental"] is False

    def test_annotate_fast_dbsnp(self, cli, tmp_path, monkeypatch):
        """annotate --dbsnp --fast passes fast=True to download_dbsnp."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        download_dbsnp_calls = []

        def mock_download_dbsnp(**kw):
            download_dbsnp_calls.append(kw)
            return tmp_path / "dbsnp_chrfixed.vcf.gz"

        monkeypatch.setattr("genechat.download.download_dbsnp", mock_download_dbsnp)
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_dbsnp", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: False)

        result = cli.invoke(app, ["annotate", "--dbsnp", "--fast"])

        assert result.exit_code == 0
        assert len(download_dbsnp_calls) == 1
        assert download_dbsnp_calls[0]["fast"] is True


# ---------------------------------------------------------------------------
# Parallel dispatch in --fast mode
# ---------------------------------------------------------------------------


class TestFastParallelDispatch:
    """Tests that --fast dispatches to parallel annotation path."""

    def test_annotate_gnomad_fast_calls_parallel(self, tmp_path, monkeypatch):
        """_annotate_gnomad with fast=True dispatches to run_parallel_annotation."""
        from genechat.cli import _annotate_gnomad
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        parallel_calls = []

        def mock_run_parallel(**kw):
            parallel_calls.append(kw)
            return 42

        monkeypatch.setattr(
            "genechat.parallel.run_parallel_annotation", mock_run_parallel
        )

        _annotate_gnomad(
            patch,
            vcf,
            step=3,
            total=4,
            is_update=False,
            fast=True,
            patch_db_path=patch_path,
        )

        assert len(parallel_calls) == 1
        assert parallel_calls[0]["source"] == "gnomad"

    def test_annotate_dbsnp_fast_calls_parallel(self, tmp_path, monkeypatch):
        """_annotate_dbsnp with fast=True dispatches to run_parallel_annotation."""
        from genechat.cli import _annotate_dbsnp
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        # dbsnp_path must return a real path for version detection
        fake_dbsnp = tmp_path / "dbsnp.vcf.gz"
        fake_dbsnp.write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.dbsnp_path", lambda: fake_dbsnp)
        monkeypatch.setattr("genechat.cli._dbsnp_version", lambda _: "b156")

        parallel_calls = []

        def mock_run_parallel(**kw):
            parallel_calls.append(kw)
            return 99

        monkeypatch.setattr(
            "genechat.parallel.run_parallel_annotation", mock_run_parallel
        )

        _annotate_dbsnp(
            patch,
            vcf,
            step=4,
            total=4,
            is_update=False,
            fast=True,
            patch_db_path=patch_path,
        )

        assert len(parallel_calls) == 1
        assert parallel_calls[0]["source"] == "dbsnp"

    def test_annotate_gnomad_non_fast_skips_parallel(self, tmp_path, monkeypatch):
        """_annotate_gnomad without fast=True does not call run_parallel_annotation."""
        from genechat.cli import _annotate_gnomad
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        parallel_calls = []
        monkeypatch.setattr(
            "genechat.parallel.run_parallel_annotation",
            lambda **kw: parallel_calls.append(kw) or 0,
        )

        # Mock pysam so sequential path can discover contigs
        fake_vf = type(
            "FakeVF",
            (),
            {
                "__enter__": lambda s: s,
                "__exit__": lambda *a: None,
                "header": type("H", (), {"contigs": ["chr1"]})(),
            },
        )()
        monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: fake_vf)

        # Mock subprocess so sequential bcftools doesn't fail
        class FakeStdout:
            def __iter__(self):
                return iter([])

            def close(self):
                pass

        class FakeStderr:
            def read(self):
                return ""

        class FakeProc:
            stdout = FakeStdout()
            stderr = FakeStderr()

            def wait(self, **kw):
                return 0

            def poll(self):
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())

        _annotate_gnomad(
            patch,
            vcf,
            step=3,
            total=4,
            is_update=False,
            fast=False,
            patch_db_path=patch_path,
        )

        assert len(parallel_calls) == 0, "parallel should NOT be called without --fast"


# ---------------------------------------------------------------------------
# Bare contig rename in annotation pipeline
# ---------------------------------------------------------------------------


class TestAnnotateBareContigs:
    """Tests for bare-contig user VCFs piped through rename during annotation."""

    def test_dbsnp_with_bare_contigs_pipes_rename(self, tmp_path, monkeypatch):
        """_annotate_dbsnp pipes through bcftools --rename-chrs for bare-contig VCFs."""
        from genechat.cli import _annotate_dbsnp
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)

        # Populate a variant with bare contig (as SnpEff would store)
        snpeff_lines = [
            "12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1||\n"
        ]
        patch.populate_from_snpeff_stream(iter(snpeff_lines))

        fake_dbsnp = tmp_path / "dbsnp_chrfixed.vcf.gz"
        fake_dbsnp.write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.dbsnp_path", lambda: fake_dbsnp)
        monkeypatch.setattr("genechat.cli._dbsnp_version", lambda _: "Build 156")

        fake_vcf = tmp_path / "raw.vcf.gz"
        fake_vcf.write_bytes(b"fake")

        # Write rename map
        chr_map = tmp_path / "bare_to_chr.txt"
        from genechat.cli import _write_bare_to_chr_map

        _write_bare_to_chr_map(chr_map)

        popen_calls = []

        class MockStdout:
            def __init__(self, lines):
                self._iter = iter(lines)

            def __iter__(self):
                return self._iter

            def __next__(self):
                return next(self._iter)

            def close(self):
                pass

        class MockProc:
            def __init__(self, cmd, **kw):
                popen_calls.append(cmd)
                # Only the second process (annotate) produces output
                if "-c" in cmd and "ID" in cmd:
                    self.stdout = MockStdout(
                        ["chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t.\tGT\t0/1\n"]
                    )
                else:
                    self.stdout = MockStdout([])
                self.returncode = 0

            def wait(self):
                return 0

            def poll(self):
                return 0

        monkeypatch.setattr("genechat.cli.subprocess.Popen", MockProc)

        _annotate_dbsnp(
            patch,
            fake_vcf,
            step=1,
            total=1,
            is_update=False,
            chr_rename_map=chr_map,
        )

        # Should have 2 Popen calls: rename pipe + annotate
        assert len(popen_calls) == 2
        rename_cmd = popen_calls[0]
        assert "--rename-chrs" in rename_cmd
        annotate_cmd = popen_calls[1]
        assert "-c" in annotate_cmd
        assert "ID" in annotate_cmd
        # Second command reads from stdin (-)
        assert annotate_cmd[-1] == "-"

        # Verify rsID was written — _chrom_variants_fixed handles both forms
        ann = patch.get_annotation("12", 21178615, "T", "C")
        assert ann["rsid"] == "rs4149056"

        patch.close()

    def test_dbsnp_without_rename_map_uses_direct_command(self, tmp_path, monkeypatch):
        """_annotate_dbsnp uses direct bcftools command when no rename needed."""
        from genechat.cli import _annotate_dbsnp
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        snpeff_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1||\n"
        ]
        patch.populate_from_snpeff_stream(iter(snpeff_lines))

        fake_dbsnp = tmp_path / "dbsnp_chrfixed.vcf.gz"
        fake_dbsnp.write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.dbsnp_path", lambda: fake_dbsnp)
        monkeypatch.setattr("genechat.cli._dbsnp_version", lambda _: "Build 156")

        fake_vcf = tmp_path / "raw.vcf.gz"
        fake_vcf.write_bytes(b"fake")

        popen_calls = []

        class MockStdout:
            def __init__(self, lines):
                self._iter = iter(lines)

            def __iter__(self):
                return self._iter

            def __next__(self):
                return next(self._iter)

            def close(self):
                pass

        class MockProc:
            def __init__(self, cmd, **kw):
                popen_calls.append(cmd)
                self.stdout = MockStdout(
                    ["chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t.\tGT\t0/1\n"]
                )
                self.returncode = 0

            def wait(self):
                return 0

            def poll(self):
                return 0

        monkeypatch.setattr("genechat.cli.subprocess.Popen", MockProc)

        _annotate_dbsnp(patch, fake_vcf, step=1, total=1, is_update=False)

        # Only 1 Popen call — no rename pipe
        assert len(popen_calls) == 1
        assert "--rename-chrs" not in popen_calls[0]
        # VCF path is the last argument (not "-" for stdin)
        assert popen_calls[0][-1] == str(fake_vcf)

        patch.close()

    def test_run_annotate_detects_bare_contigs(self, cli, tmp_path, monkeypatch):
        """_run_annotate creates chr_rename_map when VCF has bare contigs."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: True)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Detect as bare contigs
        monkeypatch.setattr("genechat.cli._detect_bare_contigs", lambda _: True)

        dbsnp_kwargs = []

        def mock_annotate_dbsnp(*args, **kwargs):
            dbsnp_kwargs.append(kwargs)

        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_dbsnp", mock_annotate_dbsnp)

        result = cli.invoke(app, ["annotate", "--dbsnp"])

        assert result.exit_code == 0
        assert "bare contig names" in result.output
        assert len(dbsnp_kwargs) == 1
        assert dbsnp_kwargs[0].get("chr_rename_map") is not None

    def test_write_bare_to_chr_map(self, tmp_path):
        """_write_bare_to_chr_map writes correct rename entries."""
        from genechat.cli import _write_bare_to_chr_map

        map_path = tmp_path / "rename.txt"
        _write_bare_to_chr_map(map_path)

        content = map_path.read_text()
        assert "1 chr1\n" in content
        assert "22 chr22\n" in content
        assert "X chrX\n" in content
        assert "Y chrY\n" in content
        assert "MT chrMT\n" in content
        assert "M chrM" not in content  # M is non-standard; only MT is mapped


# ---------------------------------------------------------------------------
# genechat status
# ---------------------------------------------------------------------------


class TestStatus:
    def test_no_genome(self, cli, monkeypatch):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        result = cli.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No genome registered" in result.output

    def test_with_genome(self, cli, tmp_path, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(genomes={"default": {"vcf_path": str(vcf)}})
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["status"])

        assert result.exit_code == 0
        out = result.output
        assert "default:" in out
        assert "exists" in out
        assert "Patch DB: not built" in out
        assert "Installed databases" in out
        assert "Annotation caches" in out

    def test_multi_genome_status(self, cli, tmp_path, monkeypatch):
        vcf1 = tmp_path / "nate.vcf.gz"
        vcf2 = tmp_path / "partner.vcf.gz"
        vcf1.write_bytes(b"fake")
        vcf2.write_bytes(b"fake")

        config = AppConfig(
            genomes={
                "nate": {"vcf_path": str(vcf1)},
                "partner": {"vcf_path": str(vcf2)},
            }
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["status"])

        assert result.exit_code == 0
        out = result.output
        assert "nate:" in out
        assert "partner:" in out

    def test_check_updates_shows_freshness(self, cli, tmp_path, monkeypatch):
        """status --check-updates shows freshness indicators for layers."""
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-01-01", "complete")
        patch.set_metadata("snpeff", "GRCh38.p14", "complete")
        patch.close()

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)
        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {
                "clinvar": "2025-06-15",
                "gnomad": None,
                "snpeff": None,
                "dbsnp": None,
            },
        )

        result = cli.invoke(app, ["status", "--check-updates"])

        assert result.exit_code == 0
        out = result.output
        assert "newer: 2025-06-15" in out

    def test_status_shows_license_tags(self, cli, tmp_path, monkeypatch):
        """status output includes license tags for completed layers."""
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-01-01", "complete")
        patch.set_metadata("snpeff", "GRCh38.p14", "complete")
        patch.set_metadata("gnomad", "v4.1", "complete")
        patch.set_metadata("dbsnp", "b156", "complete")
        patch.close()

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: True)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["status"])

        assert result.exit_code == 0
        out = result.output
        assert "clinvar (2025-01-01, public domain)" in out
        assert "snpeff (GRCh38.p14, MIT)" in out
        assert "gnomad (v4.1, ODbL 1.0)" in out
        assert "dbsnp (b156, public domain)" in out


# ---------------------------------------------------------------------------
# genechat licenses
# ---------------------------------------------------------------------------


class TestLicenses:
    def test_always_shows_base_licenses(self, cli, monkeypatch):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["licenses"])

        assert result.exit_code == 0
        out = result.output
        assert "Always applicable:" in out
        assert "ClinVar" in out
        assert "SnpEff" in out
        assert "CPIC" in out
        assert "HGNC" in out
        assert "Ensembl" in out
        assert "Enhanced-warning gene list (bundled" in out
        assert "HPO" in out
        assert "ACMG SF" in out
        assert "PGS Catalog" in out
        assert "PGS000349" in out
        assert "PGS002251" in out
        assert "docs/licenses.md" in out

    def test_gnomad_not_installed(self, cli, monkeypatch):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["licenses"])

        assert result.exit_code == 0
        assert "gnomAD:            not installed" in result.output

    def test_gnomad_installed_via_annotation(self, cli, tmp_path, monkeypatch):
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("gnomad", "v4.1", "complete")
        patch.close()

        config = AppConfig(
            genomes={"default": {"vcf_path": str(vcf), "patch_db": str(patch_path)}}
        )
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["licenses"])

        assert result.exit_code == 0
        out = result.output
        assert "gnomAD (installed):" in out
        assert "ODbL" in out
        assert "produced works" in out

    def test_gwas_installed(self, cli, tmp_path, monkeypatch):
        import sqlite3

        from genechat.config import DatabasesConfig

        gwas_db = tmp_path / "gwas.db"
        conn = sqlite3.connect(str(gwas_db))
        conn.execute("CREATE TABLE gwas_associations (rsid TEXT, trait TEXT)")
        conn.close()

        config = AppConfig(databases=DatabasesConfig(gwas_db=str(gwas_db)))
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["licenses"])

        assert result.exit_code == 0
        assert "GWAS Catalog (installed):" in result.output
        assert "CC0" in result.output


# ---------------------------------------------------------------------------
# _freshness_indicator / _resolve_stale_layers helpers
# ---------------------------------------------------------------------------


class TestFreshnessIndicator:
    def test_returns_empty_when_no_latest(self):
        assert _freshness_indicator("clinvar", "2025-01-01", {}) == ""

    def test_returns_empty_when_source_not_in_latest(self):
        assert (
            _freshness_indicator("gnomad", "2025-01-01", {"clinvar": "2025-06-15"})
            == ""
        )

    def test_returns_empty_when_latest_is_none(self):
        assert _freshness_indicator("clinvar", "2025-01-01", {"clinvar": None}) == ""

    def test_shows_newer_when_stale(self):
        result = _freshness_indicator(
            "clinvar", "2025-01-01", {"clinvar": "2025-06-15"}
        )
        assert "newer: 2025-06-15" in result
        assert "yellow" in result

    def test_shows_up_to_date_when_current(self):
        result = _freshness_indicator(
            "clinvar", "2025-06-15", {"clinvar": "2025-06-15"}
        )
        assert "up to date" in result
        assert "green" in result


class TestResolveStaleLayersUnit:
    def test_enables_stale_clinvar(self, tmp_path, monkeypatch):
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-01-01", "complete")
        patch.close()

        genome_cfg = GenomeConfig(vcf_path=str(vcf), patch_db=str(patch_path))

        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {
                "clinvar": "2025-06-15",
                "gnomad": None,
                "snpeff": None,
                "dbsnp": None,
            },
        )

        clinvar, gnomad, snpeff, dbsnp = _resolve_stale_layers(
            genome_cfg, False, False, False, False
        )
        assert clinvar is True
        assert gnomad is False
        assert snpeff is False
        assert dbsnp is False

    def test_no_stale_when_up_to_date(self, tmp_path, monkeypatch):
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("clinvar", "2025-06-15", "complete")
        patch.close()

        genome_cfg = GenomeConfig(vcf_path=str(vcf), patch_db=str(patch_path))

        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {
                "clinvar": "2025-06-15",
                "gnomad": None,
                "snpeff": None,
                "dbsnp": None,
            },
        )

        clinvar, gnomad, snpeff, dbsnp = _resolve_stale_layers(
            genome_cfg, False, False, False, False
        )
        assert clinvar is False

    def test_preserves_existing_flags(self, tmp_path, monkeypatch):
        """--stale doesn't disable layers the user explicitly requested."""
        from genechat.patch import PatchDB

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.close()

        genome_cfg = GenomeConfig(vcf_path=str(vcf), patch_db=str(patch_path))

        monkeypatch.setattr(
            "genechat.update.check_all_versions",
            lambda: {"clinvar": None, "gnomad": None, "snpeff": None, "dbsnp": None},
        )

        # User passed --gnomad explicitly, should be preserved
        clinvar, gnomad, snpeff, dbsnp = _resolve_stale_layers(
            genome_cfg, False, True, False, False
        )
        assert gnomad is True

    def test_no_patch_db_returns_flags_unchanged(self, tmp_path, monkeypatch):
        """If patch.db doesn't exist, flags pass through unchanged."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        genome_cfg = GenomeConfig(
            vcf_path=str(vcf),
            patch_db=str(tmp_path / "nonexistent.patch.db"),
        )

        clinvar, gnomad, snpeff, dbsnp = _resolve_stale_layers(
            genome_cfg, False, True, False, False
        )
        assert clinvar is False
        assert gnomad is True


# ---------------------------------------------------------------------------
# genechat update
# ---------------------------------------------------------------------------


class TestUpdateRemoved:
    def test_update_not_recognized(self, cli):
        """'update' subcommand was removed in the UX redesign."""
        result = cli.invoke(app, ["update"])
        assert result.exit_code == 2  # Typer/Click usage error


# ---------------------------------------------------------------------------
# _ensure_lookup_db
# ---------------------------------------------------------------------------


class TestEnsureLookupDb:
    def test_returns_true_when_user_rebuilt_db_exists(self, tmp_path, monkeypatch):
        """User-rebuilt DB in user_data_dir is found without checking package data."""
        user_db = tmp_path / "user" / "lookup_tables.db"
        user_db.parent.mkdir(parents=True)
        user_db.write_bytes(b"user-rebuilt")

        monkeypatch.setattr("genechat.config._user_db_path", lambda: user_db)

        # Ensure we do not fall back to package data when a user DB exists.
        def _forbid_files(_pkg: object) -> Path:
            raise AssertionError(
                "importlib.resources.files should not be called when user DB exists"
            )

        monkeypatch.setattr(_real_resources, "files", _forbid_files)
        assert _ensure_lookup_db() is True

    def test_returns_true_when_db_exists(self, tmp_path, monkeypatch):
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        (pkg_data / "lookup_tables.db").write_bytes(b"fake")

        # No user-rebuilt DB
        monkeypatch.setattr(
            "genechat.config._user_db_path", lambda: tmp_path / "no" / "db"
        )
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        assert _ensure_lookup_db() is True

    def test_returns_false_when_missing_no_source(self, tmp_path, monkeypatch, capsys):
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        # No lookup_tables.db

        monkeypatch.setattr(
            "genechat.config._user_db_path", lambda: tmp_path / "no" / "db"
        )
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: None)

        assert _ensure_lookup_db() is False
        assert "lookup_tables.db not found" in capsys.readouterr().err

    def test_auto_builds_from_source_checkout(self, tmp_path, monkeypatch, capsys):
        """When in source checkout with seed data, auto-builds lookup_tables.db."""
        import sys

        import genechat.seeds.build_db  # noqa: F401 — force module into sys.modules

        _build_db_mod = sys.modules["genechat.seeds.build_db"]

        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)

        project_root = tmp_path / "project"
        seed_dir = project_root / "data" / "seed"
        seed_dir.mkdir(parents=True)
        (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        def fake_build(seed_dir, db_path):
            db_path.write_bytes(b"built")

        monkeypatch.setattr(
            "genechat.config._user_db_path", lambda: tmp_path / "no" / "db"
        )
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: project_root)
        monkeypatch.setattr(_build_db_mod, "build_db", fake_build)

        assert _ensure_lookup_db() is True
        assert "Building lookup_tables.db" in capsys.readouterr().out

    def test_auto_build_failure_returns_false(self, tmp_path, monkeypatch, capsys):
        """When auto-build raises an exception, returns False."""
        import sys

        import genechat.seeds.build_db  # noqa: F401 — force module into sys.modules

        _build_db_mod = sys.modules["genechat.seeds.build_db"]

        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)

        project_root = tmp_path / "project"
        seed_dir = project_root / "data" / "seed"
        seed_dir.mkdir(parents=True)
        (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        def failing_build(seed_dir, db_path):
            raise RuntimeError("build failed")

        monkeypatch.setattr(
            "genechat.config._user_db_path", lambda: tmp_path / "no" / "db"
        )
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: project_root)
        monkeypatch.setattr(_build_db_mod, "build_db", failing_build)

        assert _ensure_lookup_db() is False
        assert "Error building" in capsys.readouterr().err

    def test_installed_mode_error_suggests_reinstall(
        self, tmp_path, monkeypatch, capsys
    ):
        """When no source checkout and no DB, suggests reinstalling the package."""
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)

        monkeypatch.setattr(
            "genechat.config._user_db_path", lambda: tmp_path / "no" / "db"
        )
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: None)

        assert _ensure_lookup_db() is False
        err = capsys.readouterr().err
        assert "uv tool install" in err


# ---------------------------------------------------------------------------
# Contig auto-fix
# ---------------------------------------------------------------------------


class TestContigAutoFix:
    def test_detect_bare_contigs_true(self, monkeypatch):
        """Detects VCFs with bare contig names (1, 2, ...)."""
        from genechat.cli import _detect_bare_contigs

        mock_vf = MagicMock()
        mock_vf.__enter__ = lambda s: s
        mock_vf.__exit__ = lambda s, *a: None
        mock_vf.header.contigs = ["1", "2", "X"]
        monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

        assert _detect_bare_contigs(Path("test.vcf.gz")) is True

    def test_detect_bare_contigs_false(self, monkeypatch):
        """Returns False for VCFs with chr-prefixed contigs."""
        from genechat.cli import _detect_bare_contigs

        mock_vf = MagicMock()
        mock_vf.__enter__ = lambda s: s
        mock_vf.__exit__ = lambda s, *a: None
        mock_vf.header.contigs = ["chr1", "chr2", "chrX"]
        monkeypatch.setattr("pysam.VariantFile", lambda *a, **kw: mock_vf)

        assert _detect_bare_contigs(Path("test.vcf.gz")) is False

    def test_fix_user_contigs(self, tmp_path, monkeypatch):
        """_fix_user_contigs calls bcftools and pysam.tabix_index."""
        from genechat.cli import _fix_user_contigs

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        run_calls = []
        monkeypatch.setattr(
            "genechat.cli.subprocess.run",
            lambda cmd, **kw: run_calls.append(cmd) or MagicMock(returncode=0),
        )
        monkeypatch.setattr("pysam.tabix_index", lambda *a, **kw: None)

        result = _fix_user_contigs(vcf)

        assert "chrfixed" in result.name
        assert len(run_calls) == 1
        assert "--rename-chrs" in run_calls[0]


# ---------------------------------------------------------------------------
# _annotate_snpeff skips empty contigs
# ---------------------------------------------------------------------------


class TestAnnotateSnpeffSkipsEmpty:
    def test_skips_contigs_without_variants(self, tmp_path, monkeypatch):
        """_annotate_snpeff uses TabixFile.contigs to skip empty contigs."""
        from genechat.cli import _annotate_snpeff

        # TabixFile.contigs returns only contigs with variants
        mock_tf = MagicMock()
        mock_tf.contigs = ("chr1", "chr22")
        monkeypatch.setattr("pysam.TabixFile", lambda *a, **kw: mock_tf)

        # Mock subprocess — need separate bcf_proc (bytes stdout) and
        # snpeff_proc (text stdout) per iteration
        def make_popen(cmd, **kw):
            proc = MagicMock()
            proc.wait.return_value = 0
            if "snpEff" in cmd:
                proc.stdout = iter([])  # empty text stream
            else:
                proc.stdout = MagicMock()  # bcf_proc: .close() must work
            return proc

        monkeypatch.setattr("genechat.cli.subprocess.Popen", make_popen)

        # Mock patch object
        mock_patch = MagicMock()
        mock_patch.populate_from_snpeff_stream.return_value = 0

        # Mock download._detect_snpeff_db
        monkeypatch.setattr("genechat.download._detect_snpeff_db", lambda: "GRCh38.p14")

        _annotate_snpeff(mock_patch, tmp_path / "test.vcf.gz", 1, 1, False)

        # Should only process chr1 and chr22, not 195 header contigs
        assert mock_patch.populate_from_snpeff_stream.call_count == 2


# ---------------------------------------------------------------------------
# _resolve_genome_label
# ---------------------------------------------------------------------------


class TestResolveGenomeLabel:
    def test_no_genomes_exits(self):
        from genechat.cli import _resolve_genome_label

        config = AppConfig()
        with pytest.raises(typer.Exit):
            _resolve_genome_label(config, None)

    def test_default_genome(self):
        from genechat.cli import _resolve_genome_label

        config = AppConfig(genomes={"default": {"vcf_path": "/test.vcf.gz"}})
        label, genome_cfg = _resolve_genome_label(config, None)
        assert label == "default"
        assert genome_cfg.vcf_path == "/test.vcf.gz"

    def test_specific_genome(self):
        from genechat.cli import _resolve_genome_label

        config = AppConfig(
            genomes={
                "nate": {"vcf_path": "/nate.vcf.gz"},
                "partner": {"vcf_path": "/partner.vcf.gz"},
            }
        )
        label, genome_cfg = _resolve_genome_label(config, "partner")
        assert label == "partner"
        assert genome_cfg.vcf_path == "/partner.vcf.gz"

    def test_unknown_genome_exits(self):
        from genechat.cli import _resolve_genome_label

        config = AppConfig(genomes={"default": {"vcf_path": "/test.vcf.gz"}})
        with pytest.raises(typer.Exit):
            _resolve_genome_label(config, "nonexistent")


# ---------------------------------------------------------------------------
# --version flag
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self, cli):
        result = cli.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "genechat" in result.output


# ---------------------------------------------------------------------------
# --json flag on status
# ---------------------------------------------------------------------------


class TestStatusJson:
    def test_json_output(self, cli, tmp_path, monkeypatch):
        import json as _json

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(genomes={"default": {"vcf_path": str(vcf)}})
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert "genomes" in data
        assert "references" in data
        assert "default" in data["genomes"]
        assert data["genomes"]["default"]["vcf_exists"] is True

    def test_json_no_genome(self, cli, monkeypatch):
        import json as _json

        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        result = cli.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["genomes"] == {}


# ---------------------------------------------------------------------------
# Color support
# ---------------------------------------------------------------------------


class TestColor:
    def test_no_color_flag(self, cli, monkeypatch):
        """--no-color flag disables color in output."""
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)
        result = cli.invoke(app, ["--no-color", "status"])
        assert result.exit_code == 0
        assert "\033[" not in result.output


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


class TestExceptionHandling:
    def test_keyboard_interrupt_exits_130(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "genechat.cli._run_serve",
            lambda: (_ for _ in ()).throw(KeyboardInterrupt),
        )
        with pytest.raises(SystemExit) as exc_info:
            main(["serve"])
        assert exc_info.value.code == 130
        assert "Interrupted" in capsys.readouterr().err

    def test_unexpected_exception_exits_1(self, monkeypatch, capsys):
        def raise_runtime():
            raise RuntimeError("something broke")

        monkeypatch.setattr("genechat.cli._run_serve", raise_runtime)
        with pytest.raises(SystemExit) as exc_info:
            main(["serve"])
        assert exc_info.value.code == ExitCode.GENERAL_ERROR
        err = capsys.readouterr().err
        assert "something broke" in err
        assert "github.com" in err


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_exit_codes_are_distinct(self):
        values = [e.value for e in ExitCode]
        assert len(values) == len(set(values))
