"""Users service: business logic for users operations."""
from typing import Optional
from repositories import users_repository as repo


def list_users(cursor):
    return repo.list_all(cursor)


def add_user(conn, cursor, username: str, password: str, role: str = "cashier"):
    username = (username or "").strip()
    if not username:
        raise ValueError("username_required")
    if not password:
        raise ValueError("password_required")
    role = (role or "cashier").strip() or "cashier"
    return repo.insert(conn, cursor, username, password, role)


def update_user(conn, cursor, uid: int, username: str, role: str, password: Optional[str] = None):
    if not uid:
        raise ValueError("id_required")
    username = (username or "").strip()
    if not username:
        raise ValueError("username_required")
    role = (role or "cashier").strip() or "cashier"
    return repo.update(conn, cursor, int(uid), username, role, password)


def delete_user(conn, cursor, uid: int, username: str):
    if username == "admin":
        raise PermissionError("cannot_delete_admin")
    return repo.delete(conn, cursor, int(uid))
