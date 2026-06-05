from fastapi import Header, HTTPException


def require_admin(
    x_admin_user: str | None = Header(default=None, alias="X-Admin-User"),
    x_remote_user: str | None = Header(default=None, alias="X-Remote-User"),
):
    if not (x_admin_user or x_remote_user):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    return 1
