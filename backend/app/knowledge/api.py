"""
Knowledge context: documents, chunks, embeddings and the entity graph.

Public API for other contexts. Everything else in this package is internal.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentUploaded:
    """A file was stored and its document row created; ingestion must be queued."""
    document_id: str
    storage_key: str           # app.shared.storage key
    source_type: str
    job_id: str


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
