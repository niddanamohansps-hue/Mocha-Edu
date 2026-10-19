"""Migration gate (migration safety, Stage 3).

Decides whether a ``manage.py`` command line may run. Pure standard library plus
``config.db_identity`` (itself pure): no Django import, no settings import and no
database access happen here. ``manage.py`` calls :func:`evaluate` before handing
the arguments to Django and supplies a ``load_target`` callable that returns the
configured database (only for an apply or a --plan / --check whose arguments have already passed the other checks).

What it protects, and what it does NOT
- It protects the ``manage.py`` command line only, and only the migrate commands.
  It does not see ``call_command`` (used by the test runner and by tenant
  provisioning), ``django-admin``, ``python -m django``, ``manage.py shell``
  sessions or any other script, and it does not guard other schema-changing
  commands (for example ``create_tenant`` or ``delete_tenant``). It is not a
  universal database-change guard.
- There is no bypass flag. The gate never runs a migration itself; it only
  allows, refuses, or rewrites the argument list.

Rules for ``migrate`` and ``migrate_schemas`` (they are the same command in this
project: ``django_tenants`` replaces ``migrate``)
- Applying needs EXACTLY ONE explicit scope (``--shared``, ``--tenant`` or
  ``--schema/-s NAME``): combinations and repeated scope options are refused. It
  also needs ``--apply``, ``--confirm-database NAME`` equal to the configured
  database name, and an ``EDUSEKAI_EXPECTED_DATABASE`` that matches the
  configured name, host and port EXACTLY (no ``test_`` exception).
- ``--allow-destructive`` is required for an explicit migration name (including
  ``zero``), ``--fake``, ``--fake-initial``, ``--prune`` and ``--run-syncdb``, and
  it is refused when none of those is present. An app label alone is allowed
  without it: it targets only that app's latest migrations (forward only).
- ``--plan`` / ``--check`` are NOT read-only: django-tenants calls ``ensure_schema()``
  per schema before the command looks at those options, which can create the
  ``django_migrations`` table in a schema that lacks one. They therefore get the same
  target checks as an apply (exactly one scope, no ``--settings`` / ``--pythonpath`` /
  non-default ``--database``, a matching ``EDUSEKAI_EXPECTED_DATABASE``) and only skip
  ``--apply`` / ``--confirm-database`` (which are refused if given). A protected
  operation keeps the command on the apply path (``--prune`` runs before ``--plan`` in
  Django, so ``--prune --plan`` is an apply).
- ``--list`` / ``-l`` is refused: django-tenants accepts it but nothing reads it,
  so the command would carry on and apply migrations. Use ``showmigrations``.
- ``tenant_command`` / ``all_tenants_command``: a line that has, at any position, a
  token equal to ``migrate``, ``migrate_schemas`` or either wrapper name is refused.
  The wrappers look the wrapped command up by exact name and hand the rest of the line
  on, so a nested wrapper would reach ``migrate_schemas`` without passing through this
  gate. The check is by token, not by position (it does not depend on ``--no-public``,
  ``--schema/-s`` or the nesting depth). Known limitation: a separate token equal to
  one of those names is refused even when it is an argument value, for example
  ``tenant_command shell -s migrate`` (a tenant schema named ``migrate``).
- ``--settings`` / ``--pythonpath`` and ``--database`` other than ``default`` are
  refused on an apply and on ``--plan`` / ``--check``, so the identity check cannot be
  pointed elsewhere.
- Unknown options and abbreviated options are refused (Django's command parsers
  accept abbreviations, so an abbreviation could otherwise hide a protected flag).
- ``--help``, ``-h`` and ``--version`` after a command name pass through (they exit
  without migrating). As the FIRST argument only the exact one-argument forms
  ``manage.py --help``, ``manage.py -h`` and ``manage.py --version`` are accepted: any
  other first argument that starts with ``-`` is refused instead of being left to
  Django's command dispatch.

The identity check compares configuration values (the settings module), not the
connection that is actually opened: libpq environment variables, service files, an
``OPTIONS`` entry, a proxy or DNS can still lead elsewhere. Environment and ``OPTIONS``
hardening is deferred.

The gate-only flags ``--apply``, ``--allow-destructive`` and ``--confirm-database``
are removed from the argument list before Django parses it.

Messages never echo what was typed. An option is named only when it exactly matches
the gate's own fixed option table (so the text printed is the gate's constant, not
the input); any other token is reported by its position on the command line
("token #N"). Option values, schema names, confirmation values and positional
arguments are never printed. What is printed: fixed texts, the configured database
name, host and port, a sanitized environment label, and token positions.
"""

import re
from collections import Counter, namedtuple

from config import db_identity

EXIT_REFUSED = 2

GATED_COMMANDS = ("migrate", "migrate_schemas")
WRAPPER_COMMANDS = ("tenant_command", "all_tenants_command")
SCOPE_OPTIONS = ("--shared", "--tenant", "--schema")
# Names that must not appear anywhere on a wrapper command line (see _check_wrapper).
_WRAPPED_FORBIDDEN = GATED_COMMANDS + WRAPPER_COMMANDS
# The only accepted command lines whose first argument starts with "-".
_TOP_LEVEL_FORMS = (["--help"], ["-h"], ["--version"])

Decision = namedtuple("Decision", "allowed argv message notice exit_code")

# Options of migrate / migrate_schemas as declared by Django 5.2.9 (base command
# + migrate) and django-tenants 3.9.0 (SyncCommon + MigrateSchemasCommand). The
# table is deliberately fixed: anything not listed is refused rather than guessed.
_BOOLEAN_LONG = frozenset({
    "--tenant", "--shared", "--fake", "--fake-initial", "--list", "--plan", "--prune", "--run-syncdb",
    "--check", "--noinput", "--no-initial-data", "--traceback", "--no-color", "--force-color",
    "--skip-checks", "--help", "--version",
})
_VALUE_LONG = frozenset({"--schema", "--database", "--executor", "--verbosity", "--settings", "--pythonpath"})
GATE_BOOLEAN = frozenset({"--apply", "--allow-destructive"})
GATE_VALUE = frozenset({"--confirm-database"})
_KNOWN_LONG = _BOOLEAN_LONG | _VALUE_LONG | GATE_BOOLEAN | GATE_VALUE
_SHORT_BOOLEAN = {"-h": "--help", "-l": "--list"}
_SHORT_VALUE = {"-s": "--schema", "-v": "--verbosity"}

_SAFE_LABEL = re.compile(r"[^A-Za-z0-9_.-]")

USAGE = (
    "How to run migrations deliberately (details: backend/README.md, 'Migration safety'):\n"
    "  python manage.py migrate_schemas --shared --plan\n"
    "  python manage.py migrate_schemas --shared --apply --confirm-database <database name>\n"
    "  python manage.py migrate_schemas --tenant --apply --confirm-database <database name>\n"
    "  python manage.py migrate_schemas --schema <tenant> --apply --confirm-database <database name>\n"
    "  To inspect migrations use: python manage.py showmigrations"
)


def _passthrough(argv, notice=None):
    return Decision(True, list(argv), None, notice, 0)


def _refuse(problems):
    lines = ["Migration refused by the migration gate:"]
    lines += [f"  - {problem}" for problem in problems]
    lines += ["", USAGE]
    return Decision(False, None, "\n".join(lines), None, EXIT_REFUSED)


class _Parsed:
    def __init__(self):
        self.options = {}        # canonical long name -> True or the option's value
        self.counts = Counter()  # canonical long name -> number of times given
        self.positionals = []
        self.strip = set()       # indexes of gate-only tokens to remove before Django sees them


def _parse(argv, start):
    """Tokenize argv[start:] against the fixed option table.

    Returns (parsed, problems). Problems are conservative refusals: unknown
    options, abbreviations, missing values and duplicated options. Problem texts
    name only options that exactly match the fixed table; every other token is
    reported by position (its index in argv; "manage.py" is token #0).
    """
    parsed, problems = _Parsed(), []
    i = start
    while i < len(argv):
        token = argv[i]
        if token == "--":
            parsed.positionals.extend(argv[i + 1:])
            break

        if token.startswith("--"):
            name, eq, inline = token.partition("=")
            if name in _BOOLEAN_LONG or name in GATE_BOOLEAN:
                if eq:
                    problems.append(f"option {name} does not take a value (token #{i}).")
                else:
                    if name in GATE_BOOLEAN:
                        if name in parsed.options:
                            problems.append(f"option {name} was given more than once.")
                        parsed.strip.add(i)
                    parsed.options[name] = True
                    parsed.counts[name] += 1
                i += 1
                continue
            if name in _VALUE_LONG or name in GATE_VALUE:
                value, consumed = _take_value(argv, i, name, inline if eq else None, problems)
                if value is not None:
                    if name in parsed.options:
                        problems.append(f"option {name} was given more than once.")
                    parsed.options[name] = value
                    parsed.counts[name] += 1
                    if name in GATE_VALUE:
                        parsed.strip.update(consumed)
                i += len(consumed) or 1
                continue
            if any(known.startswith(name) for known in _KNOWN_LONG):
                problems.append(
                    f"token #{i} looks like an abbreviated option. Spell options out in full here "
                    "(Django accepts abbreviations, which could hide a protected option)."
                )
            else:
                problems.append(f"token #{i} is not a recognized option for migrate_schemas.")
            i += 1
            continue

        if token.startswith("-") and len(token) > 1:
            flag = token[:2]
            if token in _SHORT_BOOLEAN:
                canonical = _SHORT_BOOLEAN[token]
                parsed.options[canonical] = True
                parsed.counts[canonical] += 1
                i += 1
                continue
            if flag in _SHORT_VALUE and "=" not in token:
                canonical = _SHORT_VALUE[flag]
                if len(token) > 2:  # -sNAME / -vN
                    value, consumed = token[2:], (i,)
                else:
                    value, consumed = _take_value(argv, i, flag, None, problems)
                if value is not None:
                    if canonical in parsed.options:
                        problems.append(f"option {canonical} was given more than once.")
                    parsed.options[canonical] = value
                    parsed.counts[canonical] += 1
                i += len(consumed) or 1
                continue
            problems.append(
                f"token #{i} is not a supported short option. Use the long form (for example --schema=NAME)."
            )
            i += 1
            continue

        parsed.positionals.append(token)
        i += 1
    return parsed, problems


def _take_value(argv, i, name, inline, problems):
    """Value of an option that needs one. Returns (value or None, consumed token indexes).

    ``name`` is always a constant of the fixed option table (a long option or "-s"/"-v").
    """
    if inline is not None:
        return inline, (i,)
    if i + 1 >= len(argv):
        problems.append(f"option {name} requires a value.")
        return None, (i,)
    following = argv[i + 1]
    if following.startswith("-") and len(following) > 1:
        problems.append(f"option {name} requires a value.")
        return None, (i,)
    return following, (i, i + 1)


def _forward(argv, parsed):
    return [token for idx, token in enumerate(argv) if idx not in parsed.strip]


def _check_wrapper(argv):
    """Refuse a wrapper command line that names a migration command or another wrapper.

    tenant_command and all_tenants_command look the wrapped command up by exact name and
    pass the rest of the line on to it (all_tenants_command takes the name from argv[3]
    instead of argv[2] whenever the token "--no-public" is anywhere on the line, and
    tenant_command removes --schema/-s first), so a wrapper that wraps a wrapper reaches
    migrate_schemas without passing through this gate. Which position holds the wrapped
    name therefore depends on the options and on the depth, so the check is by token and
    not by position: every token after the command name is compared, exactly, with the
    names in _WRAPPED_FORBIDDEN. Only the gate's own constant is ever printed.
    """
    hits = [
        (index, _WRAPPED_FORBIDDEN[_WRAPPED_FORBIDDEN.index(token)])
        for index, token in enumerate(argv)
        if index >= 2 and token in _WRAPPED_FORBIDDEN
    ]
    if not hits:
        return _passthrough(argv)
    problems = [
        "migrations cannot be run through tenant_command or all_tenants_command, and these wrappers must not be "
        "nested: tenant_command removes --schema before the migration command sees it, all_tenants_command "
        "repeats the run for every tenant, and a wrapper inside a wrapper would reach migrate_schemas without "
        "passing through this gate. Use migrate_schemas with an explicit scope instead. A separate token equal to "
        "one of these command names is refused wherever it appears, even as an argument value."
    ]
    problems += [f"token #{index} is the command name '{name}'." for index, name in hits]
    return _refuse(problems)


def _scope_text(options):
    """Fixed description of the single scope. Never includes a schema name."""
    if "--shared" in options:
        return "shared schema"
    if "--tenant" in options:
        return "all tenant schemas"
    return "shared schema (public)" if options.get("--schema") == "public" else "one tenant schema"


def _check_migration(argv, load_target):
    parsed, problems = _parse(argv, 2)
    options = parsed.options
    if problems:
        return _refuse(problems)

    if "--help" in options or "--version" in options:
        return _passthrough(_forward(argv, parsed))

    if "--list" in options:
        return _refuse([
            "--list / -l is not supported: django-tenants accepts it but nothing reads it, so the command "
            "would carry on and apply migrations. Use 'python manage.py showmigrations' to list migrations."
        ])

    if len(parsed.positionals) > 2:
        return _refuse(["too many positional arguments (at most an app label and a migration name)."])

    protected = []
    if len(parsed.positionals) == 2:
        protected.append("an explicit migration name (including 'zero')")
    for flag in ("--fake", "--fake-initial", "--prune", "--run-syncdb"):
        if flag in options:
            protected.append(flag)

    gate_flags = [flag for flag in ("--apply", "--allow-destructive", "--confirm-database") if flag in options]

    # --plan / --check never reach Django's apply step, but they are NOT read-only: for
    # every schema they touch, django-tenants calls ensure_schema() before the command
    # looks at those options, which can create the django_migrations table. They get the
    # same target checks as an apply (one scope, identity, no --settings / --pythonpath /
    # --database override) and only skip --apply and --confirm-database. A protected
    # operation keeps the command on the apply path: --prune runs before --plan.
    plan_only = ("--plan" in options or "--check" in options) and not protected
    if plan_only and gate_flags:
        return _refuse([
            "--plan / --check never apply anything, so " + ", ".join(gate_flags) +
            " must not be combined with them."
        ])

    problems = []
    scopes = [flag for flag in SCOPE_OPTIONS if flag in options]
    if not scopes:
        problems.append("no migration scope was given (use exactly one of --shared, --tenant or --schema NAME).")
    elif len(scopes) > 1:
        problems.append(
            "give exactly one scope; found " + ", ".join(scopes) + ". Run shared and tenant migrations as "
            "separate commands."
        )
    for flag in scopes:
        if parsed.counts[flag] > 1:
            problems.append(f"scope option {flag} was given more than once.")
    if "--schema" in options and not options["--schema"]:
        problems.append("--schema needs a non-empty schema name.")
    if "--database" in options and options["--database"] != "default":
        problems.append("only the 'default' database alias is supported by the gate (--database).")
    for flag in ("--settings", "--pythonpath"):
        if flag in options:
            problems.append(
                f"{flag} is not allowed when applying migrations or running --plan / --check: the target "
                "database could not be checked against the configuration Django will actually use."
            )
    if not plan_only:
        if "--apply" not in options:
            problems.append("--apply is required to apply migrations.")
        if "--confirm-database" not in options:
            problems.append("--confirm-database <database name> is required.")
        elif not options["--confirm-database"]:
            problems.append("--confirm-database needs the database name.")
        if protected and "--allow-destructive" not in options:
            problems.append(
                "protected operation(s) need --allow-destructive: " + "; ".join(protected) + "."
            )
        if not protected and "--allow-destructive" in options:
            problems.append("--allow-destructive was given but no protected operation is present; remove it.")
    if problems:
        return _refuse(problems)

    try:
        target = load_target()
    except Exception as exc:  # noqa: BLE001 - fail closed; the message is not echoed (it could be sensitive)
        return _refuse([
            f"the configured database could not be determined ({type(exc).__name__}); the command was not run."
        ])

    actual = db_identity.actual_identity(target)
    configured = f"{actual.name}@{actual.host}:{actual.port}"
    expected_value = (target.get("EDUSEKAI_EXPECTED_DATABASE") or "").strip()
    if not expected_value:
        return _refuse([
            "EDUSEKAI_EXPECTED_DATABASE is not set. Applying migrations and running --plan / --check require it "
            f"(name@host:port) so the target can be checked exactly. Configured database: {configured}."
        ])
    try:
        expected = db_identity.parse_expected(expected_value)
    except ValueError as exc:
        return _refuse([f"EDUSEKAI_EXPECTED_DATABASE is not valid: {exc}."])
    differing = db_identity.differing_fields(expected, actual)
    if differing:
        return _refuse([
            f"the configured database ({configured}) does not match EDUSEKAI_EXPECTED_DATABASE "
            f"({expected.name}@{expected.host}:{expected.port}); differing: {', '.join(differing)}. "
            "Matching is exact (no test_ exception)."
        ])
    if not plan_only and options["--confirm-database"] != actual.name:
        return _refuse([
            f"--confirm-database does not match the configured database name (configured: {configured})."
        ])

    label = _SAFE_LABEL.sub("_", (target.get("EDUSEKAI_ENV") or "").strip())[:32] or "unset"
    # Printed only after every gate check has passed. It is NOT a statement that Django
    # accepted the arguments or that anything was applied: Django has not run yet.
    if plan_only:
        notice = (
            f"Migration gate: checks passed for the configured database '{actual.name}' at "
            f"{actual.host}:{actual.port} (environment: {label}); scope: {_scope_text(options)}; "
            "operation: plan/check. These are configuration values: the gate does not verify the connection "
            "destination. --plan / --check are not guaranteed to be read-only (they can create the "
            "django_migrations table in a schema that lacks one). The command is now being handed to Django; "
            "this notice does not mean Django accepted the arguments."
        )
    else:
        notice = (
            f"Migration gate: checks passed for database '{actual.name}' at {actual.host}:{actual.port} "
            f"(environment: {label}); scope: {_scope_text(options)}; "
            f"protected operation: {'yes' if protected else 'no'}. "
            "The command is now being handed to Django; this notice does not mean Django accepted the "
            "arguments or that any migration was applied."
        )
    return Decision(True, _forward(argv, parsed), None, notice, 0)


def evaluate(argv, load_target):
    """Decide whether ``argv`` (a full sys.argv-style list) may run.

    ``load_target`` is called only when an apply or a ``--plan`` / ``--check`` is
    being considered, after every argument check has passed, and must
    return a mapping with NAME, HOST, PORT, EDUSEKAI_ENV and
    EDUSEKAI_EXPECTED_DATABASE (other keys, such as credentials, are never read).
    Never mutates ``argv``. Returns a Decision(allowed, argv, message, notice,
    exit_code): ``argv`` is what Django should receive when allowed; ``message``
    is the refusal text; ``notice`` is an informational line for stderr.
    """
    argv = list(argv)
    if len(argv) < 2:
        return _passthrough(argv)
    if argv[1].startswith("-"):
        # Fail closed: Django dispatches only these exact one-argument forms before a command
        # name; anything else would be left to its own (unverified here) dispatch.
        if argv[1:] in _TOP_LEVEL_FORMS:
            return _passthrough(argv)
        return _refuse([
            "token #1 starts with '-': before a command name only 'manage.py --help', 'manage.py -h' and "
            "'manage.py --version' are accepted. Put the command name first (for example "
            "'manage.py migrate_schemas --help')."
        ])
    command = argv[1]
    if command in WRAPPER_COMMANDS:
        return _check_wrapper(argv)
    if command not in GATED_COMMANDS:
        return _passthrough(argv)
    return _check_migration(argv, load_target)
