import argparse
import yaml

from aleenabot.database.migration import *

def main():
    # create argparse, parse args
    parser = argparse.ArgumentParser(description='migrate db from one version to another - currently runs all migrations')
    parser.add_argument("from", required=True, type=str, help="the version we should be starting from - four digit string")
    parser.add_argument("to", required=True, type=str, help="the version we should end at - four digit string")
    args = vars(parser.parse_args())

    # load database config
    config = {}

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    DB_CONFIG = config["database"]
    
    # init connection to database
    initMigrator("mysql", DB_CONFIG)
    
    # run migration
    migrationTypes = [
        DBMigrationType.CORE,
        DBMigrationType.DISCORD,
        DBMigrationType.MINECRAFT,
    ]
    dbMigrationManager.run_all(args["from"], args["to"], migrationTypes)
    
if __name__ == "__main__":
    main()