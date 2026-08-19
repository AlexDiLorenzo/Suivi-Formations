"""lisibilite : 4 familles de documents, niveau d'exigence, prenom optionnel, cle de sync composite

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Ancienne categorie -> nouvelle famille. Les diplomes rejoignent le RH : c'est
# le service RH qui les detient, et cela evite une famille a une seule ligne.
_CATEGORIE_MAP = {
    "permis_conduite": "conduite_permis",
    "caces_autorisations": "habilitations_caces",
    "formations_internes": "formations_internes",
    "diplomes": "rh_administratif",
    "administratif": "rh_administratif",
}


def upgrade() -> None:
    # Les depanneurs de DepanTime n'ont qu'un patronyme (prenom vide) : le
    # champ ne peut pas rester obligatoire si la liste est synchronisee.
    op.alter_column("drivers", "prenom", existing_type=sa.String(120), nullable=True)

    # criticite (critique/standard) devient niveau_exigence a trois crans, qui
    # sert a la fois au poids du score et a l'ordre d'affichage de la fiche.
    op.alter_column(
        "document_types",
        "criticite",
        new_column_name="niveau_exigence",
        existing_type=sa.String(20),
        existing_nullable=False,
        server_default="complementaire",
    )
    op.execute(
        "UPDATE document_types SET niveau_exigence = "
        "CASE WHEN niveau_exigence = 'critique' THEN 'obligatoire' "
        "ELSE 'complementaire' END"
    )

    for ancienne, nouvelle in _CATEGORIE_MAP.items():
        op.execute(
            sa.text("UPDATE document_types SET categorie = :n WHERE categorie = :a").bindparams(
                n=nouvelle, a=ancienne
            )
        )

    # CNI devient la piece d'identite generique (CNI ou passeport). Renommage en
    # place plutot que suppression/recreation : les documents deja deposes et
    # leurs applicabilites restent rattaches.
    op.execute(
        "UPDATE document_types SET code = 'PIECE_IDENTITE', "
        "libelle = 'Piece d''identite (CNI ou passeport)' WHERE code = 'CNI'"
    )

    # L'attestation sur l'honneur de validite du permis est abandonnee. On ne la
    # supprime que si aucun document reel n'y est rattache : sinon la FK RESTRICT
    # ferait echouer la migration, et detruire des pieces de conformite en
    # silence n'est pas une option. Le seed signalera le cas echeant.
    op.execute(
        """
        DELETE FROM driver_required_documents
         WHERE document_type_id IN (
               SELECT id FROM document_types WHERE code = 'ATTESTATION_PERMIS')
           AND document_type_id NOT IN (SELECT document_type_id FROM documents)
        """
    )
    op.execute(
        """
        DELETE FROM document_types
         WHERE code = 'ATTESTATION_PERMIS'
           AND id NOT IN (SELECT document_type_id FROM documents)
           AND id NOT IN (SELECT document_type_id FROM signature_envelopes)
        """
    )


def downgrade() -> None:
    inverse = {
        "conduite_permis": "permis_conduite",
        "habilitations_caces": "caces_autorisations",
        "rh_administratif": "administratif",
    }
    op.execute(
        "UPDATE document_types SET code = 'CNI', "
        "libelle = 'Carte nationale d''identite' WHERE code = 'PIECE_IDENTITE'"
    )
    for nouvelle, ancienne in inverse.items():
        op.execute(
            sa.text("UPDATE document_types SET categorie = :a WHERE categorie = :n").bindparams(
                n=nouvelle, a=ancienne
            )
        )
    op.execute(
        "UPDATE document_types SET niveau_exigence = "
        "CASE WHEN niveau_exigence = 'obligatoire' THEN 'critique' "
        "ELSE 'standard' END"
    )
    op.alter_column(
        "document_types",
        "niveau_exigence",
        new_column_name="criticite",
        existing_type=sa.String(20),
        existing_nullable=False,
        server_default="standard",
    )
    op.alter_column("drivers", "prenom", existing_type=sa.String(120), nullable=False)
