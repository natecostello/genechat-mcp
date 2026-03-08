"""Tests for the genechat CLI (all 7 subcommands)."""

import importlib.resources as _real_resources
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from genechat.cli import (
    _ensure_lookup_db,
    _patch_db_path_for,
    _validate_vcf,
    main,
)
from genechat.config import AppConfig


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouting:
    def test_no_subcommand_invokes_serve(self, monkeypatch):
        called = []
        monkeypatch.setattr("genechat.cli._run_serve", lambda: called.append(True))
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
        config = AppConfig()
        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), config)
        assert result == Path("/data/sample.patch.db")

    def test_from_config(self):
        config = AppConfig(genome={"patch_db": "/custom/path.db"})
        result = _patch_db_path_for(Path("/data/sample.vcf.gz"), config)
        assert result == Path("/custom/path.db")


# ---------------------------------------------------------------------------
# genechat add
# ---------------------------------------------------------------------------


class TestAdd:
    def test_add_missing_vcf(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["add", "/nonexistent/file.vcf.gz"])
        assert exc_info.value.code == 1
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
        assert "VCF registered" in capsys.readouterr().out

        # Check permissions (owner read/write only)
        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600


# ---------------------------------------------------------------------------
# genechat init
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_missing_vcf(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "/nonexistent/file.vcf.gz"])
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().err

    def test_init_full_pipeline(self, tmp_path, capsys, monkeypatch):
        """init runs: validate -> config -> lookup_db -> download -> print MCP config."""
        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")
        (tmp_path / "test.vcf.gz.tbi").write_bytes(b"fake")

        config_dir = tmp_path / "config"
        monkeypatch.setattr(
            "genechat.cli.user_config_dir", lambda _app: str(config_dir)
        )
        _mock_pysam_ok(monkeypatch)

        monkeypatch.setattr("genechat.cli._ensure_lookup_db", lambda: True)
        monkeypatch.setattr(
            "genechat.download.download_clinvar", lambda **kw: Path("x")
        )
        monkeypatch.setattr(
            "genechat.download.download_snpeff_db", lambda: "GRCh38.p14"
        )
        # Skip annotation by making snpeff_installed return False
        monkeypatch.setattr("genechat.download.snpeff_installed", lambda: False)
        monkeypatch.setattr("genechat.download.clinvar_installed", lambda: True)

        main(["init", str(vcf)])

        out = capsys.readouterr().out
        assert "GeneChat Setup" in out
        assert "mcpServers" in out
        assert (config_dir / "config.toml").exists()

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
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# genechat download
# ---------------------------------------------------------------------------


def _mock_downloads(monkeypatch):
    """Mock all download functions, return list of call names."""
    calls = []
    monkeypatch.setattr(
        "genechat.download.download_clinvar",
        lambda **kw: calls.append("clinvar") or Path("x"),
    )
    monkeypatch.setattr(
        "genechat.download.download_snpeff_db",
        lambda: calls.append("snpeff") or "GRCh38.p14",
    )
    monkeypatch.setattr(
        "genechat.download.download_gnomad",
        lambda **kw: calls.append("gnomad") or Path("x"),
    )
    monkeypatch.setattr(
        "genechat.download.download_dbsnp",
        lambda **kw: calls.append("dbsnp"),
    )
    monkeypatch.setattr("genechat.download.references_dir", lambda: Path("/tmp/refs"))
    return calls


class TestDownload:
    def test_default_downloads_clinvar_snpeff(self, monkeypatch, capsys):
        calls = _mock_downloads(monkeypatch)
        main(["download"])
        assert "clinvar" in calls
        assert "snpeff" in calls
        assert "gnomad" not in calls
        assert "dbsnp" not in calls

    def test_gnomad_flag_only(self, monkeypatch, capsys):
        """--gnomad alone downloads only gnomAD (not ClinVar/SnpEff)."""
        calls = _mock_downloads(monkeypatch)
        main(["download", "--gnomad"])
        assert "gnomad" in calls
        assert "clinvar" not in calls

    def test_all_flag(self, monkeypatch, capsys):
        calls = _mock_downloads(monkeypatch)
        main(["download", "--all"])
        assert set(calls) == {"clinvar", "snpeff", "gnomad", "dbsnp"}

    def test_dbsnp_flag_only(self, monkeypatch, capsys):
        """--dbsnp alone downloads only dbSNP (not ClinVar/SnpEff)."""
        calls = _mock_downloads(monkeypatch)
        main(["download", "--dbsnp"])
        assert "dbsnp" in calls
        assert "clinvar" not in calls


# ---------------------------------------------------------------------------
# genechat annotate
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_no_vcf_registered(self, monkeypatch, capsys):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        with pytest.raises(SystemExit) as exc_info:
            main(["annotate"])
        assert exc_info.value.code == 1
        assert "No VCF registered" in capsys.readouterr().err

    def test_shows_status_no_flags(self, tmp_path, monkeypatch, capsys):
        """annotate with no flags + existing patch.db shows annotation status."""
        from genechat.patch import PatchDB

        patch_path = tmp_path / "test.patch.db"
        patch = PatchDB.create(patch_path)
        patch.set_metadata("snpeff", "GRCh38.p14", status="complete")
        patch.close()

        vcf = tmp_path / "test.vcf.gz"
        vcf.write_bytes(b"fake")

        config = AppConfig(genome={"vcf_path": str(vcf), "patch_db": str(patch_path)})
        monkeypatch.setattr("genechat.cli.load_config", lambda: config)
        main(["annotate"])

        out = capsys.readouterr().out
        assert "snpeff" in out
        assert "GRCh38.p14" in out

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

        config = AppConfig(genome={"vcf_path": str(vcf)})
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
        assert "test" in out
        assert "exists" in out
        assert "Patch DB: not built" in out
        assert "dbSNP" in out


# ---------------------------------------------------------------------------
# genechat update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_prints_version_table(self, monkeypatch, capsys):
        monkeypatch.setattr("genechat.cli.load_config", lambda: AppConfig())
        monkeypatch.setattr("genechat.update.check_clinvar_version", lambda: None)

        main(["update"])

        out = capsys.readouterr().out
        assert "Source" in out
        assert "clinvar" in out


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
