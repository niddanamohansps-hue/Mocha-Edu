"""
Builds a complete, internally-consistent, entirely SYNTHETIC "realistic
Indian school" dataset ("Sunrise Valley Public School") for development,
QA, UI testing, performance testing, and demos - a SEPARATE tenant/command
from seed_demo_school.py (never modified by this file), with its own
schema, domain, and email/account namespace so the two can coexist in the
same database without collision.

Every record is fictional. No real person's name, phone number, email,
address, or government ID is used. Demo accounts use the RFC 2606
IANA-reserved ".test"/".invalid" email domains (guaranteed non-deliverable)
and a documented development-only password. This command never sends real
email/SMS, never calls a payment gateway, and never dispatches a real
Celery task - EmailOutboxEvent rows are written directly (bypassing
notifications.services.queue_email()'s async dispatch) exactly as
seed_demo_school.py already does, and in-app Notification rows are created
via notifications.services.notify_many() (a synchronous, dependency-free
DB write with no Celery/email side effect of its own).

Reuses existing business-logic services wherever one exists - fees.services
(assign_student_fee/record_payment), examinations.services'
calculate_examination_results_bulk() (the bulk result-calculation helper
added in Phase 9G - reused here deliberately: it is already audited,
tested, and exactly the "bulk-load then calculate in Python" shape this
seeder needs for exam results, rather than reinventing it) - instead of
writing directly to models wherever a service already encodes the
authoritative rules.

Deterministic: the same --seed always produces the same logical dataset.
Re-running without --clear against an existing schema of the same name is
rejected (matching seed_demo_school.py's own convention) - clear first for
a fresh, identical-by-seed rebuild.

Usage:
    python manage.py seed_realistic_school
    python manage.py seed_realistic_school --students 600 --seed 20260929
    python manage.py seed_realistic_school --students 150 --academic-years 2
    python manage.py seed_realistic_school --clear
    python manage.py seed_realistic_school --dry-run
"""

import random
import time as time_module
import uuid
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context


class Command(BaseCommand):
    help = (
        "Creates (or clears) a realistic, internally-consistent synthetic "
        "Indian school dataset ('Sunrise Valley Public School') for "
        "development/QA/performance testing. Separate from seed_demo_school."
    )

    SCHEMA_NAME = "sunrisevalley_school"
    DOMAIN = "sunrisevalley-demo.localhost"
    ORG_NAME = "Sunrise Valley Public School"
    # .test/.invalid are IANA-reserved for testing (RFC 2606) - guaranteed
    # to never resolve or deliver mail, regardless of environment config.
    EMAIL_DOMAIN = "example.test"
    EMAIL_DOMAIN_ALT = "example.invalid"
    DEMO_PASSWORD = "Realistic#2026"  # development/demo credential only

    CURRENT_YEAR = 2026  # calendar year the "current" academic year starts in

    # --- Region-correlated name pools (section 8/24: realistic combinations,
    # not independently-random first/last names; hundreds of names total
    # across regions) ------------------------------------------------------
    REGIONS = ["northeast", "bengal", "bihar_up", "delhi_ncr", "odisha_jharkhand", "maharashtra", "south"]
    REGION_WEIGHTS = [0.22, 0.16, 0.14, 0.12, 0.1, 0.12, 0.14]  # school is in Assam -> NE overrepresented

    MALE_NAMES = {
        "northeast": ["Ritwik", "Sanjay", "Debasish", "Angshuman", "Bikash", "Pranjal", "Himangshu",
                      "Dipankar", "Kaustav", "Rajib", "Partha", "Nayan", "Bipul", "Jintu", "Prasanta"],
        "bengal": ["Sayan", "Abhinav", "Souvik", "Rajarshi", "Debjit", "Arko", "Sagnik", "Arindam",
                   "Soumyadeep", "Sudipto", "Avik", "Ritoban", "Rishi", "Suman", "Biswajit"],
        "bihar_up": ["Aditya", "Rahul", "Abhishek", "Saurabh", "Gaurav", "Vivek", "Kunal", "Ankit",
                     "Shubham", "Prakash", "Rajeev", "Mukesh", "Satyendra", "Anuj", "Vishal"],
        "delhi_ncr": ["Arjun", "Vihaan", "Kabir", "Ishaan", "Dev", "Veer", "Ayaan", "Parth", "Rudra",
                      "Shaurya", "Yuvraj", "Lakshya", "Advik", "Ronit", "Keshav"],
        "odisha_jharkhand": ["Subham", "Biswaranjan", "Jagannath", "Rakesh", "Satyajit", "Manoj",
                              "Prasant", "Debashis", "Rabindra", "Soumya", "Bibhuti", "Niranjan"],
        "maharashtra": ["Omkar", "Aniket", "Sankalp", "Siddhesh", "Varun", "Rohan", "Yash", "Atharva",
                         "Swapnil", "Nikhil", "Pratik", "Chaitanya", "Rushikesh", "Mihir"],
        "south": ["Arjun", "Karthik", "Vignesh", "Ganesh", "Pranav", "Sriram", "Hariharan", "Naveen",
                  "Sundar", "Ramesh", "Vijay", "Siddharth", "Aravind", "Dinesh", "Rajan"],
    }
    FEMALE_NAMES = {
        "northeast": ["Priyanka", "Madhurima", "Rituparna", "Deepanjali", "Mrinalini", "Barasha",
                      "Nandini", "Pallabi", "Hiya", "Juri", "Lakhi", "Mousumi", "Pranamika", "Rumi"],
        "bengal": ["Ananya", "Srabanti", "Debolina", "Riya", "Payel", "Suchana", "Ishita", "Mahasweta",
                   "Trisha", "Antara", "Nandita", "Sreemoyee", "Debarati", "Piyali"],
        "bihar_up": ["Anushka", "Kritika", "Shreya", "Priya", "Neha", "Pooja", "Swati", "Ritu",
                     "Shalini", "Garima", "Vandana", "Nidhi", "Anjali", "Rekha"],
        "delhi_ncr": ["Diya", "Aadhya", "Kiara", "Myra", "Ira", "Navya", "Siya", "Vanya", "Prisha",
                      "Anika", "Avni", "Zara", "Pari", "Saanvi"],
        "odisha_jharkhand": ["Subhashree", "Jyotirmayee", "Swagatika", "Priyadarshini", "Manisha",
                              "Rashmita", "Debjani", "Anwesha", "Ipsita", "Rajalaxmi"],
        "maharashtra": ["Sanika", "Shravani", "Mrunmayee", "Anushka", "Siddhi", "Pooja", "Gauri",
                         "Rutuja", "Sayali", "Prajakta", "Vaishnavi", "Manasi"],
        "south": ["Kavya", "Ananya", "Divya", "Lakshmi", "Meenakshi", "Sowmya", "Nithya", "Pavithra",
                  "Deepika", "Swathi", "Revathi", "Anitha", "Keerthana"],
    }
    SURNAMES = {
        "northeast": ["Das", "Bora", "Choudhury", "Dutta", "Sharma", "Kalita", "Baruah", "Sarma",
                      "Gogoi", "Hazarika", "Saikia", "Deka"],
        "bengal": ["Das", "Dutta", "Chatterjee", "Bose", "Mukherjee", "Ghosh", "Sen", "Banerjee",
                   "Roy", "Chakraborty", "Bhattacharya"],
        "bihar_up": ["Singh", "Kumar", "Mishra", "Pandey", "Tiwari", "Sinha", "Verma", "Gupta",
                     "Yadav", "Prasad", "Chaudhary"],
        "delhi_ncr": ["Sharma", "Kapoor", "Malhotra", "Khanna", "Chawla", "Bhatia", "Mehta", "Arora",
                      "Gupta", "Bansal"],
        "odisha_jharkhand": ["Patra", "Mohanty", "Behera", "Nayak", "Sahoo", "Pradhan", "Panda",
                              "Das", "Mahato", "Hembram"],
        "maharashtra": ["Patil", "Deshmukh", "Joshi", "Kulkarni", "Pawar", "Jadhav", "Shinde",
                         "More", "Kale", "Chavan"],
        "south": ["Reddy", "Nair", "Iyer", "Rao", "Menon", "Pillai", "Krishnan", "Subramaniam",
                  "Raghavan", "Venkatesh"],
    }

    # --- Address pools, region-correlated (section 12) ---------------------
    ADDRESS_POOLS = {
        "northeast": [("Beltola", "Guwahati", "Assam", "781028"), ("Six Mile", "Guwahati", "Assam", "781022"),
                      ("Dispur", "Guwahati", "Assam", "781006"), ("Zoo Road", "Guwahati", "Assam", "781024"),
                      ("Narengi", "Guwahati", "Assam", "781026")],
        "bengal": [("Salt Lake", "Kolkata", "West Bengal", "700064"), ("Behala", "Kolkata", "West Bengal", "700034"),
                   ("Dum Dum", "Kolkata", "West Bengal", "700028"), ("Garia", "Kolkata", "West Bengal", "700084")],
        "bihar_up": [("Boring Road", "Patna", "Bihar", "800001"), ("Kankarbagh", "Patna", "Bihar", "800020"),
                     ("Gomti Nagar", "Lucknow", "Uttar Pradesh", "226010"), ("Hazratganj", "Lucknow", "Uttar Pradesh", "226001")],
        "delhi_ncr": [("Rohini", "Delhi", "Delhi", "110085"), ("Dwarka", "Delhi", "Delhi", "110075"),
                      ("Sector 62", "Noida", "Uttar Pradesh", "201309"), ("Indirapuram", "Ghaziabad", "Uttar Pradesh", "201014")],
        "odisha_jharkhand": [("Patia", "Bhubaneswar", "Odisha", "751024"), ("Chandrasekharpur", "Bhubaneswar", "Odisha", "751016"),
                              ("Kadma", "Jamshedpur", "Jharkhand", "831005"), ("Lalpur", "Ranchi", "Jharkhand", "834001")],
        "maharashtra": [("Kothrud", "Pune", "Maharashtra", "411038"), ("Andheri East", "Mumbai", "Maharashtra", "400069"),
                         ("Vashi", "Navi Mumbai", "Maharashtra", "400703"), ("Aundh", "Pune", "Maharashtra", "411007")],
        "south": [("Koramangala", "Bangalore", "Karnataka", "560034"), ("Anna Nagar", "Chennai", "Tamil Nadu", "600040"),
                  ("Gachibowli", "Hyderabad", "Telangana", "500032"), ("Kochi", "Ernakulam", "Kerala", "682001")],
    }

    OCCUPATIONS = [
        ("Software Engineer", "middle"), ("Bank Officer", "middle"), ("School Teacher", "middle"),
        ("Civil Engineer", "middle"), ("Government Officer", "middle"), ("Shop Owner", "lower-middle"),
        ("Doctor", "upper-middle"), ("Chartered Accountant", "upper-middle"), ("Business Owner", "upper-middle"),
        ("Farmer", "lower-middle"), ("Auto Driver", "lower-middle"), ("Nurse", "lower-middle"),
        ("Police Officer", "middle"), ("Railway Employee", "middle"), ("Homemaker", "middle"),
        ("Private Tutor", "lower-middle"), ("Lawyer", "upper-middle"), ("Architect", "upper-middle"),
    ]

    # --- Academic structure: 19 levels (Nursery..UKG, Class 1-10, Class
    # 11/12 x 3 streams each) - section 6. Each entry: (name, order, tier,
    # min_age, max_age) where tier drives the subject set (section 7) and
    # min/max_age drives DOB generation (section 9). -----------------------
    LEVEL_PLAN = [
        ("Nursery", 1, "early_years", 3, 4),
        ("LKG", 2, "early_years", 4, 5),
        ("UKG", 3, "early_years", 5, 6),
        ("Class 1", 4, "primary", 6, 7),
        ("Class 2", 5, "primary", 7, 8),
        ("Class 3", 6, "primary", 8, 9),
        ("Class 4", 7, "primary", 9, 10),
        ("Class 5", 8, "primary", 10, 11),
        ("Class 6", 9, "middle", 11, 12),
        ("Class 7", 10, "middle", 12, 13),
        ("Class 8", 11, "middle", 13, 14),
        ("Class 9", 12, "secondary", 14, 15),
        ("Class 10", 13, "secondary", 15, 16),
        ("Class 11 - Science", 14, "senior_science", 16, 17),
        ("Class 11 - Commerce", 15, "senior_commerce", 16, 17),
        ("Class 11 - Humanities", 16, "senior_humanities", 16, 17),
        ("Class 12 - Science", 17, "senior_science", 17, 18),
        ("Class 12 - Commerce", 18, "senior_commerce", 17, 18),
        ("Class 12 - Humanities", 19, "senior_humanities", 17, 18),
    ]
    # Sections per level name (section 10: uneven, not a flat constant).
    SECTION_COUNTS = {
        "Nursery": 2, "LKG": 2, "UKG": 2,
        "Class 1": 3, "Class 2": 3, "Class 3": 3, "Class 4": 3, "Class 5": 3,
        "Class 6": 3, "Class 7": 3, "Class 8": 3,
        "Class 9": 3, "Class 10": 3,
        "Class 11 - Science": 2, "Class 11 - Commerce": 1, "Class 11 - Humanities": 1,
        "Class 12 - Science": 2, "Class 12 - Commerce": 1, "Class 12 - Humanities": 1,
    }
    SECTION_LETTERS = ["A", "B", "C"]

    # --- Subjects per tier (section 7) -------------------------------------
    SUBJECTS_BY_TIER = {
        "early_years": [("ENG", "English"), ("NUM", "Numbers & Rhymes"), ("GK", "General Knowledge")],
        "primary": [("ENG", "English"), ("MTH", "Mathematics"), ("EVS", "Environmental Studies"),
                    ("HIN", "Hindi"), ("CMP", "Computer"), ("GK", "General Knowledge")],
        "middle": [("ENG", "English"), ("MTH", "Mathematics"), ("SCI", "Science"), ("SST", "Social Science"),
                   ("HIN", "Hindi"), ("CS", "Computer Science"), ("GK", "General Knowledge")],
        "secondary": [("ENG", "English"), ("MTH", "Mathematics"), ("SCI", "Science"), ("SST", "Social Science"),
                      ("HIN", "Hindi"), ("CAP", "Computer Applications")],
        "senior_science": [("ENG", "English"), ("PHY", "Physics"), ("CHE", "Chemistry"), ("MTH", "Mathematics"),
                            ("BIO", "Biology"), ("CS", "Computer Science")],
        "senior_commerce": [("ENG", "English"), ("ACC", "Accountancy"), ("BST", "Business Studies"),
                             ("ECO", "Economics"), ("MTH", "Mathematics"), ("CS", "Computer Science")],
        "senior_humanities": [("ENG", "English"), ("HIS", "History"), ("POL", "Political Science"),
                               ("GEO", "Geography"), ("ECO", "Economics"), ("SOC", "Sociology")],
    }

    FEE_HEAD_PLAN = [
        ("Tuition Fee", "annual"), ("Activity Fee", "annual"), ("Computer Lab Fee", "annual"),
        ("Library Fee", "annual"), ("Examination Fee", "term"),
    ]
    # Realistic annual amount RANGES by tier (section 19), tuition dominant.
    FEE_AMOUNT_RANGES = {
        "early_years": {"Tuition Fee": (28000, 42000), "Activity Fee": (2000, 4000), "Computer Lab Fee": (0, 0),
                         "Library Fee": (500, 1000), "Examination Fee": (800, 1500)},
        "primary": {"Tuition Fee": (32000, 50000), "Activity Fee": (2500, 5000), "Computer Lab Fee": (1000, 2500),
                    "Library Fee": (800, 1500), "Examination Fee": (1000, 2000)},
        "middle": {"Tuition Fee": (38000, 58000), "Activity Fee": (2500, 5000), "Computer Lab Fee": (1500, 3000),
                   "Library Fee": (800, 1500), "Examination Fee": (1200, 2200)},
        "secondary": {"Tuition Fee": (42000, 68000), "Activity Fee": (3000, 5000), "Computer Lab Fee": (2000, 3000),
                      "Library Fee": (1000, 1500), "Examination Fee": (1500, 2500)},
        "senior_science": {"Tuition Fee": (52000, 88000), "Activity Fee": (3000, 5000), "Computer Lab Fee": (2500, 3500),
                            "Library Fee": (1000, 1500), "Examination Fee": (1800, 2500)},
        "senior_commerce": {"Tuition Fee": (50000, 82000), "Activity Fee": (3000, 5000), "Computer Lab Fee": (2000, 3000),
                             "Library Fee": (1000, 1500), "Examination Fee": (1800, 2500)},
        "senior_humanities": {"Tuition Fee": (48000, 78000), "Activity Fee": (3000, 5000), "Computer Lab Fee": (1500, 2500),
                               "Library Fee": (1000, 1500), "Examination Fee": (1800, 2500)},
    }

    EXAM_PLAN = [
        ("Periodic Test 1", 60, 1, True),
        ("Half-Yearly Examination", 100, 2, True),
        ("Periodic Test 2", 60, 3, True),
        ("Annual Examination", 100, 4, False),  # left partially marked / unpublished - "in progress" state
    ]

    COURSE_CONTENT_TOPICS = [
        ("MTH", "Fractions and Decimals", "A worked-through unit on fraction/decimal conversion and operations."),
        ("MTH", "Linear Equations", "Solving linear equations in one and two variables, with worked examples."),
        ("SCI", "Matter Around Us", "States of matter, change of state, and everyday examples."),
        ("SCI", "Light and Reflection", "Laws of reflection, plane and spherical mirrors, ray diagrams."),
        ("ENG", "Grammar and Composition", "Parts of speech, tense usage, and paragraph composition practice."),
        ("SST", "The Mughal Empire", "Rise and administration of the Mughal Empire, key rulers and reforms."),
        ("SST", "Resources and Development", "Natural resource classification, conservation, and sustainable use."),
        ("CS", "Introduction to Python", "Variables, data types, and simple input/output in Python."),
        ("PHY", "Motion and Force", "Newton's laws of motion with numerical problems."),
        ("CHE", "Structure of Atom", "Atomic models, subatomic particles, and electronic configuration."),
        ("BIO", "Cell Structure and Function", "Plant and animal cell structure, organelles and their functions."),
        ("ACC", "Introduction to Accounting", "Basic accounting principles, the accounting equation, and journal entries."),
        ("HIS", "The Mughal Empire", "Rise and administration of the Mughal Empire, key rulers and reforms."),
        ("GEO", "Resources and Development", "Natural resource classification, conservation, and sustainable use."),
        ("ECO", "Demand and Supply", "Market forces, demand/supply curves, and equilibrium price."),
    ]

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=600, help="Number of students to generate (default 600).")
        parser.add_argument("--seed", type=int, default=20260929, help="Deterministic RNG seed (default 20260929).")
        parser.add_argument("--academic-years", type=int, default=3, help="Number of academic years of history (default 3).")
        parser.add_argument("--attendance-days", type=int, default=90, help="School days of attendance history (default 90).")
        parser.add_argument("--clear", action="store_true", help="Remove this school's tenant and demo users, then exit.")
        parser.add_argument("--dry-run", action="store_true", help="Print the generation plan without writing anything.")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.started_at = time_module.monotonic()
        self.n_students = options["students"]
        self.seed = options["seed"]
        self.n_academic_years = max(1, options["academic_years"])
        self.n_attendance_days = max(1, options["attendance_days"])
        self.rng = random.Random(self.seed)

        self.academic_years = [
            f"{self.CURRENT_YEAR - (self.n_academic_years - 1 - i)}-{str(self.CURRENT_YEAR - (self.n_academic_years - 1 - i) + 1)[2:]}"
            for i in range(self.n_academic_years)
        ]
        self.current_academic_year = self.academic_years[-1]

        if options["dry_run"]:
            self._print_dry_run_plan()
            return

        if options["clear"]:
            self._clear_school()
            return

        self._reset_counters()
        self._validation_issues = []

        from organizations.models import Organization

        if Organization.objects.filter(schema_name=self.SCHEMA_NAME).exists():
            raise CommandError(
                f"Schema '{self.SCHEMA_NAME}' already exists. Run with --clear first for a fresh rebuild."
            )

        self._demo_password_hash = self._make_password_hash(self.DEMO_PASSWORD)

        organization = self._create_organization()
        try:
            with tenant_context(organization):
                with transaction.atomic():
                    self._assign_role_permissions()
                    self._create_institution_profile(organization)
                    self._create_academic_structure()
                    self._create_staff_and_instructors()
                    self._create_subject_assignments()
                    self._create_students_and_families()
                    self._create_promotion_history()
                    self._create_attendance_history()
                    self._create_examinations()
                    self._create_fees_and_payments()
                    self._create_course_content()
                    self._create_notifications_and_outbox()
                    self._create_demo_accounts()
        except Exception:
            connection.set_schema_to_public()
            organization.delete(force_drop=True)
            raise

        with tenant_context(organization):
            self._validate_seeded_data()

        self._print_summary()

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def _announce(self, message):
        self.stdout.write(message)
        self.stdout.flush()

    def _reset_counters(self):
        self.created = {
            "academic_years": 0, "levels": 0, "sections": 0, "subjects": 0,
            "staff": 0, "instructors": 0, "subject_assignments": 0,
            "students": 0, "parents": 0, "family_relations": 0,
            "promotion_records": 0,
            "attendance_sessions": 0, "attendance_records": 0,
            "examinations": 0, "exam_schedules": 0, "exam_marks": 0, "exam_results": 0,
            "fee_heads": 0, "student_fees": 0, "payments": 0,
            "course_content": 0, "assignments": 0, "submissions": 0,
            "notifications": 0, "email_outbox_events": 0,
        }
        self.demo_logins = []

    def _make_password_hash(self, raw_password):
        from django.contrib.auth.hashers import make_password

        return make_password(raw_password)

    def _unique_username(self, prefix, index):
        return f"svp_{prefix}_{index:05d}_{self.seed}"

    def _random_region(self):
        return self.rng.choices(self.REGIONS, weights=self.REGION_WEIGHTS, k=1)[0]

    def _random_name(self, gender, region):
        pool = self.MALE_NAMES[region] if gender == "male" else self.FEMALE_NAMES[region]
        first = self.rng.choice(pool)
        surname = self.rng.choice(self.SURNAMES[region])
        return first, surname

    def _random_address(self, region):
        locality, city, state, pin = self.rng.choice(self.ADDRESS_POOLS[region])
        house_no = self.rng.randint(1, 400)
        return f"House No. {house_no}, {locality}, {city}, {state} - {pin}"

    def _random_phone(self):
        return f"+91-{self.rng.choice([7, 8, 9])}{self.rng.randint(100000000, 999999999)}"

    def _dob_for_level(self, min_age, max_age, as_of_year):
        """A birth date that makes the student min_age..max_age years old as
        of April 1 of as_of_year (the school's effective academic-year-start
        reference point), with the day/month randomized (section 9)."""
        age = self.rng.uniform(min_age, max_age)
        reference = date(as_of_year, 4, 1)
        birth_year = reference.year - int(age)
        birth_month = self.rng.randint(1, 12)
        birth_day = self.rng.randint(1, 28)
        return date(birth_year, birth_month, birth_day)

    def _create_user_and_profile(self, *, username, email, first_name, last_name, gender, dob, phone, address, role_slug=None):
        from accounts.models import User
        from profiles.models import Profile
        from roles.models import Role, UserRole

        user = User(username=username, email=email, password=self._demo_password_hash)
        user.save()

        profile = Profile.objects.create(
            user_id=user.id, first_name=first_name, last_name=last_name,
            gender=gender, date_of_birth=dob, phone=phone, address=address,
        )
        if role_slug:
            role = Role.objects.get(slug=role_slug)
            UserRole.objects.create(user=user, role=role)
        return user, profile

    # ------------------------------------------------------------------
    # Dry run / clear
    # ------------------------------------------------------------------

    def _print_dry_run_plan(self):
        self._announce("DRY RUN - no data will be written.\n")
        self._announce(f"School: {self.ORG_NAME}  (schema: {self.SCHEMA_NAME})")
        self._announce(f"Academic years: {', '.join(self.academic_years)} (current: {self.current_academic_year})")
        self._announce(f"Students: {self.n_students}")
        self._announce(f"Attendance days: {self.n_attendance_days}")
        self._announce(f"Levels: {len(self.LEVEL_PLAN)}")
        total_sections = sum(self.SECTION_COUNTS.values())
        self._announce(f"Sections: {total_sections}")
        self._announce(f"Examinations: {len(self.EXAM_PLAN)}")
        self._announce(f"Fee heads: {len(self.FEE_HEAD_PLAN)}")
        self._announce(f"Seed: {self.seed}")

    def _clear_school(self):
        from organizations.models import Organization

        try:
            organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        except Organization.DoesNotExist:
            self._announce(f"No schema named '{self.SCHEMA_NAME}' exists - nothing to clear.")
            return

        with tenant_context(organization):
            from profiles.models import Profile

            user_ids = list(Profile.objects.exclude(user_id=None).values_list("user_id", flat=True))

        connection.set_schema_to_public()
        organization.delete(force_drop=True)

        from accounts.models import User

        deleted, _ = User.objects.filter(id__in=user_ids).delete()
        self._announce(f"Cleared schema '{self.SCHEMA_NAME}' and {deleted} associated public-schema user row(s).")

    # ------------------------------------------------------------------
    # Organization / roles / institution profile
    # ------------------------------------------------------------------

    def _create_organization(self):
        from organizations.models import Domain, Organization

        organization = Organization.objects.create(
            schema_name=self.SCHEMA_NAME,
            name=self.ORG_NAME,
            address="Plot 14, Education Hub Road, Bhubaneswar, Odisha",
            phone="+91-674-2300000",
            email=f"info@{self.EMAIL_DOMAIN}",
            is_active=True,
        )
        Domain.objects.create(domain=self.DOMAIN, tenant=organization, is_primary=True)
        return organization

    def _assign_role_permissions(self):
        """Grants realistic (non-full) permission sets to the pre-seeded
        system roles (owner already has every permission via the
        post_migrate signal - see roles/signals.py - left untouched)."""
        from roles.models import Permission, Role

        def grant(slug, codenames):
            role = Role.objects.get(slug=slug)
            role.permissions.set(Permission.objects.filter(codename__in=codenames))

        grant("instructor", [
            "view_students", "view_academics", "manage_grading", "enter_marks", "view_examinations",
            "mark_attendance", "view_attendance", "view_attendance_reports", "view_course_content",
            "manage_course_content", "view_timetable", "view_homework", "manage_homework",
        ])
        grant("staff", [
            "view_students", "manage_students", "view_academics", "view_attendance",
            "view_attendance_reports", "view_fees", "collect_fees", "view_examinations",
            "view_notifications",
        ])
        grant("student", ["view_own_attendance", "view_own_results", "view_own_fees", "view_course_content",
                          "view_own_homework"])
        # Parents see their children through the parent portal, never the student-only "own" screens.
        grant("parent", [
            "view_own_children", "view_child_attendance", "view_child_timetable", "view_child_results",
            "view_child_fees", "pay_child_fees", "view_calendar_events", "view_child_homework",
        ])

    def _create_institution_profile(self, organization):
        from profiles.models import InstitutionProfile

        InstitutionProfile.objects.update_or_create(
            organization_id=organization.id,
            defaults={
                "tagline": "Nurturing Tomorrow's Leaders",
                "mission": "To provide holistic, value-based education that empowers every student to excel.",
                "established_date": date(1998, 6, 1),
            },
        )

    # ------------------------------------------------------------------
    # Academic structure
    # ------------------------------------------------------------------

    def _create_academic_structure(self):
        from academics.models import AcademicLevel, Program, Section, Subject

        program = Program.objects.create(name="Sunrise Valley Curriculum", code="SVC")
        self.created["academic_years"] = len(self.academic_years)

        self.levels_by_name = {}
        self.sections_by_level = {}
        self.all_sections = []
        self.subjects_by_level = {}

        for name, order, tier, min_age, max_age in self.LEVEL_PLAN:
            level = AcademicLevel.objects.create(program=program, name=name, order=order)
            level.tier = tier
            level.min_age = min_age
            level.max_age = max_age
            self.levels_by_name[name] = level
            self.created["levels"] += 1

            section_count = self.SECTION_COUNTS[name]
            sections = []
            for i in range(section_count):
                # Uneven capacity across sections (section 10) - still
                # realistic (30-42), not a flat constant.
                capacity = self.rng.randint(30, 42)
                section = Section.objects.create(level=level, name=self.SECTION_LETTERS[i], capacity=capacity)
                sections.append(section)
                self.all_sections.append(section)
                self.created["sections"] += 1
            self.sections_by_level[name] = sections

            subjects = []
            for code, subj_name in self.SUBJECTS_BY_TIER[tier]:
                subject = Subject.objects.create(level=level, name=subj_name, code=code)
                subjects.append(subject)
                self.created["subjects"] += 1
            self.subjects_by_level[name] = subjects

        self._announce(
            f"Academic structure: {self.created['levels']} levels, "
            f"{self.created['sections']} sections, {self.created['subjects']} subjects."
        )

    # ------------------------------------------------------------------
    # Staff & instructors
    # ------------------------------------------------------------------

    def _create_staff_and_instructors(self):
        """
        Realistic teacher count scaled to student volume (roughly one
        teacher per ~20 students, plus admin staff), with joining_date/
        experience_years correlated (section 14): earlier joiners skew
        toward higher prior-experience bands, newer joiners skew lower -
        both values are independently plausible (experience_years is
        career-to-date, not years-at-this-school, so a 2025 joiner CAN
        have significant prior experience - the model allows it), but
        the correlation keeps the dataset from looking like pure noise.
        """
        from profiles.models import Profile
        from staff.models import Instructor, StaffMember

        n_teachers = max(20, self.n_students // 20)
        n_admin_staff = max(8, self.n_students // 60)

        self.instructors_by_subject_code = {}
        self.all_instructors = []
        emp_seq = 1

        for i in range(n_teachers):
            region = self._random_region()
            gender = self.rng.choice(["male", "female"])
            first, surname = self._random_name(gender, region)
            dob = self._dob_for_level(26, 55, self.CURRENT_YEAR)
            years_since_birth_to_now = self.CURRENT_YEAR - dob.year
            join_years_ago = self.rng.randint(1, min(18, max(2, years_since_birth_to_now - 23)))
            joining_date = date(self.CURRENT_YEAR - join_years_ago, self.rng.randint(1, 12), self.rng.randint(1, 28))
            if join_years_ago >= 8:
                experience_years = self.rng.randint(8, 25)
            elif join_years_ago >= 3:
                experience_years = self.rng.randint(3, 15)
            else:
                experience_years = self.rng.randint(0, 6)

            username = self._unique_username("teacher", i)
            email = f"{username}@{self.EMAIL_DOMAIN}"
            user, profile = self._create_user_and_profile(
                username=username, email=email, first_name=first, last_name=surname, gender=gender,
                dob=dob, phone=self._random_phone(), address=self._random_address(region), role_slug="instructor",
            )
            subject_code, subject_name = self.rng.choice(
                [(c, n) for tier_subjects in self.SUBJECTS_BY_TIER.values() for c, n in tier_subjects]
            )
            staff_member = StaffMember.objects.create(
                profile=profile, employee_id=f"EMP/{joining_date.year}/{emp_seq:04d}",
                designation="Teacher", department=subject_name, joining_date=joining_date,
                is_active=True, experience_years=experience_years,
            )
            instructor = Instructor.objects.create(staff_member=staff_member, specialization=subject_name)
            self.instructors_by_subject_code.setdefault(subject_code, []).append(instructor)
            self.all_instructors.append(instructor)
            self.created["staff"] += 1
            self.created["instructors"] += 1
            emp_seq += 1

            if i == 0:
                self.demo_logins.append(("Teacher", email, self.DEMO_PASSWORD))
                self.sample_instructor_user = user

        designations = ["Administrative Officer", "Librarian", "Accountant", "Receptionist", "Lab Assistant", "Counsellor"]
        for i in range(n_admin_staff):
            region = self._random_region()
            gender = self.rng.choice(["male", "female"])
            first, surname = self._random_name(gender, region)
            dob = self._dob_for_level(24, 55, self.CURRENT_YEAR)
            joining_date = date(self.CURRENT_YEAR - self.rng.randint(1, 15), self.rng.randint(1, 12), self.rng.randint(1, 28))

            username = self._unique_username("staff", i)
            email = f"{username}@{self.EMAIL_DOMAIN}"
            user, profile = self._create_user_and_profile(
                username=username, email=email, first_name=first, last_name=surname, gender=gender,
                dob=dob, phone=self._random_phone(), address=self._random_address(region), role_slug="staff",
            )
            StaffMember.objects.update_or_create(
                profile=profile,
                defaults={
                    "employee_id": f"EMP/{joining_date.year}/{emp_seq:04d}",
                    "designation": self.rng.choice(designations), "department": "Administration",
                    "joining_date": joining_date, "is_active": True,
                    "experience_years": self.rng.randint(1, 20),
                },
            )
            self.created["staff"] += 1
            emp_seq += 1
            if i == 0:
                self.demo_logins.append(("Staff", email, self.DEMO_PASSWORD))

        self._announce(f"Staff: {self.created['staff']} ({self.created['instructors']} instructors).")

    def _create_subject_assignments(self):
        """
        Realistic (section 15): each teacher is assigned a SMALL number of
        section x subject slots (2-4) matching their specialization, not
        every teacher to every class. Falls back to any available
        instructor for a subject with no matching specialist (keeps every
        SubjectAssignment slot filled, which the examinations/fees seeding
        below depends on for a realistic "every section has a teacher"
        picture), rather than leaving gaps.
        """
        from academics.models import SubjectAssignment

        all_instructors_cycle = list(self.all_instructors)
        self.rng.shuffle(all_instructors_cycle)
        fallback_iter = iter(all_instructors_cycle * 10)

        assignments = []
        for level_name, sections in self.sections_by_level.items():
            subjects = self.subjects_by_level[level_name]
            for section in sections:
                for subject in subjects:
                    pool = self.instructors_by_subject_code.get(subject.code)
                    instructor = self.rng.choice(pool) if pool else next(fallback_iter)
                    assignments.append(SubjectAssignment(section=section, subject=subject, instructor=instructor))
        SubjectAssignment.objects.bulk_create(assignments)
        self.created["subject_assignments"] = len(assignments)
        self._announce(f"Subject assignments: {self.created['subject_assignments']}.")

    # ------------------------------------------------------------------
    # Students & families
    # ------------------------------------------------------------------

    def _create_students_and_families(self):
        """
        Distributes self.n_students across levels/sections unevenly
        (section 10), with age-correct DOB per level (section 9), a
        deterministic per-student "ability" factor (section 18 - used
        later to correlate attendance and exam marks), and family/sibling
        linkage (section 13): ~30% of new students join an EXISTING family
        (same surname/region, if that family has fewer than 3 children and
        a plausible age gap) rather than always creating a brand-new one.
        """
        from families.models import Parent, StudentParentRelation
        from profiles.models import Profile
        from students.models import Student, StudentLevel

        self.students = []
        self.student_ability = {}
        self.families = []  # each: {"region":..., "surname":..., "parents":[profile_ids as Parent objs], "children":[student]}

        level_weights = []
        for name, order, tier, min_age, max_age in self.LEVEL_PLAN:
            # Slightly fewer students at the very top (senior streams split
            # 3 ways) and bottom (early years, smaller intake) - a soft
            # bell-ish shape, not perfectly flat.
            if tier == "early_years":
                level_weights.append(0.7)
            elif tier.startswith("senior_"):
                level_weights.append(0.55)
            else:
                level_weights.append(1.0)

        level_names = [lp[0] for lp in self.LEVEL_PLAN]
        counts = self._distribute_counts(self.n_students, level_weights)
        admission_seq_by_year = {}

        for (name, order, tier, min_age, max_age), count in zip(self.LEVEL_PLAN, counts):
            level = self.levels_by_name[name]
            sections = self.sections_by_level[name]
            section_weights = [self.rng.uniform(0.8, 1.2) for _ in sections]
            section_counts = self._distribute_counts(count, section_weights)

            for section, n_in_section in zip(sections, section_counts):
                for _ in range(n_in_section):
                    student = self._create_one_student(level, section, min_age, max_age, admission_seq_by_year)
                    self.students.append(student)

        self._link_families()
        self._ensure_demo_student_and_parent_logins()
        self._announce(
            f"Students: {self.created['students']}. Parents: {self.created['parents']} "
            f"({self.created['family_relations']} parent-child relations)."
        )

    def _ensure_demo_student_and_parent_logins(self):
        """
        The per-student/per-family random rolls that create demo student/
        parent accounts elsewhere are a bonus, not a guarantee - with a
        small --students count they can easily roll zero hits. Section 26
        explicitly wants example student/parent accounts to exist, so this
        deterministically picks one active student with at least one
        linked parent and gives both a real portal account, unless one
        already exists from the random rolls above.
        """
        from families.models import StudentParentRelation

        has_student_login = any(label == "Student" for label, _, _ in self.demo_logins)
        has_parent_login = any(label == "Parent" for label, _, _ in self.demo_logins)
        if has_student_login and has_parent_login:
            return

        chosen_student = None
        chosen_relation = None
        for student in self.students:
            if student.status != "active":
                continue
            relation = StudentParentRelation.objects.filter(student=student, is_primary_contact=True).select_related("parent__profile").first()
            if relation is not None:
                chosen_student = student
                chosen_relation = relation
                break

        if chosen_student is None:
            return

        from accounts.models import User
        from roles.models import Role, UserRole

        if not has_student_login:
            profile = chosen_student.profile
            if not profile.user_id:
                username = self._unique_username("student_demo", 0)
                email = f"{username}@{self.EMAIL_DOMAIN}"
                user = User(username=username, email=email, password=self._demo_password_hash)
                user.save()
                profile.user_id = user.id
                profile.save(update_fields=["user_id"])
                UserRole.objects.create(user=user, role=Role.objects.get(slug="student"))
                self.demo_logins.append(("Student", email, self.DEMO_PASSWORD))

        if not has_parent_login:
            parent_profile = chosen_relation.parent.profile
            if not parent_profile.user_id:
                username = self._unique_username("parent_demo", 0)
                email = f"{username}@{self.EMAIL_DOMAIN}"
                user = User(username=username, email=email, password=self._demo_password_hash)
                user.save()
                parent_profile.user_id = user.id
                parent_profile.save(update_fields=["user_id"])
                UserRole.objects.create(user=user, role=Role.objects.get(slug="parent"))
                self.demo_logins.append(("Parent", email, self.DEMO_PASSWORD))

    def _distribute_counts(self, total, weights):
        if total <= 0 or not weights:
            return [0] * len(weights)
        weight_sum = sum(weights)
        raw = [total * w / weight_sum for w in weights]
        counts = [int(r) for r in raw]
        remainder = total - sum(counts)
        fractional_order = sorted(range(len(weights)), key=lambda idx: raw[idx] - counts[idx], reverse=True)
        for idx in fractional_order[:remainder]:
            counts[idx] += 1
        return counts

    def _create_one_student(self, level, section, min_age, max_age, admission_seq_by_year):
        from profiles.models import Profile
        from students.models import Student, StudentLevel

        region = self._random_region()
        gender = self.rng.choice(["male", "female"])
        first, surname = self._random_name(gender, region)
        dob = self._dob_for_level(min_age, max_age, self.CURRENT_YEAR)

        status_roll = self.rng.random()
        status = "active" if status_roll < 0.97 else self.rng.choice(["inactive", "transferred", "withdrawn"])

        admission_year = self.CURRENT_YEAR - self.rng.randint(0, self.n_academic_years - 1) if self.n_academic_years > 1 else self.CURRENT_YEAR
        admission_seq_by_year[admission_year] = admission_seq_by_year.get(admission_year, 0) + 1
        enrollment_id = f"SV/{admission_year}/{admission_seq_by_year[admission_year]:04d}"

        profile = Profile.objects.create(
            first_name=first, last_name=surname, gender=gender, date_of_birth=dob,
            address=self._random_address(region),
        )
        student = Student.objects.create(
            profile=profile, enrollment_id=enrollment_id,
            admission_date=date(admission_year, self.rng.randint(4, 6), self.rng.randint(1, 28)),
            status=status,
        )
        current_student_level = StudentLevel.objects.create(
            student=student, level=level, section=section,
            academic_year=self.current_academic_year, is_current=True,
        )
        student._region = region
        student._surname = surname
        student._level_name = level.name
        student._dob = dob
        student._current_student_level = current_student_level
        self.created["students"] += 1

        # Deterministic ability factor (section 18): roughly normal via the
        # average of 3 uniform draws, clipped to [0.05, 0.98].
        ability = sum(self.rng.uniform(0, 1) for _ in range(3)) / 3
        self.student_ability[student.id] = max(0.05, min(0.98, ability))

        if len(self.demo_logins) < 10 and status == "active" and self.rng.random() < 0.02:
            username = self._unique_username("student", self.created["students"])
            email = f"{username}@{self.EMAIL_DOMAIN}"
            from accounts.models import User
            from roles.models import Role, UserRole

            user = User(username=username, email=email, password=self._demo_password_hash)
            user.save()
            profile.user_id = user.id
            profile.save(update_fields=["user_id"])
            UserRole.objects.create(user=user, role=Role.objects.get(slug="student"))
            self.demo_logins.append(("Student", email, self.DEMO_PASSWORD))
            self.sample_student_for_demo = student

        return student

    def _link_families(self):
        """
        Builds family units AFTER all students exist, grouping by
        (region, surname) so siblings share both a plausible region and
        surname, then creating father/mother (or a single guardian ~12% of
        the time) per family - section 13.
        """
        from families.models import Parent, StudentParentRelation
        from profiles.models import Profile

        by_surname_region = {}
        for student in self.students:
            by_surname_region.setdefault((student._surname, student._region), []).append(student)

        for (surname, region), siblings_pool in by_surname_region.items():
            unassigned = list(siblings_pool)
            self.rng.shuffle(unassigned)
            while unassigned:
                # 30% chance this family has 2 children, 8% chance 3, else 1.
                roll = self.rng.random()
                family_size = 3 if roll < 0.08 else (2 if roll < 0.38 else 1)
                family_size = min(family_size, len(unassigned))
                children = [unassigned.pop() for _ in range(family_size)]
                self._create_family(surname, region, children)

    def _create_family(self, surname, region, children):
        from families.models import Parent, StudentParentRelation
        from profiles.models import Profile

        single_guardian = self.rng.random() < 0.12
        occupation, income = self.rng.choice(self.OCCUPATIONS)
        address = self._random_address(region)

        parent_defs = []
        if single_guardian:
            gender = self.rng.choice(["male", "female"])
            relation = "father" if gender == "male" else "mother"
            first, _ = self._random_name(gender, region)
            parent_defs.append((gender, relation, first, True))
        else:
            father_first, _ = self._random_name("male", region)
            mother_first, _ = self._random_name("female", region)
            parent_defs.append(("male", "father", father_first, True))
            if self.rng.random() > 0.08:  # ~8% of two-parent families: mother not separately registered
                parent_defs.append(("female", "mother", mother_first, False))

        parent_objs = []
        for gender, relation, first_name, is_primary in parent_defs:
            profile = Profile.objects.create(
                first_name=first_name, last_name=surname, gender=gender,
                phone=self._random_phone(), address=address,
            )
            parent = Parent.objects.create(profile=profile, occupation=occupation, income_level=income)
            parent_objs.append((parent, relation, is_primary))
            self.created["parents"] += 1

        for child in children:
            for parent, relation, is_primary in parent_objs:
                StudentParentRelation.objects.create(
                    student=child, parent=parent, relation_type=relation, is_primary_contact=is_primary,
                )
                self.created["family_relations"] += 1

        if len(self.demo_logins) < 10 and parent_objs and self.rng.random() < 0.015:
            parent, _, _ = parent_objs[0]
            from accounts.models import User
            from roles.models import Role, UserRole

            username = self._unique_username("parent", self.created["parents"])
            email = f"{username}@{self.EMAIL_DOMAIN}"
            user = User(username=username, email=email, password=self._demo_password_hash)
            user.save()
            parent.profile.user_id = user.id
            parent.profile.save(update_fields=["user_id"])
            UserRole.objects.create(user=user, role=Role.objects.get(slug="parent"))
            self.demo_logins.append(("Parent", email, self.DEMO_PASSWORD))

    # ------------------------------------------------------------------
    # Promotion history (section 20)
    # ------------------------------------------------------------------

    def _create_promotion_history(self):
        """
        For every ACTIVE student currently in a level other than the
        lowest (Nursery), builds one prior-year StudentLevel (one level
        back in LEVEL_PLAN order, same section slot where possible) plus a
        matching PromotionRecord - "promoted" for most, "retained" for a
        realistic minority (repeated the same grade), giving each such
        student 1 extra year of history. This only runs when
        --academic-years > 1 (section 5/20) - with a single academic year
        there is no "previous year" to promote FROM.
        """
        if self.n_academic_years <= 1:
            self._announce("Promotion history: skipped (--academic-years=1, no prior year to promote from).")
            return

        from students.models import PromotionRecord, StudentLevel

        level_order = [lp[0] for lp in self.LEVEL_PLAN]
        previous_academic_year = self.academic_years[-2]

        new_student_levels = []
        promotion_records = []

        for student in self.students:
            if student.status != "active":
                continue
            current_index = level_order.index(student._level_name)
            if current_index == 0:
                continue  # Nursery has no "previous grade" to have come from

            retained = self.rng.random() < 0.04
            source_level_name = level_order[current_index] if retained else level_order[current_index - 1]
            source_level = self.levels_by_name[source_level_name]
            source_sections = self.sections_by_level[source_level_name]
            source_section = self.rng.choice(source_sections)

            source_student_level = StudentLevel(
                student=student, level=source_level, section=source_section,
                academic_year=previous_academic_year, is_current=False,
            )
            new_student_levels.append((student, source_student_level, source_level, source_section, retained))

        StudentLevel.objects.bulk_create([sl for _, sl, _, _, _ in new_student_levels])

        # bulk_create() DOES populate .id for UUID-pk models (client-side
        # default), so source_student_level already carries its id here -
        # no re-fetch needed. The CURRENT StudentLevel is the one stashed
        # on the student object when it was created (_create_one_student),
        # avoiding a per-student query here.
        for student, source_student_level, source_level, source_section, retained in new_student_levels:
            target_student_level = student._current_student_level
            promotion_records.append(
                PromotionRecord(
                    student=student,
                    action="retained" if retained else "promoted",
                    source_academic_year=previous_academic_year,
                    target_academic_year=self.current_academic_year,
                    source_level=source_level, target_level=target_student_level.level,
                    source_section=source_section, target_section=target_student_level.section,
                    source_student_level=source_student_level, target_student_level=target_student_level,
                    reason="Annual promotion cycle." if not retained else "Did not meet promotion criteria - repeated grade.",
                )
            )

        PromotionRecord.objects.bulk_create(promotion_records)
        self.created["promotion_records"] = len(promotion_records)
        self._announce(f"Promotion records: {self.created['promotion_records']}.")

    # ------------------------------------------------------------------
    # Attendance history (section 16/18)
    # ------------------------------------------------------------------

    def _create_attendance_history(self):
        """
        One AttendanceSession per (section, school day), going backward
        from today across self.n_attendance_days weekdays. Per-student
        present/absent/late/leave probabilities are derived from that
        student's ability factor (section 18: a student with high ability
        tends toward high attendance too, with real noise - not a
        deterministic formula) so attendance and exam performance (seeded
        later from the SAME ability factor) are correlated but not
        identical.
        """
        from attendance.models import AttendanceSession, StudentAttendance

        school_days = []
        cursor = date.today()
        while len(school_days) < self.n_attendance_days:
            cursor -= timedelta(days=1)
            if cursor.weekday() < 5:  # Mon-Fri
                school_days.append(cursor)
        school_days.reverse()

        # Build section membership from StudentLevel directly.
        from students.models import StudentLevel

        current_levels = StudentLevel.objects.filter(
            academic_year=self.current_academic_year, is_current=True
        ).select_related("section")
        section_students = {}
        for sl in current_levels:
            if sl.section_id is None:
                continue
            section_students.setdefault(sl.section_id, []).append(sl.student_id)

        for section in self.all_sections:
            student_ids = section_students.get(section.id, [])
            if not student_ids:
                continue
            for day in school_days:
                session = AttendanceSession.objects.create(
                    section=section, academic_year=self.current_academic_year, date=day,
                )
                self.created["attendance_sessions"] += 1
                records = []
                for student_id in student_ids:
                    ability = self.student_ability.get(student_id, 0.6)
                    # Base attendance probability scales with ability:
                    # ability 0.05 -> ~70% present, ability 0.98 -> ~98% present.
                    present_prob = 0.70 + ability * 0.28
                    roll = self.rng.random()
                    if roll < present_prob:
                        status = "present"
                    elif roll < present_prob + 0.05:
                        status = "late"
                    elif roll < present_prob + 0.08:
                        status = "leave"
                    else:
                        status = "absent"
                    records.append(StudentAttendance(session=session, student_id=student_id, status=status))
                StudentAttendance.objects.bulk_create(records)
                self.created["attendance_records"] += len(records)

        self._announce(
            f"Attendance: {self.created['attendance_sessions']} sessions, "
            f"{self.created['attendance_records']} records over {len(school_days)} school days."
        )

    # ------------------------------------------------------------------
    # Examinations (section 17/18)
    # ------------------------------------------------------------------

    def _create_examinations(self):
        """
        4 examinations (section 17's exact names), each with one
        ExamSchedule per (section, subject) in the current academic year.
        Marks are correlated with the student's ability factor (section
        18): ability maps to a performance band, each band to a mark
        RANGE, with noise - not a deterministic ability->mark formula.

        Reuses examinations.services.calculate_examination_results_bulk()
        (the Phase 9G bulk result-calculation helper) to build ExamResult
        snapshots for the 3 "should_publish" examinations, then writes
        them with ExamResult.objects.bulk_create() directly - the exact
        same "calculate in Python, write once" shape Phase 9G audited and
        tested, and deliberately NOT examinations.services.
        publish_examination() (which would queue a real notification/
        outbox event per student - undesirable for a bulk seeder, exactly
        the reasoning seed_demo_school.py's own docstring already gives).
        """
        from academics.models import Subject
        from examinations.models import ExamMark, ExamResult, ExamSchedule, ExamType, Examination, GradeBoundary
        from examinations.services import calculate_examination_results_bulk
        from students.models import StudentLevel

        for ay in self.academic_years:
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("90"), max_percentage=Decimal("100"), defaults={"grade_label": "A+", "grade_point": Decimal("4.0")})
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("80"), max_percentage=Decimal("89.99"), defaults={"grade_label": "A", "grade_point": Decimal("3.7")})
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("65"), max_percentage=Decimal("79.99"), defaults={"grade_label": "B+", "grade_point": Decimal("3.3")})
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("50"), max_percentage=Decimal("64.99"), defaults={"grade_label": "B", "grade_point": Decimal("3.0")})
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("35"), max_percentage=Decimal("49.99"), defaults={"grade_label": "C", "grade_point": Decimal("2.0")})
            GradeBoundary.objects.get_or_create(academic_year=ay, min_percentage=Decimal("0"), max_percentage=Decimal("34.99"), defaults={"grade_label": "F", "grade_point": Decimal("0.0")})

        current_levels = StudentLevel.objects.filter(
            academic_year=self.current_academic_year, is_current=True
        ).select_related("section", "student")
        students_by_section = {}
        for sl in current_levels:
            if sl.section_id is None:
                continue
            students_by_section.setdefault(sl.section_id, []).append(sl.student)

        for name, max_marks, order, should_publish in self.EXAM_PLAN:
            exam_type = ExamType.objects.create(name=name, order=order)
            start = date(self.CURRENT_YEAR, 6 + order, 1)
            examination = Examination.objects.create(
                academic_year=self.current_academic_year, name=f"{name} {self.current_academic_year}",
                exam_type=exam_type, start_date=start, end_date=start + timedelta(days=7),
            )
            self.created["examinations"] += 1

            schedules_by_section_subject = {}
            for level_name, sections in self.sections_by_level.items():
                subjects = self.subjects_by_level[level_name]
                for section in sections:
                    for slot, subject in enumerate(subjects):
                        schedule = ExamSchedule.objects.create(
                            examination=examination, academic_year=self.current_academic_year,
                            subject=subject, section=section,
                            date=start + timedelta(days=slot), start_time=dt_time(9, 0), end_time=dt_time(11, 0),
                            max_marks=Decimal(str(max_marks)), pass_marks=Decimal(str(round(max_marks * 0.33))),
                        )
                        schedules_by_section_subject[(section.id, subject.id)] = schedule
                        self.created["exam_schedules"] += 1

            all_marks = []
            for level_name, sections in self.sections_by_level.items():
                subjects = self.subjects_by_level[level_name]
                for section in sections:
                    roster = [s for s in students_by_section.get(section.id, []) if s.status == "active"]
                    for subject in subjects:
                        schedule = schedules_by_section_subject[(section.id, subject.id)]
                        if not should_publish and self.rng.random() < 0.35:
                            continue  # Annual Examination: some subjects not yet marked (in progress)
                        for student in roster:
                            if self.rng.random() < 0.025:
                                all_marks.append(ExamMark(exam_schedule=schedule, student=student, is_absent=True, attendance="absent"))
                                continue
                            ability = self.student_ability.get(student.id, 0.6)
                            pct = max(0.05, min(0.99, ability + self.rng.uniform(-0.15, 0.15)))
                            marks_obtained = Decimal(str(round(pct * max_marks, 2)))
                            all_marks.append(ExamMark(exam_schedule=schedule, student=student, marks_obtained=marks_obtained))

            ExamMark.objects.bulk_create(all_marks)
            self.created["exam_marks"] += len(all_marks)

            if order <= 2:
                ExamSchedule.objects.filter(examination=examination).update(is_locked=True, locked_at=timezone.now())

            if should_publish:
                participating_student_ids = set(
                    ExamMark.objects.filter(exam_schedule__examination=examination).values_list("student_id", flat=True).distinct()
                )
                from students.models import Student

                participating_students = list(Student.objects.filter(id__in=participating_student_ids))
                results_by_student = calculate_examination_results_bulk(examination, participating_students)
                exam_results = []
                for student in participating_students:
                    result = results_by_student.get(student.id)
                    if result is None:
                        continue
                    exam_results.append(ExamResult(
                        examination=examination, student=student, academic_year=examination.academic_year,
                        total_marks_obtained=result["total_marks_obtained"], total_max_marks=result["total_max_marks"],
                        percentage=result["percentage"], overall_grade=result["overall_grade"],
                        is_pass=result["is_pass"], subject_breakdown=result["subject_breakdown"],
                    ))
                ExamResult.objects.bulk_create(exam_results)
                self.created["exam_results"] += len(exam_results)
                examination.is_published = True
                examination.published_at = timezone.now()
                examination.save(update_fields=["is_published", "published_at"])

        self._announce(
            f"Examinations: {self.created['examinations']}, schedules: {self.created['exam_schedules']}, "
            f"marks: {self.created['exam_marks']}, results: {self.created['exam_results']}."
        )

    # ------------------------------------------------------------------
    # Fees & payments (section 19)
    # ------------------------------------------------------------------

    def _create_fees_and_payments(self):
        """
        5 fee heads (section 19), amounts tier-correlated (younger/older
        grades priced differently, per FEE_AMOUNT_RANGES). Each active
        student gets all 5 StudentFee rows for the current academic year
        via fees.services.assign_student_fee() (never written to the
        model directly - section 32/33 require reusing the service), then
        a payment SCENARIO is rolled per student (fully_paid/
        partially_paid/outstanding/overdue/discounted) and applied via
        fees.services.record_payment() so every business rule (allocation
        sum validation, select_for_update, receipt numbering) runs for
        real, exactly as the live application would enforce it.
        """
        from fees.models import FeeHead
        from fees.services import assign_student_fee, record_payment

        fee_heads = {}
        for name, frequency in self.FEE_HEAD_PLAN:
            fee_head, _ = FeeHead.objects.get_or_create(name=name, defaults={"is_active": True})
            fee_heads[name] = fee_head
        self.created["fee_heads"] = len(fee_heads)

        recorder = self.all_instructors[0].staff_member if self.all_instructors else None

        for student in self.students:
            if student.status != "active":
                continue
            tier = self.levels_by_name[student._level_name].tier
            amount_ranges = self.FEE_AMOUNT_RANGES[tier]

            student_fees = []
            for name, frequency in self.FEE_HEAD_PLAN:
                low, high = amount_ranges[name]
                if high == 0:
                    continue
                amount = Decimal(str(self.rng.randint(low, high)))
                discount = Decimal("0")
                discount_reason = ""
                if self.rng.random() < 0.08:
                    discount = (amount * Decimal(str(self.rng.choice([0.1, 0.15, 0.25])))).quantize(Decimal("0.01"))
                    discount_reason = "Sibling / merit discount"
                student_fee = assign_student_fee(
                    student=student, fee_head=fee_heads[name], academic_year=self.current_academic_year,
                    amount_due=amount, due_date=date(self.CURRENT_YEAR, 7, 15),
                    discount_amount=discount, discount_reason=discount_reason,
                )
                student_fees.append(student_fee)
                self.created["student_fees"] += 1

            if not student_fees:
                continue

            scenario_roll = self.rng.random()
            if scenario_roll < 0.40:
                scenario = "fully_paid"
            elif scenario_roll < 0.70:
                scenario = "partially_paid"
            elif scenario_roll < 0.90:
                scenario = "overdue"
            else:
                scenario = "unpaid"

            if scenario == "unpaid":
                continue

            for student_fee in student_fees:
                outstanding = student_fee.amount_due - student_fee.discount_amount
                if outstanding <= 0:
                    continue
                if scenario == "fully_paid":
                    pay_amount = outstanding
                elif scenario in ("partially_paid", "overdue"):
                    pay_amount = (outstanding * Decimal(str(self.rng.uniform(0.3, 0.75)))).quantize(Decimal("0.01"))
                    if pay_amount <= 0:
                        continue
                else:
                    continue
                record_payment(
                    student=student, amount=pay_amount,
                    method=self.rng.choice(["cash", "bank_transfer", "upi", "cheque", "online"]),
                    allocations=[{"student_fee_id": student_fee.id, "amount": pay_amount}],
                    recorded_by=recorder, reference_note=f"{scenario} - {student_fee.fee_head.name}",
                )
                self.created["payments"] += 1

        self._announce(f"Fees: {self.created['student_fees']} student-fee records, {self.created['payments']} payments.")

    # ------------------------------------------------------------------
    # Course content (section 21)
    # ------------------------------------------------------------------

    def _create_course_content(self):
        from academics.models import Subject
        from course_content.models import Assignment, AssignmentSubmission, CourseContent
        from students.models import StudentLevel

        if not self.all_instructors:
            self._announce("Course content: skipped (no instructors).")
            return
        creator = self.all_instructors[0].staff_member

        current_levels = StudentLevel.objects.filter(
            academic_year=self.current_academic_year, is_current=True
        ).select_related("student")
        students_by_level = {}
        for sl in current_levels:
            students_by_level.setdefault(sl.level_id, []).append(sl.student)

        for i, (subject_code, title, description) in enumerate(self.COURSE_CONTENT_TOPICS):
            matching_levels = [lvl for lvl_name, lvl in self.levels_by_name.items()
                                if any(s.code == subject_code for s in self.subjects_by_level[lvl_name])]
            if not matching_levels:
                continue
            level = self.rng.choice(matching_levels)
            subject = next(s for s in self.subjects_by_level[level.name] if s.code == subject_code)

            is_assignment = i % 2 == 1
            content = CourseContent.objects.create(
                title=title, description=description,
                content_type="assignment" if is_assignment else "note",
                created_by=creator, is_published=True, publish_date=timezone.now(),
            )
            content.target_levels.add(level)
            content.target_subjects.add(subject)
            self.created["course_content"] += 1

            if is_assignment:
                due = timezone.now() + timedelta(days=self.rng.randint(3, 14))
                assignment = Assignment.objects.create(
                    content=content, due_date=due, total_points=Decimal("100"),
                    submission_type="file", instructions=f"Complete the exercises on '{title}' and submit before the due date.",
                )
                self.created["assignments"] += 1

                roster = students_by_level.get(level.id, [])
                active_roster = [s for s in roster if s.status == "active"][:40]
                submissions = []
                for student in active_roster:
                    if self.rng.random() >= 0.70:
                        continue
                    graded = self.rng.random() < 0.60
                    ability = self.student_ability.get(student.id, 0.6)
                    score = Decimal(str(round(max(0.1, min(0.99, ability + self.rng.uniform(-0.1, 0.1))) * 100, 2))) if graded else None
                    submissions.append(AssignmentSubmission(
                        assignment=assignment, student=student,
                        submitted_at=due - timedelta(days=self.rng.randint(0, 3)),
                        status="graded" if graded else "submitted",
                        score=score,
                    ))
                AssignmentSubmission.objects.bulk_create(submissions)
                self.created["submissions"] += len(submissions)

        self._announce(
            f"Course content: {self.created['course_content']} items "
            f"({self.created['assignments']} assignments, {self.created['submissions']} submissions)."
        )

    # ------------------------------------------------------------------
    # Notifications & outbox (section 22/27)
    # ------------------------------------------------------------------

    def _create_notifications_and_outbox(self):
        """
        In-app Notification rows via notifications.services.notify_many()
        (a synchronous DB write, no Celery/email side effect - safe to
        call for real here). EmailOutboxEvent rows are created DIRECTLY
        (bypassing notifications.services.queue_email()'s async Celery
        dispatch) with pre-set terminal statuses, exactly mirroring
        seed_demo_school.py's own deliberate avoidance of any real
        outbound email - section 27 forbids a seeder ever sending real
        email/SMS.
        """
        from notifications.models import EmailOutboxEvent
        from notifications.services import notify_many
        from profiles.models import Profile

        recipient_ids = list(
            Profile.objects.exclude(user_id=None).values_list("user_id", flat=True)[:300]
        )
        if not recipient_ids:
            self._announce("Notifications: skipped (no portal accounts).")
            return

        templates = [
            ("Examination Timetable Published", "The Half-Yearly Examination timetable has been published. Please check the portal.", "exam"),
            ("Fee Payment Received", "Your fee payment has been received and recorded.", "fee"),
            ("Attendance Updated", "Attendance for your section has been updated for today.", "attendance"),
            ("Examination Result Published", "Your examination result has been published. Please log in to view it.", "exam"),
            ("New Assignment Posted", "A new assignment has been posted. Please check the course content section.", "course_content"),
            ("Fee Payment Overdue", "A fee payment is overdue. Please clear the outstanding balance at the earliest.", "fee"),
        ]

        created_notifications = []
        for recipient_id in recipient_ids:
            title, body, category = self.rng.choice(templates)
            notif = notify_many(recipient_user_ids=[recipient_id], title=title, body=body, category=category)[0]
            if self.rng.random() < 0.55:
                notif.is_read = True
                notif.read_at = timezone.now()
                created_notifications.append(notif)
        if created_notifications:
            from notifications.models import Notification

            Notification.objects.bulk_update(created_notifications, ["is_read", "read_at"])
        self.created["notifications"] = len(recipient_ids)

        statuses_and_errors = [
            ("sent", "", None), ("sent", "", None), ("pending", "", None),
            ("retrying", "Temporary SMTP timeout.", "temporary"), ("failed", "Mailbox does not exist.", "permanent"),
        ]
        sample_emails = [f"outbox_sample_{i}@{self.EMAIL_DOMAIN_ALT}" for i in range(len(statuses_and_errors))]
        for (status, error, error_type), email in zip(statuses_and_errors, sample_emails):
            EmailOutboxEvent.objects.create(
                to_email=email, subject="Examination results available",
                body="Your examination results are now available on the portal.",
                status=status, last_error=error, error_type=error_type or "",
            )
            self.created["email_outbox_events"] += 1

        self._announce(
            f"Notifications: {self.created['notifications']}, "
            f"outbox samples: {self.created['email_outbox_events']}."
        )

    # ------------------------------------------------------------------
    # Demo accounts (section 26)
    # ------------------------------------------------------------------

    def _create_demo_accounts(self):
        from accounts.models import User
        from profiles.models import Profile
        from roles.models import Role, UserRole

        admin_username = self._unique_username("admin", 0)
        admin_email = f"{admin_username}@{self.EMAIL_DOMAIN}"
        user, profile = self._create_user_and_profile(
            username=admin_username, email=admin_email, first_name="Ananya", last_name="Chatterjee",
            gender="female", dob=date(1985, 4, 12), phone=self._random_phone(),
            address=self._random_address("bengal"), role_slug="owner",
        )
        self.demo_logins.insert(0, ("Admin (Owner)", admin_email, self.DEMO_PASSWORD))

    # ------------------------------------------------------------------
    # Validation (section 29)
    # ------------------------------------------------------------------

    def _validate_seeded_data(self):
        from django.db.models import Count, F, Sum

        from attendance.models import StudentAttendance
        from examinations.models import ExamMark, ExamResult
        from families.models import StudentParentRelation
        from fees.models import StudentFee
        from students.models import Student, StudentLevel

        issues = []

        students_without_profile = Student.objects.filter(profile__isnull=True).count()
        if students_without_profile:
            issues.append(f"{students_without_profile} student(s) with no profile")

        students_without_current_enrollment = Student.objects.filter(
            status="active"
        ).exclude(
            id__in=StudentLevel.objects.filter(is_current=True).values_list("student_id", flat=True)
        ).count()
        if students_without_current_enrollment:
            issues.append(f"{students_without_current_enrollment} active student(s) with no current enrollment")

        orphan_relations = StudentParentRelation.objects.filter(student__isnull=True).count()
        orphan_relations += StudentParentRelation.objects.filter(parent__isnull=True).count()
        if orphan_relations:
            issues.append(f"{orphan_relations} orphan family relation(s)")

        orphan_marks = ExamMark.objects.filter(student__isnull=True).count()
        if orphan_marks:
            issues.append(f"{orphan_marks} exam mark(s) with no student")

        orphan_results = ExamResult.objects.filter(student__isnull=True).count()
        if orphan_results:
            issues.append(f"{orphan_results} exam result(s) with no student")

        orphan_attendance = StudentAttendance.objects.filter(student__isnull=True).count()
        if orphan_attendance:
            issues.append(f"{orphan_attendance} attendance record(s) with no student")

        over_allocated = (
            StudentFee.objects.annotate(_allocated=Sum("allocations__amount"))
            .filter(_allocated__gt=F("amount_due") - F("discount_amount"))
            .count()
        )
        if over_allocated:
            issues.append(f"{over_allocated} StudentFee row(s) over-allocated beyond amount_due")

        duplicate_enrollment_ids = (
            Student.objects.values("enrollment_id").annotate(n=Count("id")).filter(n__gt=1).count()
        )
        if duplicate_enrollment_ids:
            issues.append(f"{duplicate_enrollment_ids} duplicate enrollment_id value(s)")

        self._validation_issues = issues

    # ------------------------------------------------------------------
    # Summary (section 30)
    # ------------------------------------------------------------------

    def _print_summary(self):
        elapsed = time_module.monotonic() - self.started_at
        c = self.created

        self._announce("=" * 60)
        self._announce("REALISTIC DEMO DATA SEED COMPLETE")
        self._announce("=" * 60)
        self._announce(f"\nSchool:\n{self.ORG_NAME}")
        self._announce(f"\nLocation:\nBhubaneswar, Odisha")
        self._announce(f"\nSchema:\n{self.SCHEMA_NAME}")
        self._announce(f"\nAcademic Years:\n{len(self.academic_years)} ({', '.join(self.academic_years)})")
        self._announce(f"\nStudents:\n{c['students']}")
        self._announce(f"\nParents:\n{c['parents']}")
        self._announce(f"\nStaff:\n{c['staff']}")
        self._announce(f"\nInstructors:\n{c['instructors']}")
        self._announce(f"\nLevels:\n{c['levels']}")
        self._announce(f"\nSections:\n{c['sections']}")
        self._announce(f"\nSubjects:\n{c['subjects']}")
        self._announce(f"\nAttendance Sessions:\n{c['attendance_sessions']}")
        self._announce(f"\nAttendance Records:\n{c['attendance_records']}")
        self._announce(f"\nExaminations:\n{c['examinations']}")
        self._announce(f"\nExam Marks:\n{c['exam_marks']}")
        self._announce(f"\nExam Results:\n{c['exam_results']}")
        self._announce(f"\nStudent Fees:\n{c['student_fees']}")
        self._announce(f"\nPayments:\n{c['payments']}")
        self._announce(f"\nNotifications:\n{c['notifications']}")
        self._announce(f"\nCourse Content:\n{c['course_content']}")
        self._announce(f"\nAssignments:\n{c['assignments']}")
        self._announce(f"\nPromotion Records:\n{c['promotion_records']}")
        self._announce("\n" + "=" * 60)
        if self._validation_issues:
            self._announce(f"Validation: FAILED ({len(self._validation_issues)} issue(s))")
            for issue in self._validation_issues:
                self._announce(f"  - {issue}")
        else:
            self._announce("Validation: PASSED")
        self._announce("=" * 60)
        self._announce(f"\nSeed runtime: {elapsed:.1f}s")
        self._announce(f"Seed value: {self.seed}")
        self._announce("\nDemo logins (development only, password shared below):")
        for label, email, password in self.demo_logins:
            self._announce(f"  {label:18s} {email:45s} {password}")
        self._announce(f"\nAll accounts share password: {self.DEMO_PASSWORD}")
        self._announce(f"All emails use the RFC 2606 reserved domains {self.EMAIL_DOMAIN} / {self.EMAIL_DOMAIN_ALT} - never real, never deliverable.")
