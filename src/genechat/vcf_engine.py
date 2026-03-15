"""VCF query engine using pysam, with patch.db annotations."""

import re
import warnings
from pathlib import Path

import pysam

from genechat.config import AppConfig, GenomeConfig
from genechat.parsers import parse_clinvar_fields, parse_genotype
from genechat.patch import PatchDB

REGION_PATTERN = re.compile(r"^chr[\dXYMT]{1,2}:\d+-\d+$")
RSID_PATTERN = re.compile(r"^rs\d+$")


class VCFEngineError(Exception):
    """Raised for VCF engine errors."""


class VCFEngine:
    """Read-only VCF query engine backed by pysam.

    Genotypes are read from the VCF. Annotations (SnpEff, ClinVar, gnomAD)
    are read from a SQLite patch.db when configured.
    """

    def __init__(self, config: AppConfig | GenomeConfig, *, max_variants: int = 100):
        # Accept either AppConfig or GenomeConfig (multi-genome)
        if isinstance(config, AppConfig):
            if len(config.genomes) != 1:
                raise VCFEngineError(
                    "VCFEngine must be constructed with a single genome when "
                    "given an AppConfig. In multi-genome setups, pass a "
                    "GenomeConfig (or explicit genome label) instead."
                )
            (genome_cfg,) = config.genomes.values()
            max_variants = config.server.max_variants_per_response
        else:
            genome_cfg = config
        self.vcf_path = Path(genome_cfg.vcf_path)
        self.max_variants = max_variants
        self._sample_name = genome_cfg.sample_name or None

        if not self.vcf_path.exists():
            raise FileNotFoundError(
                f"VCF file not found: {self.vcf_path}. "
                "If your VCF is on an encrypted or external volume, "
                "make sure it is mounted before starting GeneChat."
            )
        tbi = Path(f"{self.vcf_path}.tbi")
        csi = Path(f"{self.vcf_path}.csi")
        if not tbi.exists() and not csi.exists():
            raise FileNotFoundError(
                f"VCF index not found for {self.vcf_path}. "
                "Create one with pysam.tabix_index(..., preset='vcf') or "
                "tabix -p vcf <file>."
            )

        # Validate the file can be opened
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                self._samples = list(vcf.header.samples)
                # Detect whether VCF uses chr-prefixed contig names.
                # Check multiple canonical contigs (including mito) to
                # handle panel/subset VCFs that may not include chr1.
                self._vcf_contigs = set(vcf.header.contigs)
                _CANONICAL_CHR = (
                    "chr1",
                    "chr2",
                    "chr22",
                    "chrX",
                    "chrM",
                    "chrMT",
                )
                self._vcf_uses_chr = any(c in self._vcf_contigs for c in _CANONICAL_CHR)
        except Exception as e:
            raise VCFEngineError(f"Cannot open VCF: {e}") from e

        # Open patch database if configured
        patch_db_path = Path(genome_cfg.patch_db) if genome_cfg.patch_db else None
        if patch_db_path and patch_db_path.exists():
            self._patch = PatchDB(patch_db_path, readonly=True)
            if not self._patch.check_vcf_fingerprint(self.vcf_path):
                warnings.warn(
                    "Raw VCF has changed since patch.db was built. "
                    "Rebuild the patch database to pick up VCF changes.",
                    stacklevel=2,
                )
        elif patch_db_path and not patch_db_path.exists():
            warnings.warn(
                f"Configured patch_db not found: {patch_db_path}. "
                "Annotations will be unavailable, and rsID/ClinVar-based queries "
                "(query_rsid, query_rsids, query_clinvar) will fail until patch.db "
                "is built. Build the patch database with: genechat annotate --all",
                stacklevel=2,
            )
            self._patch = None
        else:
            self._patch = None

    def close(self):
        """Close the patch database connection if open."""
        if self._patch:
            self._patch.close()
            self._patch = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # Map patch_metadata keys to display labels
    _LABEL_MAP = {
        "snpeff": "SnpEff",
        "clinvar": "ClinVar",
        "gnomad": "gnomAD",
        "dbsnp": "dbSNP",
    }

    def annotation_versions(self) -> dict[str, str]:
        """Read annotation version info from patch.db metadata."""
        if not self._patch:
            return {}
        meta = self._patch.get_metadata()
        return {
            self._LABEL_MAP.get(k, k): v["version"]
            for k, v in meta.items()
            if v["status"] == "complete" and k != "vcf_fingerprint"
        }

    def _to_vcf_chrom(self, chrom: str) -> str:
        """Convert a chrom name (from patch.db) to the VCF's contig format.

        Handles both directions: adds 'chr' prefix when VCF uses it,
        strips 'chr' prefix when VCF uses bare contig names. For
        mitochondrial contigs (M/MT), checks actual VCF header contigs
        to pick the correct spelling.
        """
        from genechat.patch import normalize_chrom

        bare = normalize_chrom(chrom)

        # Special handling for mito: VCFs use chrM or chrMT (or M/MT)
        if bare == "MT":
            for candidate in ("chrM", "chrMT", "M", "MT"):
                if candidate in self._vcf_contigs:
                    return candidate
            # Fallback: apply general prefix rule
            return "chrMT" if self._vcf_uses_chr else "MT"

        if self._vcf_uses_chr:
            return f"chr{bare}"
        return bare

    def _get_sample_index(self) -> int:
        """Return the sample index to use (0 unless sample_name specified)."""
        if self._sample_name:
            try:
                return self._samples.index(self._sample_name)
            except ValueError:
                raise VCFEngineError(
                    f"Sample '{self._sample_name}' not found. "
                    f"Available: {', '.join(self._samples)}"
                )
        return 0

    def query_region(
        self, region: str, include_filter: str | None = None
    ) -> list[dict]:
        """Query variants in a genomic region (e.g. chr22:42126000-42130000)."""
        if not REGION_PATTERN.match(region):
            raise ValueError(
                f"Invalid region format: {region}. Expected chr<N>:<start>-<end>"
            )
        return self._fetch_and_parse(region=region, include_filter=include_filter)

    def query_regions(
        self, regions: list[str], include_filter: str | None = None
    ) -> list[dict]:
        """Query variants across multiple genomic regions."""
        for r in regions:
            if not REGION_PATTERN.match(r):
                raise ValueError(f"Invalid region format: {r}")

        variants: list[dict] = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for r in regions:
                    patch_dict = self._get_patch_dict_for_region(r)
                    for record in vcf.fetch(region=r):
                        parsed = self._record_to_dict(record, sample_idx, patch_dict)
                        if parsed:
                            if include_filter and not self._matches_filter_from_dict(
                                parsed, include_filter
                            ):
                                continue
                            variants.append(parsed)
                        if len(variants) >= self.max_variants:
                            truncated = True
                            break
                    if truncated:
                        break
        except ValueError:
            pass
        except Exception as e:
            raise VCFEngineError(f"Error querying regions: {e}") from e

        if truncated and variants:
            variants[-1]["_truncated"] = True
            variants[-1]["_truncation_notice"] = (
                f"Results capped at {self.max_variants} variants. "
                "Narrow your query for complete results."
            )
        return variants

    def query_rsid(self, rsid: str) -> list[dict]:
        """Query a specific variant by rsID using patch.db index."""
        if not RSID_PATTERN.match(rsid):
            raise ValueError(f"Invalid rsID format: {rsid}. Expected rs<digits>")

        if not self._patch:
            raise VCFEngineError(
                "rsID queries require a patch database. Run: genechat annotate --all"
            )

        patch_rows = self._patch.lookup_rsid(rsid)
        if not patch_rows:
            return []

        variants = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for pr in patch_rows:
                    vcf_chrom = self._to_vcf_chrom(pr["chrom"])
                    region = f"{vcf_chrom}:{pr['pos']}-{pr['pos']}"
                    try:
                        for record in vcf.fetch(region=region):
                            alt = ",".join(record.alts) if record.alts else "."
                            if (
                                record.pos == pr["pos"]
                                and record.ref == pr["ref"]
                                and alt == pr["alt"]
                            ):
                                parsed = self._record_to_dict(
                                    record, sample_idx, patch_override=pr
                                )
                                if parsed:
                                    variants.append(parsed)
                    except ValueError:
                        continue
                    if len(variants) >= self.max_variants:
                        truncated = True
                        break
        except Exception as e:
            raise VCFEngineError(f"Error querying rsID {rsid}: {e}") from e
        if truncated and variants:
            variants[-1]["_truncated"] = True
            variants[-1]["_truncation_notice"] = (
                f"Results capped at {self.max_variants} variants. "
                "Narrow your query for complete results."
            )
        return variants

    def query_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        """Query multiple rsIDs using patch.db batch lookup."""
        if not rsids:
            return {}
        for rsid in rsids:
            if not RSID_PATTERN.match(rsid):
                raise ValueError(f"Invalid rsID format: {rsid}. Expected rs<digits>")

        if not self._patch:
            raise VCFEngineError(
                "rsID queries require a patch database. Run: genechat annotate --all"
            )

        patch_results = self._patch.lookup_rsids(rsids)
        results: dict[str, list[dict]] = {r: [] for r in rsids}
        found_count = 0

        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                capped = False
                for rsid, patch_rows in patch_results.items():
                    for pr in patch_rows:
                        vcf_chrom = self._to_vcf_chrom(pr["chrom"])
                        region = f"{vcf_chrom}:{pr['pos']}-{pr['pos']}"
                        try:
                            for record in vcf.fetch(region=region):
                                alt = ",".join(record.alts) if record.alts else "."
                                if (
                                    record.pos == pr["pos"]
                                    and record.ref == pr["ref"]
                                    and alt == pr["alt"]
                                ):
                                    parsed = self._record_to_dict(
                                        record, sample_idx, patch_override=pr
                                    )
                                    if parsed:
                                        results[rsid].append(parsed)
                                        found_count += 1
                                        if found_count >= self.max_variants:
                                            capped = True
                                            break
                        except ValueError:
                            continue
                        if capped:
                            break
                    if capped:
                        break
        except Exception as e:
            raise VCFEngineError(f"Error querying rsIDs: {e}") from e
        if found_count >= self.max_variants:
            results["_truncated"] = [
                {
                    "_truncated": True,
                    "_truncation_notice": (
                        f"Results capped at {self.max_variants} variants. "
                        "Some rsIDs may not have been reached."
                    ),
                }
            ]
        return results

    def query_clinvar(self, significance: str, region: str | None = None) -> list[dict]:
        """Query variants by ClinVar clinical significance using patch.db."""
        if region and not REGION_PATTERN.match(region):
            raise ValueError(f"Invalid region format: {region}")

        if not self._patch:
            raise VCFEngineError(
                "ClinVar queries require a patch database. Run: genechat annotate --all"
            )

        if region:
            chrom, coords = region.split(":")
            start, end = coords.split("-")
            patch_rows = self._patch.query_clinvar(
                significance, chrom, int(start), int(end)
            )
        else:
            patch_rows = self._patch.query_clinvar(significance)

        variants = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for pr in patch_rows:
                    vcf_chrom = self._to_vcf_chrom(pr["chrom"])
                    region_str = f"{vcf_chrom}:{pr['pos']}-{pr['pos']}"
                    try:
                        for record in vcf.fetch(region=region_str):
                            alt = ",".join(record.alts) if record.alts else "."
                            if (
                                record.pos == pr["pos"]
                                and record.ref == pr["ref"]
                                and alt == pr["alt"]
                            ):
                                parsed = self._record_to_dict(
                                    record, sample_idx, patch_override=pr
                                )
                                if parsed:
                                    variants.append(parsed)
                    except ValueError:
                        continue
                    if len(variants) >= self.max_variants:
                        truncated = True
                        break
        except Exception as e:
            if isinstance(e, VCFEngineError):
                raise
            raise VCFEngineError(f"Error querying ClinVar: {e}") from e

        if truncated and variants:
            variants[-1]["_truncated"] = True
            variants[-1]["_truncation_notice"] = (
                f"Results capped at {self.max_variants} variants. "
                "Narrow your query for complete results."
            )
        return variants

    def stats(self) -> dict:
        """Compute basic variant statistics by iterating all records."""
        counts = {
            "Total variants": 0,
            "SNPs": 0,
            "Indels": 0,
            "Multi-allelic": 0,
        }
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                for record in vcf:
                    counts["Total variants"] += 1
                    alts = record.alts or ()
                    if len(alts) > 1:
                        counts["Multi-allelic"] += 1
                    if not alts:
                        continue
                    is_snp = all(len(record.ref) == 1 and len(a) == 1 for a in alts)
                    if is_snp:
                        counts["SNPs"] += 1
                    else:
                        counts["Indels"] += 1
        except Exception as e:
            raise VCFEngineError(f"Error computing stats: {e}") from e
        return counts

    def _get_patch_dict_for_region(self, region: str) -> dict[tuple, dict] | None:
        """Pre-fetch patch annotations for a region. Returns None if no patch.db."""
        if not self._patch:
            return None
        chrom, coords = region.split(":")
        start, end = coords.split("-")
        return self._patch.get_annotations_in_region(chrom, int(start), int(end))

    def _fetch_and_parse(
        self,
        region: str,
        include_filter: str | None = None,
        remaining: int | None = None,
    ) -> list[dict]:
        """Fetch variants from a region and parse into dicts."""
        cap = remaining if remaining is not None else self.max_variants
        variants = []
        truncated = False

        patch_dict = self._get_patch_dict_for_region(region)

        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for record in vcf.fetch(region=region):
                    parsed = self._record_to_dict(record, sample_idx, patch_dict)
                    if parsed:
                        if include_filter and not self._matches_filter_from_dict(
                            parsed, include_filter
                        ):
                            continue
                        variants.append(parsed)
                    if len(variants) >= cap:
                        truncated = True
                        break
        except ValueError:
            return []
        except Exception as e:
            if isinstance(e, (VCFEngineError, ValueError)):
                raise
            raise VCFEngineError(f"Error querying region {region}: {e}") from e

        if truncated and variants:
            variants[-1]["_truncated"] = True
            variants[-1]["_truncation_notice"] = (
                f"Results capped at {self.max_variants} variants. "
                "Narrow your query for complete results."
            )
        return variants

    def _matches_filter_from_dict(self, variant_dict: dict, filt: str) -> bool:
        """Check filter against variant dict annotation fields."""
        search = filt
        match = re.search(r'~"([^"]+)"', filt)
        if match:
            search = match.group(1)
        if not search:
            return False
        search_upper = search.upper()
        ann = variant_dict.get("annotation", {})
        for field in ("impact", "effect", "gene", "transcript", "hgvs_c", "hgvs_p"):
            val = ann.get(field)
            if val and search_upper in val.upper():
                return True
        return False

    def _record_to_dict(
        self,
        record: pysam.VariantRecord,
        sample_idx: int,
        patch_dict: dict[tuple, dict] | None = None,
        patch_override: dict | None = None,
    ) -> dict | None:
        """Convert a pysam VariantRecord to a variant dict.

        Annotations come from patch_dict (region batch) or
        patch_override (single-variant lookup). Genotypes always
        come from the VCF.
        """
        alt = ",".join(record.alts) if record.alts else "."

        # Genotype: always from VCF
        sample = record.samples[sample_idx]
        alleles = sample.alleles
        if alleles and all(a is not None for a in alleles):
            ref = record.ref
            alts_list = list(record.alts or [])
            allele_map = {ref: "0"}
            for i, a in enumerate(alts_list, 1):
                allele_map[a] = str(i)
            sep = "|" if sample.phased else "/"
            gt_str = sep.join(allele_map.get(a, ".") for a in alleles)
            genotype = parse_genotype(gt_str, ref, alt)
        else:
            genotype = {"display": "no call", "zygosity": "no_call"}

        # Get patch row if available
        patch_row = patch_override
        if patch_row is None and patch_dict is not None:
            patch_row = patch_dict.get((record.pos, record.ref, alt))

        if patch_row:
            # Annotations from patch.db
            rsid = patch_row.get("rsid")
            annotation = {}
            if patch_row.get("gene"):
                annotation = {
                    "gene": patch_row["gene"],
                    "effect": patch_row.get("effect"),
                    "impact": patch_row.get("impact"),
                    "transcript": patch_row.get("transcript"),
                    "hgvs_c": patch_row.get("hgvs_c"),
                    "hgvs_p": patch_row.get("hgvs_p"),
                }
            clinvar = parse_clinvar_fields(
                patch_row.get("clnsig") or "",
                patch_row.get("clndn") or "",
                patch_row.get("clnrevstat") or "",
            )
            af = patch_row.get("af")
            af_grpmax = patch_row.get("af_grpmax")
            population_freq = _parse_freq(af, af_grpmax)
        else:
            # No patch data — return variant with genotype only
            rsid = record.id if record.id and record.id != "." else None
            annotation = {}
            clinvar = {}
            population_freq = {}

        return {
            "chrom": record.chrom,
            "pos": record.pos,
            "rsid": rsid,
            "ref": record.ref,
            "alt": alt,
            "genotype": genotype,
            "annotation": annotation,
            "clinvar": clinvar,
            "population_freq": population_freq,
        }


def _parse_freq(af: float | None, af_popmax: float | None) -> dict:
    """Build population frequency dict from parsed floats."""
    result = {}
    if af is not None:
        result["global"] = af
    if af_popmax is not None:
        result["popmax"] = af_popmax
    return result
