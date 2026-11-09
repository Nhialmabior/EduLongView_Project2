"""guardian links and teacher-controlled class/term result releases"""
from alembic import op
import sqlalchemy as sa

revision = "0002_parent_release"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guardian_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("guardian_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("relationship", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("consent_recorded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consent_recorded_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("consent_recorded_at", sa.DateTime()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("revoked_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("guardian_user_id", "learner_id", name="uq_guardian_learner"),
    )
    op.create_table(
        "result_releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("term_id", sa.Integer(), sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="released"),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=False),
        sa.Column("withdrawn_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("withdrawn_at", sa.DateTime()),
        sa.UniqueConstraint("class_id", "term_id", name="uq_release_class_term"),
    )


def downgrade():
    op.drop_table("result_releases")
    op.drop_table("guardian_links")
