"""SQLite query layer for lookup tables."""

import sqlite3
from pathlib import Path

from genechat.config import AppConfig


class LookupDB:
    """Read-only access to the GeneChat lookup database.

    Supports a separate GWAS DB via ATTACH DATABASE for backward compatibility
    with both the old layout (GWAS in lookup_tables.db) and the new layout
    (GWAS in a standalone gwas.db).
    """

    def __init__(self, config: AppConfig):
        db_path = config.lookup_db_path
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Lookup database not found: {db_path}. "
                "Run: genechat init <vcf>"
            )
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA query_only = ON")

        # Determine GWAS table prefix: check main DB first (legacy layout),
        # then try attaching separate gwas.db (new layout)
        self._gwas_prefix = ""
        if self._has_table_in_main("gwas_associations"):
            self._gwas_prefix = ""  # GWAS is in the main DB
        else:
            gwas_path = Path(config.gwas_db_path)
            if gwas_path.exists():
                self._conn.execute(
                    "ATTACH DATABASE ? AS gwas", (str(gwas_path),)
                )
                self._gwas_prefix = "gwas."

    def _has_table_in_main(self, table_name: str) -> bool:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

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
        """Search PGx drug entries by drug name (case-insensitive)."""
        rows = self._conn.execute(
            "SELECT * FROM pgx_drugs WHERE UPPER(drug_name) = UPPER(?)",
            (drug_name,),
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

    def list_prs_traits(self) -> list[dict]:
        """List available PRS traits with their PGS IDs."""
        rows = self._conn.execute(
            "SELECT DISTINCT prs_id, trait FROM prs_weights ORDER BY trait, prs_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def has_gwas_table(self) -> bool:
        """Check if GWAS associations table is available (main or attached)."""
        if self._gwas_prefix:
            # Attached DB — check its schema
            row = self._conn.execute(
                "SELECT name FROM gwas.sqlite_master WHERE type='table' AND name='gwas_associations'"
            ).fetchone()
            return row is not None
        return self._has_table_in_main("gwas_associations")

    def search_gwas(
        self,
        trait: str | None = None,
        gene: str | None = None,
        rsid: str | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Search GWAS Catalog associations by trait, gene, or rsID."""
        if not self.has_gwas_table():
            return []
        table = f"{self._gwas_prefix}gwas_associations"
        query = f"SELECT * FROM {table} WHERE 1=1"
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
        """Get distinct GWAS traits associated with a gene."""
        if not self.has_gwas_table():
            return []
        table = f"{self._gwas_prefix}gwas_associations"
        rows = self._conn.execute(
            f"""SELECT trait, mapped_trait, MIN(p_value) as best_pvalue,
                      COUNT(*) as n_associations
               FROM {table}
               WHERE UPPER(mapped_gene) LIKE '%' || UPPER(?) || '%'
               GROUP BY UPPER(trait)
               ORDER BY best_pvalue IS NULL, best_pvalue ASC
               LIMIT ?""",
            (gene, max_results),
        ).fetchall()
        return [dict(r) for r in rows]
