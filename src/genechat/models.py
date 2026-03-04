"""Pydantic models for MCP tool input validation."""

from pydantic import BaseModel, Field


class QueryVariantInput(BaseModel):
    rsid: str | None = Field(None, description="rsID (e.g. rs4149056)")
    position: str | None = Field(
        None, description="Genomic position as chr:pos (e.g. chr22:42127941)"
    )


class QueryGeneInput(BaseModel):
    gene: str = Field(description="Gene symbol (e.g. SLCO1B1)")
    impact_filter: str = Field(
        "HIGH,MODERATE",
        description="Comma-separated SnpEff impact levels to include",
    )
    max_results: int = Field(50, ge=1, le=500)


class QueryClinvarInput(BaseModel):
    significance: str = Field(
        description="ClinVar significance (e.g. Pathogenic, Likely_pathogenic, drug_response)"
    )
    gene: str | None = Field(None, description="Optional gene to restrict search")
    condition: str | None = Field(None, description="Optional condition name filter")
    max_results: int = Field(50, ge=1, le=100)


class QueryPgxInput(BaseModel):
    drug: str | None = Field(None, description="Drug name (e.g. simvastatin)")
    gene: str | None = Field(None, description="Gene symbol (e.g. SLCO1B1)")
    include_all_variants: bool = Field(
        False, description="Include all variants in gene, not just known PGx"
    )


class QueryTraitInput(BaseModel):
    category: str | None = Field(
        None,
        description="Trait category: nutrigenomics, exercise, metabolism, sleep, "
        "caffeine, alcohol, cardiovascular, inflammation",
    )
    trait: str | None = Field(None, description="Specific trait name")
    gene: str | None = Field(None, description="Gene symbol")


class QueryCarrierInput(BaseModel):
    condition: str | None = Field(None, description="Optional condition name filter")
    acmg_only: bool = Field(True, description="Only ACMG-recommended genes")
    max_results: int = Field(50, ge=1, le=200)


class CalculatePrsInput(BaseModel):
    trait: str | None = Field(None, description="Trait name (e.g. coronary artery disease)")
    prs_id: str | None = Field(None, description="Specific PGS Catalog ID")
