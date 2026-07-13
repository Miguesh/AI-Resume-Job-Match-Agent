"""Create resume matching tables.

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resumes_created_at", "resumes", ["created_at"])
    op.create_index("ix_resumes_sha256", "resumes", ["sha256"], unique=True)
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_descriptions_created_at", "job_descriptions", ["created_at"])
    op.create_index("ix_job_descriptions_title", "job_descriptions", ["title"])
    op.create_table(
        "match_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resume_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("optimized_resume", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_descriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_analyses_created_at", "match_analyses", ["created_at"])
    op.create_index("ix_match_analyses_job_id", "match_analyses", ["job_id"])
    op.create_index("ix_match_analyses_resume_id", "match_analyses", ["resume_id"])


def downgrade() -> None:
    op.drop_index("ix_match_analyses_resume_id", table_name="match_analyses")
    op.drop_index("ix_match_analyses_job_id", table_name="match_analyses")
    op.drop_index("ix_match_analyses_created_at", table_name="match_analyses")
    op.drop_table("match_analyses")
    op.drop_index("ix_job_descriptions_title", table_name="job_descriptions")
    op.drop_index("ix_job_descriptions_created_at", table_name="job_descriptions")
    op.drop_table("job_descriptions")
    op.drop_index("ix_resumes_sha256", table_name="resumes")
    op.drop_index("ix_resumes_created_at", table_name="resumes")
    op.drop_table("resumes")
