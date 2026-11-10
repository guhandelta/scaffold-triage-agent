"""Who is calling, and what they may do.

There is no sign-in yet. The caller names themselves with the `X-User-Name` and `X-User-Role`
headers, falling back to DEFAULT_USER and DEFAULT_ROLE. Replace `get_current_user` with your
organization's auth (SSO, JWT, ...) and keep `require` and the role table as they are.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.schemas import Permission, Role, User

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.viewer: frozenset(),
    Role.agent: frozenset({Permission.assign, Permission.note}),
    Role.reviewer: frozenset(Permission),
    Role.admin: frozenset(Permission),
}


def user_for(name: str, role: Role) -> User:
    return User(name=name, role=role, permissions=sorted(ROLE_PERMISSIONS[role]))


def get_current_user(
    x_user_name: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> User:
    settings = get_settings()
    name = (x_user_name or "").strip()[:80] or settings.default_user
    try:
        role = Role((x_user_role or settings.default_role).strip().lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="unknown role") from None
    return user_for(name, role)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(user: User, permission: Permission) -> None:
    if permission not in user.permissions:
        raise HTTPException(
            status_code=403, detail=f"{user.role.value} cannot {permission.value} tickets"
        )
