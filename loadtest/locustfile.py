"""
Load test for one school. Run it against a STAGING copy, never against a database people use.

    pip install locust==2.32.4
    set LOADTEST_HOST=http://sunrisevalley-demo.localhost:8000
    set LOADTEST_PASSWORD=<the staging demo password>
    locust -f loadtest/locustfile.py --host %LOADTEST_HOST% -u 500 -r 25 -t 10m --headless --csv loadtest/result

Users are the seeded demo accounts. Copy users.example.csv to users.csv (role,username, one per line).
Raise the "login" throttle rate on staging first: every simulated user logs in from the same address.
The mix follows a school morning: mostly parents and students reading, teachers on their timetable,
a few administrators on lists and the dashboard. Only GET requests: the test changes no data.
"""
import csv
import os
import random
from pathlib import Path

from locust import HttpUser, between, task

PASSWORD = os.environ.get("LOADTEST_PASSWORD", "")
USERS_FILE = Path(__file__).with_name("users.csv")


def _accounts(role):
    if not USERS_FILE.exists():
        return []
    with USERS_FILE.open(newline="", encoding="utf-8") as handle:
        return [row["username"] for row in csv.DictReader(handle) if row["role"] == role]


ACCOUNTS = {role: _accounts(role) for role in ("parent", "student", "teacher", "admin")}


class SchoolUser(HttpUser):
    abstract = True
    role = ""
    wait_time = between(2, 8)  # people read a page before clicking again

    def on_start(self):
        accounts = ACCOUNTS.get(self.role) or []
        if not accounts or not PASSWORD:
            raise RuntimeError(f"Add {self.role} logins to {USERS_FILE.name} and set LOADTEST_PASSWORD.")
        response = self.client.post(
            "/api/auth/login/", json={"username": random.choice(accounts), "password": PASSWORD}, name="login"
        )
        if response.status_code != 200:
            raise RuntimeError(f"Login failed for a {self.role}: {response.status_code}")
        self.client.get("/api/auth/me/", name="me")


class Parent(SchoolUser):
    role = "parent"
    weight = 50

    @task(4)
    def children(self):
        self.client.get("/api/parent-portal/children/", name="parent: children")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications/", name="notifications")

    @task(1)
    def me(self):
        self.client.get("/api/parent-portal/me/", name="parent: me")


class Student(SchoolUser):
    role = "student"
    weight = 20

    @task(3)
    def timetable(self):
        self.client.get("/api/timetable/my-timetable/", name="student: timetable")

    @task(2)
    def notifications(self):
        self.client.get("/api/notifications/", name="notifications")


class Teacher(SchoolUser):
    role = "teacher"
    weight = 20

    @task(3)
    def timetable(self):
        self.client.get("/api/timetable/my-timetable/", name="teacher: timetable")

    @task(2)
    def assignments(self):
        self.client.get("/api/academics/assignments/", name="teacher: assignments")

    @task(1)
    def dashboard(self):
        self.client.get("/api/dashboard/summary/", name="dashboard")


class Admin(SchoolUser):
    role = "admin"
    weight = 10

    @task(3)
    def students(self):
        self.client.get("/api/students/list/?page=1", name="admin: students")

    @task(2)
    def dashboard(self):
        self.client.get("/api/dashboard/summary/", name="dashboard")

    @task(1)
    def parents(self):
        self.client.get("/api/families/parents/?page=1", name="admin: parents")

    @task(1)
    def staff(self):
        self.client.get("/api/staff/members/?page=1", name="admin: staff")

    @task(1)
    def low_attendance(self):
        self.client.get("/api/attendance/reports/below-threshold/", name="admin: below-threshold report")
