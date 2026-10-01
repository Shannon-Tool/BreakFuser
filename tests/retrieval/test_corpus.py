from __future__ import annotations

import pytest

from breakfuser.retrieval.corpus import CuratedCorpusRetriever


@pytest.mark.asyncio
async def test_medical_corpus_returns_labeled_source() -> None:
    docs = await CuratedCorpusRetriever().retrieve("metformin eGFR 25")
    assert docs
    assert docs[0].source_type == "curated_summary"
    assert "30" in docs[0].excerpt
    assert len(docs[0].sha256) == 64
    assert docs[0].retrieved_at
    assert docs[0].url.startswith("https://")


@pytest.mark.asyncio
async def test_corpus_covers_interaction_half_life_and_license() -> None:
    interaction = await CuratedCorpusRetriever().retrieve("apixaban ketoconazole")
    assert "CYP3A4" in interaction[0].excerpt
    half_life = await CuratedCorpusRetriever().retrieve("clearance 4 L/h volume 40 L half-life")
    assert "6.93" in half_life[0].excerpt
    mit = await CuratedCorpusRetriever().retrieve("MIT license NOTICE")
    assert "copyright" in mit[0].excerpt.lower()
    assert "Apache-style" in mit[0].excerpt


@pytest.mark.asyncio
async def test_no_match_returns_empty_list() -> None:
    assert await CuratedCorpusRetriever().retrieve("unrelated zebra choreography") == []
