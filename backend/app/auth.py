"""Who is calling, and what they may do.

There is no sign-in yet. The caller names themselves with the `X-User-Name` and `X-User-Role`
headers, falling back to the defaults in triage.yaml. Replace `get_current_user` with your
organization's auth (SSO, JWT, ...) and keep `require` as it is. What each role may do is set
under `access.roles` in triage.yaml.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.org_config import Access, OrgConfig, get_org_config
from app.schemas import Permission, Role, User


def user_for(name: str, role: Role, access: Access) -> User:
    return User(name=name, role=role, permissions=access.permissions(role))


def get_current_user(
    config: Annotated[OrgConfig, Depends(get_org_config)],
    x_user_name: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> User:
    access = config.access
    name = (x_user_name or "").strip()[:80] or access.default_user
    try:
        role = Role((x_user_role or access.default_role).strip().lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="unknown role") from None
    return user_for(name, role, access)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(user: User, permission: Permission) -> None:
    if permission not in user.permissions:
        raise HTTPException(
            status_code=403, detail=f"{user.role.value} cannot {permission.value} tickets"
        )
