"""Tests for genechat.download (reference database management)."""

from genechat.download import (
    DBSNP_CONTIGS,
    GNOMAD_CHROMS,
    _concat_dbsnp_chromosomes,
    _dbsnp_state_path,
    _download_dbsnp_chromosome,
    _load_dbsnp_state,
    _save_dbsnp_state,
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


class TestDbsnpState:
    def test_load_empty_when_no_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", tmp_path / "refs")
        (tmp_path / "refs" / "dbsnp").mkdir(parents=True)
        assert _load_dbsnp_state() == {}

    def test_save_and_load_roundtrip(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        (refs / "dbsnp").mkdir(parents=True)
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        state = {"completed_contigs": ["NC_000001.11", "NC_000002.12"]}
        _save_dbsnp_state(state)
        loaded = _load_dbsnp_state()
        assert loaded == state

    def test_load_returns_empty_on_corrupt_json(self, monkeypatch, tmp_path):
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)

        (ddir / "dbsnp_progress.json").write_text("not valid json{{{")
        assert _load_dbsnp_state() == {}


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

    def test_per_chromosome_pipeline(self, monkeypatch, tmp_path, capsys):
        """Verify per-chromosome download, concat, and cleanup."""
        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        # Use only 2 contigs for speed
        monkeypatch.setattr(
            "genechat.download.DBSNP_CONTIGS",
            [("NC_000021.9", "chr21"), ("NC_000022.11", "chr22")],
        )

        def mock_dl_chrom(refseq, chrom, remote_url, chr_map, output):
            output.write_bytes(f"fake-{chrom}".encode())

        monkeypatch.setattr(
            "genechat.download._download_dbsnp_chromosome", mock_dl_chrom
        )

        def mock_concat(chr_files, output):
            output.write_bytes(b"concatenated")
            output.with_name(f"{output.name}.tbi").write_bytes(b"tbi")

        monkeypatch.setattr("genechat.download._concat_dbsnp_chromosomes", mock_concat)

        result = download_dbsnp()
        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"concatenated"

        # State file should be cleaned up
        assert not _dbsnp_state_path().exists()
        # Per-chromosome dir should be cleaned up
        assert not (refs / "dbsnp" / "per_chrom").exists()

    def test_resume_skips_completed(self, monkeypatch, tmp_path, capsys):
        """Verify completed chromosomes are skipped on resume."""
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        monkeypatch.setattr(
            "genechat.download.DBSNP_CONTIGS",
            [("NC_000021.9", "chr21"), ("NC_000022.11", "chr22")],
        )

        # Pre-create state with chr21 already complete
        chr_dir = ddir / "per_chrom"
        chr_dir.mkdir()
        (chr_dir / "dbsnp_chr21.vcf.gz").write_bytes(b"done-chr21")
        _save_dbsnp_state({"completed_contigs": ["NC_000021.9"]})

        downloaded = []

        def mock_dl_chrom(refseq, chrom, remote_url, chr_map, output):
            downloaded.append(chrom)
            output.write_bytes(f"fake-{chrom}".encode())

        monkeypatch.setattr(
            "genechat.download._download_dbsnp_chromosome", mock_dl_chrom
        )

        def mock_concat(chr_files, output):
            output.write_bytes(b"concatenated")
            output.with_name(f"{output.name}.tbi").write_bytes(b"tbi")

        monkeypatch.setattr("genechat.download._concat_dbsnp_chromosomes", mock_concat)

        result = download_dbsnp()
        assert result is not None
        # Only chr22 should have been downloaded
        assert downloaded == ["chr22"]
        out = capsys.readouterr().out
        assert "skipping" in out
        assert "Resuming" in out

    def test_force_ignores_state(self, monkeypatch, tmp_path, capsys):
        """Verify --force re-downloads all chromosomes."""
        refs = tmp_path / "refs"
        ddir = refs / "dbsnp"
        ddir.mkdir(parents=True)
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        monkeypatch.setattr(
            "genechat.download.DBSNP_CONTIGS",
            [("NC_000021.9", "chr21"), ("NC_000022.11", "chr22")],
        )

        # Pre-create state — should be ignored with force=True
        _save_dbsnp_state({"completed_contigs": ["NC_000021.9"]})

        downloaded = []

        def mock_dl_chrom(refseq, chrom, remote_url, chr_map, output):
            downloaded.append(chrom)
            output.write_bytes(f"fake-{chrom}".encode())

        monkeypatch.setattr(
            "genechat.download._download_dbsnp_chromosome", mock_dl_chrom
        )

        def mock_concat(chr_files, output):
            output.write_bytes(b"concatenated")
            output.with_name(f"{output.name}.tbi").write_bytes(b"tbi")

        monkeypatch.setattr("genechat.download._concat_dbsnp_chromosomes", mock_concat)

        result = download_dbsnp(force=True)
        assert result is not None
        # Both should be downloaded
        assert "chr21" in downloaded
        assert "chr22" in downloaded

    def test_file_based_fallback_when_raw_exists(self, monkeypatch, tmp_path, capsys):
        """Verify legacy raw file triggers file-based rename path."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

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

        result = download_dbsnp()
        assert result is not None
        # Raw files should have been cleaned up
        assert not raw.exists()
        assert not raw_tbi.exists()

    def test_partial_failure_preserves_state(self, monkeypatch, tmp_path, capsys):
        """Verify state is preserved when a chromosome fails mid-way."""
        import subprocess

        refs = tmp_path / "refs"
        monkeypatch.setattr("genechat.download.REFERENCES_DIR", refs)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        monkeypatch.setattr(
            "genechat.download.DBSNP_CONTIGS",
            [
                ("NC_000021.9", "chr21"),
                ("NC_000022.11", "chr22"),
                ("NC_000023.11", "chrX"),
            ],
        )

        call_count = 0

        def mock_dl_chrom(refseq, chrom, remote_url, chr_map, output):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise subprocess.CalledProcessError(1, "bcftools", stderr=b"fail")
            output.write_bytes(f"fake-{chrom}".encode())

        monkeypatch.setattr(
            "genechat.download._download_dbsnp_chromosome", mock_dl_chrom
        )

        result = download_dbsnp()
        assert result is None

        # State should show chr21 as complete
        state = _load_dbsnp_state()
        assert "NC_000021.9" in state.get("completed_contigs", [])
        # chr22 failed, so should not be in completed
        assert "NC_000022.11" not in state.get("completed_contigs", [])


class TestDownloadDbsnpChromosome:
    def test_pipes_view_through_rename(self, monkeypatch, tmp_path):
        """Verify bcftools view | bcftools annotate pipeline."""
        import io

        popen_calls = []

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                popen_calls.append(cmd)
                self.cmd = cmd
                self.returncode = 0
                self.stderr = None

                if "view" in cmd:
                    self.stdout = io.BytesIO(b"fake-vcf-data")
                    # stderr=DEVNULL in real code, so no stderr pipe
                    self.stderr = None
                elif "annotate" in cmd:
                    if "-o" in cmd:
                        out_idx = cmd.index("-o") + 1
                        from pathlib import Path as P

                        P(cmd[out_idx]).write_bytes(b"renamed")
                    self.stdout = None
                    self.stderr = io.BytesIO(b"")

            def communicate(self):
                return b"", b""

            def wait(self):
                return self.returncode

        monkeypatch.setattr("subprocess.Popen", MockPopen)

        chr_map = tmp_path / "map.txt"
        chr_map.write_text("NC_000022.11 chr22\n")
        output = tmp_path / "chr22.vcf.gz"

        _download_dbsnp_chromosome(
            "NC_000022.11",
            "chr22",
            "https://example.com/dbsnp.gz",
            chr_map,
            output,
        )

        assert output.exists()
        # Verify both bcftools commands were called
        assert any("view" in cmd for cmd in popen_calls)
        assert any("annotate" in cmd for cmd in popen_calls)

    def test_cleans_up_tmp_on_failure(self, monkeypatch, tmp_path):
        """Verify tmp file is removed when pipeline fails."""
        import io
        import subprocess

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                self.cmd = cmd
                self.returncode = 1 if "view" in cmd else 0
                # view uses DEVNULL (no stderr pipe), rename has PIPE
                self.stderr = None if "view" in cmd else io.BytesIO(b"error")
                self.stdout = io.BytesIO(b"") if "view" in cmd else None

            def communicate(self):
                return b"", b""

            def wait(self):
                return self.returncode

            def poll(self):
                return self.returncode

            def kill(self):
                pass

        monkeypatch.setattr("subprocess.Popen", MockPopen)

        chr_map = tmp_path / "map.txt"
        chr_map.write_text("NC_000022.11 chr22\n")
        output = tmp_path / "chr22.vcf.gz"

        try:
            _download_dbsnp_chromosome(
                "NC_000022.11",
                "chr22",
                "https://example.com/dbsnp.gz",
                chr_map,
                output,
            )
        except subprocess.CalledProcessError:
            pass

        # No tmp file should remain
        assert not output.with_suffix(".tmp.vcf.gz").exists()


class TestConcatDbsnpChromosomes:
    def test_concat_and_index(self, monkeypatch, tmp_path):
        """Verify concat calls bcftools concat + tabix and creates output."""
        import subprocess

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            from pathlib import Path as P

            if "concat" in cmd and "-o" in cmd:
                out_idx = cmd.index("-o") + 1
                P(cmd[out_idx]).write_bytes(b"concatenated")
            if "tabix" in cmd[0]:
                P(cmd[-1] + ".tbi").write_bytes(b"tbi")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        chr_files = [tmp_path / "chr21.vcf.gz", tmp_path / "chr22.vcf.gz"]
        for f in chr_files:
            f.write_bytes(b"fake")

        output = tmp_path / "dbsnp_chrfixed.vcf.gz"
        _concat_dbsnp_chromosomes(chr_files, output)

        assert output.exists()
        assert output.with_name(f"{output.name}.tbi").exists()

        concat_call = [c for c in calls if "concat" in c]
        assert len(concat_call) == 1
        tabix_call = [c for c in calls if "tabix" in c[0]]
        assert len(tabix_call) == 1

    def test_cleans_up_on_failure(self, monkeypatch, tmp_path):
        """Verify tmp files are cleaned up when concat fails."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if "concat" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"error")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        chr_files = [tmp_path / "chr21.vcf.gz"]
        chr_files[0].write_bytes(b"fake")
        output = tmp_path / "dbsnp_chrfixed.vcf.gz"

        try:
            _concat_dbsnp_chromosomes(chr_files, output)
        except subprocess.CalledProcessError:
            pass

        assert not output.exists()
        tmp_files = list(tmp_path.glob("*.tmp*"))
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

    def test_uses_dbsnp_contigs_constant(self, tmp_path):
        """Verify _write_refseq_chr_map uses the DBSNP_CONTIGS constant."""
        mapfile = tmp_path / "map.txt"
        _write_refseq_chr_map(mapfile)

        lines = mapfile.read_text().strip().split("\n")
        assert len(lines) == len(DBSNP_CONTIGS)
        for line, (refseq, chrom) in zip(lines, DBSNP_CONTIGS):
            assert line == f"{refseq} {chrom}"
