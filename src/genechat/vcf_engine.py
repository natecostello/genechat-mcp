"""VCF query engine using pysam."""

import re
from pathlib import Path

import pysam

from genechat.config import AppConfig
from genechat.parsers import parse_ann_field, parse_clinvar_fields, parse_genotype

REGION_PATTERN = re.compile(r"^chr[\dXYMT]{1,2}:\d+-\d+$")
RSID_PATTERN = re.compile(r"^rs\d+$")


class VCFEngineError(Exception):
    """Raised for VCF engine errors."""


class VCFEngine:
    """Read-only VCF query engine backed by pysam."""

    def __init__(self, config: AppConfig):
        self.vcf_path = Path(config.genome.vcf_path)
        self.max_variants = config.server.max_variants_per_response
        self._sample_name = config.genome.sample_name or None

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
        except Exception as e:
            raise VCFEngineError(f"Cannot open VCF: {e}") from e

    def annotation_versions(self, prefix: str = "GeneChat_") -> dict[str, str]:
        """Read ##GeneChat_* (or custom prefix) header lines from the VCF."""
        versions = {}
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                for rec in vcf.header.records:
                    if rec.type == "GENERIC" and rec.key.startswith(prefix):
                        label = rec.key[len(prefix) :]
                        versions[label] = rec.value
        except (OSError, ValueError) as e:
            raise VCFEngineError(f"Cannot read VCF headers: {e}") from e
        return versions

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

        # Open VCF once and iterate all regions with the same handle
        variants: list[dict] = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for r in regions:
                    for record in vcf.fetch(region=r):
                        if include_filter and not self._matches_filter(
                            record, include_filter
                        ):
                            continue
                        parsed = self._record_to_dict(record, sample_idx)
                        if parsed:
                            variants.append(parsed)
                        if len(variants) >= self.max_variants:
                            truncated = True
                            break
                    if truncated:
                        break
        except ValueError:
            # pysam raises ValueError for unknown contigs
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
        """Query a specific variant by rsID (e.g. rs4149056)."""
        if not RSID_PATTERN.match(rsid):
            raise ValueError(f"Invalid rsID format: {rsid}. Expected rs<digits>")
        # No region-based shortcut for rsID — must scan entire file.
        # rsIDs can repeat across records (different alleles, overlapping
        # representations), so collect all matches up to max_variants.
        variants: list[dict] = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for record in vcf:
                    if record.id != rsid:
                        continue
                    parsed = self._record_to_dict(record, sample_idx)
                    if parsed:
                        variants.append(parsed)
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
        """Query multiple rsIDs in a single VCF scan.

        Returns a dict mapping each rsID to its list of variant dicts.
        Much more efficient than calling query_rsid() repeatedly.
        """
        for rsid in rsids:
            if not RSID_PATTERN.match(rsid):
                raise ValueError(f"Invalid rsID format: {rsid}. Expected rs<digits>")

        target_set = set(rsids)
        results: dict[str, list[dict]] = {r: [] for r in rsids}
        found_count = 0
        truncated = False

        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for record in vcf:
                    if record.id and record.id in target_set:
                        parsed = self._record_to_dict(record, sample_idx)
                        if parsed:
                            results[record.id].append(parsed)
                            found_count += 1
                    if found_count >= self.max_variants:
                        truncated = True
                        break
        except Exception as e:
            raise VCFEngineError(f"Error querying rsIDs: {e}") from e

        if truncated:
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
        """Query variants by ClinVar clinical significance."""
        if region and not REGION_PATTERN.match(region):
            raise ValueError(f"Invalid region format: {region}")

        variants = []
        truncated = False
        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                if region:
                    iterator = vcf.fetch(region=region)
                else:
                    iterator = vcf.fetch()

                for record in iterator:
                    clnsig = self._get_info_str(record, "CLNSIG")
                    if not clnsig or significance.lower() not in clnsig.lower():
                        continue
                    parsed = self._record_to_dict(record, sample_idx)
                    if parsed:
                        variants.append(parsed)
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
        """Compute basic variant statistics by iterating all records.

        Returns a dict with counts for:
        - 'Total variants'
        - 'SNPs'
        - 'Indels'
        - 'Multi-allelic'
        """
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
                    # Classify at record level so counts are comparable to Total
                    is_snp = all(len(record.ref) == 1 and len(a) == 1 for a in alts)
                    if is_snp:
                        counts["SNPs"] += 1
                    else:
                        counts["Indels"] += 1
        except Exception as e:
            raise VCFEngineError(f"Error computing stats: {e}") from e
        return counts

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

        try:
            with pysam.VariantFile(str(self.vcf_path)) as vcf:
                sample_idx = self._get_sample_index()
                for record in vcf.fetch(region=region):
                    if include_filter and not self._matches_filter(
                        record, include_filter
                    ):
                        continue
                    parsed = self._record_to_dict(record, sample_idx)
                    if parsed:
                        variants.append(parsed)
                    if len(variants) >= cap:
                        truncated = True
                        break
        except ValueError:
            # pysam raises ValueError for invalid regions (e.g. unknown contig)
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

    def _matches_filter(self, record: pysam.VariantRecord, filt: str) -> bool:
        """Basic filter matching for impact level strings.

        Supports plain strings like 'HIGH' and bcftools-style expressions
        like 'INFO/ANN~"HIGH"'.
        """
        # e.g. 'INFO/ANN~"HIGH"' or plain impact strings like 'HIGH'.
        try:
            # If the filter looks like INFO/ANN~"VALUE", extract VALUE.
            search = filt
            match = re.search(r'~"([^"]+)"', filt)
            if match:
                search = match.group(1)
            if not search:
                return False
            ann = self._get_info_str(record, "ANN")
            if ann and search.upper() in ann.upper():
                return True
        except Exception:
            # On any error retrieving/processing the ANN field, treat as no match.
            pass
        return False

    def _record_to_dict(
        self, record: pysam.VariantRecord, sample_idx: int
    ) -> dict | None:
        """Convert a pysam VariantRecord to a variant dict."""
        alt = ",".join(record.alts) if record.alts else "."
        rsid = record.id if record.id and record.id != "." else None

        # Genotype
        sample = record.samples[sample_idx]
        alleles = sample.alleles
        if alleles and all(a is not None for a in alleles):
            # Reconstruct GT-style display for parse_genotype
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

        # SnpEff ANN
        ann_raw = self._get_info_str(record, "ANN")
        annotation = parse_ann_field(ann_raw) if ann_raw else {}

        # ClinVar
        clnsig = self._get_info_str(record, "CLNSIG")
        clndn = self._get_info_str(record, "CLNDN")
        clnrevstat = self._get_info_str(record, "CLNREVSTAT")
        clinvar = parse_clinvar_fields(clnsig or "", clndn or "", clnrevstat or "")

        # Population frequencies
        af = self._get_info_float(record, "AF")
        af_popmax = self._get_info_float(record, "AF_popmax")
        if af_popmax is None:
            af_popmax = self._get_info_float(record, "AF_grpmax")
        population_freq = _parse_freq(af, af_popmax)

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

    @staticmethod
    def _get_info_str(record: pysam.VariantRecord, key: str) -> str | None:
        """Safely get an INFO field as a string. Handles tuples from Number=. fields."""
        try:
            val = record.info[key]
        except KeyError:
            return None
        if val is None:
            return None
        if isinstance(val, tuple):
            return ",".join(str(v) for v in val)
        return str(val)

    @staticmethod
    def _get_info_float(record: pysam.VariantRecord, key: str) -> float | None:
        """Safely get an INFO field as a float. Handles tuples from Number=A fields."""
        try:
            val = record.info[key]
        except KeyError:
            return None
        if val is None:
            return None
        if isinstance(val, tuple):
            return float(val[0]) if val else None
        return float(val)


def _parse_freq(af: float | None, af_popmax: float | None) -> dict:
    """Build population frequency dict from parsed floats."""
    result = {}
    if af is not None:
        result["global"] = af
    if af_popmax is not None:
        result["popmax"] = af_popmax
    return result
