"""billing: plans, subscriptions, invoices, usage_records

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-08

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


PLAN_SPECS = [
    dict(tier="free", name="Free", price_cents=0, max_deliveries_per_month=1000, max_endpoints=1,
         log_retention_days=7, rate_limit_per_minute=100, rate_limit_per_hour=1000, rate_limit_per_day=10000,
         allow_overage=False, has_advanced_analytics=False, has_priority_support=False, has_sso=False),
    dict(tier="starter", name="Starter", price_cents=2900, max_deliveries_per_month=100_000, max_endpoints=20,
         log_retention_days=30, rate_limit_per_minute=200, rate_limit_per_hour=2000, rate_limit_per_day=20000,
         allow_overage=True, has_advanced_analytics=False, has_priority_support=True, has_sso=False),
    dict(tier="pro", name="Pro", price_cents=9900, max_deliveries_per_month=5_000_000, max_endpoints=None,
         log_retention_days=90, rate_limit_per_minute=500, rate_limit_per_hour=5000, rate_limit_per_day=50000,
         allow_overage=True, has_advanced_analytics=True, has_priority_support=True, has_sso=False),
    dict(tier="enterprise", name="Enterprise", price_cents=0, max_deliveries_per_month=None, max_endpoints=None,
         log_retention_days=365, rate_limit_per_minute=1000, rate_limit_per_hour=10000, rate_limit_per_day=100000,
         allow_overage=True, has_advanced_analytics=True, has_priority_support=True, has_sso=True),
]


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tier", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("stripe_price_id", sa.String(100), nullable=True),
        sa.Column("price_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_deliveries_per_month", sa.Integer, nullable=True),
        sa.Column("max_endpoints", sa.Integer, nullable=True),
        sa.Column("log_retention_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=False, server_default="100"),
        sa.Column("rate_limit_per_hour", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("rate_limit_per_day", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("allow_overage", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_advanced_analytics", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_priority_support", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_sso", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(100), nullable=False, unique=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("invoice_pdf_url", sa.String(1000), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])

    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_records_organization_id", "usage_records", ["organization_id"])

    plans_table = sa.table(
        "plans", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("tier", sa.String), sa.column("name", sa.String),
        sa.column("price_cents", sa.Integer), sa.column("max_deliveries_per_month", sa.Integer),
        sa.column("max_endpoints", sa.Integer), sa.column("log_retention_days", sa.Integer),
        sa.column("rate_limit_per_minute", sa.Integer), sa.column("rate_limit_per_hour", sa.Integer),
        sa.column("rate_limit_per_day", sa.Integer), sa.column("allow_overage", sa.Boolean),
        sa.column("has_advanced_analytics", sa.Boolean), sa.column("has_priority_support", sa.Boolean),
        sa.column("has_sso", sa.Boolean),
    )
    op.bulk_insert(plans_table, [{**spec, "id": uuid.uuid5(uuid.NAMESPACE_DNS, f"relayhub-plan-{spec['tier']}")} for spec in PLAN_SPECS])

    # log_retention_days was already added to organizations in migration 0007;
    # this migration only needs to add the FK constraint now that plans exists,
    # completing what 0001's comment promised back in Phase 1.
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.create_foreign_key("fk_organizations_plan_id_plans", "plans", ["plan_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_constraint("fk_organizations_plan_id_plans", type_="foreignkey")
    op.drop_table("usage_records")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("plans")
