from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    Exists,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat, TruncMonth
from django.utils import timezone
from django.utils.text import slugify

from apps.auths.models import User
from apps.blog.models import Category, Comment, Post, Tag


NEWEST_POSTS_LIMIT = 5
POSTS_PER_PAGE = 10
FIRST_PAGE = 1
POST_EDIT_DELAY = timedelta(hours=1)
TOP_AUTHORS_LIMIT = 5
HOT_COMMENT_LIMIT = 10
NORMAL_COMMENT_LIMIT = 3
HOT_POPULARITY = "hot"
NORMAL_POPULARITY = "normal"
QUIET_POPULARITY = "quiet"
UNCATEGORIZED = "Uncategorized"
FEED_POST_LIMIT = 50
TAGGED_POST_LIMIT = 20


# Level 1: Basic queries

def categories_by_name() -> QuerySet[Category]:
    """Return categories sorted by name."""
    return Category.objects.order_by("name")


def published_posts() -> QuerySet[Post]:
    """Return published posts, newest first."""
    return Post.objects.filter(
        status=Post.Status.PUBLISHED,
    ).order_by("-created_at")


def newest_published_posts() -> QuerySet[Post]:
    """Return the five newest published posts."""
    return published_posts()[:NEWEST_POSTS_LIMIT]


def post_by_slug(slug: str) -> Post | None:
    """Return the post for a slug, or None if it does not exist."""
    return Post.objects.filter(slug=slug).first()


def active_users_count() -> int:
    """Count active users who are not staff."""
    return User.objects.filter(
        is_active=True,
        is_staff=False,
    ).count()


def has_drafts() -> bool:
    """Return whether any draft posts exist."""
    return Post.objects.filter(
        status=Post.Status.DRAFT,
    ).exists()


def published_posts_page(page: int) -> QuerySet[Post]:
    """Return one page of published posts, newest first."""
    page = max(page, FIRST_PAGE)
    start = (page - FIRST_PAGE) * POSTS_PER_PAGE
    end = start + POSTS_PER_PAGE
    return published_posts()[start:end]


# Level 2: Field lookups

def posts_with_word_in_title(word: str) -> QuerySet[Post]:
    """Return posts whose title contains the word, ignoring case."""
    return Post.objects.filter(title__icontains=word)


def users_with_email_domain(domain: str) -> QuerySet[User]:
    """Return users whose email ends with the given domain."""
    return User.objects.filter(email__iendswith=f"@{domain}")


def posts_without_category() -> QuerySet[Post]:
    """Return posts without a category."""
    return Post.objects.filter(category__isnull=True)


def categories_by_slugs(slugs: list[str]) -> QuerySet[Category]:
    """Return categories whose slugs appear in the given list."""
    return Category.objects.filter(slug__in=slugs)


def posts_in_month(year: int, month: int) -> QuerySet[Post]:
    """Return posts created in the given year and month."""
    return Post.objects.filter(
        created_at__year=year,
        created_at__month=month,
    )


def posts_last_days(days: int) -> QuerySet[Post]:
    """Return posts created within the last given number of days."""
    cutoff = timezone.now() - timedelta(days=days)
    return Post.objects.filter(created_at__gte=cutoff)


def posts_between(start: date, end: date) -> QuerySet[Post]:
    """Return posts created on or between the given dates."""
    return Post.objects.filter(
        created_at__date__range=(start, end),
    )


# Level 3: Queries across relations

def author_published_posts(email: str) -> QuerySet[Post]:
    """Return published posts by the author with this email."""
    return Post.objects.filter(
        author__email__iexact=email,
        status=Post.Status.PUBLISHED,
    )


def posts_with_tag(tag_slug: str) -> QuerySet[Post]:
    """Return posts with the given tag."""
    return Post.objects.filter(tags__slug=tag_slug).distinct()


def comments_in_category(category_slug: str) -> QuerySet[Comment]:
    """Return comments on posts in the given category."""
    return Comment.objects.filter(post__category__slug=category_slug)


def users_with_published_posts() -> QuerySet[User]:
    """Return each user who has a published post once."""
    return User.objects.filter(
        post__status=Post.Status.PUBLISHED,
    ).distinct()


def posts_without_tags() -> QuerySet[Post]:
    """Return posts that have no tags."""
    return Post.objects.filter(tags__isnull=True)


def users_without_comments() -> QuerySet[User]:
    """Return users who have never written a comment."""
    return User.objects.filter(comment__isnull=True)


def posts_with_both_tags(first_slug: str, second_slug: str) -> QuerySet[Post]:
    """Return posts that have both specified tags."""
    return Post.objects.filter(
        tags__slug=first_slug,
    ).filter(
        tags__slug=second_slug,
    ).distinct()


# Level 4: Q and F expressions

def search_posts(text: str) -> QuerySet[Post]:
    """Return posts containing text in the title or body."""
    return Post.objects.filter(
        Q(title__icontains=text) | Q(body__icontains=text),
    )


def published_posts_missing_info() -> QuerySet[Post]:
    """Return published posts missing a category or tags."""
    return Post.objects.filter(
        Q(category__isnull=True) | Q(tags__isnull=True),
        status=Post.Status.PUBLISHED,
    ).distinct()


def edited_posts() -> QuerySet[Post]:
    """Return posts updated more than an hour after creation."""
    return Post.objects.filter(
        updated_at__gt=F("created_at") + POST_EDIT_DELAY,
    )


def comments_by_post_author() -> QuerySet[Comment]:
    """Return comments written by the author of the commented-on post."""
    return Comment.objects.filter(
        author_id=F("post__author_id"),
    )


def comments_before_post() -> QuerySet[Comment]:
    """Return comments created before their post."""
    return Comment.objects.filter(
        created_at__lt=F("post__created_at"),
    )


# Level 5: values and values_list

def published_authors_emails() -> list[str]:
    """Return unique published-post author emails, sorted alphabetically."""
    return list(
        Post.objects.filter(
            status=Post.Status.PUBLISHED,
        )
        .order_by("author__email")
        .values_list("author__email", flat=True)
        .distinct()
    )


def published_posts_overview() -> list[dict[str, Any]]:
    """Return published post titles, author emails, and category names."""
    return list(
        Post.objects.filter(
            status=Post.Status.PUBLISHED,
        ).values(
            "title",
            author_email=F("author__email"),
            category_name=Coalesce(
                "category__name",
                Value(UNCATEGORIZED),
            ),
        )
    )


# Level 6: Aggregation

def posts_stats() -> dict[str, Any]:
    """Return total, status counts, and earliest/latest post dates."""
    return Post.objects.aggregate(
        total=Count("pk"),
        published=Count(
            "pk",
            filter=Q(status=Post.Status.PUBLISHED),
        ),
        drafts=Count(
            "pk",
            filter=Q(status=Post.Status.DRAFT),
        ),
        first_post_at=Min("created_at"),
        last_post_at=Max("created_at"),
    )


def average_comments_per_post() -> float:
    """Return the average comments per published post, rounded to 2 places."""
    result = Post.objects.filter(
        status=Post.Status.PUBLISHED,
    ).annotate(
        comment_count=Count("comment"),
    ).aggregate(
        average=Avg("comment_count"),
    )
    return round(result["average"] or 0.0, 2)


# Level 7: Annotations

def categories_with_post_count() -> QuerySet[Category]:
    """Return categories annotated with their total post count."""
    return Category.objects.annotate(
        post_count=Count("post"),
    ).order_by("-post_count", "name")


def categories_with_published_count() -> QuerySet[Category]:
    """Return categories annotated with their published post count."""
    return Category.objects.annotate(
        published_count=Count(
            "post",
            filter=Q(post__status=Post.Status.PUBLISHED),
        ),
    ).order_by("name")


def top_authors() -> QuerySet[User]:
    """Return the five users with the most published posts."""
    return User.objects.annotate(
        published_count=Count(
            "post",
            filter=Q(post__status=Post.Status.PUBLISHED),
        ),
    ).order_by("-published_count", "email")[:TOP_AUTHORS_LIMIT]


def popular_tags(min_posts: int) -> QuerySet[Tag]:
    """Return tags used on at least the requested number of posts."""
    return Tag.objects.annotate(
        post_count=Count("post", distinct=True),
    ).filter(
        post_count__gte=min_posts,
    ).order_by("-post_count", "name")


def posts_per_status() -> list[dict[str, Any]]:
    """Return the number of posts for each status."""
    return list(
        Post.objects.values("status")
        .annotate(count=Count("pk"))
        .order_by("status")
    )


def users_activity() -> QuerySet[User]:
    """Return users annotated with correct post and comment counts."""
    return User.objects.annotate(
        post_count=Count("post", distinct=True),
        comment_count=Count("comment", distinct=True),
    ).order_by("email")


# Level 8: Database functions and conditions

def search_users_by_full_name(text: str) -> QuerySet[User]:
    """Search users by their combined first and last name."""
    return User.objects.annotate(
        full_name=Concat(
            "first_name",
            Value(" "),
            "last_name",
            output_field=CharField(),
        ),
    ).filter(
        full_name__icontains=text,
    )


def published_posts_per_month() -> list[dict[str, Any]]:
    """Return published post counts grouped by month, oldest first."""
    return list(
        Post.objects.filter(
            status=Post.Status.PUBLISHED,
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )


def posts_with_popularity() -> QuerySet[Post]:
    """Return posts with comment counts and popularity labels."""
    return Post.objects.annotate(
        comment_count=Count("comment"),
    ).annotate(
        popularity=Case(
            When(
                comment_count__gte=HOT_COMMENT_LIMIT,
                then=Value(HOT_POPULARITY),
            ),
            When(
                comment_count__gte=NORMAL_COMMENT_LIMIT,
                then=Value(NORMAL_POPULARITY),
            ),
            default=Value(QUIET_POPULARITY),
            output_field=CharField(),
        ),
    )


# Level 9: Changing data

def get_or_create_tag(name: str) -> tuple[Tag, bool]:
    """Return a tag by slug, creating it if necessary."""
    tag_slug = slugify(name)
    return Tag.objects.get_or_create(
        slug=tag_slug,
        defaults={"name": name},
    )


def publish_old_drafts(days: int) -> int:
    """Publish drafts older than the requested number of days."""
    cutoff = timezone.now() - timedelta(days=days)
    return Post.objects.filter(
        status=Post.Status.DRAFT,
        created_at__lt=cutoff,
    ).update(
        status=Post.Status.PUBLISHED,
        updated_at=timezone.now(),
    )


def tag_category_posts(category_slug: str, tag_slug: str) -> int:
    """Add a tag to every post in a category and return the post count."""
    posts = Post.objects.filter(category__slug=category_slug)
    post_count = posts.count()
    tag = Tag.objects.get(slug=tag_slug)
    tag.post_set.add(*posts)
    return post_count


@transaction.atomic
def merge_categories(source_slug: str, target_slug: str) -> int:
    """Move source-category posts to target, then delete the source."""
    source = Category.objects.get(slug=source_slug)
    target = Category.objects.get(slug=target_slug)
    posts = Post.objects.filter(category=source)
    moved_count = posts.count()
    posts.update(category=target)
    source.delete()
    return moved_count


def delete_inactive_users_comments() -> int:
    """Delete comments by inactive users and return the deleted count."""
    deleted_count, _ = Comment.objects.filter(
        author__is_active=False,
    ).delete()
    return deleted_count


# Level 10: Related-object loading

def published_feed() -> list[str]:
    """Return the 50 newest published posts as feed lines."""
    posts = Post.objects.filter(
        status=Post.Status.PUBLISHED,
    ).select_related(
        "author",
        "category",
    ).order_by(
        "-created_at",
    )[:FEED_POST_LIMIT]

    return [
        (
            f"{post.title} | {post.author.email} | "
            f"{post.category.name if post.category else UNCATEGORIZED}"
        )
        for post in posts
    ]


def newest_posts_with_tags() -> list[str]:
    """Return the 20 newest posts as title and tag lines."""
    posts = Post.objects.order_by(
        "-created_at",
    ).prefetch_related(
        Prefetch("tags", queryset=Tag.objects.order_by("name")),
    )[:TAGGED_POST_LIMIT]

    return [
        f"{post.title}: {', '.join(tag.name for tag in post.tags.all())}"
        for post in posts
    ]


def categories_with_published_posts() -> dict[str, list[str]]:
    """Return category names mapped to their published post titles."""
    categories = Category.objects.prefetch_related(
        Prefetch(
            "post_set",
            queryset=Post.objects.filter(
                status=Post.Status.PUBLISHED,
            ).order_by("-created_at"),
            to_attr="published_posts",
        ),
    )

    return {
        category.name: [
            post.title for post in category.published_posts
        ]
        for category in categories
    }


# Level 11: Subquery and Exists

def posts_with_last_comment() -> QuerySet[Post]:
    """Return published posts annotated with their newest comment body."""
    newest_comment = Comment.objects.filter(
        post=OuterRef("pk"),
    ).order_by(
        "-created_at",
    ).values(
        "body",
    )[:1]

    return Post.objects.filter(
        status=Post.Status.PUBLISHED,
    ).annotate(
        last_comment=Subquery(newest_comment),
    )


def posts_with_staff_comments() -> QuerySet[Post]:
    """Return posts that have at least one comment by a staff user."""
    staff_comments = Comment.objects.filter(
        post=OuterRef("pk"),
        author__is_staff=True,
    )
    return Post.objects.filter(Exists(staff_comments))


def users_with_draft_as_latest_post() -> QuerySet[User]:
    """Return users whose newest post is a draft, with its status."""
    latest_post = Post.objects.filter(
        author=OuterRef("pk"),
    ).order_by(
        "-created_at",
    )

    return User.objects.annotate(
        latest_post_status=Subquery(
            latest_post.values("status")[:1],
        ),
    ).filter(
        latest_post_status=Post.Status.DRAFT,
    )


QUERIES = {
    1: categories_by_name,
    2: published_posts,
    3: newest_published_posts,
    4: post_by_slug,
    5: active_users_count,
    6: has_drafts,
    7: published_posts_page,
    8: posts_with_word_in_title,
    9: users_with_email_domain,
    10: posts_without_category,
    11: categories_by_slugs,
    12: posts_in_month,
    13: posts_last_days,
    14: posts_between,
    15: author_published_posts,
    16: posts_with_tag,
    17: comments_in_category,
    18: users_with_published_posts,
    19: posts_without_tags,
    20: users_without_comments,
    21: posts_with_both_tags,
    22: search_posts,
    23: published_posts_missing_info,
    24: edited_posts,
    25: comments_by_post_author,
    26: comments_before_post,
    27: published_authors_emails,
    28: published_posts_overview,
    29: posts_stats,
    30: average_comments_per_post,
    31: categories_with_post_count,
    32: categories_with_published_count,
    33: top_authors,
    34: popular_tags,
    35: posts_per_status,
    36: users_activity,
    37: search_users_by_full_name,
    38: published_posts_per_month,
    39: posts_with_popularity,
    40: get_or_create_tag,
    41: publish_old_drafts,
    42: tag_category_posts,
    43: merge_categories,
    44: delete_inactive_users_comments,
    45: published_feed,
    46: newest_posts_with_tags,
    47: categories_with_published_posts,
    48: posts_with_last_comment,
    49: posts_with_staff_comments,
    50: users_with_draft_as_latest_post,
}