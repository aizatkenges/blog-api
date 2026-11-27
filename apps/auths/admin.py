from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import BooleanRadioFilter
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm

from apps.auths.forms import (
    CustomUserChangeForm,
    CustomUserCreationForm,
)
from apps.auths.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    change_password_form = AdminPasswordChangeForm

    ordering = ("email",)
    search_fields = ("email", "first_name", "last_name")

    list_display = (
        "user_header",
        "active_label",
        "staff_label",
        "posts_count",
    )
    list_filter = (
        ("is_active", BooleanRadioFilter),
        ("is_staff", BooleanRadioFilter),
    )
    list_filter_submit = True

    readonly_fields = ("last_login",)
    filter_horizontal = ("groups", "user_permissions")
    actions = ("activate_users", "deactivate_users")

    fieldsets = (
        (
            "Personal info",
            {
                "classes": ("tab",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password",
                ),
            },
        ),
        (
            "Permissions",
            {
                "classes": ("tab",),
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            "Important dates",
            {
                "classes": ("tab",),
                "fields": ("last_login",),
            },
        ),
    )

    add_fieldsets = (
        (
            "Create user",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[User]:
        return (
            super()
            .get_queryset(request)
            .annotate(_posts_count=Count("post", distinct=True))
        )

    @display(description="User", header=True, ordering="first_name")
    def user_header(self, obj: User) -> tuple[str, str, str]:
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        initials = (f"{obj.first_name[:1]}{obj.last_name[:1]}").upper()

        return full_name or obj.email, obj.email, initials

    @display(
        description="Active",
        ordering="is_active",
        label={True: "success", False: "danger"},
    )
    def active_label(self, obj: User) -> tuple[bool, str]:
        return obj.is_active, "Active" if obj.is_active else "Inactive"

    @display(
        description="Staff",
        ordering="is_staff",
        label={True: "info", False: "warning"},
    )
    def staff_label(self, obj: User) -> tuple[bool, str]:
        return obj.is_staff, "Staff" if obj.is_staff else "Regular"

    @display(description="Posts", ordering="_posts_count")
    def posts_count(self, obj: User) -> int:
        return obj._posts_count

    @action(description="Activate selected users", permissions=["change"])
    def activate_users(
        self,
        request: HttpRequest,
        queryset: QuerySet[User],
    ) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"{updated} users activated.",
            messages.SUCCESS,
        )

    @action(description="Deactivate selected users", permissions=["change"])
    def deactivate_users(
        self,
        request: HttpRequest,
        queryset: QuerySet[User],
    ) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} users deactivated.",
            messages.SUCCESS,
        )


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    search_fields = ("name",)
