"""Identity-guard mixin for tenant models (Stage 3E.2). Not attached to any model yet.

A plain Python mixin: it imports no Django, no django-tenants and no models, defines no
fields (so it needs no migration), and delegates every decision to ``config.db_guard``.
Each override asks ``db_guard.require_expected_database`` first and only then calls
``super()``, so a refusal (``IdentityGuardError``, propagated unchanged) stops the operation
before the parent can run any SQL, insert a row, create a schema or invoke migrations.

Intended use (a later stage): list it BEFORE the django-tenants class so it sits earlier in
the method resolution order::

    class Organization(IdentityGuardedTenantMixin, TenantMixin): ...

Methods and the django-tenants 3.9.0 parent signatures they wrap (checked against the
installed source, models.py lines 102, 143, 171):

- ``save(*args, **kwargs)``             parent ``save(self, verbosity=1, *args, **kwargs)``
- ``create_schema(*args, **kwargs)``    parent ``create_schema(self, check_if_exists=False,
                                         sync_schema=True, verbosity=1)``
- ``_drop_schema(force_drop=False, *args, **kwargs)``
                                         parent ``_drop_schema(self, force_drop=False)``

Why ``save`` is guarded on EVERY call, not only for new rows
- Telling a new tenant from an update needs Django internals (``_state.adding``, the primary
  key), which this pure module must not know about.
- ``clone_tenant`` saves a copied row whose ``_state.adding`` is false (it sets ``pk = None`` on a
  fetched object, clone_tenant.py:121-127) and then creates the schema in SQL
  (``CloneSchema``, clone_tenant.py:129). Guarding every ``save`` covers the row insert that
  precedes that DDL without any Django-specific condition.
- The cost: an update of a tenant row is also refused while the identity is absent or
  mismatched. A narrower condition can be added later if that proves too strict.

Why ``_drop_schema`` is guarded only when it can drop
- The parent drops only when ``auto_drop_schema`` or ``force_drop`` is truthy (models.py:152),
  so the guard runs exactly then. ``delete()`` calls ``_drop_schema`` before it deletes the
  row (models.py:168-169), so a refusal leaves both the row and the schema alone. Whether the
  schema actually exists is not checked here (that would need database access), so the guard
  may run for a drop that would turn out to be a no-op.

Rollback: the library's cleanup in ``save`` calls ``delete(force_drop=True)`` (models.py:120-124).
It goes through the same guarded ``_drop_schema``; there is no bypass.
"""

from config import db_guard

OPERATION_SAVE = "tenant_save"
OPERATION_CREATE_SCHEMA = "tenant_create_schema"
OPERATION_DROP_SCHEMA = "tenant_drop_schema"


class IdentityGuardedTenantMixin:
    def save(self, *args, **kwargs):
        db_guard.require_expected_database(OPERATION_SAVE, tier=db_guard.TIER_PROVISIONING)
        return super().save(*args, **kwargs)

    def create_schema(self, *args, **kwargs):
        db_guard.require_expected_database(OPERATION_CREATE_SCHEMA, tier=db_guard.TIER_PROVISIONING)
        return super().create_schema(*args, **kwargs)

    def _drop_schema(self, force_drop=False, *args, **kwargs):
        # The same condition the parent uses to decide whether it drops anything.
        if force_drop or getattr(self, "auto_drop_schema", False):
            db_guard.require_expected_database(OPERATION_DROP_SCHEMA, tier=db_guard.TIER_DESTRUCTIVE)
        return super()._drop_schema(force_drop, *args, **kwargs)
