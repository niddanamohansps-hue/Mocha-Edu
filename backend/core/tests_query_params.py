"""A malformed ?query value is the caller's mistake: it must never come back as a server error.

QueryParamSweepTests is the regression net for every API route. It finds each GET route that takes no path
parameter, reads the query parameter names its own view module uses, and sends malformed values for each one
(not a UUID, too big for any integer column, an impossible date). Any 500 fails the test with the route and
parameter, so a new endpoint that forgets to validate a value is caught in CI without anyone listing it here.
"""
import inspect
import re
import sys

from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TransactionTestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from .query_params import date_param, int_param, model_param, uuid_param

MALFORMED = ["abc", "99999999999999999999", "2026-13-45"]
# Parameters that are not read by our views: DRF's own (format/page are validated by DRF and answer 404 by
# design) and authentication helpers.
SKIP_PARAMS = {"format", "page", "page_size", "cursor", "active_role", "token", "data"}
_PARAM_PATTERNS = [
    re.compile(r"""query_params\.get\(\s*["'](\w+)["']"""),
    re.compile(r"""query_params\[\s*["'](\w+)["']"""),
    re.compile(r"""params\.get\(\s*["'](\w+)["']"""),
    re.compile(r"""params\[\s*["'](\w+)["']"""),
    re.compile(r"""(?:model_param|date_param|int_param|uuid_param|object_param)\([^)]*?["'](\w+)["']"""),
    re.compile(r"""for (?:key|field) in \(([^)]*)\)"""),
]


def _request(query):
    return Request(RequestFactory().get("/x/", query))


class HelperTests(SimpleTestCase):
    def test_absent_or_empty_is_none_and_good_values_convert(self):
        from academics.models import Section, SubjectAssignment

        self.assertIsNone(uuid_param(_request({}), "x"))
        self.assertIsNone(model_param(_request({"x": ""}), "x", Section))
        sid = "6c1f6c1e-8f0e-4c8e-9a1e-0d4f5b6a7c8d"
        self.assertEqual(str(model_param(_request({"x": sid}), "x", Section)), sid)
        self.assertEqual(int_param(_request({"x": "7"}), "x"), 7)
        self.assertEqual(int_param(_request({"x": "0"}), "x", minimum=1), 1)
        self.assertEqual(str(date_param(_request({"x": "2026-02-01"}), "x")), "2026-02-01")
        # the type comes from the field: an Instructor id is an integer, a Section id a UUID
        self.assertEqual(model_param(_request({"x": "12"}), "x", SubjectAssignment, "instructor"), 12)

    def test_malformed_values_are_400_naming_the_parameter(self):
        from academics.models import Section, SubjectAssignment

        cases = [
            lambda: uuid_param(_request({"section": "abc"}), "section"),
            lambda: model_param(_request({"section": "abc"}), "section", Section),
            lambda: model_param(_request({"instructor": "abc"}), "instructor", SubjectAssignment, "instructor"),
            lambda: model_param(_request({"instructor": "99999999999999999999"}), "instructor", SubjectAssignment, "instructor"),
            lambda: int_param(_request({"limit": "1e9"}), "limit"),
            lambda: date_param(_request({"date": "2026-13-45"}), "date"),
        ]
        for case in cases:
            with self.assertRaises(ValidationError) as caught:
                case()
            self.assertEqual(len(caught.exception.detail), 1)


def _routes():
    """(path, view module) for every API route reachable with GET and no path parameter."""
    found = []

    def walk(patterns, prefix):
        for p in patterns:
            text = str(p.pattern)
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + text)
                continue
            if not isinstance(p, URLPattern):
                continue
            path = (prefix + text).replace("^", "").replace("$", "").replace("\\Z", "").replace("\\.", ".")
            if "<" in path or "(" in path or "[" in path or not path.startswith("api/"):
                continue
            callback = p.callback
            actions = getattr(callback, "actions", None)
            cls = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
            if actions is not None:
                if "get" not in actions:
                    continue
            elif cls is None or not hasattr(cls, "get"):
                continue
            module = sys.modules.get((cls or callback).__module__)
            found.append(("/" + path.replace("/?", "/"), module))

    walk(get_resolver().url_patterns, "")
    seen, out = set(), []
    for path, module in found:
        if path not in seen:
            seen.add(path)
            out.append((path, module))
    return out


def _params_used(module):
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return set()
    names = set()
    for pattern in _PARAM_PATTERNS:
        for match in pattern.findall(source):
            names.update(re.findall(r"\w+", match) if "," in match or " " in match else [match])
    return {n for n in names if n not in SKIP_PARAMS and not n.startswith("_")}


class QueryParamSweepTests(TransactionTestCase):
    SCHEMA, DOMAIN = "qp_sweep_school", "qp-sweep.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Sweep School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.owner = User.objects.create_user(username="qp_owner", email="qp_owner@qp.test", password="Pass1234!")
        from django_tenants.utils import tenant_context

        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=role)

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username="qp_owner").delete()

    def test_no_route_answers_500_to_a_malformed_query_value(self):
        client = APIClient()
        client.raise_request_exception = False

        def login():
            response = client.post("/api/auth/login/", {"username": "qp_owner", "password": "Pass1234!"}, HTTP_HOST=self.DOMAIN)
            self.assertEqual(response.status_code, 200)

        login()
        routes = _routes()
        self.assertGreater(len(routes), 80, "route discovery found too few routes; the walker is broken")
        failures, checked, unauthenticated = [], 0, 0
        for path, module in routes:
            for name in sorted(_params_used(module)):
                for value in MALFORMED:
                    checked += 1
                    status = client.get(path, {name: value}, HTTP_HOST=self.DOMAIN).status_code
                    if status == 401:  # the session expired mid-sweep: log in again, or every later check is void
                        login()
                        status = client.get(path, {name: value}, HTTP_HOST=self.DOMAIN).status_code
                        unauthenticated += status == 401
                    if status >= 500:
                        failures.append(f"{path}?{name}={value} -> {status}")
        print(f"\nquery-parameter sweep: {len(routes)} routes, {checked} requests, {len(failures)} server errors")
        self.assertGreater(checked, 300, "too few requests were made; parameter discovery is broken")
        self.assertEqual(unauthenticated, 0, "requests ran without a session, so they proved nothing")
        self.assertEqual(failures, [], "these answered a server error:\n" + "\n".join(failures))
