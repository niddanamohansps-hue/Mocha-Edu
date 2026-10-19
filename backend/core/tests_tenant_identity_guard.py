"""Pure unit tests for config.tenant_identity_guard (Stage 3E.2).

Fake parent classes and a mocked guard: no Django setup, no settings, no .env, no database.
Run from the backend folder with bytecode writing disabled:

    python -B -m unittest -v core.tests_tenant_identity_guard
"""

import ast
import importlib.util
import inspect
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from config import db_guard
from config import tenant_identity_guard as guard_module
from config.db_guard import IdentityGuardError, TIER_DESTRUCTIVE, TIER_PROVISIONING
from config.tenant_identity_guard import (
    OPERATION_CREATE_SCHEMA,
    OPERATION_DROP_SCHEMA,
    OPERATION_SAVE,
    IdentityGuardedTenantMixin,
)

BACKEND = Path(__file__).resolve().parents[1]


class Recorder:
    """Shared call log for the mocked guard and the fake parent."""

    def __init__(self, refuse_with=None):
        self.log = []
        self.refuse_with = refuse_with

    def guard(self, operation, *, tier, alias=None):
        self.log.append(("guard", operation, tier, alias))
        if self.refuse_with is not None:
            raise self.refuse_with
        return "ok"


def make_classes(recorder):
    """A fake django-tenants-like parent and a guarded subclass, with the real parent signatures."""

    class FakeTenant:
        auto_drop_schema = False

        def save(self, verbosity=1, *args, **kwargs):
            recorder.log.append(("parent.save", verbosity, args, tuple(sorted(kwargs.items()))))
            return "saved"

        def create_schema(self, check_if_exists=False, sync_schema=True, verbosity=1):
            recorder.log.append(("parent.create_schema", check_if_exists, sync_schema, verbosity))
            return "created"

        def _drop_schema(self, force_drop=False):
            recorder.log.append(("parent._drop_schema", force_drop))
            return "dropped"

    class GuardedTenant(IdentityGuardedTenantMixin, FakeTenant):
        pass

    return FakeTenant, GuardedTenant


class MixinTestCase(unittest.TestCase):
    refuse_with = None

    def setUp(self):
        self.recorder = Recorder(self.refuse_with)
        patcher = mock.patch.object(db_guard, "require_expected_database", side_effect=self.recorder.guard)
        self.guard_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.FakeTenant, self.GuardedTenant = make_classes(self.recorder)

    def names(self):
        return [entry[0] for entry in self.recorder.log]


class SaveTests(MixinTestCase):
    def test_the_guard_runs_before_the_parent_save_with_the_provisioning_tier(self):
        self.assertEqual(self.GuardedTenant().save(), "saved")
        self.assertEqual(self.names(), ["guard", "parent.save"])
        self.assertEqual(self.recorder.log[0], ("guard", OPERATION_SAVE, TIER_PROVISIONING, None))

    def test_parent_arguments_and_return_value_are_preserved(self):
        result = self.GuardedTenant().save(3, "extra", force_insert=True, using="default")
        self.assertEqual(result, "saved")
        self.assertEqual(self.recorder.log[1], ("parent.save", 3, ("extra",), (("force_insert", True), ("using", "default"))))
        self.recorder.log.clear()
        self.GuardedTenant().save(force_insert=True)  # how Django's QuerySet.create() calls save()
        self.assertEqual(self.recorder.log[1], ("parent.save", 1, (), (("force_insert", True),)))

    def test_the_guard_is_called_once_and_the_parent_once(self):
        self.GuardedTenant().save()
        self.assertEqual(self.guard_mock.call_count, 1)
        self.assertEqual(self.names().count("parent.save"), 1)


class CreateSchemaTests(MixinTestCase):
    def test_the_guard_runs_before_the_parent_create_schema_with_the_provisioning_tier(self):
        self.assertEqual(self.GuardedTenant().create_schema(), "created")
        self.assertEqual(self.names(), ["guard", "parent.create_schema"])
        self.assertEqual(self.recorder.log[0], ("guard", OPERATION_CREATE_SCHEMA, TIER_PROVISIONING, None))

    def test_parent_arguments_and_return_value_are_preserved(self):
        self.assertEqual(self.GuardedTenant().create_schema(True, False, verbosity=3), "created")
        self.assertEqual(self.recorder.log[1], ("parent.create_schema", True, False, 3))
        self.recorder.log.clear()
        self.GuardedTenant().create_schema(check_if_exists=True)
        self.assertEqual(self.recorder.log[1], ("parent.create_schema", True, True, 1))


class DropSchemaTests(MixinTestCase):
    def test_a_forced_drop_is_guarded_with_the_destructive_tier_before_the_parent(self):
        self.assertEqual(self.GuardedTenant()._drop_schema(force_drop=True), "dropped")
        self.assertEqual(self.names(), ["guard", "parent._drop_schema"])
        self.assertEqual(self.recorder.log[0], ("guard", OPERATION_DROP_SCHEMA, TIER_DESTRUCTIVE, None))
        self.assertEqual(self.recorder.log[1], ("parent._drop_schema", True))

    def test_force_drop_may_be_positional(self):
        self.GuardedTenant()._drop_schema(True)
        self.assertEqual(self.names(), ["guard", "parent._drop_schema"])
        self.assertEqual(self.recorder.log[1], ("parent._drop_schema", True))

    def test_an_instance_flagged_auto_drop_schema_is_guarded(self):
        tenant = self.GuardedTenant()
        tenant.auto_drop_schema = True  # what the delete_tenant command does
        self.assertEqual(tenant._drop_schema(), "dropped")
        self.assertEqual(self.names(), ["guard", "parent._drop_schema"])
        self.assertEqual(self.recorder.log[1], ("parent._drop_schema", False))

    def test_a_class_level_auto_drop_schema_is_guarded(self):
        class AutoDrop(self.GuardedTenant):
            auto_drop_schema = True

        AutoDrop()._drop_schema()
        self.assertEqual(self.names(), ["guard", "parent._drop_schema"])

    def test_a_path_that_does_not_drop_is_not_guarded_but_still_delegates(self):
        for call in (lambda t: t._drop_schema(), lambda t: t._drop_schema(False), lambda t: t._drop_schema(force_drop=False)):
            with self.subTest():
                self.recorder.log.clear()
                self.assertEqual(call(self.GuardedTenant()), "dropped")
                self.assertEqual(self.names(), ["parent._drop_schema"])
                self.assertEqual(self.recorder.log[0], ("parent._drop_schema", False))
        self.assertEqual(self.guard_mock.call_count, 0)

    def test_truthy_values_count_like_the_parent_condition(self):
        for value in (1, "yes", [0]):
            with self.subTest(value=value):
                self.recorder.log.clear()
                self.GuardedTenant()._drop_schema(value)
                self.assertEqual(self.names(), ["guard", "parent._drop_schema"])


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.error = IdentityGuardError("mismatch", "tenant_save", TIER_PROVISIONING)
        self.recorder = Recorder(self.error)
        patcher = mock.patch.object(db_guard, "require_expected_database", side_effect=self.recorder.guard)
        patcher.start()
        self.addCleanup(patcher.stop)
        _, self.GuardedTenant = make_classes(self.recorder)

    def assertRefusedBefore(self, call):
        with self.assertRaises(IdentityGuardError) as caught:
            call(self.GuardedTenant())
        self.assertIs(caught.exception, self.error)  # propagated unchanged, not wrapped or replaced
        self.assertEqual([entry[0] for entry in self.recorder.log], ["guard"])  # the parent never ran

    def test_a_refused_save_never_reaches_the_parent(self):
        self.assertRefusedBefore(lambda t: t.save(force_insert=True))

    def test_a_refused_create_schema_never_reaches_the_parent(self):
        self.assertRefusedBefore(lambda t: t.create_schema(check_if_exists=True))

    def test_a_refused_forced_drop_never_reaches_the_parent(self):
        self.assertRefusedBefore(lambda t: t._drop_schema(force_drop=True))

    def test_a_refused_auto_drop_never_reaches_the_parent(self):
        def call(tenant):
            tenant.auto_drop_schema = True
            return tenant._drop_schema()

        self.assertRefusedBefore(call)

    def test_other_exceptions_from_the_guard_also_propagate_unchanged(self):
        for exception in (RuntimeError("boom"), KeyboardInterrupt()):
            with self.subTest(type=type(exception).__name__):
                recorder = Recorder(exception)
                with mock.patch.object(db_guard, "require_expected_database", side_effect=recorder.guard):
                    _, guarded = make_classes(recorder)
                    with self.assertRaises(type(exception)) as caught:
                        guarded().save()
                self.assertIs(caught.exception, exception)
                self.assertEqual([entry[0] for entry in recorder.log], ["guard"])


class CooperativeInheritanceTests(MixinTestCase):
    def make_hierarchy(self):
        recorder = self.recorder

        class Audit:
            def save(self, *args, **kwargs):
                recorder.log.append(("audit.save",))
                return super().save(*args, **kwargs)

            def create_schema(self, *args, **kwargs):
                recorder.log.append(("audit.create_schema",))
                return super().create_schema(*args, **kwargs)

            def _drop_schema(self, *args, **kwargs):
                recorder.log.append(("audit._drop_schema",))
                return super()._drop_schema(*args, **kwargs)

        class GuardFirst(IdentityGuardedTenantMixin, Audit, self.FakeTenant):
            pass

        class AuditFirst(Audit, IdentityGuardedTenantMixin, self.FakeTenant):
            pass

        return GuardFirst, AuditFirst

    def test_the_mixin_cooperates_with_other_mixins_in_either_order(self):
        guard_first, audit_first = self.make_hierarchy()
        for method, call in (("save", lambda t: t.save()), ("create_schema", lambda t: t.create_schema()),
                             ("_drop_schema", lambda t: t._drop_schema(force_drop=True))):
            with self.subTest(method=method, order="guard first"):
                self.recorder.log.clear()
                call(guard_first())
                self.assertEqual(self.names(), ["guard", f"audit.{method}", f"parent.{method}"])
            with self.subTest(method=method, order="audit first"):
                self.recorder.log.clear()
                call(audit_first())
                self.assertEqual(self.names(), [f"audit.{method}", "guard", f"parent.{method}"])

    def test_the_mixin_never_calls_the_parent_directly(self):
        # With a refusing guard, the other mixin in the chain still runs only if it comes first.
        guard_first, audit_first = self.make_hierarchy()
        self.recorder.refuse_with = IdentityGuardError("absent", "tenant_save", TIER_PROVISIONING)
        with self.assertRaises(IdentityGuardError):
            guard_first().save()
        self.assertEqual(self.names(), ["guard"])  # nothing after the guard ran, not even the other mixin
        self.recorder.log.clear()
        with self.assertRaises(IdentityGuardError):
            audit_first().save()
        self.assertEqual(self.names(), ["audit.save", "guard"])  # the parent still did not run

    def test_a_diamond_hierarchy_calls_each_class_once(self):
        recorder = self.recorder

        class Left(self.FakeTenant):
            def save(self, *args, **kwargs):
                recorder.log.append(("left.save",))
                return super().save(*args, **kwargs)

        class Right(self.FakeTenant):
            def save(self, *args, **kwargs):
                recorder.log.append(("right.save",))
                return super().save(*args, **kwargs)

        class Diamond(IdentityGuardedTenantMixin, Left, Right):
            pass

        Diamond().save()
        self.assertEqual(self.names(), ["guard", "left.save", "right.save", "parent.save"])


class RealAdapterIntegrationTests(unittest.TestCase):
    """The real adapter with fake Django modules: refusal comes from config.db_guard, not from this module."""

    EXPECTED = "edusekai_db@127.0.0.1:5432"

    def run_with(self, expected, database_name="edusekai_db"):
        recorder = Recorder()
        _, guarded = make_classes(recorder)
        values = {"DATABASES": {"default": {"NAME": database_name, "HOST": "127.0.0.1", "PORT": "5432",
                                            "USER": "u-SYNTH", "PASSWORD": "p-SYNTH"}}}
        if expected is not None:
            values["EDUSEKAI_EXPECTED_DATABASE"] = expected
        conf = types.ModuleType("django.conf")
        conf.settings = types.SimpleNamespace(**values)
        utils = types.ModuleType("django_tenants.utils")
        utils.get_tenant_database_alias = lambda: "default"
        with mock.patch.dict(sys.modules, {"django.conf": conf, "django_tenants.utils": utils}):
            try:
                return guarded().save(), recorder, None
            except IdentityGuardError as error:
                return None, recorder, error

    def test_a_matching_identity_reaches_the_parent(self):
        result, recorder, error = self.run_with(self.EXPECTED)
        self.assertIsNone(error)
        self.assertEqual(result, "saved")
        self.assertEqual([e[0] for e in recorder.log], ["parent.save"])

    def test_absent_malformed_and_mismatched_identities_stop_before_the_parent(self):
        for expected, database, code in ((None, "edusekai_db", "absent"), ("", "edusekai_db", "absent"),
                                         ("garbage", "edusekai_db", "malformed"),
                                         (self.EXPECTED, "other_db", "mismatch"),
                                         (self.EXPECTED, "test_edusekai_db", "mismatch")):
            with self.subTest(code=code, database=database):
                result, recorder, error = self.run_with(expected, database)
                self.assertIsNone(result)
                self.assertEqual(error.code, code)
                self.assertEqual((error.operation, error.tier), (OPERATION_SAVE, TIER_PROVISIONING))
                self.assertEqual(recorder.log, [])  # the fake parent never ran


class OperationNameTests(unittest.TestCase):
    def test_operation_names_are_valid_adapter_labels_and_distinct(self):
        labels = (OPERATION_SAVE, OPERATION_CREATE_SCHEMA, OPERATION_DROP_SCHEMA)
        for label in labels:
            self.assertIsNotNone(re.fullmatch(r"[a-z][a-z0-9_.:-]{0,63}", label), label)
        self.assertEqual(len(set(labels)), 3)


class SignatureTests(unittest.TestCase):
    def test_the_overrides_accept_everything_the_parents_accept(self):
        def shape(function):
            parameters = inspect.signature(function).parameters.values()
            return [(p.name, p.kind.name, p.default if p.default is not p.empty else "<required>") for p in parameters]

        self.assertEqual(shape(IdentityGuardedTenantMixin.save),
                         [("self", "POSITIONAL_OR_KEYWORD", "<required>"), ("args", "VAR_POSITIONAL", "<required>"),
                          ("kwargs", "VAR_KEYWORD", "<required>")])
        self.assertEqual(shape(IdentityGuardedTenantMixin.create_schema),
                         [("self", "POSITIONAL_OR_KEYWORD", "<required>"), ("args", "VAR_POSITIONAL", "<required>"),
                          ("kwargs", "VAR_KEYWORD", "<required>")])
        self.assertEqual(shape(IdentityGuardedTenantMixin._drop_schema),
                         [("self", "POSITIONAL_OR_KEYWORD", "<required>"), ("force_drop", "POSITIONAL_OR_KEYWORD", False),
                          ("args", "VAR_POSITIONAL", "<required>"), ("kwargs", "VAR_KEYWORD", "<required>")])

    @unittest.skipUnless(importlib.util.find_spec("django_tenants") is not None, "django_tenants is not installed")
    def test_the_installed_django_tenants_signatures_match_what_the_mixin_wraps(self):
        # Read as text and parsed; django_tenants is NOT imported.
        spec = importlib.util.find_spec("django_tenants")
        models_path = Path(list(spec.submodule_search_locations)[0]) / "models.py"
        tree = ast.parse(models_path.read_text(encoding="utf-8"))
        tenant_mixin = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TenantMixin")
        methods = {n.name: n for n in tenant_mixin.body if isinstance(n, ast.FunctionDef)}

        def shape(function):
            args = function.args
            return ([a.arg for a in args.args], [ast.literal_eval(d) for d in args.defaults],
                    args.vararg.arg if args.vararg else None, args.kwarg.arg if args.kwarg else None)

        self.assertEqual(shape(methods["save"]), (["self", "verbosity"], [1], "args", "kwargs"))
        self.assertEqual(shape(methods["create_schema"]),
                         (["self", "check_if_exists", "sync_schema", "verbosity"], [False, True, 1], None, None))
        self.assertEqual(shape(methods["_drop_schema"]), (["self", "force_drop"], [False], None, None))
        flags = [n for n in tenant_mixin.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "auto_drop_schema" for t in n.targets)]
        self.assertEqual(len(flags), 1)


class PurityTests(unittest.TestCase):
    def test_the_mixin_is_a_plain_class_with_exactly_three_overrides_and_no_fields(self):
        self.assertEqual(IdentityGuardedTenantMixin.__mro__, (IdentityGuardedTenantMixin, object))
        own = {k for k in vars(IdentityGuardedTenantMixin) if not k.startswith("__")}
        self.assertEqual(own, {"save", "create_schema", "_drop_schema"})

    def test_the_module_imports_only_the_adapter_and_no_django_internals(self):
        tree = ast.parse((BACKEND / "config" / "tenant_identity_guard.py").read_text(encoding="utf-8"))
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([(n.module, [a.name for a in n.names]) for n in imports], [("config", ["db_guard"])])
        attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for forbidden in ("_state", "adding", "pk", "settings", "connections", "connection", "cursor"):
            self.assertNotIn(forbidden, attributes | names)

    def test_it_does_not_reimplement_the_identity_comparison(self):
        source = (BACKEND / "config" / "tenant_identity_guard.py").read_text(encoding="utf-8")
        for forbidden in ("check_identity", "parse_expected", "differing_fields", "EDUSEKAI_EXPECTED_DATABASE"):
            code_only = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
            tree = ast.parse(code_only)
            strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            self.assertFalse([s for s in strings if forbidden in s and len(s) < 80], forbidden)

    def test_importing_the_mixin_loads_no_django_tenants_models_or_database_driver(self):
        code = (
            "import sys\n"
            "import config.tenant_identity_guard\n"
            "bad = sorted(m for m in sys.modules if m.split('.')[0] in {'django_tenants', 'organizations', 'accounts',"
            " 'payments', 'profiles', 'students', 'staff', 'academics', 'fees', 'roles', 'core'})\n"
            "assert not bad, bad\n"
            "assert 'psycopg2' not in sys.modules\n"
            "from django.conf import settings\n"
            "assert not settings.configured\n"
            "print('safe')\n"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=BACKEND, capture_output=True, text=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("safe", result.stdout)


if __name__ == "__main__":
    unittest.main()
