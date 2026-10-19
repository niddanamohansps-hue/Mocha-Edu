"""Pure unit tests for config.db_identity.check_identity (database identity policy, Stage 3A).

Standard library only: no Django settings, no django.setup(), no test runner, no database.
Run from the backend folder with bytecode writing disabled:

    python -B -m unittest core.tests_db_guard
"""

import ast
import unittest
from pathlib import Path

from config import db_identity
from config.db_identity import (
    IDENTITY_ABSENT,
    IDENTITY_MALFORMED,
    IDENTITY_MISMATCH,
    IDENTITY_OK,
    IDENTITY_RESULTS,
    check_identity,
)

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED = "edusekai_db@127.0.0.1:5432"
# Credentials that must never be read or appear in a result:
SECRET_USER = "dbuser-SYNTH"
SECRET_PASSWORD = "pw-SYNTH-0000"


def settings_for(name="edusekai_db", host="127.0.0.1", port="5432", **extra):
    return {"NAME": name, "HOST": host, "PORT": port, "USER": SECRET_USER, "PASSWORD": SECRET_PASSWORD, **extra}


class ResultCodeTests(unittest.TestCase):
    def test_the_result_codes_are_the_four_fixed_strings(self):
        self.assertEqual(IDENTITY_RESULTS, ("ok", "absent", "malformed", "mismatch"))
        self.assertEqual((IDENTITY_OK, IDENTITY_ABSENT, IDENTITY_MALFORMED, IDENTITY_MISMATCH), IDENTITY_RESULTS)

    def test_allow_derived_test_is_keyword_only(self):
        with self.assertRaises(TypeError):
            check_identity(EXPECTED, settings_for(), True)

    def test_every_outcome_is_one_of_the_fixed_codes(self):
        cases = [(EXPECTED, settings_for()), ("", settings_for()), (None, settings_for()), ("garbage", settings_for()),
                 (EXPECTED, settings_for(name="other")), (EXPECTED, None), (EXPECTED, {}), (12345, settings_for())]
        for flag in (False, True):
            for expected, db in cases:
                with self.subTest(expected=type(expected).__name__, db=type(db).__name__, flag=flag):
                    self.assertIn(check_identity(expected, db, allow_derived_test=flag), IDENTITY_RESULTS)


class OkTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(check_identity(EXPECTED, settings_for()), IDENTITY_OK)

    def test_port_is_normalised_like_the_existing_helper(self):
        for port in (5432, "5432", "05432", " 5432 "):
            with self.subTest(port=port):
                self.assertEqual(check_identity(EXPECTED, settings_for(port=port)), IDENTITY_OK)

    def test_surrounding_whitespace_of_the_expected_value_is_ignored(self):
        self.assertEqual(check_identity("  " + EXPECTED + "\n", settings_for()), IDENTITY_OK)

    def test_enabling_the_derived_rule_does_not_change_an_exact_match(self):
        self.assertEqual(check_identity(EXPECTED, settings_for(), allow_derived_test=True), IDENTITY_OK)


class AbsentTests(unittest.TestCase):
    def test_missing_expected_identity(self):
        for value in (None, "", "   ", "\t\n"):
            for flag in (False, True):
                with self.subTest(value=value, flag=flag):
                    self.assertEqual(check_identity(value, settings_for(), allow_derived_test=flag), IDENTITY_ABSENT)


class MalformedTests(unittest.TestCase):
    def test_malformed_expected_identity(self):
        for value in ("edusekai_db", "edusekai_db@127.0.0.1", "@127.0.0.1:5432", "db@:5432", "db@host:abc",
                      "db@host:0", "db@host:65536", "db@::1:5432", "db @host:5432", "db@host :5432", "a@b@c"):
            for flag in (False, True):
                with self.subTest(value=value, flag=flag):
                    self.assertEqual(check_identity(value, settings_for(), allow_derived_test=flag), IDENTITY_MALFORMED)

    def test_a_value_that_is_not_a_string_is_malformed_and_none_is_absent(self):
        for value in (5432, 1.5, ["a@b:1"], {"a": 1}, b"a@b:1", True):
            with self.subTest(value=value):
                self.assertEqual(check_identity(value, settings_for()), IDENTITY_MALFORMED)
        self.assertEqual(check_identity(None, settings_for()), IDENTITY_ABSENT)


class MismatchTests(unittest.TestCase):
    def test_name_mismatch(self):
        for name in ("other_db", "Edusekai_db", "edusekai_db2", "edusekai", "edusekai_db_", ""):
            with self.subTest(name=name):
                self.assertEqual(check_identity(EXPECTED, settings_for(name=name)), IDENTITY_MISMATCH)

    def test_host_mismatch(self):
        for host in ("localhost", "127.0.0.2", "db", "127.0.0.1.example", "", "LOCALHOST"):
            with self.subTest(host=host):
                self.assertEqual(check_identity(EXPECTED, settings_for(host=host)), IDENTITY_MISMATCH)
        # Host comparison is case-sensitive, as in the existing helper.
        self.assertEqual(check_identity("db@Host:5432", settings_for(name="db", host="host")), IDENTITY_MISMATCH)

    def test_port_mismatch(self):
        for port in ("5433", 5433, "", None, "abc"):
            with self.subTest(port=port):
                self.assertEqual(check_identity(EXPECTED, settings_for(port=port)), IDENTITY_MISMATCH)

    def test_missing_or_empty_settings_never_match(self):
        for db in (None, {}, {"NAME": None, "HOST": None, "PORT": None}, {"USER": "u"}):
            with self.subTest(db=db):
                self.assertEqual(check_identity(EXPECTED, db), IDENTITY_MISMATCH)
                self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=True), IDENTITY_MISMATCH)


class DerivedTestDatabaseTests(unittest.TestCase):
    TEST_NAME = "test_edusekai_db"

    def test_exact_derived_name_is_accepted_only_when_enabled(self):
        db = settings_for(name=self.TEST_NAME)
        self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=True), IDENTITY_OK)

    def test_derived_name_is_refused_when_disabled_or_default(self):
        db = settings_for(name=self.TEST_NAME)
        self.assertEqual(check_identity(EXPECTED, db), IDENTITY_MISMATCH)
        self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=False), IDENTITY_MISMATCH)

    def test_only_the_value_true_enables_the_rule(self):
        db = settings_for(name=self.TEST_NAME)
        for value in (1, "yes", "True", [1], object(), None, 0, ""):
            with self.subTest(value=value):
                self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=value), IDENTITY_MISMATCH)

    def test_derived_name_with_a_different_host_or_port_is_refused(self):
        for db in (settings_for(name=self.TEST_NAME, host="localhost"),
                   settings_for(name=self.TEST_NAME, host="10.0.0.5"),
                   settings_for(name=self.TEST_NAME, host=""),
                   settings_for(name=self.TEST_NAME, port="5433"),
                   settings_for(name=self.TEST_NAME, port="")):
            with self.subTest(host=db["HOST"], port=db["PORT"]):
                self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=True), IDENTITY_MISMATCH)

    def test_unrelated_names_are_refused_even_when_the_rule_is_enabled(self):
        for name in ("other_db", "test_other_db", "test_", "test", "TEST_edusekai_db", "Test_edusekai_db",
                     "test_edusekai_db_extra", "xtest_edusekai_db", "test__edusekai_db",
                     "test_edusekai", "edusekai_db_test", "test_test_edusekai_db"):
            with self.subTest(name=name):
                self.assertEqual(check_identity(EXPECTED, settings_for(name=name), allow_derived_test=True),
                                 IDENTITY_MISMATCH)

    def test_enabling_the_rule_does_not_rescue_a_non_matching_host_with_the_base_name(self):
        self.assertEqual(check_identity(EXPECTED, settings_for(host="localhost"), allow_derived_test=True),
                         IDENTITY_MISMATCH)

    def test_the_rule_derives_from_the_expected_name_only(self):
        # Expected "other_db": the derived name is "test_other_db", not "test_edusekai_db".
        self.assertEqual(check_identity("other_db@127.0.0.1:5432", settings_for(name="test_other_db"),
                                        allow_derived_test=True), IDENTITY_OK)
        self.assertEqual(check_identity("other_db@127.0.0.1:5432", settings_for(name=self.TEST_NAME),
                                        allow_derived_test=True), IDENTITY_MISMATCH)


class ConsistencyWithExistingHelpersTests(unittest.TestCase):
    """check_identity wraps the existing helpers; their behavior is unchanged."""

    CASES = [settings_for(), settings_for(port=5432), settings_for(port="05432"), settings_for(name="other"),
             settings_for(host="localhost"), settings_for(port="5433"), settings_for(name="test_edusekai_db"),
             settings_for(name="test_edusekai_db", host="localhost"), settings_for(name="test_edusekai_db", port="1"),
             settings_for(name="test_other_db")]

    def test_enabled_result_agrees_with_matches(self):
        expected = db_identity.parse_expected(EXPECTED)
        for db in self.CASES:
            with self.subTest(name=db["NAME"], host=db["HOST"], port=db["PORT"]):
                actual = db_identity.actual_identity(db)
                self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=True) == IDENTITY_OK,
                                 db_identity.matches(expected, actual))

    def test_default_result_agrees_with_differing_fields(self):
        expected = db_identity.parse_expected(EXPECTED)
        for db in self.CASES:
            with self.subTest(name=db["NAME"], host=db["HOST"], port=db["PORT"]):
                actual = db_identity.actual_identity(db)
                self.assertEqual(check_identity(EXPECTED, db) == IDENTITY_OK,
                                 not db_identity.differing_fields(expected, actual))

    def test_matches_and_evaluate_are_unchanged_for_representative_inputs(self):
        expected = db_identity.parse_expected(EXPECTED)
        self.assertTrue(db_identity.matches(expected, db_identity.actual_identity(settings_for(name="test_edusekai_db"))))
        self.assertFalse(db_identity.matches(expected, db_identity.actual_identity(settings_for(name="other"))))
        self.assertEqual(db_identity.evaluate("development", EXPECTED, settings_for()), [])
        self.assertEqual([f.code for f in db_identity.evaluate("development", "", settings_for())],
                         [db_identity.CODE_NOT_SET])
        self.assertEqual([f.code for f in db_identity.evaluate("development", "garbage", settings_for())],
                         [db_identity.CODE_MALFORMED])
        self.assertEqual([f.code for f in db_identity.evaluate("development", EXPECTED, settings_for(name="other"))],
                         [db_identity.CODE_MISMATCH])


class NoLeakTests(unittest.TestCase):
    def test_results_are_fixed_codes_without_connection_details_or_credentials(self):
        db = settings_for(name="secretly_named_db", host="secret-host.internal", port="6543")
        for expected in (EXPECTED, "secretly_named_db@secret-host.internal:6543", "garbage", "", None):
            for flag in (False, True):
                result = check_identity(expected, db, allow_derived_test=flag)
                with self.subTest(expected=expected, flag=flag):
                    self.assertIn(result, IDENTITY_RESULTS)
                    self.assertIsInstance(result, str)
                    shown = repr(result)
                    for sensitive in (SECRET_USER, SECRET_PASSWORD, "secretly_named_db", "secret-host", "6543",
                                      "edusekai_db", "127.0.0.1"):
                        self.assertNotIn(sensitive, shown)

    def test_credentials_are_never_read(self):
        class Guarded(dict):
            def get(self, key, default=None):
                if key in ("USER", "PASSWORD", "OPTIONS"):
                    raise AssertionError(f"{key} must not be read")
                return super().get(key, default)

            def __getitem__(self, key):
                if key in ("USER", "PASSWORD", "OPTIONS"):
                    raise AssertionError(f"{key} must not be read")
                return super().__getitem__(key)

        db = Guarded(settings_for(OPTIONS={"service": "x"}))
        self.assertEqual(check_identity(EXPECTED, db), IDENTITY_OK)
        self.assertEqual(check_identity(EXPECTED, db, allow_derived_test=True), IDENTITY_OK)

    def test_inputs_are_not_mutated_and_results_are_deterministic(self):
        db = settings_for()
        snapshot = dict(db)
        results = {check_identity(EXPECTED, db, allow_derived_test=True) for _ in range(5)}
        self.assertEqual(results, {IDENTITY_OK})
        self.assertEqual(db, snapshot)


class PurityTests(unittest.TestCase):
    def test_the_policy_module_imports_only_the_standard_library(self):
        tree = ast.parse((BACKEND / "config" / "db_identity.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, {"re", "collections"}, imported)
        for forbidden in ("django", "psycopg2", "psycopg", "celery", "decouple", "logging"):
            self.assertNotIn(forbidden, imported)


if __name__ == "__main__":
    unittest.main()
