from django.contrib import admin

from .models import Membership, Team


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "season", "join_code", "member_count", "created_at"]
    search_fields = ["name", "join_code"]
    readonly_fields = ["join_code", "created_at"]
    inlines = [MembershipInline]

    @admin.display(description="Members")
    def member_count(self, team):
        return team.memberships.count()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "team", "role", "joined_at"]
    list_filter = ["role", "team"]
    search_fields = ["user__username", "team__name"]
    autocomplete_fields = ["user", "team"]
