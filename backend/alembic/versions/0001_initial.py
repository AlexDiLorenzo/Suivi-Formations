"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "document_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("libelle", sa.String(120), nullable=False),
        sa.Column("duree_validite_jours_default", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "drivers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id_depantime", sa.String(64), nullable=True),
        sa.Column("prenom", sa.String(120), nullable=False),
        sa.Column("nom", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telephone", sa.String(32), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="active"),
        sa.Column("date_entree", sa.Date(), nullable=True),
        sa.Column("date_sortie", sa.Date(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_drivers_external_id_depantime", "drivers", ["external_id_depantime"], unique=True)

    op.create_table(
        "driver_required_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("required_since", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("driver_id", "document_type_id", name="uq_driver_doctype"),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("driver_id", "document_type_id", name="uq_doc_driver_type"),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path_encrypted", sa.String(512), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("date_emission", sa.Date(), nullable=False),
        sa.Column("date_peremption", sa.Date(), nullable=False),
        sa.Column("uploaded_by", sa.String(20), nullable=False),
        sa.Column("uploaded_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("statut", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("validated_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    op.create_foreign_key(
        "fk_doc_current_version",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "document_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reminders_driver_id", "reminders", ["driver_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_occurred_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_reminders_driver_id", table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("document_requests")
    op.drop_constraint("fk_doc_current_version", "documents", type_="foreignkey")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("driver_required_documents")
    op.drop_index("ix_drivers_external_id_depantime", table_name="drivers")
    op.drop_table("drivers")
    op.drop_table("document_types")
    op.drop_table("admin_users")
