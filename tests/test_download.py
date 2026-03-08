"""Tests for genechat.download (reference database management)."""

from genechat.download import (
    GNOMAD_CHROMS,
    clinvar_installed,
    clinvar_path,
    clinvar_tbi_path,
    download_clinvar,
    gnomad_installed,
    references_dir,
    snpeff_installed,
    _detect_snpeff_db,
)


class TestPaths:
    def test_references_dir_creates_directory(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        result = references_dir()
        assert result.exists()
        assert result == tmp_path / "refs"

    def test_clinvar_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert clinvar_path().name == "clinvar.vcf.gz"

    def test_clinvar_tbi_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert clinvar_tbi_path().name == "clinvar.vcf.gz.tbi"


class TestInstalled:
    def test_clinvar_installed_true(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        refs.mkdir()
        (refs / "clinvar.vcf.gz").write_bytes(b"fake")
        (refs / "clinvar.vcf.gz.tbi").write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert clinvar_installed() is True

    def test_clinvar_installed_false(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        refs.mkdir()
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert clinvar_installed() is False

    def test_gnomad_installed_false(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert gnomad_installed() is False

    def test_gnomad_installed_true(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        gdir = refs / "gnomad_exomes_v4"
        gdir.mkdir(parents=True)
        for c in GNOMAD_CHROMS:
            (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz").write_bytes(b"x")
            (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz.tbi").write_bytes(b"x")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert gnomad_installed() is True

    def test_gnomad_installed_missing_tbi(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        gdir = refs / "gnomad_exomes_v4"
        gdir.mkdir(parents=True)
        for c in GNOMAD_CHROMS:
            (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz").write_bytes(b"x")
        # No .tbi files
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert gnomad_installed() is False

    def test_snpeff_installed(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/snpEff")
        assert snpeff_installed() is True

    def test_snpeff_not_installed(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        assert snpeff_installed() is False


class TestDownloadClinvar:
    def test_skips_when_existing(self, monkeypatch, tmp_path, capsys):
        refs = tmp_path / "refs"
        refs.mkdir()
        (refs / "clinvar.vcf.gz").write_bytes(b"fake")
        (refs / "clinvar.vcf.gz.tbi").write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        result = download_clinvar()
        assert result == refs / "clinvar.vcf.gz"
        assert "already downloaded" in capsys.readouterr().out


class TestDetectSnpeffDb:
    def test_default_when_not_installed(self, monkeypatch):
        def fail_run(*a, **kw):
            raise OSError("not found")

        monkeypatch.setattr("subprocess.run", fail_run)
        assert _detect_snpeff_db() == "GRCh38.p14"
