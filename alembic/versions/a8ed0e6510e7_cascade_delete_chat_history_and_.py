"""cascade delete chat history and summaries with user/org

Revision ID: a8ed0e6510e7
Revises: d8d7bb1d4415
Create Date: 2026-07-23 22:26:44.414659

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8ed0e6510e7"
down_revision: Union[str, Sequence[str], None] = "d8d7bb1d4415"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Explicit constraint names (not None) so downgrade can drop them and the
# names are stable across environments.
_CH_ORG = "fk_chat_history_organization_id"
_CH_USER = "fk_chat_history_user_id"
_CS_USER = "fk_conversation_summaries_user_id"
_CS_ORG = "fk_conversation_summaries_organization_id"


def upgrade() -> None:
    """Add ON DELETE CASCADE FKs from chat_history / conversation_summaries
    to users and organizations, so deleting a parent erases the child rows."""
    op.create_foreign_key(
        _CH_ORG,
        "chat_history",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        _CH_USER,
        "chat_history",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        _CS_USER,
        "conversation_summaries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        _CS_ORG,
        "conversation_summaries",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Drop the cascade FKs by name."""
    op.drop_constraint(_CS_ORG, "conversation_summaries", type_="foreignkey")
    op.drop_constraint(_CS_USER, "conversation_summaries", type_="foreignkey")
    op.drop_constraint(_CH_USER, "chat_history", type_="foreignkey")
    op.drop_constraint(_CH_ORG, "chat_history", type_="foreignkey")
