"""The joining-document checklist. Creates a tenant schema, so it needs a disposable PostgreSQL database."""
import shutil
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from roles.signals import seed_default_roles

from .documents import (
    ChecklistOverviewView,
    DocumentItemView,
    DocumentTypeDetailView,
    DocumentTypesView,
    StaffDocumentsView,
    create_checklist,
)
from .models import StaffDocumentItem, StaffDocumentType, StaffMember

User = get_user_model()
PDF = b"%PDF-1.4 a scanned certificate"


class StaffDocumentTests(TransactionTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        connection.set_schema_to_public()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.school = Organization.objects.create(schema_name=f"sdoc_{suffix}", name="Docs School")
        Domain.objects.create(domain=f"sdoc-{suffix}.localhost", tenant=self.school, is_primary=True)
        self.factory = APIRequestFactory()
        with tenant_context(self.school):
            seed_default_roles()
            self.owner = self._user("owner", "owner")
            self.clerk = self._user("student", "clerk")  # a role without staff permissions
            self.staff = self._member("Asha")

    def _user(self, role_slug, label):
        user = User.objects.create_user(
            username=f"{label}_{uuid.uuid4().hex[:6]}@school.com", email=f"{label}@school.com", password="Password123!"
        )
        UserRole.objects.create(user=user, role=Role.objects.get(slug=role_slug))
        return user

    def _member(self, name):
        profile = Profile.objects.create(first_name=name, last_name="Rao", email=f"{name.lower()}@school.com")
        return StaffMember.objects.create(profile=profile, employee_id=f"E-{uuid.uuid4().hex[:5]}", designation="Teacher")

    def _call(self, view, method, user, data=None, fmt="json", **kwargs):
        request = getattr(self.factory, method)("/x/", data, format=fmt) if method != "get" else self.factory.get("/x/", data)
        request.tenant = self.school
        force_authenticate(request, user=user)
        return view.as_view()(request, **kwargs)

    def _types(self, *names):
        for index, name in enumerate(names):
            StaffDocumentType.objects.create(name=name, order=index)

    def test_the_standard_list_is_managed_by_people_who_can_change_staff_and_names_are_not_repeated(self):
        with tenant_context(self.school):
            self.assertEqual(self._call(DocumentTypesView, "get", self.clerk).status_code, 403)
            self.assertEqual(self._call(DocumentTypesView, "post", self.clerk, {"name": "PAN card"}).status_code, 403)
            made = self._call(DocumentTypesView, "post", self.owner, {"name": "  PAN   card "})
            self.assertEqual((made.status_code, made.data["name"]), (201, "PAN card"))
            self.assertEqual(self._call(DocumentTypesView, "post", self.owner, {"name": "pan CARD"}).status_code, 400)
            self.assertEqual(self._call(DocumentTypesView, "post", self.owner, {"name": " "}).status_code, 400)
            off = self._call(DocumentTypeDetailView, "patch", self.owner, {"is_active": False}, pk=made.data["id"])
            self.assertEqual((off.status_code, off.data["is_active"]), (200, False))
            self.assertEqual(self._call(DocumentTypesView, "get", self.owner).status_code, 200)

    def test_starting_a_checklist_adds_each_active_document_once_and_never_touches_what_has_come_in(self):
        with tenant_context(self.school):
            self._types("Aadhaar card", "Degree certificate", "Old reference")
            StaffDocumentType.objects.filter(name="Old reference").update(is_active=False)
            self.assertEqual(create_checklist(self.staff), 2)
            self.assertEqual(create_checklist(self.staff), 0)  # nothing duplicated
            item = StaffDocumentItem.objects.get(staff=self.staff, name="Aadhaar card")
            self._call(DocumentItemView, "patch", self.owner, {"status": "received"}, pk=item.pk)
            self._types("Police verification")
            self.assertEqual(create_checklist(self.staff), 1)
            item.refresh_from_db()
            self.assertEqual(item.status, "received")  # a later top-up leaves received items alone
            started = self._call(StaffDocumentsView, "post", self.owner, {}, staff_id=self.staff.pk)
            self.assertEqual(started.status_code, 201)
            self.assertEqual(len(started.data), 3)

    def test_a_one_off_item_can_be_added_but_not_twice(self):
        with tenant_context(self.school):
            added = self._call(StaffDocumentsView, "post", self.owner, {"name": "Medical fitness"}, staff_id=self.staff.pk)
            self.assertEqual((added.status_code, [i["name"] for i in added.data]), (201, ["Medical fitness"]))
            again = self._call(StaffDocumentsView, "post", self.owner, {"name": "medical FITNESS"}, staff_id=self.staff.pk)
            self.assertEqual(again.status_code, 400)
            self.assertEqual(self._call(StaffDocumentsView, "get", self.clerk, staff_id=self.staff.pk).status_code, 403)
            self.assertEqual(self._call(StaffDocumentsView, "post", self.clerk, {"name": "x"}, staff_id=self.staff.pk).status_code, 403)

    def test_marking_received_waived_or_pending_follows_the_rules(self):
        with tenant_context(self.school):
            self._types("Aadhaar card")
            create_checklist(self.staff)
            item = StaffDocumentItem.objects.get()

            def patch(data, user=None):
                return self._call(DocumentItemView, "patch", user or self.owner, data, pk=item.pk)

            self.assertEqual(patch({"status": "received"}, self.clerk).status_code, 403)
            self.assertEqual(patch({"status": "later"}).status_code, 400)
            self.assertEqual(patch({"status": "waived"}).status_code, 400)  # needs a reason
            self.assertEqual(patch({"status": "received", "received_on": "2999-01-01"}).status_code, 400)
            self.assertEqual(patch({"status": "received", "received_on": "nonsense"}).status_code, 400)
            ok = patch({"status": "received", "received_on": "2026-01-05"})
            self.assertEqual((ok.status_code, ok.data["received_on"]), (200, "2026-01-05"))
            waived = patch({"status": "waived", "note": "Not applicable for contract staff"})
            self.assertEqual((waived.data["status"], waived.data["received_on"]), ("waived", None))
            back = patch({"status": "pending"})
            self.assertEqual((back.data["status"], back.data["received_on"]), ("pending", None))

    def test_the_file_is_checked_attached_and_only_served_to_permitted_people(self):
        with override_settings(MEDIA_ROOT=self.media), tenant_context(self.school):
            self._types("Degree certificate")
            create_checklist(self.staff)
            item = StaffDocumentItem.objects.get()

            def upload(name, content):
                return self._call(
                    DocumentItemView, "post", self.owner, {"file": SimpleUploadedFile(name, content)}, fmt="multipart", pk=item.pk
                )

            self.assertEqual(upload("cert.pdf", b"not really a pdf").status_code, 400)  # contents must match the extension
            self.assertEqual(upload("cert.exe", PDF).status_code, 400)
            self.assertEqual(upload("cert.pdf", PDF + b"x" * (5 * 1024 * 1024)).status_code, 400)
            self.assertEqual(self._call(DocumentItemView, "post", self.owner, {}, fmt="multipart", pk=item.pk).status_code, 400)
            self.assertEqual(self._call(DocumentItemView, "get", self.owner, pk=item.pk).status_code, 404)  # nothing yet
            done = upload("cert.pdf", PDF)
            self.assertEqual(done.status_code, 200, done.data)
            self.assertEqual((done.data["status"], done.data["has_file"]), ("received", True))  # attaching marks it received
            self.assertNotIn("file", done.data)  # the storage path is never exposed
            served = self._call(DocumentItemView, "get", self.owner, pk=item.pk)
            self.assertEqual(served.status_code, 200)
            self.assertEqual(b"".join(served.streaming_content), PDF)
            self.assertEqual(self._call(DocumentItemView, "get", self.clerk, pk=item.pk).status_code, 403)

    def test_the_overview_lists_who_is_still_owing_documents_most_outstanding_first(self):
        with tenant_context(self.school):
            self._types("Aadhaar card", "Degree certificate")
            other = self._member("Bina")
            create_checklist(self.staff)
            create_checklist(other)
            for item in StaffDocumentItem.objects.filter(staff=other):
                self._call(DocumentItemView, "patch", self.owner, {"status": "received"}, pk=item.pk)
            nobody = self._member("Cara")  # never given a checklist: not listed
            self.assertEqual(self._call(ChecklistOverviewView, "get", self.clerk).status_code, 403)
            everyone = self._call(ChecklistOverviewView, "get", self.owner)
            self.assertEqual([(r["name"], r["pending"], r["received"]) for r in everyone.data], [("Asha Rao", 2, 0), ("Bina Rao", 0, 2)])
            owing = self._call(ChecklistOverviewView, "get", self.owner, {"outstanding": "true"})
            self.assertEqual([r["name"] for r in owing.data], ["Asha Rao"])
            self.assertNotIn(nobody.pk, [r["staff"] for r in everyone.data])
