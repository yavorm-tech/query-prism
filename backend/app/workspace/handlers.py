"""Workspace reactions to other contexts' events (subscribed in app.bootstrap)."""
from app.identity.api import CompanyRegistered
from app.workspace.service import create_topic


async def create_default_topic(event: CompanyRegistered) -> None:
    await create_topic(
        team_id=event.team_id,
        company_id=event.company_id,
        name="Main",
        created_by=event.owner_id,
        description="Default topic",
    )
