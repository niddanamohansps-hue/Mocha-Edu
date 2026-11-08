"""The joining-document checklist: what the school asks every new staff member for, and what has come in."""
import os

from django.conf import settings
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import permissions, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from core.dates import school_today
from roles.permissions import HasPermission

from .models import StaffDocumentItem, StaffDocumentType, StaffMember

MAX_BYTES = 5 * 1024 * 1024
# The first bytes of each accepted format. The extension alone is only a claim.
SIGNATURES = {
    "pdf": (b"%PDF-",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
}


def create_checklist(staff):
    """Give a staff member one pending item for each active standard document they do not have yet. Safe to call
    again: nothing is duplicated and nothing already received is touched. Returns the number added."""
    have = set(StaffDocumentItem.objects.filter(staff=staff).values_list("name", flat=True))
    added = 0
    for doc_type in StaffDocumentType.objects.filter(is_active=True):
        if doc_type.name not in have:
            StaffDocumentItem.objects.create(staff=staff, document_type=doc_type, name=doc_type.name)
            added += 1
    return added


def check_file(value):
    if value.size > MAX_BYTES:
        raise ValidationError({"file": ["The file must be 5 MB or smaller."]})
    extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if extension not in SIGNATURES:
        raise ValidationError({"file": ["Upload a PDF, JPG or PNG file."]})
    head = value.read(8)
    value.seek(0)
    if not any(head.startswith(sig) for sig in SIGNATURES[extension]):
        raise ValidationError({"file": [f"The file does not look like a valid {extension.upper()}."]})
    return value


class ItemSerializer(serializers.ModelSerializer):
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = StaffDocumentItem
        fields = ["id", "staff", "name", "status", "received_on", "note", "has_file", "updated_at"]
        read_only_fields = fields

    def get_has_file(self, obj):
        return bool(obj.file)


class TypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffDocumentType
        fields = ["id", "name", "order", "is_active"]
        extra_kwargs = {"name": {"validators": []}}

    def validate_name(self, value):
        value = " ".join((value or "").split())
        if not value:
            raise serializers.ValidationError("Give the document a name.")
        clash = StaffDocumentType.objects.filter(name__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("That document is already on the list.")
        return value


def _perm(request, write):
    return [permissions.IsAuthenticated(), HasPermission("change_staff" if write else "view_staff")]


class DocumentTypesView(APIView):
    """The school's standard checklist."""

    def get_permissions(self):
        return _perm(self.request, self.request.method != "GET")

    def get(self, request):
        return Response(TypeSerializer(StaffDocumentType.objects.all(), many=True).data)

    def post(self, request):
        serializer = TypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc_type = serializer.save()
        log_action(request, "staff_document_type_added", "StaffDocumentType", str(doc_type.id), {"name": doc_type.name})
        return Response(TypeSerializer(doc_type).data, status=201)


class DocumentTypeDetailView(APIView):
    def get_permissions(self):
        return _perm(self.request, True)

    def patch(self, request, pk):
        try:
            doc_type = StaffDocumentType.objects.get(pk=pk)
        except (StaffDocumentType.DoesNotExist, ValueError, TypeError):
            raise Http404
        serializer = TypeSerializer(doc_type, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        doc_type = serializer.save()
        log_action(request, "staff_document_type_changed", "StaffDocumentType", str(doc_type.id), {})
        return Response(TypeSerializer(doc_type).data)


class ChecklistOverviewView(APIView):
    """Staff who have a checklist, with how much of it is still outstanding."""

    def get_permissions(self):
        return _perm(self.request, False)

    def get(self, request):
        rows = (
            StaffMember.objects.filter(document_items__isnull=False, is_active=True)
            .select_related("profile")
            .annotate(
                pending=Count("document_items", filter=Q(document_items__status="pending"), distinct=True),
                received=Count("document_items", filter=Q(document_items__status="received"), distinct=True),
                total=Count("document_items", distinct=True),
            )
            .order_by("-pending", "profile__first_name")
        )
        if request.query_params.get("outstanding") == "true":
            rows = rows.filter(pending__gt=0)
        return Response(
            [
                {
                    "staff": r.pk,
                    "name": f"{r.profile.first_name} {r.profile.last_name}".strip(),
                    "employee_id": r.employee_id,
                    "designation": r.designation,
                    "joining_date": r.joining_date,
                    "pending": r.pending,
                    "received": r.received,
                    "total": r.total,
                }
                for r in rows
            ]
        )


def _staff(pk):
    try:
        return StaffMember.objects.get(pk=pk)
    except (StaffMember.DoesNotExist, ValueError, TypeError):
        raise Http404


class StaffDocumentsView(APIView):
    """One staff member's checklist: list it, start it from the standard list, or add a one-off item."""

    def get_permissions(self):
        return _perm(self.request, self.request.method != "GET")

    def get(self, request, staff_id):
        staff = _staff(staff_id)
        return Response(ItemSerializer(staff.document_items.all(), many=True).data)

    def post(self, request, staff_id):
        staff = _staff(staff_id)
        name = " ".join(str(request.data.get("name") or "").split())
        if not name:
            added = create_checklist(staff)
            log_action(request, "staff_checklist_started", "StaffMember", str(staff.id), {"added": added})
        else:
            if len(name) > 100:
                raise ValidationError({"name": ["Keep the name under 100 characters."]})
            if staff.document_items.filter(name__iexact=name).exists():
                raise ValidationError({"name": ["That document is already on this checklist."]})
            StaffDocumentItem.objects.create(staff=staff, name=name)
            log_action(request, "staff_document_item_added", "StaffMember", str(staff.id), {"name": name})
        return Response(ItemSerializer(staff.document_items.all(), many=True).data, status=201)


class DocumentItemView(APIView):
    """Mark an item received or not needed, with the date and a note; or attach the scanned file."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        return _perm(self.request, self.request.method != "GET")

    def _item(self, pk):
        try:
            return StaffDocumentItem.objects.select_related("staff").get(pk=pk)
        except (StaffDocumentItem.DoesNotExist, ValueError, TypeError):
            raise Http404

    def patch(self, request, pk):
        item = self._item(pk)
        data = request.data
        new_status = data.get("status", item.status)
        if new_status not in StaffDocumentItem.Status.values:
            raise ValidationError({"status": ["Choose pending, received or waived."]})
        note = str(data.get("note", item.note) or "").strip()[:500]
        if new_status == StaffDocumentItem.Status.WAIVED and not note:
            raise ValidationError({"note": ["Say why this document is not needed."]})
        received_on = item.received_on
        if new_status == StaffDocumentItem.Status.RECEIVED:
            raw = data.get("received_on")
            if raw:
                from django.utils.dateparse import parse_date

                received_on = parse_date(str(raw))
                if received_on is None:
                    raise ValidationError({"received_on": ["Enter a valid date."]})
                if received_on > school_today():
                    raise ValidationError({"received_on": ["The date cannot be in the future."]})
            received_on = received_on or school_today()
        else:
            received_on = None
        item.status, item.note, item.received_on = new_status, note, received_on
        item.updated_by_user_id = request.user.id
        item.save(update_fields=["status", "note", "received_on", "updated_by_user_id", "updated_at"])
        log_action(request, "staff_document_updated", "StaffDocumentItem", str(item.id), {"status": new_status})
        return Response(ItemSerializer(item).data)

    def post(self, request, pk):
        """Attach the file. A pending item becomes received, dated today."""
        item = self._item(pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Choose a file to upload."]})
        item.file = check_file(upload)
        if item.status != StaffDocumentItem.Status.RECEIVED:
            item.status = StaffDocumentItem.Status.RECEIVED
            item.received_on = school_today()
        item.updated_by_user_id = request.user.id
        item.save()
        log_action(request, "staff_document_file_added", "StaffDocumentItem", str(item.id), {})
        return Response(ItemSerializer(item).data)

    def get(self, request, pk):
        """The scanned file, through a permission-checked response and never a /media/ URL."""
        item = self._item(pk)
        if not item.file:
            raise Http404("No file was uploaded for this document.")
        log_action(request, "staff_document_file_viewed", "StaffDocumentItem", str(item.id), {})
        filename = os.path.basename(item.file.name)
        if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
            response = HttpResponse()
            prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/")
            response["X-Accel-Redirect"] = f"{prefix}/{item.file.name}"
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        try:
            return FileResponse(item.file.open("rb"), filename=filename)
        except OSError:
            raise Http404("The file could not be read from storage.")
