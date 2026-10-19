#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Migrations are OPT-IN. Nothing is generated, migrated or seeded when the
# container starts unless RUN_MIGRATIONS_ON_START is exactly "true" (docker-compose.yml
# defaults it to false). A deliberate one-off run is preferred over migrating on
# every start; see the "Migration safety" section of README.md.
#
# When enabled, the shared and the tenant migrations run as two separate, gated
# steps (the migration gate in manage.py also needs EDUSEKAI_EXPECTED_DATABASE in
# this container's environment). A failed step stops the container before the
# server starts. Migrations that were already applied are NOT reversed.
#
# Migration files are no longer generated here: run makemigrations while developing
# and commit the result. The public tenant is not seeded here either: run
# seed_public.py by hand once the shared migrations have been applied.
if [ "$RUN_MIGRATIONS_ON_START" = "true" ]
then
    echo "RUN_MIGRATIONS_ON_START=true: applying migrations to database '$DB_NAME' at $DB_HOST:$DB_PORT"

    echo "Syncing SHARED apps (Public Schema)..."
    python manage.py migrate_schemas --shared --apply --confirm-database "$DB_NAME" --noinput
    status=$?
    if [ "$status" -ne 0 ]
    then
        echo "Shared migration failed (exit code $status). Migrations already applied are NOT reversed. Not starting the server." >&2
        exit "$status"
    fi

    echo "Syncing TENANT apps (All Schemas)..."
    python manage.py migrate_schemas --tenant --apply --confirm-database "$DB_NAME" --noinput
    status=$?
    if [ "$status" -ne 0 ]
    then
        echo "Tenant migration failed (exit code $status). Migrations already applied are NOT reversed. Not starting the server." >&2
        exit "$status"
    fi
else
    echo "Migrations are not run at container start (set RUN_MIGRATIONS_ON_START=true to opt in)."
    echo "Apply them deliberately: python manage.py migrate_schemas --shared --apply --confirm-database <database name>"
fi

# Note: Test data population should be run manually for specific tenants
# Example: python manage.py populate_test_data --schema=your_tenant_name
# Or access container: docker exec -it EduSekai_backend python manage.py populate_test_data --schema=your_tenant

exec "$@"
