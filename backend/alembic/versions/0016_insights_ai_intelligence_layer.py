"""insights: health snapshots, anomalies, incidents, RCA

Phase 3 -- AI Integration / Intelligence Layer. Adds the intelligence layer's own
tables. Reads FROM delivery_jobs/delivery_attempts/endpoints (no new FKs needed on
those tables, no changes to Phase 1/2 tables at all) and stores only derived state:
point-in-time health snapshots, detected anomalies, correlated incidents, and
root-cause-analysis records (deterministic and/or AI-assisted).

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "endpoint_health_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("health_score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float, nullable=True),
        sa.Column("failure_rate", sa.Float, nullable=True),
        sa.Column("http_4xx_rate", sa.Float, nullable=True),
        sa.Column("http_5xx_rate", sa.Float, nullable=True),
        sa.Column("timeout_rate", sa.Float, nullable=True),
        sa.Column("retry_rate", sa.Float, nullable=True),
        sa.Column("dlq_rate", sa.Float, nullable=True),
        sa.Column("latency_p50_ms", sa.Float, nullable=True),
        sa.Column("latency_p95_ms", sa.Float, nullable=True),
        sa.Column("supporting_signals", sa.JSON, nullable=False, server_default="{}"),
    )
    op.create_index("ix_endpoint_health_snapshots_organization_id", "endpoint_health_snapshots", ["organization_id"])
    op.create_index("ix_endpoint_health_snapshots_endpoint_id", "endpoint_health_snapshots", ["endpoint_id"])
    op.create_index("ix_endpoint_health_snapshots_status", "endpoint_health_snapshots", ["status"])
    # Dashboard's "latest snapshot per endpoint" query is the hot path.
    op.create_index(
        "ix_endpoint_health_snapshots_endpoint_window",
        "endpoint_health_snapshots",
        ["endpoint_id", "window_end"],
    )

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("failure_category", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovering_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"])
    op.create_index("ix_incidents_endpoint_id", "incidents", ["endpoint_id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    # Incident-correlation dedup check: "is there already an OPEN/INVESTIGATING/
    # RECOVERING incident for this endpoint" -- avoid a full table scan per anomaly.
    op.create_index("ix_incidents_endpoint_status", "incidents", ["endpoint_id", "status"])

    op.create_table(
        "insight_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=True),
        sa.Column("metric", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("observed_value", sa.Float, nullable=False),
        sa.Column("baseline_value", sa.Float, nullable=False),
        sa.Column("delta", sa.Float, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_insight_anomalies_organization_id", "insight_anomalies", ["organization_id"])
    op.create_index("ix_insight_anomalies_endpoint_id", "insight_anomalies", ["endpoint_id"])
    op.create_index("ix_insight_anomalies_metric", "insight_anomalies", ["metric"])
    op.create_index("ix_insight_anomalies_observed_at", "insight_anomalies", ["observed_at"])
    op.create_index("ix_insight_anomalies_incident_id", "insight_anomalies", ["incident_id"])
    # Correlation window scan: "recent anomalies for this endpoint not yet attached
    # to an incident".
    op.create_index(
        "ix_insight_anomalies_endpoint_observed",
        "insight_anomalies",
        ["endpoint_id", "observed_at"],
    )

    op.create_table(
        "insight_root_cause_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="deterministic"),
        sa.Column("likely_cause", sa.String(500), nullable=False),
        sa.Column("confidence_level", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("recommendations", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("ai_raw_output", sa.JSON, nullable=True),
        sa.Column("ai_provider", sa.String(50), nullable=True),
        sa.Column("ai_model", sa.String(100), nullable=True),
    )
    op.create_index("ix_insight_root_cause_analyses_organization_id", "insight_root_cause_analyses", ["organization_id"])
    op.create_index("ix_insight_root_cause_analyses_incident_id", "insight_root_cause_analyses", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_insight_root_cause_analyses_incident_id", table_name="insight_root_cause_analyses")
    op.drop_index("ix_insight_root_cause_analyses_organization_id", table_name="insight_root_cause_analyses")
    op.drop_table("insight_root_cause_analyses")

    op.drop_index("ix_insight_anomalies_endpoint_observed", table_name="insight_anomalies")
    op.drop_index("ix_insight_anomalies_incident_id", table_name="insight_anomalies")
    op.drop_index("ix_insight_anomalies_observed_at", table_name="insight_anomalies")
    op.drop_index("ix_insight_anomalies_metric", table_name="insight_anomalies")
    op.drop_index("ix_insight_anomalies_endpoint_id", table_name="insight_anomalies")
    op.drop_index("ix_insight_anomalies_organization_id", table_name="insight_anomalies")
    op.drop_table("insight_anomalies")

    op.drop_index("ix_incidents_endpoint_status", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_endpoint_id", table_name="incidents")
    op.drop_index("ix_incidents_organization_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_endpoint_health_snapshots_endpoint_window", table_name="endpoint_health_snapshots")
    op.drop_index("ix_endpoint_health_snapshots_status", table_name="endpoint_health_snapshots")
    op.drop_index("ix_endpoint_health_snapshots_endpoint_id", table_name="endpoint_health_snapshots")
    op.drop_index("ix_endpoint_health_snapshots_organization_id", table_name="endpoint_health_snapshots")
    op.drop_table("endpoint_health_snapshots")
