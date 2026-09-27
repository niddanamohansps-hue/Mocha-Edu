from django.contrib import admin
from django.db import connection
from .models import Parent, StudentParentRelation


class TenantOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return connection.schema_name != "public"

    def has_view_permission(self, request, obj=None):
        return connection.schema_name != "public"

    def has_add_permission(self, request):
        return connection.schema_name != "public"

    def has_change_permission(self, request, obj=None):
        return connection.schema_name != "public"

    def has_delete_permission(self, request, obj=None):
        return connection.schema_name != "public"


class StudentLinkInline(admin.TabularInline):
    model = StudentParentRelation
    extra = 1
    raw_id_fields = ("student",)


class ParentInline(admin.StackedInline):
    model = Parent
    extra = 0
    can_delete = False
    verbose_name = "Parent record for this Identity"


@admin.register(Parent)
class ParentAdmin(TenantOnlyAdmin):
    list_display = ("get_full_name", "occupation", "get_children_count")
    search_fields = ("profile__first_name", "profile__last_name", "occupation")
    inlines = [StudentLinkInline]
    raw_id_fields = ("profile",)

    def get_full_name(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"

    get_full_name.short_description = "Parent Name"

    def get_children_count(self, obj):
        return obj.student_links.count()

    get_children_count.short_description = "Children Linked"


@admin.register(StudentParentRelation)
class StudentParentRelationAdmin(TenantOnlyAdmin):
    list_display = ("student", "parent", "relation_type", "is_primary_contact")
    list_filter = ("relation_type", "is_primary_contact")
    raw_id_fields = ("student", "parent")
