"""Unit tests for config.db_guard (the Django identity adapter, Stage 3C).

Standard library only, with fakes: no Django settings, no Django test runner, no database
connection. ``django.conf``, ``django_tenants.utils`` and ``django.db`` are replaced in
``sys.modules`` for the duration of each test, so the adapter's lazy imports see fakes.
Run from the backend folder with bytecode writing disabled:

    python -B -m unittest core.tests_db_guard_adapter
"""

import ast
import contextlib
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from config import db_guard
from config.db_guard import (
    TIER_DESTRUCTIVE,
    TIER_PROVISIONING,
    IdentityGuardError,
    require_expected_database,
)

BACKEND = Path(__file__).resolve().parents[1]
TIERS = (TIER_DESTRUCTIVE, TIER_PROVISIONING)
EXPECTED = "edusekai_db@127.0.0.1:5432"
SECRET = "SYNTH-SECRET-0000"
SENSITIVE = (SECRET, "secretly_named_db", "secret-host.internal", "6543", "dbuser-SYNTH", "pw-SYNTH-0000")


def db(name="edusekai_db", host="127.0.0.1", port="5432", **extra):
    return {"NAME": name, "HOST": host, "PORT": port, "USER": "dbuser-SYNTH", "PASSWORD": "pw-SYNTH-0000",
            "OPTIONS": {"service": SECRET}, **extra}


class RecordingSettings:
    """Fake Django settings that records every attribute the adapter reads."""

    def __init__(self, **values):
        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "accessed", [])

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self.accessed.append(name)
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None


class ExplodingDb(types.ModuleType):
    """Stands in for django.db: any attribute access means the adapter touched the database layer."""

    def __getattr__(self, name):
        if name.startswith("__"):  # let the import machinery and introspection see an ordinary module
            raise AttributeError(name)
        raise AssertionError(f"django.db.{name} must not be used by the adapter")


_DEFAULT = object()  # "build the normal fake django.test.utils" (None means: make its import fail)


class ExplodingTestUtils(types.ModuleType):
    """Stands in for django.test.utils: any non-dunder attribute access fails the test."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        raise AssertionError(f"django.test.utils.{name} must not be used in this situation")


def fake_test_utils(active):
    """A fake django.test.utils whose _TestState looks like Django's, with or without saved_data."""
    module = types.ModuleType("django.test.utils")

    class _TestState:
        pass

    if active:
        _TestState.saved_data = types.SimpleNamespace()
    module._TestState = _TestState
    return module


@contextlib.contextmanager
def fake_django(settings_obj, tenant_alias="default", alias_error=None, alias_calls=None,
                test_runner_active=False, test_utils=_DEFAULT):
    """Install fake django.conf / django_tenants.utils / django.db / django.test.utils for the lazy imports.

    ``test_runner_active`` says whether the fake Django test environment is set up; ``test_utils`` replaces
    the whole fake django.test.utils module (use None to make its import fail).
    """
    conf = types.ModuleType("django.conf")
    conf.settings = settings_obj
    utils = types.ModuleType("django_tenants.utils")

    def get_tenant_database_alias():
        if alias_calls is not None:
            alias_calls.append(1)
        if alias_error is not None:
            raise alias_error
        return tenant_alias

    utils.get_tenant_database_alias = get_tenant_database_alias
    test_utils_module = fake_test_utils(test_runner_active) if test_utils is _DEFAULT else test_utils
    with mock.patch.dict(sys.modules, {"django.conf": conf, "django_tenants.utils": utils,
                                       "django.db": ExplodingDb("django.db"),
                                       "django.test.utils": test_utils_module}):
        yield


def settings_with(databases=None, expected=EXPECTED, **extra):
    values = {"DATABASES": {"default": db()} if databases is None else databases, **extra}
    if expected is not None:
        values["EDUSEKAI_EXPECTED_DATABASE"] = expected
    return RecordingSettings(**values)


def guard(settings_obj, operation="create_tenant", tier=TIER_PROVISIONING, **kwargs):
    fake_keys = ("tenant_alias", "alias_error", "alias_calls", "test_runner_active", "test_utils")
    with fake_django(settings_obj, **{k: kwargs.pop(k) for k in list(kwargs) if k in fake_keys}):
        return require_expected_database(operation, tier=tier, **kwargs)


def refused(test, settings_obj, *, code, operation="create_tenant", tier=TIER_PROVISIONING, **kwargs):
    with test.assertRaises(IdentityGuardError) as caught:
        guard(settings_obj, operation=operation, tier=tier, **kwargs)
    error = caught.exception
    test.assertEqual(error.code, code)
    test.assertEqual((error.operation, error.tier), (operation, tier))
    return error


def leaks(error):
    shown = " ".join([str(error), repr(error), repr(error.args), repr(vars(error)), str(error.__cause__),
                      str(error.__suppress_context__)])
    return [item for item in SENSITIVE if item in shown]


class OkTests(unittest.TestCase):
    def test_exact_match_returns_ok_for_both_tiers(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertEqual(guard(settings_with(), tier=tier), "ok")

    def test_port_normalisation_follows_the_pure_policy(self):
        self.assertEqual(guard(settings_with({"default": db(port=5432)})), "ok")
        self.assertEqual(guard(settings_with({"default": db(port="05432")})), "ok")

    def test_only_the_expected_identity_and_databases_settings_are_read(self):
        settings_obj = settings_with(EDUSEKAI_ALLOW_DERIVED_TEST_DB=True, EDUSEKAI_ENV="development")
        guard(settings_obj)
        self.assertEqual(set(settings_obj.accessed),
                         {"EDUSEKAI_EXPECTED_DATABASE", "DATABASES", "EDUSEKAI_ALLOW_DERIVED_TEST_DB"})


class AbsentTests(unittest.TestCase):
    def test_absent_expected_identity_is_refused_for_both_tiers(self):
        cases = [settings_with(expected=""), settings_with(expected="   "), settings_with(expected=None),
                 settings_with(expected=None)]  # the last two: the attribute is missing entirely
        for tier in TIERS:
            for settings_obj in cases:
                with self.subTest(tier=tier):
                    refused(self, settings_obj, code="absent", tier=tier)

    def test_a_none_value_counts_as_absent(self):
        refused(self, settings_with(EDUSEKAI_EXPECTED_DATABASE=None, expected=None), code="absent")


class MalformedAndMismatchTests(unittest.TestCase):
    def test_malformed_expected_identity_is_refused(self):
        for value in ("edusekai_db", "db@host", "@h:1", "db@host:abc", "db@::1:5432", 5432, ["a@b:1"]):
            for tier in TIERS:
                with self.subTest(value=value, tier=tier):
                    refused(self, settings_with(expected=value), code="malformed", tier=tier)

    def test_name_host_and_port_mismatches_are_refused(self):
        for entry in (db(name="other_db"), db(host="localhost"), db(port="5433"), db(name="Edusekai_db"),
                      db(name="", host="", port="")):
            for tier in TIERS:
                with self.subTest(name=entry["NAME"], host=entry["HOST"], port=entry["PORT"], tier=tier):
                    refused(self, settings_with({"default": entry}), code="mismatch", tier=tier)

    def test_the_derived_test_database_is_refused_by_default(self):
        # No test-only setting at all, even with a (fake) active Django test environment.
        for active in (False, True):
            for tier in TIERS:
                with self.subTest(active=active, tier=tier):
                    refused(self, settings_with({"default": db(name="test_edusekai_db")}), code="mismatch",
                            tier=tier, test_runner_active=active)


class DerivedTestDatabasePolicyTests(unittest.TestCase):
    """The test-database exception needs the explicit setting (exactly True) AND an active Django test environment."""

    DERIVED = "test_edusekai_db"

    def derived_settings(self, flag=True, **overrides):
        values = {"EDUSEKAI_ALLOW_DERIVED_TEST_DB": flag} if flag is not None else {}
        return settings_with(overrides.pop("databases", {"default": db(name=self.DERIVED)}), **values, **overrides)

    def test_exact_derived_name_is_accepted_only_with_the_setting_and_an_active_test_environment(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertEqual(guard(self.derived_settings(), tier=tier, test_runner_active=True), "ok")

    def test_the_setting_alone_is_not_enough(self):
        # An ordinary process that merely has the setting True (for example argv[1] == "test" without Django's
        # test runner): Django's test environment is not active, so the exception stays off.
        for tier in TIERS:
            with self.subTest(tier=tier):
                refused(self, self.derived_settings(), code="mismatch", tier=tier, test_runner_active=False)

    def test_an_active_test_environment_alone_is_not_enough(self):
        for flag in (None, False):
            with self.subTest(flag=flag):
                refused(self, self.derived_settings(flag=flag), code="mismatch", test_runner_active=True)

    def test_only_the_value_true_enables_it(self):
        for flag in ("True", "true", "yes", 1, [True], object(), "1", 2):
            with self.subTest(flag=repr(flag)[:12]):
                refused(self, self.derived_settings(flag=flag), code="mismatch", test_runner_active=True)

    def test_the_test_utils_module_is_not_even_imported_unless_the_setting_is_exactly_true(self):
        exploding = ExplodingTestUtils("django.test.utils")
        for flag in (None, False, "True", 1):
            with self.subTest(flag=repr(flag)):
                refused(self, self.derived_settings(flag=flag), code="mismatch", test_utils=exploding)
        # Base database with the setting off: also never touches it.
        self.assertEqual(guard(settings_with(), test_utils=exploding), "ok")

    def test_a_failure_to_check_the_test_environment_keeps_the_exception_off(self):
        # Import failure and a missing marker both leave a plain mismatch, not an "unavailable" error.
        refused(self, self.derived_settings(), code="mismatch", test_utils=None)
        broken = types.ModuleType("django.test.utils")  # no _TestState attribute at all
        refused(self, self.derived_settings(), code="mismatch", test_utils=broken)
        # The exact base database is unaffected by those failures.
        self.assertEqual(guard(settings_with({"default": db()}, EDUSEKAI_ALLOW_DERIVED_TEST_DB=True), test_utils=None),
                         "ok")

    def test_only_the_exact_derived_name_with_matching_host_and_port_is_accepted(self):
        accepted = {"default": db(name=self.DERIVED)}
        self.assertEqual(guard(self.derived_settings(databases=accepted), test_runner_active=True), "ok")
        refused_entries = [
            db(name=self.DERIVED, host="localhost"), db(name=self.DERIVED, host="10.0.0.5"),
            db(name=self.DERIVED, host=""), db(name=self.DERIVED, port="5433"), db(name=self.DERIVED, port=""),
            db(name="other_db"), db(name="test_other_db"), db(name="test_"), db(name="TEST_edusekai_db"),
            db(name="test_edusekai_db_1"),      # a parallel-run style suffix: not accepted (unresolved policy)
            db(name="test_edusekai_db_extra"), db(name="test__edusekai_db"), db(name="test_test_edusekai_db"),
            db(name="xtest_edusekai_db"), db(name=""),
        ]
        for entry in refused_entries:
            with self.subTest(name=entry["NAME"], host=entry["HOST"], port=entry["PORT"]):
                refused(self, self.derived_settings(databases={"default": entry}), code="mismatch",
                        test_runner_active=True)

    def test_the_base_database_and_other_outcomes_keep_their_codes_when_the_exception_is_on(self):
        self.assertEqual(guard(self.derived_settings(databases={"default": db()}), test_runner_active=True), "ok")
        for expected, code in (("", "absent"), (None, "absent"), ("garbage", "malformed"), ("db@host", "malformed")):
            with self.subTest(expected=expected):
                refused(self, self.derived_settings(expected=expected), code=code, test_runner_active=True)
        refused(self, self.derived_settings(databases={"default": db(name="other_db")}), code="mismatch",
                test_runner_active=True)

    def test_refusal_errors_are_unchanged_and_sanitised_when_the_exception_is_on(self):
        for entry in (db(name="secretly_named_db", host="secret-host.internal", port="6543"),
                      db(name=self.DERIVED, host="secret-host.internal")):
            with self.subTest(name=entry["NAME"]):
                error = refused(self, self.derived_settings(databases={"default": entry}), code="mismatch",
                                test_runner_active=True)
                self.assertEqual(str(error), "database identity guard refused operation 'create_tenant' "
                                             "(tier: provisioning, code: mismatch)")
                self.assertEqual(leaks(error), [])

    def test_explicit_aliases_follow_the_same_rule(self):
        databases = {"default": db(), "tenants": db(name=self.DERIVED)}
        self.assertEqual(guard(self.derived_settings(databases=databases), alias="tenants", test_runner_active=True),
                         "ok")
        refused(self, self.derived_settings(databases=databases), code="mismatch", alias="tenants",
                test_runner_active=False)


class InputValidationTests(unittest.TestCase):
    def untouched_django(self):
        """Settings whose every read fails the test: validation must happen before any lookup."""
        settings_obj = settings_with()
        calls = []
        return settings_obj, calls

    def test_unknown_tiers_are_refused_and_never_treated_as_a_default(self):
        for tier in ("", "Destructive", "provisioning ", "other", "invalid", None, 5, ["destructive"], b"destructive"):
            with self.subTest(tier=tier):
                settings_obj, calls = self.untouched_django()
                with self.assertRaises(IdentityGuardError) as caught:
                    with fake_django(settings_obj, alias_calls=calls):
                        require_expected_database("create_tenant", tier=tier)
                error = caught.exception
                self.assertEqual((error.code, error.operation, error.tier), ("unavailable", "create_tenant", "invalid"))
                self.assertEqual(settings_obj.accessed, [])
                self.assertEqual(calls, [])

    def test_invalid_operation_labels_are_refused_without_being_echoed(self):
        for operation in ("", None, 5, "Create_Tenant", "has space", "x\n", "a" * 65, "bad;rm", "../etc", "ünï",
                          "1abc", "-abc", b"create", [], "drop schema " + SECRET):
            with self.subTest(operation=repr(operation)[:20]):
                settings_obj, calls = self.untouched_django()
                with self.assertRaises(IdentityGuardError) as caught:
                    with fake_django(settings_obj, alias_calls=calls):
                        require_expected_database(operation, tier=TIER_DESTRUCTIVE)
                error = caught.exception
                self.assertEqual((error.code, error.operation, error.tier), ("unavailable", "invalid", TIER_DESTRUCTIVE))
                self.assertNotIn(SECRET, str(error) + repr(error))
                self.assertEqual(settings_obj.accessed, [])

    def test_valid_labels_are_accepted(self):
        for operation in ("create_tenant", "drop_schema", "seed.demo:clear", "a", "cleanup-public_db9", "x" * 64):
            with self.subTest(operation=operation):
                self.assertEqual(guard(settings_with(), operation=operation), "ok")

    def test_tier_is_keyword_only(self):
        with self.assertRaises(TypeError):
            require_expected_database("create_tenant", TIER_DESTRUCTIVE)


class AliasTests(unittest.TestCase):
    DATABASES = {"default": db(name="wrong_db"), "tenants": db(), "replica": db(host="10.0.0.9")}

    def test_an_explicit_alias_is_used_as_supplied(self):
        calls = []
        self.assertEqual(guard(settings_with(self.DATABASES), alias="tenants", alias_calls=calls), "ok")
        self.assertEqual(calls, [])  # the tenant alias is not resolved when an alias is supplied
        refused(self, settings_with(self.DATABASES), code="mismatch", alias="default")
        refused(self, settings_with(self.DATABASES), code="mismatch", alias="replica")

    def test_the_tenant_alias_is_resolved_when_no_alias_is_given(self):
        calls = []
        self.assertEqual(guard(settings_with(self.DATABASES), tenant_alias="tenants", alias_calls=calls), "ok")
        self.assertEqual(calls, [1])
        calls = []
        refused(self, settings_with(self.DATABASES), code="mismatch", tenant_alias="default", alias_calls=calls)
        self.assertEqual(calls, [1])

    def test_a_missing_alias_is_unavailable_with_no_fallback_to_default(self):
        matching_default = {"default": db()}
        refused(self, settings_with(matching_default), code="unavailable", alias="missing")
        refused(self, settings_with(matching_default), code="unavailable", tenant_alias="missing")

    def test_unusable_aliases_are_unavailable(self):
        for alias in ("", 5, ["default"], b"default"):
            with self.subTest(alias=alias):
                refused(self, settings_with(), code="unavailable", alias=alias)
        refused(self, settings_with(), code="unavailable", tenant_alias=None)  # the tenant alias resolved to None
        refused(self, settings_with(), code="unavailable", tenant_alias="")


class UnexpectedFailureTests(unittest.TestCase):
    def test_alias_resolution_failure_is_unavailable_and_hides_the_message(self):
        error = refused(self, settings_with(), code="unavailable", alias_error=RuntimeError("password=" + SECRET))
        self.assertEqual(leaks(error), [])
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)

    def test_settings_failures_are_unavailable(self):
        class Unconfigured:
            @property
            def EDUSEKAI_EXPECTED_DATABASE(self):
                raise RuntimeError("settings are not configured " + SECRET)

        class NoDatabases:
            EDUSEKAI_EXPECTED_DATABASE = EXPECTED

        class BadDatabases:
            EDUSEKAI_EXPECTED_DATABASE = EXPECTED
            DATABASES = None

        for settings_obj in (Unconfigured(), NoDatabases(), BadDatabases()):
            with self.subTest(settings=type(settings_obj).__name__):
                error = refused(self, settings_obj, code="unavailable")
                self.assertEqual(leaks(error), [])

    def test_a_database_entry_that_is_not_a_mapping_is_unavailable(self):
        for entry in (None, "edusekai_db", 5432, ["a"], object()):
            with self.subTest(entry=type(entry).__name__):
                refused(self, settings_with({"default": entry}), code="unavailable")

    def test_django_conf_failing_to_import_is_unavailable(self):
        with mock.patch.dict(sys.modules, {"django.conf": None}):
            with self.assertRaises(IdentityGuardError) as caught:
                require_expected_database("create_tenant", tier=TIER_PROVISIONING)
        self.assertEqual(caught.exception.code, "unavailable")

    def test_tenant_alias_helper_failing_to_import_is_unavailable(self):
        with fake_django(settings_with()):
            with mock.patch.dict(sys.modules, {"django_tenants.utils": None}):
                with self.assertRaises(IdentityGuardError) as caught:
                    require_expected_database("create_tenant", tier=TIER_PROVISIONING)
        self.assertEqual(caught.exception.code, "unavailable")

    def test_base_exceptions_are_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            guard(settings_with(), alias_error=KeyboardInterrupt())


class NoLeakTests(unittest.TestCase):
    def test_no_refusal_exposes_connection_details_or_credentials(self):
        secret_db = db(name="secretly_named_db", host="secret-host.internal", port="6543")
        cases = [
            (settings_with({"default": secret_db}), {}),                                    # mismatch
            (settings_with({"default": secret_db}, expected="garbage"), {}),                # malformed
            (settings_with({"default": secret_db}, expected=""), {}),                       # absent
            (settings_with({"default": secret_db}), {"alias": "nope"}),                     # unavailable
            (settings_with({"default": secret_db}), {"alias_error": RuntimeError(SECRET)}),  # unavailable
        ]
        for settings_obj, kwargs in cases:
            for tier in TIERS:
                with self.subTest(tier=tier, kwargs=sorted(kwargs)):
                    with self.assertRaises(IdentityGuardError) as caught:
                        guard(settings_obj, tier=tier, **kwargs)
                    self.assertEqual(leaks(caught.exception), [])
                    self.assertIn(caught.exception.code, db_guard.GUARD_CODES)

    def test_the_message_is_fixed_text_built_from_validated_values(self):
        error = IdentityGuardError("mismatch", "create_tenant", TIER_DESTRUCTIVE)
        self.assertEqual(str(error), "database identity guard refused operation 'create_tenant' "
                                     "(tier: destructive, code: mismatch)")
        self.assertEqual(error.args, (str(error),))

    def test_the_error_class_replaces_values_outside_the_fixed_sets(self):
        error = IdentityGuardError(SECRET, SECRET + " raw", SECRET)
        self.assertEqual((error.code, error.operation, error.tier), ("unavailable", "invalid", "invalid"))
        self.assertNotIn(SECRET, str(error) + repr(error) + repr(vars(error)))

    def test_the_error_survives_pickling_semantics(self):
        error = IdentityGuardError("absent", "seed_public", TIER_PROVISIONING)
        factory, args = error.__reduce__()
        clone = factory(*args)
        self.assertEqual((clone.code, clone.operation, clone.tier), ("absent", "seed_public", TIER_PROVISIONING))

    def test_the_error_is_not_a_database_or_validation_error_type(self):
        self.assertTrue(issubclass(IdentityGuardError, Exception))
        self.assertEqual(IdentityGuardError.__mro__[1], Exception)


class NoDatabaseAccessTests(unittest.TestCase):
    def test_the_adapter_never_touches_django_db(self):
        # fake_django installs a django.db whose every attribute access fails the test.
        self.assertEqual(guard(settings_with()), "ok")
        refused(self, settings_with({"default": db(name="other")}), code="mismatch")

    def test_the_code_never_imports_django_db_or_names_connections_or_cursors(self):
        # Checked on the syntax tree, so the docstring (which says these are NOT used) is ignored.
        tree = ast.parse((BACKEND / "config" / "db_guard.py").read_text(encoding="utf-8"))
        modules, names = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        self.assertFalse([m for m in modules if m == "django.db" or m.startswith("django.db.")], modules)
        for forbidden in ("connections", "connection", "cursor", "execute"):
            self.assertNotIn(forbidden, names)


class ImportSafetyTests(unittest.TestCase):
    def module_level_imports(self):
        tree = ast.parse((BACKEND / "config" / "db_guard.py").read_text(encoding="utf-8"))
        imported = set()
        for node in tree.body:  # module level only; lazy imports inside functions are allowed
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        return imported

    def test_module_level_imports_are_standard_library_and_the_pure_policy_only(self):
        self.assertEqual(self.module_level_imports(), {"re", "collections", "config"})

    def test_django_imports_are_lazy_and_inside_the_adapter(self):
        tree = ast.parse((BACKEND / "config" / "db_guard.py").read_text(encoding="utf-8"))
        lazy = set()
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            for node in ast.walk(function):
                if isinstance(node, ast.ImportFrom):
                    lazy.add(node.module)
        self.assertEqual(lazy, {"django.conf", "django_tenants.utils", "django.test.utils"})

    def test_importing_the_adapter_loads_no_project_models_or_database_driver(self):
        code = (
            "import sys\n"
            "import config.db_guard\n"
            "apps = {'organizations', 'accounts', 'payments', 'profiles', 'students', 'staff', 'academics',\n"
            "        'fees', 'roles', 'core', 'families', 'attendance', 'timetable', 'examinations'}\n"
            "loaded = sorted(m for m in sys.modules if m.split('.')[0] in apps)\n"
            "assert not loaded, loaded\n"
            "assert 'psycopg2' not in sys.modules, 'database driver loaded'\n"
            "from django.conf import settings\n"
            "assert not settings.configured, 'importing the adapter configured Django settings'\n"
            "print('safe')\n"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=BACKEND, capture_output=True, text=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("safe", result.stdout)


if __name__ == "__main__":
    unittest.main()
