from peewee import BooleanField
from peewee import CharField
from peewee import DatabaseProxy
from peewee import DateTimeField
from peewee import FloatField
from peewee import ForeignKeyField
from peewee import IntegerField
from peewee import Model
from peewee import MySQLDatabase
from peewee import SqliteDatabase
from playhouse.shortcuts import ReconnectMixin

# ------------------------------------------------------------------------------
# mixed in classes
# ------------------------------------------------------------------------------
class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    pass

# ------------------------------------------------------------------------------
# database and helpers
# ------------------------------------------------------------------------------

db = DatabaseProxy()

def initDB(
        _type:str="sqlite",
        config = {"path":"database.db", "pragmas":{"journal_mode":"wal"}}
    ):
    if _type == "sqlite":
        db.initialize(SqliteDatabase(config["path"], pragmas=config["pragmas"]))
    elif _type == "mysql":
        db.initialize(ReconnectMySQLDatabase(config["database"], user=config["user"], password=config["password"], host=config["host"], port=config["port"]))
    else:
        raise ValueError("Invalid database type!")

# ------------------------------------------------------------------------------
# core models
# ------------------------------------------------------------------------------
class BaseModel(Model):
    """A base model for all our models"""
    class Meta:
        database = db

class Dbmeta(BaseModel):
    '''simple model to store database metadata'''
    version = IntegerField()

class User(BaseModel):
    '''A user for our server'''
    name = CharField()
    displayName = CharField()

class Permission(BaseModel):
    '''Represents permissions the user has within the bot'''
    name = CharField()
    description = CharField()

class Permissions(BaseModel):
    '''list of permissions with some metadata for users'''
    user = ForeignKeyField(User, backref="grants")  # Backref to User.grants
    permission = ForeignKeyField(Permission, backref="grants")  # Backref to Permission.grants
    active = BooleanField()
    datetime = DateTimeField()
    reason = CharField()

# ------------------------------------------------------------------------------
# Discord Models
# ------------------------------------------------------------------------------
class DiscordUser(BaseModel):
    '''linkage between the core user and their discord id(s)'''
    user = ForeignKeyField(User, backref="discord_accounts")  # Backref to User.discord_accounts
    accountid = CharField()

# ------------------------------------------------------------------------------
# minecraft models
# ------------------------------------------------------------------------------

# core
class MinecraftUser(BaseModel):
    '''A user in minecraft'''
    user = ForeignKeyField(User, backref="minecraft_accounts")  # Backref to User.minecraft_accounts
    name = CharField()
    uuid = CharField()
    current = BooleanField()

class MinecraftInstance(BaseModel):
    '''Naively represents an instance we've launched'''
    name = CharField()
    version = CharField()
    loader = CharField()
    description = CharField()
    advancementsEnabled = BooleanField()
    storageEnabled = BooleanField()
    lastLaunched = DateTimeField()

# advancements
class MinecraftAdvancement(BaseModel):
    '''We assume it's an advancement somewhere in Minecraft.'''
    name = CharField()
    registryName = CharField()
    
class MinecraftUserAdvancement(BaseModel):
    '''A linkage between user and advacements'''
    user = ForeignKeyField(MinecraftUser)
    advancement = ForeignKeyField(MinecraftAdvancement)
    date = DateTimeField()
    instance = ForeignKeyField(MinecraftInstance)

# death
class MinecraftDeathObject(BaseModel):
    name = CharField()

class MinecraftDeathSource(BaseModel):
    name = CharField()

class MinecraftDeathCause(BaseModel):
    name = CharField()

class MinecraftDeath(BaseModel):
    cause = ForeignKeyField(MinecraftDeathCause)
    deathString = CharField()
    deathObject = ForeignKeyField(MinecraftDeathObject)
    user = ForeignKeyField(MinecraftUser)
    source = ForeignKeyField(MinecraftDeathSource)
    indirectSource = ForeignKeyField(MinecraftDeathSource)
    datetime = DateTimeField()
    instance = ForeignKeyField(MinecraftInstance)
    
class MinecraftDeathTaunt(BaseModel):
    cause = ForeignKeyField(MinecraftDeathCause)
    object = ForeignKeyField(MinecraftDeathObject)
    source = ForeignKeyField(MinecraftDeathSource)
    indirectSource = ForeignKeyField(MinecraftDeathSource)
    writer = ForeignKeyField(User)
    taunt = CharField()