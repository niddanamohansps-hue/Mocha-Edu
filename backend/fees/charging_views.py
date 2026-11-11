"""API for instalment plans, charging a structure to its class, and concessions."""
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from roles.permissions import HasPermission

from . import charging
from .models import ConcessionType, FeeInstallment, FeeStructure, StudentConcession, StudentFee
from .services import get_staff_member_for_user


class FeeInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInstallment
        fields = ["id", "name", "percent", "due_date", "position"]
        read_only_fields = ["id", "position"]


class InstallmentPlanSerializer(serializers.Serializer):
    installments = serializers.ListField(
        child=serializers.DictField(), allow_empty=True, max_length=24
    )

    def validate_installments(self, rows):
        row_serializer = FeeInstallmentSerializer(data=rows, many=True)
        row_serializer.is_valid(raise_exception=True)
        return row_serializer.validated_data


def _plan_payload(structure):
    return {
        "structure": str(structure.id),
        "installments": FeeInstallmentSerializer(structure.installments.all(), many=True).data,
        "locked": StudentFee.objects.filter(fee_structure=structure).exists(),
    }


class InstallmentPlanView(APIView):
    """GET / PUT /api/fees/structures/<id>/installments/ - read or replace the instalment plan."""

    def get_permissions(self):
        code = "view_fees" if self.request.method == "GET" else "manage_fee_structures"
        return [IsAuthenticated(), HasPermission(code)]

    def get(self, request, structure_id):
        return Response(_plan_payload(get_object_or_404(FeeStructure, id=structure_id)))

    def put(self, request, structure_id):
        structure = get_object_or_404(FeeStructure, id=structure_id)
        serializer = InstallmentPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = charging.replace_installments(structure, serializer.validated_data["installments"])
        log_action(
            request, action="fee_installments_set", model_name="FeeStructure", object_id=structure.id,
            changes={"installments": [{"name": r.name, "percent": str(r.percent), "due_date": str(r.due_date)} for r in rows]},
        )
        return Response(_plan_payload(structure))


class ChargeStructureView(APIView):
    """GET  /api/fees/structures/<id>/charge/ - preview who would be charged what.
    POST /api/fees/structures/<id>/charge/ - charge them. Safe to repeat."""

    permission_classes = [IsAuthenticated, HasPermission("manage_fee_structures")]

    def get(self, request, structure_id):
        structure = get_object_or_404(FeeStructure.objects.select_related("fee_head"), id=structure_id)
        return Response(charging.plan_charge(structure).summary())

    def post(self, request, structure_id):
        structure = get_object_or_404(FeeStructure.objects.select_related("fee_head"), id=structure_id)
        summary = charging.charge_structure(structure).summary()
        log_action(
            request, action="fee_structure_charged", model_name="FeeStructure", object_id=structure.id,
            changes={
                "students_charged": summary["students_to_charge"], "fees_created": summary["fees_to_create"],
                "amount": summary["amount_to_charge"], "concessions": summary["concession_total"],
            },
        )
        return Response(summary, status=status.HTTP_201_CREATED)


class ConcessionTypeSerializer(serializers.ModelSerializer):
    fee_head_name = serializers.CharField(source="fee_head.name", read_only=True, default=None)

    class Meta:
        model = ConcessionType
        fields = ["id", "name", "kind", "value", "fee_head", "fee_head_name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        value = attrs.get("value", getattr(self.instance, "value", None))
        if value is not None and value <= 0:
            raise serializers.ValidationError({"value": "Enter an amount above zero."})
        if kind == "percent" and value is not None and value > 100:
            raise serializers.ValidationError({"value": "A percentage cannot be more than 100."})
        return attrs


class _ManageOrView:
    def get_permissions(self):
        code = "view_fees" if self.action in ("list", "retrieve") else "manage_fee_structures"
        return [IsAuthenticated(), HasPermission(code)]


class ConcessionTypeViewSet(_ManageOrView, viewsets.ModelViewSet):
    """Concession and scholarship types. No DELETE: switch one off with is_active instead."""

    queryset = ConcessionType.objects.select_related("fee_head")
    serializer_class = ConcessionTypeSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "kind"]

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="concession_type_created", model_name="ConcessionType", object_id=obj.id,
                   changes={"name": obj.name, "kind": obj.kind, "value": str(obj.value)})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="concession_type_updated", model_name="ConcessionType", object_id=obj.id,
                   changes={k: str(v) for k, v in serializer.validated_data.items()})


class StudentConcessionSerializer(serializers.ModelSerializer):
    concession_name = serializers.CharField(source="concession_type.name", read_only=True)
    kind = serializers.CharField(source="concession_type.kind", read_only=True)
    value = serializers.DecimalField(source="concession_type.value", max_digits=10, decimal_places=2, read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentConcession
        fields = [
            "id", "student", "student_name", "concession_type", "concession_name", "kind", "value",
            "academic_year", "note", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}".strip()

    def validate(self, attrs):
        ctype = attrs.get("concession_type")
        if ctype is not None and not ctype.is_active and self.instance is None:
            raise serializers.ValidationError({"concession_type": "This concession is switched off."})
        return attrs


class StudentConcessionViewSet(_ManageOrView, viewsets.ModelViewSet):
    """Concessions given to students. Given concessions apply to fees charged afterwards;
    fees already charged keep their amounts. No DELETE: switch one off instead."""

    queryset = StudentConcession.objects.select_related("concession_type", "student__profile")
    serializer_class = StudentConcessionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "academic_year", "concession_type", "is_active"]

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action in ("update", "partial_update"):
            for name in ("student", "concession_type", "academic_year"):
                serializer.fields[name].read_only = True
        return serializer

    def perform_create(self, serializer):
        obj = serializer.save(granted_by=get_staff_member_for_user(self.request.user))
        log_action(self.request, action="concession_granted", model_name="StudentConcession", object_id=obj.id,
                   changes={"student": str(obj.student_id), "concession": obj.concession_type.name,
                            "academic_year": obj.academic_year})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action="concession_updated", model_name="StudentConcession", object_id=obj.id,
                   changes={k: str(v) for k, v in serializer.validated_data.items()})
