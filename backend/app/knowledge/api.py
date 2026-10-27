"""
Knowledge context: documents, chunks, embeddings and the entity graph.

Public API for other contexts. Everything else in this package is internal.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentIngested:
    """A document finished ingestion and is now searchable."""
    document_id: str
    company_id: str
    team_id: str
    visibility: str


@dataclass(frozen=True)
class DocumentDeleted:
    document_id: str
    company_id: str
    team_id: str
    visibility: str
