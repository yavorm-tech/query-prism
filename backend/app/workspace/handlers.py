"""Workspace reactions to other contexts' events (subscribed in app.bootstrap)."""
from app.identity.api import CompanyRegistered
from app.workspace.service import create_topic, team_has_topic_named


async def create_default_topic(event: CompanyRegistered) -> None:
    # Events are delivered at least once: don't create a second "Main".
    if await team_has_topic_named(event.team_id, "Main"):
        return
    await create_topic(
        team_id=event.team_id,
        company_id=event.company_id,
        name="Main",
        created_by=event.owner_id,
        description="Default topic",
    )
