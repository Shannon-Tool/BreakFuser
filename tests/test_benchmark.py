from __future__ import annotations

from collections import Counter

from bench.harvest.corpus import HARVEST_CORPUS, REFUSAL_CORPUS


def test_golden_corpus_size_domains_and_labels() -> None:
    assert len(HARVEST_CORPUS) == 70
    counts = Counter(case["domain"] for case in HARVEST_CORPUS)
    assert len(counts) == 7
    assert set(counts.values()) == {10}
    assert all(case["required_atoms"] and case["oracle_strategy"] for case in HARVEST_CORPUS)
    assert sum(case["expected_quality"] == "hard" for case in HARVEST_CORPUS) >= 10
    assert len(REFUSAL_CORPUS) >= 16
