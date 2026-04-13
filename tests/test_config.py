"""Tests for config parsing, especially multi-genome support."""

import importlib.resources as _real_resources
from pathlib import Path

from genechat.config import (
    AppConfig,
    _default_db_path,
    get_data_dir,
    load_config,
    write_config,
)


class TestAppConfig:
    def test_genomes_dict(self):
        config = AppConfig(genomes={"nate": {"vcf_path": "/nate.vcf.gz"}})
        assert config.genomes["nate"].vcf_path == "/nate.vcf.gz"

    def test_multiple_genomes(self):
        config = AppConfig(
            genomes={
                "nate": {"vcf_path": "/nate.vcf.gz"},
                "partner": {"vcf_path": "/partner.vcf.gz"},
            }
        )
        assert len(config.genomes) == 2

    def test_empty_config(self):
        config = AppConfig()
        assert config.genomes == {}

    def test_ignores_legacy_fields(self):
        """Legacy fields (genome, default_genome) are silently ignored."""
        config = AppConfig(
            genome={"vcf_path": "/old.vcf.gz"},
            default_genome="something",
        )
        # Legacy fields are ignored via model_config extra="ignore"
        assert not hasattr(config, "default_genome")
        assert config.genomes == {}

    def test_no_default_genome_field(self):
        """AppConfig no longer has a default_genome field."""
        config = AppConfig(genomes={"nate": {"vcf_path": "/nate.vcf.gz"}})
        assert not hasattr(config, "default_genome")


class TestWriteConfig:
    def test_writes_genomes_section(self, tmp_path):
        config_path = write_config(Path("/test.vcf.gz"), tmp_path, label="nate")
        content = config_path.read_text()
        assert "[genomes.nate]" in content
        assert "/test.vcf.gz" in content

    def test_default_label(self, tmp_path):
        config_path = write_config(Path("/test.vcf.gz"), tmp_path)
        content = config_path.read_text()
        assert "[genomes.default]" in content

    def test_preserves_existing_genomes(self, tmp_path):
        """Adding a second genome preserves the first."""
        write_config(Path("/nate.vcf.gz"), tmp_path, label="nate")
        config_path = write_config(Path("/partner.vcf.gz"), tmp_path, label="partner")
        content = config_path.read_text()
        assert "[genomes.nate]" in content
        assert "[genomes.partner]" in content
        assert "/nate.vcf.gz" in content
        assert "/partner.vcf.gz" in content

    def test_migrates_legacy_genome(self, tmp_path):
        """If config has legacy [genome], migrates to [genomes.default]."""
        # Write a legacy-format config manually
        config_file = tmp_path / "config.toml"
        config_file.write_text('[genome]\nvcf_path = "/old.vcf.gz"\n')
        config_path = write_config(Path("/new.vcf.gz"), tmp_path, label="new")
        content = config_path.read_text()
        assert "[genomes.default]" in content
        assert "[genomes.new]" in content
        assert "/old.vcf.gz" in content
        assert "/new.vcf.gz" in content
        # Legacy [genome] section should not be present
        assert (
            content.count("[genome]") == 0
            or "[genome]" not in content.split("[genomes")[0]
        )


class TestDefaultDbPath:
    """Two-tier resolution: user-rebuilt DB takes priority over package-bundled."""

    def test_prefers_user_rebuilt_db(self, tmp_path, monkeypatch):
        user_db = tmp_path / "user" / "lookup_tables.db"
        user_db.parent.mkdir(parents=True)
        user_db.write_bytes(b"user-rebuilt")

        monkeypatch.setattr("genechat.config._user_db_path", lambda: user_db)

        result = _default_db_path()
        assert result == user_db

    def test_falls_back_to_package_bundled(self, tmp_path, monkeypatch):
        user_db = tmp_path / "user" / "lookup_tables.db"
        # user_db does not exist

        pkg_data = tmp_path / "pkg" / "data"
        pkg_data.mkdir(parents=True)
        pkg_db = pkg_data / "lookup_tables.db"
        pkg_db.write_bytes(b"package-bundled")

        monkeypatch.setattr("genechat.config._user_db_path", lambda: user_db)
        monkeypatch.setattr(_real_resources, "files", lambda _pkg: tmp_path / "pkg")

        result = _default_db_path()
        assert result == pkg_db


class TestLoadConfig:
    def test_env_vars_ignored(self, tmp_path, monkeypatch):
        """GENECHAT_VCF and GENECHAT_GENOME env vars are no longer supported."""
        monkeypatch.setenv("GENECHAT_VCF", "/env.vcf.gz")
        monkeypatch.setattr("genechat.config._find_config_file", lambda: None)
        config = load_config()
        # GENECHAT_VCF should have no effect
        assert config.genomes == {}

    def test_legacy_genome_section_migrated(self, tmp_path):
        """Legacy [genome] section is migrated to [genomes.default] at load time."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[genome]\nvcf_path = "/old.vcf.gz"\n')
        config = load_config(str(config_file))
        assert "default" in config.genomes
        assert config.genomes["default"].vcf_path == "/old.vcf.gz"

    def test_legacy_default_genome_field_ignored(self, tmp_path):
        """Legacy default_genome field in TOML is silently dropped."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'default_genome = "nate"\n\n'
            '[genomes.nate]\nvcf_path = "/nate.vcf.gz"\n\n'
            '[genomes.partner]\nvcf_path = "/partner.vcf.gz"\n'
        )
        config = load_config(str(config_file))
        assert len(config.genomes) == 2

    def test_load_multi_genome_toml(self, tmp_path):
        """Loads [genomes.*] sections from TOML."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[genomes.nate]\nvcf_path = "/nate.vcf.gz"\n\n'
            '[genomes.partner]\nvcf_path = "/partner.vcf.gz"\n'
        )
        config = load_config(str(config_file))
        assert len(config.genomes) == 2
        assert config.genomes["nate"].vcf_path == "/nate.vcf.gz"
        assert config.genomes["partner"].vcf_path == "/partner.vcf.gz"

    def test_data_dir_propagated_to_env(self, tmp_path, monkeypatch):
        """data_dir from config.toml is propagated to GENECHAT_DATA_DIR env var."""
        monkeypatch.delenv("GENECHAT_DATA_DIR", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[databases]\ndata_dir = "/data/genechat"\n\n'
            '[genomes.test]\nvcf_path = "/test.vcf.gz"\n'
        )
        load_config(str(config_file))
        import os

        assert os.environ.get("GENECHAT_DATA_DIR") == "/data/genechat"
        # Clean up
        monkeypatch.delenv("GENECHAT_DATA_DIR")

    def test_env_var_takes_precedence_over_config_data_dir(self, tmp_path, monkeypatch):
        """GENECHAT_DATA_DIR env var takes precedence over config.toml data_dir."""
        monkeypatch.setenv("GENECHAT_DATA_DIR", "/env/override")
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[databases]\ndata_dir = "/config/path"\n\n'
            '[genomes.test]\nvcf_path = "/test.vcf.gz"\n'
        )
        load_config(str(config_file))
        import os

        # Env var should NOT be overwritten by config
        assert os.environ.get("GENECHAT_DATA_DIR") == "/env/override"


class TestGetDataDir:
    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("GENECHAT_DATA_DIR", "/custom/data")
        assert get_data_dir() == Path("/custom/data")

    def test_tilde_expanded(self, monkeypatch):
        monkeypatch.setenv("GENECHAT_DATA_DIR", "~/genechat-data")
        result = get_data_dir()
        assert "~" not in str(result)
        assert str(result).endswith("genechat-data")

    def test_falls_back_to_platformdirs(self, monkeypatch):
        monkeypatch.delenv("GENECHAT_DATA_DIR", raising=False)
        result = get_data_dir()
        # Should return the platformdirs default (varies by OS)
        assert isinstance(result, Path)
        assert "genechat" in str(result)
