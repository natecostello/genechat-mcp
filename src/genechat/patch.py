"""Patch database: SQLite-based annotation storage for raw VCFs.

Annotations (SnpEff, ClinVar, gnomAD, dbSNP) are stored in a SQLite database
keyed by (chrom, pos, ref, alt). At query time, VCFEngine joins raw VCF
genotypes with patch annotations.
"""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from genechat.parsers import parse_ann_field

SCHEMA = """\
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS annotations (
    chrom TEXT NOT NULL,
    pos INTEGER NOT NULL,
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    rsid TEXT,
    rsid_source TEXT,
    gene TEXT,
    effect TEXT,
    impact TEXT,
    transcript TEXT,
    hgvs_c TEXT,
    hgvs_p TEXT,
    clnsig TEXT,
    clndn TEXT,
    clnrevstat TEXT,
    af REAL,
    af_grpmax REAL,
    PRIMARY KEY (chrom, pos, ref, alt)
);

CREATE TABLE IF NOT EXISTS patch_metadata (
    source TEXT PRIMARY KEY,
    version TEXT,
    updated_at TEXT,
    status TEXT DEFAULT 'pending'
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_ann_rsid ON annotations(rsid) WHERE rsid IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_ann_clnsig ON annotations(clnsig) WHERE clnsig IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_ann_gene ON annotations(gene) WHERE gene IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_ann_pos ON annotations(chrom, pos)",
]


class PatchDB:
    """SQLite patch database for VCF annotations."""

    def __init__(self, db_path: Path, readonly: bool = False):
        self.db_path = db_path
        if readonly:
            self._conn = sqlite3.connect(
                f"file:{db_path}?mode=ro", uri=True, check_same_thread=False
            )
        else:
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    @classmethod
    def create(cls, db_path: Path) -> "PatchDB":
        """Create a new patch database with schema."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = cls(db_path)
        db._conn.executescript(SCHEMA)
        for idx in INDEXES:
            db._conn.execute(idx)
        db._conn.commit()
        # Restrict permissions — patch.db contains personal genomic annotations
        try:
            os.chmod(db_path, 0o600)
        except OSError:
            pass  # Best-effort on platforms that don't support chmod
        return db

    def close(self):
        self._conn.close()

    # -- Read methods (used by VCFEngine at query time) --

    def get_annotation(self, chrom: str, pos: int, ref: str, alt: str) -> dict | None:
        """Get annotation for a single variant."""
        row = self._conn.execute(
            "SELECT * FROM annotations WHERE chrom=? AND pos=? AND ref=? AND alt=?",
            (chrom, pos, ref, alt),
        ).fetchone()
        return dict(row) if row else None

    def get_annotations_in_region(
        self, chrom: str, start: int, end: int
    ) -> dict[tuple, dict]:
        """Get all annotations in a region, keyed by (pos, ref, alt)."""
        rows = self._conn.execute(
            "SELECT * FROM annotations WHERE chrom=? AND pos BETWEEN ? AND ?",
            (chrom, start, end),
        ).fetchall()
        return {(r["pos"], r["ref"], r["alt"]): dict(r) for r in rows}

    def lookup_rsid(self, rsid: str) -> list[dict]:
        """Look up variants by rsID using the index."""
        rows = self._conn.execute(
            "SELECT * FROM annotations WHERE rsid=?", (rsid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def lookup_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        """Look up multiple rsIDs in one query."""
        if not rsids:
            return {}
        placeholders = ",".join("?" for _ in rsids)
        rows = self._conn.execute(
            f"SELECT * FROM annotations WHERE rsid IN ({placeholders})", rsids
        ).fetchall()
        results: dict[str, list[dict]] = {r: [] for r in rsids}
        for row in rows:
            r = dict(row)
            if r["rsid"] in results:
                results[r["rsid"]].append(r)
        return results

    def query_clinvar(
        self,
        significance: str,
        chrom: str | None = None,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """Query variants by ClinVar significance substring (case-insensitive)."""
        if chrom and start is not None and end is not None:
            rows = self._conn.execute(
                "SELECT * FROM annotations "
                "WHERE clnsig IS NOT NULL "
                "AND instr(lower(clnsig), lower(?)) > 0 "
                "AND chrom=? AND pos BETWEEN ? AND ?",
                (significance, chrom, start, end),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM annotations "
                "WHERE clnsig IS NOT NULL "
                "AND instr(lower(clnsig), lower(?)) > 0",
                (significance,),
            ).fetchall()
        return [dict(r) for r in rows]

    def rsid_coverage(self, sample_size: int = 1000) -> tuple[int, int]:
        """Return (total, has_rsid) from a sample of annotations.

        Probes the annotations table to estimate what fraction of variants
        already have rsIDs. Used to decide whether dbSNP download is needed.
        Both counts are computed from the same sampled subset to avoid bias.
        """
        row = self._conn.execute(
            "SELECT "
            "  COUNT(*) AS total, "
            "  SUM(CASE WHEN rsid IS NOT NULL THEN 1 ELSE 0 END) AS has_rsid "
            "FROM (SELECT rsid FROM annotations LIMIT ?)",
            (sample_size,),
        ).fetchone()
        if not row:
            return (0, 0)
        total = row["total"] or 0
        if total == 0:
            return (0, 0)
        has_rsid = row["has_rsid"] or 0
        return (total, has_rsid)

    def get_metadata(self) -> dict[str, dict]:
        """Get all patch metadata entries."""
        rows = self._conn.execute(
            "SELECT source, version, updated_at, status FROM patch_metadata"
        ).fetchall()
        return {r["source"]: dict(r) for r in rows}

    def get_vcf_fingerprint(self) -> str | None:
        """Get stored VCF fingerprint."""
        row = self._conn.execute(
            "SELECT version FROM patch_metadata WHERE source='vcf_fingerprint'"
        ).fetchone()
        return row["version"] if row else None

    # -- Write methods (used during annotation) --

    def populate_from_snpeff_stream(self, stream: Iterator[str]) -> int:
        """Parse SnpEff-annotated VCF stream and upsert rows.

        Step 1: creates or updates ALL rows. Extracts ANN field + ID column.
        Uses UPSERT to preserve ClinVar/gnomAD/dbSNP columns on re-runs.
        Returns the number of rows processed.
        """
        count = 0
        batch = []
        for record in parse_vcf_stream(stream, ["ANN"]):
            ann_raw = record.get("ANN", "")
            ann = parse_ann_field(ann_raw) if ann_raw else {}
            rsid = record.get("rsid")
            batch.append(
                (
                    record["chrom"],
                    record["pos"],
                    record["ref"],
                    record["alt"],
                    rsid,
                    "vcf" if rsid else None,
                    ann.get("gene"),
                    ann.get("effect"),
                    ann.get("impact"),
                    ann.get("transcript"),
                    ann.get("hgvs_c"),
                    ann.get("hgvs_p"),
                )
            )
            if len(batch) >= 10_000:
                self._insert_snpeff_batch(batch)
                count += len(batch)
                batch.clear()
        if batch:
            self._insert_snpeff_batch(batch)
            count += len(batch)
        self._conn.commit()
        return count

    def _insert_snpeff_batch(self, batch: list[tuple]):
        self._conn.executemany(
            "INSERT INTO annotations "
            "(chrom, pos, ref, alt, rsid, rsid_source, "
            "gene, effect, impact, transcript, hgvs_c, hgvs_p) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(chrom, pos, ref, alt) DO UPDATE SET "
            "rsid=COALESCE(excluded.rsid, annotations.rsid), "
            "rsid_source=COALESCE(excluded.rsid_source, annotations.rsid_source), "
            "gene=excluded.gene, "
            "effect=excluded.effect, "
            "impact=excluded.impact, "
            "transcript=excluded.transcript, "
            "hgvs_c=excluded.hgvs_c, "
            "hgvs_p=excluded.hgvs_p",
            batch,
        )

    def update_clinvar_from_stream(self, stream: Iterator[str]) -> int:
        """Parse bcftools ClinVar-annotated VCF stream and UPDATE rows.

        Step 2: updates existing rows with ClinVar fields.
        Returns the number of rows updated.
        """
        count = 0
        batch = []
        for record in parse_vcf_stream(stream, ["CLNSIG", "CLNDN", "CLNREVSTAT"]):
            clnsig = record.get("CLNSIG")
            if not clnsig:
                continue
            batch.append(
                (
                    clnsig,
                    record.get("CLNDN"),
                    record.get("CLNREVSTAT"),
                    record["chrom"],
                    record["pos"],
                    record["ref"],
                    record["alt"],
                )
            )
            if len(batch) >= 10_000:
                count += self._update_clinvar_batch(batch)
                batch.clear()
        if batch:
            count += self._update_clinvar_batch(batch)
        self._conn.commit()
        return count

    def _update_clinvar_batch(self, batch: list[tuple]) -> int:
        before = self._conn.total_changes
        self._conn.executemany(
            "UPDATE annotations SET clnsig=?, clndn=?, clnrevstat=? "
            "WHERE chrom=? AND pos=? AND ref=? AND alt=?",
            batch,
        )
        return self._conn.total_changes - before

    def update_gnomad_from_stream(self, stream: Iterator[str]) -> int:
        """Parse bcftools gnomAD-annotated VCF stream and UPDATE rows.

        Step 3: updates existing rows with population frequency fields.
        Returns the number of rows updated.
        """
        count = 0
        batch = []
        for record in parse_vcf_stream(stream, ["AF", "AF_grpmax", "AF_popmax"]):
            af = record.get("AF")
            # Prefer AF_popmax, fall back to AF_grpmax (gnomAD v4 renamed it)
            af_grpmax = record.get("AF_popmax") or record.get("AF_grpmax")
            if af is None and af_grpmax is None:
                continue
            batch.append(
                (
                    float(af) if af else None,
                    float(af_grpmax) if af_grpmax else None,
                    record["chrom"],
                    record["pos"],
                    record["ref"],
                    record["alt"],
                )
            )
            if len(batch) >= 10_000:
                count += self._update_gnomad_batch(batch)
                batch.clear()
        if batch:
            count += self._update_gnomad_batch(batch)
        self._conn.commit()
        return count

    def _update_gnomad_batch(self, batch: list[tuple]) -> int:
        before = self._conn.total_changes
        self._conn.executemany(
            "UPDATE annotations SET af=?, af_grpmax=? "
            "WHERE chrom=? AND pos=? AND ref=? AND alt=?",
            batch,
        )
        return self._conn.total_changes - before

    def update_dbsnp_from_stream(self, stream: Iterator[str]) -> int:
        """Parse bcftools dbSNP-annotated VCF stream and UPDATE rsid where NULL.

        Step 4: backfills rsIDs from dbSNP for records missing an rsID.
        Returns the number of rows updated.
        """
        count = 0
        batch = []
        for record in parse_vcf_stream(stream, []):
            rsid = record.get("rsid")
            if not rsid:
                continue
            batch.append(
                (
                    rsid,
                    record["chrom"],
                    record["pos"],
                    record["ref"],
                    record["alt"],
                )
            )
            if len(batch) >= 10_000:
                count += self._update_dbsnp_batch(batch)
                batch.clear()
        if batch:
            count += self._update_dbsnp_batch(batch)
        self._conn.commit()
        return count

    def _update_dbsnp_batch(self, batch: list[tuple]) -> int:
        before = self._conn.total_changes
        self._conn.executemany(
            "UPDATE annotations SET rsid=?, rsid_source='dbsnp' "
            "WHERE chrom=? AND pos=? AND ref=? AND alt=? AND rsid IS NULL",
            batch,
        )
        return self._conn.total_changes - before

    def clear_layer(self, layer: str):
        """Clear annotation columns for a specific layer (for incremental updates)."""
        if layer == "snpeff":
            self._conn.execute(
                "UPDATE annotations SET gene=NULL, effect=NULL, impact=NULL, "
                "transcript=NULL, hgvs_c=NULL, hgvs_p=NULL"
            )
        elif layer == "clinvar":
            self._conn.execute(
                "UPDATE annotations SET clnsig=NULL, clndn=NULL, clnrevstat=NULL"
            )
        elif layer == "gnomad":
            self._conn.execute("UPDATE annotations SET af=NULL, af_grpmax=NULL")
        elif layer == "dbsnp":
            self._conn.execute(
                "UPDATE annotations SET rsid=NULL, rsid_source=NULL "
                "WHERE rsid_source='dbsnp'"
            )
        else:
            raise ValueError(f"Unsupported annotation layer: {layer!r}")
        self._conn.commit()

    def set_metadata(self, source: str, version: str, status: str = "complete"):
        """Set or update metadata for an annotation source."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._conn.execute(
            "INSERT OR REPLACE INTO patch_metadata (source, version, updated_at, status) "
            "VALUES (?, ?, ?, ?)",
            (source, version, now, status),
        )
        self._conn.commit()

    def store_vcf_fingerprint(self, vcf_path: Path):
        """Store VCF file identity for staleness detection."""
        stat = os.stat(vcf_path)
        fingerprint = f"{stat.st_size}:{stat.st_mtime_ns}"
        self.set_metadata("vcf_fingerprint", fingerprint)

    def check_vcf_fingerprint(self, vcf_path: Path) -> bool:
        """Check if VCF matches stored fingerprint. Returns True if match."""
        stored = self.get_vcf_fingerprint()
        if not stored:
            return True  # No fingerprint stored, assume OK
        stat = os.stat(vcf_path)
        current = f"{stat.st_size}:{stat.st_mtime_ns}"
        return stored == current


# -- VCF stream parser --


def parse_vcf_stream(
    stream: Iterator[str], extract_fields: list[str]
) -> Iterator[dict]:
    """Parse a VCF text stream, yielding dicts with (chrom, pos, ref, alt, rsid, {fields}).

    Skips header lines (starting with #).
    Extracts the ID column (rsid) and the requested INFO fields.
    """
    for line in stream:
        if line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t", 9)  # only split what we need
        if len(cols) < 8:
            continue
        chrom, pos_str, id_col, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
        info = cols[7]

        extracted: dict = {
            "chrom": chrom,
            "pos": int(pos_str),
            "ref": ref,
            "alt": alt,
        }
        if id_col != ".":
            extracted["rsid"] = id_col

        for field in extract_fields:
            value = _extract_info_field(info, field)
            if value is not None:
                extracted[field] = value

        yield extracted


def _extract_info_field(info: str, field: str) -> str | None:
    """Extract a specific INFO field value, avoiding substring collisions.

    Searches for the field preceded by ';' or at start of string,
    followed by '=', to prevent 'AF' matching 'AF_grpmax'.
    """
    target = f"{field}="
    # Check start of INFO string
    if info.startswith(target):
        start = len(target)
        end = info.find(";", start)
        return info[start:end] if end != -1 else info[start:]
    # Check after semicolons
    target = f";{field}="
    idx = info.find(target)
    if idx != -1:
        start = idx + len(target)
        end = info.find(";", start)
        return info[start:end] if end != -1 else info[start:]
    return None
