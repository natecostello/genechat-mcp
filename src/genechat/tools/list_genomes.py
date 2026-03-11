"""List registered genomes — lets the LLM discover available genomes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from genechat.config import AppConfig
    from genechat.vcf_engine import VCFEngine


def register(mcp, engines: dict[str, VCFEngine], db, config: AppConfig):
    @mcp.tool()
    def list_genomes() -> str:
        """List all registered genomes with their labels and basic info.

        Use this tool FIRST to discover which genomes are available before
        querying variants, genes, or other genomic data. Returns genome labels,
        VCF paths, and annotation state for each registered genome.
        """
        if not engines:
            return "No genomes registered. Ask the user to run `genechat init <vcf>`."

        lines = [f"**{len(engines)} genome(s) registered:**\n"]

        for label, engine in engines.items():
            genome_cfg = config.genomes.get(label)
            if not genome_cfg:
                continue

            lines.append(f"### {label}")
            lines.append(f"- **VCF:** {genome_cfg.vcf_path}")
            lines.append(f"- **Build:** {genome_cfg.genome_build}")

            # Annotation state from patch.db
            if genome_cfg.patch_db and Path(genome_cfg.patch_db).exists():
                from genechat.patch import PatchDB

                patch = PatchDB(Path(genome_cfg.patch_db), readonly=True)
                try:
                    meta = patch.get_metadata()
                finally:
                    patch.close()

                layers = []
                for source in ["snpeff", "clinvar", "gnomad", "dbsnp"]:
                    info = meta.get(source, {})
                    if info and info.get("status") == "complete":
                        version = info.get("version", "")
                        layers.append(f"{source} ({version})" if version else source)
                if layers:
                    lines.append(f"- **Annotations:** {', '.join(layers)}")
                else:
                    lines.append("- **Annotations:** none")
            else:
                lines.append("- **Annotations:** not built (no patch.db)")

            lines.append("")

        if len(engines) == 1:
            lines.append(
                "*Only one genome registered — it will be used automatically "
                "when `genome` is omitted from tool calls.*"
            )
        else:
            lines.append(
                '*Multiple genomes registered — pass `genome="<label>"` '
                "to specify which one to query.*"
            )

        return "\n".join(lines)
