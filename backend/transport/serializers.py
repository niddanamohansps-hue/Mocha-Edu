import re

from rest_framework import serializers

from . import services
from .models import Driver, Route, RouteStop, StudentTransport, TransportBill, Vehicle


def person_name(profile):
    return f"{profile.first_name} {profile.last_name}".strip()


class VehicleSerializer(serializers.ModelSerializer):
    routes_count = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = ("id", "registration_number", "name", "make_model", "capacity", "insurance_expiry", "fitness_expiry",
                  "is_active", "notes", "routes_count", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_routes_count(self, vehicle):
        return vehicle.routes.count()

    def validate_registration_number(self, value):
        return value.strip().upper()

    def validate_capacity(self, value):
        if self.instance is not None:
            fullest = max((services.seats_taken(route) for route in self.instance.routes.all()), default=0)
            if value < fullest:
                raise serializers.ValidationError(f"A route using this bus already has {fullest} students seated.")
        return value


class DriverSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = ("id", "full_name", "role", "phone", "license_number", "license_expiry", "staff", "staff_name",
                  "is_active", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_staff_name(self, driver):
        return person_name(driver.staff.profile) if driver.staff_id else ""

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the name.")
        return value


class RouteSerializer(serializers.ModelSerializer):
    vehicle_registration = serializers.CharField(source="vehicle.registration_number", read_only=True, default="")
    capacity = serializers.IntegerField(source="vehicle.capacity", read_only=True, default=None)
    driver_name = serializers.CharField(source="driver.full_name", read_only=True, default="")
    helper_name = serializers.CharField(source="helper.full_name", read_only=True, default="")
    seats_taken = serializers.SerializerMethodField()
    stops_count = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = ("id", "name", "vehicle", "vehicle_registration", "capacity", "driver", "driver_name", "helper",
                  "helper_name", "start_point", "end_point", "monthly_fee", "is_active", "notes", "seats_taken",
                  "stops_count", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_seats_taken(self, route):
        return services.seats_taken(route)

    def get_stops_count(self, route):
        return route.stops.count()

    def validate(self, attrs):
        vehicle = attrs.get("vehicle", getattr(self.instance, "vehicle", None))
        driver = attrs.get("driver", getattr(self.instance, "driver", None))
        helper = attrs.get("helper", getattr(self.instance, "helper", None))
        if driver is not None and driver.role != Driver.Role.DRIVER:
            raise serializers.ValidationError({"driver": "Choose a person recorded as a driver."})
        if helper is not None and helper.role != Driver.Role.HELPER:
            raise serializers.ValidationError({"helper": "Choose a person recorded as a helper."})
        if self.instance is not None:
            taken = services.seats_taken(self.instance)
            if vehicle is not None and vehicle.capacity < taken:
                raise serializers.ValidationError(
                    {"vehicle": f"This route already has {taken} students seated; {vehicle.registration_number} has only {vehicle.capacity} seats."}
                )
            if taken and vehicle is None:
                raise serializers.ValidationError({"vehicle": "Students are seated on this route, so it needs a bus."})
            if attrs.get("is_active") is False and taken:
                raise serializers.ValidationError({"is_active": f"{taken} students still use this route. Move them first."})
        return attrs


class RouteStopSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source="route.name", read_only=True)
    students = serializers.SerializerMethodField()
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = RouteStop
        fields = ("id", "route", "route_name", "name", "sequence", "pickup_time", "drop_time", "monthly_fee", "fee",
                  "students", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_students(self, stop):
        return stop.assignments.filter(end_date__isnull=True).count()

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the stop name.")
        return value

    def validate_route(self, route):
        if self.instance is not None and route.pk != self.instance.route_id:
            raise serializers.ValidationError("A stop cannot be moved to another route. Create a new stop there.")
        return route


class StudentTransportSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    route_name = serializers.CharField(source="route.name", read_only=True)
    stop_name = serializers.CharField(source="stop.name", read_only=True, default="")
    monthly_fee = serializers.DecimalField(source="fee", max_digits=10, decimal_places=2, read_only=True)
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = StudentTransport
        fields = ("id", "student", "student_name", "enrollment_id", "route", "route_name", "stop", "stop_name", "mode",
                  "pickup_note", "monthly_fee", "start_date", "end_date", "is_open", "created_at")
        read_only_fields = fields

    def get_student_name(self, seat):
        return person_name(seat.student.profile)

    def get_is_open(self, seat):
        return seat.end_date is None


class AssignInputSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    route = serializers.UUIDField()
    stop = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField()
    mode = serializers.ChoiceField(choices=StudentTransport.Mode.choices, required=False, default=StudentTransport.Mode.BOTH)
    pickup_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        from students.models import Student

        student = Student.objects.filter(pk=attrs["student"]).select_related("profile").first()
        if student is None:
            raise serializers.ValidationError({"student": "Student not found."})
        route = Route.objects.filter(pk=attrs["route"]).first()
        if route is None:
            raise serializers.ValidationError({"route": "Route not found."})
        stop = None
        if attrs.get("stop"):
            stop = RouteStop.objects.filter(pk=attrs["stop"]).first()
            if stop is None:
                raise serializers.ValidationError({"stop": "Stop not found."})
        return {
            "student": student, "route": route, "stop": stop, "start_date": attrs["start_date"],
            "mode": attrs["mode"], "pickup_note": attrs["pickup_note"],
        }


class EndInputSerializer(serializers.Serializer):
    end_date = serializers.DateField(required=False)


class TransportBillSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    stop_name = serializers.CharField(source="stop.name", read_only=True, default="")
    route_name = serializers.CharField(source="route.name", read_only=True)

    class Meta:
        model = TransportBill
        fields = ("id", "student", "student_name", "enrollment_id", "month", "route", "route_name", "stop", "stop_name",
                  "amount", "student_fee", "created_at")
        read_only_fields = fields

    def get_student_name(self, bill):
        return person_name(bill.student.profile)


class BillRunSerializer(serializers.Serializer):
    month = serializers.CharField(help_text="YYYY-MM")
    due_date = serializers.DateField(required=False, allow_null=True)

    def validate_month(self, value):
        match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
        if not match:
            raise serializers.ValidationError("Use the form YYYY-MM, like 2026-10.")
        return int(match.group(1)), int(match.group(2))
