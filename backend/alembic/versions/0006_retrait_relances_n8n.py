"""retrait des relances n8n : suppression de la table reminders

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-21

Il n'y a plus de workflow n8n. Les relances par email qui passaient par
`/api/internal/reminders/*` sont retirees ; elles n'avaient jamais servi —
`reminders` etait vide en production au moment de cette migration, comme
`document_requests`. L'etape 13 les remplacera par un mail des documents
manquants, qui ne s'y prendra pas de la meme facon.

La synchronisation de l'equipe, elle, est desormais portee par l'application
(cf. app/scheduler.py) : elle ne dependait de n8n que pour son declenchement.

`document_requests` est conservee : les magic links restent branches cote
backend (PublicUploadView), meme si l'interface ne les propose plus.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("reminders")


def downgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "driver_id",
            UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
