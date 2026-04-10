"""add hdsaison role

Revision ID: 0002_add_hdsaison_role
Revises: 0001_auth_init
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_hdsaison_role"
down_revision = "0001_auth_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("name", sa.String(length=50)),
        sa.column("description", sa.String(length=255)),
    )

    exists = conn.execute(
        sa.select(sa.literal(1)).select_from(roles).where(roles.c.name == "hdsaison")
    ).first()
    if not exists:
        conn.execute(
            sa.insert(roles).values(name="hdsaison", description="HDSaison operator")
        )


def downgrade() -> None:
    conn = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("name", sa.String(length=50)),
    )
    conn.execute(sa.delete(roles).where(roles.c.name == "hdsaison"))
