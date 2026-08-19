# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Authenticator Database Migration Script

Migrates password data from the old DBM files to the new SQLAlchemy database.

Old structure:
- /srv/jupyterhub/passwords.dbm (username -> bcrypt hash)
- /srv/jupyterhub/force_password_change.dbm (username -> "1")

New structure (in JupyterHub database):
- auth_user_passwords table
"""

from __future__ import annotations

import dbm
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.authenticators.models import UserPassword
from core.database import Base

OLD_PASSWORDS_DBM = "/srv/jupyterhub/passwords.dbm"
OLD_FORCE_CHANGE_DBM = "/srv/jupyterhub/force_password_change.dbm"
MIGRATION_MARKER = "/srv/jupyterhub/.auth_migrated"


def check_migration_needed() -> bool:
    """Check if migration is needed."""
    # Skip if already migrated
    if os.path.exists(MIGRATION_MARKER):
        return False

    # Skip if old database doesn't exist
    # DBM files may have extensions like .db, .dir, .pag
    dbm_exists = any(os.path.exists(f"{OLD_PASSWORDS_DBM}{ext}") for ext in ["", ".db", ".dir", ".pag", ".dat"])

    return dbm_exists


def migrate_auth_data(target_db_url: str) -> dict:
    """
    Migrate auth data from old DBM files to new database.

    Args:
        target_db_url: SQLAlchemy URL for the target database

    Returns:
        Migration statistics
    """
    if not check_migration_needed():
        return {"status": "skipped", "reason": "Migration not needed"}

    print(f"[AUTH MIGRATION] Starting migration from {OLD_PASSWORDS_DBM}")

    stats = {
        "users_migrated": 0,
        "errors": [],
    }

    try:
        # Connect to new database
        engine = create_engine(target_db_url)
        Base.metadata.create_all(engine)
        SessionFactory = sessionmaker(bind=engine)
        session = SessionFactory()

        # Load force change flags first
        force_change_users = set()
        try:
            with dbm.open(OLD_FORCE_CHANGE_DBM, "r") as db:
                for key in db:
                    username = key.decode("utf8") if isinstance(key, bytes) else key
                    force_change_users.add(username)
        except Exception as e:
            print(f"[AUTH MIGRATION] No force_change data or error: {e}")

        # Migrate passwords
        print("[AUTH MIGRATION] Migrating user passwords...")
        try:
            with dbm.open(OLD_PASSWORDS_DBM, "r") as db:
                for key in db:
                    try:
                        username = key.decode("utf8") if isinstance(key, bytes) else key
                        password_hash = db[key]

                        # Check if user already exists in new table
                        existing = session.query(UserPassword).filter_by(username=username).first()

                        if existing:
                            print(f"[AUTH MIGRATION] User {username} already exists, skipping")
                        else:
                            user_pw = UserPassword(
                                username=username,
                                password_hash=password_hash,
                                force_change=username in force_change_users,
                            )
                            session.add(user_pw)
                            stats["users_migrated"] += 1

                    except Exception as e:
                        stats["errors"].append(f"User {key}: {e}")

        except Exception as e:
            stats["errors"].append(f"Failed to open passwords DBM: {e}")
            stats["status"] = "error"
            return stats

        session.commit()
        session.close()

        print(f"[AUTH MIGRATION] Migrated {stats['users_migrated']} users")

        # Mark migration as complete
        _mark_migration_complete()

        # Rename old files to backup
        _backup_old_files()

        stats["status"] = "success"
        print(f"[AUTH MIGRATION] Migration complete: {stats}")

    except Exception as e:
        stats["status"] = "error"
        stats["errors"].append(str(e))
        print(f"[AUTH MIGRATION] Migration failed: {e}")

    return stats


def _mark_migration_complete():
    """Create a marker file to indicate migration is complete."""
    Path(MIGRATION_MARKER).touch()


def _backup_old_files():
    """Rename old DBM files to backup."""
    for base_path in [OLD_PASSWORDS_DBM, OLD_FORCE_CHANGE_DBM]:
        for ext in ["", ".db", ".dir", ".pag", ".dat"]:
            old_path = f"{base_path}{ext}"
            if os.path.exists(old_path):
                backup_path = f"{old_path}.migrated"
                try:
                    os.rename(old_path, backup_path)
                    print(f"[AUTH MIGRATION] Backed up {old_path} to {backup_path}")
                except Exception as e:
                    print(f"[AUTH MIGRATION] Failed to backup {old_path}: {e}")


if __name__ == "__main__":
    # CLI usage for manual migration
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrate.py <target_db_url>")
        print("Example: python migrate.py sqlite:////srv/jupyterhub/jupyterhub.sqlite")
        sys.exit(1)

    target_url = sys.argv[1]
    result = migrate_auth_data(target_url)
    print(f"Result: {result}")
