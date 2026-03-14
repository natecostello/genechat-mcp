---
status: accepted
date: 2026-03-14
related ADRs:
  - [0001-patch-architecture.md](0001-patch-architecture.md)
---

# Enhanced Warnings for High-Impact Gene Results

## Context and Problem Statement

GeneChat returns genomic annotations that an LLM then presents conversationally.
For most variants the existing medical disclaimer is sufficient. However, certain
genes are associated with severe, progressive, or fatal conditions that lack
effective treatments — learning carrier status for these conditions carries
documented psychological harm. 23andMe was required by the FDA to gate results
for APOE, LRRK2/GBA, and BRCA1/2 behind opt-in consent. While GeneChat has no
regulatory obligation, the same concern applies: the LLM will naturally interpret
results ("You carry APOE e4, which means...") without any signal to exercise
caution.

## Decision Drivers

- **User autonomy**: Users sought out WGS data and installed this tool — they
  should not be patronized
- **Psychological safety**: Unsolicited disclosure of untreatable conditions
  (Huntington's, ALS, prion disease) causes documented harm
- **LLM behavior**: Without a signal in the tool output, the LLM will interpret
  results identically for CYP2D6 metabolizer status and Huntington's carrier
  status
- **Maintainability**: The gene list must update automatically as upstream
  databases grow — AI-accelerated gene discovery makes manual curation
  unsustainable
- **Precision**: The list must avoid false positives (warnings for actionable
  conditions where the finding empowers the patient)

## Considered Options

1. **Status quo** — no special handling, rely on the per-response medical
   disclaimer
2. **Enhanced warnings via mechanically derived gene list** — prepend a warning
   to tool output when results involve genes associated with severe untreatable
   conditions
3. **Consent-gated queries** — require explicit user confirmation before
   returning results for high-impact genes

## Decision Outcome

**Option 2: Enhanced warnings via mechanical derivation.**

The gene list is derived from three public, versioned data sources with no
subjective curation required:

1. **ClinVar** — genes with "Pathogenic" significance on GRCh38 (with review
   criteria) → ~5,500 genes
2. **HPO** (Human Phenotype Ontology) — genes annotated with death/lethality
   or neurodegeneration phenotype terms → ~700 genes
3. **Intersect** ClinVar ∩ HPO → ~550 genes
4. **Subtract** ACMG Secondary Findings v3.3 (81 clinically actionable genes)
   → ~540 genes

This captures genes where: (a) pathogenic variants are known, (b) the condition
involves death or progressive neurodegeneration, AND (c) the gene is NOT on the
ACMG actionability list. The ACMG subtraction is critical — BRCA1/2, LDLR,
RYR1, and other actionable genes are excluded because their findings empower the
patient to take preventive action.

### HPO phenotype terms used

**Death/lethality:**
- HP:0003826 Stillbirth
- HP:0003811 Neonatal death
- HP:0001522 Death in infancy
- HP:0003819 Death in childhood
- HP:0011421 Death in adolescence
- HP:0100613 Death in early adulthood
- HP:0033041 Death in middle age

**Neurodegeneration/progressive deterioration:**
- HP:0002180 Neurodegeneration
- HP:0001268 Mental deterioration
- HP:0002344 Progressive neurologic deterioration
- HP:0007272 Progressive psychomotor deterioration
- HP:0006964 Cerebral cortical neurodegeneration
- HP:0007064 Progressive language deterioration
- HP:0002529 Neuronal loss in central nervous system

### Validation

Confirmed captures: HTT, SOD1, PRNP, C9orf72, MAPT, FUS, TARDBP, SNCA, APP,
PSEN1, ATXN2, ATXN7.

Confirmed excludes: BRCA1, BRCA2, MLH1, LDLR, RYR1, TP53, SCN5A, KCNH2.

### Why not Option 1

The LLM has no signal to differentiate pharmacogenomic results from Huntington's
carrier status. Both arrive as identical tool responses. The disclaimer at the
end of every response is routinely ignored.

### Why not Option 3

MCP tools don't have a native "confirm and retry" pattern. The implementation
complexity is high, and users will immediately re-query with the confirmation
flag, making it security theater rather than genuine informed consent.

## Confirmation

- The `enhanced_warning_genes` table is populated by `genechat install --seeds`
- Unit tests verify that known high-impact genes (HTT, SOD1, PRNP) are in the
  table and actionable genes (BRCA1, LDLR) are excluded
- Tool tests verify the warning text is prepended to output for matched genes

## More Information

- Issue #48: ADR discussion
- Issue #51: Implementation specification
- Issue #52: README LLM interpretation guidance
