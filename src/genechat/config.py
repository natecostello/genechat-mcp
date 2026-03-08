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
    databases: DatabasesConfig = DatabasesConfig()
    server: ServerConfig = ServerConfig()
    display: DisplayConfig = DisplayConfig()

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


def write_config(vcf_path: Path, config_dir: Path, sample_name: str = "") -> Path:
    """Write or update config.toml with the given VCF path.

    Preserves existing settings (server, display, patch_db) if the config
    already exists. Returns the config file path.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    # Read existing config to preserve all settings
    data: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            data = {}

    # Update genome section, preserving other genome fields (e.g. patch_db)
    genome = data.setdefault("genome", {})
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


def _serialize_config(data: dict) -> str:
    """Serialize config dict to TOML. Handles str, int, float, bool values."""
    lines = []
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in values.items():
            if isinstance(val, str) and not val:
                continue  # Skip unset string fields
            if isinstance(val, bool):
                lines.append(f"{key} = {'true' if val else 'false'}")
            elif isinstance(val, (int, float)):
                lines.append(f"{key} = {val}")
            else:
                s = str(val).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{s}"')
        lines.append("")
    return "\n".join(lines)


def load_config(path: str | None = None) -> AppConfig:
    """Load config from a TOML file. Falls back to defaults if no file found.

    Supports GENECHAT_VCF env var as a shortcut for genome.vcf_path,
    useful for simple setups where a config file can be skipped.
    """
    config_path = Path(path) if path else _find_config_file()

    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        config = AppConfig(**data)
    else:
        config = AppConfig()

    # GENECHAT_VCF env var overrides vcf_path if not already set
    vcf_env = os.environ.get("GENECHAT_VCF")
    if vcf_env and not config.genome.vcf_path:
        config.genome.vcf_path = vcf_env

    return config
