#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE fractaldb;
    GRANT ALL PRIVILEGES ON DATABASE fractaldb TO $POSTGRES_USER;
    CREATE DATABASE fundamentaldb;
    GRANT ALL PRIVILEGES ON DATABASE fundamentaldb TO $POSTGRES_USER;
EOSQL
