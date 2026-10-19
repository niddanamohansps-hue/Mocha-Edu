"""Database identity helpers (migration safety, Stage 2).

Pure standard library: no Django import, no database access. Everything here
works on plain values, so it can be unit-tested without settings or a database
(``python -m unittest core.tests_db_identity``).

What it does
- parses the declared identity ``EDUSEKAI_EXPECTED_DATABASE`` ("name@host:port"),
- compares it with the database the settings actually point at,
- builds a safe PostgreSQL ``application_name``.

It only produces *findings* (warnings). Nothing here blocks a command; blocking
is a later, separately approved stage.

Comparison rules (deliberately strict and literal)
- name, host and port must match exactly; "127.0.0.1" and "localhost" are
  different identities, and host comparison is case-sensitive;
- Django derives the test database name as ``test_<NAME>`` (the test runner
  switches settings to it before system checks run), so ``test_<expected name>``
  on the same host and port is accepted as the matching test database.

Findings never contain credentials: only database name, host and port are used.
"""

import re
from collections import namedtuple

Identity = namedtuple("Identity", "name host port")
Finding = namedtuple("Finding", "code message hint")

CODE_NOT_SET = "edusekai.W001"
CODE_MISMATCH = "edusekai.W002"
CODE_BAD_LABEL = "edusekai.W003"
CODE_MALFORMED = "edusekai.W004"

# Result codes of check_identity(). Plain fixed strings: they carry no database name,
# host, port or credential.
IDENTITY_OK = "ok"
IDENTITY_ABSENT = "absent"
IDENTITY_MALFORMED = "malformed"
IDENTITY_MISMATCH = "mismatch"
IDENTITY_RESULTS = (IDENTITY_OK, IDENTITY_ABSENT, IDENTITY_MALFORMED, IDENTITY_MISMATCH)

ENV_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")
APP_NAME_PREFIX = "edusekai:"
APP_NAME_MAX = 63  # PostgreSQL truncates application_name to NAMEDATALEN - 1 bytes
_UNSAFE_APP_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.:-]")


def parse_expected(value):
    """Parse "name@host:port" into an Identity.

    Raises ValueError with a message safe to show to a developer.
    """
    text = (value or "").strip()
    name, at, rest = text.rpartition("@")
    if not at or not name:
        raise ValueError('expected the form "name@host:port"')
    host, colon, port = rest.rpartition(":")
    if not colon or not host:
        raise ValueError('expected the form "name@host:port" (host and port are both required)')
    if any(ch.isspace() for ch in text) or ":" in host or "@" in name:
        raise ValueError("whitespace is not allowed, and IPv6 literals are not supported (use a hostname)")
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        raise ValueError("the port must be a number from 1 to 65535")
    return Identity(name=name, host=host, port=str(int(port)))


def actual_identity(db_settings):
    """Identity of the configured database, from a Django-style DATABASES entry.

    Reads NAME, HOST and PORT only. Never touches USER or PASSWORD.
    """
    port = str(db_settings.get("PORT", "") or "").strip()
    if port.isdigit():
        port = str(int(port))
    return Identity(
        name=str(db_settings.get("NAME", "") or "").strip(),
        host=str(db_settings.get("HOST", "") or "").strip(),
        port=port,
    )


def differing_fields(expected, actual):
    """Names of the fields in which two identities differ (empty when equal)."""
    return [field for field in Identity._fields if getattr(expected, field) != getattr(actual, field)]


def matches(expected, actual):
    """True if ``actual`` is the expected database or its derived test database."""
    if not differing_fields(expected, actual):
        return True
    derived_test_name = "test_" + expected.name
    return (
        actual.name == derived_test_name
        and actual.host == expected.host
        and actual.port == expected.port
    )


def check_identity(expected_value, db_settings, *, allow_derived_test=False):
    """Decide whether the configured database is the expected one. Returns a fixed code.

    ``expected_value``     the declared identity, "name@host:port" (EDUSEKAI_EXPECTED_DATABASE)
    ``db_settings``        a DATABASES-style mapping; only NAME, HOST and PORT are read
    ``allow_derived_test`` keyword-only; only the value ``True`` enables the test-database rule

    Result (one of IDENTITY_RESULTS, never any name, host, port or credential):
    - "absent"     the expected identity is None, empty or whitespace only
    - "malformed"  it is present but not a valid "name@host:port" (or not a string)
    - "ok"         name, host and port equal the expected ones exactly (same comparison and
                   port normalisation as differing_fields/actual_identity), or, only when
                   ``allow_derived_test`` is True, the name is exactly "test_" + the expected
                   name and host and port equal the expected ones
    - "mismatch"   anything else, including an unrelated database name with the rule enabled

    Pure: no Django, no settings, no logging, no I/O. It does not change matches() or evaluate().
    """
    if expected_value is None:
        return IDENTITY_ABSENT
    if not isinstance(expected_value, str):
        return IDENTITY_MALFORMED
    if not expected_value.strip():
        return IDENTITY_ABSENT
    try:
        expected = parse_expected(expected_value)
    except ValueError:
        return IDENTITY_MALFORMED

    actual = actual_identity(db_settings or {})
    if not differing_fields(expected, actual):
        return IDENTITY_OK
    if (
        allow_derived_test is True
        and actual.name == "test_" + expected.name
        and actual.host == expected.host
        and actual.port == expected.port
    ):
        return IDENTITY_OK
    return IDENTITY_MISMATCH


def build_application_name(env_label):
    """"edusekai:<label>", restricted to safe characters and at most 63 bytes.

    The label is a free text from the environment, so unsafe characters are
    replaced rather than trusted. An empty label becomes "unset".
    """
    label = _UNSAFE_APP_NAME_CHARS.sub("_", (env_label or "").strip()) or "unset"
    return (APP_NAME_PREFIX + label)[:APP_NAME_MAX]


def _format(identity):
    return f"{identity.name}@{identity.host}:{identity.port}"


def evaluate(env_label, expected_value, db_settings):
    """Findings for the configured environment label and database identity.

    ``env_label``       value of EDUSEKAI_ENV ("" when unset)
    ``expected_value``  value of EDUSEKAI_EXPECTED_DATABASE ("" when unset)
    ``db_settings``     the DATABASES["default"] mapping (only NAME/HOST/PORT are read)
    """
    findings = []
    label = (env_label or "").strip()
    if label and not ENV_LABEL_RE.match(label):
        findings.append(
            Finding(
                CODE_BAD_LABEL,
                "EDUSEKAI_ENV contains characters that are not allowed (letters, digits, '_', '.', '-'; "
                "at most 32 characters; must start with a letter or digit).",
                "Fix EDUSEKAI_ENV in the environment. Unsafe characters are replaced in the database "
                "application_name.",
            )
        )

    actual = actual_identity(db_settings)
    if not (expected_value or "").strip():
        findings.append(
            Finding(
                CODE_NOT_SET,
                "EDUSEKAI_EXPECTED_DATABASE is not set, so the configured database "
                f"({_format(actual)}) cannot be checked against the one you intend to use.",
                'Set EDUSEKAI_EXPECTED_DATABASE="name@host:port" for this environment (see .env.example).',
            )
        )
        return findings

    try:
        expected = parse_expected(expected_value)
    except ValueError as exc:
        findings.append(
            Finding(
                CODE_MALFORMED,
                f"EDUSEKAI_EXPECTED_DATABASE is not valid: {exc}.",
                'Use the form "name@host:port", for example "mydb@127.0.0.1:5432".',
            )
        )
        return findings

    if not matches(expected, actual):
        differing = ", ".join(differing_fields(expected, actual))
        findings.append(
            Finding(
                CODE_MISMATCH,
                f"The configured database ({_format(actual)}) does not match the expected database "
                f"({_format(expected)}); differing: {differing}.",
                "Check DB_NAME, DB_HOST and DB_PORT. A DB_* variable exported in the terminal overrides "
                "the .env file.",
            )
        )
    return findings
