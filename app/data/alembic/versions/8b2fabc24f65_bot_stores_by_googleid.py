"""bot_stores by googleID

Revision ID: 8b2fabc24f65
Revises: 45b0282f06ea
Create Date: 2026-03-04 14:33:32.887063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b2fabc24f65'
down_revision: Union[str, Sequence[str], None] = '45b0282f06ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remover FK antiga
    op.drop_constraint('bot_stores_bot_id_fkey', 'bot_stores', type_='foreignkey')

    # 2. Criar coluna temporária string
    op.add_column('bot_stores', sa.Column('user_id_bot', sa.String(), nullable=True))

    # 3. Migrar dados (INTEGER id -> STRING user_id)
    op.execute("""
        UPDATE bot_stores bs
        SET user_id_bot = b.user_id
        FROM bots b
        WHERE bs.bot_id = b.id
    """)

    # 4. Tornar NOT NULL após migração
    op.alter_column('bot_stores', 'user_id_bot', nullable=False)

    # 5. Criar nova FK
    op.create_foreign_key(
        'bot_stores_user_id_bot_fkey',
        'bot_stores',
        'bots',
        ['user_id_bot'],
        ['user_id'],
        ondelete='CASCADE'
    )

    # 6. Remover coluna antiga
    op.drop_column('bot_stores', 'bot_id')


def downgrade() -> None:
    op.add_column('bot_stores', sa.Column('bot_id', sa.INTEGER(), nullable=True))

    op.execute("""
        UPDATE bot_stores bs
        SET bot_id = b.id
        FROM bots b
        WHERE bs.user_id_bot = b.user_id
    """)

    op.alter_column('bot_stores', 'bot_id', nullable=False)

    op.drop_constraint('bot_stores_user_id_bot_fkey', 'bot_stores', type_='foreignkey')

    op.create_foreign_key(
        'bot_stores_bot_id_fkey',
        'bot_stores',
        'bots',
        ['bot_id'],
        ['id'],
        ondelete='CASCADE'
    )

    op.drop_column('bot_stores', 'user_id_bot')
