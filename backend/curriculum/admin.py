"""Teachers edit lessons here as YAML. Every save is checked: examples must
run, quiz answers must match, and challenge solutions must pass their goals."""

import yaml
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .library import check_lesson
from .models import Course, Lesson, PlaygroundChallenge, Robot, Unit, World

YAML_WIDGET = forms.Textarea(attrs={
    "rows": 40, "cols": 110, "spellcheck": "false",
    "style": "font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; width: 100%;",
})


class _ReadableDumper(yaml.SafeDumper):
    """Writes multi-line text (Markdown, code) as readable `|` blocks."""


def _represent_str(dumper, text):
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_ReadableDumper.add_representer(str, _represent_str)


def dump_yaml(data):
    return yaml.dump(data, Dumper=_ReadableDumper, sort_keys=False, allow_unicode=True, width=100,
                     default_flow_style=False)


def load_yaml(text, what):
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValidationError(f"The {what} isn't valid YAML: {error}")
    if not isinstance(data, dict):
        raise ValidationError(f"The {what} must be a YAML dictionary.")
    return data


class LessonForm(forms.ModelForm):
    """Saving a copy of a file-based lesson under a new slug makes it an admin lesson."""

    content_yaml = forms.CharField(
        label="Blocks (YAML)", widget=YAML_WIDGET,
        help_text="concepts: [...] and blocks: [...], in the same format as the files in content/courses/. "
                  "Saving runs every example and challenge solution, so it can take a few seconds.",
    )

    class Meta:
        model = Lesson
        fields = ["unit", "slug", "title", "summary", "order", "published"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.source:
            self.fields["content_yaml"].help_text = (
                f"⚠️ This lesson comes from {self.instance.source} in the repository. Changes made here are "
                "replaced the next time lessons are imported (every deploy). To keep changes, edit that file "
                "instead, or give this lesson a new slug to make your own copy."
            )
        content = self.instance.content if self.instance.pk else {"concepts": [], "blocks": [
            {"type": "text", "markdown": "Write the lesson here."},
        ]}
        self.fields["content_yaml"].initial = dump_yaml(content)

    def clean(self):
        cleaned = super().clean()
        text = cleaned.get("content_yaml")
        if not text:
            return cleaned
        data = load_yaml(text, "lesson")
        if not isinstance(data.get("blocks"), list) or not data["blocks"]:
            raise ValidationError("The lesson needs a list of blocks.")
        content = {"concepts": data.get("concepts", []), "blocks": data["blocks"]}
        lesson = {
            "id": cleaned.get("slug") or "new-lesson",
            "title": cleaned.get("title", ""),
            "summary": cleaned.get("summary", ""),
            **content,
        }
        problems = check_lesson(lesson)
        if problems:
            raise ValidationError([ValidationError(p) for p in problems])
        cleaned["content"] = content
        return cleaned

    def save(self, commit=True):
        self.instance.content = self.cleaned_data["content"]
        if "slug" in self.changed_data:
            self.instance.source = ""
        return super().save(commit)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonForm
    list_display = ["title", "slug", "unit", "order", "published", "version", "from_file", "updated_at", "preview"]
    list_filter = ["published", "unit__course", "unit"]
    list_editable = ["order", "published"]
    search_fields = ["title", "slug"]
    fieldsets = [
        (None, {"fields": ["unit", "slug", "title", "summary", "order", "published"]}),
        ("Content", {"fields": ["content_yaml"]}),
    ]

    @admin.display(description="From a file", boolean=True)
    def from_file(self, lesson):
        return bool(lesson.source)

    @admin.display(description="Preview")
    def preview(self, lesson):
        return format_html('<a href="{}" target="_blank">Open ↗</a>', lesson.get_absolute_url())


class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ["order", "title", "slug", "published"]
    readonly_fields = ["title", "slug"]
    extra = 0
    show_change_link = True
    can_delete = False


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["__str__", "course", "order"]
    list_filter = ["course"]
    inlines = [LessonInline]


class UnitInline(admin.TabularInline):
    model = Unit
    fields = ["order", "icon", "title", "slug"]
    extra = 0
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "published", "owner_team", "order"]
    inlines = [UnitInline]


class SpecForm(forms.ModelForm):
    """Edit a JSON spec as YAML."""

    spec_yaml = forms.CharField(label="Spec (YAML)", widget=YAML_WIDGET)
    what = "spec"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spec_yaml"].initial = dump_yaml(self.instance.spec) if self.instance.pk else ""

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("spec_yaml"):
            spec = load_yaml(cleaned["spec_yaml"], self.what)
            if cleaned.get("slug"):
                spec["id"] = cleaned["slug"]
            self.check_spec(spec)
            cleaned["spec"] = spec
        return cleaned

    def check_spec(self, spec):
        pass

    def save(self, commit=True):
        self.instance.spec = self.cleaned_data["spec"]
        return super().save(commit)


class WorldForm(SpecForm):
    what = "world"

    class Meta:
        model = World
        fields = ["slug", "name"]

    def check_spec(self, spec):
        from trainer_sim.shapes import ShapeError
        from trainer_sim.world import World as SimWorld

        try:
            SimWorld(spec)
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            raise ValidationError(f"Problem in the world: {error}")


class RobotForm(SpecForm):
    what = "robot"

    class Meta:
        model = Robot
        fields = ["slug", "name"]

    def check_spec(self, spec):
        from trainer_sim.robot import RobotSpec
        from trainer_sim.shapes import ShapeError

        try:
            RobotSpec(spec)
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            raise ValidationError(f"Problem in the robot: {error}")


class ChallengeForm(SpecForm):
    what = "challenge"

    class Meta:
        model = PlaygroundChallenge
        fields = ["slug", "title", "order", "published"]

    def check_spec(self, spec):
        spec.setdefault("title", self.cleaned_data.get("title", ""))
        problems = check_lesson({
            "id": f"playground/{spec['id']}", "title": spec["title"], "summary": "playground",
            "blocks": [{**spec, "type": "challenge"}],
        })
        if problems:
            raise ValidationError([ValidationError(p) for p in problems])


@admin.register(World)
class WorldAdmin(admin.ModelAdmin):
    form = WorldForm
    list_display = ["name", "slug"]
    fields = ["slug", "name", "spec_yaml"]


@admin.register(Robot)
class RobotAdmin(admin.ModelAdmin):
    form = RobotForm
    list_display = ["name", "slug"]
    fields = ["slug", "name", "spec_yaml"]


@admin.register(PlaygroundChallenge)
class PlaygroundChallengeAdmin(admin.ModelAdmin):
    form = ChallengeForm
    list_display = ["title", "slug", "order", "published"]
    list_editable = ["order", "published"]
    fields = ["slug", "title", "order", "published", "spec_yaml"]
