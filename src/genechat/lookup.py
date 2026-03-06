"""SQLite query layer for lookup tables."""

import sqlite3
from pathlib import Path

from genechat.config import AppConfig


class LookupDB:
    """Read-only access to the GeneChat lookup database."""

    def __init__(self, config: AppConfig):
        db_path = config.lookup_db_path
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Lookup database not found: {db_path}. "
                "Run: python scripts/build_lookup_db.py"
            )
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA query_only = ON")

    def close(self):
        self._conn.close()

    def get_gene(self, symbol: str) -> dict | None:
        """Case-insensitive gene lookup by symbol."""
        row = self._conn.execute(
            "SELECT * FROM genes WHERE UPPER(symbol) = UPPER(?)", (symbol,)
        ).fetchone()
        return dict(row) if row else None

    def get_gene_region(self, symbol: str, padding: int = 2000) -> str | None:
        """Return 'chrom:start-end' region for a gene with padding."""
        gene = self.get_gene(symbol)
        if not gene:
            return None
        start = max(1, gene["start"] - padding)
        end = gene["end"] + padding
        return f"{gene['chrom']}:{start}-{end}"

    def search_pgx_by_drug(self, drug_name: str) -> list[dict]:
        """Search PGx drug entries by drug name or alias (case-insensitive)."""
        rows = self._conn.execute(
            "SELECT * FROM pgx_drugs WHERE "
            "UPPER(drug_name) = UPPER(?) OR "
            "UPPER(drug_aliases) LIKE '%' || UPPER(?) || '%'",
            (drug_name, drug_name),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_pgx_by_gene(self, gene: str) -> list[dict]:
        """Search PGx drug entries by gene (case-insensitive)."""
        rows = self._conn.execute(
            "SELECT * FROM pgx_drugs WHERE UPPER(gene) = UPPER(?)", (gene,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_pgx_variants(self, gene: str) -> list[dict]:
        """Get known PGx variants for a gene."""
        rows = self._conn.execute(
            "SELECT * FROM pgx_variants WHERE UPPER(gene) = UPPER(?)", (gene,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trait_variants(
        self,
        category: str | None = None,
        trait: str | None = None,
        gene: str | None = None,
    ) -> list[dict]:
        """Get trait variants, optionally filtered."""
        query = "SELECT * FROM trait_variants WHERE 1=1"
        params: list[str] = []
        if category:
            query += " AND UPPER(trait_category) = UPPER(?)"
            params.append(category)
        if trait:
            query += " AND UPPER(trait) LIKE '%' || UPPER(?) || '%'"
            params.append(trait)
        if gene:
            query += " AND UPPER(gene) = UPPER(?)"
            params.append(gene)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_carrier_genes(
        self, condition: str | None = None, acmg_only: bool = False
    ) -> list[dict]:
        """Get carrier screening genes."""
        query = "SELECT * FROM carrier_genes WHERE 1=1"
        params: list = []
        if condition:
            query += " AND UPPER(condition_name) LIKE '%' || UPPER(?) || '%'"
            params.append(condition)
        if acmg_only:
            query += " AND acmg_recommended = 1"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_prs_weights(
        self, trait: str | None = None, prs_id: str | None = None
    ) -> list[dict]:
        """Get PRS weights for a trait or specific PRS ID."""
        query = "SELECT * FROM prs_weights WHERE 1=1"
        params: list[str] = []
        if trait:
            query += " AND UPPER(trait) LIKE '%' || UPPER(?) || '%'"
            params.append(trait)
        if prs_id:
            query += " AND prs_id = ?"
            params.append(prs_id)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def has_gwas_table(self) -> bool:
        """Check if GWAS associations table exists."""
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gwas_associations'"
        ).fetchone()
        return row is not None

    def search_gwas(
        self,
        trait: str | None = None,
        gene: str | None = None,
        rsid: str | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Search GWAS Catalog associations by trait, gene, or rsID.

        Returns results ordered by p-value (most significant first).
        """
        if not self.has_gwas_table():
            return []
        query = "SELECT * FROM gwas_associations WHERE 1=1"
        params: list[str] = []
        if trait:
            query += " AND (UPPER(trait) LIKE '%' || UPPER(?) || '%' OR UPPER(mapped_trait) LIKE '%' || UPPER(?) || '%')"
            params.extend([trait, trait])
        if gene:
            query += " AND UPPER(mapped_gene) LIKE '%' || UPPER(?) || '%'"
            params.append(gene)
        if rsid:
            query += " AND rsid = ?"
            params.append(rsid)
        query += " ORDER BY p_value IS NULL, p_value ASC LIMIT ?"
        params.append(max_results)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def gwas_traits_for_gene(self, gene: str, max_results: int = 20) -> list[dict]:
        """Get distinct GWAS traits associated with a gene, ordered by significance."""
        if not self.has_gwas_table():
            return []
        rows = self._conn.execute(
            """SELECT trait, mapped_trait, MIN(p_value) as best_pvalue,
                      COUNT(*) as n_associations
               FROM gwas_associations
               WHERE UPPER(mapped_gene) LIKE '%' || UPPER(?) || '%'
               GROUP BY UPPER(trait)
               ORDER BY best_pvalue IS NULL, best_pvalue ASC
               LIMIT ?""",
            (gene, max_results),
        ).fetchall()
        return [dict(r) for r in rows]
