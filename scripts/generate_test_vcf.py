#!/usr/bin/env python3
"""Generate a synthetic VCF for testing GeneChat.

Creates a small VCF with known variants covering PGx, ClinVar, trait,
and carrier screening use cases. Uses pysam for compression and indexing.
"""

from pathlib import Path

import pysam

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "tests" / "data"

VCF_HEADER = """\
##fileformat=VCFv4.2
##FILTER=<ID=PASS,Description="All filters passed">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##INFO=<ID=ANN,Number=.,Type=String,Description="SnpEff functional annotation">
##INFO=<ID=CLNSIG,Number=.,Type=String,Description="ClinVar clinical significance">
##INFO=<ID=CLNDN,Number=.,Type=String,Description="ClinVar disease name">
##INFO=<ID=CLNREVSTAT,Number=.,Type=String,Description="ClinVar review status">
##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">
##INFO=<ID=AF_popmax,Number=A,Type=Float,Description="Maximum allele frequency across populations">
##contig=<ID=chr1,length=248956422>
##contig=<ID=chr2,length=242193529>
##contig=<ID=chr4,length=190214555>
##contig=<ID=chr6,length=170805979>
##contig=<ID=chr7,length=159345973>
##contig=<ID=chr9,length=138394717>
##contig=<ID=chr10,length=133797422>
##contig=<ID=chr11,length=135086622>
##contig=<ID=chr12,length=133275309>
##contig=<ID=chr15,length=101991189>
##contig=<ID=chr16,length=90338345>
##contig=<ID=chr13,length=114364328>
##contig=<ID=chr14,length=107043718>
##contig=<ID=chr17,length=83257441>
##contig=<ID=chr19,length=58617616>
##contig=<ID=chr20,length=64444167>
##contig=<ID=chr22,length=50818468>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tTEST_SAMPLE"""

# Each variant: (CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, GT)
# Sorted by chrom then pos for valid VCF
VARIANTS = [
    # DPYD *2A — het carrier (chr1)
    (
        "chr1",
        97450058,
        "rs3918290",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|splice_donor_variant|HIGH|DPYD|ENSG00000188641|transcript|ENST00000370192|protein_coding||c.1905+1G>A|||||||;"
        "CLNSIG=Pathogenic;CLNDN=Dihydropyrimidine_dehydrogenase_deficiency;"
        "CLNREVSTAT=criteria_provided,_multiple_submitters,_no_conflicts;AF=0.01;AF_popmax=0.02",
        "0/1",
    ),
    # MTHFR C677T — het (chr1)
    (
        "chr1",
        11796321,
        "rs1801133",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|missense_variant|MODERATE|MTHFR|ENSG00000177000|transcript|ENST00000376592|protein_coding||c.665C>T|p.Ala222Val||||||;"
        "CLNSIG=risk_factor;CLNDN=MTHFR_thermolabile_variant;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.33;AF_popmax=0.44",
        "0/1",
    ),
    # Factor V Leiden — hom ref (chr1)
    (
        "chr1",
        169549811,
        "rs6025",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|missense_variant|MODERATE|F5|ENSG00000198734|transcript|ENST00000367797|protein_coding||c.1601G>A|p.Arg534Gln||||||;"
        "CLNSIG=Pathogenic;CLNDN=Factor_V_Leiden_thrombophilia;"
        "CLNREVSTAT=criteria_provided,_multiple_submitters,_no_conflicts;AF=0.03;AF_popmax=0.05",
        "0/0",
    ),
    # ADH1B — het (chr4)
    (
        "chr4",
        99318162,
        "rs1229984",
        "T",
        "C",
        ".",
        "PASS",
        "ANN=C|missense_variant|MODERATE|ADH1B|ENSG00000196616|transcript|ENST00000394887|protein_coding||c.143A>G|p.His48Arg||||||;"
        "AF=0.25;AF_popmax=0.75",
        "0/1",
    ),
    # HFE C282Y — het carrier (chr6)
    (
        "chr6",
        26091179,
        "rs1800562",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|missense_variant|MODERATE|HFE|ENSG00000010704|transcript|ENST00000357618|protein_coding||c.845G>A|p.Cys282Tyr||||||;"
        "CLNSIG=Pathogenic;CLNDN=Hereditary_hemochromatosis;"
        "CLNREVSTAT=criteria_provided,_multiple_submitters,_no_conflicts;AF=0.06;AF_popmax=0.10",
        "0/1",
    ),
    # CFTR F508del — het carrier (chr7)
    (
        "chr7",
        117559590,
        "rs113993960",
        "ATCT",
        "A",
        ".",
        "PASS",
        "ANN=A|frameshift_variant|HIGH|CFTR|ENSG00000001626|transcript|ENST00000003084|protein_coding||c.1521_1523del|p.Phe508del||||||;"
        "CLNSIG=Pathogenic;CLNDN=Cystic_fibrosis;"
        "CLNREVSTAT=reviewed_by_expert_panel;AF=0.02;AF_popmax=0.04",
        "0/1",
    ),
    # 9p21 CAD locus (chr9)
    (
        "chr9",
        22125503,
        "rs1333049",
        "C",
        "G",
        ".",
        "PASS",
        "ANN=G|intergenic_region|MODIFIER|CDKN2B-AS1||||||||||||||;AF=0.47;AF_popmax=0.52",
        "1/1",
    ),
    # CYP2C9 *2 — hom ref (chr10)
    (
        "chr10",
        94942290,
        "rs1799853",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|missense_variant|MODERATE|CYP2C9|ENSG00000138109|transcript|ENST00000260682|protein_coding||c.430C>T|p.Arg144Cys||||||;"
        "CLNSIG=drug_response;CLNDN=warfarin_response;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.12;AF_popmax=0.15",
        "0/0",
    ),
    # CYP2C19 *2 — het (chr10)
    (
        "chr10",
        94781859,
        "rs4244285",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|splice_variant|HIGH|CYP2C19|ENSG00000165841|transcript|ENST00000371321|protein_coding||c.681G>A|||||||;"
        "CLNSIG=drug_response;CLNDN=clopidogrel_response;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.15;AF_popmax=0.30",
        "0/1",
    ),
    # ACTN3 R577X — hom alt CC (chr11)
    (
        "chr11",
        66560624,
        "rs1815739",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|stop_gained|HIGH|ACTN3|ENSG00000095932|transcript|ENST00000502587|protein_coding||c.1729C>T|p.Arg577Ter||||||;"
        "AF=0.42;AF_popmax=0.58",
        "0/0",
    ),
    # SLCO1B1 *5 — het (chr12)
    (
        "chr12",
        21178615,
        "rs4149056",
        "T",
        "C",
        ".",
        "PASS",
        "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG00000134538|transcript|ENST00000256958|protein_coding||c.521T>C|p.Val174Ala||||||;"
        "CLNSIG=drug_response;CLNDN=Simvastatin_response;"
        "CLNREVSTAT=criteria_provided,_multiple_submitters,_no_conflicts;AF=0.14;AF_popmax=0.21",
        "0/1",
    ),
    # ALDH2 — het (chr12)
    (
        "chr12",
        111803962,
        "rs671",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|missense_variant|MODERATE|ALDH2|ENSG00000111275|transcript|ENST00000261733|protein_coding||c.1510G>A|p.Glu504Lys||||||;"
        "AF=0.08;AF_popmax=0.28",
        "0/1",
    ),
    # CYP1A2 caffeine — het (chr15)
    (
        "chr15",
        74749576,
        "rs762551",
        "A",
        "C",
        ".",
        "PASS",
        "ANN=C|upstream_gene_variant|MODIFIER|CYP1A2|ENSG00000140505|transcript|ENST00000343932|protein_coding||||||||||;"
        "AF=0.33;AF_popmax=0.45",
        "0/1",
    ),
    # FTO obesity — het (chr16)
    (
        "chr16",
        53786615,
        "rs9939609",
        "T",
        "A",
        ".",
        "PASS",
        "ANN=A|intron_variant|MODIFIER|FTO|ENSG00000140718|transcript|ENST00000471389|protein_coding||||||||||;"
        "AF=0.42;AF_popmax=0.49",
        "0/1",
    ),
    # VKORC1 — hom alt (chr16)
    (
        "chr16",
        31096368,
        "rs9923231",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|upstream_gene_variant|MODIFIER|VKORC1|ENSG00000167397|transcript|ENST00000394975|protein_coding||||||||||;"
        "CLNSIG=drug_response;CLNDN=warfarin_dose;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.39;AF_popmax=0.94",
        "1/1",
    ),
    # APOE rs429358 (E4 defining) — het (chr19)
    (
        "chr19",
        44908684,
        "rs429358",
        "T",
        "C",
        ".",
        "PASS",
        "ANN=C|missense_variant|MODERATE|APOE|ENSG00000130203|transcript|ENST00000252486|protein_coding||c.388T>C|p.Cys130Arg||||||;"
        "CLNSIG=risk_factor;CLNDN=Alzheimer_disease;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.15;AF_popmax=0.20",
        "0/1",
    ),
    # APOE rs7412 (E2 defining) — hom ref (chr19)
    (
        "chr19",
        44908822,
        "rs7412",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|missense_variant|MODERATE|APOE|ENSG00000130203|transcript|ENST00000252486|protein_coding||c.526C>T|p.Arg176Cys||||||;"
        "CLNSIG=risk_factor;CLNDN=Hyperlipoproteinemia_type_III;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.08;AF_popmax=0.12",
        "0/0",
    ),
    # MC1R red hair — het (chr16)
    (
        "chr16",
        89919709,
        "rs1805007",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|missense_variant|MODERATE|MC1R|ENSG00000258839|transcript|ENST00000555147|protein_coding||c.451C>T|p.Arg151Cys||||||;"
        "AF=0.07;AF_popmax=0.12",
        "0/1",
    ),
    # HERC2 eye color — hom alt (blue eyes) (chr15)
    (
        "chr15",
        28120472,
        "rs12913832",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|intergenic_region|MODIFIER|HERC2||||||||||||||;AF=0.50;AF_popmax=0.79",
        "1/1",
    ),
    # COMT Val158Met — het (chr22)
    (
        "chr22",
        19963748,
        "rs4680",
        "G",
        "A",
        ".",
        "PASS",
        "ANN=A|missense_variant|MODERATE|COMT|ENSG00000093010|transcript|ENST00000361682|protein_coding||c.472G>A|p.Val158Met||||||;"
        "AF=0.50;AF_popmax=0.55",
        "0/1",
    ),
    # TCF7L2 T2D PRS variant — het (chr10)
    (
        "chr10",
        112998590,
        "rs7903146",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|intron_variant|MODIFIER|TCF7L2|ENSG00000148737|transcript|ENST00000543371|protein_coding||||||||||;"
        "AF=0.28;AF_popmax=0.40",
        "0/1",
    ),
    # KCNJ11 T2D PRS variant — hom alt (chr11)
    (
        "chr11",
        17388025,
        "rs5219",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|missense_variant|MODERATE|KCNJ11|ENSG00000187486|transcript|ENST00000339994|protein_coding||c.67C>T|p.Lys23Glu||||||;"
        "AF=0.36;AF_popmax=0.50",
        "1/1",
    ),
    # FOXO3 longevity — het (chr6)
    (
        "chr6",
        108881026,
        "rs2802292",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|intron_variant|MODIFIER|FOXO3|ENSG00000118689|transcript|ENST00000343882|protein_coding||||||||||;"
        "AF=0.30;AF_popmax=0.45",
        "0/1",
    ),
    # CYP2D6 *4 — het (chr22)
    (
        "chr22",
        42128945,
        "rs3892097",
        "C",
        "T",
        ".",
        "PASS",
        "ANN=T|splice_variant|HIGH|CYP2D6|ENSG00000100197|transcript|ENST00000360608|protein_coding||c.506-1G>A|||||||;"
        "CLNSIG=drug_response;CLNDN=CYP2D6_poor_metabolizer;"
        "CLNREVSTAT=criteria_provided,_single_submitter;AF=0.12;AF_popmax=0.22",
        "0/1",
    ),
]


def generate_vcf():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vcf_path = OUTPUT_DIR / "test_sample.vcf"
    gz_path = OUTPUT_DIR / "test_sample.vcf.gz"

    # Sort variants by chromosome order and position
    chrom_order = {f"chr{i}": i for i in range(1, 23)}
    chrom_order.update({"chrX": 23, "chrY": 24, "chrM": 25})
    sorted_variants = sorted(VARIANTS, key=lambda v: (chrom_order.get(v[0], 99), v[1]))

    with open(vcf_path, "w") as f:
        f.write(VCF_HEADER + "\n")
        for chrom, pos, rsid, ref, alt, qual, filt, info, gt in sorted_variants:
            f.write(
                f"{chrom}\t{pos}\t{rsid}\t{ref}\t{alt}\t{qual}\t{filt}\t{info}\tGT\t{gt}\n"
            )

    # Compress and index with pysam
    if gz_path.exists():
        gz_path.unlink()
    tbi_path = Path(f"{gz_path}.tbi")
    if tbi_path.exists():
        tbi_path.unlink()

    pysam.tabix_compress(str(vcf_path), str(gz_path))
    pysam.tabix_index(str(gz_path), preset="vcf")

    # Clean up uncompressed VCF
    vcf_path.unlink()

    print(f"Compressed and indexed: {gz_path}")


if __name__ == "__main__":
    generate_vcf()
