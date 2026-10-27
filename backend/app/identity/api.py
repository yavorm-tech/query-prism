"""
Identity context: companies, users, teams, membership, invites, credentials.

Public API for other contexts. Everything else in this package is internal.
"""
from dataclasses import dataclass
from app.identity import service


@dataclass(frozen=True)
class CompanyRegistered:
    """A company signed up (password or Google). Its first team and owner exist."""
    company_id: str
    team_id: str
    owner_id: str


async def get_team(team_id: str, company_id: str) -> dict | None:
    """The team, only if it belongs to company_id."""
    return await service.get_team(team_id, company_id)


class TenantDirectory:
    """Implements metering's TenantDirectory port."""

    async def count_teams(self, company_id: str) -> int:
        return await service.count_teams(company_id)

    async def count_users(self, company_id: str) -> int:
        return await service.count_users(company_id)
