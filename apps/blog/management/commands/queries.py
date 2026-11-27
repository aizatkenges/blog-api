from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)
from django.db import connection
from django.db.models import Count, QuerySet
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.auths.models import User
from apps.blog.models import Category, Post, Tag
from apps.blog.queries import QUERIES


ROWS_TO_DISPLAY = 5
DEFAULT_PAGE = 1
DEFAULT_LOOKBACK_DAYS = 365
MIN_POPULAR_POSTS = 1
SAMPLE_EMAIL_DOMAIN = "example.com"
SAMPLE_CATEGORY_SLUG = "django"
SAMPLE_TAG_SLUG = "python"
SAMPLE_SECOND_TAG_SLUG = "django"
MISSING_SLUG = "no-such-post"
MISSING_TITLE = "missing-title"
MISSING_TEXT = "missing-text"
MISSING_NAME = "missing-name"
SAMPLE_TAG_NAME = "Homework 3 tag"
SAMPLE_DRAFT_AGE_DAYS = 30
MUTATING_QUERY_NUMBERS = {40, 41, 42, 43, 44}


class Command(BaseCommand):
    help = "Run blog ORM queries."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--number",
            type=int,
            help="Run only the query with this number.",
        )
        parser.add_argument(
            "--sql",
            action="store_true",
            help="Print the SQL statements for the query.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        number: int | None = options["number"]
        show_sql: bool = options["sql"]

        if number is not None:
            numbers = [number]
        else:
            numbers = [
                query_number
                for query_number in sorted(QUERIES)
                if query_number not in MUTATING_QUERY_NUMBERS
            ]

        for query_number in numbers:
            function = QUERIES.get(query_number)
            if function is None:
                raise CommandError(
                    f"Query number {query_number} does not exist."
                )

            arguments = self._sample_arguments(query_number)

            with CaptureQueriesContext(connection) as context:
                result = function(**arguments)
                if isinstance(result, QuerySet):
                    result = list(result)

            query_count = len(context.captured_queries)
            query_word = "query" if query_count == 1 else "queries"
            self.stdout.write(
                f"#{query_number} {function.__name__} "
                f"— {query_count} SQL {query_word}"
            )

            if show_sql:
                for captured_query in context.captured_queries:
                    self.stdout.write(captured_query["sql"])

            self._write_result(result)

    def _sample_arguments(self, number: int) -> dict[str, Any]:
        if number == 4:
            slug = Post.objects.order_by("slug").values_list(
                "slug",
                flat=True,
            ).first()
            return {"slug": slug or MISSING_SLUG}

        if number == 7:
            return {"page": DEFAULT_PAGE}

        if number == 8:
            title = Post.objects.order_by("pk").values_list(
                "title",
                flat=True,
            ).first()
            return {"word": title or MISSING_TITLE}

        if number == 9:
            return {"domain": SAMPLE_EMAIL_DOMAIN}

        if number == 11:
            slugs = list(
                Category.objects.order_by("slug").values_list(
                    "slug",
                    flat=True,
                )[:2]
            )
            return {"slugs": slugs}

        if number == 12:
            created_at = Post.objects.order_by("created_at").values_list(
                "created_at",
                flat=True,
            ).first()
            sample_date = created_at or timezone.now()
            return {
                "year": sample_date.year,
                "month": sample_date.month,
            }

        if number == 13:
            return {"days": DEFAULT_LOOKBACK_DAYS}

        if number == 14:
            first_post_date = Post.objects.order_by(
                "created_at",
            ).values_list(
                "created_at",
                flat=True,
            ).first()
            end = timezone.localdate()
            start = first_post_date.date() if first_post_date else end
            return {"start": start, "end": end}

        if number == 15:
            email = User.objects.filter(
                post__status=Post.Status.PUBLISHED,
            ).values_list(
                "email",
                flat=True,
            ).first()
            return {"email": email or f"sample@{SAMPLE_EMAIL_DOMAIN}"}

        if number == 16:
            tag_slug = Tag.objects.filter(
                post__isnull=False,
            ).values_list(
                "slug",
                flat=True,
            ).first()
            return {"tag_slug": tag_slug or SAMPLE_TAG_SLUG}

        if number == 17:
            category_slug = Category.objects.filter(
                post__comment__isnull=False,
            ).values_list(
                "slug",
                flat=True,
            ).first()
            return {
                "category_slug": category_slug or SAMPLE_CATEGORY_SLUG,
            }

        if number == 21:
            post = Post.objects.annotate(
                tag_count=Count("tags", distinct=True),
            ).filter(
                tag_count__gte=2,
            ).first()

            if post is None:
                return {
                    "first_slug": SAMPLE_TAG_SLUG,
                    "second_slug": SAMPLE_SECOND_TAG_SLUG,
                }

            slugs = list(
                post.tags.order_by("slug").values_list(
                    "slug",
                    flat=True,
                )[:2]
            )
            return {
                "first_slug": slugs[0],
                "second_slug": slugs[1],
            }

        if number == 22:
            title = Post.objects.order_by("pk").values_list(
                "title",
                flat=True,
            ).first()
            return {"text": title or MISSING_TEXT}

        if number == 34:
            return {"min_posts": MIN_POPULAR_POSTS}

        if number == 37:
            user_names = User.objects.order_by("pk").values_list(
                "first_name",
                "last_name",
            ).first()

            if user_names is None:
                return {"text": MISSING_NAME}

            first_name, last_name = user_names
            return {"text": f"{first_name} {last_name[:3]}"}

        if number == 40:
            return {"name": SAMPLE_TAG_NAME}

        if number == 41:
            return {"days": SAMPLE_DRAFT_AGE_DAYS}

        if number == 42:
            return {
                "category_slug": SAMPLE_CATEGORY_SLUG,
                "tag_slug": SAMPLE_TAG_SLUG,
            }

        if number == 43:
            return {
                "source_slug": "testing",
                "target_slug": SAMPLE_CATEGORY_SLUG,
            }

        return {}

    def _write_result(self, result: Any) -> None:
        if isinstance(result, list):
            for row in result[:ROWS_TO_DISPLAY]:
                self.stdout.write(f"  {self._format_row(row)}")
            self.stdout.write(f"  ({len(result)} rows)")
            return

        self.stdout.write(f"  {self._format_row(result)}")

    def _format_row(self, row: Any) -> str:
        if not hasattr(row, "_meta"):
            return str(row)

        model_fields = {
            field.attname for field in row._meta.concrete_fields
        }
        annotations = {
            key: value
            for key, value in row.__dict__.items()
            if key not in model_fields and key != "_state"
        }

        if annotations:
            return f"{row} {annotations}"
        return str(row)
