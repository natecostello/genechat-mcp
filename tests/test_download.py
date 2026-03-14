"""Tests for genechat.download (reference database management)."""

from genechat.download import (
    GNOMAD_CHROMS,
    _write_refseq_chr_map,
    clinvar_installed,
    clinvar_path,
    clinvar_tbi_path,
    dbsnp_dir,
    dbsnp_installed,
    dbsnp_path,
    dbsnp_raw_path,
    delete_gnomad_chr,
    download_clinvar,
    download_dbsnp,
    download_gnomad_chr,
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

    def test_detects_4_3_from_stderr(self, monkeypatch):
        import subprocess

        def mock_run(*a, **kw):
            r = subprocess.CompletedProcess(a, 0)
            r.stdout = ""
            r.stderr = "SnpEff\t4.3t\t2017-11-24\n"
            return r

        monkeypatch.setattr("subprocess.run", mock_run)
        assert _detect_snpeff_db() == "GRCh38.86"

    def test_detects_4_3_from_stdout(self, monkeypatch):
        import subprocess

        def mock_run(*a, **kw):
            r = subprocess.CompletedProcess(a, 0)
            r.stdout = "SnpEff\t4.3t\t2017-11-24\n"
            r.stderr = ""
            return r

        monkeypatch.setattr("subprocess.run", mock_run)
        assert _detect_snpeff_db() == "GRCh38.86"


class TestDbsnpPaths:
    def test_dbsnp_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        d = dbsnp_dir()
        assert d == tmp_path / "refs" / "dbsnp"

    def test_dbsnp_raw_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert dbsnp_raw_path().name == "GCF_000001405.40.gz"

    def test_dbsnp_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert dbsnp_path().name == "dbsnp_chrfixed.vcf.gz"


class TestDbsnpInstalled:
    def test_false_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        assert dbsnp_installed() is False

    def test_false_when_no_tbi(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        (ddir / "dbsnp_chrfixed.vcf.gz").write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert dbsnp_installed() is False

    def test_true_when_both_exist(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        (ddir / "dbsnp_chrfixed.vcf.gz").write_bytes(b"fake")
        (ddir / "dbsnp_chrfixed.vcf.gz.tbi").write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        assert dbsnp_installed() is True


class TestDbsnpDownload:
    def test_skips_when_existing(self, monkeypatch, tmp_path, capsys):
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        (ddir / "dbsnp_chrfixed.vcf.gz").write_bytes(b"fake")
        (ddir / "dbsnp_chrfixed.vcf.gz.tbi").write_bytes(b"fake")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        # Ensure test is hermetic even without bcftools/tabix on PATH
        monkeypatch.setattr("shutil.which", lambda name: None)

        result = download_dbsnp()
        assert result == ddir / "dbsnp_chrfixed.vcf.gz"
        assert "already downloaded" in capsys.readouterr().out

    def test_fails_without_bcftools(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        monkeypatch.setattr("shutil.which", lambda name: None)

        result = download_dbsnp()
        assert result is None
        assert "bcftools not found" in capsys.readouterr().err

    def test_fails_without_tabix(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/usr/bin/bcftools" if name == "bcftools" else None,
        )

        result = download_dbsnp()
        assert result is None
        assert "tabix not found" in capsys.readouterr().err

    def test_calls_bcftools_rename_and_tabix(self, monkeypatch, tmp_path, capsys):
        """Verify bcftools annotate --rename-chrs and tabix are called correctly."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Pre-create raw dbSNP files so download is skipped
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        raw = ddir / "GCF_000001405.40.gz"
        raw.write_bytes(b"fake-vcf")
        raw.with_suffix(raw.suffix + ".tbi").write_bytes(b"fake-tbi")

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            from pathlib import Path as P

            # For bcftools annotate, create the output file
            if "annotate" in cmd and "-o" in cmd:
                out_idx = cmd.index("-o") + 1
                P(cmd[out_idx]).write_bytes(b"renamed")
            # For tabix, create the .tbi index file
            if "tabix" in cmd[0]:
                vcf_arg = cmd[-1]
                P(vcf_arg + ".tbi").write_bytes(b"fake-tbi")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        # Mock download_file to avoid network
        monkeypatch.setattr(
            "genechat.download.download_file", lambda url, dest, label="": None
        )

        result = download_dbsnp()
        assert result is not None

        # Verify bcftools was called with --rename-chrs
        bcf_call = [c for c in calls if "bcftools" in c[0] and "--rename-chrs" in c]
        assert len(bcf_call) == 1
        assert "-Oz" in bcf_call[0]

        # Verify tabix was called
        tabix_call = [c for c in calls if "tabix" in c[0]]
        assert len(tabix_call) == 1
        assert "-p" in tabix_call[0]
        assert "vcf" in tabix_call[0]

    def test_file_based_deletes_raw_after_rename(self, monkeypatch, tmp_path, capsys):
        """Verify raw dbSNP files are deleted after successful file-based rename."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Pre-create raw dbSNP files
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        raw = ddir / "GCF_000001405.40.gz"
        raw.write_bytes(b"fake-vcf-data")
        raw_tbi = raw.with_suffix(raw.suffix + ".tbi")
        raw_tbi.write_bytes(b"fake-tbi")

        def mock_run(cmd, **kwargs):
            from pathlib import Path as P

            if "annotate" in cmd and "-o" in cmd:
                out_idx = cmd.index("-o") + 1
                P(cmd[out_idx]).write_bytes(b"renamed")
            if "tabix" in cmd[0]:
                vcf_arg = cmd[-1]
                P(vcf_arg + ".tbi").write_bytes(b"fake-tbi")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr(
            "genechat.download.download_file", lambda url, dest, label="": None
        )

        result = download_dbsnp()
        assert result is not None
        # Raw files should have been cleaned up
        assert not raw.exists()
        assert not raw_tbi.exists()
        assert "freed" in capsys.readouterr().out

    def test_streaming_path_when_no_raw(self, monkeypatch, tmp_path, capsys):
        """Verify streaming path is used when raw dbSNP file doesn't exist."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        # No raw files — should trigger streaming path

        # Mock _stream_dbsnp_rename to create the output file
        def mock_stream(chr_map, output):
            output.write_bytes(b"streamed-output")

        monkeypatch.setattr("genechat.download._stream_dbsnp_rename", mock_stream)

        def mock_run(cmd, **kwargs):
            from pathlib import Path as P

            if "tabix" in cmd[0]:
                vcf_arg = cmd[-1]
                P(vcf_arg + ".tbi").write_bytes(b"fake-tbi")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = download_dbsnp()
        assert result is not None
        assert result.exists()

    def test_cleans_up_tmp_on_failure(self, monkeypatch, tmp_path, capsys):
        """Verify tmp file is cleaned up when bcftools fails."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Pre-create raw dbSNP files
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        raw = ddir / "GCF_000001405.40.gz"
        raw.write_bytes(b"fake-vcf")
        raw.with_suffix(raw.suffix + ".tbi").write_bytes(b"fake-tbi")

        def mock_run(cmd, **kwargs):
            if "annotate" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"bcf error")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr(
            "genechat.download.download_file", lambda url, dest, label="": None
        )

        result = download_dbsnp()
        assert result is None

        # Verify no tmp file left behind
        tmp_files = list(ddir.glob("*.tmp*"))
        assert len(tmp_files) == 0


class TestDownloadGnomadChr:
    def test_downloads_vcf_and_tbi(self, monkeypatch, tmp_path, capsys):
        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        downloaded = []

        def mock_download(url, dest, label=""):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake")
            downloaded.append(dest.name)

        monkeypatch.setattr("genechat.download.download_file", mock_download)

        result = download_gnomad_chr("1")
        assert result.exists()
        assert "gnomad.exomes.v4.1.sites.chr1.vcf.bgz" in downloaded
        assert "gnomad.exomes.v4.1.sites.chr1.vcf.bgz.tbi" in downloaded

    def test_skips_existing(self, monkeypatch, tmp_path, capsys):
        refs = tmp_path / "refs"
        gdir = refs / "gnomad_exomes_v4"
        gdir.mkdir(parents=True)
        (gdir / "gnomad.exomes.v4.1.sites.chr1.vcf.bgz").write_bytes(b"x")
        (gdir / "gnomad.exomes.v4.1.sites.chr1.vcf.bgz.tbi").write_bytes(b"x")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        downloaded = []
        monkeypatch.setattr(
            "genechat.download.download_file",
            lambda url, dest, label="": downloaded.append(dest.name),
        )

        download_gnomad_chr("1")
        assert len(downloaded) == 0
        assert "Already exists" in capsys.readouterr().out

    def test_redownloads_when_tbi_missing(self, monkeypatch, tmp_path):
        """VCF+TBI are an atomic pair; missing TBI triggers re-download of both."""
        refs = tmp_path / "refs"
        gdir = refs / "gnomad_exomes_v4"
        gdir.mkdir(parents=True)
        (gdir / "gnomad.exomes.v4.1.sites.chr1.vcf.bgz").write_bytes(b"x")
        # No .tbi file
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        downloaded = []

        def mock_download(url, dest, label=""):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake")
            downloaded.append(dest.name)

        monkeypatch.setattr("genechat.download.download_file", mock_download)

        download_gnomad_chr("1")
        assert "gnomad.exomes.v4.1.sites.chr1.vcf.bgz" in downloaded
        assert "gnomad.exomes.v4.1.sites.chr1.vcf.bgz.tbi" in downloaded


class TestDeleteGnomadChr:
    def test_deletes_vcf_and_tbi(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        gdir = refs / "gnomad_exomes_v4"
        gdir.mkdir(parents=True)
        vcf = gdir / "gnomad.exomes.v4.1.sites.chr1.vcf.bgz"
        tbi = gdir / "gnomad.exomes.v4.1.sites.chr1.vcf.bgz.tbi"
        vcf.write_bytes(b"x")
        tbi.write_bytes(b"x")
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        delete_gnomad_chr("1")
        assert not vcf.exists()
        assert not tbi.exists()

    def test_no_error_when_missing(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        refs.mkdir(parents=True)
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        # Should not raise
        delete_gnomad_chr("1")


class TestRefseqChrMap:
    def test_writes_all_chromosomes(self, tmp_path):
        mapfile = tmp_path / "map.txt"
        _write_refseq_chr_map(mapfile)

        lines = mapfile.read_text().strip().split("\n")
        assert len(lines) == 25  # 22 autosomes + X + Y + MT

        # Check first and last entries
        assert lines[0] == "NC_000001.11 chr1"
        assert any("NC_000023.11 chrX" in line for line in lines)
        assert any("NC_012920.1 chrMT" in line for line in lines)
