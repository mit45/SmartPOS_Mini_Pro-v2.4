"""Users repository: raw DB operations for users table."""
from typing import List, Tuple, Optional

def list_all(cursor) -> List[Tuple[int, str, str]]:
    cursor.execute("SELECT id,username,role FROM users ORDER BY username")
    return [(int(r[0]), str(r[1]), str(r[2])) for r in cursor.fetchall()]


def insert(conn, cursor, username: str, password: str, role: str) -> int:
    cursor.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", (username, password, role))
    conn.commit()
    return int(cursor.lastrowid)


def update(conn, cursor, uid: int, username: str, role: str, password: Optional[str] = None) -> None:
    if password:
        cursor.execute("UPDATE users SET username=?,password=?,role=? WHERE id=?", (username, password, role, uid))
    else:
        cursor.execute("UPDATE users SET username=?,role=? WHERE id=?", (username, role, uid))
    conn.commit()


def delete(conn, cursor, uid: int) -> None:
    cursor.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
