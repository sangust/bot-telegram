"""delivery jobs and bot schedules

Revision ID: 8f3a5f6c2c10
Revises: 595ed4b3bb23
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f3a5f6c2c10'
down_revision: Union[str, Sequence[str], None] = '595ed4b3bb23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bot_stores', sa.Column('affiliate_link', sa.String(length=500), nullable=True))

    op.create_table(
        'bot_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('run_time', sa.Time(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_id', 'run_time', name='uq_bot_schedule_time'),
    )
    op.create_index(op.f('ix_bot_schedules_bot_id'), 'bot_schedules', ['bot_id'], unique=False)

    op.create_table(
        'delivery_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'succeeded', 'failed', name='deliveryjobstatus'), nullable=False),
        sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('sent_count', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schedule_id'], ['bot_schedules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_id', 'schedule_id', 'run_at', name='uq_delivery_job_schedule_run'),
    )
    op.create_index(op.f('ix_delivery_jobs_bot_id'), 'delivery_jobs', ['bot_id'], unique=False)
    op.create_index(op.f('ix_delivery_jobs_run_at'), 'delivery_jobs', ['run_at'], unique=False)
    op.create_index(op.f('ix_delivery_jobs_schedule_id'), 'delivery_jobs', ['schedule_id'], unique=False)
    op.create_index('ix_delivery_jobs_status_run_at', 'delivery_jobs', ['status', 'run_at'], unique=False)

    op.add_column('pending_chat_ids', sa.Column('bot_token', sa.String(length=300), nullable=True))
    op.add_column('pending_chat_ids', sa.Column('connection_code', sa.String(length=100), nullable=True))
    op.add_column('pending_chat_ids', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pending_chat_ids', sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('pending_chat_ids', 'chat_id', existing_type=sa.VARCHAR(length=100), nullable=True)
    op.create_index(op.f('ix_pending_chat_ids_connection_code'), 'pending_chat_ids', ['connection_code'], unique=True)

    op.execute("UPDATE pending_chat_ids SET bot_token = '', connection_code = google_id, created_at = NOW() WHERE bot_token IS NULL OR connection_code IS NULL")

    op.alter_column('pending_chat_ids', 'bot_token', existing_type=sa.VARCHAR(length=300), nullable=False)
    op.alter_column('pending_chat_ids', 'connection_code', existing_type=sa.VARCHAR(length=100), nullable=False)
    op.alter_column('pending_chat_ids', 'created_at', existing_type=sa.DateTime(timezone=True), nullable=False)

    op.execute("UPDATE bots SET time_to_sent = '12:00:00+00' WHERE time_to_sent IS NULL")
    op.execute(
        """
        INSERT INTO bot_schedules (bot_id, run_time, created_at, updated_at)
        SELECT id, time_to_sent, NOW(), NOW()
        FROM bots
        ON CONFLICT (bot_id, run_time) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index('ix_delivery_jobs_status_run_at', table_name='delivery_jobs')
    op.drop_index(op.f('ix_delivery_jobs_schedule_id'), table_name='delivery_jobs')
    op.drop_index(op.f('ix_delivery_jobs_run_at'), table_name='delivery_jobs')
    op.drop_index(op.f('ix_delivery_jobs_bot_id'), table_name='delivery_jobs')
    op.drop_table('delivery_jobs')

    op.drop_index(op.f('ix_bot_schedules_bot_id'), table_name='bot_schedules')
    op.drop_table('bot_schedules')

    op.drop_index(op.f('ix_pending_chat_ids_connection_code'), table_name='pending_chat_ids')
    op.drop_column('pending_chat_ids', 'connected_at')
    op.drop_column('pending_chat_ids', 'created_at')
    op.drop_column('pending_chat_ids', 'connection_code')
    op.drop_column('pending_chat_ids', 'bot_token')
    op.alter_column('pending_chat_ids', 'chat_id', existing_type=sa.VARCHAR(length=100), nullable=False)

    op.drop_column('bot_stores', 'affiliate_link')
    sa.Enum(name='deliveryjobstatus').drop(op.get_bind(), checkfirst=False)
