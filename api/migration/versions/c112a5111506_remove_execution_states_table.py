"""remove execution states table

Revision ID: c112a5111506
Revises: 6ec2fa2fbe0e
Create Date: 2025-07-14 21:03:23.317893

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c112a5111506"
down_revision: Union[str, Sequence[str], None] = "6ec2fa2fbe0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add the new output_id column as nullable
    op.add_column("jobs", sa.Column("output_id", sa.UUID(), nullable=True))

    # Step 2: Migrate data from execution_states to jobs.output_id (only for jobs with execution_state_id)
    connection = op.get_bind()

    # Update jobs.output_id with the corresponding output_id from execution_states
    connection.execute(
        sa.text("""
        UPDATE jobs
        SET output_id = execution_states.output_id
        FROM execution_states
        WHERE jobs.execution_state_id = execution_states.id
    """)
    )

    # Step 3: Delete jobs that have null execution_state_id (orphaned jobs)
    result = connection.execute(
        sa.text("""
        DELETE FROM jobs WHERE execution_state_id IS NULL
    """)
    )
    print(f"Deleted {result.rowcount} jobs with null execution_state_id")

    # Note: output_id remains nullable in the new schema

    # Step 4: Create the new foreign key constraint
    op.create_foreign_key("jobs_output_id_fkey", "jobs", "outputs", ["output_id"], ["id"])

    # Step 5: Create index for the new column
    op.create_index("idx_jobs_output_id", "jobs", ["output_id"], unique=False)

    # Step 6: Drop the old foreign key constraint
    op.drop_constraint(op.f("jobs_execution_state_id_fkey"), "jobs", type_="foreignkey")

    # Step 7: Drop the old column
    op.drop_column("jobs", "execution_state_id")

    # Step 8: Clean up execution_states table
    op.drop_index(op.f("idx_execution_states_last_executed"), table_name="execution_states")
    op.drop_index(op.f("idx_execution_states_output_id"), table_name="execution_states")
    op.drop_table("execution_states")


def downgrade() -> None:
    """Downgrade schema."""
    # Step 1: Recreate execution_states table first
    op.create_table(
        "execution_states",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("request_number", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("last_response", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
        sa.Column("last_executed_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column("output_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(["output_id"], ["outputs.id"], name=op.f("execution_states_output_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("execution_states_pkey")),
    )
    op.create_index(op.f("idx_execution_states_output_id"), "execution_states", ["output_id"], unique=False)
    op.create_index(op.f("idx_execution_states_last_executed"), "execution_states", ["last_executed_at"], unique=False)

    # Step 2: Add execution_state_id column back to jobs
    op.add_column("jobs", sa.Column("execution_state_id", sa.UUID(), autoincrement=False, nullable=True))

    # Step 3: Create foreign key to execution_states (now that table exists)
    op.create_foreign_key(
        op.f("jobs_execution_state_id_fkey"), "jobs", "execution_states", ["execution_state_id"], ["id"]
    )

    # Step 4: Drop the new foreign key constraint and index
    op.drop_constraint("jobs_output_id_fkey", "jobs", type_="foreignkey")
    op.drop_index("idx_jobs_output_id", table_name="jobs")

    # Step 5: Drop the output_id column
    op.drop_column("jobs", "output_id")
