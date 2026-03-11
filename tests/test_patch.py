"""Tests for PatchDB and VCF stream parser."""

import pytest

from genechat.patch import PatchDB, parse_vcf_stream, _extract_info_field


# -- VCF stream parser tests --


class TestExtractInfoField:
    def test_field_at_start(self):
        assert _extract_info_field("AF=0.14;AC=1", "AF") == "0.14"

    def test_field_in_middle(self):
        assert _extract_info_field("AC=1;AF=0.14;AN=2", "AF") == "0.14"

    def test_field_at_end(self):
        assert _extract_info_field("AC=1;AF=0.14", "AF") == "0.14"

    def test_field_not_present(self):
        assert _extract_info_field("AC=1;AN=2", "AF") is None

    def test_no_prefix_collision(self):
        """AF should not match AF_grpmax."""
        assert _extract_info_field("AF_grpmax=0.18;AF=0.14", "AF") == "0.14"

    def test_grpmax_extraction(self):
        assert _extract_info_field("AF=0.14;AF_grpmax=0.18", "AF_grpmax") == "0.18"

    def test_complex_ann_field(self):
        info = "ANN=T|splice_donor_variant|HIGH|DPYD;CLNSIG=Pathogenic"
        assert _extract_info_field(info, "ANN") == "T|splice_donor_variant|HIGH|DPYD"
        assert _extract_info_field(info, "CLNSIG") == "Pathogenic"


class TestParseVcfStream:
    def _make_stream(self, lines):
        """Create an iterator of VCF lines."""
        return iter(lines)

    def test_skips_headers(self):
        lines = [
            "##fileformat=VCFv4.2\n",
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n",
            "chr1\t100\trs123\tA\tG\t.\tPASS\tAF=0.1\tGT\t0/1\n",
        ]
        results = list(parse_vcf_stream(self._make_stream(lines), ["AF"]))
        assert len(results) == 1
        assert results[0]["chrom"] == "chr1"
        assert results[0]["pos"] == 100
        assert results[0]["rsid"] == "rs123"
        assert results[0]["AF"] == "0.1"

    def test_dot_id_not_rsid(self):
        lines = ["chr1\t100\t.\tA\tG\t.\tPASS\tAF=0.1\tGT\t0/1\n"]
        results = list(parse_vcf_stream(self._make_stream(lines), []))
        assert "rsid" not in results[0]

    def test_extracts_multiple_fields(self):
        lines = [
            "chr1\t100\trs1\tA\tG\t.\tPASS\tCLNSIG=Pathogenic;CLNDN=disease;CLNREVSTAT=reviewed\tGT\t0/1\n"
        ]
        results = list(
            parse_vcf_stream(
                self._make_stream(lines), ["CLNSIG", "CLNDN", "CLNREVSTAT"]
            )
        )
        assert results[0]["CLNSIG"] == "Pathogenic"
        assert results[0]["CLNDN"] == "disease"
        assert results[0]["CLNREVSTAT"] == "reviewed"

    def test_skips_short_lines(self):
        lines = ["chr1\t100\n"]
        results = list(parse_vcf_stream(self._make_stream(lines), []))
        assert len(results) == 0

    def test_ann_field_extraction(self):
        ann = "T|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||"
        lines = [f"chr12\t21178615\trs4149056\tT\tC\t.\tPASS\tANN={ann}\tGT\t0/1\n"]
        results = list(parse_vcf_stream(self._make_stream(lines), ["ANN"]))
        assert results[0]["ANN"] == ann


# -- PatchDB tests --


class TestPatchDBCreate:
    def test_creates_database(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = PatchDB.create(db_path)
        assert db_path.exists()
        # Verify schema
        tables = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "annotations" in table_names
        assert "patch_metadata" in table_names
        db.close()

    def test_idempotent_create(self, tmp_path):
        db_path = tmp_path / "test.db"
        db1 = PatchDB.create(db_path)
        db1.close()
        db2 = PatchDB.create(db_path)
        db2.close()


class TestPatchDBReadWrite:
    @pytest.fixture
    def patch_db(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        yield db
        db.close()

    def test_populate_and_get(self, patch_db):
        lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST00000256958|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        count = patch_db.populate_from_snpeff_stream(iter(lines))
        assert count == 1

        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann is not None
        assert ann["rsid"] == "rs4149056"
        assert ann["gene"] == "SLCO1B1"
        assert ann["effect"] == "missense_variant"
        assert ann["impact"] == "MODERATE"

    def test_update_clinvar(self, patch_db):
        # First populate with SnpEff
        snpeff_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        patch_db.populate_from_snpeff_stream(iter(snpeff_lines))

        # Then update with ClinVar
        clinvar_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "CLNSIG=drug_response;CLNDN=Simvastatin_response;CLNREVSTAT=criteria_provided\t"
            "GT\t0/1\n"
        ]
        count = patch_db.update_clinvar_from_stream(iter(clinvar_lines))
        assert count == 1

        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["clnsig"] == "drug_response"
        assert ann["clndn"] == "Simvastatin_response"

    def test_update_gnomad(self, patch_db):
        snpeff_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        patch_db.populate_from_snpeff_stream(iter(snpeff_lines))

        gnomad_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\tAF=0.14;AF_grpmax=0.21\tGT\t0/1\n"
        ]
        count = patch_db.update_gnomad_from_stream(iter(gnomad_lines))
        assert count == 1

        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["af"] == pytest.approx(0.14)
        assert ann["af_grpmax"] == pytest.approx(0.21)

    def test_update_dbsnp(self, patch_db):
        # Populate without rsID
        snpeff_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        patch_db.populate_from_snpeff_stream(iter(snpeff_lines))
        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["rsid"] is None

        # Backfill from dbSNP
        dbsnp_lines = ["chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t.\tGT\t0/1\n"]
        count = patch_db.update_dbsnp_from_stream(iter(dbsnp_lines))
        assert count == 1

        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["rsid"] == "rs4149056"
        assert ann["rsid_source"] == "dbsnp"

    def test_dbsnp_does_not_overwrite_vcf_rsid(self, patch_db):
        # Populate with rsID from VCF
        snpeff_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        patch_db.populate_from_snpeff_stream(iter(snpeff_lines))

        # Try to overwrite with dbSNP
        dbsnp_lines = ["chr12\t21178615\trs9999999\tT\tC\t.\tPASS\t.\tGT\t0/1\n"]
        patch_db.update_dbsnp_from_stream(iter(dbsnp_lines))

        ann = patch_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["rsid"] == "rs4149056"  # not overwritten
        assert ann["rsid_source"] == "vcf"


class TestPatchDBLookup:
    @pytest.fixture
    def populated_db(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        snpeff_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n",
            "chr7\t117559590\trs113993960\tATCT\tA\t.\tPASS\t"
            "ANN=A|frameshift_variant|HIGH|CFTR|ENSG|transcript|ENST|protein_coding||c.1521_1523del|p.Phe508del||||||\t"
            "GT\t0/1\n",
        ]
        db.populate_from_snpeff_stream(iter(snpeff_lines))
        clinvar_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "CLNSIG=drug_response;CLNDN=Simvastatin_response;CLNREVSTAT=criteria_provided\t"
            "GT\t0/1\n",
            "chr7\t117559590\trs113993960\tATCT\tA\t.\tPASS\t"
            "CLNSIG=Pathogenic;CLNDN=Cystic_fibrosis;CLNREVSTAT=reviewed_by_expert_panel\t"
            "GT\t0/1\n",
        ]
        db.update_clinvar_from_stream(iter(clinvar_lines))
        yield db
        db.close()

    def test_lookup_rsid(self, populated_db):
        results = populated_db.lookup_rsid("rs4149056")
        assert len(results) == 1
        assert results[0]["gene"] == "SLCO1B1"

    def test_lookup_rsid_missing(self, populated_db):
        results = populated_db.lookup_rsid("rs999999999")
        assert len(results) == 0

    def test_lookup_rsids_batch(self, populated_db):
        results = populated_db.lookup_rsids(["rs4149056", "rs113993960", "rs999"])
        assert len(results["rs4149056"]) == 1
        assert len(results["rs113993960"]) == 1
        assert len(results["rs999"]) == 0

    def test_get_annotations_in_region(self, populated_db):
        results = populated_db.get_annotations_in_region("chr12", 21178600, 21178700)
        assert len(results) == 1
        key = (21178615, "T", "C")
        assert key in results
        assert results[key]["gene"] == "SLCO1B1"

    def test_query_clinvar_pathogenic(self, populated_db):
        results = populated_db.query_clinvar("Pathogenic")
        assert len(results) == 1
        assert results[0]["gene"] == "CFTR"

    def test_query_clinvar_with_region(self, populated_db):
        results = populated_db.query_clinvar(
            "drug_response", "chr12", 21178600, 21178700
        )
        assert len(results) == 1
        assert results[0]["rsid"] == "rs4149056"

    def test_query_clinvar_no_match(self, populated_db):
        results = populated_db.query_clinvar("Benign")
        assert len(results) == 0


class TestPatchDBMetadata:
    def test_set_and_get_metadata(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        db.set_metadata("snpeff", "5.2c")
        db.set_metadata("clinvar", "2026-03-01")
        meta = db.get_metadata()
        assert "snpeff" in meta
        assert meta["snpeff"]["version"] == "5.2c"
        assert meta["snpeff"]["status"] == "complete"
        assert "clinvar" in meta
        db.close()

    def test_vcf_fingerprint(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        # Create a dummy VCF file
        vcf_file = tmp_path / "test.vcf.gz"
        vcf_file.write_bytes(b"fake vcf data")
        db.store_vcf_fingerprint(vcf_file)
        assert db.check_vcf_fingerprint(vcf_file) is True

        # Modify the file
        vcf_file.write_bytes(b"modified vcf data")
        assert db.check_vcf_fingerprint(vcf_file) is False
        db.close()


class TestPatchDBClearLayer:
    @pytest.fixture
    def full_db(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        snpeff_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        db.populate_from_snpeff_stream(iter(snpeff_lines))
        clinvar_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "CLNSIG=drug_response;CLNDN=test;CLNREVSTAT=reviewed\tGT\t0/1\n"
        ]
        db.update_clinvar_from_stream(iter(clinvar_lines))
        gnomad_lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\tAF=0.14;AF_grpmax=0.21\tGT\t0/1\n"
        ]
        db.update_gnomad_from_stream(iter(gnomad_lines))
        yield db
        db.close()

    def test_clear_clinvar(self, full_db):
        full_db.clear_layer("clinvar")
        ann = full_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["clnsig"] is None
        assert ann["gene"] == "SLCO1B1"  # SnpEff fields untouched

    def test_clear_gnomad(self, full_db):
        full_db.clear_layer("gnomad")
        ann = full_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["af"] is None
        assert ann["af_grpmax"] is None
        assert ann["gene"] == "SLCO1B1"  # SnpEff fields untouched

    def test_clear_snpeff(self, full_db):
        full_db.clear_layer("snpeff")
        ann = full_db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["gene"] is None
        assert ann["clnsig"] == "drug_response"  # ClinVar untouched

    def test_clear_unknown_layer_raises(self, full_db):
        with pytest.raises(ValueError, match="Unsupported annotation layer"):
            full_db.clear_layer("unknown")


class TestPatchDBRsidCoverage:
    def test_empty_db(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        total, has_rsid = db.rsid_coverage()
        assert total == 0
        assert has_rsid == 0
        db.close()

    def test_all_have_rsids(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\tANN=C|missense|MODERATE|SLCO1B1||\n",
            "chr7\t117559590\trs113993960\tCTT\tC\t.\tPASS\tANN=C|frameshift|HIGH|CFTR||\n",
        ]
        db.populate_from_snpeff_stream(iter(lines))
        total, has_rsid = db.rsid_coverage()
        assert total == 2
        assert has_rsid == 2
        db.close()

    def test_none_have_rsids(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        lines = [
            "chr12\t21178615\t.\tT\tC\t.\tPASS\tANN=C|missense|MODERATE|SLCO1B1||\n",
            "chr7\t117559590\t.\tCTT\tC\t.\tPASS\tANN=C|frameshift|HIGH|CFTR||\n",
        ]
        db.populate_from_snpeff_stream(iter(lines))
        total, has_rsid = db.rsid_coverage()
        assert total == 2
        assert has_rsid == 0
        db.close()


class TestPatchDBEdgeCases:
    def test_lookup_rsids_empty_list(self, tmp_path):
        db = PatchDB.create(tmp_path / "test.db")
        result = db.lookup_rsids([])
        assert result == {}
        db.close()

    def test_upsert_preserves_other_layers(self, tmp_path):
        """INSERT...ON CONFLICT should not wipe ClinVar/gnomAD columns."""
        db = PatchDB.create(tmp_path / "test.db")
        # Populate with SnpEff
        snpeff_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        db.populate_from_snpeff_stream(iter(snpeff_lines))
        # Add ClinVar
        clinvar_lines = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "CLNSIG=drug_response;CLNDN=test;CLNREVSTAT=reviewed\tGT\t0/1\n"
        ]
        db.update_clinvar_from_stream(iter(clinvar_lines))
        # Re-run SnpEff (simulating incremental update)
        snpeff_lines_v2 = [
            "chr12\t21178615\trs4149056\tT\tC\t.\tPASS\t"
            "ANN=C|missense_variant|MODERATE|SLCO1B1|ENSG|transcript|ENST2|protein_coding||c.521T>C|p.Val174Ala||||||\t"
            "GT\t0/1\n"
        ]
        db.populate_from_snpeff_stream(iter(snpeff_lines_v2))
        # ClinVar should be preserved
        ann = db.get_annotation("chr12", 21178615, "T", "C")
        assert ann["clnsig"] == "drug_response"
        assert ann["transcript"] == "ENST2"  # SnpEff field updated
        db.close()
