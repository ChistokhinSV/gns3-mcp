"""GM-109: authentication refreshes must not switch the selected project

Several clients share one GNS3 server. The 5-minute keep-alive used to set the
current project to the first opened one, which moved node and console calls into
another user's lab.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "gns3_mcp" / "server"))

import app as app_module  # noqa: E402
from app import background_authentication, refresh_current_project  # noqa: E402

OTHER_LAB = {"project_id": "p-other", "name": "afs-e2e", "status": "opened"}
MY_LAB = {"project_id": "p-mine", "name": "gm108-console-test", "status": "opened"}


def _gns3(projects):
    return SimpleNamespace(
        get_projects=AsyncMock(return_value=projects),
        authenticate=AsyncMock(return_value=True),
        connection_error=None,
    )


class TestRefreshCurrentProject:
    @pytest.mark.asyncio
    async def test_keeps_selected_project_when_another_is_opened_first(self):
        context = SimpleNamespace(current_project_id="p-mine")
        current = await refresh_current_project(_gns3([OTHER_LAB, MY_LAB]), context)
        assert context.current_project_id == "p-mine"
        assert current["name"] == "gm108-console-test"

    @pytest.mark.asyncio
    async def test_keeps_selected_project_when_it_was_closed(self):
        closed = {**MY_LAB, "status": "closed"}
        context = SimpleNamespace(current_project_id="p-mine")
        current = await refresh_current_project(_gns3([OTHER_LAB, closed]), context)
        # no silent move to afs-e2e; the next tool call reports the closed project
        assert context.current_project_id == "p-mine"
        assert current["status"] == "closed"

    @pytest.mark.asyncio
    async def test_keeps_selected_project_when_it_was_deleted(self):
        context = SimpleNamespace(current_project_id="p-gone")
        assert await refresh_current_project(_gns3([OTHER_LAB]), context) is None
        assert context.current_project_id == "p-gone"

    @pytest.mark.asyncio
    async def test_picks_first_opened_when_none_selected(self):
        context = SimpleNamespace(current_project_id=None)
        current = await refresh_current_project(_gns3([OTHER_LAB, MY_LAB]), context)
        assert context.current_project_id == "p-other"
        assert current["name"] == "afs-e2e"

    @pytest.mark.asyncio
    async def test_nothing_opened_and_none_selected(self):
        context = SimpleNamespace(current_project_id=None)
        closed = {**MY_LAB, "status": "closed"}
        assert await refresh_current_project(_gns3([closed]), context) is None
        assert context.current_project_id is None


class TestKeepAlive:
    @pytest.mark.asyncio
    async def test_keep_alive_does_not_switch_project(self):
        """One keep-alive round with two opened projects keeps the selected one"""
        context = SimpleNamespace(current_project_id="p-mine")
        gns3 = _gns3([OTHER_LAB, MY_LAB])
        # stop the loop at its 5-minute sleep after the first successful round
        with patch.object(
            app_module.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)
        ):
            await background_authentication(gns3, context)

        gns3.authenticate.assert_awaited_once()
        gns3.get_projects.assert_awaited_once()
        assert context.current_project_id == "p-mine"

    @pytest.mark.asyncio
    async def test_keep_alive_selects_a_project_at_startup(self):
        context = SimpleNamespace(current_project_id=None)
        with patch.object(
            app_module.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)
        ):
            await background_authentication(_gns3([MY_LAB]), context)
        assert context.current_project_id == "p-mine"
