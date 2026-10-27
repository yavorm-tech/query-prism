"""
Composition root: connects contexts without them importing upward.

Called by both entry points (app.main for the API, app.worker for Celery),
so events published in either process reach the same handlers.
"""
from app.shared import events
from app.identity.api import CompanyRegistered, TenantDirectory
from app.metering.api import set_tenant_directory
from app.workspace.api import TopicDeleted
from app.workspace.handlers import create_default_topic
from app.knowledge.api import DocumentDeleted, DocumentIngested
from app.retrieval.handlers import drop_answers_for_document, drop_answers_for_topic


def wire() -> None:
    # Ports
    set_tenant_directory(TenantDirectory())

    # Events
    events.subscribe(CompanyRegistered, create_default_topic)
    events.subscribe(DocumentIngested, drop_answers_for_document)
    events.subscribe(DocumentDeleted, drop_answers_for_document)
    events.subscribe(TopicDeleted, drop_answers_for_topic)
