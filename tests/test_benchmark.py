from __future__ import annotations

import json
from collections import Counter

import bench.base as base
import bench.harvest.run as harvest_run
from bench.harvest.corpus import HARVEST_CORPUS, REFUSAL_CORPUS


def test_golden_corpus_size_domains_and_labels() -> None:
    assert len(HARVEST_CORPUS) == 70
    counts = Counter(case["domain"] for case in HARVEST_CORPUS)
    assert len(counts) == 7
    assert set(counts.values()) == {10}
    assert all(case["required_atoms"] and case["oracle_strategy"] for case in HARVEST_CORPUS)
    assert sum(case["expected_quality"] == "hard" for case in HARVEST_CORPUS) >= 10
    assert len(REFUSAL_CORPUS) >= 16


def test_base_main_writes_json_summary_without_retired_markdown(
    tmp_path, monkeypatch, capsys
) -> None:
    async def fake_run():
        return {"metadata": {}, "experiment": {"ok": True}}

    monkeypatch.setattr(base, "ROOT", tmp_path)
    monkeypatch.setattr(base, "run", fake_run)
    monkeypatch.setattr(base, "markdown", lambda results: "retired")
    (tmp_path / "bench").mkdir()
    (tmp_path / "docs").mkdir()

    base.main()

    output = tmp_path / "bench" / "base_results.json"
    assert json.loads(output.read_text())["experiment"] == {"ok": True}
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert not (tmp_path / "docs" / "experiments_base.md").exists()


def test_harvest_main_writes_json_summary_without_retired_markdown(
    tmp_path, monkeypatch, capsys
) -> None:
    async def fake_run():
        return {
            "metadata": {"instances": 1},
            "provenance_checks": {"verified_facts": 1, "failures": 0},
        }

    monkeypatch.setattr(harvest_run, "ROOT", tmp_path)
    monkeypatch.setattr(harvest_run, "run", fake_run)
    monkeypatch.setattr(harvest_run, "markdown", lambda results: "retired")
    (tmp_path / "bench" / "harvest").mkdir(parents=True)
    (tmp_path / "docs").mkdir()

    harvest_run.main()

    output = tmp_path / "bench" / "harvest" / "results.json"
    assert json.loads(output.read_text())["metadata"]["instances"] == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert not (tmp_path / "docs" / "experiments_harvest.md").exists()
