from playhouse.migrate import SqliteDatabase
from playhouse.migrate import SqliteMigrator

# dumb placeholders, need fixed
db = my_db = SqliteDatabase('my_database.db')
migrator = SqliteMigrator(my_db)

migrations = {}

# 0000 to 0001

def migrate_0000_to_0001():
   # nothing to do, should just init the db.
   pass

migrations[("0000", "0001")] = migrate_0000_to_0001