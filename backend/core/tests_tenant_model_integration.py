"""Database-free compatibility test: can a Django tenant model use IdentityGuardedTenantMixin?

Runs in a separate subprocess with its own SYNTHETIC ``settings.configure(...)``. It does not import
the EduSekai settings or ``config/__init__.py`` (no Celery), reads no .env, passes no project
environment variables, and opens no database connection: every django-tenants method that could reach
PostgreSQL (``TenantMixin.save``, ``create_schema``, ``_drop_schema`` and ``Model.delete``) is replaced
by a recording fake before anything is called. The real, unmodified ``organizations`` app is loaded so
the probe models can be compared with the real ``Organization`` field set. ``Organization`` itself is
only inspected, never changed. Run from the backend folder:

    python -B -m unittest -v core.tests_tenant_model_integration

Not covered (needs a disposable database): real row inserts, ``CREATE SCHEMA``, migrations, real
``DROP SCHEMA``, the library's own ``save`` internals and ``makemigrations``' database read.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import json, os, sys, types, uuid
from importlib import metadata
from pathlib import Path
from unittest import mock

backend = Path(sys.argv[1])
workdir = Path.cwd()

# Stand-in "config" package: lets `from config import db_guard` work WITHOUT config/__init__.py (Celery)
# and without config.settings.
config_package = types.ModuleType("config")
config_package.__path__ = [str(backend / "config")]
sys.modules["config"] = config_package
sys.path.insert(0, str(backend))  # only so the real, unmodified `organizations` app can be imported

# A synthetic app for the probe models (in memory; its path is the empty working directory).
probe_package = types.ModuleType("probeapp")
probe_package.__path__ = [str(workdir)]
sys.modules["probeapp"] = probe_package

import django
from django.conf import settings

settings.configure(
    DEBUG=False,
    SECRET_KEY="synthetic-not-a-secret",
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    # django.contrib.contenttypes is required because django_tenants.postgresql_backend.base (imported by
    # django_tenants.models) imports ContentType at module level; the first run failed without it.
    INSTALLED_APPS=["django.contrib.contenttypes", "django_tenants", "organizations", "probeapp"],
    SHARED_APPS=("django_tenants", "django.contrib.contenttypes", "organizations"),   # ready() needs these settings
    TENANT_APPS=("probeapp",),
    TENANT_MODEL="organizations.Organization",
    TENANT_DOMAIN_MODEL="organizations.Domain",
    DATABASE_ROUTERS=("django_tenants.routers.TenantSyncRouter",),
    DATABASES={"default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": "probe_db", "USER": "probe_user", "PASSWORD": "probe-password-SYNTH",
        "HOST": "probe-host.invalid", "PORT": "5432",
    }},
)
django.setup()

from django.db import connections, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.state import ModelState, ProjectState
from django_tenants.models import TenantMixin

from config import db_guard
from config.db_guard import IdentityGuardError
from config.tenant_identity_guard import IdentityGuardedTenantMixin
from organizations.models import Organization

def no_connection(where):
    """No database connection is OPEN. A DatabaseWrapper object may exist (django_tenants creates one during
    django.setup(); that is only a Python object), but it must hold no connection and have run no query."""
    for wrapper in connections.all(initialized_only=True):
        assert wrapper.connection is None, f"a database connection is open ({where}): {wrapper!r}"
        assert len(wrapper.queries_log) == 0, f"a query was logged ({where}): {wrapper!r}"

wrappers_after_setup = [str(w) for w in connections.all(initialized_only=True)]
no_connection("after django.setup()")

# --- the probe models: same shape as Organization, with and without the mixin -----------------------------
def build(name, bases):
    attrs = {
        "__module__": "probeapp.probe_models",
        "Meta": type("Meta", (), {"app_label": "probeapp", "ordering": ["name"]}),
        "id": models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False),
        "name": models.CharField(max_length=255),
        "address": models.TextField(blank=True),
        "phone": models.CharField(max_length=20, blank=True),
        "email": models.EmailField(blank=True),
        "is_active": models.BooleanField(default=True),
        "created_at": models.DateTimeField(auto_now_add=True),
        "updated_at": models.DateTimeField(auto_now=True),
        "auto_create_schema": True,
    }
    return types.new_class(name, bases, exec_body=lambda namespace: namespace.update(attrs))

Plain = build("PlainProbe", (TenantMixin,))
Guarded = build("GuardedProbe", (IdentityGuardedTenantMixin, TenantMixin))   # 1. Django accepts this order

# 2. MRO: the mixin comes before TenantMixin, and the real Organization now uses it in that order
mro = Guarded.__mro__
assert mro.index(IdentityGuardedTenantMixin) < mro.index(TenantMixin) < mro.index(models.Model), mro
assert Organization.__mro__[1] is IdentityGuardedTenantMixin, Organization.__mro__
assert Organization.__mro__[2] is TenantMixin, Organization.__mro__
assert Organization.save is IdentityGuardedTenantMixin.save
assert Organization.create_schema is IdentityGuardedTenantMixin.create_schema

# 3. fields equivalent: guarded vs plain vs the real Organization
def field_shape(model):
    return {f.name: f.deconstruct()[1:] for f in model._meta.concrete_fields}

assert field_shape(Guarded) == field_shape(Plain), "the mixin changed the model fields"
organization_fields = {k: v for k, v in field_shape(Organization).items()}
assert field_shape(Guarded) == organization_fields, (sorted(field_shape(Guarded)), sorted(organization_fields))
assert Guarded._meta.ordering == Plain._meta.ordering == Organization._meta.ordering
assert [f.name for f in Guarded._meta.local_fields] == [f.name for f in Plain._meta.local_fields]

# 8. model state and a migration-autodetector comparison, no connection needed
plain_state = ModelState.from_model(Plain)
guarded_state = ModelState.from_model(Guarded)
assert {n: f.deconstruct()[1:] for n, f in plain_state.fields.items()} == \
       {n: f.deconstruct()[1:] for n, f in guarded_state.fields.items()}
assert plain_state.options == guarded_state.options
mixin_in_bases = IdentityGuardedTenantMixin in guarded_state.bases
assert mixin_in_bases and IdentityGuardedTenantMixin not in plain_state.bases

def project_with(state, bases):
    same_name = ModelState("probeapp", "Probe", dict(state.fields), dict(state.options), bases, list(state.managers))
    return ProjectState(models={("probeapp", "probe"): same_name})

autodetected = MigrationAutodetector(
    project_with(plain_state, plain_state.bases), project_with(guarded_state, guarded_state.bases)
).changes(graph=MigrationGraph())
assert autodetected == {}, f"the mixin would generate a migration: {autodetected!r}"

# --- delegation with every database-reaching parent method replaced ------------------------------------------
log = []

def fake_save(self, verbosity=1, *args, **kwargs):
    log.append(("parent.save", verbosity, args, tuple(sorted(kwargs.items()))))
    return "saved"

def fake_create_schema(self, check_if_exists=False, sync_schema=True, verbosity=1):
    log.append(("parent.create_schema", check_if_exists, sync_schema, verbosity))
    return "created"

def fake_drop_schema(self, force_drop=False):
    log.append(("parent._drop_schema", force_drop))
    return "dropped"

def fake_model_delete(self, *args, **kwargs):
    log.append(("model.delete",))
    return (1, {})

refusal = {"error": None}

def fake_guard(operation, *, tier, alias=None):
    log.append(("guard", operation, tier))
    if refusal["error"] is not None:
        raise refusal["error"]
    return "ok"

def parents_patched():
    stack = mock.patch.multiple(TenantMixin, save=fake_save, create_schema=fake_create_schema,
                                _drop_schema=fake_drop_schema)
    return stack

def names():
    return [entry[0] for entry in log]

def fresh(model, **extra):
    return model(schema_name="probe_one", name="Probe One", **extra)

with parents_patched(), mock.patch.object(models.Model, "delete", fake_model_delete):
    # 4. guard-before-parent, cooperative delegation, arguments and return values preserved (mocked guard)
    with mock.patch.object(db_guard, "require_expected_database", fake_guard):
        refusal["error"] = None
        log.clear()
        assert fresh(Guarded).save(force_insert=True) == "saved"
        assert log == [("guard", "tenant_save", "provisioning"),
                       ("parent.save", 1, (), (("force_insert", True),))], log
        log.clear()
        assert fresh(Guarded).create_schema(True, verbosity=2) == "created"
        assert log == [("guard", "tenant_create_schema", "provisioning"),
                       ("parent.create_schema", True, True, 2)], log
        log.clear()
        assert fresh(Guarded)._drop_schema(force_drop=True) == "dropped"
        assert log == [("guard", "tenant_drop_schema", "destructive"), ("parent._drop_schema", True)], log

        # 7. delete(): the guarded drop happens before the parent drop, which happens before the row delete
        log.clear()
        fresh(Guarded).delete(force_drop=True)
        assert log == [("guard", "tenant_drop_schema", "destructive"), ("parent._drop_schema", True),
                       ("model.delete",)], log
        log.clear()
        fresh(Guarded).delete()   # a plain row delete: nothing is dropped, so no guard call
        assert log == [("parent._drop_schema", False), ("model.delete",)], log
        log.clear()
        flagged = fresh(Guarded)
        flagged.auto_drop_schema = True   # what the delete_tenant command does
        flagged.delete()
        assert names() == ["guard", "parent._drop_schema", "model.delete"], log

        # control: the unguarded model never calls the guard
        log.clear()
        fresh(Plain).save(); fresh(Plain).create_schema(); fresh(Plain).delete(force_drop=True)
        assert "guard" not in names(), log

        # 5 + 6. a refusal propagates unchanged and stops the parent
        error = IdentityGuardError("mismatch", "tenant_save", "provisioning")
        refusal["error"] = error
        for label, call in (("save", lambda o: o.save(force_insert=True)),
                            ("create_schema", lambda o: o.create_schema(check_if_exists=True)),
                            ("forced drop", lambda o: o._drop_schema(force_drop=True)),
                            ("delete(force_drop=True)", lambda o: o.delete(force_drop=True))):
            log.clear()
            try:
                call(fresh(Guarded))
            except IdentityGuardError as raised:
                assert raised is error, label
            else:
                raise AssertionError(f"{label} was not refused")
            assert log == [("guard", log[0][1], log[0][2])], (label, log)   # only the guard ran
            assert "model.delete" not in names() and not any(n.startswith("parent.") for n in names()), (label, log)
        refusal["error"] = None

    # the REAL adapter in the chain: synthetic settings carry no expected identity yet
    log.clear()
    try:
        fresh(Guarded).save()
    except IdentityGuardError as raised:
        assert (raised.code, raised.operation, raised.tier) == ("absent", "tenant_save", "provisioning"), raised.code
    else:
        raise AssertionError("an absent identity must refuse")
    assert log == [], log
    settings.EDUSEKAI_EXPECTED_DATABASE = "probe_db@probe-host.invalid:5432"
    assert fresh(Guarded).save() == "saved" and names() == ["parent.save"], log
    settings.EDUSEKAI_EXPECTED_DATABASE = "another_db@probe-host.invalid:5432"
    log.clear()
    for call, code, tier in ((lambda o: o.save(), "mismatch", "provisioning"),
                             (lambda o: o.delete(force_drop=True), "mismatch", "destructive")):
        try:
            call(fresh(Guarded))
        except IdentityGuardError as raised:
            assert (raised.code, raised.tier) == (code, tier), (raised.code, raised.tier)
        else:
            raise AssertionError("a mismatched identity must refuse")
    assert log == [], log   # neither the parent drop nor the row delete ran

no_connection("at the end")

# 9. project settings, Celery and a connection were never touched
assert "DJANGO_SETTINGS_MODULE" not in os.environ
assert settings.SETTINGS_MODULE is None
for forbidden in ("config.settings", "config.celery", "celery"):
    assert forbidden not in sys.modules, forbidden
assert not hasattr(config_package, "__file__")

print("EVIDENCE " + json.dumps({
    "django_version": django.get_version(),
    "django_tenants_version": metadata.version("django-tenants"),
    "django_tenants_file": sys.modules["django_tenants"].__file__,
    "guarded_mro": [c.__name__ for c in Guarded.__mro__],
    "organization_mro": [c.__name__ for c in Organization.__mro__],
    "guarded_state_bases": [getattr(b, "__name__", str(b)) for b in guarded_state.bases],
    "plain_state_bases": [getattr(b, "__name__", str(b)) for b in plain_state.bases],
    "autodetector_changes": {},
    "settings_module": settings.SETTINGS_MODULE,
    "env_settings_module": os.environ.get("DJANGO_SETTINGS_MODULE"),
    "forbidden_modules_loaded": sorted(m for m in sys.modules if m in ("config.settings", "config.celery", "celery")),
    "wrappers_existing_after_setup": wrappers_after_setup,
    "wrappers_existing_at_end": [str(c) for c in connections.all(initialized_only=True)],
    "open_connections": [str(c) for c in connections.all(initialized_only=True) if c.connection is not None],
    "queries_logged": sum(len(c.queries_log) for c in connections.all(initialized_only=True)),
}))
print("integration-ok")
'''

ENV_ALLOW = ("SYSTEMROOT", "PATH", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH",
             "TEMP", "TMP")


class TenantModelCompatibilityTests(unittest.TestCase):
    def test_django_accepts_the_mixin_before_tenantmixin_and_the_call_chain_is_guarded(self):
        # No DJANGO_SETTINGS_MODULE, DB_*, PG*, EDUSEKAI_* or other project variables are passed on.
        env = {name: os.environ[name] for name in ENV_ALLOW if name in os.environ}
        with tempfile.TemporaryDirectory() as empty_directory:
            result = subprocess.run([sys.executable, "-E", "-B", "-c", SCRIPT, str(BACKEND)], cwd=empty_directory,
                                    env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-4000:])
        self.assertIn("integration-ok", result.stdout)
        lines = [line for line in result.stdout.splitlines() if line.startswith("EVIDENCE ")]
        self.assertEqual(len(lines), 1)
        evidence = json.loads(lines[0][len("EVIDENCE "):])
        print("\n  integration evidence:", json.dumps(evidence, sort_keys=True))
        self.assertEqual(evidence["django_version"], "5.2.9")
        self.assertEqual(evidence["django_tenants_version"], "3.9.0")
        self.assertLess(evidence["guarded_mro"].index("IdentityGuardedTenantMixin"),
                        evidence["guarded_mro"].index("TenantMixin"))
        self.assertLess(evidence["organization_mro"].index("IdentityGuardedTenantMixin"),
                        evidence["organization_mro"].index("TenantMixin"))
        self.assertIn("IdentityGuardedTenantMixin", evidence["guarded_state_bases"])
        self.assertNotIn("IdentityGuardedTenantMixin", evidence["plain_state_bases"])
        self.assertEqual(evidence["autodetector_changes"], {})
        self.assertIsNone(evidence["settings_module"])
        self.assertIsNone(evidence["env_settings_module"])
        self.assertEqual(evidence["forbidden_modules_loaded"], [])
        self.assertEqual(evidence["open_connections"], [])
        self.assertEqual(evidence["queries_logged"], 0)


if __name__ == "__main__":
    unittest.main()
