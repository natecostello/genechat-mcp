# Data Source Licenses

GeneChat uses data from multiple public databases. License obligations depend on
which annotation layers the user installs. The base install (`genechat init`
without extra flags) uses public-domain and permissively licensed data —
citations are appreciated but not legally required. SnpEff is MIT-licensed,
which requires preserving the copyright notice when redistributing the software.

Run `genechat licenses` to see which licenses apply to your specific installation.

---

## Always applicable (default install)

### ClinVar

- **License:** Public domain (US Government work)
- **URL:** <https://www.ncbi.nlm.nih.gov/clinvar/>
- **Obligations:** None (citation appreciated)
- **Disclaimer:** ClinVar data is not intended for direct diagnostic use or
  medical decision-making without review by a genetics professional.
- **Citation:** Landrum MJ et al., "ClinVar: improvements to accessing data,"
  Nucleic Acids Res. 2024. PMID: [37953324](https://pubmed.ncbi.nlm.nih.gov/37953324/)

### SnpEff

- **License:** MIT
- **URL:** <https://pcingola.github.io/SnpEff/>
- **Obligations:** Include copyright notice in derivative works
- **Citation:** Cingolani P et al., "A program for annotating and predicting the
  effects of single nucleotide polymorphisms, SnpEff," Fly. 2012.
  DOI: [10.4161/fly.19695](https://doi.org/10.4161/fly.19695)

### CPIC (Clinical Pharmacogenetics Implementation Consortium)

- **License:** CC0 1.0 (public domain dedication)
- **URL:** <https://cpicpgx.org/>
- **Obligations:** None (citation requested)
- **Citation:** Relling MV & Klein TE, "CPIC: Clinical Pharmacogenetics
  Implementation Consortium of the Pharmacogenomics Research Network,"
  Clin Pharmacol Ther. 2011. PMID: [21270786](https://pubmed.ncbi.nlm.nih.gov/21270786/)

### HGNC (HUGO Gene Nomenclature Committee)

- **License:** CC0 1.0
- **URL:** <https://www.genenames.org/>
- **Obligations:** None
- **Citation:** Seal RL et al., "Genenames.org: the HGNC resources in 2023,"
  Nucleic Acids Res. 2023. PMID: [36243972](https://pubmed.ncbi.nlm.nih.gov/36243972/)

### Ensembl

- **License:** No restrictions on use
- **URL:** <https://www.ensembl.org/>
- **Obligations:** None
- **Citation:** Harrison PW et al., "Ensembl 2024," Nucleic Acids Res. 2024.
  PMID: [39656687](https://pubmed.ncbi.nlm.nih.gov/39656687/)

---

## Optional annotation layers

### gnomAD (Genome Aggregation Database)

- **License:** Open Database License (ODbL) v1.0
- **URL:** <https://gnomad.broadinstitute.org/>
- **License URL:** <https://opendatacommons.org/licenses/odbl/1-0/>
- **Install flag:** `--gnomad`
- **Obligations:**
  - **Attribution required.** Include: "Contains information from the Genome
    Aggregation Database (gnomAD), which is made available under the ODbL."
  - **Share-alike on derivative databases.** The patch.db file containing gnomAD
    allele frequencies is a derivative database under ODbL. If shared, the
    gnomAD-derived portions must remain under ODbL.
  - **Produced works are not share-alike.** Tool responses sent to the LLM are
    "produced works" under ODbL — they require only the attribution notice
    above, not share-alike.
  - GeneChat source code (MIT) is unaffected by ODbL.
- **Citation:** Chen S et al., "A genomic mutational constraint map using
  variation in 76,156 human genomes," Nature. 2024.
  DOI: [10.1038/s41586-023-06045-0](https://doi.org/10.1038/s41586-023-06045-0)

### dbSNP

- **License:** Public domain (US Government work)
- **URL:** <https://www.ncbi.nlm.nih.gov/snp/>
- **Install flag:** `--dbsnp`
- **Obligations:** None
- **Citation:** Sherry ST et al., "dbSNP: the NCBI database of genetic
  variation," Nucleic Acids Res. 2001.
  PMID: [11125122](https://pubmed.ncbi.nlm.nih.gov/11125122/)

### GWAS Catalog

- **License:** CC0 1.0 (for data published after 2021)
- **URL:** <https://www.ebi.ac.uk/gwas/>
- **Install flag:** `--gwas`
- **Obligations:** None (citation requested)
- **Citation:** Sollis E et al., "The NHGRI-EBI GWAS Catalog: knowledgebase and
  deposition resource," Nucleic Acids Res. 2023.
  PMID: [36350656](https://pubmed.ncbi.nlm.nih.gov/36350656/)

---

## Seed data (PGS Catalog scores)

### PGS Catalog (platform)

- **License:** EBI Terms of Use + per-score publication licenses
- **URL:** <https://www.pgscatalog.org/>
- **License URL:** <https://www.ebi.ac.uk/about/terms-of-use/>
- **Obligations:** Cite the catalog paper and each individual score publication
- **Catalog citation:** Lambert SA et al., "The Polygenic Score Catalog: new
  functionality and tools to enable FAIR research," Nat Genet. 2024.
  DOI: [10.1038/s41588-024-01937-x](https://doi.org/10.1038/s41588-024-01937-x)

### Per-score citations

All bundled PGS scores are from publications with permissive licenses (CC BY 4.0
via open-access BMC and Nature Communications journals, or standard academic
terms for factual data).

| PGS ID | Trait | Variants | Publication | License |
|--------|-------|----------|-------------|---------|
| PGS000010 | Coronary artery disease | 27 | Mega JL et al., Lancet 2015. PMID: [25748612](https://pubmed.ncbi.nlm.nih.gov/25748612/) | Standard academic |
| PGS000349 | Coronary artery disease | 70 | Pechlivanis S et al., BMC Med Genet 2020. PMID: [32912153](https://pubmed.ncbi.nlm.nih.gov/32912153/) | CC BY 4.0 |
| PGS000074 | Colorectal cancer | 103 | Graff RE et al., Nat Commun 2021. PMID: [33579919](https://pubmed.ncbi.nlm.nih.gov/33579919/) | CC BY 4.0 |
| PGS002251 | Body mass index (BMI) | 97 | Dashti HS et al., BMC Med 2022. PMID: [35016652](https://pubmed.ncbi.nlm.nih.gov/35016652/) | CC BY 4.0 |

---

## Enhanced-warning gene list (installed via seed data)

The enhanced-warning gene list is built from the intersection of ClinVar
pathogenic variants and HPO severe phenotypes, minus ACMG SF v3.3 actionable
genes. It is included in `lookup_tables.db` via `genechat install --seeds`.

### HPO (Human Phenotype Ontology)

- **License:** Custom (see <https://hpo.jax.org/license>)
- **Obligations:**
  - Must cite the HPO paper
  - Must display the HPO version used
  - Must not modify HPO data
- **Citation:** Kohler S et al., "The Human Phenotype Ontology in 2021,"
  Nucleic Acids Res. 2021. PMID: [33264411](https://pubmed.ncbi.nlm.nih.gov/33264411/)

### ACMG SF v3.3

- **License:** Published paper (standard academic terms)
- **Citation:** Miller DT et al., "ACMG SF v3.2 list for reporting of secondary
  findings in clinical exome and genome sequencing," Genet Med. 2023.
  PMID: [37347242](https://pubmed.ncbi.nlm.nih.gov/37347242/)
