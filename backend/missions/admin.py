"""Staff edit Mission Mode games and challenges here as YAML. Every save is
checked like a lesson: a challenge's solution must earn all three stars
and its starter none, in the separate checker process."""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from curriculum.admin import YAML_WIDGET, dump_yaml, load_yaml
from curriculum.library import run_checker

from .models import MissionChallenge, MissionGame, MissionProgress

FROM_FILE_WARNING = (
    "⚠️ This comes from {source} in the repository. Changes made here are replaced the next time content "
    "is imported (every deploy). To keep changes, edit that file instead."
)


def _problems(problems):
    if problems:
        raise ValidationError([ValidationError(p) for p in problems])


class MissionGameForm(forms.ModelForm):
    spec_yaml = forms.CharField(
        label="Game (YAML)", widget=YAML_WIDGET,
        help_text="The same format as content/missions/<game>/game.yaml, with the robot and the attachments "
                  "filled in. Saving checks the field, the models and the missions.",
    )

    class Meta:
        model = MissionGame
        fields = ["slug", "title", "summary", "order", "published"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spec_yaml"].initial = dump_yaml(self.instance.spec) if self.instance.pk else ""
        if self.instance.source:
            self.fields["spec_yaml"].help_text = FROM_FILE_WARNING.format(source=self.instance.source)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("spec_yaml"):
            spec = load_yaml(cleaned["spec_yaml"], "game")
            spec["id"] = cleaned.get("slug") or spec.get("id")
            spec.setdefault("title", cleaned.get("title", ""))
            _problems(run_checker({"mission_game": {**spec, "challenges": []}, "run": False}))
            cleaned["spec"] = spec
        return cleaned

    def save(self, commit=True):
        self.instance.spec = self.cleaned_data["spec"]
        return super().save(commit)


class MissionChallengeForm(forms.ModelForm):
    spec_yaml = forms.CharField(
        label="Challenge (YAML)", widget=YAML_WIDGET,
        help_text="The same format as content/missions/<game>/challenges/*.yaml. Saving runs the solution "
                  "(it must earn 3 stars) and the starter (it must earn none), so it can take a few seconds.",
    )

    class Meta:
        model = MissionChallenge
        fields = ["game", "slug", "title", "tier", "order", "published"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spec_yaml"].initial = dump_yaml(self.instance.spec) if self.instance.pk else ""
        if self.instance.source:
            self.fields["spec_yaml"].help_text = FROM_FILE_WARNING.format(source=self.instance.source)

    def clean(self):
        cleaned = super().clean()
        game = cleaned.get("game")
        if cleaned.get("spec_yaml") and game:
            spec = load_yaml(cleaned["spec_yaml"], "challenge")
            spec["id"] = cleaned.get("slug") or spec.get("id")
            spec["title"] = cleaned.get("title") or spec.get("title", "")
            spec["tier"] = cleaned.get("tier", spec.get("tier"))
            _problems(run_checker({"mission_game": {**game.spec, "challenges": []}, "mission_challenge": spec}))
            cleaned["spec"] = spec
        return cleaned

    def save(self, commit=True):
        self.instance.spec = self.cleaned_data["spec"]
        if "slug" in self.changed_data:
            self.instance.source = ""
        return super().save(commit)


class MissionChallengeInline(admin.TabularInline):
    model = MissionChallenge
    fields = ["order", "tier", "title", "slug", "published"]
    readonly_fields = ["title", "slug"]
    extra = 0
    show_change_link = True
    can_delete = False


@admin.register(MissionGame)
class MissionGameAdmin(admin.ModelAdmin):
    form = MissionGameForm
    list_display = ["title", "slug", "order", "published"]
    fields = ["slug", "title", "summary", "order", "published", "spec_yaml"]
    inlines = [MissionChallengeInline]


@admin.register(MissionChallenge)
class MissionChallengeAdmin(admin.ModelAdmin):
    form = MissionChallengeForm
    list_display = ["title", "slug", "game", "tier", "order", "published", "preview"]
    list_filter = ["game", "tier", "published"]
    list_editable = ["order", "published"]
    search_fields = ["title", "slug"]
    fields = ["game", "slug", "title", "tier", "order", "published", "spec_yaml"]

    @admin.display(description="Preview")
    def preview(self, challenge):
        return format_html('<a href="/#/missions/{}" target="_blank">Open ↗</a>', challenge.slug)


@admin.register(MissionProgress)
class MissionProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "challenge", "stars", "best_score", "updated_at"]
    list_filter = ["challenge__game"]
    search_fields = ["user__username"]
    readonly_fields = ["user", "challenge", "stars", "best_score", "updated_at"]
