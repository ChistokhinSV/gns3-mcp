"""project_docs update confirms what GNS3 stored (GM-96)

A client reported the same `content_length` for two updates of different size. The server
did report the length it received, so the confirmation now also carries the previous
length and the length read back after the write, with a warning on any mismatch.
"""

import json
from types import SimpleNamespace

import pytest


class FakeReadmeBackend:
    """Stores README text per project; `truncate_to` simulates a lossy write"""

    def __init__(self, truncate_to: int | None = None):
        self.files: dict[str, str] = {}
        self.truncate_to = truncate_to

    async def get_project_readme(self, project_id: str) -> str:
        return self.files.get(project_id, "")

    async def update_project_readme(self, project_id: str, content: str) -> bool:
        self.files[project_id] = content[: self.truncate_to] if self.truncate_to else content
        return True


def _ctx(gns3) -> SimpleNamespace:
    app = SimpleNamespace(gns3=gns3, current_project_id="p-1")
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app))


async def _update(ctx, content: str) -> dict:
    from main import project_docs

    return json.loads(await project_docs(ctx, action="update", content=content, project_id="p-1"))


@pytest.mark.asyncio
async def test_two_updates_report_their_own_lengths():
    ctx = _ctx(FakeReadmeBackend())

    first = await _update(ctx, "a" * 3204)
    second = await _update(ctx, "b" * 3504)

    assert (first["content_length"], first["previous_length"], first["stored_length"]) == (
        3204,
        0,
        3204,
    )
    assert (second["content_length"], second["previous_length"], second["stored_length"]) == (
        3504,
        3204,
        3504,
    )
    assert "warning" not in second


@pytest.mark.asyncio
async def test_lossy_write_is_reported():
    ctx = _ctx(FakeReadmeBackend(truncate_to=3204))

    result = await _update(ctx, "x" * 3504)

    assert result["content_length"] == 3504
    assert result["stored_length"] == 3204
    assert "differs" in result["warning"]
