from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from breakfuser.adapters import estimate_tokens
from breakfuser.context import (
    ContextCompressor,
    PersistentVirtualFilesystem,
    VirtualFilesystem,
    redact_transcript_secrets,
    transcript_text,
)
from breakfuser.deterministic import arithmetic, count_occurrences, date_math, deterministic_answer
from breakfuser.errors import BreakFuserError
from breakfuser.skills import Skill, SkillRegistry


def test_virtual_filesystem_crud_search_and_confines_paths(tmp_path) -> None:
    filesystem = VirtualFilesystem()
    path = filesystem.write("/facts/needle.txt", "alpha\nexact needle\nomega", {"kind": "fact"})
    assert filesystem.read(path).endswith("omega")
    assert filesystem.search("needle")[0].line == 2
    assert filesystem.search("NEEDLE", case_sensitive=False)
    assert filesystem.list("/facts") == [path]
    assert filesystem.stat(path).tokens == estimate_tokens(filesystem.read(path))
    filesystem.edit(path, "exact", "precise")
    assert "precise needle" in filesystem.read(path)
    with pytest.raises(BreakFuserError):
        filesystem.read("/missing")
    with pytest.raises(BreakFuserError):
        filesystem.write("../escape", "no")
    with pytest.raises(BreakFuserError):
        filesystem.edit(path, "absent", "value")

    persistent = PersistentVirtualFilesystem(str(tmp_path / "vfs"))
    persistent.write("/persisted/data.txt", "recoverable")
    assert (tmp_path / "vfs" / "persisted" / "data.txt").read_text() == "recoverable"


@pytest.mark.asyncio
async def test_three_compression_tiers_and_exact_recovery() -> None:
    filesystem = VirtualFilesystem()
    compressor = ContextCompressor(filesystem, 100, output_threshold=5)
    payload = "\n".join(f"line-{index} {'x' * 20}" for index in range(20))
    pointer = compressor.offload_output(payload, "/tool/output.txt")
    assert pointer.startswith("[Tool output offloaded:")
    assert len(pointer.splitlines()[1:]) == 10
    assert filesystem.read("/tool/output.txt") == payload
    assert compressor.offload_output("small", "/unused") == "small"

    tool_messages = [
        {
            "role": "assistant",
            "content": "write",
            "tool_calls": [
                {
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps({"path": "/tool/output.txt", "content": payload}),
                    }
                }
            ],
        },
        *[{"role": "user", "content": "recent"} for _ in range(4)],
    ]
    tool_messages[0]["tool_calls"][0]["function"]["arguments"] = json.dumps(
        {"path": "/tool/output.txt", "content": payload * 4}
    )
    argument_compressor = ContextCompressor(filesystem, 500, output_threshold=5)
    offloaded = await argument_compressor.compress(
        tool_messages,
        session_intent="intent",
        artifacts_created=[],
        next_steps=["next"],
    )
    assert offloaded.tier == "arguments"
    assert "offloaded" in offloaded.messages[0]["tool_calls"][0]["function"]["arguments"]

    long_messages = [
        {"role": "user", "content": f"needle-{index} " + "x" * 30} for index in range(8)
    ]
    summarized = await compressor.compress(
        long_messages,
        session_intent="recover the needle",
        artifacts_created=["/tool/output.txt"],
        next_steps=["search canonical transcript"],
    )
    assert summarized.tier == "summary"
    assert summarized.transcript_path
    summary = summarized.messages[0]["content"]
    assert all(
        heading in summary for heading in ("Session Intent", "Artifacts Created", "Next Steps")
    )
    canonical = filesystem.read(summarized.transcript_path)
    assert "needle-0" in canonical
    assert filesystem.search("needle-0", "/transcripts")


@given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=10))
def test_compression_and_vfs_roundtrip_property(content, query) -> None:
    filesystem = VirtualFilesystem()
    filesystem.write("/property.txt", content)
    assert filesystem.read("/property.txt") == content
    matches = filesystem.search(query)
    assert bool(matches) == (query in content)


def test_skills_and_deterministic_operations() -> None:
    registry = SkillRegistry([Skill(name="research", description="short", body="full-body")])
    assert "full-body" not in registry.base_prompt()
    assert registry.load("research") == "full-body"
    with pytest.raises(KeyError):
        registry.load("missing")
    assert arithmetic("2 + 3 * 4") == 14
    assert arithmetic("-2 ** 2") == -4
    assert count_occurrences("Ababa", "ab") == 2
    assert date_math("2024-02-28", 1) == "2024-02-29"
    assert deterministic_answer("What is 2 + 3?") == "5"
    assert deterministic_answer("count 'ab' in 'abab'") == "2"
    assert deterministic_answer("what date is 2024-01-01 +2 days?") == "2024-01-03"
    assert deterministic_answer("ordinary question") is None
    with pytest.raises(ValueError):
        arithmetic("import os")
    with pytest.raises(ValueError):
        count_occurrences("text", "")
    assert "secret" not in redact_transcript_secrets("api_key=secret")
    assert "user: hello" in transcript_text([{"role": "user", "content": "hello"}])
