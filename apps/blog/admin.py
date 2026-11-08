from typing import Any, ClassVar

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    ChoicesDropdownFilter,
    MultipleRelatedDropdownFilter,
    RangeDateTimeFilter,
    RelatedDropdownFilter,
)
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action, display
from unfold.sections import TableSection

from apps.blog.models import Category, Comment, Post, Tag

COMMENT_PREVIEW_LENGTH = 80


class CategoryPostsSection(TableSection):
    verbose_name = "Posts"
    related_name = "post_set"
    fields: ClassVar[list[str]] = ["title", "status", "created_at"]


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "posts_count")
    search_fields = ("name",)
    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {
        "slug": ("name",),
    }
    list_sections: ClassVar[list[type[TableSection]]] = [
        CategoryPostsSection,
    ]

    @display(description="Posts", ordering="_posts_count")
    def posts_count(self, obj: Category) -> int:
        return obj._posts_count

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[Category]:
        return (
            super()
            .get_queryset(request)
            .annotate(_posts_count=Count("post", distinct=True))
            .prefetch_related("post_set")
        )


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ("name", "slug", "posts_count")
    search_fields = ("name",)
    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {
        "slug": ("name",),
    }

    @display(description="Posts", ordering="_posts_count")
    def posts_count(self, obj: Tag) -> int:
        return obj._posts_count

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[Tag]:
        return (
            super()
            .get_queryset(request)
            .annotate(_posts_count=Count("post", distinct=True))
        )


COMMENTS_PER_PAGE = 10


class PostCommentsSection(TableSection):
    verbose_name = "Comments"
    related_name = "comment_set"
    fields = ("author", "body", "created_at")


class CommentInline(TabularInline):
    model = Comment
    tab = True
    per_page = COMMENTS_PER_PAGE
    extra = 0
    fields = ("author", "body", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)
    show_change_link = True

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[Comment]:
        return super().get_queryset(request).select_related("author")


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = (
        "post_header",
        "status_label",
        "category",
        "tags_dropdown",
        "comments_count",
        "created_at",
    )
    search_fields = ("title", "body", "author__email")

    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("category", RelatedDropdownFilter),
        ("tags", MultipleRelatedDropdownFilter),
        ("author", AutocompleteSelectFilter),
        ("created_at", RangeDateTimeFilter),
    )
    list_filter_submit = True
    list_select_related = ("author", "category")
    list_sections: ClassVar[list[type[TableSection]]] = [
        PostCommentsSection,
    ]

    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {
        "slug": ("title",),
    }
    autocomplete_fields = ("author", "category", "tags")
    readonly_fields = ("created_at", "updated_at")
    warn_unsaved_form = True

    formfield_overrides: ClassVar[dict[type, dict[str, Any]]] = {
        models.TextField: {"widget": WysiwygWidget},
    }

    inlines: ClassVar[list[type[TabularInline]]] = [CommentInline]

    fieldsets = (
        (
            "Content",
            {
                "classes": ("tab",),
                "fields": ("title", "slug", "body"),
            },
        ),
        (
            "Classification",
            {
                "classes": ("tab",),
                "fields": ("category", "tags", "status"),
            },
        ),
        (
            "Meta",
            {
                "classes": ("tab",),
                "fields": ("author", "created_at", "updated_at"),
            },
        ),
    )

    actions = ("publish_selected", "move_to_drafts")
    actions_row: ClassVar[list[str]] = ["toggle_publication"]
    actions_list: ClassVar[list[str]] = ["publish_all_drafts"]
    actions_detail: ClassVar[list[str]] = ["open_comments"]
    actions_submit_line: ClassVar[list[str]] = ["save_and_publish"]

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[Post]:
        return (
            super()
            .get_queryset(request)
            .select_related("author", "category")
            .annotate(_comments_count=Count("comment", distinct=True))
            .prefetch_related(
                "tags",
                Prefetch(
                    "comment_set",
                    queryset=Comment.objects.select_related("author"),
                ),
            )
        )

    @display(description="Post", header=True, ordering="title")
    def post_header(self, obj: Post) -> tuple[str, str]:
        return obj.title, obj.author.email

    @display(
        description="Status",
        ordering="status",
        label={"published": "success", "draft": "warning"},
    )
    def status_label(self, obj: Post) -> tuple[str, str]:
        return obj.status, obj.get_status_display()

    @display(description="Tags", dropdown=True)
    def tags_dropdown(self, obj: Post) -> dict[str, Any]:
        tags = list(obj.tags.all())

        return {
            "title": f"Tags ({len(tags)})",
            "items": [
                {
                    "title": tag.name,
                    "link": reverse(
                        "admin:blog_tag_change",
                        args=(tag.pk,),
                    ),
                }
                for tag in tags
            ],
        }

    @display(description="Comments", ordering="_comments_count")
    def comments_count(self, obj: Post) -> int:
        return obj._comments_count

    @action(
        description="Publish selected",
        permissions=["change"],
    )
    def publish_selected(
        self,
        request: HttpRequest,
        queryset: QuerySet[Post],
    ) -> None:
        updated = queryset.update(
            status=Post.Status.PUBLISHED,
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{updated} posts published.",
            messages.SUCCESS,
        )

    @action(
        description="Move to drafts",
        permissions=["change"],
    )
    def move_to_drafts(
        self,
        request: HttpRequest,
        queryset: QuerySet[Post],
    ) -> None:
        updated = queryset.update(
            status=Post.Status.DRAFT,
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{updated} posts moved to drafts.",
            messages.SUCCESS,
        )

    @action(
        description="Publish / unpublish",
        icon="swap_horiz",
        permissions=["change"],
        url_path="toggle-publication",
    )
    def toggle_publication(
        self,
        request: HttpRequest,
        object_id: str,
    ) -> HttpResponse:
        post = get_object_or_404(
            self.get_queryset(request),
            pk=object_id,
        )

        if not self.has_change_permission(request, post):
            raise PermissionDenied

        post.status = (
            Post.Status.DRAFT
            if post.status == Post.Status.PUBLISHED
            else Post.Status.PUBLISHED
        )
        post.save(update_fields=("status", "updated_at"))

        self.message_user(
            request,
            f"Post moved to {post.get_status_display()}.",
            messages.SUCCESS,
        )
        return redirect("admin:blog_post_changelist")

    @action(
        description="Publish all drafts",
        icon="publish",
        permissions=["change"],
        url_path="publish-all-drafts",
    )
    def publish_all_drafts(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        if not self.has_change_permission(request):
            raise PermissionDenied

        updated = (
            self.get_queryset(request)
            .filter(status=Post.Status.DRAFT)
            .update(
                status=Post.Status.PUBLISHED,
                updated_at=timezone.now(),
            )
        )
        self.message_user(
            request,
            f"{updated} drafts published.",
            messages.SUCCESS,
        )
        return redirect("admin:blog_post_changelist")

    @action(
        description="Open comments",
        icon="comment",
        permissions=["open_comments"],
        url_path="open-comments",
    )
    def open_comments(
        self,
        request: HttpRequest,
        object_id: str,
    ) -> HttpResponse:
        post = get_object_or_404(
            self.get_queryset(request),
            pk=object_id,
        )

        if not self.has_open_comments_permission(request, object_id):
            raise PermissionDenied

        url = reverse("admin:blog_comment_changelist")
        return redirect(f"{url}?post__id__exact={post.pk}")

    def has_open_comments_permission(
        self,
        request: HttpRequest,
        object_id: str | None = None,
    ) -> bool:
        return self.has_view_permission(request) and request.user.has_perm(
            "blog.view_comment"
        )

    @action(
        description="Save & publish",
        icon="publish",
        permissions=["change"],
    )
    def save_and_publish(
        self,
        request: HttpRequest,
        obj: Post,
    ) -> None:
        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        obj.status = Post.Status.PUBLISHED
        obj.save(update_fields=("status", "updated_at"))

        self.message_user(
            request,
            "Post published.",
            messages.SUCCESS,
        )


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = (
        "post_title",
        "author",
        "short_body",
        "created_at",
    )
    list_filter = (
        ("post", AutocompleteSelectFilter),
        ("author", AutocompleteSelectFilter),
        ("created_at", RangeDateTimeFilter),
    )
    list_filter_submit = True
    search_fields = (
        "body",
        "author__email",
        "post__title",
    )
    autocomplete_fields = ("post", "author")
    list_select_related = ("post", "author")

    @display(description="Post", ordering="post__title")
    def post_title(self, obj: Comment) -> str:
        return obj.post.title

    @display(description="Comment")
    def short_body(self, obj: Comment) -> str:
        if len(obj.body) <= COMMENT_PREVIEW_LENGTH:
            return obj.body

        return f"{obj.body[:COMMENT_PREVIEW_LENGTH]}..."
