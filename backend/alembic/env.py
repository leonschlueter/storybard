from __future__ import annotations
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from app.db.base import Base
from app.core.config import settings

# import models so metadata is populated
from app.models.campaign import Campaign
from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.character_sheet import CharacterSheet
from app.models.item_def import ItemDef
from app.models.inventory import InventoryItem
from app.models.spell_def import SpellDef
from app.models.actor_spell import ActorSpell
from app.models.lore import LorePage
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.event import Event
from app.models.pending_roll import PendingRoll

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    return os.getenv("DATABASE_URL", settings.DATABASE_URL)

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
