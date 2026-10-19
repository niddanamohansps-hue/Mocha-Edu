"""Unit tests for the migration gate (config/migration_gate.py).

Pure standard library: no Django settings, no django.setup(), no database, no
migrations. Run from the backend folder with bytecode writing disabled:

    python -B -m unittest core.tests_migration_gate

The tests also read a few project files as text (entrypoint, compose, README,
.env.example, manage.py) to pin the Docker and documentation requirements; nothing
is executed from them.
"""

import ast
import contextlib
import importlib.util
import io
import itertools
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from config import db_identity
from config import migration_gate as gate

BACKEND = Path(__file__).resolve().parents[1]
DB = "edusekai_db"
TARGET = {
    "NAME": DB,
    "HOST": "127.0.0.1",
    "PORT": "5432",
    "EDUSEKAI_ENV": "development",
    "EDUSEKAI_EXPECTED_DATABASE": "edusekai_db@127.0.0.1:5432",
    # Credentials that must never be read or shown:
    "USER": "dbuser",
    "PASSWORD": "s3cretpw",
}
APPLY = ["--apply", "--confirm-database", DB]
FAKE_SECRET = "SECRET-TOKEN-xyz123"  # must never appear in any message, notice, stdout or stderr
MANAGE_PY = BACKEND / "manage.py"


class GateCase(unittest.TestCase):
    def evaluate(self, *args, target=None, command="manage.py"):
        self.loads = 0
        resolved = TARGET if target is None else target

        def load():
            self.loads += 1
            if isinstance(resolved, BaseException):
                raise resolved
            return dict(resolved)

        argv = [command, *args]
        decision = gate.evaluate(argv, load)
        self.assertEqual(argv, [command, *args], "evaluate() must not mutate its input")
        return decision

    def assertAllowed(self, *args, **kwargs):
        decision = self.evaluate(*args, **kwargs)
        self.assertTrue(decision.allowed, decision.message)
        self.assertEqual(decision.exit_code, 0)
        self.assertIsNone(decision.message)
        return decision

    def assertRefused(self, *args, contains=(), **kwargs):
        decision = self.evaluate(*args, **kwargs)
        self.assertFalse(decision.allowed, f"expected a refusal for {args}")
        self.assertEqual(decision.exit_code, gate.EXIT_REFUSED)
        self.assertIsNone(decision.argv)
        self.assertIsNone(decision.notice)
        for needle in ((contains,) if isinstance(contains, str) else contains):
            self.assertIn(needle, decision.message)
        for secret in ("s3cretpw", "dbuser"):
            self.assertNotIn(secret, decision.message)
        return decision


class PassThroughTests(GateCase):
    def test_other_commands_are_untouched_and_never_load_the_target(self):
        for args in (["runserver", "0.0.0.0:8000"], ["test", "students", "--keepdb"], ["makemigrations", "--noinput"],
                     ["showmigrations"], ["shell"], ["check"], ["collectstatic", "--noinput"],
                     ["help", "migrate"], ["--version"], ["--help"]):
            with self.subTest(args=args):
                decision = self.assertAllowed(*args)
                self.assertEqual(decision.argv, ["manage.py", *args])
                self.assertIsNone(decision.notice)
                self.assertEqual(self.loads, 0)

    def test_empty_and_minimal_argv(self):
        for argv in ([], ["manage.py"]):
            decision = gate.evaluate(argv, lambda: self.fail("must not load"))
            self.assertTrue(decision.allowed)
            self.assertEqual(decision.argv, argv)

    def test_wrappers_around_other_commands_pass_unchanged(self):
        for args in (["tenant_command", "showmigrations", "--schema=acme"], ["all_tenants_command", "showmigrations"],
                     ["all_tenants_command", "--no-public", "showmigrations"], ["tenant_command"]):
            with self.subTest(args=args):
                self.assertEqual(self.assertAllowed(*args).argv, ["manage.py", *args])


class BareAndIncompleteTests(GateCase):
    def test_bare_commands_are_refused_without_loading_the_target(self):
        for command in ("migrate", "migrate_schemas"):
            with self.subTest(command=command):
                decision = self.assertRefused(command, contains=("no migration scope", "--apply", "--confirm-database"))
                self.assertIn("showmigrations", decision.message)  # usage block
                self.assertEqual(self.loads, 0)

    def test_missing_pieces_are_each_reported(self):
        self.assertRefused("migrate_schemas", "--noinput", contains="no migration scope")
        self.assertRefused("migrate_schemas", "--shared", contains="--apply is required")
        self.assertRefused("migrate_schemas", "--shared", "--apply", contains="--confirm-database <database name> is required")
        self.assertRefused("migrate_schemas", *APPLY, contains="no migration scope")
        self.assertRefused("migrate_schemas", "--shared", "--confirm-database", DB, contains="--apply is required")

    def test_wrong_confirmation_is_refused(self):
        for wrong in ("Edusekai_db", "edusekai", "edusekai_db ", "test_edusekai_db", "mis_db"):
            with self.subTest(wrong=wrong):
                self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", wrong,
                                   contains="does not match the configured database name")
                self.assertEqual(self.loads, 1)  # identity was checked before comparing the confirmation

    def test_confirmation_edge_cases(self):
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database=", contains="needs the database name")
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", contains="requires a value")
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", "--noinput",
                           contains="requires a value")
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", DB,
                           "--confirm-database", DB, contains="more than once")
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--apply", "--confirm-database", DB,
                           contains="more than once")


class IdentityTests(GateCase):
    base = ["migrate_schemas", "--shared", *APPLY]

    def test_unset_expected_identity_is_refused(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                target = dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=value)
                self.assertRefused(*self.base, target=target, contains="EDUSEKAI_EXPECTED_DATABASE is not set")
        target = {k: v for k, v in TARGET.items() if k != "EDUSEKAI_EXPECTED_DATABASE"}
        self.assertRefused(*self.base, target=target, contains="EDUSEKAI_EXPECTED_DATABASE is not set")

    def test_malformed_expected_identity_is_refused(self):
        for value in ("edusekai_db", "edusekai_db@127.0.0.1", "@127.0.0.1:5432", "db@host:abc", "db@::1:5432"):
            with self.subTest(value=value):
                self.assertRefused(*self.base, target=dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=value),
                                   contains="is not valid")

    def test_every_field_must_match_exactly(self):
        for expected, field in (("other_db@127.0.0.1:5432", "name"), ("edusekai_db@10.0.0.5:5432", "host"),
                                ("edusekai_db@127.0.0.1:5433", "port"), ("edusekai_db@localhost:5432", "host"),
                                ("Edusekai_db@127.0.0.1:5432", "name")):
            with self.subTest(expected=expected):
                self.assertRefused(*self.base, target=dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=expected),
                                   contains=(f"differing: {field}", "Matching is exact"))

    def test_a_test_database_is_not_accepted_under_the_dev_identity(self):
        test_db = dict(TARGET, NAME="test_edusekai_db")
        # Stage 2's warning check accepts the derived test database...
        self.assertTrue(db_identity.matches(db_identity.parse_expected(TARGET["EDUSEKAI_EXPECTED_DATABASE"]),
                                            db_identity.actual_identity(test_db)))
        # ...but an apply must not.
        self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", "test_edusekai_db",
                           target=test_db, contains=("differing: name", "no test_ exception"))

    def test_the_test_database_can_be_applied_to_only_with_its_own_expected_identity(self):
        test_db = dict(TARGET, NAME="test_edusekai_db", EDUSEKAI_EXPECTED_DATABASE="test_edusekai_db@127.0.0.1:5432")
        self.assertAllowed("migrate_schemas", "--shared", "--apply", "--confirm-database", "test_edusekai_db", target=test_db)

    def test_exact_identity_is_allowed_and_port_is_normalised(self):
        self.assertAllowed(*self.base)
        self.assertAllowed(*self.base, target=dict(TARGET, PORT=5432))
        self.assertAllowed(*self.base, target=dict(TARGET, PORT="05432"))

    def test_a_target_that_cannot_be_loaded_fails_closed_without_echoing_the_error(self):
        decision = self.assertRefused(*self.base, target=RuntimeError("password is s3cretpw"),
                                      contains=("could not be determined", "RuntimeError"))
        self.assertNotIn("password is", decision.message)

    def test_gate_decision_matches_identity_differences(self):
        cases = [("edusekai_db@127.0.0.1:5432", dict(TARGET), True),
                 ("edusekai_db@127.0.0.1:5432", dict(TARGET, HOST="localhost"), False),
                 ("edusekai_db@127.0.0.1:5432", dict(TARGET, PORT="5433"), False),
                 ("edusekai_db@127.0.0.1:5432", dict(TARGET, NAME="other_db"), False),
                 ("edusekai_db@127.0.0.1:5432", dict(TARGET, NAME="test_edusekai_db"), False)]
        for expected, target, should_pass in cases:
            with self.subTest(expected=expected, target=target["NAME"], host=target["HOST"], port=target["PORT"]):
                target["EDUSEKAI_EXPECTED_DATABASE"] = expected
                identical = not db_identity.differing_fields(db_identity.parse_expected(expected),
                                                             db_identity.actual_identity(target))
                self.assertEqual(identical, should_pass)
                decision = self.evaluate("migrate_schemas", "--shared", "--apply", "--confirm-database", target["NAME"],
                                         target=target)
                self.assertEqual(decision.allowed, should_pass)


class ValidApplyTests(GateCase):
    def test_scope_forms_are_accepted_and_gate_flags_are_stripped(self):
        scopes = (["--shared"], ["--tenant"], ["--schema", "acme"], ["--schema=acme"],
                  ["-s", "acme"], ["-sacme"], ["--schema", "public"])
        for scope in scopes:
            with self.subTest(scope=scope):
                decision = self.assertAllowed("migrate_schemas", *scope, *APPLY)
                self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", *scope])
                self.assertEqual(self.loads, 1)

    def test_migrate_is_gated_exactly_like_migrate_schemas(self):
        decision = self.assertAllowed("migrate", "--shared", *APPLY)
        self.assertEqual(decision.argv, ["manage.py", "migrate", "--shared"])
        self.assertRefused("migrate", contains="no migration scope")

    def test_equals_form_of_the_confirmation_and_ordering(self):
        decision = self.assertAllowed("migrate_schemas", "--confirm-database=" + DB, "--shared", "--apply")
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared"])

    def test_other_django_options_are_kept_in_order(self):
        decision = self.assertAllowed("migrate_schemas", "-v", "2", "--shared", "--noinput", "--executor", "standard",
                                      "--traceback", *APPLY, "--no-color")
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "-v", "2", "--shared", "--noinput",
                                         "--executor", "standard", "--traceback", "--no-color"])
        decision = self.assertAllowed("migrate_schemas", "-v2", "--shared", *APPLY)
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "-v2", "--shared"])

    def test_returned_argv_is_a_new_list(self):
        argv = ["manage.py", "migrate_schemas", "--shared", *APPLY]
        decision = gate.evaluate(argv, lambda: dict(TARGET))
        self.assertIsNot(decision.argv, argv)
        self.assertEqual(argv, ["manage.py", "migrate_schemas", "--shared", *APPLY])

    def test_database_alias(self):
        self.assertAllowed("migrate_schemas", "--shared", "--database", "default", *APPLY)
        self.assertAllowed("migrate_schemas", "--shared", "--database=default", *APPLY)
        self.assertRefused("migrate_schemas", "--shared", "--database", "other", *APPLY, contains="'default' database alias")
        self.assertRefused("migrate_schemas", "--shared", "--database=replica", *APPLY, contains="'default' database alias")


class ScopeConflictTests(GateCase):
    """F1: an apply names exactly one scope; combinations and repeats are refused."""

    def test_more_than_one_scope_is_refused(self):
        combos = (["--shared", "--tenant"], ["--tenant", "--shared"], ["--schema", "acme", "--tenant"],
                  ["--schema", "acme", "--shared"], ["--schema", "public", "--shared"],
                  ["--schema", "public", "--tenant"], ["-s", "acme", "--tenant"], ["-sacme", "--shared"],
                  ["--shared", "--tenant", "--schema", "acme"])
        for combo in combos:
            with self.subTest(combo=combo):
                self.assertRefused("migrate_schemas", *combo, *APPLY, contains="give exactly one scope")
                self.assertEqual(self.loads, 0)

    def test_repeated_scope_options_are_refused(self):
        for combo in (["--shared", "--shared"], ["--tenant", "--tenant"], ["--schema", "a", "--schema", "a"],
                      ["-s", "a", "--schema", "a"], ["--schema=a", "-sa"]):
            with self.subTest(combo=combo):
                self.assertRefused("migrate_schemas", *combo, *APPLY, contains="more than once")
                self.assertEqual(self.loads, 0)

    def test_no_scope_is_refused_and_empty_schema_is_refused(self):
        self.assertRefused("migrate_schemas", *APPLY, contains="exactly one of --shared, --tenant or --schema NAME")
        self.assertRefused("migrate_schemas", "--schema=", *APPLY, contains="non-empty schema name")
        self.assertRefused("migrate_schemas", "-s", "", *APPLY, contains="non-empty schema name")

    def test_each_single_scope_is_accepted(self):
        for scope in (["--shared"], ["--tenant"], ["--schema", "acme"], ["--schema", "public"]):
            with self.subTest(scope=scope):
                self.assertAllowed("migrate_schemas", *scope, *APPLY)

    def test_schema_public_is_the_shared_scope(self):
        decision = self.assertAllowed("migrate_schemas", "--schema", "public", *APPLY)
        self.assertIn("scope: shared schema (public)", decision.notice)

    def test_plan_and_check_need_exactly_one_scope(self):
        # D2: --plan / --check are not read-only, so they name one scope like an apply.
        for flag in ("--plan", "--check"):
            with self.subTest(flag=flag):
                self.assertRefused("migrate_schemas", flag, contains="exactly one of --shared, --tenant or --schema NAME")
                self.assertRefused("migrate_schemas", "--shared", "--tenant", flag, contains="give exactly one scope")
                self.assertRefused("migrate_schemas", "--shared", "--shared", flag, contains="more than once")
                self.assertEqual(self.loads, 0)


class ProtectedOperationTests(GateCase):
    def test_app_label_alone_needs_no_destructive_flag(self):
        decision = self.assertAllowed("migrate_schemas", "--schema", "acme", "certificates", *APPLY)
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--schema", "acme", "certificates"])
        self.assertIn("protected operation: no", decision.notice)

    def test_explicit_targets_need_the_flag(self):
        for name in ("0001", "0002_alter_certificate_integrity_hash_idcardtoken", "zero"):
            with self.subTest(name=name):
                self.assertRefused("migrate_schemas", "--shared", "certificates", name, *APPLY,
                                   contains="need --allow-destructive")
                decision = self.assertAllowed("migrate_schemas", "--shared", "certificates", name, *APPLY,
                                              "--allow-destructive")
                self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared", "certificates", name])
                self.assertIn("protected operation: yes", decision.notice)

    def test_each_protected_flag_needs_the_destructive_flag(self):
        for flag in ("--fake", "--fake-initial", "--prune", "--run-syncdb"):
            with self.subTest(flag=flag):
                self.assertRefused("migrate_schemas", "--shared", flag, *APPLY, contains=("need --allow-destructive", flag))
                decision = self.assertAllowed("migrate_schemas", "--shared", flag, *APPLY, "--allow-destructive")
                self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared", flag])

    def test_prune_with_plan_is_protected(self):
        self.assertRefused("migrate_schemas", "--shared", "certificates", "--prune", "--plan", contains="--apply is required")
        self.assertRefused("migrate_schemas", "--shared", "certificates", "--prune", "--plan", *APPLY,
                           contains="need --allow-destructive")
        decision = self.assertAllowed("migrate_schemas", "--shared", "certificates", "--prune", "--plan", *APPLY,
                                      "--allow-destructive")
        self.assertIn("--plan", decision.argv)

    def test_run_syncdb_with_check_is_protected(self):
        self.assertRefused("migrate_schemas", "--shared", "--run-syncdb", "--check", contains="--apply is required")

    def test_unnecessary_destructive_flag_is_refused(self):
        self.assertRefused("migrate_schemas", "--shared", *APPLY, "--allow-destructive",
                           contains="no protected operation is present")
        self.assertRefused("migrate_schemas", "--shared", "certificates", *APPLY, "--allow-destructive",
                           contains="no protected operation is present")

    def test_duplicate_destructive_flag_is_refused(self):
        self.assertRefused("migrate_schemas", "--shared", "--fake", *APPLY, "--allow-destructive", "--allow-destructive",
                           contains="more than once")

    def test_too_many_positionals_are_refused(self):
        self.assertRefused("migrate_schemas", "--shared", "a", "b", "c", *APPLY, contains="too many positional")


class ListTests(GateCase):
    def test_list_is_refused_in_every_form(self):
        for args in (["--list"], ["-l"], ["--list", "--plan"], ["-l", "--shared"], ["--shared", "--list", *APPLY]):
            with self.subTest(args=args):
                decision = self.assertRefused("migrate_schemas", *args, contains=("showmigrations", "carry on"))
                self.assertEqual(self.loads, 0)
                self.assertNotIn("--apply is required", decision.message)  # the list message stands alone


class PlanAndCheckTests(GateCase):
    """D2: --plan / --check are NOT read-only (ensure_schema), so they get the apply target checks."""

    FLAGS = ("--plan", "--check")
    SCOPES = (["--shared"], ["--tenant"], ["--schema", "acme"], ["--schema=acme"], ["-s", "acme"],
              ["--schema", "public"])

    def test_one_scope_and_a_matching_identity_are_accepted_without_apply_or_confirmation(self):
        for flag in self.FLAGS:
            for scope in self.SCOPES:
                with self.subTest(flag=flag, scope=scope):
                    decision = self.assertAllowed("migrate_schemas", *scope, flag)
                    self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", *scope, flag])
                    self.assertEqual(self.loads, 1)
        decision = self.assertAllowed("migrate_schemas", "--shared", "certificates", "--plan")
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared", "certificates", "--plan"])
        self.assertAllowed("migrate", "--shared", "--check")  # migrate is gated exactly like migrate_schemas

    def test_the_notice_says_it_is_not_read_only_and_not_proof_of_acceptance(self):
        for flag in self.FLAGS:
            with self.subTest(flag=flag):
                notice = self.assertAllowed("migrate_schemas", "--shared", flag).notice
                self.assertTrue(notice.startswith("Migration gate: checks passed"))
                self.assertIn("'edusekai_db' at 127.0.0.1:5432 (environment: development)", notice)
                self.assertIn("scope: shared schema;", notice)
                self.assertIn("operation: plan/check", notice)
                self.assertIn("not guaranteed to be read-only", notice)
                self.assertIn("this notice does not mean Django accepted the arguments", notice)
                self.assertIn("does not verify the connection destination", notice)
                self.assertNotIn("protected operation", notice)
                for secret in ("s3cretpw", "dbuser"):
                    self.assertNotIn(secret, notice)
        self.assertIn("scope: shared schema (public)",
                      self.assertAllowed("migrate_schemas", "--schema", "public", "--plan").notice)

    def test_an_unset_malformed_or_mismatched_identity_is_refused(self):
        cases = ((dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=""), "EDUSEKAI_EXPECTED_DATABASE is not set"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=None), "EDUSEKAI_EXPECTED_DATABASE is not set"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="   "), "EDUSEKAI_EXPECTED_DATABASE is not set"),
                 ({k: v for k, v in TARGET.items() if k != "EDUSEKAI_EXPECTED_DATABASE"},
                  "EDUSEKAI_EXPECTED_DATABASE is not set"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="edusekai_db"), "is not valid"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="db@host:abc"), "is not valid"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="other_db@127.0.0.1:5432"), "differing: name"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="edusekai_db@localhost:5432"), "differing: host"),
                 (dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="edusekai_db@127.0.0.1:5433"), "differing: port"),
                 (dict(TARGET, NAME="test_edusekai_db"), "no test_ exception"),
                 (dict(TARGET, HOST=""), "differing: host"),
                 (dict(TARGET, PORT=""), "differing: port"))
        for flag in self.FLAGS:
            for target, needle in cases:
                with self.subTest(flag=flag, needle=needle, name=target.get("NAME"), host=target.get("HOST")):
                    decision = self.assertRefused("migrate_schemas", "--shared", flag, target=target, contains=needle)
                    self.assertEqual(self.loads, 1)  # refused only after the identity was compared
                    self.assertNotIn("checks passed", decision.message)

    def test_a_target_that_cannot_be_loaded_is_refused_without_echoing_the_error(self):
        for flag in self.FLAGS:
            with self.subTest(flag=flag):
                decision = self.assertRefused("migrate_schemas", "--shared", flag, target=RuntimeError(FAKE_SECRET),
                                              contains=("could not be determined", "RuntimeError"))
                self.assertNotIn(FAKE_SECRET, decision.message)

    def test_target_overrides_are_refused_before_the_target_is_loaded(self):
        for flag in self.FLAGS:
            for extra, needle in ((["--settings", "config.other"], "not allowed when applying"),
                                  (["--settings=config.other"], "not allowed when applying"),
                                  (["--pythonpath", "/tmp"], "not allowed when applying"),
                                  (["--pythonpath=/tmp"], "not allowed when applying"),
                                  (["--database", "other"], "'default' database alias"),
                                  (["--database=replica"], "'default' database alias")):
                with self.subTest(flag=flag, extra=extra):
                    decision = self.assertRefused("migrate_schemas", "--shared", flag, *extra, contains=needle)
                    if "alias" not in needle:
                        self.assertIn("or running --plan / --check", decision.message)
                    self.assertEqual(self.loads, 0)
            with self.subTest(flag=flag, extra="default alias"):
                self.assertAllowed("migrate_schemas", "--shared", flag, "--database", "default")
                self.assertAllowed("migrate_schemas", "--shared", flag, "--database=default")

    def test_scope_problems_are_refused_before_the_target_is_loaded(self):
        for flag in self.FLAGS:
            for scope, needle in (([], "no migration scope"), (["--shared", "--tenant"], "give exactly one scope"),
                                  (["--schema", "a", "--shared"], "give exactly one scope"),
                                  (["--shared", "--shared"], "more than once"),
                                  (["--schema=", ], "non-empty schema name"), (["-s", ""], "non-empty schema name")):
                with self.subTest(flag=flag, scope=scope):
                    self.assertRefused("migrate_schemas", *scope, flag, contains=needle)
                    self.assertEqual(self.loads, 0)

    def test_plan_and_check_cannot_be_combined_with_gate_only_flags(self):
        for extra in (["--apply"], ["--confirm-database", DB], ["--allow-destructive"], APPLY):
            for flag in self.FLAGS:
                with self.subTest(flag=flag, extra=extra):
                    self.assertRefused("migrate_schemas", "--shared", flag, *extra, contains="never apply anything")
                    self.assertEqual(self.loads, 0)

    def test_protected_operations_stay_on_the_apply_path(self):
        for flag in self.FLAGS:
            for protected in (["--prune"], ["--fake"], ["--fake-initial"], ["--run-syncdb"], ["certificates", "0001"],
                              ["certificates", "zero"]):
                with self.subTest(flag=flag, protected=protected):
                    # Not an ordinary plan: --apply, the confirmation and --allow-destructive are all required.
                    self.assertRefused("migrate_schemas", "--shared", *protected, flag,
                                       contains=("--apply is required", "--confirm-database", "need --allow-destructive"))
                    self.assertEqual(self.loads, 0)
                    self.assertRefused("migrate_schemas", "--shared", *protected, flag, *APPLY,
                                       contains="need --allow-destructive")
                    decision = self.assertAllowed("migrate_schemas", "--shared", *protected, flag, *APPLY,
                                                  "--allow-destructive")
                    self.assertIn("protected operation: yes", decision.notice)
                    self.assertNotIn("operation: plan/check", decision.notice)

    def test_list_abbreviations_and_help_keep_their_existing_handling(self):
        self.assertRefused("migrate_schemas", "--shared", "--plan", "--list", contains="showmigrations")
        for abbreviation in ("--pl", "--pla", "--chec", "--ch"):
            with self.subTest(abbreviation=abbreviation):
                self.assertRefused("migrate_schemas", "--shared", abbreviation, contains="abbreviated")
                self.assertEqual(self.loads, 0)
        decision = self.assertAllowed("migrate_schemas", "--plan", "--help")  # help exits before any work
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--plan", "--help"])
        self.assertEqual(self.loads, 0)

    def test_every_refused_plan_or_check_has_no_notice_and_loads_the_target_at_most_once(self):
        argvs = (["--plan"], ["--check", "--shared", "--tenant"], ["--shared", "--plan", "--settings=x"],
                 ["--shared", "--check", "--database", "x"], ["--shared", "--plan", "--apply"],
                 ["--shared", "--prune", "--plan"], ["--shared", "--plan", "--bogus"])
        for tail in argvs:
            for target in (TARGET, dict(TARGET, NAME="other_db"), dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=""),
                           RuntimeError("boom")):
                with self.subTest(tail=tail, target=type(target).__name__):
                    decision = self.evaluate("migrate_schemas", *tail, target=target)
                    if not decision.allowed:
                        self.assertIsNone(decision.notice)
                        self.assertEqual(decision.exit_code, gate.EXIT_REFUSED)
                    self.assertLessEqual(self.loads, 1)


class WrapperTests(GateCase):
    """D1: tenant_command / all_tenants_command. See NestedWrapperTests for the position-independent cases."""

    def test_wrapper_routed_migrations_are_always_refused(self):
        cases = (["tenant_command", "migrate"], ["tenant_command", "migrate_schemas", "--schema", "acme"],
                 ["tenant_command", "migrate_schemas", "--schema=acme", *APPLY],
                 ["all_tenants_command", "migrate"], ["all_tenants_command", "migrate_schemas", "--shared"],
                 ["all_tenants_command", "--no-public", "migrate"],
                 ["all_tenants_command", "migrate", "--no-public"],
                 ["all_tenants_command", "--no-public", "migrate_schemas", *APPLY])
        for args in cases:
            with self.subTest(args=args):
                decision = self.assertRefused(*args, contains=("migrate_schemas with an explicit scope",
                                                               "tenant_command or all_tenants_command"))
                self.assertEqual(self.loads, 0)


class NestedWrapperTests(GateCase):
    """D1: a wrapper line is refused when ANY token after the command name is a migration command or a wrapper.

    SCOPE OF THESE TESTS: they verify the gate's TOKEN-SCANNING POLICY only (which command lines the gate
    refuses or forwards). They do not prove how Django or django-tenants actually dispatch wrapper lines;
    that analysis is source-inferred from the installed packages (versions not confirmed) and has not been
    runtime-verified.

    Where the wrapped command's name sits depends on --no-public (all_tenants_command takes it from argv[3]
    instead of argv[2] whenever that token is anywhere on the line), on --schema/-s (tenant_command removes it
    first) and on the nesting depth, so these tests vary all three instead of listing one command string.
    """

    WRAPPERS = gate.WRAPPER_COMMANDS
    MIGRATIONS = gate.GATED_COMMANDS
    EXTRAS = ([], ["-s", "acme"], ["--schema", "acme"], ["--schema=acme"], ["-sacme"], ["--no-public"],
              ["--shared"], ["--noinput", "--no-public"])

    def chains(self, last):
        """Every wrapper chain of depth 1 to 3 that ends in `last`."""
        for depth in (1, 2, 3):
            for wrappers in itertools.product(self.WRAPPERS, repeat=depth):
                yield [*wrappers, last]

    def variants(self, base):
        """`base` with each extra token group inserted at every position after the first wrapper."""
        for extra in self.EXTRAS:
            for at in range(1, len(base) + 1):
                yield base[:at] + extra + base[at:]

    def test_token_policy_refuses_every_generated_chain_that_names_a_migration_command(self):
        # Policy test: the gate refuses these lines. It says nothing about what Django would have dispatched.
        count = 0
        for name in self.MIGRATIONS:
            for base in self.chains(name):
                for tail in self.variants(base):
                    count += 1
                    with self.subTest(tail=tail):
                        decision = self.assertRefused(*tail, contains=("tenant_command or all_tenants_command",
                                                                        "must not be nested",
                                                                        "migrate_schemas with an explicit scope"))
                        self.assertEqual(self.loads, 0)
                        self.assertNotIn("acme", decision.message)
        # Expected size from the dimensions: per migration name, each depth d has len(WRAPPERS)**d chains of
        # d + 1 tokens, and every extra group is inserted at d + 1 positions (1 .. len(base)).
        per_name = sum(len(self.WRAPPERS) ** depth * len(self.EXTRAS) * (depth + 1) for depth in (1, 2, 3))
        self.assertEqual(count, len(self.MIGRATIONS) * per_name)

    def test_token_policy_refuses_the_doubled_wrapper_forms_from_the_review(self):
        # Policy test only: these forms are believed (from source reading, not runtime) to reach migrate_schemas.
        forms = (["all_tenants_command", "all_tenants_command", "migrate_schemas", "--shared"],
                 ["all_tenants_command", "--no-public", "all_tenants_command", "migrate_schemas", "--shared"],
                 ["tenant_command", "tenant_command", "migrate_schemas", "--shared", "-s", "acme"],
                 ["tenant_command", "tenant_command", "-s", "acme", "migrate_schemas"],
                 ["tenant_command", "all_tenants_command", "migrate"],
                 ["all_tenants_command", "tenant_command", "migrate"])
        for args in forms:
            for suffix in ([], APPLY):
                with self.subTest(args=args, suffix=suffix):
                    self.assertRefused(*args, *suffix, contains="must not be nested")
                    self.assertEqual(self.loads, 0)

    def test_nested_wrappers_are_refused_even_without_a_migration_command(self):
        for base in self.chains("showmigrations"):
            if len(base) == 2:  # a single wrapper around a non-migration command is allowed (see below)
                continue
            for tail in self.variants(base):
                with self.subTest(tail=tail):
                    self.assertRefused(*tail, contains="must not be nested")
                    self.assertEqual(self.loads, 0)

    def test_every_offending_token_is_reported_by_position_using_the_gates_own_constant(self):
        self.assertRefused("tenant_command", "tenant_command", "showmigrations",
                           contains="token #2 is the command name 'tenant_command'")
        self.assertRefused("all_tenants_command", "--no-public", "migrate",
                           contains="token #3 is the command name 'migrate'")
        decision = self.assertRefused("all_tenants_command", "all_tenants_command", "migrate_schemas", "--shared",
                                      contains=("token #2 is the command name 'all_tenants_command'",
                                                "token #3 is the command name 'migrate_schemas'"))
        self.assertNotIn("token #4", decision.message)

    def test_no_public_placement_does_not_matter(self):
        for args in (["all_tenants_command", "--no-public", "migrate_schemas"],
                     ["all_tenants_command", "migrate_schemas", "--no-public"],
                     ["all_tenants_command", "showmigrations", "migrate_schemas", "--no-public"],
                     ["all_tenants_command", "--no-public", "showmigrations", "migrate_schemas"],
                     ["all_tenants_command", "--no-public", "--no-public", "migrate"],
                     ["all_tenants_command", "showmigrations", "--no-public", "all_tenants_command", "migrate"]):
            with self.subTest(args=args):
                self.assertRefused(*args, contains="tenant_command or all_tenants_command")

    def test_schema_option_placement_does_not_matter(self):
        for args in (["tenant_command", "-s", "acme", "migrate_schemas"], ["tenant_command", "--schema=acme", "migrate"],
                     ["tenant_command", "migrate_schemas", "--schema", "acme"], ["tenant_command", "migrate", "-sacme"],
                     ["tenant_command", "-s", "acme", "-s", "beta", "migrate"],
                     ["tenant_command", "showmigrations", "--schema=acme", "migrate"]):
            with self.subTest(args=args):
                self.assertRefused(*args, contains="tenant_command or all_tenants_command")

    def test_tokens_after_a_double_dash_are_still_checked(self):
        self.assertRefused("tenant_command", "showmigrations", "--", "migrate_schemas", contains="token #4")
        self.assertRefused("all_tenants_command", "--", "all_tenants_command", contains="must not be nested")

    def test_malformed_or_incomplete_wrapper_lines_are_not_treated_as_migrations(self):
        for args in (["tenant_command"], ["all_tenants_command"], ["tenant_command", "-s"], ["tenant_command", "--schema="],
                     ["all_tenants_command", "--no-public"], ["all_tenants_command", "--no-public", "--no-public"],
                     ["tenant_command", ""], ["tenant_command", "--"], ["all_tenants_command", "-s", "acme"]):
            with self.subTest(args=args):
                decision = self.assertAllowed(*args)
                self.assertEqual(decision.argv, ["manage.py", *args])
                self.assertIsNone(decision.notice)
                self.assertEqual(self.loads, 0)

    def test_unrelated_wrapper_lines_and_lookalike_names_are_unaffected(self):
        for args in (["tenant_command", "showmigrations", "--schema=acme"], ["tenant_command", "shell", "-s", "acme"],
                     ["tenant_command", "loaddata", "data.json", "--schema=acme"], ["all_tenants_command", "showmigrations"],
                     ["all_tenants_command", "--no-public", "check"], ["tenant_command", "showmigrations", "migrations"],
                     ["tenant_command", "showmigrations", "migrate.py"],
                     ["tenant_command", "showmigrations", "migrate_schemas2"],
                     ["tenant_command", "showmigrations", "Migrate"],
                     # The inline form is ONE token ("--schema=migrate"), never a command name.
                     ["tenant_command", "showmigrations", "--schema=migrate"],
                     ["tenant_command", "showmigrations", "-smigrate_schemas"]):
            with self.subTest(args=args):
                decision = self.assertAllowed(*args)
                self.assertEqual(decision.argv, ["manage.py", *args])
                self.assertIsNone(decision.notice)
                self.assertEqual(self.loads, 0)

    def test_known_limitation_a_separate_token_named_like_a_command_is_refused(self):
        # A tenant schema (or any argument) that is a separate token equal to one of these names is refused.
        for args in (["tenant_command", "shell", "-s", "migrate"], ["tenant_command", "showmigrations", "--schema", "migrate_schemas"],
                     ["all_tenants_command", "showmigrations", "migrate"],
                     ["tenant_command", "shell", "-s", "tenant_command"]):
            with self.subTest(args=args):
                self.assertRefused(*args, contains="even as an argument value")

    def test_non_wrapper_commands_that_mention_these_names_are_not_wrapper_lines(self):
        # Documented limit: only lines that start with a wrapper command are checked by token.
        for args in (["help", "migrate_schemas"], ["help", "tenant_command"], ["shell", "migrate"],
                     ["showmigrations", "migrate"]):
            with self.subTest(args=args):
                self.assertEqual(self.assertAllowed(*args).argv, ["manage.py", *args])
                self.assertEqual(self.loads, 0)

    def test_wrapper_refusals_do_not_echo_other_arguments(self):
        for args in (["tenant_command", "tenant_command", "migrate_schemas", f"--password={FAKE_SECRET}"],
                     ["all_tenants_command", "--no-public", "migrate", FAKE_SECRET],
                     ["tenant_command", "migrate", "-s", FAKE_SECRET],
                     ["tenant_command", "tenant_command", FAKE_SECRET, "showmigrations"],
                     ["all_tenants_command", f"--{FAKE_SECRET}", "all_tenants_command"]):
            with self.subTest(args=args[:3]):
                decision = self.assertRefused(*args)
                self.assertNotIn(FAKE_SECRET, decision.message)
                self.assertNotIn("--password", decision.message)


class DashLeadingTests(GateCase):
    """Dash-leading first argument: only the exact forms manage.py --help / -h / --version are accepted."""

    def test_the_exact_top_level_forms_are_accepted_and_forwarded_unchanged(self):
        for token in ("--help", "-h", "--version"):
            with self.subTest(token=token):
                decision = self.assertAllowed(token)
                self.assertEqual(decision.argv, ["manage.py", token])
                self.assertIsNone(decision.notice)
                self.assertEqual(self.loads, 0)

    def test_the_no_command_behaviour_is_preserved(self):
        for argv in ([], ["manage.py"]):
            with self.subTest(argv=argv):
                decision = gate.evaluate(argv, lambda: self.fail("must not load"))
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.argv, argv)
                self.assertIsNone(decision.notice)
                self.assertEqual(decision.exit_code, 0)

    def test_any_other_first_argument_starting_with_a_dash_is_refused(self):
        cases = (["--help", "migrate_schemas"], ["-h", "check"], ["--version", "--help"], ["--help", "--help"],
                 ["--version", "extra"], ["--settings=config.other", "migrate_schemas", "--shared", *APPLY],
                 ["--settings", "config.other", "migrate_schemas"], ["--pythonpath=/tmp", "check"],
                 ["-x"], ["-"], ["--"], ["--HELP"], ["-H"], ["--hel"], ["--vers"], ["--versions"], ["-v", "2", "check"],
                 ["--noinput", "migrate_schemas"], ["--no-color", "runserver"], ["--help", "tenant_command", "migrate"],
                 ["--", "migrate_schemas", "--shared"])
        for args in cases:
            with self.subTest(args=args):
                self.assertRefused(*args, contains=("token #1 starts with '-'", "only 'manage.py --help'"))
                self.assertEqual(self.loads, 0)

    def test_help_or_version_after_a_command_name_do_not_skip_the_normal_checks(self):
        self.assertRefused("migrate_schemas", "--bogus", "--help", contains="not a recognized option")
        self.assertRefused("migrate_schemas", "--shared", "--he", contains="abbreviated")
        self.assertRefused("migrate_schemas", "--version=1", contains="does not take a value")
        # After a double dash, "--help" is a positional (an app label), not the help flag.
        self.assertRefused("migrate_schemas", "--shared", "--", "--help", contains="--apply is required")
        self.assertRefused("tenant_command", "migrate", "--help", contains="must not be nested")
        self.assertEqual(self.loads, 0)

    def test_refusals_do_not_echo_the_first_argument(self):
        for token in (f"--password={FAKE_SECRET}", f"--{FAKE_SECRET}", f"-{FAKE_SECRET}"):
            with self.subTest(token=token[:12]):
                decision = self.assertRefused(token, "migrate_schemas")
                self.assertNotIn(FAKE_SECRET, decision.message)
                self.assertNotIn("--password", decision.message)
                self.assertIn("token #1", decision.message)


class ParserSafetyTests(GateCase):
    def test_abbreviated_options_are_refused(self):
        for abbreviation in ("--sh", "--sche", "--tenan", "--pl", "--ch", "--fak", "--fake-i", "--pru", "--run",
                             "--ap", "--appl", "--conf", "--confirm", "--allow", "--noi", "--lis", "--he", "--vers"):
            with self.subTest(abbreviation=abbreviation):
                self.assertRefused("migrate_schemas", "--shared", abbreviation, *APPLY, contains="abbreviated")
                self.assertEqual(self.loads, 0)

    def test_unknown_options_are_refused(self):
        for option in ("--bogus", "--no-input", "--dry-run", "--yes", "--migrate"):
            with self.subTest(option=option):
                self.assertRefused("migrate_schemas", "--shared", option, *APPLY, contains=("not a recognized option", "token #3"))

    def test_unsupported_short_options_are_refused(self):
        for token in ("-x", "-lv2", "-s=acme", "-hv"):
            with self.subTest(token=token):
                self.assertRefused("migrate_schemas", "--shared", token, *APPLY, contains=("not a supported short option", "token #3"))

    def test_values_and_arity(self):
        self.assertRefused("migrate_schemas", "--shared=1", *APPLY, contains="does not take a value")
        self.assertRefused("migrate_schemas", "--apply=yes", "--shared", contains="does not take a value")
        self.assertRefused("migrate_schemas", "--schema", contains="requires a value")
        self.assertRefused("migrate_schemas", "--schema", "--apply", contains="requires a value")
        self.assertRefused("migrate_schemas", "--schema", "a", "--schema", "b", *APPLY, contains="more than once")

    def test_double_dash_makes_the_rest_positional(self):
        self.assertRefused("migrate_schemas", "--shared", *APPLY, "--", "certificates", "0001", contains="need --allow-destructive")
        decision = self.assertAllowed("migrate_schemas", "--shared", *APPLY, "--allow-destructive", "--", "certificates", "0001")
        self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared", "--", "certificates", "0001"])

    def test_protected_looking_tokens_after_a_double_dash_are_classified_as_positionals(self):
        """Verified by this test: the gate's own classification. After "--" the gate counts every token as a
        positional (app label or migration name), so --prune and friends are NOT treated as protected flags there.
        NOT verified here: how Django parses such a line. Source reading suggests Django would treat "--prune"
        as an unknown app label, but that is source-inferred and runtime-unverified."""
        head = ["migrate_schemas", "--shared", *APPLY]  # real options must come BEFORE the separator
        destructive = [*head, "--allow-destructive"]
        for flag in ("--prune", "--fake", "--fake-initial", "--run-syncdb"):
            with self.subTest(flag=flag):
                # One positional: classified as an app label, so no protected operation and no destructive flag.
                decision = self.assertAllowed(*head, "--", flag)
                self.assertEqual(decision.argv, ["manage.py", *head[:1], "--shared", "--", flag])
                self.assertIn("protected operation: no", decision.notice)
                self.assertRefused(*destructive, "--", flag, contains="no protected operation is present")
        # Two positionals are an app label plus an explicit migration name: protected, whatever they look like.
        for pair in (["certificates", "0001"], ["--prune", "--fake"], ["certificates", "--run-syncdb"]):
            with self.subTest(pair=pair):
                self.assertRefused(*head, "--", *pair, contains="need --allow-destructive")
                decision = self.assertAllowed(*destructive, "--", *pair)
                self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", "--shared", "--", *pair])
                self.assertIn("protected operation: yes", decision.notice)
        # More than two positionals are refused outright.
        self.assertRefused(*head, "--", "--prune", "--fake", "--run-syncdb", contains="too many positional")
        # A real protected flag BEFORE the separator is still classified as protected.
        self.assertRefused("migrate_schemas", "--shared", "--prune", *APPLY, "--", "certificates",
                           contains="need --allow-destructive")

    def test_gate_flags_after_double_dash_are_not_treated_as_gate_flags(self):
        # One token after "--" is a positional (an app label), not the gate flag: --apply is still missing.
        self.assertRefused("migrate_schemas", "--shared", "--", "--apply", contains="--apply is required")
        # Several tokens after "--" are refused earlier, as too many positionals; nothing is allowed either way.
        self.assertRefused("migrate_schemas", "--shared", "--", "--apply", "--confirm-database", DB,
                           contains="too many positional")

    def test_settings_and_pythonpath_are_refused_on_applies(self):
        for extra in (["--settings", "config.other"], ["--settings=config.other"], ["--pythonpath", "/tmp"],
                      ["--pythonpath=/tmp"]):
            with self.subTest(extra=extra):
                self.assertRefused("migrate_schemas", "--shared", *extra, *APPLY, contains="not allowed when applying")
                self.assertEqual(self.loads, 0)


class HelpAndVersionTests(GateCase):
    def test_help_and_version_pass_through_with_gate_flags_stripped(self):
        for args, expected in ((["--help"], ["--help"]), (["-h"], ["-h"]), (["--version"], ["--version"]),
                               (["--apply", "-h"], ["-h"]), (["--shared", "--allow-destructive", "--help"], ["--shared", "--help"]),
                               (["--list", "--help"], ["--list", "--help"]), (["-h", *APPLY], ["-h"])):
            with self.subTest(args=args):
                decision = self.assertAllowed("migrate_schemas", *args)
                self.assertEqual(decision.argv, ["manage.py", "migrate_schemas", *expected])
                self.assertEqual(self.loads, 0)

    def test_parse_problems_still_win_over_help(self):
        self.assertRefused("migrate_schemas", "--bogus", "-h", contains="not a recognized option")


class MessageTests(GateCase):
    def test_notice_shows_the_target_and_scope_but_no_credentials(self):
        decision = self.assertAllowed("migrate_schemas", "--shared", *APPLY)
        self.assertEqual(
            decision.notice,
            "Migration gate: checks passed for database 'edusekai_db' at 127.0.0.1:5432 "
            "(environment: development); scope: shared schema; protected operation: no. "
            "The command is now being handed to Django; this notice does not mean Django accepted the arguments "
            "or that any migration was applied.",
        )
        for secret in ("s3cretpw", "dbuser"):
            self.assertNotIn(secret, decision.notice)

    def test_environment_label_is_sanitised_and_defaults_to_unset(self):
        decision = self.assertAllowed("migrate_schemas", "--shared", *APPLY, target=dict(TARGET, EDUSEKAI_ENV="dev env;rm"))
        self.assertIn("environment: dev_env_rm)", decision.notice)
        decision = self.assertAllowed("migrate_schemas", "--shared", *APPLY, target=dict(TARGET, EDUSEKAI_ENV=None))
        self.assertIn("environment: unset)", decision.notice)

    def test_user_supplied_tokens_are_not_echoed(self):
        decision = self.assertRefused("migrate_schemas", "--shared", "--password=hunter2", *APPLY,
                                      contains="token #3")
        self.assertNotIn("hunter2", decision.message)
        self.assertNotIn("--password", decision.message)
        decision = self.assertRefused("migrate_schemas", "--shared", "--apply", "--confirm-database", "hunter2")
        self.assertNotIn("hunter2", decision.message)

    def test_no_decision_ever_contains_credentials(self):
        battery = [["migrate"], ["migrate_schemas", "--list"], ["migrate_schemas", "--shared", *APPLY],
                   ["migrate_schemas", "--shared", "--apply", "--confirm-database", "wrong"],
                   ["tenant_command", "migrate"], ["migrate_schemas", "--shared", "certificates", "0001", *APPLY],
                   ["migrate_schemas", "--shared", *APPLY, "--settings=x"]]
        for args in battery:
            for target in (TARGET, dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=""), dict(TARGET, NAME="other")):
                decision = self.evaluate(*args, target=target)
                text = " ".join(filter(None, (decision.message, decision.notice, *(decision.argv or []))))
                self.assertNotIn("s3cretpw", text)
                self.assertNotIn("dbuser", text)

    def test_refusals_carry_the_usage_hint_and_exit_code_2(self):
        decision = self.assertRefused("migrate")
        self.assertEqual(decision.exit_code, 2)
        self.assertIn("migrate_schemas --shared --apply --confirm-database <database name>", decision.message)


class PurityTests(unittest.TestCase):
    def test_gate_and_identity_modules_import_only_the_standard_library(self):
        allowed = {"migration_gate.py": {"re", "collections", "config"}, "db_identity.py": {"re", "collections"}}
        for filename, permitted in allowed.items():
            tree = ast.parse((BACKEND / "config" / filename).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
            with self.subTest(module=filename):
                self.assertLessEqual(imported, permitted, imported)

    def test_importing_the_gate_does_not_configure_django_or_load_a_database_driver(self):
        code = (
            "import sys\n"
            "import config.migration_gate\n"
            "from django.conf import settings\n"
            "assert not settings.configured, 'importing the gate loaded Django settings'\n"
            "assert 'psycopg2' not in sys.modules, 'importing the gate loaded the database driver'\n"
            "print('pure')\n"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pure", result.stdout)


class ProjectFileTests(unittest.TestCase):
    """Pin the Docker, manage.py and documentation requirements by reading the files as text."""

    def read(self, relative):
        return (BACKEND / relative).read_text(encoding="utf-8")

    def active_lines(self, relative):
        return [line for line in self.read(relative).splitlines() if line.strip() and not line.lstrip().startswith("#")]

    def test_entrypoint_has_no_automatic_makemigrations_or_seeding(self):
        active = "\n".join(self.active_lines("entrypoint.sh"))
        self.assertNotIn("makemigrations", active)
        self.assertNotIn("seed_public", active)
        self.assertNotIn("|| true", active)

    def test_entrypoint_migrates_only_when_explicitly_enabled(self):
        text = "\n".join(self.active_lines("entrypoint.sh"))  # comments excluded
        switch = '[ "$RUN_MIGRATIONS_ON_START" = "true" ]'
        shared = 'migrate_schemas --shared --apply --confirm-database "$DB_NAME"'
        tenant = 'migrate_schemas --tenant --apply --confirm-database "$DB_NAME"'
        for needle in (switch, shared, tenant, 'exec "$@"'):
            self.assertIn(needle, text)
        # The two scoped steps run in order, both inside the opt-in block.
        self.assertLess(text.index(switch), text.index(shared))
        self.assertLess(text.index(shared), text.index(tenant))
        self.assertLess(text.index(tenant), text.index("else"))
        # Nothing migrates before the opt-in check.
        self.assertNotIn("migrate_schemas", text[: text.index(switch)])
        # Each step fails fast and the server is not started afterwards.
        self.assertEqual(text.count('exit "$status"'), 2)
        self.assertLess(text.index('exit "$status"'), text.index('exec "$@"'))

    def test_compose_limits_restarts_and_defaults_migrations_off(self):
        text = self.read("docker-compose.yml")
        self.assertIn("restart: on-failure:3", text)
        self.assertIn("RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START:-false}", text)
        self.assertIn("restart: always", text)  # the database service keeps its policy

    def test_env_example_documents_the_opt_in_switch_as_off(self):
        self.assertIn("RUN_MIGRATIONS_ON_START=false", self.active_lines(".env.example"))

    def test_manage_py_runs_the_gate_before_django_and_reads_no_credentials(self):
        text = self.read("manage.py")
        self.assertIn("migration_gate", text)
        self.assertIn("evaluate(", text)
        self.assertIn("sys.exit(decision.exit_code)", text)
        self.assertLess(text.index("evaluate("), text.index("execute_from_command_line(decision.argv)"))
        for credential in ("PASSWORD", '"USER"', "'USER'"):
            self.assertNotIn(credential, text)

    def test_readme_documents_the_limits_and_procedures(self):
        text = self.read("README.md")
        for needle in ("Migration safety", "call_command", "django-admin", "python -m django", "ensure_schema",
                       "showmigrations", "seed_public.py", "EDUSEKAI_EXPECTED_DATABASE", "on-failure:3",
                       "RUN_MIGRATIONS_ON_START", "--allow-destructive", "DB_NAME", "not reversed", "exactly one scope",
                       "token #", "universal database-change guard", "create_tenant", "delete_tenant",
                       "docker compose run", "checks passed", "confirmation is supplied by the entrypoint",
                       "wrappers cannot be nested", "tenant_command shell -s migrate", "starts with `-`",
                       "not guaranteed to be read-only", "checked like an apply", "configuration values"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class NoEchoTests(GateCase):
    """F2: refusal messages and notices never echo what was typed."""

    @staticmethod
    def secret_argvs():
        s = FAKE_SECRET
        return [
            ["migrate_schemas", "--shared", f"--{s}", *APPLY],
            ["migrate_schemas", "--shared", f"--{s}=value", *APPLY],
            ["migrate_schemas", "--shared", f"--bogus={s}", *APPLY],
            ["migrate_schemas", "--shared", f"-p{s}", *APPLY],
            ["migrate_schemas", "--shared", f"-x={s}", *APPLY],
            ["migrate_schemas", "--shared", f"-l{s}", *APPLY],
            ["migrate_schemas", f"--schema={s}"],
            ["migrate_schemas", "--schema", s, "--apply", "--confirm-database", s],
            ["migrate_schemas", "--schema", s, *APPLY],
            ["migrate_schemas", "--shared", "--apply", f"--confirm-database={s}"],
            ["migrate_schemas", "--shared", "--apply", "--confirm-database", DB, s, s],
            ["migrate_schemas", "--shared", *APPLY, s, "--allow-destructive"],
            ["migrate_schemas", "--shared", *APPLY, "app", s, "--allow-destructive"],
            ["migrate_schemas", "--shared", f"--shared={s}", *APPLY],
            ["migrate_schemas", "--shared", f"--apply={s}"],
            ["migrate_schemas", "--shared", f"--database={s}", *APPLY],
            ["migrate_schemas", "--shared", f"--executor={s}", *APPLY],
            ["migrate_schemas", "--shared", f"--settings={s}", *APPLY],
            ["migrate_schemas", "--shared", f"--pythonpath={s}", *APPLY],
            ["migrate_schemas", "--shared", f"--list={s}"],
            ["migrate_schemas", "--shared", "--", s, *APPLY],
            ["migrate_schemas", s],
            ["migrate", s],
            ["tenant_command", "migrate", f"--schema={s}"],
            ["all_tenants_command", "--no-public", "migrate_schemas", s],
            # D1: nested wrappers
            ["tenant_command", "tenant_command", "migrate_schemas", s],
            ["all_tenants_command", "all_tenants_command", s, "showmigrations"],
            ["tenant_command", "showmigrations", "-s", s],
            ["tenant_command", "migrate", "-s", s],
            # D2: --plan / --check
            ["migrate_schemas", "--schema", s, "--plan"],
            ["migrate_schemas", "--shared", "--plan", f"--settings={s}"],
            ["migrate_schemas", "--shared", "--check", "--database", s],
            ["migrate_schemas", "--shared", "--plan", f"--bogus={s}"],
            ["migrate_schemas", "--plan", s],
            ["migrate_schemas", "--shared", "--plan", "--confirm-database", s],
            # Dash-leading first argument
            [f"--{s}"],
            [f"--settings={s}", "migrate_schemas", "--shared"],
            ["--help", s],
        ]

    def test_secret_like_tokens_never_appear_in_messages_or_notices(self):
        targets = (TARGET, dict(TARGET, NAME="other_db"), dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=""),
                   RuntimeError(FAKE_SECRET))
        for args in self.secret_argvs():
            for target in targets:
                with self.subTest(args=args[:3], target=type(target).__name__):
                    decision = self.evaluate(*args, target=target)
                    shown = " ".join(filter(None, (decision.message, decision.notice)))
                    self.assertNotIn(FAKE_SECRET, shown)
                    self.assertNotIn(FAKE_SECRET.lower(), shown.lower())

    def test_a_secret_schema_name_is_not_in_the_notice(self):
        decision = self.assertAllowed("migrate_schemas", "--schema", FAKE_SECRET, *APPLY)
        self.assertIn("scope: one tenant schema", decision.notice)
        self.assertNotIn(FAKE_SECRET, decision.notice)

    def test_unrecognized_tokens_are_reported_by_position_only(self):
        decision = self.assertRefused("migrate_schemas", "--shared", "--bogus", *APPLY, contains="token #3")
        self.assertNotIn("--bogus", decision.message)
        decision = self.assertRefused("migrate_schemas", "--shared", "--sh", *APPLY, contains=("token #3", "abbreviated"))
        self.assertNotIn("--sh ", decision.message)
        decision = self.assertRefused("migrate_schemas", "--shared", "-x", *APPLY, contains="token #3")
        self.assertNotIn("-x", decision.message.replace("--", ""))

    def test_only_constants_of_the_option_table_are_ever_named(self):
        decision = self.assertRefused("migrate_schemas", "--shared", "--apply", "--apply", "--confirm-database", DB,
                                      contains="option --apply was given more than once")
        self.assertNotIn(DB, decision.message)


class NoticeTests(GateCase):
    """F3: the notice appears only once every check has passed, and is not a claim about Django."""

    def test_refusals_have_no_notice_and_stop_before_the_target_is_used_where_possible(self):
        for args in (["migrate"], ["migrate_schemas", "--shared"], ["migrate_schemas", "--list"],
                     ["migrate_schemas", "--shared", "--tenant", *APPLY], ["tenant_command", "migrate"]):
            with self.subTest(args=args):
                decision = self.assertRefused(*args)
                self.assertIsNone(decision.notice)
                self.assertEqual(self.loads, 0)
        for target in (dict(TARGET, NAME="other_db"), dict(TARGET, EDUSEKAI_EXPECTED_DATABASE="")):
            decision = self.assertRefused("migrate_schemas", "--shared", *APPLY, target=target)
            self.assertIsNone(decision.notice)

    def test_the_notice_says_checks_passed_and_is_not_proof_of_anything_else(self):
        decision = self.assertAllowed("migrate_schemas", "--shared", *APPLY)
        self.assertTrue(decision.notice.startswith("Migration gate: checks passed"))
        self.assertIn("does not mean Django accepted the arguments or that any migration was applied", decision.notice)
        self.assertNotIn("applying migrations to", decision.notice)

    def test_help_has_no_notice_and_plan_or_check_have_one_only_after_the_checks_passed(self):
        self.assertIsNone(self.assertAllowed("migrate_schemas", "-h").notice)
        self.assertIsNone(self.assertAllowed("migrate_schemas", "--help").notice)
        self.assertIsNone(self.assertAllowed("--help").notice)
        for flag in ("--plan", "--check"):
            with self.subTest(flag=flag):
                self.assertTrue(self.assertAllowed("migrate_schemas", "--shared", flag).notice.startswith(
                    "Migration gate: checks passed"))
                self.assertRefused("migrate_schemas", "--shared", flag, target=dict(TARGET, NAME="other_db"))
                self.assertRefused("migrate_schemas", flag)


def load_manage_module():
    """Load backend/manage.py by path (its top level imports only importlib, os and sys)."""
    spec = importlib.util.spec_from_file_location("edusekai_manage_under_test", MANAGE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManageFlowTests(unittest.TestCase):
    """F7: manage.py control flow with Django replaced by a stub. No Django, no settings, no database."""

    def setUp(self):
        self.manage = load_manage_module()
        self.calls = []

        def fake_execute(argv):
            self.calls.append({"argv": list(argv), "settings": os.environ.get("DJANGO_SETTINGS_MODULE")})

        management = types.ModuleType("django.core.management")
        management.execute_from_command_line = fake_execute
        stubs = {"django": types.ModuleType("django"), "django.core": types.ModuleType("django.core"),
                 "django.core.management": management}
        stubs["django"].__path__ = []
        stubs["django.core"].__path__ = []
        self.stubs = stubs
        saved = {name: sys.modules.get(name, _MISSING) for name in stubs}
        sys.modules.update(stubs)

        def restore():
            for name, original in saved.items():
                if original is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original

        self.addCleanup(restore)
        env_patch = mock.patch.dict(os.environ)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("DJANGO_SETTINGS_MODULE", None)

    def forbidden_target(self):
        raise AssertionError("the database target must not be loaded for this command")

    def run_main(self, *args, loader=None):
        argv = ["manage.py", *args]
        stdout, stderr = io.StringIO(), io.StringIO()
        loader = loader or (lambda: dict(TARGET))
        code = None
        with mock.patch.object(sys, "argv", list(argv)), mock.patch.object(self.manage, "_load_target", loader), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                self.manage.main()
            except SystemExit as exc:
                code = exc.code
            self.assertEqual(sys.argv, argv, "main() must not modify sys.argv")
        return code, stdout.getvalue(), stderr.getvalue()

    def test_a_refusal_exits_with_code_2_and_never_reaches_django(self):
        for args in (["migrate"], ["migrate_schemas", "--shared"], ["migrate_schemas", "--list"],
                     ["tenant_command", "migrate"], ["migrate_schemas", "--shared", "--tenant", *APPLY]):
            with self.subTest(args=args):
                self.calls.clear()
                code, out, err = self.run_main(*args)
                self.assertEqual(code, 2)
                self.assertEqual(self.calls, [])
                self.assertEqual(out, "")
                self.assertIn("Migration refused by the migration gate", err)
                self.assertNotIn("checks passed", err)

    def test_a_valid_apply_prints_the_notice_then_hands_stripped_arguments_to_django(self):
        code, out, err = self.run_main("migrate_schemas", "--shared", *APPLY)
        self.assertIsNone(code)
        self.assertEqual([call["argv"] for call in self.calls], [["manage.py", "migrate_schemas", "--shared"]])
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("Migration gate: checks passed"))
        self.assertTrue(err.endswith("\n"))
        self.assertNotIn("Migration refused", err)

    def test_other_commands_pass_through_untouched_and_silently(self):
        for args in (["runserver", "0.0.0.0:8000"], ["test", "students"], ["showmigrations"], ["makemigrations"],
                     ["--version"], ["create_tenant"]):
            with self.subTest(args=args):
                self.calls.clear()
                code, out, err = self.run_main(*args, loader=self.forbidden_target)
                self.assertIsNone(code)
                self.assertEqual([call["argv"] for call in self.calls], [["manage.py", *args]])
                self.assertEqual((out, err), ("", ""))

    def test_help_is_forwarded_without_loading_the_target(self):
        for args in (["migrate_schemas", "-h"], ["migrate_schemas", "--help"], ["--help"], ["-h"], ["--version"]):
            with self.subTest(args=args):
                self.calls.clear()
                code, out, err = self.run_main(*args, loader=self.forbidden_target)
                self.assertIsNone(code)
                self.assertEqual([call["argv"] for call in self.calls], [["manage.py", *args]])
                self.assertEqual((out, err), ("", ""))

    def test_plan_and_check_load_the_target_once_print_the_notice_and_forward_the_arguments(self):
        for flag in ("--plan", "--check"):
            with self.subTest(flag=flag):
                self.calls.clear()
                seen = []

                def counting_loader():
                    seen.append(1)
                    return dict(TARGET)

                code, out, err = self.run_main("migrate_schemas", "--shared", flag, loader=counting_loader)
                self.assertIsNone(code)
                self.assertEqual(len(seen), 1)
                self.assertEqual([call["argv"] for call in self.calls], [["manage.py", "migrate_schemas", "--shared", flag]])
                self.assertEqual(out, "")
                self.assertTrue(err.startswith("Migration gate: checks passed"))
                self.assertIn("not guaranteed to be read-only", err)

    def test_plan_and_check_that_fail_the_gate_exit_with_code_2_and_never_reach_django(self):
        bad_target = (lambda: dict(TARGET, NAME="other_db"), lambda: dict(TARGET, EDUSEKAI_EXPECTED_DATABASE=""))
        for flag in ("--plan", "--check"):
            with self.subTest(flag=flag, case="no scope"):
                code, out, err = self.run_main("migrate_schemas", flag, loader=self.forbidden_target)
                self.assertEqual(code, 2)
                self.assertEqual(self.calls, [])
                self.assertIn("no migration scope", err)
            with self.subTest(flag=flag, case="override"):
                code, _out, err = self.run_main("migrate_schemas", "--shared", flag, "--settings=x",
                                                loader=self.forbidden_target)
                self.assertEqual(code, 2)
                self.assertEqual(self.calls, [])
                self.assertIn("is not allowed when applying", err)  # refused on the arguments, before any loading
            for loader in bad_target:
                with self.subTest(flag=flag, case="identity"):
                    code, _out, err = self.run_main("migrate_schemas", "--shared", flag, loader=loader)
                    self.assertEqual(code, 2)
                    self.assertEqual(self.calls, [])
                    self.assertNotIn("checks passed", err)

    def test_nested_wrappers_and_dash_leading_arguments_exit_with_code_2_and_never_reach_django(self):
        for args, needle in ((["all_tenants_command", "all_tenants_command", "migrate_schemas", "--shared"],
                              "must not be nested"),
                             (["tenant_command", "tenant_command", "showmigrations"], "must not be nested"),
                             (["--settings=config.other", "migrate_schemas", "--shared", *APPLY],
                              "token #1 starts with '-'"),
                             (["--help", "migrate_schemas"], "token #1 starts with '-'"),
                             (["-x"], "token #1 starts with '-'")):
            with self.subTest(args=args):
                code, out, err = self.run_main(*args, loader=self.forbidden_target)
                self.assertEqual(code, 2)
                self.assertEqual(self.calls, [])
                self.assertEqual(out, "")
                self.assertIn("Migration refused by the migration gate", err)
                self.assertIn(needle, err)
                self.assertNotIn("checks passed", err)

    def test_settings_module_default_is_set_before_django_runs_and_an_existing_one_is_kept(self):
        self.run_main("showmigrations", loader=self.forbidden_target)
        self.assertEqual(self.calls[-1]["settings"], "config.settings")
        os.environ["DJANGO_SETTINGS_MODULE"] = "some.other.settings"
        self.run_main("showmigrations", loader=self.forbidden_target)
        self.assertEqual(self.calls[-1]["settings"], "some.other.settings")

    def test_a_target_that_cannot_be_loaded_refuses_with_code_2(self):
        def broken():
            raise RuntimeError(FAKE_SECRET)

        code, out, err = self.run_main("migrate_schemas", "--shared", *APPLY, loader=broken)
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])
        self.assertIn("could not be determined (RuntimeError)", err)
        self.assertNotIn(FAKE_SECRET, out + err)

    def test_a_wrong_identity_refuses_with_code_2(self):
        code, out, err = self.run_main("migrate_schemas", "--shared", *APPLY,
                                       loader=lambda: dict(TARGET, NAME="other_db"))
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])
        self.assertIn("does not match EDUSEKAI_EXPECTED_DATABASE", err)

    def test_missing_django_raises_the_helpful_import_error_before_the_gate_runs(self):
        sys.modules["django.core.management"] = None  # makes "from django.core.management import ..." fail
        with self.assertRaises(ImportError) as raised:
            self.run_main("migrate", loader=self.forbidden_target)
        self.assertIn("Couldn't import Django", str(raised.exception))
        self.assertEqual(self.calls, [])

    def test_nothing_secret_reaches_stdout_or_stderr(self):
        for args in NoEchoTests.secret_argvs():
            with self.subTest(args=args[:3]):
                self.calls.clear()
                _code, out, err = self.run_main(*args)
                self.assertNotIn(FAKE_SECRET, out + err)
                self.assertNotIn("s3cretpw", out + err)
                self.assertNotIn("dbuser", out + err)

    def test_the_gate_is_consulted_exactly_once_per_run(self):
        seen = []

        def counting_loader():
            seen.append(1)
            return dict(TARGET)

        self.run_main("migrate_schemas", "--shared", *APPLY, loader=counting_loader)
        self.assertEqual(len(seen), 1)


class LoadTargetTests(unittest.TestCase):
    """F7: manage.py _load_target() against a fake settings module. No real settings, no database."""

    MODULE_NAME = "edusekai_fake_settings_for_tests"

    def setUp(self):
        self.manage = load_manage_module()
        self.fake = types.ModuleType(self.MODULE_NAME)
        self.fake.DATABASES = {"default": {"NAME": "edusekai_db", "HOST": "127.0.0.1", "PORT": "5432",
                                           "USER": "dbuser", "PASSWORD": "s3cretpw",
                                           "OPTIONS": {"application_name": "edusekai:development"}}}
        self.fake.EDUSEKAI_ENV = "development"
        self.fake.EDUSEKAI_EXPECTED_DATABASE = "edusekai_db@127.0.0.1:5432"
        sys.modules[self.MODULE_NAME] = self.fake
        self.addCleanup(sys.modules.pop, self.MODULE_NAME, None)
        env_patch = mock.patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": self.MODULE_NAME})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_returns_only_the_values_the_gate_needs(self):
        target = self.manage._load_target()
        self.assertEqual(target, {"NAME": "edusekai_db", "HOST": "127.0.0.1", "PORT": "5432",
                                  "EDUSEKAI_ENV": "development",
                                  "EDUSEKAI_EXPECTED_DATABASE": "edusekai_db@127.0.0.1:5432"})
        for secret in ("s3cretpw", "dbuser"):
            self.assertNotIn(secret, repr(target))

    def test_the_settings_module_named_by_the_environment_is_the_one_used(self):
        self.fake.DATABASES["default"]["NAME"] = "another_db"
        self.assertEqual(self.manage._load_target()["NAME"], "another_db")

    def test_optional_identity_settings_default_to_empty(self):
        del self.fake.EDUSEKAI_ENV
        del self.fake.EDUSEKAI_EXPECTED_DATABASE
        target = self.manage._load_target()
        self.assertEqual((target["EDUSEKAI_ENV"], target["EDUSEKAI_EXPECTED_DATABASE"]), ("", ""))

    def test_missing_pieces_raise_and_the_gate_turns_them_into_a_refusal(self):
        broken = (lambda: setattr(self.fake, "DATABASES", {}), lambda: delattr(self.fake, "DATABASES"),
                  lambda: os.environ.pop("DJANGO_SETTINGS_MODULE"),
                  lambda: os.environ.__setitem__("DJANGO_SETTINGS_MODULE", "edusekai_no_such_settings_module"))
        for break_it in broken:
            with self.subTest(break_it=break_it):
                with mock.patch.dict(os.environ):
                    break_it()
                    with self.assertRaises(Exception):
                        self.manage._load_target()
                    decision = gate.evaluate(["manage.py", "migrate_schemas", "--shared", *APPLY], self.manage._load_target)
                    self.assertFalse(decision.allowed)
                    self.assertEqual(decision.exit_code, 2)
                    self.assertIn("could not be determined", decision.message)

    def test_loading_the_target_and_deciding_end_to_end_with_the_real_gate(self):
        args = ["manage.py", "migrate_schemas", "--shared", *APPLY]
        self.assertTrue(gate.evaluate(args, self.manage._load_target).allowed)
        self.fake.EDUSEKAI_EXPECTED_DATABASE = ""
        decision = gate.evaluate(args, self.manage._load_target)
        self.assertFalse(decision.allowed)
        self.assertIn("EDUSEKAI_EXPECTED_DATABASE is not set", decision.message)


_MISSING = object()


if __name__ == "__main__":
    unittest.main()
