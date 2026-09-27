from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginFailure, RateLimitHit, User
from .pins import random_pin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "display_name", "kind", "avatar", "is_staff", "date_joined", "last_login"]
    list_filter = ["kind", "is_staff", "is_active", "memberships__team"]
    search_fields = ["username", "display_name"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profile", {"fields": ("kind", "display_name", "avatar")}),
        ("Sign-in protection", {"fields": ("failed_logins", "locked_until")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "kind", "password1", "password2")}),
    )
    actions = ["reset_pin", "unlock"]

    @admin.action(description="Give selected students a new PIN")
    def reset_pin(self, request, queryset):
        for user in queryset.filter(kind=User.Kind.STUDENT):
            pin = random_pin()
            user.set_password(pin)
            user.failed_logins = 0
            user.locked_until = None
            user.save()
            self.message_user(request, f"New PIN for {user.username}: {pin}", messages.SUCCESS)

    @admin.action(description="Unlock selected accounts")
    def unlock(self, request, queryset):
        count = queryset.update(failed_logins=0, locked_until=None)
        self.message_user(request, f"Unlocked {count} account(s).")


@admin.register(LoginFailure)
class LoginFailureAdmin(admin.ModelAdmin):
    """Deleting a computer's rows here lifts its sign-in block early."""

    list_display = ["ip", "username", "created_at"]
    list_filter = ["ip"]
    readonly_fields = ["ip", "username", "created_at"]


@admin.register(RateLimitHit)
class RateLimitHitAdmin(admin.ModelAdmin):
    """New accounts and wrong team codes per computer. Deleting rows lifts a limit early."""

    list_display = ["scope", "key", "created_at"]
    list_filter = ["scope"]
    readonly_fields = ["scope", "key", "created_at"]
