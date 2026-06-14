"""merge knowledge and leads branches

Revision ID: 119e059a686b
Revises: 43aded7c2a7d, b3f2c9a7d4e1
Create Date: 2026-06-14 00:27:44.626128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '119e059a686b'
down_revision: Union[str, None] = ('43aded7c2a7d', 'b3f2c9a7d4e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
