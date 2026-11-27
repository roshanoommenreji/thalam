"""The release graph: seven tables (SPEC-002-R2).

Revision ID: 0001
Revises: none
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATES = (
    "'planned', 'scoped', 'ready', 'change_approved', 'deploying', 'verifying', 'released', "
    "'rolled_back', 'cancelled'"
)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "component",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("retired_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component")),
        sa.UniqueConstraint("name", name=op.f("uq_component_name")),
    )
    op.create_table(
        "dependency",
        sa.Column("src_id", sa.Integer(), nullable=False),
        sa.Column("dst_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("src_id <> dst_id", name=op.f("ck_dependency_not_self")),
        sa.ForeignKeyConstraint(["src_id"], ["component.id"],
                                name=op.f("fk_dependency_src_id_component")),
        sa.ForeignKeyConstraint(["dst_id"], ["component.id"],
                                name=op.f("fk_dependency_dst_id_component")),
        sa.PrimaryKeyConstraint("src_id", "dst_id", name=op.f("pk_dependency")),
    )
    op.create_table(
        "release",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("jira_version_id", sa.Text(), nullable=True),
        sa.Column("created_at", TZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(r"version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'",
                           name=op.f("ck_release_version")),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"],
                                name=op.f("fk_release_component_id_component")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release")),
        sa.UniqueConstraint("component_id", "version",
                            name=op.f("uq_release_component_id_version")),
    )
    op.create_table(
        "release_need",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("spec", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_need_release_id_release")),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"],
                                name=op.f("fk_release_need_component_id_component")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_need")),
        sa.UniqueConstraint("release_id", "component_id",
                            name=op.f("uq_release_need_release_id_component_id")),
    )
    op.create_table(
        "release_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('state', 'replan')", name=op.f("ck_release_event_kind")),
        sa.CheckConstraint(f"state IS NULL OR state IN ({STATES})",
                           name=op.f("ck_release_event_state")),
        sa.CheckConstraint(
            "(kind = 'state' AND state IS NOT NULL"
            " AND (state = 'planned') = (window_start IS NOT NULL))"
            " OR (kind = 'replan' AND state IS NULL AND window_start IS NOT NULL)",
            name=op.f("ck_release_event_shape"),
        ),
        sa.CheckConstraint(
            "(window_start IS NULL) = (window_end IS NULL)"
            " AND (window_end IS NULL OR window_end >= window_start)",
            name=op.f("ck_release_event_window"),
        ),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_event_release_id_release")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_event")),
        sa.UniqueConstraint("release_id", "at", name=op.f("uq_release_event_release_id_at")),
    )
    op.create_table(
        "release_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("jira_key", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_item_release_id_release")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_item")),
        sa.UniqueConstraint("release_id", "jira_key",
                            name=op.f("uq_release_item_release_id_jira_key")),
    )
    op.create_table(
        "calendar_window",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("starts", sa.Date(), nullable=False),
        sa.Column("ends", sa.Date(), nullable=False),
        sa.CheckConstraint("kind IN ('freeze', 'blackout')",
                           name=op.f("ck_calendar_window_kind")),
        sa.CheckConstraint("ends >= starts", name=op.f("ck_calendar_window_order")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_window")),
        sa.UniqueConstraint("name", name=op.f("uq_calendar_window_name")),
    )


def downgrade() -> None:
    for table in ("calendar_window", "release_item", "release_event", "release_need",
                  "release", "dependency", "component"):
        op.drop_table(table)
