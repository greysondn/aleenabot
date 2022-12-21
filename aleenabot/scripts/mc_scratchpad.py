# I gave up on trying to do this in any "right" way, so I'm just
# dumping code in and I'll sort out the specifics later.

from aleenabot.database.migration import initMigrator
from aleenabot.database.migration import dbMigrationManager as migrator
from aleenabot.database.migration import DBMigrationType as MGT
import aleenabot.database.database as db


def createDB():
    initMigrator()
    migrator.run_all("0000", "0001", [MGT.CORE, MGT.MINECRAFT])

# ------------------------------------------------------------------------------

def dbAddVanillaMinecraftOneSixteenFive():
    mod, created = db.MCMod.get_or_create(name = "Minecraft")
    version, created = db.MCMinecraftVersion.get_or_create(version="1.16.5", nickname="The Nether Update")
    loader, created = db.MCModLoader.get_or_create(name = "Minecraft (Vanilla)")
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
# main
# ------------------------------------------------------------------------------

def main():
    db.initDB()
    dbAddVanillaMinecraftOneSixteenFive()
    
if __name__ == "__main__":
    main()