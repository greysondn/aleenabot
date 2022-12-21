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
# main
# ------------------------------------------------------------------------------

def main():
    createDB()

if __name__ == "__main__":
    main()