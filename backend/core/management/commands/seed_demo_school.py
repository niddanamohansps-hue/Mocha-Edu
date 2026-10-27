"""
Builds a complete, internally-consistent, entirely SYNTHETIC demo school
("Green Valley International School") for manual UI testing - one tenant,
realistic academic structure, ~500 students, families, staff, attendance
history, timetable, examinations/results, fees/payments, notification
outbox states, audit trail, and course content.

Every record is fictional. Demo accounts use the IANA-reserved ".test"
email TLD (guaranteed non-deliverable/non-real, see RFC 2606) and a
documented development-only password - never real personal data, never a
real payment, never a real outbound email/SMS.

Reuses existing business-logic services wherever one exists (fees.services,
roles seeding via the post_migrate signal, examinations' own result-
calculation helper) rather than writing to models directly where a service
already encodes the correct rules - see each _seed_* method's docstring for
exactly which path was taken and why.

Usage:
    python manage.py seed_demo_school
    python manage.py seed_demo_school --students 500 --seed 2026
    python manage.py seed_demo_school --students 100 --seed 7 --academic-years 1
    python manage.py seed_demo_school --clear
    python manage.py seed_demo_school --dry-run
"""

import random
import string
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context


class Command(BaseCommand):
    help = (
        "Creates (or clears) a complete synthetic demo school "
        "('Green Valley International School') for manual UI testing."
    )

    SCHEMA_NAME = "greenvalley_demo"
    DOMAIN = "greenvalley-demo.localhost"
    ORG_NAME = "Green Valley International School"
    # .test is IANA-reserved for testing (RFC 2606) - guaranteed to never
    # resolve or deliver mail, regardless of environment configuration.
    EMAIL_DOMAIN = "demo.edusekai.test"
    DEMO_PASSWORD = "DemoPass#2026"  # development/demo credential only
    SUPERUSER_USERNAME = "demo_superuser"

    BASE_YEAR = 2026  # the "current" academic year is always this, regardless of --academic-years

    GRADE_COUNT = 10  # Grade 1 .. Grade 10
    # Younger grades get 3 sections (more students at the bottom of the
    # pyramid, as in a real school); older grades get 2.
    SECTIONS_FOR_GRADE = {1: 3, 2: 3, 3: 3, 4: 3, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2}
    SECTION_LETTERS = ["A", "B", "C"]

    CORE_SUBJECTS = [
        ("ENG", "English"),
        ("MTH", "Mathematics"),
        ("SCI", "Science"),
        ("SOC", "Social Studies"),
    ]

    MALE_FIRST_NAMES = [
        "Aarav", "Rohan", "Arjun", "Vihaan", "Kabir", "Ishaan", "Reyansh", "Aditya",
        "Vivaan", "Sai", "Dhruv", "Karan", "Yash", "Aryan", "Dev", "Krishna", "Rudra",
        "Shaurya", "Parth", "Veer", "Ansh", "Ayaan", "Atharv", "Harsh", "Nikhil",
        "Rahul", "Siddharth", "Varun", "Vikram", "Tanish", "Lakshya", "Pranav",
        "Raghav", "Ritvik", "Samar", "Ujjwal", "Yuvraj", "Abhinav", "Chirag", "Devansh",
    ]
    FEMALE_FIRST_NAMES = [
        "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Sara", "Pari", "Anika",
        "Ira", "Navya", "Riya", "Isha", "Avni", "Tara", "Zara", "Meera", "Nitya",
        "Aarohi", "Prisha", "Vanya", "Siya", "Kavya", "Shreya", "Tanvi", "Aditi",
        "Bhavya", "Charvi", "Disha", "Esha", "Gauri", "Ishita", "Jiya", "Khushi",
        "Lavanya", "Mahika", "Niharika", "Oorja", "Pihu", "Rhea",
    ]
    SURNAMES = [
        "Sharma", "Das", "Mehta", "Kapoor", "Sen", "Gupta", "Reddy", "Nair", "Iyer",
        "Rao", "Verma", "Singh", "Patel", "Joshi", "Malhotra", "Chatterjee", "Bose",
        "Mukherjee", "Pillai", "Menon", "Agarwal", "Bansal", "Chawla", "Desai",
        "Dutta", "Ghosh", "Kulkarni", "Mishra", "Pandey", "Rastogi", "Saxena",
        "Shah", "Trivedi", "Yadav", "Bhatia", "Chandra", "Dubey", "Khanna",
        "Nambiar", "Thakur",
    ]
    STREETS = [
        "Lake View Road", "Maple Avenue", "Garden Lane", "Hill Side Street",
        "Riverside Colony", "Palm Grove Road", "Sunrise Boulevard", "Cedar Park",
        "Orchid Street", "Willow Creek Road",
    ]
    CITIES = ["Rivergate", "Lakeview Town", "Hillcrest", "Northfield", "Brookhaven"]
    DEPARTMENTS = ["Science", "Mathematics", "Languages", "Social Science", "Administration"]
    JOB_TITLES = [
        "Software Engineer", "Shop Owner", "Civil Engineer", "Bank Officer",
        "Doctor", "Accountant", "Government Officer", "Farmer", "Business Owner",
        "Nurse", "Architect", "Sales Manager",
    ]

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=500, help="Number of students to create (default: 500).")
        parser.add_argument("--seed", type=int, default=2026, help="Deterministic RNG seed - same seed always produces the same dataset (default: 2026).")
        parser.add_argument("--academic-years", type=int, default=2, help="How many academic years of history to create, ending at the current year (default: 2).")
        parser.add_argument("--clear", action="store_true", help="Remove the demo school (and only the demo school) instead of creating it.")
        parser.add_argument("--dry-run", action="store_true", help="Print the dataset plan without creating anything.")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.num_students = options["students"]
        self.seed = options["seed"]
        self.num_years = max(1, options["academic_years"])
        self.rng = random.Random(self.seed)

        self.years = [str(self.BASE_YEAR - (self.num_years - 1 - i)) for i in range(self.num_years)]
        self.current_year = self.years[-1]
        self.previous_year = self.years[-2] if len(self.years) > 1 else None

        if options["dry_run"]:
            self._print_dry_run_plan()
            return

        if options["clear"]:
            self._clear_demo_school()
            return

        from django.contrib.auth.hashers import make_password

        # Computed once - see _create_user_and_profile for why.
        self._demo_password_hash = make_password(self.DEMO_PASSWORD)

        from organizations.models import Organization

        if Organization.objects.filter(schema_name=self.SCHEMA_NAME).exists():
            raise CommandError(
                f"Demo school already exists (schema='{self.SCHEMA_NAME}'). "
                f"Re-run with --clear first if you want to recreate it."
            )

        self._reset_counters()

        self.stdout.write(self.style.SUCCESS(
            f"Creating demo school '{self.ORG_NAME}' (schema='{self.SCHEMA_NAME}', "
            f"seed={self.seed}, students={self.num_students}, years={self.years})..."
        ))

        organization = self._create_organization()
        try:
            with tenant_context(organization):
                with transaction.atomic():
                    self._grant_role_permissions()
                    self._create_demo_accounts_and_structure(organization)
        except Exception:
            # All-or-nothing: a failure partway through must not leave a
            # half-seeded demo school sitting around under a name a future
            # --clear-free run would collide with. Clean up the
            # Organization (and its freshly-created, still mostly-empty
            # schema) before re-raising so the error is visible but the
            # database is left exactly as it was before this command ran.
            connection.set_schema_to_public()
            org = Organization.objects.filter(schema_name=self.SCHEMA_NAME).first()
            if org is not None:
                org.delete(force_drop=True)  # force_drop=True actually drops the Postgres
                # schema itself - a plain .delete() only removes the Organization row and
                # would leave an orphaned schema a future run could collide with.
            raise

        self._print_summary()

    def _announce(self, message):
        self.stdout.write(message)
        self.stdout.flush()

    def _reset_counters(self):
        self.created = {
            "students": 0, "parents": 0, "families": 0, "instructors": 0,
            "staff": 0, "sections": 0, "subjects": 0, "subject_assignments": 0,
            "attendance_sessions": 0, "attendance_records": 0,
            "timetable_entries": 0, "rooms": 0, "periods": 0,
            "examinations": 0, "exam_schedules": 0, "exam_marks": 0,
            "exam_results": 0, "fee_structures": 0, "student_fees": 0,
            "payments": 0, "outbox_events": 0, "audit_logs": 0,
            "course_content": 0, "assignments": 0, "submissions": 0,
            "promotion_records": 0,
        }
        self.demo_logins = []  # list of (role_label, email, password) for the final report

    # ------------------------------------------------------------------
    # Dry run / clear
    # ------------------------------------------------------------------

    def _print_dry_run_plan(self):
        num_sections = sum(self.SECTIONS_FOR_GRADE[g] for g in range(1, self.GRADE_COUNT + 1))
        num_subjects = len(self.CORE_SUBJECTS) * self.GRADE_COUNT
        self.stdout.write(self.style.WARNING("DRY RUN - no data will be created.\n"))
        self.stdout.write(
            f"Would create:\n"
            f"  Organization:        1 ('{self.ORG_NAME}', schema='{self.SCHEMA_NAME}')\n"
            f"  Academic years:      {self.num_years} ({', '.join(self.years)})\n"
            f"  Grades/levels:       {self.GRADE_COUNT}\n"
            f"  Sections:            {num_sections}\n"
            f"  Subjects:            {num_subjects}\n"
            f"  Students:            {self.num_students}\n"
            f"  Teachers:            35\n"
            f"  Non-teaching staff:  15\n"
            f"  Examinations:        5 (4 published, 1 unpublished)\n"
            f"  Fee heads:           4\n"
            f"  Seed:                {self.seed}\n"
        )

    def _clear_demo_school(self):
        from accounts.models import User
        from organizations.models import Organization

        try:
            organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        except Organization.DoesNotExist:
            self.stdout.write(self.style.WARNING("No existing demo school to clear - nothing to do."))
            return

        # Collect every public-schema User this demo tenant's Profiles
        # reference BEFORE dropping the schema (the schema drop removes the
        # Profile rows, but Profile.user_id is only a soft link - it does
        # NOT cascade-delete the actual User row, which lives in public).
        with tenant_context(organization):
            from profiles.models import Profile

            user_ids = list(Profile.objects.exclude(user_id=None).values_list("user_id", flat=True))

        connection.set_schema_to_public()
        organization.delete(force_drop=True)  # drops the tenant schema + Organization + Domain rows

        deleted_count = User.objects.filter(id__in=user_ids).count()
        User.objects.filter(id__in=user_ids).delete()
        # The demo superuser is tracked separately (it never gets a
        # tenant Profile - see _create_demo_accounts_and_structure), so it
        # needs its own explicit, exact-username removal.
        extra_deleted, _ = User.objects.filter(username=self.SUPERUSER_USERNAME).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Cleared demo school: dropped schema '{self.SCHEMA_NAME}' and removed "
            f"{deleted_count + (1 if extra_deleted else 0)} associated user account(s). "
            f"No other tenant's data was touched."
        ))

    # ------------------------------------------------------------------
    # Organization / tenant creation
    # ------------------------------------------------------------------

    def _create_organization(self):
        from organizations.models import Domain, Organization

        organization = Organization.objects.create(
            schema_name=self.SCHEMA_NAME,
            name=self.ORG_NAME,
            address="12 Lake View Road, Rivergate",
            phone="+91-99999-00000",
            email=f"info@{self.EMAIL_DOMAIN}",
            is_active=True,
        )  # auto_create_schema=True on Organization creates + migrates the schema synchronously
        Domain.objects.create(domain=self.DOMAIN, tenant=organization, is_primary=True)
        return organization

    # ------------------------------------------------------------------
    # RBAC - the five system roles seed with ZERO permissions except
    # "owner" (see roles/signals.py) - a school admin configuring this
    # system for real would grant each role a sensible, scoped permission
    # set via the Roles UI; this reproduces that exact configuration so
    # each demo login actually sees something when they sign in, without
    # granting everyone full access ("owner" is the only full-access role,
    # and that's pre-existing platform behavior, not something added here).
    # ------------------------------------------------------------------

    def _grant_role_permissions(self):
        from roles.models import Permission, Role

        def grant(slug, codenames, name=None, description="", is_system_role=True):
            role, _ = Role.objects.get_or_create(
                slug=slug,
                defaults={"name": name or slug.title(), "description": description, "is_system_role": is_system_role},
            )
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            return role

        grant("instructor", [
            "view_student", "view_staff", "view_subject", "view_section", "view_academic_level",
            "view_attendance", "mark_attendance", "view_attendance_reports",
            "view_timetable",
            "view_examinations", "manage_examinations", "enter_marks",
            "view_course_content", "manage_course_content", "create_assignment", "grade_assignment",
            "view_dashboard",
        ])
        grant("staff", [
            "view_student", "add_student", "change_student",
            "view_family", "add_family", "change_family",
            "view_staff",
            "view_academic_level", "view_section", "view_subject",
            "view_attendance", "view_attendance_reports",
            "view_timetable",
            "view_examinations", "view_exam_reports",
            "view_dashboard",
        ])
        grant("student", ["view_own_fees", "pay_own_fees", "submit_assignment", "view_course_content"])
        grant("parent", [
            "view_own_children", "view_child_attendance", "view_child_timetable",
            "view_child_results", "view_child_fees", "pay_child_fees",
        ])
        self.principal_role = grant(
            "principal", [
                "view_student", "add_student", "change_student",
                "view_staff", "add_staff", "change_staff",
                "view_family",
                "view_program", "view_academic_level", "view_section", "view_subject", "view_subject_assignment",
                "view_course_content", "manage_course_content",
                "view_attendance", "view_attendance_reports", "view_staff_attendance",
                "view_timetable", "view_timetable_reports",
                "view_examinations", "manage_examinations", "publish_results", "view_results",
                "manage_grading", "view_exam_reports",
                "view_fees", "view_financial_reports",
                "view_dashboard", "view_audit_log",
            ],
            name="Principal", description="Academic leadership - broad oversight, not system administration.",
            is_system_role=False,
        )
        self.accountant_role = grant(
            "accountant", [
                "view_student",
                "view_fees", "manage_fee_structures", "collect_payments", "view_financial_reports",
                "view_dashboard",
            ],
            name="Accountant", description="Finance/accounts office.", is_system_role=False,
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def _create_demo_accounts_and_structure(self, organization):
        # Everything below runs inside one open transaction (see handle()),
        # so these are the only progress signals visible before the final
        # summary - without them, a large --students run goes completely
        # silent for its entire duration (nothing commits, so nothing is
        # even queryable from another connection, until the whole thing
        # finishes) and can look hung even though it's actively working.
        self._announce("Creating institution profile...")
        self._create_institution_profile(organization)
        self._announce("Creating academic structure (levels, sections, subjects)...")
        self._create_academic_structure()
        self._announce("Creating staff and instructors...")
        self._create_staff_and_instructors()
        self._announce("Creating subject assignments...")
        self._create_subject_assignments()
        self._announce(f"Creating {self.num_students} students and their families...")
        self._create_students_and_families()
        self._announce("Creating timetable...")
        self._create_timetable()
        self._announce("Creating attendance history (~2 months)...")
        self._create_attendance_history()
        self._announce("Creating examinations, schedules, marks, and results...")
        self._create_examinations()
        self._announce("Creating fee structures and payments...")
        self._create_fees_and_payments()
        self._announce("Creating course content...")
        self._create_course_content()
        self._announce("Creating notification outbox samples...")
        self._create_notification_outbox_samples()
        self._create_audit_log_samples()
        self._create_administration_accounts()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unique_username(self, prefix, index):
        return f"demo_{prefix}_{index:04d}_{self.seed}"

    def _create_user_and_profile(self, *, username, email, first_name, last_name, gender, dob, phone, address, role_slug=None):
        from accounts.models import User
        from profiles.models import Profile
        from roles.models import Role, UserRole

        # Every demo account intentionally shares the exact same documented
        # DEMO_PASSWORD - so the (deliberately expensive, by design) password
        # hash only needs to be computed ONCE for the whole command (see
        # handle()), not once per user. With ~1,000+ accounts at the default
        # --students 500, re-hashing per user turned out to be the dominant
        # cost of the entire run (Django's hasher is intentionally slow to
        # resist brute-forcing - a real per-user cost with unique passwords,
        # but pure waste when every account's password is identical anyway).
        user = User(username=username, email=User.objects.normalize_email(email) if email else email, password=self._demo_password_hash)
        user.save()
        profile = Profile.objects.create(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=dob,
            blood_group=self.rng.choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
            phone=phone,
            address=address,
            local_username=username,
        )
        if role_slug:
            role = Role.objects.get(slug=role_slug)
            UserRole.objects.create(user=user, role=role)
        return user, profile

    def _random_name(self, gender):
        first = self.rng.choice(self.MALE_FIRST_NAMES if gender == "male" else self.FEMALE_FIRST_NAMES)
        return first, self.rng.choice(self.SURNAMES)

    def _random_address(self):
        return f"{self.rng.randint(1, 200)} {self.rng.choice(self.STREETS)}, {self.rng.choice(self.CITIES)}"

    def _random_phone(self):
        return f"+91-9{self.rng.randint(100000000, 999999999)}"

    # ------------------------------------------------------------------
    # Institution profile
    # ------------------------------------------------------------------

    def _create_institution_profile(self, organization):
        from profiles.models import InstitutionProfile

        InstitutionProfile.objects.create(
            organization_id=organization.id,
            tagline="Nurturing Curiosity, Building Character",
            mission="To provide a supportive, inclusive learning environment where every student can thrive academically and personally.",
            vision="To be a model institution recognised for academic excellence and holistic development.",
            about=f"{self.ORG_NAME} is a demo K-10 institution created for manual UI testing. All data is synthetic.",
            established_date=date(1998, 6, 1),
            website=f"https://www.{self.EMAIL_DOMAIN}",
        )

    # ------------------------------------------------------------------
    # Academic structure
    # ------------------------------------------------------------------

    def _create_academic_structure(self):
        from academics.models import AcademicLevel, Program, Section, Subject

        program = Program.objects.create(
            name="K-10 General Program", code="GVS-K10",
            description="General K-10 curriculum.",
        )
        self.program = program
        self.levels = {}       # grade_number -> AcademicLevel
        self.sections_by_level = {}  # grade_number -> [Section, ...]
        self.all_sections = []
        self.subjects_by_level = {}  # grade_number -> [Subject, ...] (core subjects only)

        for grade in range(1, self.GRADE_COUNT + 1):
            level = AcademicLevel.objects.create(program=program, name=f"Grade {grade}", order=grade)
            self.levels[grade] = level

            sections = []
            for letter in self.SECTION_LETTERS[: self.SECTIONS_FOR_GRADE[grade]]:
                section = Section.objects.create(level=level, name=letter, capacity=30)
                sections.append(section)
                self.all_sections.append(section)
                self.created["sections"] += 1
            self.sections_by_level[grade] = sections

            level_subjects = []
            for prefix, name in self.CORE_SUBJECTS:
                subject = Subject.objects.create(
                    level=level,
                    name=name,
                    code=f"{prefix}{grade:02d}",
                    credits=Decimal("4.0") if name in ("Mathematics", "Science") else Decimal("3.0"),
                    is_elective=False,
                    description=f"{name} curriculum for Grade {grade}.",
                )
                level_subjects.append(subject)
                self.created["subjects"] += 1
            self.subjects_by_level[grade] = level_subjects

    # ------------------------------------------------------------------
    # Staff & instructors
    # ------------------------------------------------------------------

    def _create_staff_and_instructors(self):
        from staff.models import Instructor, StaffMember

        self.instructors_by_subject_area = {name: [] for _, name in self.CORE_SUBJECTS}
        self.all_instructors = []
        self.all_staff = []

        num_teachers = 35
        num_non_teaching = 15

        for i in range(num_teachers):
            gender = self.rng.choice(["male", "female"])
            first, last = self._random_name(gender)
            username = self._unique_username("teacher", i)
            is_demo_login = i == 0
            email = f"teacher@{self.EMAIL_DOMAIN}" if is_demo_login else f"{username}@{self.EMAIL_DOMAIN}"

            user, profile = self._create_user_and_profile(
                username=username, email=email, first_name=first, last_name=last, gender=gender,
                dob=date(self.BASE_YEAR - self.rng.randint(28, 58), self.rng.randint(1, 12), self.rng.randint(1, 28)),
                phone=self._random_phone(), address=self._random_address(), role_slug="instructor",
            )
            subject_area = self.CORE_SUBJECTS[i % len(self.CORE_SUBJECTS)][1]
            staff = StaffMember.objects.create(
                profile=profile, employee_id=f"GVS-T-{i + 1:04d}", designation="Teacher",
                department=subject_area, joining_date=date(self.BASE_YEAR - self.rng.randint(1, 15), 6, 1),
                qualification=f"{self.rng.choice(['B.Ed.', 'M.Ed.', 'M.A.', 'M.Sc.'])} in {subject_area}",
                experience_years=self.rng.randint(1, 20),
            )
            instructor = Instructor.objects.create(
                staff_member=staff, specialization=subject_area,
                license_number=f"LIC-{self.rng.randint(100000, 999999)}",
                bio=f"Experienced {subject_area} educator at {self.ORG_NAME}.",
            )
            self.instructors_by_subject_area[subject_area].append(instructor)
            self.all_instructors.append(instructor)
            self.all_staff.append(staff)
            self.created["instructors"] += 1
            self.created["staff"] += 1
            if is_demo_login:
                self.demo_teacher_instructor = instructor
                self.demo_logins.append(("Teacher", email, self.DEMO_PASSWORD))

        for i in range(num_non_teaching):
            gender = self.rng.choice(["male", "female"])
            first, last = self._random_name(gender)
            username = self._unique_username("staff", i)
            is_demo_staff_login = i == 0
            is_demo_accountant_login = i == 1
            if is_demo_staff_login:
                email = f"staff@{self.EMAIL_DOMAIN}"
            elif is_demo_accountant_login:
                email = f"accountant@{self.EMAIL_DOMAIN}"
            else:
                email = f"{username}@{self.EMAIL_DOMAIN}"

            role_slug = "accountant" if is_demo_accountant_login else "staff"
            department = "Finance" if is_demo_accountant_login else self.rng.choice(self.DEPARTMENTS)
            designation = "Accountant" if is_demo_accountant_login else self.rng.choice(
                ["Administrative Assistant", "Librarian", "Registrar", "Front Office Executive", "Lab Assistant"]
            )

            user, profile = self._create_user_and_profile(
                username=username, email=email, first_name=first, last_name=last, gender=gender,
                dob=date(self.BASE_YEAR - self.rng.randint(25, 55), self.rng.randint(1, 12), self.rng.randint(1, 28)),
                phone=self._random_phone(), address=self._random_address(), role_slug=role_slug,
            )
            # profiles.signals.create_profile_for_role already auto-creates a
            # stub StaffMember as soon as the UserRole(role_slug="staff") above
            # is saved (it does this for "staff"/"owner" specifically - see
            # that signal) - update_or_create (not .create()) avoids colliding
            # with that stub while still setting our own richer field values.
            staff, _ = StaffMember.objects.update_or_create(
                profile=profile,
                defaults={
                    "employee_id": f"GVS-S-{i + 1:04d}", "designation": designation,
                    "department": department, "joining_date": date(self.BASE_YEAR - self.rng.randint(1, 10), 6, 1),
                    "qualification": self.rng.choice(["B.Com.", "B.A.", "M.Com.", "B.Sc."]),
                    "experience_years": self.rng.randint(1, 15),
                },
            )
            self.all_staff.append(staff)
            self.created["staff"] += 1
            if is_demo_accountant_login:
                self.demo_accountant_staff = staff
                self.demo_logins.append(("Accountant", email, self.DEMO_PASSWORD))
            elif is_demo_staff_login:
                self.demo_staff_member = staff
                self.demo_logins.append(("Staff (registrar)", email, self.DEMO_PASSWORD))

    # ------------------------------------------------------------------
    # Subject assignments (who teaches what, where)
    # ------------------------------------------------------------------

    def _create_subject_assignments(self):
        from academics.models import SubjectAssignment

        self.assignment_by_section_subject = {}
        for section in self.all_sections:
            grade = section.level.order
            for subject in self.subjects_by_level[grade]:
                pool = self.instructors_by_subject_area[subject.name]
                instructor = pool[self.rng.randrange(len(pool))]
                assignment = SubjectAssignment.objects.create(section=section, subject=subject, instructor=instructor)
                self.assignment_by_section_subject[(section.id, subject.id)] = assignment
                self.created["subject_assignments"] += 1

    # ------------------------------------------------------------------
    # Students & families
    # ------------------------------------------------------------------

    def _create_students_and_families(self):
        from families.models import Parent, StudentParentRelation
        from students.models import AcademicHistory, PromotionRecord, Student, StudentLevel

        self.all_students = []
        self.students_by_section = {s.id: [] for s in self.all_sections}
        self.student_performance = {}  # student.id -> "high" | "average" | "borderline" | "failing"
        performance_bands = (
            ["high"] * 15 + ["average"] * 55 + ["borderline"] * 20 + ["failing"] * 10
        )  # 100-weighted distribution

        parent_pool = []  # list of Parent objects, reused across siblings
        family_last_names_used = {}

        is_demo_student_login_assigned = False
        is_demo_parent_login_assigned = False

        for i in range(self.num_students):
            section = self.all_sections[i % len(self.all_sections)]
            grade = section.level.order
            gender = self.rng.choice(["male", "female"])
            first, last = self._random_name(gender)
            age = grade + 5  # Grade 1 -> age ~6, Grade 10 -> age ~15
            dob = date(self.BASE_YEAR - age, self.rng.randint(1, 12), self.rng.randint(1, 28))

            status_roll = self.rng.random()
            if status_roll < 0.03 and grade == self.GRADE_COUNT:
                status = "graduated"
            elif status_roll < 0.05:
                status = "inactive"
            else:
                status = "active"

            username = self._unique_username("student", i)
            is_demo_login = (not is_demo_student_login_assigned) and status == "active"
            email = f"student@{self.EMAIL_DOMAIN}" if is_demo_login else f"{username}@{self.EMAIL_DOMAIN}"

            user, profile = self._create_user_and_profile(
                username=username, email=email, first_name=first, last_name=last, gender=gender,
                dob=dob, phone="", address=self._random_address(), role_slug="student",
            )
            student = Student.objects.create(
                profile=profile,
                enrollment_id=f"GVS-{self.current_year}-{i + 1:04d}",
                admission_date=date(self.BASE_YEAR - self.rng.randint(0, age - 5), 6, self.rng.randint(1, 28)),
                status=status,
            )
            self.all_students.append(student)
            self.students_by_section[section.id].append(student)
            self.student_performance[student.id] = self.rng.choice(performance_bands)
            self.created["students"] += 1

            if is_demo_login:
                is_demo_student_login_assigned = True
                self.demo_student = student
                self.demo_logins.append(("Student", email, self.DEMO_PASSWORD))

            StudentLevel.objects.create(
                student=student, level=section.level, section=section,
                academic_year=self.current_year, is_current=(status == "active"),
            )
            if self.previous_year and grade > 1:
                prev_level = self.levels[grade - 1]
                prev_section = self.sections_by_level[grade - 1][i % len(self.sections_by_level[grade - 1])]
                StudentLevel.objects.create(
                    student=student, level=prev_level, section=prev_section,
                    academic_year=self.previous_year, is_current=False,
                )
                PromotionRecord.objects.create(
                    student=student, action="graduated" if status == "graduated" else "promoted",
                    source_academic_year=self.previous_year, target_academic_year=self.current_year,
                    source_level=prev_level, target_level=section.level,
                    source_section=prev_section, target_section=section,
                    reason="Annual promotion." if status != "graduated" else "Completed Grade 10.",
                )
                self.created["promotion_records"] += 1

            if self.rng.random() < 0.15:
                AcademicHistory.objects.create(
                    student=student, previous_school=f"{self.rng.choice(self.CITIES)} Public School",
                    last_grade_passed=f"Grade {max(1, grade - 1)}",
                    completion_year=self.BASE_YEAR - self.rng.randint(1, 3),
                    remarks="Transferred due to relocation.",
                )

            # --- family / parent linkage ---------------------------------
            reuse_existing_family = self.rng.random() < 0.25 and family_last_names_used.get(last)
            if reuse_existing_family:
                family_parents = family_last_names_used[last]
            else:
                family_parents = []
                father_first, _ = self._random_name("male")
                mother_first, _ = self._random_name("female")
                for parent_first, parent_gender, relation in (
                    (father_first, "male", "father"), (mother_first, "female", "mother")
                ):
                    if relation == "mother" and self.rng.random() < 0.15:
                        continue  # single-parent / single-guardian family
                    parent_username = self._unique_username(f"parent_{relation}", i)
                    is_parent_demo_login = (not is_demo_parent_login_assigned) and relation == "father" and status == "active"
                    parent_email = (
                        f"parent@{self.EMAIL_DOMAIN}" if is_parent_demo_login
                        else f"{parent_username}@{self.EMAIL_DOMAIN}"
                    )
                    _, parent_profile = self._create_user_and_profile(
                        username=parent_username, email=parent_email, first_name=parent_first, last_name=last,
                        gender=parent_gender, dob=date(self.BASE_YEAR - self.rng.randint(32, 55), 1, 1),
                        phone=self._random_phone(), address=profile.address, role_slug="parent",
                    )
                    parent = Parent.objects.create(
                        profile=parent_profile, occupation=self.rng.choice(self.JOB_TITLES),
                        office_address=self._random_address(),
                        income_level=self.rng.choice(["low", "middle", "high"]),
                    )
                    family_parents.append((parent, relation))
                    self.created["parents"] += 1
                    if is_parent_demo_login:
                        is_demo_parent_login_assigned = True
                        self.demo_parent = parent
                        self.demo_logins.append(("Parent", parent_email, self.DEMO_PASSWORD))
                family_last_names_used[last] = family_parents
                self.created["families"] += 1

            for idx, (parent, relation) in enumerate(family_parents):
                StudentParentRelation.objects.create(
                    student=student, parent=parent, relation_type=relation,
                    is_primary_contact=(idx == 0), can_pickup=True,
                )

        # Make sure the demo parent/student logins are actually linked to
        # each other, regardless of where chance placed them, so logging
        # in as "parent@..." shows "student@..."'s real data in the UI.
        if hasattr(self, "demo_parent") and hasattr(self, "demo_student"):
            if not StudentParentRelation.objects.filter(parent=self.demo_parent, student=self.demo_student).exists():
                StudentParentRelation.objects.get_or_create(
                    student=self.demo_student, parent=self.demo_parent,
                    defaults={"relation_type": "guardian", "is_primary_contact": True, "can_pickup": True},
                )

    # ------------------------------------------------------------------
    # Timetable
    # ------------------------------------------------------------------

    def _create_timetable(self):
        from timetable.models import Period, Room, TimetableEntry

        self.periods = []
        period_slots = [
            ("Period 1", time(8, 0), time(8, 45)), ("Period 2", time(8, 45), time(9, 30)),
            ("Period 3", time(9, 30), time(10, 15)), ("Short Break", time(10, 15), time(10, 30)),
            ("Period 4", time(10, 30), time(11, 15)), ("Period 5", time(11, 15), time(12, 0)),
            ("Lunch Break", time(12, 0), time(12, 40)), ("Period 6", time(12, 40), time(13, 25)),
            ("Period 7", time(13, 25), time(14, 10)),
        ]
        for order, (name, start, end) in enumerate(period_slots, start=1):
            is_break = "Break" in name
            period = Period.objects.create(
                academic_year=self.current_year, name=name, order=order,
                start_time=start, end_time=end, is_break=is_break,
            )
            self.periods.append(period)
            self.created["periods"] += 1
        self.teaching_periods = [p for p in self.periods if not p.is_break]

        self.rooms_by_section = {}
        for i, section in enumerate(self.all_sections):
            room = Room.objects.create(name=f"Room {101 + i}", capacity=35)
            self.rooms_by_section[section.id] = room
            self.created["rooms"] += 1
        self.science_labs = [Room.objects.create(name=f"Science Lab {i + 1}", capacity=30) for i in range(2)]
        self.created["rooms"] += len(self.science_labs)

        teacher_busy = set()  # (day, period_id, instructor_id)
        room_busy = set()     # (day, period_id, room_id)

        for section in self.all_sections:
            grade = section.level.order
            subjects = self.subjects_by_level[grade]
            home_room = self.rooms_by_section[section.id]

            for day in range(5):  # Monday..Friday
                available_periods = list(self.teaching_periods)
                self.rng.shuffle(available_periods)
                slot_index = 0
                for subject in subjects:
                    assignment = self.assignment_by_section_subject[(section.id, subject.id)]
                    instructor = assignment.instructor
                    room = self.rng.choice(self.science_labs) if subject.name == "Science" else home_room

                    placed = False
                    while slot_index < len(available_periods):
                        period = available_periods[slot_index]
                        slot_index += 1
                        key_teacher = (day, period.id, instructor.id if instructor else None)
                        key_room = (day, period.id, room.id)
                        if instructor and key_teacher in teacher_busy:
                            continue
                        if key_room in room_busy:
                            continue
                        TimetableEntry.objects.create(
                            academic_year=self.current_year, section=section, subject=subject,
                            instructor=instructor, room=room, day_of_week=day, period=period,
                        )
                        if instructor:
                            teacher_busy.add(key_teacher)
                        room_busy.add(key_room)
                        self.created["timetable_entries"] += 1
                        placed = True
                        break
                    if not placed:
                        continue  # ran out of free periods this day for this section - acceptable, skip

    # ------------------------------------------------------------------
    # Attendance (~2 months of school days, deterministic patterns)
    # ------------------------------------------------------------------

    def _create_attendance_history(self):
        from attendance.models import AttendanceSession, StudentAttendance

        end_date = date(self.BASE_YEAR, 3, 31)
        start_date = end_date - timedelta(days=62)  # ~2 months back, weekends excluded below
        school_days = []
        d = start_date
        while d <= end_date:
            if d.weekday() < 5:
                school_days.append(d)
            d += timedelta(days=1)

        # Deterministic per-student attendance "profile" - distinct from
        # exam performance, so the two dashboards show independently
        # varied (not perfectly correlated) pictures.
        profile_pool = (
            ["mostly_present"] * 60 + ["occasional_absence"] * 20
            + ["frequent_late"] * 12 + ["occasional_excused"] * 8
        )
        student_attendance_profile = {s.id: self.rng.choice(profile_pool) for s in self.all_students}

        recorder = self.all_staff[0]

        for section in self.all_sections:
            roster = [s for s in self.students_by_section[section.id] if s.status == "active"]
            if not roster:
                continue
            for day in school_days:
                session = AttendanceSession.objects.create(
                    section=section, academic_year=self.current_year, date=day, recorded_by=recorder,
                )
                self.created["attendance_sessions"] += 1
                records = []
                for student in roster:
                    profile = student_attendance_profile[student.id]
                    roll = self.rng.random()
                    if profile == "mostly_present":
                        status = "present" if roll < 0.94 else self.rng.choice(["absent", "late"])
                    elif profile == "occasional_absence":
                        status = "absent" if roll < 0.12 else "present"
                    elif profile == "frequent_late":
                        status = "late" if roll < 0.30 else "present"
                    else:  # occasional_excused
                        status = "leave" if roll < 0.08 else "present"
                    records.append(StudentAttendance(session=session, student=student, status=status, recorded_by=recorder))
                StudentAttendance.objects.bulk_create(records)
                self.created["attendance_records"] += len(records)

    # ------------------------------------------------------------------
    # Examinations
    # ------------------------------------------------------------------

    PERFORMANCE_BANDS = {
        "high": (88, 97), "average": (62, 78), "borderline": (41, 52), "failing": (18, 36),
    }

    def _create_examinations(self):
        """
        Creates 5 examinations across the current academic year. The first
        4 are fully marked and published (via the pure, side-effect-free
        calculate_student_examination_result() helper - see note below);
        the 5th ("Final Examination") is left with only partial marks and
        UNPUBLISHED, to exercise that state in the UI.

        Deliberately does NOT call examinations.services.publish_examination()
        directly: that function (correctly) also queues a real, async
        result-published email via notifications.services.queue_email()
        for every student/parent - exactly the behavior wanted for a real
        publish, but not for a bulk data seeder, where it would attempt a
        real Celery dispatch (and, in a misconfigured environment, a real
        send) for ~500+ synthetic addresses. The task's own instructions
        explicitly anticipate this ("seed the relevant outbox state without
        sending external emails" - see _create_notification_outbox_samples).
        The actual grading/aggregation logic IS reused as-is.
        """
        from examinations.models import ExamSchedule, ExamType, Examination, ExamMark, ExamResult, GradeBoundary
        from examinations.services import calculate_student_examination_result

        for academic_year in self.years:
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("90"), max_percentage=Decimal("100"), grade_label="A+", grade_point=Decimal("4.0"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("80"), max_percentage=Decimal("89.99"), grade_label="A", grade_point=Decimal("3.7"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("70"), max_percentage=Decimal("79.99"), grade_label="B+", grade_point=Decimal("3.3"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("60"), max_percentage=Decimal("69.99"), grade_label="B", grade_point=Decimal("3.0"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("50"), max_percentage=Decimal("59.99"), grade_label="C", grade_point=Decimal("2.5"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("40"), max_percentage=Decimal("49.99"), grade_label="D", grade_point=Decimal("2.0"))
            GradeBoundary.objects.create(academic_year=academic_year, min_percentage=Decimal("0"), max_percentage=Decimal("39.99"), grade_label="F", grade_point=Decimal("0.0"))

        exam_plan = [
            ("Unit Test 1", date(self.BASE_YEAR - 1, 8, 10), date(self.BASE_YEAR - 1, 8, 14), True),
            ("Mid-Term Examination", date(self.BASE_YEAR - 1, 10, 5), date(self.BASE_YEAR - 1, 10, 12), True),
            ("Unit Test 2", date(self.BASE_YEAR - 1, 12, 1), date(self.BASE_YEAR - 1, 12, 5), True),
            ("Half-Yearly Examination", date(self.BASE_YEAR, 1, 12), date(self.BASE_YEAR, 1, 19), True),
            ("Final Examination", date(self.BASE_YEAR, 3, 2), date(self.BASE_YEAR, 3, 10), False),
        ]

        for order, (name, start_date, end_date, should_publish) in enumerate(exam_plan, start=1):
            exam_type = ExamType.objects.create(name=name, order=order)
            examination = Examination.objects.create(
                academic_year=self.current_year, name=f"{name} {self.current_year}",
                exam_type=exam_type, start_date=start_date, end_date=end_date,
            )
            self.created["examinations"] += 1

            schedules_by_section_subject = {}
            for section in self.all_sections:
                grade = section.level.order
                for slot, subject in enumerate(self.subjects_by_level[grade]):
                    schedule = ExamSchedule.objects.create(
                        examination=examination, academic_year=self.current_year,
                        subject=subject, section=section,
                        date=start_date + timedelta(days=slot),
                        start_time=time(9, 0), end_time=time(11, 0),
                        max_marks=Decimal("100"), pass_marks=Decimal("40"),
                    )
                    schedules_by_section_subject[(section.id, subject.id)] = schedule
                    self.created["exam_schedules"] += 1

            for section in self.all_sections:
                grade = section.level.order
                roster = [s for s in self.students_by_section[section.id] if s.status == "active"]
                for subject in self.subjects_by_level[grade]:
                    schedule = schedules_by_section_subject[(section.id, subject.id)]
                    if not should_publish and self.rng.random() < 0.4:
                        continue  # Final Examination: ~40% of schedules have no marks yet (in progress)
                    marks_to_create = []
                    for student in roster:
                        if self.rng.random() < 0.03:
                            marks_to_create.append(ExamMark(exam_schedule=schedule, student=student, is_absent=True, attendance="absent", entered_by=self.demo_teacher_instructor.staff_member))
                            continue
                        band = self.PERFORMANCE_BANDS[self.student_performance[student.id]]
                        pct = self.rng.uniform(*band)
                        marks_obtained = Decimal(str(round(pct, 2)))
                        marks_to_create.append(ExamMark(exam_schedule=schedule, student=student, marks_obtained=marks_obtained, entered_by=self.demo_teacher_instructor.staff_member))
                    ExamMark.objects.bulk_create(marks_to_create)
                    self.created["exam_marks"] += len(marks_to_create)

            if order <= 2:
                ExamSchedule.objects.filter(examination=examination).update(is_locked=True, locked_at=timezone.now())

            if should_publish:
                participating_student_ids = set(
                    ExamMark.objects.filter(exam_schedule__examination=examination).values_list("student_id", flat=True).distinct()
                )
                from students.models import Student

                for student in Student.objects.filter(id__in=participating_student_ids):
                    result = calculate_student_examination_result(examination, student)
                    if result is None:
                        continue
                    ExamResult.objects.create(
                        examination=examination, student=student, academic_year=examination.academic_year,
                        total_marks_obtained=result["total_marks_obtained"], total_max_marks=result["total_max_marks"],
                        percentage=result["percentage"], overall_grade=result["overall_grade"],
                        is_pass=result["is_pass"], subject_breakdown=result["subject_breakdown"],
                    )
                    self.created["exam_results"] += 1
                examination.is_published = True
                examination.published_at = timezone.now()
                examination.save(update_fields=["is_published", "published_at", "updated_at"])

    # ------------------------------------------------------------------
    # Fees & payments
    # ------------------------------------------------------------------

    def _create_fees_and_payments(self):
        """Reuses fees.services.assign_student_fee()/record_payment() directly
        (both contain real allocation/validation logic worth not re-deriving),
        with a different payment scenario per student (deterministic on index)."""
        from fees.models import FeeHead
        from fees.services import assign_student_fee, record_payment

        fee_heads_data = [
            ("Tuition Fee", Decimal("15000")), ("Transport Fee", Decimal("3000")),
            ("Examination Fee", Decimal("1200")), ("Library Fee", Decimal("500")),
        ]
        fee_heads = []
        for name, amount in fee_heads_data:
            head = FeeHead.objects.create(name=name, description=f"{name} for {self.current_year}.")
            fee_heads.append((head, amount))
            self.created["fee_structures"] += 1

        due_date = date(self.BASE_YEAR, 4, 15)  # academic-year-end due date; BASE_YEAR context makes some already overdue
        recorder = self.demo_accountant_staff

        scenario_pool = ["fully_paid"] * 40 + ["partially_paid"] * 30 + ["overdue"] * 20 + ["unpaid"] * 10

        for i, student in enumerate(self.all_students):
            if student.status != "active":
                continue
            scenario = scenario_pool[i % len(scenario_pool)]
            student_fees = []
            for head, amount in fee_heads:
                sf = assign_student_fee(
                    student=student, fee_head=head, academic_year=self.current_year,
                    amount_due=amount, due_date=due_date if scenario != "overdue" else date(self.BASE_YEAR, 1, 15),
                )
                student_fees.append(sf)
                self.created["student_fees"] += 1

            total_due = sum(sf.amount_due for sf in student_fees)
            if scenario == "fully_paid":
                record_payment(
                    student=student, amount=total_due, method=self.rng.choice(["cash", "upi", "bank_transfer"]),
                    allocations=[{"student_fee_id": sf.id, "amount": sf.amount_due} for sf in student_fees],
                    recorded_by=recorder, reference_note="Full payment for the year.",
                )
                self.created["payments"] += 1
            elif scenario == "partially_paid":
                partial_fee = student_fees[0]
                partial_amount = (partial_fee.amount_due / 2).quantize(Decimal("1."))
                record_payment(
                    student=student, amount=partial_amount, method=self.rng.choice(["cash", "upi"]),
                    allocations=[{"student_fee_id": partial_fee.id, "amount": partial_amount}],
                    recorded_by=recorder, reference_note="Partial payment - installment 1.",
                )
                self.created["payments"] += 1
            # "overdue" and "unpaid" scenarios: no payment at all (overdue differs via its earlier due_date, already past)

    # ------------------------------------------------------------------
    # Course content
    # ------------------------------------------------------------------

    def _create_course_content(self):
        from course_content.models import Assignment, AssignmentSubmission, CourseContent

        topics = [
            "Introduction to Fractions", "The Water Cycle", "Grammar Essentials",
            "Our Solar System", "Map Reading Skills", "Basic Algebra", "Plant Life Cycles",
            "Reading Comprehension Strategies", "Indian Freedom Movement", "States of Matter",
        ]
        for i, topic in enumerate(topics):
            creator = self.all_staff[i % len(self.all_staff)]
            content = CourseContent.objects.create(
                title=topic, description=f"Study notes: {topic}.", content_type="note",
                created_by=creator, is_published=True, publish_date=timezone.now() - timedelta(days=i * 3),
                is_pinned=(i == 0),
            )
            grade = (i % self.GRADE_COUNT) + 1
            content.target_levels.add(self.levels[grade])
            self.created["course_content"] += 1

        for i in range(8):
            creator = self.demo_teacher_instructor.staff_member
            grade = (i % self.GRADE_COUNT) + 1
            subject = self.subjects_by_level[grade][i % len(self.subjects_by_level[grade])]
            due = timezone.now() + timedelta(days=self.rng.randint(-10, 14))
            content = CourseContent.objects.create(
                title=f"Assignment: {subject.name} Worksheet {i + 1}",
                description=f"Complete the {subject.name} worksheet and submit before the due date.",
                content_type="assignment", created_by=creator, is_published=True,
                publish_date=timezone.now() - timedelta(days=5),
            )
            content.target_levels.add(self.levels[grade])
            content.target_subjects.add(subject)
            self.created["course_content"] += 1
            assignment = Assignment.objects.create(
                content=content, due_date=due, total_points=Decimal("100"),
                submission_type="text", instructions=f"Answer all questions on {subject.name}.",
            )
            self.created["assignments"] += 1

            roster = []
            for section in self.sections_by_level[grade]:
                roster.extend(self.students_by_section[section.id])
            for student in roster[:10]:
                if self.rng.random() < 0.7:
                    submitted_at = due - timedelta(days=self.rng.randint(0, 3))
                    graded = self.rng.random() < 0.6
                    AssignmentSubmission.objects.create(
                        assignment=assignment, student=student, submitted_at=submitted_at,
                        submission_text="Submitted answers.", status="graded" if graded else "submitted",
                        score=Decimal(str(self.rng.randint(60, 100))) if graded else None,
                        feedback="Good work." if graded else "",
                        graded_by=creator if graded else None,
                        graded_at=submitted_at + timedelta(days=2) if graded else None,
                    )
                    self.created["submissions"] += 1

    # ------------------------------------------------------------------
    # Notification outbox samples (direct model creation - NEVER via
    # queue_email(), so no real Celery dispatch/email send is ever
    # attempted by running this command).
    # ------------------------------------------------------------------

    def _create_notification_outbox_samples(self):
        from notifications.models import EmailOutboxEvent

        samples = [
            ("sent", "Your examination results are available", 0, "", ""),
            ("sent", "Fee payment received - receipt enclosed", 0, "", ""),
            ("pending", "Your examination results are available", 0, "", ""),
            ("retrying", "Fee due reminder", 1, "temporary", "Connection timed out while contacting the mail server."),
            ("retrying", "Your examination results are available", 2, "temporary", "Connection refused."),
            ("failed", "Fee due reminder", 3, "temporary", "Connection timed out while contacting the mail server."),
            ("failed", "Welcome to the parent portal", 1, "permanent", "550 No such user here."),
        ]
        demo_emails = [login[1] for login in self.demo_logins] or [f"demo@{self.EMAIL_DOMAIN}"]
        for i, (status, subject, attempts, error_type, last_error) in enumerate(samples):
            EmailOutboxEvent.objects.create(
                to_email=demo_emails[i % len(demo_emails)], subject=subject,
                body=f"{subject} - please log in to the portal for details.",
                status=status, attempts=attempts, error_type=error_type, last_error=last_error,
                sent_at=timezone.now() if status == "sent" else None,
            )
            self.created["outbox_events"] += 1

    # ------------------------------------------------------------------
    # Audit log samples (direct model creation - log_action() is designed
    # around an inbound HTTP request, which a management command doesn't
    # have; the AuditLog model itself is the thing to reuse here).
    # ------------------------------------------------------------------

    def _create_audit_log_samples(self):
        from core.models import AuditLog

        owner_username = self.demo_owner_user.username if hasattr(self, "demo_owner_user") else "demo_owner"
        owner_id = self.demo_owner_user.id if hasattr(self, "demo_owner_user") else None

        sample_actions = [
            ("student_created", "Student", {"enrollment_id": self.all_students[0].enrollment_id}),
            ("staff_created", "StaffMember", {"designation": "Teacher"}),
            ("examination_created", "Examination", {"name": "Final Examination"}),
            ("marks_submitted", "ExamSchedule", {"total_records": 20}),
            ("results_published", "Examination", {"name": "Unit Test 1"}),
            ("fee_created", "FeeHead", {"name": "Tuition Fee"}),
            ("payment_recorded", "Payment", {"method": "cash"}),
        ]
        for action, model_name, changes in sample_actions:
            AuditLog.objects.create(
                actor_id=owner_id, actor_username=owner_username, action=action,
                model_name=model_name, object_id=str(uuid.uuid4()), changes=changes,
                ip_address="127.0.0.1", user_agent="seed_demo_school management command",
            )
            self.created["audit_logs"] += 1

    # ------------------------------------------------------------------
    # Administration accounts (superuser, owner, principal)
    # ------------------------------------------------------------------

    def _create_administration_accounts(self):
        from accounts.models import User
        from roles.models import Role, UserRole

        owner_user, owner_profile = self._create_user_and_profile(
            username=self._unique_username("owner", 0), email=f"owner@{self.EMAIL_DOMAIN}",
            first_name="Meera", last_name="Kulkarni", gender="female",
            dob=date(1978, 4, 12), phone=self._random_phone(), address=self._random_address(),
            role_slug="owner",
        )
        self.demo_owner_user = owner_user
        self.demo_logins.append(("School Administrator (owner)", f"owner@{self.EMAIL_DOMAIN}", self.DEMO_PASSWORD))

        principal_user, principal_profile = self._create_user_and_profile(
            username=self._unique_username("principal", 0), email=f"principal@{self.EMAIL_DOMAIN}",
            first_name="Ravi", last_name="Nambiar", gender="male",
            dob=date(1972, 9, 3), phone=self._random_phone(), address=self._random_address(),
        )
        UserRole.objects.create(user=principal_user, role=self.principal_role)
        self.demo_logins.append(("Principal", f"principal@{self.EMAIL_DOMAIN}", self.DEMO_PASSWORD))

        # Superuser - a cross-tenant Django/admin account, not a tenant
        # end-user, so it deliberately gets no Profile/role in this
        # schema (see _clear_demo_school for how it's still safely
        # removed by exact-username match on --clear).
        if not User.objects.filter(username=self.SUPERUSER_USERNAME).exists():
            User.objects.create_superuser(
                username=self.SUPERUSER_USERNAME, email=f"admin@{self.EMAIL_DOMAIN}", password=self.DEMO_PASSWORD,
            )
        self.demo_logins.append(("Superuser", f"admin@{self.EMAIL_DOMAIN}", self.DEMO_PASSWORD))

    # ------------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------------

    def _print_summary(self):
        self.stdout.write(self.style.SUCCESS("\nDemo school created successfully.\n"))
        self.stdout.write(f"Organization: {self.ORG_NAME}  (schema='{self.SCHEMA_NAME}', domain='{self.DOMAIN}')\n")
        for key, value in self.created.items():
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write("\nDemo login credentials (development only - do not use in production):")
        for role_label, email, password in self.demo_logins:
            self.stdout.write(f"  {role_label:35s} {email:35s} password={password}")
        self.stdout.write(
            self.style.WARNING(
                "\nAll accounts use the IANA-reserved '.test' email domain and a shared, "
                "documented development password - no real email will ever be delivered to them."
            )
        )
