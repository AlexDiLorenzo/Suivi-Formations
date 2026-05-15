"""evolution modele documentaire : profil depanneur, categorie/criticite/mode des types, peremption optionnelle

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("profil", sa.String(20), nullable=True))

    op.add_column("document_types", sa.Column("categorie", sa.String(40), nullable=True))
    op.add_column(
        "document_types",
        sa.Column("est_perimable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "document_types",
        sa.Column("criticite", sa.String(20), nullable=False, server_default="standard"),
    )
    op.add_column(
        "document_types",
        sa.Column("mode_acquisition", sa.String(20), nullable=False, server_default="upload"),
    )

    op.alter_column("document_versions", "date_peremption", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column("document_versions", "date_peremption", existing_type=sa.Date(), nullable=False)
    op.drop_column("document_types", "mode_acquisition")
    op.drop_column("document_types", "criticite")
    op.drop_column("document_types", "est_perimable")
    op.drop_column("document_types", "categorie")
    op.drop_column("drivers", "profil")
