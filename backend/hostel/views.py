"""Hostel API. view_hostel reads; manage_hostel changes. A linked parent sees their child's room."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from core.query_params import uuid_param
from roles.permissions import HasPermission

from . import services
from .models import Hostel, HostelAllocation, HostelRoom


def _name(student):
    p = student.profile
    return f"{p.first_name} {p.last_name}".strip()


class HostelSerializer(serializers.ModelSerializer):
    warden_name = serializers.SerializerMethodField()
    fee_structure_label = serializers.SerializerMethodField()
    rooms = serializers.IntegerField(read_only=True, source="room_count")
    beds = serializers.IntegerField(read_only=True, source="bed_count")
    occupied = serializers.IntegerField(read_only=True, source="occupied_count")

    class Meta:
        model = Hostel
        fields = [
            "id", "name", "gender", "warden", "warden_name", "warden_phone", "fee_structure", "fee_structure_label",
            "is_active", "rooms", "beds", "occupied",
        ]
        read_only_fields = ["id"]

    def get_warden_name(self, obj):
        if not obj.warden_id:
            return None
        p = obj.warden.profile
        return f"{p.first_name} {p.last_name}".strip()

    def get_fee_structure_label(self, obj):
        s = obj.fee_structure
        return f"{s.fee_head.name} · {s.academic_year} · ₹{s.amount}" if s else None


class RoomSerializer(serializers.ModelSerializer):
    occupied = serializers.IntegerField(read_only=True, source="occupied_count", default=0)
    occupants = serializers.SerializerMethodField()

    class Meta:
        model = HostelRoom
        fields = ["id", "hostel", "number", "floor", "capacity", "is_active", "occupied", "occupants"]
        read_only_fields = ["id"]

    def get_occupants(self, obj):
        current = getattr(obj, "current_allocations", None)
        if current is None:
            current = obj.allocations.filter(end_date__isnull=True).select_related("student__profile")
        return [{"allocation": str(a.id), "student": str(a.student_id), "name": _name(a.student), "since": a.start_date} for a in current]

    def validate(self, attrs):
        if self.instance and "capacity" in attrs:
            in_room = self.instance.allocations.filter(end_date__isnull=True).count()
            if attrs["capacity"] < in_room:
                raise serializers.ValidationError({"capacity": f"{in_room} students live in this room now."})
        return attrs


class AllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    room_number = serializers.CharField(source="room.number", read_only=True)
    hostel_name = serializers.CharField(source="room.hostel.name", read_only=True)
    warden_phone = serializers.CharField(source="room.hostel.warden_phone", read_only=True)

    class Meta:
        model = HostelAllocation
        fields = ["id", "student", "student_name", "room", "room_number", "hostel_name", "warden_phone",
                  "start_date", "end_date", "note"]

    def get_student_name(self, obj):
        return _name(obj.student)


class _Perms:
    def get_permissions(self):
        code = "view_hostel" if self.request.method in ("GET", "HEAD", "OPTIONS") else "manage_hostel"
        return [IsAuthenticated(), HasPermission(code)]


class HostelViewSet(_Perms, viewsets.ModelViewSet):
    serializer_class = HostelSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Hostel.objects.select_related("warden__profile", "fee_structure__fee_head").annotate(
            room_count=Count("rooms", filter=Q(rooms__is_active=True), distinct=True),
        )

    def _with_beds(self, hostels):
        from django.db.models import Sum

        for h in hostels:
            h.bed_count = h.rooms.filter(is_active=True).aggregate(n=Sum("capacity"))["n"] or 0
            h.occupied_count = HostelAllocation.objects.filter(room__hostel=h, end_date__isnull=True).count()
        return hostels

    def list(self, request, *args, **kwargs):
        return Response(HostelSerializer(self._with_beds(list(self.get_queryset())), many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(HostelSerializer(self._with_beds([self.get_object()])[0]).data)

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="hostel_created", model_name="Hostel", object_id=obj.id, changes={"name": obj.name})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="hostel_updated", model_name="Hostel", object_id=obj.id,
                   changes={k: str(v) for k, v in serializer.validated_data.items()})

    def _for_response(self, obj):
        return HostelSerializer(self._with_beds([self.get_queryset().get(id=obj.id)])[0]).data

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        self.perform_create(s)
        return Response(self._for_response(s.instance), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        s = self.get_serializer(self.get_object(), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        self.perform_update(s)
        return Response(self._for_response(s.instance))

    @action(detail=True, methods=["get", "post"], url_path="charge")
    def charge(self, request, pk=None):
        """GET: preview the hostel fee for current boarders. POST: charge it (safe to repeat)."""
        from fees import charging

        if not HasPermission("manage_hostel").has_permission(request, self) or not HasPermission(
            "manage_fee_structures"
        ).has_permission(request, self):
            raise PermissionDenied("Charging hostel fees needs Manage Hostel and Manage Fee Structures.")
        hostel = self.get_object()
        structure = hostel.fee_structure
        if structure is None:
            raise serializers.ValidationError("Choose this hostel's fee structure first.")
        who = services.boarder_enrollments(hostel)
        if request.method == "GET":
            return Response(charging.plan_charge(structure, who(structure)).summary())
        summary = charging.charge_structure(structure, who).summary()
        log_action(request, action="hostel_fee_charged", model_name="Hostel", object_id=hostel.id,
                   changes={"fees_created": summary["fees_to_create"], "amount": summary["amount_to_charge"]})
        return Response(summary, status=status.HTTP_201_CREATED)


class RoomViewSet(_Perms, viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        from django.db.models import Prefetch

        qs = HostelRoom.objects.select_related("hostel").annotate(
            occupied_count=Count("allocations", filter=Q(allocations__end_date__isnull=True))
        ).prefetch_related(Prefetch(
            "allocations", queryset=HostelAllocation.objects.filter(end_date__isnull=True).select_related("student__profile"),
            to_attr="current_allocations",
        ))
        hostel = uuid_param(self.request, "hostel")
        return qs.filter(hostel_id=hostel) if hostel else qs

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="hostel_room_created", model_name="HostelRoom", object_id=obj.id,
                   changes={"hostel": str(obj.hostel_id), "number": obj.number, "capacity": obj.capacity})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="hostel_room_updated", model_name="HostelRoom", object_id=obj.id,
                   changes={k: str(v) for k, v in serializer.validated_data.items()})


class AllocateSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    room = serializers.UUIDField()
    start_date = serializers.DateField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AllocateView(APIView):
    """POST /api/hostel/allocations/ - give a student a room, or move them to another."""

    permission_classes = [IsAuthenticated, HasPermission("manage_hostel")]

    def post(self, request):
        from students.models import Student

        s = AllocateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        student = get_object_or_404(Student.objects.select_related("profile"), id=s.validated_data["student"])
        room = get_object_or_404(HostelRoom, id=s.validated_data["room"])
        allocation = services.allocate(student=student, room=room, start_date=s.validated_data.get("start_date"),
                                       note=s.validated_data.get("note", ""))
        log_action(request, action="hostel_student_allocated", model_name="HostelAllocation", object_id=allocation.id,
                   changes={"student": str(student.id), "room": str(room.id)})
        return Response(AllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)


class VacateView(APIView):
    """POST /api/hostel/allocations/<id>/vacate/ - the student leaves the room."""

    permission_classes = [IsAuthenticated, HasPermission("manage_hostel")]

    def post(self, request, allocation_id):
        allocation = get_object_or_404(HostelAllocation.objects.select_related("student__profile", "room__hostel"), id=allocation_id)
        end = serializers.DateField(required=False).run_validation(request.data.get("end_date")) if request.data.get("end_date") else None
        allocation = services.vacate(allocation, end_date=end)
        log_action(request, action="hostel_student_vacated", model_name="HostelAllocation", object_id=allocation.id,
                   changes={"student": str(allocation.student_id), "end_date": str(allocation.end_date)})
        return Response(AllocationSerializer(allocation).data)


class StudentHostelView(APIView):
    """GET /api/hostel/students/<id>/ - a student's current room and past stays.
    Staff with view_hostel, or the student's linked parent."""

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from fees.services import get_child_for_parent, get_parent_for_user
        from students.models import Student

        student = get_object_or_404(Student, id=student_id)
        staff = HasPermission("view_hostel").has_permission(request, self) or HasPermission("manage_hostel").has_permission(request, self)
        parent = get_parent_for_user(request.user)
        if not staff and not (parent and get_child_for_parent(parent, student.id)):
            raise PermissionDenied("You cannot see this student's hostel details.")
        stays = student.hostel_allocations.select_related("room__hostel", "student__profile")
        data = AllocationSerializer(stays, many=True).data
        return Response({"current": next((d for d in data if d["end_date"] is None), None), "history": data})
