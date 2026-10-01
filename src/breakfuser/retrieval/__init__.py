"""Retrieval-grounded evidence interfaces."""

from breakfuser.retrieval.corpus import CuratedCorpusRetriever
from breakfuser.retrieval.http import HttpDocumentRetriever
from breakfuser.retrieval.models import RetrievalSource, SourceDocument
from breakfuser.retrieval.service import GroundedEvidenceService

__all__ = [
    "CuratedCorpusRetriever",
    "GroundedEvidenceService",
    "HttpDocumentRetriever",
    "RetrievalSource",
    "SourceDocument",
]
