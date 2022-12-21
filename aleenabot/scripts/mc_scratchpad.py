# I gave up on trying to do this in any "right" way, so I'm just
# dumping code in and I'll sort out the specifics later.

from aleenabot.database.migration import initMigrator
from aleenabot.database.migration import dbMigrationManager as migrator
from aleenabot.database.migration import DBMigrationType as MGT
import aleenabot.database.database as db
import pandas as pd

def createDB():
    initMigrator()
    migrator.run_all("0000", "0001", [MGT.CORE, MGT.MINECRAFT])

# ------------------------------------------------------------------------------

def dbAddVanillaMinecraftOneSixteenFive():
    mod, created = db.MCMod.get_or_create(name = "Minecraft")
    version, created = db.MCMinecraftVersion.get_or_create(version="1.16.5", nickname="The Nether Update")
    loader, created = db.MCModLoader.get_or_create(name = "Minecraft")
    modVersion, created = db.MCModVersion.get_or_create(
                                                            mod = mod,
                                                            minecraftVersion = version,
                                                            modLoader = loader,
                                                            version = "1.16.5",
                                                            sha3Checksum  = "skip",
                                                            shakeChecksum = "skip",
                                                            filename    = "skip"
                                                       )

# ------------------------------------------------------------------------------

def dbAddItemsFromCSV():
    csv = pd.read_csv(".\\__data\\vanilla\\items.csv")
    
    mc_mod         = db.MCMod.get(name = "Minecraft")
    mc_modVersion  = db.MCModVersion.get(mod = mc_mod, version = "1.16.5")
    
    for i in range(len(csv)):
        # get line
        line = csv.iloc[i]
    
        # should be an item, so let's just do it in order.
        i_isblockitem        = False
        if (line["Is BlockItem"] == "+"):
            i_isblockitem    = True
        
        # and we can just create it from there, with
        # awful defaults for many items, I guess
        item, created = db.MCItem.get_or_create(
                name                    = line["Display Name"],
                registryName            = line["ID"],
                lore                    = line["Tooltip"],
                nbt                     = line["Tag"],
                source                  = mc_mod,
                firstSourceVersion      = mc_modVersion,
                lastSourceVersion       = mc_modVersion,
                material                = None,
                slot                    = None,
                archetype               = None,
                translationKey          = line["Translation Key"],
                isBlockitem             = i_isblockitem,
                attackDamage            = 0.0,
                attackDamageModifier    = 0.0,
                attackSpeed             = 0.0,
                attackSpeedModifer      = 0.0,
                burnTime                = float(line["Burn Time"]),
                canEatWhileFull         = False,
                damageReduceAmount      = 0.0,
                durability              = 0.0,
                efficiency              = 0.0,
                enchantability          = float(line["Enchantability"]),
                harvestLevel            = 0.0,
                healing                 = 0.0,
                isFastEating            = 0.0,
                isMeat                  = False,
                inventoryModelName      = 0.0,
                maxDamage               = float(line["Max Damage"]),
                maxStackSize            = int(line["Max Stack Size"]),
                saturation              = 0.0,
                toughness               = 0.0,
                useDuration             = 0.0,
        )

        # and now tags
        if (str(line["Tags"]) != "nan"):
            swp_tags = line["Tags"].split()
            
            for tag in swp_tags:
                if (tag.strip() != ""):
                    i_tag, created = db.MCItemTag.get_or_create(registryName = tag.strip())
                    
                    db.MCItems_to_MCTags.get_or_create(item = item, tag = i_tag)
# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------

def main():
    db.initDB()
    dbAddItemsFromCSV()
    
if __name__ == "__main__":
    main()