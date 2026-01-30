from fastapi import Header

# DEV MODE: 헤더 없으면 admin_id=1로 처리
def require_admin(x_admin_id: int | None = Header(default=None)):
    return x_admin_id or 1
