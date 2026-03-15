"""Parallel per-chromosome annotation for --fast mode.

Parallelizes gnomAD and dbSNP annotation across chromosomes using
ProcessPoolExecutor and per-chromosome temp SQLite databases.
See ADR-0010 and docs/plans/parallel-annotation.md for design.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from genechat.patch import parse_vcf_stream

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_WORKERS = 8


# ---------------------------------------------------------------------------
# Worker functions (top-level for pickling)
# ---------------------------------------------------------------------------


def annotate_gnomad_chromosome(
    chrom: str,
    vcf_contig: str,
    vcf_path: str,
    gnomad_file: str,
    temp_db_path: str,
    chr_rename_map_path: str | None,
) -> tuple[str, int, str]:
    """Annotate a single chromosome with gnomAD and write results to temp DB.

    Returns (chrom, row_count, temp_db_path).
    """
    conn = sqlite3.connect(temp_db_path)
    conn.execute(
        "CREATE TABLE results ("
        "chrom TEXT, pos INT, ref TEXT, alt TEXT, "
        "af REAL, af_grpmax REAL, "
        "PRIMARY KEY(chrom, pos, ref, alt))"
    )

    if chr_rename_map_path:
        # bare-contig VCF: view -r {bare} | rename bare→chr | annotate
        view_proc = subprocess.Popen(
            ["bcftools", "view", "-r", vcf_contig, vcf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        rename_proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "--rename-chrs",
                chr_rename_map_path,
                "-",
            ],
            stdin=view_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        view_proc.stdout.close()
        proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "-a",
                gnomad_file,
                "-c",
                "INFO/AF,INFO/AF_grpmax",
                "-",
            ],
            stdin=rename_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        rename_proc.stdout.close()
    else:
        # chr-prefixed VCF: annotate directly with region filter
        view_proc = None
        rename_proc = None
        proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "-a",
                gnomad_file,
                "-c",
                "INFO/AF,INFO/AF_grpmax",
                "-r",
                vcf_contig,
                vcf_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    try:
        count = _parse_gnomad_to_db(conn, proc)
        rc = proc.wait()
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"bcftools annotate (gnomAD) failed on chr{chrom}: {stderr}"
            )
        if rename_proc:
            rename_rc = rename_proc.wait()
            if rename_rc != 0:
                raise RuntimeError(
                    f"bcftools annotate --rename-chrs failed with "
                    f"exit code {rename_rc} on chr{chrom}"
                )
        if view_proc:
            view_rc = view_proc.wait()
            if view_rc != 0:
                raise RuntimeError(
                    f"bcftools view failed with exit code {view_rc} on chr{chrom}"
                )
    except Exception:
        _cleanup_procs(proc, rename_proc, view_proc)
        conn.close()
        raise
    finally:
        if proc.stdout is not None:
            proc.stdout.close()

    conn.commit()
    conn.close()
    return (chrom, count, temp_db_path)


def annotate_dbsnp_chromosome(
    chrom: str,
    vcf_contig: str,
    vcf_path: str,
    dbsnp_vcf: str,
    temp_db_path: str,
    chr_rename_map_path: str | None,
) -> tuple[str, int, str]:
    """Annotate a single chromosome with dbSNP and write results to temp DB.

    Returns (chrom, row_count, temp_db_path).
    """
    conn = sqlite3.connect(temp_db_path)
    conn.execute(
        "CREATE TABLE results ("
        "chrom TEXT, pos INT, ref TEXT, alt TEXT, "
        "rsid TEXT, "
        "PRIMARY KEY(chrom, pos, ref, alt))"
    )

    if chr_rename_map_path:
        view_proc = subprocess.Popen(
            ["bcftools", "view", "-r", vcf_contig, vcf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        rename_proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "--rename-chrs",
                chr_rename_map_path,
                "-",
            ],
            stdin=view_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        view_proc.stdout.close()
        proc = subprocess.Popen(
            ["bcftools", "annotate", "-a", dbsnp_vcf, "-c", "ID", "-"],
            stdin=rename_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        rename_proc.stdout.close()
    else:
        view_proc = None
        rename_proc = None
        proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "-a",
                dbsnp_vcf,
                "-c",
                "ID",
                "-r",
                vcf_contig,
                vcf_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    try:
        count = _parse_dbsnp_to_db(conn, proc)
        rc = proc.wait()
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"bcftools annotate (dbSNP) failed on chr{chrom}: {stderr}"
            )
        if rename_proc:
            rename_rc = rename_proc.wait()
            if rename_rc != 0:
                raise RuntimeError(
                    f"bcftools annotate --rename-chrs failed with "
                    f"exit code {rename_rc} on chr{chrom}"
                )
        if view_proc:
            view_rc = view_proc.wait()
            if view_rc != 0:
                raise RuntimeError(
                    f"bcftools view failed with exit code {view_rc} on chr{chrom}"
                )
    except Exception:
        _cleanup_procs(proc, rename_proc, view_proc)
        conn.close()
        raise
    finally:
        if proc.stdout is not None:
            proc.stdout.close()

    conn.commit()
    conn.close()
    return (chrom, count, temp_db_path)


# ---------------------------------------------------------------------------
# VCF parsing helpers (used by workers)
# ---------------------------------------------------------------------------


def _parse_gnomad_to_db(conn: sqlite3.Connection, proc: subprocess.Popen) -> int:
    """Parse gnomAD-annotated VCF stream into temp DB results table."""
    count = 0
    batch: list[tuple] = []
    for record in parse_vcf_stream(iter(proc.stdout), ["AF", "AF_grpmax", "AF_popmax"]):
        af_str = record.get("AF")
        af_grpmax_str = record.get("AF_popmax") or record.get("AF_grpmax")
        if af_str is None and af_grpmax_str is None:
            continue
        af = _parse_af(af_str)
        af_grpmax = _parse_af(af_grpmax_str)
        if af is None and af_grpmax is None:
            continue
        batch.append(
            (
                record["chrom"],
                record["pos"],
                record["ref"],
                record["alt"],
                af,
                af_grpmax,
            )
        )
        if len(batch) >= 10_000:
            conn.executemany(
                "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?, ?)", batch
            )
            count += len(batch)
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?, ?)", batch
        )
        count += len(batch)
    return count


def _parse_dbsnp_to_db(conn: sqlite3.Connection, proc: subprocess.Popen) -> int:
    """Parse dbSNP-annotated VCF stream into temp DB results table."""
    count = 0
    batch: list[tuple] = []
    for record in parse_vcf_stream(iter(proc.stdout), []):
        rsid = record.get("rsid")
        if not rsid:
            continue
        batch.append(
            (
                record["chrom"],
                record["pos"],
                record["ref"],
                record["alt"],
                rsid,
            )
        )
        if len(batch) >= 10_000:
            conn.executemany(
                "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?)", batch
            )
            count += len(batch)
            batch.clear()
    if batch:
        conn.executemany("INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?)", batch)
        count += len(batch)
    return count


def _parse_af(value: str | None) -> float | None:
    """Parse an AF value, handling '.' and multi-allelic comma-separated."""
    if value is None or value == ".":
        return None
    try:
        # Multi-allelic: take first value
        if "," in value:
            value = value.split(",")[0]
        return float(value)
    except (ValueError, IndexError):
        return None


def _cleanup_procs(*procs: subprocess.Popen | None) -> None:
    """Terminate and reap subprocess(es) safely."""
    for p in procs:
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


# ---------------------------------------------------------------------------
# Merge function
# ---------------------------------------------------------------------------


def merge_temp_databases(
    patch_db_path: str,
    results: list[tuple[str, int, str]],
    layer: str,
) -> int:
    """Merge per-chromosome temp DBs into the main patch.db.

    Args:
        patch_db_path: Path to the main patch.db.
        results: List of (chrom, count, temp_db_path) from workers.
        layer: "gnomad" or "dbsnp".

    Returns total rows merged.
    """
    if layer not in ("gnomad", "dbsnp"):
        raise ValueError(f"Invalid layer {layer!r}, expected 'gnomad' or 'dbsnp'")

    conn = sqlite3.connect(patch_db_path)
    total = 0

    use_update_from = sqlite3.sqlite_version_info >= (3, 33, 0)

    for chrom, count, temp_path in results:
        if count == 0:
            Path(temp_path).unlink(missing_ok=True)
            continue

        conn.execute("ATTACH DATABASE ? AS tmpdb", (temp_path,))

        if layer == "gnomad":
            if use_update_from:
                cur = conn.execute(
                    "UPDATE annotations SET af = tmpdb.results.af, "
                    "af_grpmax = tmpdb.results.af_grpmax "
                    "FROM tmpdb.results "
                    "WHERE annotations.chrom = tmpdb.results.chrom "
                    "AND annotations.pos = tmpdb.results.pos "
                    "AND annotations.ref = tmpdb.results.ref "
                    "AND annotations.alt = tmpdb.results.alt"
                )
            else:
                cur = conn.execute(
                    "UPDATE annotations SET "
                    "af = (SELECT r.af FROM tmpdb.results r "
                    "  WHERE r.chrom = annotations.chrom AND r.pos = annotations.pos "
                    "  AND r.ref = annotations.ref AND r.alt = annotations.alt), "
                    "af_grpmax = (SELECT r.af_grpmax FROM tmpdb.results r "
                    "  WHERE r.chrom = annotations.chrom AND r.pos = annotations.pos "
                    "  AND r.ref = annotations.ref AND r.alt = annotations.alt) "
                    "WHERE EXISTS (SELECT 1 FROM tmpdb.results r "
                    "  WHERE r.chrom = annotations.chrom AND r.pos = annotations.pos "
                    "  AND r.ref = annotations.ref AND r.alt = annotations.alt)"
                )
            total += cur.rowcount

        elif layer == "dbsnp":
            if use_update_from:
                cur = conn.execute(
                    "UPDATE annotations SET rsid = tmpdb.results.rsid, "
                    "rsid_source = 'dbsnp' "
                    "FROM tmpdb.results "
                    "WHERE annotations.chrom = tmpdb.results.chrom "
                    "AND annotations.pos = tmpdb.results.pos "
                    "AND annotations.ref = tmpdb.results.ref "
                    "AND annotations.alt = tmpdb.results.alt "
                    "AND annotations.rsid IS NULL"
                )
            else:
                cur = conn.execute(
                    "UPDATE annotations SET "
                    "rsid = (SELECT r.rsid FROM tmpdb.results r "
                    "  WHERE r.chrom = annotations.chrom AND r.pos = annotations.pos "
                    "  AND r.ref = annotations.ref AND r.alt = annotations.alt), "
                    "rsid_source = 'dbsnp' "
                    "WHERE annotations.rsid IS NULL "
                    "AND EXISTS (SELECT 1 FROM tmpdb.results r "
                    "  WHERE r.chrom = annotations.chrom AND r.pos = annotations.pos "
                    "  AND r.ref = annotations.ref AND r.alt = annotations.alt)"
                )
            total += cur.rowcount

        conn.commit()
        conn.execute("DETACH DATABASE tmpdb")
        Path(temp_path).unlink(missing_ok=True)

    conn.close()
    return total


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _resolve_vcf_contigs(
    vcf_path: str, chroms: list[str], bare: bool
) -> dict[str, str]:
    """Build chrom → vcf_contig_name map by inspecting VCF header.

    For bare-contig VCFs, maps chrom "1" → "1", "MT" → "MT".
    For chr-prefixed VCFs, maps chrom "1" → "chr1", "MT" → "chrM" or "chrMT"
    depending on what's in the header.
    """
    import pysam

    with pysam.VariantFile(vcf_path) as vf:
        header_contigs = set(vf.header.contigs)

    mapping = {}
    for chrom in chroms:
        if bare:
            # Bare contig: check exact match only.
            # Do NOT map MT→M: the rename map only covers MT→chrMT,
            # so using "M" here would leave the contig un-renamed and
            # silently miss mitochondrial annotations.
            if chrom in header_contigs:
                mapping[chrom] = chrom
        else:
            # Chr-prefixed: try chrN, also chrM vs chrMT
            chr_name = f"chr{chrom}"
            if chr_name in header_contigs:
                mapping[chrom] = chr_name
            elif chrom == "MT":
                # Try chrM (common) and chrMT (dbSNP convention)
                if "chrM" in header_contigs:
                    mapping[chrom] = "chrM"
                elif "chrMT" in header_contigs:
                    mapping[chrom] = "chrMT"
    return mapping


def run_parallel_annotation(
    vcf_path: Path,
    patch_db_path: Path,
    chroms: list[str],
    source: str,
    reference_path_fn: Callable[[str], Path],
    chr_rename_map: Path | None = None,
    progress_callback: Callable[[str, int, int, int], None] | None = None,
) -> int:
    """Run parallel per-chromosome annotation.

    Args:
        vcf_path: Path to the user's VCF file.
        patch_db_path: Path to the main patch.db.
        chroms: List of chromosome names to process (bare form, e.g. ["1", "2", ..., "X"]).
        source: "gnomad" or "dbsnp".
        reference_path_fn: Function that returns the reference file path for a chrom.
        chr_rename_map: Path to contig rename map file (if bare-contig VCF).
        progress_callback: Called with (chrom, row_count, completed, total).

    Returns total rows merged into patch.db.
    """
    if source not in ("gnomad", "dbsnp"):
        raise ValueError(f"Invalid source {source!r}, expected 'gnomad' or 'dbsnp'")

    bare = chr_rename_map is not None
    contig_map = _resolve_vcf_contigs(str(vcf_path), chroms, bare)

    # Filter to chroms that exist in the VCF
    available_chroms = [c for c in chroms if c in contig_map]
    if not available_chroms:
        return 0

    worker_count = min(os.cpu_count() or 1, len(available_chroms), MAX_WORKERS)

    tmp_dir = tempfile.mkdtemp(prefix="genechat_parallel_")

    worker_fn = (
        annotate_gnomad_chromosome if source == "gnomad" else annotate_dbsnp_chromosome
    )

    futures = {}
    try:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            for chrom in available_chroms:
                ref_path = reference_path_fn(chrom)
                if not ref_path.exists():
                    continue
                temp_db = os.path.join(tmp_dir, f"{source}_{chrom}.db")
                vcf_contig = contig_map[chrom]

                future = executor.submit(
                    worker_fn,
                    chrom,
                    vcf_contig,
                    str(vcf_path),
                    str(ref_path),
                    temp_db,
                    str(chr_rename_map) if chr_rename_map else None,
                )
                futures[future] = chrom

            # total_chroms from actually submitted futures, not available_chroms
            total_chroms = len(futures)
            completed = 0
            results = []
            for future in as_completed(futures):
                chrom_name = futures[future]
                result = future.result()  # raises if worker failed
                results.append(result)
                completed += 1
                if progress_callback:
                    progress_callback(chrom_name, result[1], completed, total_chroms)

        # Merge all temp DBs into main patch.db
        total_rows = merge_temp_databases(str(patch_db_path), results, source)
        return total_rows
    finally:
        # Clean up temp directory (temp files already deleted by merge)
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
