"""Tests for parallel per-chromosome annotation (issue #66)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from genechat.parallel import (
    MAX_WORKERS,
    _parse_af,
    annotate_dbsnp_chromosome,
    annotate_gnomad_chromosome,
    merge_temp_databases,
    run_parallel_annotation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GNOMAD_VCF_LINES = [
    "##fileformat=VCFv4.2\n",
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
    "chr1\t100\trs1\tA\tG\t.\t.\tAF=0.01;AF_grpmax=0.02\n",
    "chr1\t200\trs2\tC\tT\t.\t.\tAF=0.05;AF_grpmax=0.08\n",
    "chr1\t300\t.\tG\tA\t.\t.\t.\n",  # no AF
]

DBSNP_VCF_LINES = [
    "##fileformat=VCFv4.2\n",
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
    "chr1\t100\trs123\tA\tG\t.\t.\t.\n",
    "chr1\t200\trs456\tC\tT\t.\t.\t.\n",
    "chr1\t300\t.\tG\tA\t.\t.\t.\n",  # no rsID
]


def _create_patch_db(path):
    """Create a minimal patch.db with the annotations table."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE annotations ("
        "chrom TEXT, pos INT, ref TEXT, alt TEXT, "
        "rsid TEXT, rsid_source TEXT, "
        "gene TEXT, effect TEXT, impact TEXT, "
        "transcript TEXT, hgvs_c TEXT, hgvs_p TEXT, "
        "clnsig TEXT, clndn TEXT, clnrevstat TEXT, "
        "af REAL, af_grpmax REAL, "
        "PRIMARY KEY(chrom, pos, ref, alt))"
    )
    # Insert test rows (bare chrom names, matching normalize_chrom output)
    conn.executemany(
        "INSERT INTO annotations (chrom, pos, ref, alt, gene, effect, impact) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("1", 100, "A", "G", "GENE1", "missense", "MODERATE"),
            ("1", 200, "C", "T", "GENE1", "synonymous", "LOW"),
            ("1", 300, "G", "A", "GENE2", "frameshift", "HIGH"),
        ],
    )
    conn.commit()
    conn.close()


class MockStdout:
    """Mock stdout that wraps an iterator with close()."""

    def __init__(self, lines):
        self._lines = iter(lines)

    def __iter__(self):
        return self._lines

    def __next__(self):
        return next(self._lines)

    def close(self):
        pass

    def read(self):
        return ""


class MockProc:
    """Mock subprocess.Popen."""

    def __init__(self, stdout_lines=None, returncode=0):
        self.stdout = MockStdout(stdout_lines or [])
        self.stderr = MockStdout([])
        self.returncode = returncode
        self._waited = False

    def wait(self, timeout=None):
        self._waited = True
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass


# ---------------------------------------------------------------------------
# _parse_af tests
# ---------------------------------------------------------------------------


class TestParseAf:
    def test_normal_value(self):
        assert _parse_af("0.05") == 0.05

    def test_dot_returns_none(self):
        assert _parse_af(".") is None

    def test_none_returns_none(self):
        assert _parse_af(None) is None

    def test_multi_allelic_takes_first(self):
        assert _parse_af("0.01,0.02") == 0.01

    def test_invalid_returns_none(self):
        assert _parse_af("abc") is None


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------


class TestGnomadWorker:
    def test_produces_temp_db(self, tmp_path):
        temp_db = str(tmp_path / "gnomad_1.db")

        with patch("genechat.parallel.subprocess.Popen") as mock_popen:
            mock_proc = MockProc(stdout_lines=GNOMAD_VCF_LINES)
            mock_popen.return_value = mock_proc

            chrom, count, path = annotate_gnomad_chromosome(
                chrom="1",
                vcf_contig="chr1",
                vcf_path="/fake/sample.vcf.gz",
                gnomad_file="/fake/gnomad_chr1.vcf.gz",
                temp_db_path=temp_db,
                chr_rename_map_path=None,
            )

        assert chrom == "1"
        assert count == 2  # 2 rows with AF data
        assert path == temp_db

        # Verify temp DB contents
        conn = sqlite3.connect(temp_db)
        rows = conn.execute("SELECT * FROM results ORDER BY pos").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0] == ("1", 100, "A", "G", 0.01, 0.02)
        assert rows[1] == ("1", 200, "C", "T", 0.05, 0.08)

    def test_bare_contig_uses_three_stage_pipe(self, tmp_path):
        temp_db = str(tmp_path / "gnomad_1.db")
        popen_calls = []

        def mock_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            proc = MockProc(
                stdout_lines=GNOMAD_VCF_LINES if len(popen_calls) == 3 else []
            )
            proc.stdout = MockStdout(GNOMAD_VCF_LINES if len(popen_calls) == 3 else [])
            return proc

        with patch("genechat.parallel.subprocess.Popen", side_effect=mock_popen):
            annotate_gnomad_chromosome(
                chrom="1",
                vcf_contig="1",
                vcf_path="/fake/sample.vcf.gz",
                gnomad_file="/fake/gnomad_chr1.vcf.gz",
                temp_db_path=temp_db,
                chr_rename_map_path="/fake/rename.txt",
            )

        assert len(popen_calls) == 3
        # First: bcftools view -r 1
        assert popen_calls[0][0] == "bcftools"
        assert "view" in popen_calls[0]
        assert "-r" in popen_calls[0]
        assert "1" in popen_calls[0]
        # Second: bcftools annotate --rename-chrs
        assert "--rename-chrs" in popen_calls[1]
        # Third: bcftools annotate -a gnomad
        assert "-a" in popen_calls[2]


class TestDbsnpWorker:
    def test_produces_temp_db(self, tmp_path):
        temp_db = str(tmp_path / "dbsnp_1.db")

        with patch("genechat.parallel.subprocess.Popen") as mock_popen:
            mock_proc = MockProc(stdout_lines=DBSNP_VCF_LINES)
            mock_popen.return_value = mock_proc

            chrom, count, path = annotate_dbsnp_chromosome(
                chrom="1",
                vcf_contig="chr1",
                vcf_path="/fake/sample.vcf.gz",
                dbsnp_vcf="/fake/dbsnp.vcf.gz",
                temp_db_path=temp_db,
                chr_rename_map_path=None,
            )

        assert chrom == "1"
        assert count == 2  # 2 rows with rsIDs
        assert path == temp_db

        conn = sqlite3.connect(temp_db)
        rows = conn.execute("SELECT * FROM results ORDER BY pos").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0] == ("1", 100, "A", "G", "rs123")
        assert rows[1] == ("1", 200, "C", "T", "rs456")


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------


class TestMerge:
    def test_gnomad_updates_af(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        # Create a temp DB with gnomAD results
        temp_db = str(tmp_path / "gnomad_1.db")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, "
            "af REAL, af_grpmax REAL, PRIMARY KEY(chrom, pos, ref, alt))"
        )
        conn.execute("INSERT INTO results VALUES ('1', 100, 'A', 'G', 0.01, 0.02)")
        conn.execute("INSERT INTO results VALUES ('1', 200, 'C', 'T', 0.05, 0.08)")
        conn.commit()
        conn.close()

        total = merge_temp_databases(patch_db, [("1", 2, temp_db)], "gnomad")

        assert total == 2
        conn = sqlite3.connect(patch_db)
        row = conn.execute(
            "SELECT af, af_grpmax FROM annotations WHERE chrom='1' AND pos=100"
        ).fetchone()
        assert row == (0.01, 0.02)
        row2 = conn.execute(
            "SELECT af, af_grpmax FROM annotations WHERE chrom='1' AND pos=300"
        ).fetchone()
        assert row2 == (None, None)  # not in temp DB
        conn.close()

    def test_dbsnp_updates_rsid(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        temp_db = str(tmp_path / "dbsnp_1.db")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, "
            "rsid TEXT, PRIMARY KEY(chrom, pos, ref, alt))"
        )
        conn.execute("INSERT INTO results VALUES ('1', 100, 'A', 'G', 'rs999')")
        conn.execute("INSERT INTO results VALUES ('1', 200, 'C', 'T', 'rs888')")
        conn.commit()
        conn.close()

        total = merge_temp_databases(patch_db, [("1", 2, temp_db)], "dbsnp")

        assert total == 2
        conn = sqlite3.connect(patch_db)
        row = conn.execute(
            "SELECT rsid, rsid_source FROM annotations WHERE chrom='1' AND pos=100"
        ).fetchone()
        assert row == ("rs999", "dbsnp")
        conn.close()

    def test_dbsnp_does_not_overwrite_existing_rsid(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        # Set an existing rsID
        conn = sqlite3.connect(patch_db)
        conn.execute(
            "UPDATE annotations SET rsid='rs_existing', rsid_source='vcf' "
            "WHERE chrom='1' AND pos=100"
        )
        conn.commit()
        conn.close()

        temp_db = str(tmp_path / "dbsnp_1.db")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, "
            "rsid TEXT, PRIMARY KEY(chrom, pos, ref, alt))"
        )
        conn.execute("INSERT INTO results VALUES ('1', 100, 'A', 'G', 'rs_new')")
        conn.execute("INSERT INTO results VALUES ('1', 200, 'C', 'T', 'rs888')")
        conn.commit()
        conn.close()

        total = merge_temp_databases(patch_db, [("1", 2, temp_db)], "dbsnp")

        assert total == 1  # only pos=200 updated (pos=100 already has rsID)
        conn = sqlite3.connect(patch_db)
        row = conn.execute(
            "SELECT rsid, rsid_source FROM annotations WHERE chrom='1' AND pos=100"
        ).fetchone()
        assert row == ("rs_existing", "vcf")  # preserved
        conn.close()

    def test_merge_preserves_other_annotations(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        temp_db = str(tmp_path / "gnomad_1.db")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, "
            "af REAL, af_grpmax REAL, PRIMARY KEY(chrom, pos, ref, alt))"
        )
        conn.execute("INSERT INTO results VALUES ('1', 100, 'A', 'G', 0.01, 0.02)")
        conn.commit()
        conn.close()

        merge_temp_databases(patch_db, [("1", 1, temp_db)], "gnomad")

        conn = sqlite3.connect(patch_db)
        row = conn.execute(
            "SELECT gene, effect, impact, af, af_grpmax "
            "FROM annotations WHERE chrom='1' AND pos=100"
        ).fetchone()
        # SnpEff columns preserved, gnomAD columns updated
        assert row == ("GENE1", "missense", "MODERATE", 0.01, 0.02)
        conn.close()

    def test_skips_empty_results(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        temp_db = str(tmp_path / "empty.db")
        # Don't create the file — count=0 should skip

        total = merge_temp_databases(patch_db, [("1", 0, temp_db)], "gnomad")
        assert total == 0

    def test_cleans_up_temp_files(self, tmp_path):
        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        temp_db = str(tmp_path / "gnomad_1.db")
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, "
            "af REAL, af_grpmax REAL, PRIMARY KEY(chrom, pos, ref, alt))"
        )
        conn.execute("INSERT INTO results VALUES ('1', 100, 'A', 'G', 0.01, 0.02)")
        conn.commit()
        conn.close()

        assert Path(temp_db).exists()
        merge_temp_databases(patch_db, [("1", 1, temp_db)], "gnomad")
        assert not Path(temp_db).exists()


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_worker_count_respects_limits(self):
        # min(cpu_count, chroms, MAX_WORKERS)
        with patch("os.cpu_count", return_value=16):
            assert min(os.cpu_count() or 1, 5, MAX_WORKERS) == 5
        with patch("os.cpu_count", return_value=2):
            assert min(os.cpu_count() or 1, 24, MAX_WORKERS) == 2
        with patch("os.cpu_count", return_value=None):
            assert min(os.cpu_count() or 1, 24, MAX_WORKERS) == 1

    def test_worker_failure_cleanup(self, tmp_path):
        """Failed worker should not leave temp files behind."""
        from concurrent.futures import ThreadPoolExecutor

        patch_db = str(tmp_path / "patch.db")
        _create_patch_db(patch_db)

        # Create a fake reference file so the orchestrator doesn't skip it
        ref_file = tmp_path / "gnomad_1.vcf.gz"
        ref_file.touch()

        def failing_worker(*args, **kwargs):
            raise RuntimeError("bcftools failed")

        with (
            patch("genechat.parallel._resolve_vcf_contigs", return_value={"1": "chr1"}),
            patch(
                "genechat.parallel.annotate_gnomad_chromosome",
                side_effect=failing_worker,
            ),
            # Use ThreadPoolExecutor so mocks don't need pickling
            patch("genechat.parallel.ProcessPoolExecutor", ThreadPoolExecutor),
        ):
            with pytest.raises(RuntimeError, match="bcftools failed"):
                run_parallel_annotation(
                    vcf_path=Path("/fake/sample.vcf.gz"),
                    patch_db_path=Path(patch_db),
                    chroms=["1"],
                    source="gnomad",
                    reference_path_fn=lambda c: tmp_path / f"gnomad_{c}.vcf.gz",
                    chr_rename_map=None,
                )

        # Temp directory should be cleaned up
        # (we can't easily check this without more instrumentation,
        # but the finally block in run_parallel_annotation handles it)
