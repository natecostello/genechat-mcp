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


class DatabasesConfig(BaseModel):
    lookup_db: str = ""


class ServerConfig(BaseModel):
    transport: str = "stdio"
    host: str = "localhost"
    port: int = 3001
    max_variants_per_response: int = 100
    query_timeout: int = 30


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


def load_config(path: str | None = None) -> AppConfig:
    """Load config from a TOML file. Falls back to defaults if no file found.

    Supports GENECHAT_VCF env var as a shortcut for genome.vcf_path,
    useful for Docker where users can skip config files entirely.
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
