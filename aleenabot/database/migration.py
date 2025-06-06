from playhouse.migrate import MySQLMigrator
from playhouse.migrate import SqliteDatabase
from playhouse.migrate import SqliteMigrator
from playhouse.migrate import migrate
from enum import Enum
import aleenabot.database.database as db
from peewee import ForeignKeyField


# types of migrations
class DBMigrationType(Enum):
    CORE      = "core"
    """value: 'core'"""
    DISCORD   = "discord"
    """Value: 'discord'"""
    MINECRAFT = "minecraft"
    """value 'minecraft'"""

# wrap the transformations in a transaction so we can search them consistently
class DBMigration():
    def __init__(
                    self,
                    before:str = "-1",
                    after:str  = "-1",
                    forward    = None,
                    backward   = None,
                    _type      = DBMigrationType.CORE
        ):
        self.before:str = before
        self.after:str  = after
        self.forward    = forward
        self.backward   = backward
        self._type      = _type
    
    def canForward(self):
        return (self.forward != None)

    def canBackward(self):
        return (self.backward != None)

    def hasVersions(self, before, after):
        # we support going backwards, too...
        # ... but the two must be distinct.
        ret = False
        
        if (self.before == before):
            if (self.after == after):
                ret = True
            else:
                ret = False
        elif (self.before == after):
            if (self.after == before):
                ret = True
            else:
                ret = False
        else:
            ret = False
        
        return ret

    def canMigrate(self, before, after, _type) -> bool:
        ret:bool = False
        
        # it's really just a complex question, honestly
        if (self._type == _type): 
            if (self.hasVersions(before, after)):
                if (self.before == before):
                    if (self.canForward()):
                        ret = True
                    elif (self.canBackward()):
                        ret = True
        
        return ret
    
    def get(self, before, after, _type):
        ret = None
        
        if (self.canMigrate(before, after, _type)):
            if (self.before == before):
                ret = self.forward
            else:
                ret = self.backward
        
        return ret

# likewise, a dumb migration manager
class DBMigrationManager():
    def __init__(self):
        self.migrations:list[DBMigration] = []
    
    def find(self, before, after, _type):
        ret = None
        for migration in self.migrations:
            if (ret == None):
                if migration.canMigrate(before, after, _type):
                    ret = migration.get(before, after, _type)
        return ret
    
    def run(self, before, after, _type):
        funct = self.find(before, after, _type)
        if (funct != None):
            funct()
            
    def add(self, migration:DBMigration):
        self.migrations.append(migration)
    
    def run_all(self, before, after, _types):
        _before = int(before)
        _after  = int(after)
        current = _before
        
        for i in range(_before, (_after + 1)):
            cstr = str(current).zfill(4)
            astr = str(i).zfill(4)
            
            for t in _types:
                self.run(cstr, astr, t)
            
            current = int(i)


# ------------------------------------------------------------------------------
# Database placeholder stuff, et al
# ------------------------------------------------------------------------------
_db = db.db
dbMigrationManager = DBMigrationManager()
migrator = SqliteMigrator(_db) # literally any type to make it happy

def initMigrator(
        _type:str="sqlite",
        config = {"path":"database.db", "pragmas":{"journal_mode":"wal"}}
    ):
    
    global migrator
    
    # init db
    db.initDB(_type, config)
    
    # now do our own thing
    if _type == "sqlite":
        migrator = SqliteMigrator(_db)
    elif _type == "mysql":
        migrator = MySQLMigrator(_db)
    else:
        raise ValueError("Invalid database type!")

# ------------------------------------------------------------------------------
# Database migrations, finally!
# ------------------------------------------------------------------------------

# 0000 to 0001
# ------------
def core_0000_to_0001():
    with _db:
        _db.create_tables(
            [
                db.Dbmeta,
                db.User,
                db.Permission,
                db.Permissions,

            ]
        )
    
    # and create a new version row
    db.Dbmeta.create(version=1)

def core_0001_to_0000():
    print("Just delete the bloody thing! YEESH!")

dbMigrationManager.add(
    DBMigration(
        "0000",
        "0001",
        core_0000_to_0001,
        core_0001_to_0000,
        DBMigrationType.CORE
    )
)

def discord_0000_to_0001():
    with _db:
        _db.create_tables(
            [
                db.DiscordUser
            ]
        )

def discord_0001_to_0000():
    print("Just delete the bloody thing! YEESH!")
    
dbMigrationManager.add(
    DBMigration(
        "0000",
        "0001",
        discord_0000_to_0001,
        discord_0001_to_0000,
        DBMigrationType.DISCORD
    )
)

def mc_0000_to_0001():
    with _db:
        _db.create_tables(
            [
                db.MinecraftUser,
                db.MinecraftInstance,
                db.MinecraftAdvancement,
                db.MinecraftUserAdvancement,
                db.MinecraftDeathObject,
                db.MinecraftDeathSource,
                db.MinecraftDeathCause,
                db.MinecraftDeath,
                db.MinecraftDeathTaunt
            ]
        )
        
def mc_0001_to_0000():
    print("Just delete the bloody thing! YEESH!")

dbMigrationManager.add(
    DBMigration(
        "0000",
        "0001",
        mc_0000_to_0001,
        mc_0001_to_0000,
        DBMigrationType.MINECRAFT
    )
)

# ------------------------------------------------------------------------------

def core_0001_to_0002():
    meta = db.Dbmeta.get(version=1)
    meta.version = 2
    meta.save()

def core_0002_to_0001():
    meta = db.Dbmeta.get(version=2)
    meta.version = 1
    meta.save()

dbMigrationManager.add(
    DBMigration(
        "0001",
        "0002",
        core_0001_to_0002,
        core_0002_to_0001,
        DBMigrationType.CORE
    )
)