"""add plans

Revision ID: cddae214969e
Revises: 01f044673689
Create Date: 2018-12-19 17:19:24.448568

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cddae214969e'
down_revision = '01f044673689'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('plan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('cost', sa.Float(), nullable=True),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('updated_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_created_date'), 'plan', ['created_date'], unique=False)
    op.create_index(op.f('ix_plan_name'), 'plan', ['name'], unique=True)
    op.create_index(op.f('ix_plan_updated_date'), 'plan', ['updated_date'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_plan_updated_date'), table_name='plan')
    op.drop_index(op.f('ix_plan_name'), table_name='plan')
    op.drop_index(op.f('ix_plan_created_date'), table_name='plan')
    op.drop_table('plan')
    # ### end Alembic commands ###