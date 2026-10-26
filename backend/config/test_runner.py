"""A test runner that makes creating a school in a test fast.

Almost every test creates one or two schools, and creating a school normally runs every tenant migration
(20-45 seconds each). This runner migrates ONE empty base schema once, after the test database is set up.
With ``TENANT_CREATION_FAKES_MIGRATIONS`` and ``TENANT_BASE_SCHEMA`` set (see settings), django-tenants then
creates each school by copying that schema (structure and the seeded roles and fee heads) and only records
the migrations as applied. The resulting schema is the same as a migrated one; it is just built faster.

Only used when tests run with ``EDUSEKAI_TEST_CLONE_TENANTS=1``. It changes nothing outside tests: the
base schema lives in the throwaway test database and is dropped with it.
"""
import time

from django.core.management import call_command
from django.db import connection
from django.test.runner import DiscoverRunner

BASE_SCHEMA = "tenant_base"


class CloneBaseSchemaRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)
        started = time.monotonic()
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{BASE_SCHEMA}" CASCADE')
            cursor.execute(f'CREATE SCHEMA "{BASE_SCHEMA}"')
        call_command("migrate_schemas", schema_name=BASE_SCHEMA, interactive=False, verbosity=0)
        connection.set_schema_to_public()
        print(f"[tests] Base school schema '{BASE_SCHEMA}' migrated in {time.monotonic() - started:.0f}s; "
              "test schools are now copied from it.")
        return old_config
