"""Tests for config parsing, especially multi-genome support."""

from pathlib import Path

from genechat.config import AppConfig, load_config, write_config


class TestAppConfigPostInit:
    def test_legacy_genome_creates_default(self):
        """Legacy [genome] section is treated as genomes['default']."""
        config = AppConfig(genome={"vcf_path": "/my.vcf.gz"})
        assert "default" in config.genomes
        assert config.genomes["default"].vcf_path == "/my.vcf.gz"
        assert config.default_genome == "default"

    def test_genomes_dict_populates_legacy(self):
        """genomes dict syncs to legacy genome field for backward compat."""
        config = AppConfig(genomes={"nate": {"vcf_path": "/nate.vcf.gz"}})
        assert config.genome.vcf_path == "/nate.vcf.gz"
        assert config.default_genome == "nate"

    def test_multiple_genomes(self):
        config = AppConfig(
            genomes={
                "nate": {"vcf_path": "/nate.vcf.gz"},
                "partner": {"vcf_path": "/partner.vcf.gz"},
            }
        )
        assert len(config.genomes) == 2
        assert config.default_genome == "nate"  # first key

    def test_explicit_default_genome(self):
        config = AppConfig(
            genomes={
                "nate": {"vcf_path": "/nate.vcf.gz"},
                "partner": {"vcf_path": "/partner.vcf.gz"},
            },
            default_genome="partner",
        )
        assert config.default_genome == "partner"

    def test_empty_config(self):
        config = AppConfig()
        assert config.genomes == {}
        assert config.default_genome == ""


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


class TestLoadConfig:
    def test_genechat_vcf_env(self, tmp_path, monkeypatch):
        """GENECHAT_VCF env var creates a single-genome config."""
        monkeypatch.setenv("GENECHAT_VCF", "/env.vcf.gz")
        monkeypatch.setattr("genechat.config._find_config_file", lambda: None)
        config = load_config()
        assert "default" in config.genomes
        assert config.genomes["default"].vcf_path == "/env.vcf.gz"

    def test_genechat_genome_env(self, tmp_path, monkeypatch):
        """GENECHAT_GENOME env var overrides default_genome."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[genomes.nate]\nvcf_path = "/nate.vcf.gz"\n\n'
            '[genomes.partner]\nvcf_path = "/partner.vcf.gz"\n'
        )
        monkeypatch.setenv("GENECHAT_GENOME", "partner")
        config = load_config(str(config_file))
        assert config.default_genome == "partner"

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
