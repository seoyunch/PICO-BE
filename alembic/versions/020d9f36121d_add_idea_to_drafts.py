"""add idea to drafts

Revision ID: 020d9f36121d
Revises: 26b42e7c90f9
Create Date: 2026-07-25 17:42:27.567306

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020d9f36121d"
down_revision: Union[str, None] = "26b42e7c90f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drafts", sa.Column("idea", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("drafts", "idea")
