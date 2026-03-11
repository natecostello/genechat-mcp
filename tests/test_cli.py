"""Tests for the genechat CLI (all 7 subcommands)."""

import importlib.resources as _real_resources
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from genechat.cli import (
    ExitCode,
    _ensure_lookup_db,
    _patch_db_path_for,
    _validate_vcf,
    main,
)
from genechat.config import AppConfig, GenomeConfig


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
        main([])
        out = capsys.readouterr().out
        assert "genechat init" in out
        assert "Quick start" in out

    def test_no_subcommand_invokes_serve_when_piped(self, monkeypatch):
        """No subcommand with piped stdin starts the server."""
        called = []
        monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
        monkeypatch.setattr("sys.stdin", _FakeStdin(tty=False))
        main([])
        assert called == [True]

    def test_serve_subcommand_invokes_serve(self, monkeypatch):
        called = []
        monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
        main(["serve"])
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
        from genechat.config import GenomeConfig

        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), GenomeConfig())
        assert result == Path("/data/sample.patch.db")

    def test_from_genome_config(self):
        from genechat.config import GenomeConfig

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
    def test_add_missing_vcf(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["add", "/nonexistent/file.vcf.gz"])
        assert exc_info.value.code == ExitCode.VCF_ERROR
        assert "not found" in capsys.readouterr().err

    def test_add_writes_config(self, tmp_path, capsys, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        main(["add", str(vcf)])

        config_path = config_dir / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        assert str(vcf.resolve()) in content
        out = capsys.readouterr().out
        assert "VCF registered" in out
        assert "'default'" in out

        # Check permissions (owner read/write only)
        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_add_with_label(self, tmp_path, capsys, monkeypatch):
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        main(["add", str(vcf), "--label", "nate"])

        config_path = config_dir / "config.toml"
        content = config_path.read_text()
        assert "[genomes.nate]" in content
        out = capsys.readouterr().out
        assert "'nate'" in out


# ---------------------------------------------------------------------------
# genechat init
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_missing_vcf(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "/nonexistent/file.vcf.gz"])
        assert exc_info.value.code == ExitCode.VCF_ERROR
        assert "not found" in capsys.readouterr().err

    def test_init_full_pipeline(self, tmp_path, capsys, monkeypatch):
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
            "genechat.cli._run_annotate", lambda args: annotate_calls.append(args)
        )

        main(["init", str(vcf)])

        out = capsys.readouterr().out
        assert "GeneChat Setup" in out
        assert "mcpServers" in out
        assert (config_dir / "config.toml").exists()
        assert len(annotate_calls) == 1, "init must delegate to _run_annotate"

    def test_init_gwas_flag(self, tmp_path, capsys, monkeypatch):
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
        monkeypatch.setattr("genechat.cli._run_annotate", lambda args: None)

        install_calls = []
        monkeypatch.setattr(
            "genechat.cli._run_install",
            lambda args: install_calls.append(args),
        )

        main(["init", str(vcf), "--gwas"])

        out = capsys.readouterr().out
        assert install_calls, "_run_install was not called"
        assert install_calls[0].gwas is True
        assert "Optional: Enable GWAS" not in out

    def test_init_gnomad_passes_flag_to_annotate(self, tmp_path, capsys, monkeypatch):
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

        annotate_args = []
        monkeypatch.setattr(
            "genechat.cli._run_annotate",
            lambda args: annotate_args.append(args),
        )

        main(["init", str(vcf), "--gnomad"])

        assert len(annotate_args) == 1
        assert annotate_args[0].gnomad is True

    def test_init_missing_lookup_db(self, tmp_path, capsys, monkeypatch):
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

        with pytest.raises(SystemExit) as exc_info:
            main(["init", str(vcf)])
        assert exc_info.value.code == ExitCode.CONFIG_ERROR


# ---------------------------------------------------------------------------
# genechat install
# ---------------------------------------------------------------------------


class TestInstall:
    def test_no_flags_shows_available(self, monkeypatch, capsys):
        """install with no flags lists available databases."""
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        main(["install"])
        out = capsys.readouterr().out
        assert "--gwas" in out
        assert "--seeds" in out
        assert "Available databases" in out

    def test_gwas_flag(self, monkeypatch, capsys):
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
        main(["install", "--gwas"])
        assert "gwas" in calls

    def test_gwas_skips_when_installed(self, monkeypatch, capsys):
        """--gwas without --force skips when already installed."""
        monkeypatch.setattr(
            "genechat.gwas.gwas_db_path", lambda: Path("/tmp/data/gwas.db")
        )
        monkeypatch.setattr("genechat.gwas.gwas_installed", lambda: True)
        main(["install", "--gwas"])
        out = capsys.readouterr().out
        assert "already installed" in out

    def test_gwas_force_rebuilds(self, monkeypatch, capsys):
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
        main(["install", "--gwas", "--force"])
        assert len(calls) == 1
        assert calls[0].get("force") is True


# ---------------------------------------------------------------------------
# genechat annotate
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_no_vcf_registered(self, monkeypatch, capsys):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        with pytest.raises(SystemExit) as exc_info:
            main(["annotate"])
        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        assert "No VCF registered" in capsys.readouterr().err

    def test_shows_usage_no_action_flags(self, tmp_path, monkeypatch, capsys):
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
        main(["annotate", "--genome", "personal"])

        out = capsys.readouterr().out
        assert "Usage:" in out
        assert "personal" in out
        assert "status" in out.lower()

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
        self, tmp_path, monkeypatch, capsys
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
            patch, vcf_path, step, total, is_update, incremental=False
        ):
            annotate_calls.append({"incremental": incremental})

        monkeypatch.setattr("genechat.cli._annotate_gnomad", mock_annotate_gnomad)
        # Skip snpeff and clinvar
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)

        main(["annotate", "--gnomad"])

        assert len(annotate_calls) == 1
        assert annotate_calls[0]["incremental"] is True

    def test_annotate_gnomad_not_incremental_when_installed(
        self, tmp_path, monkeypatch, capsys
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
            patch, vcf_path, step, total, is_update, incremental=False
        ):
            annotate_calls.append({"incremental": incremental})

        monkeypatch.setattr("genechat.cli._annotate_gnomad", mock_annotate_gnomad)
        monkeypatch.setattr("genechat.cli._annotate_snpeff", lambda *a, **kw: None)
        monkeypatch.setattr("genechat.cli._annotate_clinvar", lambda *a, **kw: None)

        main(["annotate", "--gnomad"])

        assert len(annotate_calls) == 1
        assert annotate_calls[0]["incremental"] is False


# ---------------------------------------------------------------------------
# genechat status
# ---------------------------------------------------------------------------


class TestStatus:
    def test_no_genome(self, monkeypatch, capsys):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        main(["status"])
        assert "No genome registered" in capsys.readouterr().out

    def test_with_genome(self, tmp_path, monkeypatch, capsys):
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

        main(["status"])

        out = capsys.readouterr().out
        assert "default:" in out
        assert "exists" in out
        assert "Patch DB: not built" in out
        assert "Installed databases" in out
        assert "Annotation caches" in out

    def test_multi_genome_status(self, tmp_path, monkeypatch, capsys):
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

        main(["status"])

        out = capsys.readouterr().out
        assert "nate:" in out
        assert "partner:" in out


# ---------------------------------------------------------------------------
# genechat update
# ---------------------------------------------------------------------------


class TestUpdateRemoved:
    def test_update_not_recognized(self):
        """'update' subcommand was removed in the UX redesign."""
        with pytest.raises(SystemExit) as exc_info:
            main(["update"])
        assert exc_info.value.code == 2  # argparse usage error


# ---------------------------------------------------------------------------
# _ensure_lookup_db
# ---------------------------------------------------------------------------


class TestEnsureLookupDb:
    def test_returns_true_when_db_exists(self, tmp_path, monkeypatch):
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        (pkg_data / "lookup_tables.db").write_bytes(b"fake")

        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        assert _ensure_lookup_db() is True

    def test_returns_false_when_missing_no_source(self, tmp_path, monkeypatch, capsys):
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        # No lookup_tables.db

        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: None)

        assert _ensure_lookup_db() is False
        assert "lookup_tables.db not found" in capsys.readouterr().err

    def test_auto_builds_from_source_checkout(self, tmp_path, monkeypatch, capsys):
        """When in source checkout with seed data, auto-builds lookup_tables.db."""
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        # No lookup_tables.db yet

        # Set up fake project root with seed dir and build script
        project_root = tmp_path / "project"
        seed_dir = project_root / "data" / "seed"
        seed_dir.mkdir(parents=True)
        scripts_dir = project_root / "scripts"
        scripts_dir.mkdir()
        build_script = scripts_dir / "build_lookup_db.py"
        build_script.write_text(
            "def build_db(seed_dir, db_path):\n    db_path.write_bytes(b'built')\n"
        )
        (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: project_root)

        assert _ensure_lookup_db() is True
        assert "Building lookup_tables.db" in capsys.readouterr().out

    def test_auto_build_failure_returns_false(self, tmp_path, monkeypatch, capsys):
        """When auto-build raises an exception, returns False."""
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)

        project_root = tmp_path / "project"
        seed_dir = project_root / "data" / "seed"
        seed_dir.mkdir(parents=True)
        scripts_dir = project_root / "scripts"
        scripts_dir.mkdir()
        build_script = scripts_dir / "build_lookup_db.py"
        build_script.write_text(
            "def build_db(seed_dir, db_path):\n    raise RuntimeError('build failed')\n"
        )
        (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")
        monkeypatch.setattr("genechat.cli._find_project_root", lambda: project_root)

        assert _ensure_lookup_db() is False
        assert "Error building" in capsys.readouterr().err

    def test_installed_mode_error_suggests_reinstall(
        self, tmp_path, monkeypatch, capsys
    ):
        """When no source checkout and no DB, suggests reinstalling the package."""
        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)

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
# _resolve_genome_label
# ---------------------------------------------------------------------------


class TestResolveGenomeLabel:
    def test_no_genomes_exits(self):
        from genechat.cli import _resolve_genome_label

        config = AppConfig()
        with pytest.raises(SystemExit):
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
        with pytest.raises(SystemExit):
            _resolve_genome_label(config, "nonexistent")


# ---------------------------------------------------------------------------
# --version flag
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "genechat" in out


# ---------------------------------------------------------------------------
# --json flag on status
# ---------------------------------------------------------------------------


class TestStatusJson:
    def test_json_output(self, tmp_path, monkeypatch, capsys):
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

        main(["status", "--json"])

        out = capsys.readouterr().out
        data = _json.loads(out)
        assert "genomes" in data
        assert "references" in data
        assert "default" in data["genomes"]
        assert data["genomes"]["default"]["vcf_exists"] is True

    def test_json_no_genome(self, monkeypatch, capsys):
        import json as _json

        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)

        main(["status", "--json"])

        out = capsys.readouterr().out
        data = _json.loads(out)
        assert data["genomes"] == {}


# ---------------------------------------------------------------------------
# Color support
# ---------------------------------------------------------------------------


class TestColor:
    def test_no_color_env_disables_color(self, monkeypatch):
        from genechat.cli import _red

        import genechat.cli

        genechat.cli._COLOR_ENABLED = None
        monkeypatch.setenv("NO_COLOR", "1")
        assert _red("text") == "text"

    def test_no_color_flag(self, monkeypatch, capsys):
        """--no-color flag disables color in output."""
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr(
            "genechat.download.references_dir", lambda: Path("/tmp/refs")
        )
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: False)
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.gnomad_installed", lambda: False)
        monkeypatch.setattr("genechat.download.dbsnp_installed", lambda: False)
        main(["--no-color", "status"])
        out = capsys.readouterr().out
        assert "\033[" not in out


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
