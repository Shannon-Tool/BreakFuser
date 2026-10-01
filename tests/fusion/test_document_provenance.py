from __future__ import annotations

import pytest

from breakfuser.adapters import StaticBackend
from breakfuser.fusion.composer import FusionComposer
from breakfuser.retrieval.models import SourceDocument
from tests.fusion.test_composer import empty_harvest


@pytest.mark.asyncio
async def test_paraphrased_claim_keeps_document_provenance() -> None:
    document = SourceDocument(
        id="metformin-renal-label",
        title="Metformin label",
        url="https://example.com/label",
        excerpt="Metformin is contraindicated below eGFR 30 and can accumulate and cause lactic acidosis in renal impairment.",
        source_type="curated_summary",
    )
    composer = FusionComposer(StaticBackend("eGFR below 30 is contraindicated."), "local")
    bundle = await composer.compose("renal question", "draft", empty_harvest(), [document])
    assert bundle.provenance[0].document_ids == ["metformin-renal-label"]
    assert not bundle.provenance[0].inferred
