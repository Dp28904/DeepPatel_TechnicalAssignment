"""add users session_version

Adds users.session_version. It is increased whenever a user's password changes;
each login session stores the version it was created with, so changing a password
logs out every other session of that user. Existing users start at 1.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08 12:50:47.235087
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
