"""TOML config loader for GeneChat."""

import os
import tomllib
from importlib import resources
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel


class GenomeConfig(BaseModel):
    vcf_path: str = ""
    genome_build: str = "GRCh38"
    sample_name: str = ""
    patch_db: str = ""


class DatabasesConfig(BaseModel):
    lookup_db: str = ""


class ServerConfig(BaseModel):
    transport: str = "stdio"
    host: str = "localhost"
    port: int = 3001
    max_variants_per_response: int = 100


class DisplayConfig(BaseModel):
    include_population_freq: bool = True
    include_raw_annotation: bool = False


class AppConfig(BaseModel):
    genome: GenomeConfig = GenomeConfig()
    genomes: dict[str, GenomeConfig] = {}
    databases: DatabasesConfig = DatabasesConfig()
    server: ServerConfig = ServerConfig()
    display: DisplayConfig = DisplayConfig()
    default_genome: str = ""

    def model_post_init(self, __context: object) -> None:
        """Normalize genome config: ensure genomes dict is populated."""
        # If genomes dict has entries, use it as-is
        if self.genomes:
            # Sync legacy genome field with the first genome for backward compat
            if not self.genome.vcf_path:
                first_label = next(iter(self.genomes))
                self.genome = self.genomes[first_label]
            if not self.default_genome:
                self.default_genome = next(iter(self.genomes))
        elif self.genome.vcf_path:
            # Legacy [genome] section → treat as genomes["default"]
            self.genomes = {"default": self.genome}
            if not self.default_genome:
                self.default_genome = "default"
        # If neither is set, leave both empty (no VCF configured)

    @property
    def lookup_db_path(self) -> str:
        """Return the lookup DB path, defaulting to package data."""
        if self.databases.lookup_db:
            return self.databases.lookup_db
        return str(_default_db_path())


def _default_db_path() -> Path:
    """Locate the built-in lookup_tables.db from package data."""
    ref = resources.files("genechat") / "data" / "lookup_tables.db"
    # For installed packages, this may be a traversable; resolve to a real path
    with resources.as_file(ref) as p:
        return Path(p)


def _find_config_file() -> Path | None:
    """Search for config.toml in standard locations."""
    # 1. GENECHAT_CONFIG env var
    env_path = os.environ.get("GENECHAT_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 2. XDG config directory
    xdg = Path(user_config_dir("genechat")) / "config.toml"
    if xdg.exists():
        return xdg

    # 3. Current working directory
    local = Path("config.toml")
    if local.exists():
        return local

    return None


def write_config(
    vcf_path: Path,
    config_dir: Path,
    sample_name: str = "",
    label: str = "",
) -> Path:
    """Write or update config.toml with the given VCF path.

    If ``label`` is provided, writes to ``[genomes.<label>]``.
    If no label, writes to ``[genomes.default]``.
    Preserves existing settings (server, display, other genomes) if the config
    already exists. Returns the config file path.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    label = label or "default"

    # Read existing config to preserve all settings
    data: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            import sys as _sys

            print(
                f"Error: Existing config is corrupt: {config_path}",
                file=_sys.stderr,
            )
            print(
                "  Fix or delete the file manually, then retry.",
                file=_sys.stderr,
            )
            _sys.exit(1)

    # Migrate legacy [genome] to [genomes.default] if present
    if "genome" in data and "genomes" not in data:
        data["genomes"] = {"default": data.pop("genome")}
    elif "genome" in data and "genomes" in data:
        # Legacy [genome] exists alongside [genomes.*] — merge into default
        data["genomes"].setdefault("default", {}).update(data.pop("genome"))

    # Update the target genome label
    genomes = data.setdefault("genomes", {})
    genome = genomes.setdefault(label, {})
    genome["vcf_path"] = str(vcf_path)
    if sample_name:
        genome["sample_name"] = sample_name

    content = _serialize_config(data)

    # Write via temp file with 0o600 permissions, then atomically replace.
    tmp_path = config_path.with_suffix(".tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, config_path)

    return config_path


def _serialize_value(key: str, val: object) -> str | None:
    """Serialize a single TOML key-value pair. Returns None to skip."""
    if isinstance(val, str) and not val:
        return None  # Skip unset string fields
    if isinstance(val, bool):
        return f"{key} = {'true' if val else 'false'}"
    if isinstance(val, (int, float)):
        return f"{key} = {val}"
    s = str(val).replace("\\", "\\\\").replace('"', '\\"')
    return f'{key} = "{s}"'


def _serialize_config(data: dict) -> str:
    """Serialize config dict to TOML. Handles nested tables (e.g. genomes.*)."""
    lines = []
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        # Check if this is a table of tables (e.g. genomes with sub-dicts)
        has_subtables = any(isinstance(v, dict) for v in values.values())
        if has_subtables:
            for sub_key, sub_values in values.items():
                if isinstance(sub_values, dict):
                    lines.append(f"[{section}.{sub_key}]")
                    for key, val in sub_values.items():
                        line = _serialize_value(key, val)
                        if line:
                            lines.append(line)
                    lines.append("")
                else:
                    # Mixed table — top-level keys before subtables
                    line = _serialize_value(sub_key, sub_values)
                    if line:
                        lines.insert(
                            next(
                                (
                                    i
                                    for i, ln in enumerate(lines)
                                    if ln.startswith(f"[{section}.")
                                ),
                                len(lines),
                            ),
                            line,
                        )
        else:
            lines.append(f"[{section}]")
            for key, val in values.items():
                line = _serialize_value(key, val)
                if line:
                    lines.append(line)
            lines.append("")
    return "\n".join(lines)


def load_config(path: str | None = None) -> AppConfig:
    """Load config from a TOML file. Falls back to defaults if no file found.

    Supports env vars:
    - GENECHAT_VCF: shortcut for a single-genome vcf_path
    - GENECHAT_GENOME: select default genome label
    """
    config_path = Path(path) if path else _find_config_file()

    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        config = AppConfig(**data)
    else:
        config = AppConfig()

    # GENECHAT_VCF env var: add as genomes["default"] if no genomes configured
    vcf_env = os.environ.get("GENECHAT_VCF")
    if vcf_env and not config.genomes:
        genome_cfg = GenomeConfig(vcf_path=vcf_env)
        config.genomes = {"default": genome_cfg}
        config.genome = genome_cfg
        config.default_genome = "default"

    # GENECHAT_GENOME env var: override default genome label
    genome_env = os.environ.get("GENECHAT_GENOME")
    if genome_env and genome_env in config.genomes:
        config.default_genome = genome_env

    return config
