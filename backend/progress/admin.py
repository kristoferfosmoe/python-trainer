from django.contrib import admin

from .models import Attempt, CodeDraft, LessonProgress


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "page", "finished", "updated_at"]
    list_filter = ["finished", "lesson__unit__course"]
    search_fields = ["user__username", "lesson__slug"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "key", "passed", "lesson_version", "created_at"]
    list_filter = ["passed"]
    search_fields = ["user__username", "key"]
    readonly_fields = [f.name for f in Attempt._meta.fields]


@admin.register(CodeDraft)
class CodeDraftAdmin(admin.ModelAdmin):
    list_display = ["user", "key", "updated_at"]
    search_fields = ["user__username", "key"]
