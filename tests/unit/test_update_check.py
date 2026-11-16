"""GM-110: gns3_connection check reports a newer release without slowing down"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "gns3_mcp" / "server"))

import update_check  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(update_check, "_cached", None)
    monkeypatch.setattr(update_check, "_task", None)
    monkeypatch.delenv(update_check.DISABLE_ENV, raising=False)
    monkeypatch.delenv(update_check.AUTO_UPDATE_ENV, raising=False)


def _fake_fetch(version, delay=0.0, calls=None):
    async def fetch():
        if calls is not None:
            calls.append(1)
        await asyncio.sleep(delay)
        update_check._cached = (time.monotonic(), version)
        return version

    return fetch


class TestVersions:
    @pytest.mark.parametrize(
        "latest, installed, newer",
        [
            ("0.61.0", "0.60.1", True),
            ("0.60.10", "0.60.9", True),
            ("0.60.1", "0.60.1", False),
            ("0.60.0", "0.60.1", False),  # a source checkout ahead of PyPI
            ("1.0", "1.0.0", False),
            ("0.61.0rc1", "0.60.1", False),  # pre-releases are not announced
            ("0.61.0", "dev", False),
        ],
    )
    def test_is_newer(self, latest, installed, newer):
        assert update_check.is_newer(latest, installed) is newer


class TestWindow:
    @pytest.mark.asyncio
    async def test_slow_lookup_reports_nothing_now_and_fills_the_cache(self, monkeypatch):
        calls = []
        monkeypatch.setattr(update_check, "_fetch", _fake_fetch("9.9.9", 0.2, calls))

        started = time.monotonic()
        assert await update_check.latest_version(window=0.05) is None
        assert time.monotonic() - started < 0.15  # the window, not the lookup

        await asyncio.sleep(0.25)  # the shielded lookup finished in the background
        assert await update_check.latest_version(window=0.05) == "9.9.9"
        assert len(calls) == 1  # answered from the cache

    @pytest.mark.asyncio
    async def test_network_error_reports_nothing(self, monkeypatch):
        class Broken:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                raise update_check.httpx.ConnectError("no route to host")

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(update_check, "_ssl_context", lambda: None)
        monkeypatch.setattr(update_check.httpx, "AsyncClient", Broken)

        assert await update_check.latest_version() is None
        assert update_check._cached is None  # a failure is retried next time

    @pytest.mark.asyncio
    async def test_can_be_turned_off(self, monkeypatch):
        calls = []
        monkeypatch.setattr(update_check, "_fetch", _fake_fetch("9.9.9", calls=calls))
        monkeypatch.setenv(update_check.DISABLE_ENV, "false")

        assert await update_check.latest_version() is None
        assert calls == []


class TestNotice:
    @pytest.mark.asyncio
    async def test_newer_release_is_reported_with_the_update_path(self, monkeypatch):
        monkeypatch.setattr(update_check, "_fetch", _fake_fetch("9.9.9"))
        monkeypatch.setenv(update_check.AUTO_UPDATE_ENV, "false")

        notice = await update_check.update_notice("0.60.1")

        assert notice["latest"] == "9.9.9" and notice["installed"] == "0.60.1"
        assert "uvx gns3-mcp@latest configure <agent> --yes" in notice["how_to_update"]

    @pytest.mark.asyncio
    async def test_same_version_is_not_reported(self, monkeypatch):
        monkeypatch.setattr(update_check, "_fetch", _fake_fetch("0.60.1"))
        assert await update_check.update_notice("0.60.1") is None

    def test_update_path_follows_the_configure_choice(self, monkeypatch):
        monkeypatch.setenv(update_check.AUTO_UPDATE_ENV, "true")
        assert update_check.how_to_update().startswith("Restart the agent")
        monkeypatch.delenv(update_check.AUTO_UPDATE_ENV)
        unknown = update_check.how_to_update()
        assert "claude plugin update gns3-lab@gns3-mcp" in unknown
        assert "docker compose pull" in unknown
