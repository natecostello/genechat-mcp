"""Tests for VCF field parsers."""

from genechat.parsers import parse_ann_field, parse_clinvar_fields, parse_genotype


class TestParseAnnField:
    def test_basic_ann(self):
        ann = "T|missense_variant|MODERATE|SLCO1B1|ENSG00000134538|transcript|ENST00000256958|protein_coding||c.521T>C|p.Val174Ala|||||"
        result = parse_ann_field(ann)
        assert result["gene"] == "SLCO1B1"
        assert result["effect"] == "missense_variant"
        assert result["impact"] == "MODERATE"
        assert result["hgvs_c"] == "c.521T>C"
        assert result["hgvs_p"] == "p.Val174Ala"

    def test_empty_ann(self):
        assert parse_ann_field("") == {}
        assert parse_ann_field(".") == {}

    def test_multiple_transcripts(self):
        ann = (
            "T|missense_variant|MODERATE|GENE1|ID1|transcript|TR1|coding||c.1A>T|p.Met1Leu|||||,"
            "T|synonymous_variant|LOW|GENE1|ID1|transcript|TR2|coding||c.3G>A|p.Met1Met|||||"
        )
        result = parse_ann_field(ann)
        assert result["effect"] == "missense_variant"  # First (most severe)

    def test_short_ann(self):
        result = parse_ann_field("T|splice")
        assert "raw" in result


class TestParseClinvarFields:
    def test_basic_clinvar(self):
        result = parse_clinvar_fields(
            "Pathogenic", "Cystic_fibrosis", "reviewed_by_expert_panel"
        )
        assert result["significance"] == "Pathogenic"
        assert result["condition"] == "Cystic fibrosis"
        assert result["review_status"] == "reviewed by expert panel"

    def test_empty_clinvar(self):
        assert parse_clinvar_fields("", "", "") == {}
        assert parse_clinvar_fields(".", ".", ".") == {}

    def test_no_condition(self):
        result = parse_clinvar_fields("drug_response", ".", ".")
        assert result["significance"] == "drug response"
        assert result["condition"] is None


class TestParseGenotype:
    def test_het(self):
        result = parse_genotype("0/1", "T", "C")
        assert result["display"] == "T/C"
        assert result["zygosity"] == "heterozygous"

    def test_hom_ref(self):
        result = parse_genotype("0/0", "A", "G")
        assert result["display"] == "A/A"
        assert result["zygosity"] == "homozygous_ref"

    def test_hom_alt(self):
        result = parse_genotype("1/1", "G", "A")
        assert result["display"] == "A/A"
        assert result["zygosity"] == "homozygous_alt"

    def test_no_call(self):
        result = parse_genotype("./.", "A", "T")
        assert result["zygosity"] == "no_call"

    def test_phased(self):
        result = parse_genotype("0|1", "T", "C")
        assert result["display"] == "T/C"
        assert result["zygosity"] == "heterozygous"

    def test_multiallelic(self):
        result = parse_genotype("1/2", "A", "T,G")
        assert result["display"] == "T/G"
        assert result["zygosity"] == "heterozygous"
