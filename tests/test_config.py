"""Tests for config parsing, especially multi-genome support."""

from pathlib import Path

from genechat.config import AppConfig, load_config, write_config


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
