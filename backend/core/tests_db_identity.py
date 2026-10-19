"""Unit tests for the database-identity helpers and the system-check adapter.

No database and no Django settings are used: everything runs on plain values.
Run with:  python -m unittest core.tests_db_identity   (from the backend folder)
"""

import unittest
from types import SimpleNamespace

from config import db_identity as ident
from core import checks

DB = {"NAME": "edusekai_db", "HOST": "127.0.0.1", "PORT": "5432", "USER": "dbuser", "PASSWORD": "s3cretpw"}
EXPECTED = "edusekai_db@127.0.0.1:5432"


def codes(findings):
    return [f.code for f in findings]


class ParseExpectedTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(ident.parse_expected(EXPECTED), ident.Identity("edusekai_db", "127.0.0.1", "5432"))
        self.assertEqual(ident.parse_expected("  db@host.example:05432 "), ident.Identity("db", "host.example", "5432"))

    def test_invalid_forms_are_rejected(self):
        for bad in ("", "   ", "edusekai_db", "edusekai_db@127.0.0.1", "@127.0.0.1:5432", "db@:5432",
                    "db@host:", "db@host:abc", "db@host:0", "db@host:65536", "db@host:-1",
                    "db name@host:5432", "db@ho st:5432", "db@::1:5432", "a@b@host:5432x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ident.parse_expected(bad)

    def test_none_is_rejected(self):
        with self.assertRaises(ValueError):
            ident.parse_expected(None)


class ActualIdentityTests(unittest.TestCase):
    def test_reads_only_name_host_port(self):
        actual = ident.actual_identity(DB)
        self.assertEqual(actual, ident.Identity("edusekai_db", "127.0.0.1", "5432"))
        self.assertNotIn("dbuser", repr(actual))
        self.assertNotIn("s3cretpw", repr(actual))

    def test_port_is_normalised_and_missing_values_are_empty(self):
        self.assertEqual(ident.actual_identity({"NAME": "d", "HOST": "h", "PORT": 5432}).port, "5432")
        self.assertEqual(ident.actual_identity({"NAME": "d", "HOST": "h", "PORT": "05432"}).port, "5432")
        self.assertEqual(ident.actual_identity({}), ident.Identity("", "", ""))
        self.assertEqual(ident.actual_identity({"NAME": None, "HOST": None, "PORT": None}), ident.Identity("", "", ""))


class MatchingTests(unittest.TestCase):
    expected = ident.Identity("edusekai_db", "127.0.0.1", "5432")

    def test_exact_match(self):
        self.assertTrue(ident.matches(self.expected, ident.Identity("edusekai_db", "127.0.0.1", "5432")))

    def test_each_field_mismatch(self):
        for actual, field in ((ident.Identity("other_db", "127.0.0.1", "5432"), "name"),
                              (ident.Identity("edusekai_db", "10.0.0.5", "5432"), "host"),
                              (ident.Identity("edusekai_db", "127.0.0.1", "5433"), "port")):
            with self.subTest(field=field):
                self.assertFalse(ident.matches(self.expected, actual))
                self.assertEqual(ident.differing_fields(self.expected, actual), [field])

    def test_localhost_is_a_different_identity_and_host_is_case_sensitive(self):
        self.assertFalse(ident.matches(self.expected, ident.Identity("edusekai_db", "localhost", "5432")))
        self.assertFalse(ident.matches(ident.Identity("d", "Host", "5432"), ident.Identity("d", "host", "5432")))

    def test_derived_test_database_is_accepted_only_on_the_same_host_and_port(self):
        self.assertTrue(ident.matches(self.expected, ident.Identity("test_edusekai_db", "127.0.0.1", "5432")))
        self.assertFalse(ident.matches(self.expected, ident.Identity("test_edusekai_db", "10.0.0.5", "5432")))
        self.assertFalse(ident.matches(self.expected, ident.Identity("test_edusekai_db", "127.0.0.1", "5433")))
        self.assertFalse(ident.matches(self.expected, ident.Identity("test_other_db", "127.0.0.1", "5432")))
        self.assertFalse(ident.matches(self.expected, ident.Identity("test_test_edusekai_db", "127.0.0.1", "5432")))


class EvaluateTests(unittest.TestCase):
    def test_matching_configuration_has_no_findings(self):
        self.assertEqual(ident.evaluate("development", EXPECTED, DB), [])

    def test_derived_test_database_has_no_findings(self):
        test_db = dict(DB, NAME="test_edusekai_db")
        self.assertEqual(ident.evaluate("development", EXPECTED, test_db), [])

    def test_expected_not_set(self):
        for unset in ("", "   ", None):
            with self.subTest(unset=unset):
                findings = ident.evaluate("development", unset, DB)
                self.assertEqual(codes(findings), [ident.CODE_NOT_SET])
                self.assertIn("edusekai_db@127.0.0.1:5432", findings[0].message)

    def test_mismatch_names_the_differing_fields(self):
        findings = ident.evaluate("development", EXPECTED, dict(DB, NAME="mis_db", PORT="5433"))
        self.assertEqual(codes(findings), [ident.CODE_MISMATCH])
        self.assertIn("name, port", findings[0].message)
        self.assertIn("overrides the .env", findings[0].hint)

    def test_malformed_expected_value(self):
        findings = ident.evaluate("development", "not-an-identity", DB)
        self.assertEqual(codes(findings), [ident.CODE_MALFORMED])

    def test_bad_environment_label_is_reported_independently(self):
        findings = ident.evaluate("dev env!", EXPECTED, DB)
        self.assertEqual(codes(findings), [ident.CODE_BAD_LABEL])
        findings = ident.evaluate("dev env!", "", DB)
        self.assertEqual(codes(findings), [ident.CODE_BAD_LABEL, ident.CODE_NOT_SET])

    def test_unset_label_is_not_a_warning(self):
        self.assertEqual(ident.evaluate("", EXPECTED, DB), [])

    def test_messages_never_contain_credentials(self):
        for label, expected in (("development", ""), ("development", "x"), ("dev env!", EXPECTED),
                                ("development", "other@127.0.0.1:5432")):
            for finding in ident.evaluate(label, expected, DB):
                text = finding.message + " " + (finding.hint or "")
                self.assertNotIn("dbuser", text)
                self.assertNotIn("s3cretpw", text)


class ApplicationNameTests(unittest.TestCase):
    def test_default_and_label(self):
        self.assertEqual(ident.build_application_name(""), "edusekai:unset")
        self.assertEqual(ident.build_application_name(None), "edusekai:unset")
        self.assertEqual(ident.build_application_name("development"), "edusekai:development")

    def test_unsafe_characters_are_replaced(self):
        name = ident.build_application_name("dev env;DROP TABLE x")
        self.assertEqual(name, "edusekai:dev_env_DROP_TABLE_x")
        self.assertRegex(name, r"^[A-Za-z0-9_.:-]+$")

    def test_length_is_capped_at_63(self):
        name = ident.build_application_name("x" * 500)
        self.assertEqual(len(name), 63)
        self.assertTrue(name.startswith("edusekai:x"))

    def test_whitespace_only_label_is_unset(self):
        self.assertEqual(ident.build_application_name("   "), "edusekai:unset")


class CheckAdapterTests(unittest.TestCase):
    """core.checks adapts the findings to Django warnings; it never opens a connection."""

    def _settings(self, **overrides):
        values = dict(DATABASES={"default": DB}, EDUSEKAI_ENV="development", EDUSEKAI_EXPECTED_DATABASE=EXPECTED)
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_no_messages_when_identity_matches(self):
        self.assertEqual(checks.messages_from_settings(self._settings()), [])

    def test_mismatch_becomes_a_django_warning(self):
        messages = checks.messages_from_settings(self._settings(DATABASES={"default": dict(DB, NAME="mis_db")}))
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.id, ident.CODE_MISMATCH)
        self.assertEqual(message.level, 30)  # django.core.checks.WARNING
        self.assertIn("mis_db@127.0.0.1:5432", message.msg)
        self.assertTrue(message.hint)

    def test_unset_expected_database_warns(self):
        messages = checks.messages_from_settings(self._settings(EDUSEKAI_EXPECTED_DATABASE=""))
        self.assertEqual([m.id for m in messages], [ident.CODE_NOT_SET])

    def test_missing_settings_attributes_are_tolerated(self):
        messages = checks.messages_from_settings(SimpleNamespace(DATABASES={"default": DB}))
        self.assertEqual([m.id for m in messages], [ident.CODE_NOT_SET])
        messages = checks.messages_from_settings(SimpleNamespace())
        self.assertEqual([m.id for m in messages], [ident.CODE_NOT_SET])

    def test_check_is_registered_under_its_own_tag_and_accepts_kwargs(self):
        self.assertEqual(checks.check_database_identity.tags, ("edusekai",))
        self.assertNotIn("database", checks.check_database_identity.tags)


if __name__ == "__main__":
    unittest.main()
