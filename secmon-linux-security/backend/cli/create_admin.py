"""Create the initial Admin account without accepting passwords on the command line."""

from __future__ import annotations

import getpass

from argon2 import PasswordHasher

from backend.config import get_settings
from database.migrate import migrate


def main() -> None:
    username = input("Admin username: ").strip()
    if not username or any(not (c.isalnum() or c in "_.-") for c in username):
        raise SystemExit("Invalid username")
    password = getpass.getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    settings = get_settings()
    migrate(settings.database_path, __import__("pathlib").Path("database/migrations"))
    import sqlite3

    with sqlite3.connect(settings.database_path) as conn:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise SystemExit("Admin already exists")
        cursor = conn.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?,'admin')",
            (username, PasswordHasher().hash(password)),
        )
        conn.execute(
            "INSERT INTO audit_logs(user_id,action,target_type) VALUES (?, 'create_admin', 'user')",
            (cursor.lastrowid,),
        )
    print("Admin created")


if __name__ == "__main__":
    main()
