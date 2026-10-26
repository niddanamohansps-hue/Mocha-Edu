"""
Connects and fills an EXISTING seeded school ("Sunrise Valley Public School", schema ``sunrisevalley_school``)
so every module has related data, for manual UI testing and demos.

``seed_realistic_school`` builds students, families, staff, attendance, exams and fees, but almost no parent or
student can sign in, no staff member is a parent, and payroll, transport and library are empty. This command
adds, through the real services (so the data obeys the same rules as the screens):

  accounts       a portal login for every parent of an active student, and for students from Class 6 up
  staff_parents  some staff members who are also parents of students at the school (one person, one login)
  calendar       the school year's holidays, exams, meetings and activities
  staff_attendance  two months of staff attendance (not on holidays), so payroll has real days to work with
  leave          leave types and applications, approved and rejected, with some still waiting
  payroll        pay items, salaries (with raises), and two monthly runs: one paid, one waiting for approval
  timetable      periods, classrooms, a conflict-free weekly timetable, and cover for teachers on leave
  announcements  published, scheduled, draft and archived notices to staff, parents and students
  transport      buses, drivers, routes with stops (and one flat-fare route), seats, billed and part-paid fees
  library        books and copies, open and overdue loans, late returns with fines billed, waived or pending
  certificates   bonafide, character, transfer and experience certificates, and generated ID cards
  admissions     enquiries for next year, applications at every stage, and interviews
  inventory      stock, purchases and assets (runs seed_inventory_demo)
  alerts         absence alerts and payment receipts switched on (fee reminders stay off)

It is additive: nothing is deleted or changed. Each step skips itself when its data is already there, so running
the command again is safe. To start over, clear and re-seed the whole school with ``seed_realistic_school``.
Announcements are in-app only: no email is queued.

Everything is fictional. Logins use the same development-only password as ``seed_realistic_school`` and
``.test`` email addresses that can never receive mail. No real email, SMS or payment gateway is used: the
services it calls would queue emails (a leave approval emails the staff member, for example), so email queuing
is switched off for the whole run. In-app notifications are still created.

Usage (from the backend folder):
    python manage.py seed_connect_school
    python manage.py seed_connect_school --schema sunrisevalley_school --steps accounts,payroll
"""
import random
from contextlib import ExitStack
from datetime import date, time, timedelta
from unittest import mock
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import tenant_context

from ._seed_connect_more import MoreSteps

D = Decimal
DEFAULT_SCHEMA = "sunrisevalley_school"
PASSWORD = "Realistic#2026"  # development/demo credential only; the same one seed_realistic_school documents
EMAIL_DOMAIN = "example.test"
# In dependency order: the calendar before attendance, leave before payroll, accounts before announcements.
STEPS = (
    "accounts", "staff_parents", "calendar", "staff_attendance", "leave", "payroll", "timetable", "announcements",
    "transport", "library", "certificates", "admissions", "inventory", "alerts",
)

FIRST_NAMES = ["Ramesh", "Suresh", "Mahesh", "Dilip", "Anil", "Bhaskar", "Jitu", "Rafique", "Tarun", "Hemanta",
               "Manoj", "Pradip", "Naba", "Kamal", "Biren", "Habib", "Rupam", "Dhiren"]
LAST_NAMES = ["Das", "Baruah", "Kalita", "Saikia", "Hazarika", "Sarma", "Gogoi", "Ali", "Nath", "Boro"]

LOCALITIES = ["Beltola", "Ganeshguri", "Six Mile", "Khanapara", "Maligaon", "Jalukbari", "Zoo Road", "Chandmari"]
STOP_SUFFIXES = ["Chariali", "Market", "Bus Stand", "Temple Gate", "Petrol Pump", "Bridge", "Park", "Tiniali"]
STOP_FEES = ["900", "1100", "1300", "1500"]

CATEGORIES = ["Fiction", "Science", "Mathematics", "History", "Reference", "Biography", "Literature", "Activity Books"]
# title, author, category, price
BOOKS = [
    ("The Jungle Book", "Rudyard Kipling", "Fiction", "260"), ("Treasure Island", "R. L. Stevenson", "Fiction", "240"),
    ("Alice's Adventures in Wonderland", "Lewis Carroll", "Fiction", "220"), ("Gulliver's Travels", "Jonathan Swift", "Fiction", "250"),
    ("Panchatantra Tales", "Vishnu Sharma", "Fiction", "180"), ("Jataka Tales", "Retold", "Fiction", "170"),
    ("Tales of Lord Krishna", "Retold", "Fiction", "190"), ("The Adventures of Tom Sawyer", "Mark Twain", "Fiction", "260"),
    ("Robinson Crusoe", "Daniel Defoe", "Fiction", "240"), ("Black Beauty", "Anna Sewell", "Fiction", "210"),
    ("Heidi", "Johanna Spyri", "Fiction", "200"), ("Little Women", "Louisa May Alcott", "Fiction", "280"),
    ("Basic Science for Class 6", "School Board", "Science", "320"), ("Basic Science for Class 8", "School Board", "Science", "350"),
    ("The Story of the Earth", "Retold", "Science", "300"), ("Our Solar System", "Retold", "Science", "290"),
    ("Wonders of the Human Body", "Retold", "Science", "310"), ("Plants and Animals Around Us", "Retold", "Science", "260"),
    ("Experiments You Can Do at Home", "Retold", "Science", "340"), ("Elementary Mathematics Part 1", "School Board", "Mathematics", "280"),
    ("Elementary Mathematics Part 2", "School Board", "Mathematics", "280"), ("Fun with Numbers", "Retold", "Mathematics", "230"),
    ("Geometry Made Simple", "Retold", "Mathematics", "300"), ("Mental Maths Practice", "School Board", "Mathematics", "210"),
    ("Ancient India", "Retold", "History", "330"), ("The Freedom Struggle", "Retold", "History", "360"),
    ("Kings and Kingdoms of Assam", "Retold", "History", "370"), ("The Story of the Ahom Dynasty", "Retold", "History", "340"),
    ("World History for Young Readers", "Retold", "History", "420"), ("Student's Dictionary", "Editorial Board", "Reference", "480"),
    ("Atlas of the World", "Editorial Board", "Reference", "650"), ("Encyclopedia for Children", "Editorial Board", "Reference", "720"),
    ("Hindi Grammar", "Editorial Board", "Reference", "260"), ("General Knowledge Digest", "Editorial Board", "Reference", "240"),
    ("The Life of Mahatma Gandhi", "Retold", "Biography", "270"), ("Dr. A. P. J. Abdul Kalam: A Life", "Retold", "Biography", "310"),
    ("Great Scientists of India", "Retold", "Biography", "320"), ("Women Who Changed the World", "Retold", "Biography", "330"),
    ("Poems for Young Readers", "Anthology", "Literature", "200"), ("Assamese Folk Tales", "Anthology", "Literature", "220"),
    ("Short Stories for Class 7", "Anthology", "Literature", "230"), ("Rhymes and Songs", "Anthology", "Literature", "150"),
    ("Drawing and Colouring Book", "Activity", "Activity Books", "120"), ("Origami for Beginners", "Activity", "Activity Books", "160"),
    ("Puzzles and Brain Teasers", "Activity", "Activity Books", "170"), ("Crosswords for Kids", "Activity", "Activity Books", "130"),
]

SALARY_BY_DESIGNATION = {
    "Administrative Officer": 30000, "Librarian": 24000, "Accountant": 32000,
    "Receptionist": 18000, "Lab Assistant": 19000, "Counsellor": 28000,
}


def _clock(hour, minute):
    """A time of day from an hour and any number of minutes, which may run past the hour."""
    total = hour * 60 + minute
    return time(total // 60 % 24, total % 60)


def _round_to(value, step):
    return int(round(value / step) * step)


class Command(MoreSteps, BaseCommand):
    help = "Connects an existing seeded school: portal logins, staff who are parents, and data for every module."

    def add_arguments(self, parser):
        parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"The school's schema (default {DEFAULT_SCHEMA}).")
        parser.add_argument("--seed", type=int, default=20260929, help="Deterministic random seed.")
        parser.add_argument("--steps", default=",".join(STEPS), help=f"Comma-separated steps to run. Available: {', '.join(STEPS)}.")

    def handle(self, *args, **options):
        from organizations.models import Organization

        schema = options["schema"]
        if schema == "public":
            raise CommandError("This command fills a school, not the public schema.")
        steps = [s.strip() for s in options["steps"].split(",") if s.strip()]
        unknown = [s for s in steps if s not in STEPS]
        if unknown:
            raise CommandError(f"Unknown step(s): {', '.join(unknown)}. Available: {', '.join(STEPS)}.")
        organization = Organization.objects.filter(schema_name=schema).first()
        if organization is None:
            raise CommandError(f"No school with schema '{schema}' exists. Run seed_realistic_school first.")

        self.rng = random.Random(options["seed"])
        self.today = timezone.localdate()
        with tenant_context(organization), self._no_email():
            self._load_people()
            for name in [s for s in STEPS if s in steps]:  # always in dependency order
                with transaction.atomic():
                    result = getattr(self, f"_step_{name}")()
                self.stdout.write(f"[{name}] {result}")
        self.stdout.write(self.style.SUCCESS("Done. Logins use the same development password as seed_realistic_school."))

    # --- shared lookups ---------------------------------------------------------------------------------

    # Every module that imports queue_email by name, so each reference has to be replaced where it is used.
    EMAIL_QUEUERS = (
        "notifications.services", "notifications.alerts", "staff.leave_services", "announcements.services",
        "inventory.alerts",
    )

    def _no_email(self):
        """Switch off email queuing for the run: no outbox row is written, so nothing can ever be sent later."""
        stack = ExitStack()
        for module in self.EMAIL_QUEUERS:
            stack.enter_context(mock.patch(f"{module}.queue_email", return_value=None))
        return stack

    def _load_people(self):
        from roles.models import UserRole
        from staff.models import StaffMember
        from students.models import Student

        self.students = list(Student.objects.filter(status="active").select_related("profile").order_by("enrollment_id"))
        self.staff = list(StaffMember.objects.filter(is_active=True).select_related("profile").order_by("employee_id"))
        owner_role = UserRole.objects.filter(role__slug="owner").select_related("user").first()
        self.owner_id = owner_role.user_id if owner_role else None
        if not self.students or not self.staff:
            raise CommandError("This school has no active students or staff. Run seed_realistic_school first.")

    def _staff_user_id(self, designation):
        member = next((s for s in self.staff if s.designation == designation and s.profile.user_id), None)
        return member.profile.user_id if member else None

    def _new_user(self, username, email, role, profile, password_hash):
        """A login for ``profile``. The profile is linked before the role is added, so no duplicate profile appears."""
        from accounts.models import User
        from roles.models import UserRole

        user = User(username=username, email=email, password=password_hash)
        user.save()
        profile.user_id = user.id
        profile.save(update_fields=["user_id"])
        UserRole.objects.create(user=user, role=role)
        return user

    # --- accounts -----------------------------------------------------------------------------------------

    def _step_accounts(self):
        from django.contrib.auth.hashers import make_password

        from families.models import Parent
        from roles.models import Role
        from students.models import StudentLevel

        parent_role, student_role = Role.objects.get(slug="parent"), Role.objects.get(slug="student")
        password_hash = make_password(PASSWORD)  # hashed once and shared: hashing hundreds of passwords is slow

        parents = (
            Parent.objects.filter(profile__user_id__isnull=True, student_links__student__status="active")
            .select_related("profile").distinct().order_by("id")
        )
        made_parents = no_email = 0
        for parent in parents:
            tag = str(parent.id)[:8]
            has_email = self.rng.random() > 0.2  # a fifth of parents gave no email: they still get the in-app notice
            if not has_email:
                no_email += 1
            # No email is stored as NULL, not "": the email column is unique and NULLs may repeat, empty strings may not.
            self._new_user(f"svc_p_{tag}", f"svc_p_{tag}@{EMAIL_DOMAIN}" if has_email else None, parent_role, parent.profile, password_hash)
            made_parents += 1

        current = {
            e.student_id: e.level.order
            for e in StudentLevel.objects.filter(is_current=True, student__status="active").select_related("level")
        }
        made_students = 0
        for student in self.students:
            if student.profile.user_id or current.get(student.id, 0) < 9:  # order 9 is Class 6
                continue
            tag = str(student.id)[:8]
            self._new_user(f"svc_s_{tag}", f"svc_s_{tag}@{EMAIL_DOMAIN}", student_role, student.profile, password_hash)
            made_students += 1
        return f"{made_parents} parent logins ({no_email} without an email address), {made_students} student logins (Class 6 and up)"

    # --- staff who are also parents ------------------------------------------------------------------------

    def _step_staff_parents(self):
        from families.models import Parent, StudentParentRelation
        from roles.models import Role, UserRole

        parent_role = Role.objects.get(slug="parent")
        already = sum(1 for s in self.staff if hasattr(s.profile, "parent_record"))
        wanted = min(25, max(5, round(len(self.staff) * 0.12))) - already  # top up, so a second run adds nobody
        if wanted <= 0:
            return f"skipped: {already} staff members are already parents"
        candidates = [s for s in self.staff if s.profile.user_id and not hasattr(s.profile, "parent_record")]
        self.rng.shuffle(candidates)

        made = guardians = 0
        for member in candidates:
            if made >= wanted:
                break
            relation = {"male": "father", "female": "mother"}.get(member.profile.gender, "guardian")
            student = self._student_for(member, relation)
            if student is None and relation != "guardian":
                relation = "guardian"  # no child lacks a father or mother, so join the family as a guardian
                student = self._student_for(member, relation)
            if student is None:
                continue
            # The whole family: every child of the parents this student already has.
            family = {student.id: student}
            for link in StudentParentRelation.objects.filter(student=student).select_related("parent"):
                for sibling_link in StudentParentRelation.objects.filter(parent=link.parent).select_related("student"):
                    if sibling_link.student.status == "active":
                        family[sibling_link.student_id] = sibling_link.student
            parent = Parent.objects.create(profile=member.profile, occupation=member.designation or "Staff", income_level="middle")
            for child in family.values():
                StudentParentRelation.objects.get_or_create(
                    student=child, parent=parent, defaults={"relation_type": relation, "is_primary_contact": False}
                )
            UserRole.objects.get_or_create(user_id=member.profile.user_id, role=parent_role)
            made += 1
            guardians += relation == "guardian"
        return f"{made} staff members are now also parents ({guardians} as guardians where no father or mother place was free)"

    def _student_for(self, member, relation):
        """An active student the staff member can plausibly be the ``relation`` of: no one has that place, the age fits."""
        from families.models import StudentParentRelation

        dob = member.profile.date_of_birth
        pool = []
        for student in self.students:
            child_dob = student.profile.date_of_birth
            if dob and child_dob and (child_dob - dob).days < 365 * 21:
                continue  # a parent must be at least about 21 years older
            links = StudentParentRelation.objects.filter(student=student)
            if not links.exists() or links.filter(parent__profile=member.profile).exists():
                continue
            if relation != "guardian" and links.filter(relation_type=relation).exists():
                continue
            if relation == "guardian" and links.filter(relation_type="guardian").exists():
                continue
            pool.append(student)
        return self.rng.choice(pool) if pool else None

    # --- staff attendance -----------------------------------------------------------------------------------

    def _step_staff_attendance(self):
        from attendance.models import AttendanceSettings, StaffAttendance

        off = AttendanceSettings.weekly_off()
        first = self.today - timedelta(days=75)
        days = [first + timedelta(days=i) for i in range((self.today - first).days) if (first + timedelta(days=i)).weekday() not in off]
        holidays = self._holiday_dates(first, self.today)
        days = [d for d in days if d not in holidays]
        existing = set(StaffAttendance.objects.filter(date__gte=first).values_list("staff_id", "date"))
        rows = []
        for member in self.staff:
            for day in days:
                if (member.id, day) in existing or (member.joining_date and day < member.joining_date):
                    continue
                roll = self.rng.random()
                status = ("present" if roll < 0.935 else "late" if roll < 0.965 else "absent" if roll < 0.98
                          else "leave" if roll < 0.995 else "half_day")
                rows.append(StaffAttendance(staff=member, date=day, status=status))
        StaffAttendance.objects.bulk_create(rows, ignore_conflicts=True)
        return f"{len(rows)} attendance marks for {len(self.staff)} staff over {len(days)} working days"

    # --- payroll ----------------------------------------------------------------------------------------------

    def _step_payroll(self):
        from payroll import services
        from payroll.models import PayrollRun, SalaryComponent

        if SalaryComponent.objects.filter(code="HRA").exists():
            return "skipped: pay items already exist"
        calc, kind = SalaryComponent.Calculation, SalaryComponent.Kind
        defs = [
            ("House rent allowance", "HRA", kind.EARNING, calc.PERCENT_OF_BASIC, "20", 1),
            ("Conveyance allowance", "CONV", kind.EARNING, calc.FIXED, "1600", 2),
            ("Medical allowance", "MED", kind.EARNING, calc.FIXED, "1250", 3),
            ("Provident fund", "PF", kind.DEDUCTION, calc.PERCENT_OF_BASIC, "12", 4),
            ("Professional tax", "PTAX", kind.DEDUCTION, calc.FIXED, "200", 5),
        ]
        comp = {
            code: SalaryComponent.objects.create(name=name, code=code, kind=k, calculation=c, default_value=D(v), sort_order=o)
            for name, code, k, c, v, o in defs
        }
        base, raised = date(2025, 4, 1), date(2026, 4, 1)
        raises = 0
        for member in self.staff:
            if member.designation == "Teacher":
                basic = min(55000, 22000 + (member.experience_years or 0) * 1200)
            else:
                basic = SALARY_BY_DESIGNATION.get(member.designation, 22000) + self.rng.choice([0, 1000, 2000])
            basic = _round_to(basic, 500)
            if self.rng.random() < 0.4:  # a raise this April: the old salary stays in the history
                services.set_salary(staff=member, basic_amount=D(_round_to(basic / 1.08, 100)), effective_from=base, note="Starting salary", user_id=self.owner_id)
                services.set_salary(staff=member, basic_amount=D(basic), effective_from=raised, note="Annual increment", user_id=self.owner_id)
                raises += 1
            else:
                services.set_salary(staff=member, basic_amount=D(basic), effective_from=base, note="Starting salary", user_id=self.owner_id)
            senior = member.designation == "Teacher" and (member.experience_years or 0) >= 12
            for code in ("HRA", "CONV", "PF", "PTAX"):
                # Senior teachers get a larger conveyance amount than the usual one.
                value = D("2200") if code == "CONV" and senior else None
                services.assign_component(staff=member, component=comp[code], effective_from=base, value=value, user_id=self.owner_id)
            if self.rng.random() < 0.3:
                services.assign_component(staff=member, component=comp["MED"], effective_from=base, user_id=self.owner_id)

        first_of_this = self.today.replace(day=1)
        last_month_end = first_of_this - timedelta(days=1)
        prev_month_end = last_month_end.replace(day=1) - timedelta(days=1)
        approver = self._staff_user_id("Accountant") or next((s.profile.user_id for s in self.staff if s.profile.user_id and s.profile.user_id != self.owner_id), None)

        paid = services.create_run(year=prev_month_end.year, month=prev_month_end.month, notes="Salary for the month", user_id=self.owner_id)
        services.calculate_run(paid, user_id=self.owner_id)
        paid.refresh_from_db()
        services.approve_run(paid, user_id=approver)
        paid.refresh_from_db()
        services.record_payment(paid, user_id=approver, paid_on=min(self.today, last_month_end + timedelta(days=3)), method=PayrollRun.Method.BANK_TRANSFER, reference="NEFT batch")

        waiting = services.create_run(year=last_month_end.year, month=last_month_end.month, notes="Waiting for approval", user_id=self.owner_id)
        services.calculate_run(waiting, user_id=self.owner_id)
        return f"5 pay items, salaries for {len(self.staff)} staff ({raises} with a raise), a paid run for {prev_month_end:%B %Y} and a calculated run for {last_month_end:%B %Y}"

    # --- transport -----------------------------------------------------------------------------------------------

    def _step_transport(self):
        from fees.models import StudentFee
        from fees.services import record_payment
        from transport import services
        from transport.models import Driver, Route, RouteStop, Vehicle

        if Vehicle.objects.filter(registration_number__startswith="AS-01-SV").exists():
            return "skipped: demo vehicles already exist"
        today = self.today
        n_buses = max(3, min(8, len(self.students) // 90 + 3))
        capacities = [52, 40, 32, 40, 52, 32, 40, 32]
        buses = []
        for i in range(n_buses):
            insurance = today + timedelta(days=self.rng.randint(90, 300))
            fitness = today + timedelta(days=self.rng.randint(90, 300))
            if i == 0:
                insurance = today - timedelta(days=20)  # one expired policy
            if i == 1:
                fitness = today + timedelta(days=12)  # one fitness certificate due soon
            buses.append(Vehicle.objects.create(
                registration_number=f"AS-01-SV-{1001 + i}", name=f"Bus {i + 1}", make_model=self.rng.choice(["Tata Starbus", "Ashok Leyland Lynx", "Force Traveller"]),
                capacity=capacities[i], insurance_expiry=insurance, fitness_expiry=fitness,
            ))
        names = [f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}" for _ in range(n_buses * 2)]
        drivers, helpers = [], []
        for i in range(n_buses):
            licence = today + timedelta(days=self.rng.randint(120, 900))
            if i == 2:
                licence = today + timedelta(days=25)  # one licence due soon
            drivers.append(Driver.objects.create(
                full_name=names[i], role=Driver.Role.DRIVER, phone=f"+91-9{self.rng.randint(100000000, 999999999)}",
                license_number=f"AS01 2019{self.rng.randint(100000, 999999)}", license_expiry=licence,
            ))
            if i % 2 == 0:
                helpers.append(Driver.objects.create(full_name=names[n_buses + i], role=Driver.Role.HELPER, phone=f"+91-8{self.rng.randint(100000000, 999999999)}"))

        school = "Sunrise Valley Public School"
        routes = []
        for i, bus in enumerate(buses):
            place = LOCALITIES[i % len(LOCALITIES)]
            flat = i == n_buses - 1  # the last route has no stops: one flat fare, with a pick-up note on each seat
            route = Route.objects.create(
                name=f"{place} route" + (" (flat fare)" if flat else ""), vehicle=bus, driver=drivers[i],
                helper=helpers[i // 2] if i % 2 == 0 and i // 2 < len(helpers) else None,
                start_point="Bus depot" if not flat else "", end_point=school, monthly_fee=D("1000") if not flat else D("800"),
            )
            if not flat:
                for k in range(4):
                    RouteStop.objects.create(
                        route=route, name=f"{place} {STOP_SUFFIXES[(i + k) % len(STOP_SUFFIXES)]}", sequence=k + 1,
                        pickup_time=_clock(6, 35 + k * 9 + i * 2), drop_time=_clock(15, 10 + k * 8),
                        monthly_fee=D(STOP_FEES[k]) if k != 1 else None,  # the second stop uses the route fee
                    )
            routes.append(route)

        seated = self._seat_students(routes, services)
        last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        months = [last_month, (last_month - timedelta(days=1)).replace(day=1)]  # the last two full months, newest first
        billed = 0
        for month in reversed(months):
            summary = services.bill_month(year=month.year, month=month.month, user_id=self.owner_id)
            billed += summary["billed"]
        paid = 0
        oldest = months[-1]
        for fee in StudentFee.objects.filter(transport_bill__month=oldest).select_related("student"):
            if self.rng.random() < 0.7:
                record_payment(
                    student=fee.student, amount=fee.amount_due, method=self.rng.choice(["cash", "bank_transfer", "upi"]),
                    allocations=[{"student_fee_id": fee.id, "amount": fee.amount_due}], recorded_by=None,
                )
                paid += 1
        return f"{len(buses)} buses, {len(drivers) + len(helpers)} drivers and helpers, {len(routes)} routes, {seated} students seated, {billed} monthly fees billed, {paid} paid"

    def _seat_students(self, routes, services):
        """About a fifth of the families use the bus; brothers and sisters share a route and stop."""
        from families.models import StudentParentRelation
        from transport.models import RouteStop, StudentTransport

        by_id = {s.id: s for s in self.students}
        seen, families = set(), []
        for student in self.students:
            if student.id in seen:
                continue
            group = {student.id}
            for link in StudentParentRelation.objects.filter(student=student):
                group |= set(StudentParentRelation.objects.filter(parent=link.parent).values_list("student_id", flat=True))
            group &= set(by_id)
            seen |= group
            families.append([by_id[i] for i in sorted(group, key=str)])
        self.rng.shuffle(families)

        start = date(self.today.year if self.today.month >= 4 else self.today.year - 1, 4, 1)
        seated = 0
        for family in families:
            if self.rng.random() > 0.22:
                continue
            for route in self.rng.sample(routes, len(routes)):
                taken = StudentTransport.objects.filter(route=route, end_date__isnull=True).count()
                if taken + len(family) > route.vehicle.capacity:
                    continue
                stops = list(RouteStop.objects.filter(route=route).order_by("sequence"))
                stop = self.rng.choice(stops) if stops else None
                note = "" if stop else f"near the {self.rng.choice(STOP_SUFFIXES).lower()}, {route.name.replace(' (flat fare)', '').replace(' route', '')}"
                mode = self.rng.choices(["both", "pickup", "dropoff"], weights=[85, 8, 7])[0]
                for child in family:
                    services.assign_student(
                        student=child, route=route, stop=stop, start_date=start, mode=mode, pickup_note=note, user_id=self.owner_id
                    )
                    seated += 1
                break
        return seated

    # --- library ------------------------------------------------------------------------------------------------------

    def _step_library(self):
        from library import services
        from library.models import Book, BookCategory, BookCopy, Fine, LibrarySettings

        if BookCopy.objects.filter(accession_number__startswith="SVL-").exists():
            return "skipped: demo books already exist"
        today = self.today
        LibrarySettings.update_singleton(user_id=self.owner_id, fine_per_day=D("2.00"))
        librarian = self._staff_user_id("Librarian") or self.owner_id
        cats = {name: BookCategory.objects.create(name=name) for name in CATEGORIES}
        accession, copies = 0, []
        for title, author, category, price in BOOKS:
            book = Book.objects.create(
                title=title, author=author, category=cats[category], price=D(price),
                shelf_location=f"Rack {self.rng.choice('ABCDEF')}-{self.rng.randint(1, 6)}",
                publication_year=self.rng.randint(1995, 2023),
            )
            for _ in range(self.rng.choice([2, 3, 3, 4, 5])):
                accession += 1
                copies.append(BookCopy.objects.create(book=book, accession_number=f"SVL-{accession:05d}"))
        self.rng.shuffle(copies)
        pool = iter(copies)

        students = list(self.students)
        teachers = list(self.staff)
        self.rng.shuffle(students)
        self.rng.shuffle(teachers)
        borrowers = iter(students)

        def take_copy():
            return next(pool, None)

        returned = late = lost = staff_loans = 0
        late_loans = []
        # History: books borrowed and handed back, on time or late.
        for _ in range(55):
            student, copy = next(borrowers, None), take_copy()
            if student is None or copy is None:
                break
            ago = self.rng.randint(25, 80)
            loan = services.issue_book(copy=copy, student=student, issued_on=today - timedelta(days=ago), user_id=librarian)
            if self.rng.random() < 0.25:
                back = loan.due_on + timedelta(days=self.rng.randint(3, 12))
                if back > today:
                    back = today - timedelta(days=1)
                if back < loan.issued_on:
                    back = loan.issued_on
                _, fine = services.return_book(loan=loan, returned_on=back, user_id=librarian)
                late += 1
                if fine is not None:
                    late_loans.append(fine)
            else:
                back = min(today, loan.issued_on + timedelta(days=self.rng.randint(2, 13)))
                services.return_book(loan=loan, returned_on=back, user_id=librarian)
            returned += 1
        # Staff borrow too.
        for member in teachers[:10]:
            copy = take_copy()
            if copy is None:
                break
            services.issue_book(copy=copy, staff=member, issued_on=today - timedelta(days=self.rng.randint(1, 40)), user_id=librarian)
            staff_loans += 1
        # Books on loan now: most on time, some overdue.
        open_now = overdue = 0
        for _ in range(45):
            student, copy = next(borrowers, None), take_copy()
            if student is None or copy is None:
                break
            ago = self.rng.randint(1, 13) if self.rng.random() < 0.8 else self.rng.randint(18, 34)
            loan = services.issue_book(copy=copy, student=student, issued_on=today - timedelta(days=ago), user_id=librarian)
            open_now += 1
            overdue += int(loan.due_on < today)
        # Two lost books.
        for _ in range(2):
            student, copy = next(borrowers, None), take_copy()
            if student is None or copy is None:
                break
            loan = services.issue_book(copy=copy, student=student, issued_on=today - timedelta(days=30), user_id=librarian)
            _, fine = services.report_lost(loan=loan, on=today - timedelta(days=3), user_id=librarian)
            lost += 1
            if fine is not None:
                late_loans.append(fine)

        # Fines: some billed in Fees, one waived with a reason, one collected from staff, the rest left pending.
        billed = waived = 0
        for index, fine in enumerate(late_loans):
            fine = Fine.objects.select_related("loan").get(pk=fine.pk)
            if fine.loan.student_id is None:
                continue
            if index % 3 == 0:
                try:
                    services.bill_fine(fine=fine, user_id=librarian)
                    billed += 1
                except Exception:
                    pass
            elif index == 1:
                services.waive_fine(fine=fine, reason="Book returned late because the school was closed", user_id=librarian)
                waived += 1
        return (f"{len(BOOKS)} titles, {len(copies)} copies, {returned} returned loans ({late} late), {open_now + staff_loans} on loan now "
                f"({overdue} overdue), {lost} lost, {billed} fines billed in Fees, {waived} waived")

    # --- alerts -----------------------------------------------------------------------------------------------------------

    def _step_alerts(self):
        from notifications.models import NotificationSettings

        NotificationSettings.update_singleton(
            user_id=self.owner_id, absence_alerts_enabled=True, payment_receipts_enabled=True
        )
        return "absence alerts and payment receipts switched on (fee reminders stay off, so no old fees are chased)"
