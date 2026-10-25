from __future__ import annotations

import getpass
import re

from app.database import connect, initialize_database
from app.security import hash_password


def main() -> None:
    initialize_database()
    username = input("Admin username: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
        raise SystemExit("Use 3-40 letters, numbers, dots, underscores, or hyphens.")

    password = getpass.getpass("Admin password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")

    with connect() as connection:
        connection.execute(
            """INSERT INTO admin_users (username, password_hash) VALUES (?, ?)
               ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash""",
            (username, hash_password(password)),
        )
    print(f"Admin account '{username}' is ready.")


if __name__ == "__main__":
    main()
