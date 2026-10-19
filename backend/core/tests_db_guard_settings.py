"""Static tests of the database identity guard's settings policy (Stage 3D).

``config/settings.py`` cannot be imported by a pure test (it needs SECRET_KEY and the other
required settings, and reads .env). These tests therefore inspect its SYNTAX TREE only: they
import nothing from the project except what they read as text, never touch Django or a
database, and never read .env. Run from the backend folder with bytecode writing disabled:

    python -B -m unittest core.tests_db_guard_settings

What they prove is the source structure: how the test-only setting is defined, that it
cannot come from the environment, and that the adapter reads it only as ``is True``. They do
NOT prove how Django behaves at runtime (see the Stage 3D report).
"""

import ast
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FLAG = "EDUSEKAI_ALLOW_DERIVED_TEST_DB"
EXPECTED_SETTING = "EDUSEKAI_EXPECTED_DATABASE"
ARGV_TEST_EXPRESSION = "len(sys.argv) > 1 and sys.argv[1] == 'test'"


def parse(relative):
    return ast.parse((BACKEND / relative).read_text(encoding="utf-8"))


def module_assignments(tree, name):
    """Module-level plain assignments to ``name`` (not nested in if/for/def)."""
    return [node for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)]


def store_count(tree, name):
    """Every place ``name`` is bound anywhere in the tree (assignments, augmented, annotated, loops)."""
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == name
               and isinstance(node.ctx, ast.Store))


class TestOnlySettingDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = parse("config/settings.py")

    def test_running_tests_is_the_argv_expression(self):
        assignments = module_assignments(self.tree, "_RUNNING_TESTS")
        self.assertEqual(len(assignments), 1)
        expected = ast.dump(ast.parse(ARGV_TEST_EXPRESSION, mode="eval").body)
        self.assertEqual(ast.dump(assignments[0].value), expected)

    def test_the_flag_is_defined_exactly_once_at_module_level_as_running_tests(self):
        assignments = module_assignments(self.tree, FLAG)
        self.assertEqual(len(assignments), 1)
        value = assignments[0].value
        self.assertIsInstance(value, ast.Name)
        self.assertEqual(value.id, "_RUNNING_TESTS")
        self.assertEqual(store_count(self.tree, FLAG), 1)  # no other binding, e.g. inside an if branch

    def test_the_flag_is_defined_after_running_tests(self):
        running = module_assignments(self.tree, "_RUNNING_TESTS")[0]
        flag = module_assignments(self.tree, FLAG)[0]
        self.assertGreater(flag.lineno, running.lineno)

    def test_the_flag_cannot_come_from_the_environment_or_a_literal_override(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotEqual(node.value, FLAG, "the flag name appears as a string (for example in config(...))")
            if isinstance(node, ast.Call):
                for argument in node.args:
                    self.assertFalse(isinstance(argument, ast.Name) and argument.id == FLAG)
        # No wildcard or dynamic way of rebinding it either.
        self.assertFalse([n for n in ast.walk(self.tree) if isinstance(n, (ast.AugAssign, ast.AnnAssign))
                          and isinstance(n.target, ast.Name) and n.target.id == FLAG])

    def test_the_expected_identity_setting_keeps_its_empty_default_and_is_never_derived(self):
        assignments = module_assignments(self.tree, EXPECTED_SETTING)
        self.assertEqual(len(assignments), 1)
        call = assignments[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(call.func.id, "config")
        self.assertEqual(call.args[0].value, EXPECTED_SETTING)
        defaults = {k.arg: k.value for k in call.keywords}
        self.assertEqual(set(defaults), {"default"})
        self.assertEqual(defaults["default"].value, "")
        # Not rebound anywhere else (for example in the test-run branch): no invented identity.
        self.assertEqual(store_count(self.tree, EXPECTED_SETTING), 1)

    def test_no_warning_mode_or_absent_identity_policy_setting_exists(self):
        names = {node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)}
        for name in names:
            upper = name.upper()
            self.assertFalse(upper.startswith("EDUSEKAI_") and ("ABSENT" in upper or "WARN" in upper), name)


class AdapterReadsTheSettingStrictlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = parse("config/db_guard.py")

    def test_the_adapter_compares_the_setting_with_is_not_true(self):
        found = []
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.IsNot)
                    and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is True
                    and isinstance(node.left, ast.Call) and getattr(node.left.func, "id", "") == "getattr"
                    and len(node.left.args) == 3
                    and isinstance(node.left.args[1], ast.Constant) and node.left.args[1].value == FLAG
                    and isinstance(node.left.args[2], ast.Constant) and node.left.args[2].value is False):
                found.append(node)
        self.assertEqual(len(found), 1)

    def test_the_flag_name_appears_in_the_adapter_only_as_that_one_read_and_in_documentation(self):
        literal_uses = [n for n in ast.walk(self.tree) if isinstance(n, ast.Constant) and n.value == FLAG]
        self.assertEqual(len(literal_uses), 1)

    def test_the_test_environment_check_is_wrapped_so_that_failure_means_off(self):
        functions = {n.name: n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}
        allowed = functions["_derived_test_database_allowed"]
        tries = [n for n in ast.walk(allowed) if isinstance(n, ast.Try)]
        self.assertEqual(len(tries), 1)
        handler = tries[0].handlers[0]
        self.assertEqual(handler.type.id, "Exception")
        returns = [n for n in ast.walk(handler) if isinstance(n, ast.Return)]
        self.assertTrue(returns and all(isinstance(r.value, ast.Constant) and r.value.value is False for r in returns))

    def test_the_marker_is_djangos_test_state_imported_lazily(self):
        functions = {n.name: n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}
        imports = [n for n in ast.walk(functions["_test_environment_active"]) if isinstance(n, ast.ImportFrom)]
        self.assertEqual([(i.module, [a.name for a in i.names]) for i in imports],
                         [("django.test.utils", ["_TestState"])])
        for node in self.tree.body:  # nothing from django.test at module level
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.assertNotIn("django", getattr(node, "module", None) or "")


if __name__ == "__main__":
    unittest.main()
