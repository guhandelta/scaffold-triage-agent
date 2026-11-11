"""Which tickets a caller may see.

A ticket with no team is visible to everyone. A ticket with a team is visible to people in that
team, and to admins, who see every ticket. Anyone not in the people directory sees only the
tickets with no team.
"""

from app.schemas import Role, TicketRecord, User


def can_see(user: User, record: TicketRecord, teams: set[str]) -> bool:
    return user.role == Role.admin or record.team is None or record.team in teams
