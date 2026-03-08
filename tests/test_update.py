"""Tests for genechat.update (version checking)."""

from genechat.update import check_clinvar_version, format_status_table


class TestFormatStatusTable:
    def test_installed_sources(self):
        installed = {
            "snpeff": {
                "version": "GRCh38.p14",
                "updated_at": "2025-01-15",
                "status": "complete",
            },
            "clinvar": {
                "version": "2025-01-10",
                "updated_at": "2025-01-10",
                "status": "complete",
            },
        }
        latest = {
            "snpeff": None,
            "clinvar": "2025-02-01",
            "gnomad": None,
            "dbsnp": None,
        }
        table = format_status_table(installed, latest)

        assert "snpeff" in table
        assert "clinvar" in table
        assert "update available" in table  # clinvar has newer version
        assert "check unavailable" in table  # snpeff has no latest check

    def test_all_not_installed(self):
        installed = {}
        latest = {"snpeff": None, "clinvar": None, "gnomad": None, "dbsnp": None}
        table = format_status_table(installed, latest)

        assert "not installed" in table

    def test_up_to_date(self):
        installed = {
            "clinvar": {
                "version": "2025-01-10",
                "updated_at": "2025-01-10",
                "status": "complete",
            },
        }
        latest = {
            "snpeff": None,
            "clinvar": "2025-01-10",
            "gnomad": None,
            "dbsnp": None,
        }
        table = format_status_table(installed, latest)

        assert "up to date" in table


class TestCheckClinvarVersion:
    def test_returns_none_on_network_error(self, monkeypatch):
        def fail_urlopen(*a, **kw):
            raise ConnectionError("no network")

        monkeypatch.setattr("genechat.update.urlopen", fail_urlopen)
        assert check_clinvar_version() is None
