import json
from typing import Any

from django.db.models import Count, Q
from django.http import HttpRequest

from apps.auths.models import User
from apps.blog.models import Category, Comment, Post
from settings.conf import BLOG_ENV_ID

PRODUCTION_ENVIRONMENT_ID = "prod"
TOP_AUTHORS_LIMIT = 5
PERCENT_MULTIPLIER = 100
CHART_PRIMARY_COLOR = "#0d9488"


def environment_callback(request: HttpRequest) -> list[str]:
    if BLOG_ENV_ID == PRODUCTION_ENVIRONMENT_ID:
        return ["Production", "danger"]

    return ["Local", "warning"]


def drafts_badge(request: HttpRequest) -> int:
    return Post.objects.filter(
        status=Post.Status.DRAFT,
    ).count()


def superuser_required(request: HttpRequest) -> bool:
    return request.user.is_superuser


def dashboard_callback(
    request: HttpRequest,
    context: dict[str, Any],
) -> dict[str, Any]:
    post_counts = Post.objects.aggregate(
        total=Count("pk"),
        published=Count(
            "pk",
            filter=Q(status=Post.Status.PUBLISHED),
        ),
        drafts=Count(
            "pk",
            filter=Q(status=Post.Status.DRAFT),
        ),
    )

    total_posts = post_counts["total"]
    published_count = post_counts["published"]
    drafts_count = post_counts["drafts"]

    categories = list(
        Category.objects.annotate(
            posts_count=Count("post"),
        ).order_by("name")
    )

    top_authors = (
        User.objects.annotate(
            posts_count=Count("post"),
        )
        .filter(posts_count__gt=0)
        .order_by("-posts_count", "email")[:TOP_AUTHORS_LIMIT]
    )

    published_percent = (
        published_count / total_posts * PERCENT_MULTIPLIER if total_posts else 0
    )
    drafts_percent = (
        drafts_count / total_posts * PERCENT_MULTIPLIER if total_posts else 0
    )

    context.update(
        {
            "cards": [
                {
                    "title": "Total users",
                    "value": User.objects.count(),
                    "icon": "group",
                },
                {
                    "title": "Published posts",
                    "value": published_count,
                    "icon": "publish",
                },
                {
                    "title": "Draft posts",
                    "value": drafts_count,
                    "icon": "edit_note",
                },
                {
                    "title": "Comments",
                    "value": Comment.objects.count(),
                    "icon": "comment",
                },
            ],
            "category_chart": json.dumps(
                {
                    "labels": [category.name for category in categories],
                    "datasets": [
                        {
                            "label": "Posts",
                            "data": [category.posts_count for category in categories],
                            "backgroundColor": CHART_PRIMARY_COLOR,
                        },
                    ],
                }
            ),
            "authors_table": {
                "headers": ["Author", "Email", "Posts"],
                "rows": [
                    [
                        (f"{author.first_name} {author.last_name}").strip()
                        or author.email,
                        author.email,
                        author.posts_count,
                    ]
                    for author in top_authors
                ],
            },
            "publication_progress": [
                {
                    "title": "Published",
                    "description": (
                        f"{published_count} posts ({published_percent:.1f}%)"
                    ),
                    "value": published_percent,
                },
                {
                    "title": "Drafts",
                    "description": (f"{drafts_count} posts ({drafts_percent:.1f}%)"),
                    "value": drafts_percent,
                },
            ],
        }
    )

    return context
