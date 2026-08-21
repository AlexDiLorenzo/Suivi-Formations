"""socle vs complementaire, perimetre derive de DepanTime, fin du reglage manuel

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21

Le niveau d'exigence passe de trois crans a deux : SOCLE (sans lui on ne roule
pas, seul a compter dans le taux de conformite) et COMPLEMENTAIRE (valorise le
profil, suivi a part). Ce que l'ancien niveau `profil` reglait document par
document sur chaque fiche est repris par `document_types.perimetre`, derive des
attributs synchronises depuis DepanTime : plus rien ne se coche.

Les exigences deja posees (driver_required_documents) ne sont pas retouchees
ici : la synchro les reconcilie a son prochain passage, en ajoutant ce qui
manque et en retirant ce qui n'a plus lieu d'etre (sauf si une piece y est
deja rattachee). Le seed des types doit tourner avant elle.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── document_types : deux niveaux + un perimetre ─────────────────
    op.add_column(
        "document_types",
        sa.Column("perimetre", sa.String(20), nullable=False, server_default="tous"),
    )
    # `profil` bascule en complementaire : ces types (FIMO/FCO, B2XL, B1VL,
    # CACES) valorisent le profil sans bloquer. Le seed repose ensuite le
    # niveau et le perimetre exacts de chaque type, y compris les nouveaux.
    op.execute(
        "UPDATE document_types SET niveau_exigence = 'socle' "
        "WHERE niveau_exigence = 'obligatoire'"
    )
    op.execute(
        "UPDATE document_types SET niveau_exigence = 'complementaire' "
        "WHERE niveau_exigence = 'profil'"
    )

    # ── drivers : les attributs qui portent le perimetre ─────────────
    op.add_column("drivers", sa.Column("equipe", sa.String(30), nullable=True))
    op.add_column("drivers", sa.Column("profil_vehicule", sa.String(30), nullable=True))
    op.add_column(
        "drivers",
        sa.Column("interim", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Report de l'ancien profil de permis : `permis_c_ce` designait deja les
    # poids lourds. Sans cela les fiches resteraient sans perimetre lourd
    # jusqu'a la premiere synchro, qui seule connait la valeur exacte.
    op.execute(
        "UPDATE drivers SET profil_vehicule = 'plateau_pl' WHERE profil = 'permis_c_ce'"
    )
    op.drop_column("drivers", "profil")


def downgrade() -> None:
    op.add_column("drivers", sa.Column("profil", sa.String(20), nullable=True))
    op.execute(
        "UPDATE drivers SET profil = 'permis_c_ce' WHERE profil_vehicule = 'plateau_pl'"
    )
    op.drop_column("drivers", "interim")
    op.drop_column("drivers", "profil_vehicule")
    op.drop_column("drivers", "equipe")

    op.execute(
        "UPDATE document_types SET niveau_exigence = 'obligatoire' "
        "WHERE niveau_exigence = 'socle'"
    )
    op.execute(
        "UPDATE document_types SET niveau_exigence = 'profil' WHERE perimetre <> 'tous'"
    )
    op.drop_column("document_types", "perimetre")
