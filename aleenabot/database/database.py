from peewee import BooleanField
from peewee import CharField
from peewee import DatabaseProxy
from peewee import FloatField
from peewee import ForeignKeyField
from peewee import IntegerField
from peewee import Model
from peewee import MySQLDatabase
from peewee import SqliteDatabase

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
        raise NotImplementedError("MySQL support hasn't been written yet!")
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

# ------------------------------------------------------------------------------
# minecraft models
# ------------------------------------------------------------------------------
class MCMinecraftUser(BaseModel):
    '''A user in minecraft'''
    user = ForeignKeyField(User)
    uuid = CharField()

class MCMod(BaseModel):
    """A mod for minecraft"""
    name = CharField()

class MCModLoader(BaseModel):
    """A mod loader for minecraft"""
    name = CharField()

class MCMinecraftVersion(BaseModel):
    """A version of minecraft"""
    version  = CharField()
    nickname = CharField()

class MCModVersion(BaseModel):
    """A specific version of a mod in minecraft"""
    mod              = ForeignKeyField(MCMod)
    minecraftVersion = ForeignKeyField(MCMinecraftVersion)
    modLoader        = ForeignKeyField(MCModLoader)
    version          = CharField()
    sha3Checksum     = CharField() # 512
    shakeChecksum    = CharField() # 256
    filename         = CharField() # expected, not literal

class MCItemTag(BaseModel):
    registryName = CharField()

class MCEffectType(BaseModel):
    name = CharField()

class MCEffect(BaseModel):
    name          = CharField()
    registryName  = CharField()
    effectType    = ForeignKeyField(MCEffectType)
    isInstant     = BooleanField()
    liquidColor   = CharField()

class MCRarity(BaseModel):
    name = CharField()

class MCItemArchetype(BaseModel):
    name = CharField()

class MCEnchantment(BaseModel):
    name = CharField()
    registryName = CharField()
    minLevel = IntegerField()
    maxLevel = IntegerField()
    rarity   = ForeignKeyField(MCRarity)
    isCurse  = BooleanField()
    archetype = ForeignKeyField(MCItemArchetype)
    isAllowedOnBooks = BooleanField()
    isTreasure = BooleanField()

class MCItem(BaseModel):
    """An item in Minecraft"""
    name         = CharField()
    registryName = CharField()
    
    lore                 = CharField(null=True)
    nbt                  = CharField(null=True)
    source               = ForeignKeyField(MCMod)
    firstSourceVersion   = ForeignKeyField(MCModVersion)
    lastSourceVersion    = ForeignKeyField(MCModVersion)
    
    material       = CharField(null=True)
    slot           = CharField(null=True)
    archetype      = ForeignKeyField(MCItemArchetype, null=True)
    translationKey = CharField()
    isBlockitem    = BooleanField()

    attackDamage         = FloatField()
    attackDamageModifier = FloatField()
    attackSpeed          = FloatField()
    attackSpeedModifer   = FloatField()
    burnTime             = FloatField()
    canEatWhileFull      = BooleanField()
    damageReduceAmount   = FloatField()
    durability           = FloatField()
    efficiency           = FloatField()
    enchantability       = FloatField()
    harvestLevel         = FloatField()
    healing              = FloatField()
    isFastEating         = FloatField()
    isMeat               = BooleanField()
    inventoryModelName   = CharField()
    maxDamage            = FloatField()
    maxStackSize         = IntegerField()
    saturation           = FloatField()
    toughness            = FloatField()
    useDuration          = FloatField()

class MCItemOrItemTag(BaseModel):
    item = ForeignKeyField(MCItem,    null = True)
    tag  = ForeignKeyField(MCItemTag, null = True)

class MCItems_to_MCEffects(BaseModel):
    item    = ForeignKeyField(MCItem)
    effect  = ForeignKeyField(MCEffect)

class MCItemRepairMaterials(BaseModel):
    item            = ForeignKeyField(MCItem)
    repairMaterial  = ForeignKeyField(MCItem)

class MCItems_to_MCTags(BaseModel):
    item = ForeignKeyField(MCItem)
    tag  = ForeignKeyField(MCItemTag)

class MCModPack(BaseModel):
    """A standard issue modpack for minecraft"""
    name = CharField()

class MCMods_to_MCModPacks(BaseModel):
    modpack = ForeignKeyField(MCModPack)
    mod     = ForeignKeyField(MCModVersion)

class MCEMCConfig(BaseModel):
    name           = CharField()
    modPack        = ForeignKeyField(MCModPack)
    baseValue      = IntegerField()
    allowInfinite  = BooleanField()
    importDefaults = BooleanField()

class MCEMC(BaseModel):
    config          = ForeignKeyField(MCModPack)
    item            = ForeignKeyField(MCItem)
    isTransmutable  = BooleanField()
    value           = IntegerField()
    resolvable      = BooleanField()
    layer           = IntegerField()
    lockValue       = BooleanField()

class MCRecipe(BaseModel):
    registryName = CharField()
    outputItem   = ForeignKeyField(MCItem)
    enabled      = BooleanField()
    outputCount  = IntegerField()
    group        = CharField(null=True)
    serializer   = CharField()
    icon         = CharField()
    isShapeless  = BooleanField()
    inputPattern = CharField(null=True)
    station      = ForeignKeyField(MCItem)
    isDynamic    = BooleanField()
    # csv_line["Class"]

class MCRecipeInput(BaseModel):
    recipe = ForeignKeyField(MCRecipe)
    item   = ForeignKeyField(MCItemOrItemTag)
    count  = IntegerField()
    char   = CharField(null=True)