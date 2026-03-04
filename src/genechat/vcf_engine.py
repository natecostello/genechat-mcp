"""VCF query engine wrapping bcftools."""

import re
import shutil
import subprocess
from pathlib import Path

from genechat.config import AppConfig
from genechat.parsers import parse_ann_field, parse_clinvar_fields, parse_genotype

REGION_PATTERN = re.compile(r"^chr[\dXYMT]{1,2}:\d+-\d+$")
RSID_PATTERN = re.compile(r"^rs\d+$")

# bcftools query format — extracts all fields we need per variant
QUERY_FORMAT = (
    "%CHROM\\t%POS\\t%ID\\t%REF\\t%ALT\\t"
    "%INFO/ANN\\t%INFO/CLNSIG\\t%INFO/CLNDN\\t"
    "%INFO/CLNREVSTAT\\t%INFO/AF\\t%INFO/AF_popmax"
    "[\\t%GT]\\n"
)


class VCFEngineError(Exception):
    """Raised for VCF engine errors."""


class VCFEngine:
    """Read-only VCF query engine backed by bcftools."""

    def __init__(self, config: AppConfig):
        self.vcf_path = Path(config.genome.vcf_path)
        self.timeout = config.server.bcftools_timeout
        self.max_variants = config.server.max_variants_per_response

        if not shutil.which("bcftools"):
            raise VCFEngineError(
                "bcftools not found in PATH. "
                "Install with: conda install -c bioconda bcftools"
            )
        if not self.vcf_path.exists():
            raise FileNotFoundError(f"VCF file not found: {self.vcf_path}")
        tbi = Path(f"{self.vcf_path}.tbi")
        csi = Path(f"{self.vcf_path}.csi")
        if not tbi.exists() and not csi.exists():
            raise FileNotFoundError(
                f"VCF index not found. Run: tabix -p vcf {self.vcf_path}"
            )

    def query_region(
        self, region: str, include_filter: str | None = None
    ) -> list[dict]:
        """Query variants in a genomic region (e.g. chr22:42126000-42130000)."""
        if not REGION_PATTERN.match(region):
            raise ValueError(
                f"Invalid region format: {region}. Expected chr<N>:<start>-<end>"
            )
        cmd = [
            "bcftools", "query",
            "-f", QUERY_FORMAT,
            "-r", region,
        ]
        if include_filter:
            cmd.extend(["-i", include_filter])
        cmd.append(str(self.vcf_path))
        return self._execute_and_parse(cmd)

    def query_regions(
        self, regions: list[str], include_filter: str | None = None
    ) -> list[dict]:
        """Query variants across multiple genomic regions."""
        for r in regions:
            if not REGION_PATTERN.match(r):
                raise ValueError(f"Invalid region format: {r}")
        cmd = [
            "bcftools", "query",
            "-f", QUERY_FORMAT,
            "-r", ",".join(regions),
        ]
        if include_filter:
            cmd.extend(["-i", include_filter])
        cmd.append(str(self.vcf_path))
        return self._execute_and_parse(cmd)

    def query_rsid(self, rsid: str) -> list[dict]:
        """Query a specific variant by rsID (e.g. rs4149056)."""
        if not RSID_PATTERN.match(rsid):
            raise ValueError(
                f"Invalid rsID format: {rsid}. Expected rs<digits>"
            )
        cmd = [
            "bcftools", "query",
            "-f", QUERY_FORMAT,
            "-i", f'ID="{rsid}"',
            str(self.vcf_path),
        ]
        return self._execute_and_parse(cmd)

    def query_clinvar(
        self, significance: str, region: str | None = None
    ) -> list[dict]:
        """Query variants by ClinVar clinical significance."""
        filt = f'INFO/CLNSIG~"{significance}"'
        cmd = [
            "bcftools", "query",
            "-f", QUERY_FORMAT,
            "-i", filt,
        ]
        if region:
            if not REGION_PATTERN.match(region):
                raise ValueError(f"Invalid region format: {region}")
            cmd.extend(["-r", region])
        cmd.append(str(self.vcf_path))
        return self._execute_and_parse(cmd)

    def stats(self) -> str:
        """Run bcftools stats and return raw output."""
        cmd = ["bcftools", "stats", str(self.vcf_path)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise VCFEngineError(f"bcftools stats failed: {result.stderr}")
        return result.stdout

    def _execute_and_parse(self, cmd: list[str]) -> list[dict]:
        """Execute bcftools command and parse output into variant dicts."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise VCFEngineError(
                f"bcftools query timed out after {self.timeout}s. "
                "Try narrowing your query region."
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "no such INFO" in stderr or "not found" in stderr.lower():
                return []
            raise VCFEngineError(f"bcftools error: {stderr}")

        variants = []
        truncated = False
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parsed = self._parse_line(line)
            if parsed:
                variants.append(parsed)
            if len(variants) >= self.max_variants:
                truncated = True
                break

        if truncated and variants:
            variants[-1]["_truncated"] = True
            variants[-1]["_truncation_notice"] = (
                f"Results capped at {self.max_variants} variants. "
                "Narrow your query for complete results."
            )

        return variants

    def _parse_line(self, line: str) -> dict | None:
        """Parse a single bcftools query output line into a variant dict."""
        parts = line.split("\t")
        if len(parts) < 11:
            return None

        chrom, pos_str, rsid, ref, alt = parts[0], parts[1], parts[2], parts[3], parts[4]
        ann_raw, clnsig, clndn, clnrevstat = parts[5], parts[6], parts[7], parts[8]
        af_raw, af_popmax_raw = parts[9], parts[10]
        gt = parts[11] if len(parts) > 11 else "."

        try:
            pos = int(pos_str)
        except ValueError:
            return None

        variant = {
            "chrom": chrom,
            "pos": pos,
            "rsid": rsid if rsid != "." else None,
            "ref": ref,
            "alt": alt,
            "genotype": parse_genotype(gt, ref, alt),
            "annotation": parse_ann_field(ann_raw),
            "clinvar": parse_clinvar_fields(clnsig, clndn, clnrevstat),
            "population_freq": _parse_freq(af_raw, af_popmax_raw),
        }
        return variant


def _parse_freq(af_raw: str, af_popmax_raw: str) -> dict:
    """Parse allele frequency fields."""
    result = {}
    if af_raw and af_raw != ".":
        try:
            result["global"] = float(af_raw)
        except ValueError:
            pass
    if af_popmax_raw and af_popmax_raw != ".":
        try:
            result["popmax"] = float(af_popmax_raw)
        except ValueError:
            pass
    return result
