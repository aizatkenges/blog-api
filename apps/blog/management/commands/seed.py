from random import choice, randint, random, sample
from time import perf_counter
from typing import Any

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.text import slugify
from faker import Faker

from apps.auths.models import User
from apps.blog.models import Category, Comment, Post, Tag

DEFAULT_USERS = 20
DEFAULT_POSTS = 100
DEFAULT_COMMENTS = 500
COUNT_OPTION_NAMES = ("users", "posts", "comments")

SEED_PASSWORD = "SeedPassword123!"
EMAIL_DOMAIN = "example.com"
EMAIL_FALLBACK_NAME = "user"

ACTIVE_PROBABILITY = 0.90
STAFF_PROBABILITY = 0.10


PUBLISHED_PROBABILITY = 0.70
NO_CATEGORY_PROBABILITY = 0.10

POST_BODY_PARAGRAPHS = 3
MIN_POST_TAGS = 0
MAX_POST_TAGS = 5

POST_SLUG_FALLBACK = "post"
FIRST_DUPLICATE_SUFFIX = 2

MIN_COMMENT_SENTENCES = 1
MAX_COMMENT_SENTENCES = 3


CATEGORY_NAMES = (
    "Python",
    "Django",
    "REST APIs",
    "Databases",
    "DevOps",
    "Testing",
    "Web Development",
    "Software Architecture",
)

TAG_NAMES = (
    "Python",
    "Django",
    "Django REST Framework",
    "API",
    "REST",
    "PostgreSQL",
    "SQLite",
    "Docker",
    "Git",
    "GitHub",
    "Testing",
    "Backend",
    "Frontend",
    "Deployment",
    "Security",
    "Authentication",
    "Performance",
    "Clean Code",
    "Linux",
    "Cloud",
)


class Command(BaseCommand):
    help = "Fill the database with fake data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--users", type=int, default=DEFAULT_USERS, help="Number of users to create"
        )
        parser.add_argument(
            "--posts", type=int, default=DEFAULT_POSTS, help="Number of posts to create"
        )
        parser.add_argument(
            "--comments",
            type=int,
            default=DEFAULT_COMMENTS,
            help="Number of comments to create",
        )
        parser.add_argument(
            "--clear", action="store_true", help="Delete existing data before seeding"
        )

    def _clear_database(self) -> None:
        Comment.objects.all().delete()
        Post.objects.all().delete()
        Tag.objects.all().delete()
        Category.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("Existing seed data deleted.")

    def _build_unique_email(
        self,
        first_name: str,
        last_name: str,
        used_emails: set[str],
    ) -> str:
        first_part = slugify(first_name) or EMAIL_FALLBACK_NAME
        last_part = slugify(last_name) or EMAIL_FALLBACK_NAME
        email_base = f"{first_part}.{last_part}"

        email = f"{email_base}@{EMAIL_DOMAIN}"
        suffix = FIRST_DUPLICATE_SUFFIX

        while email in used_emails:
            email = f"{email_base}{suffix}@{EMAIL_DOMAIN}"
            suffix += 1
        used_emails.add(email)
        return email

    def _build_unique_post_slug(
        self,
        title: str,
        used_slugs: set[str],
    ) -> str:
        max_length = Post._meta.get_field("slug").max_length
        slug_base = slugify(title) or POST_SLUG_FALLBACK
        slug_base = slug_base[:max_length]

        post_slug = slug_base
        suffix = FIRST_DUPLICATE_SUFFIX

        while post_slug in used_slugs:
            ending = f"-{suffix}"
            post_slug = f"{slug_base[: max_length - len(ending)]}{ending}"
            suffix += 1

        used_slugs.add(post_slug)
        return post_slug

    def _create_users(self, users_count: int, fake: Faker) -> int:
        used_emails = {
            email.lower() for email in User.objects.values_list("email", flat=True)
        }
        password_hash = make_password(SEED_PASSWORD)
        users_to_create: list[User] = []

        for _ in range(users_count):
            first_name = fake.first_name()
            last_name = fake.last_name()
            email = self._build_unique_email(
                first_name,
                last_name,
                used_emails,
            )
            users_to_create.append(
                User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password_hash,
                    is_active=random() < ACTIVE_PROBABILITY,
                    is_staff=random() < STAFF_PROBABILITY,
                )
            )
        User.objects.bulk_create(users_to_create)
        return len(users_to_create)

    def _create_categories(self) -> int:
        existing_names = set(Category.objects.values_list("name", flat=True))
        existing_slugs = set(Category.objects.values_list("slug", flat=True))
        categories_to_create: list[Category] = []

        for name in CATEGORY_NAMES:
            category_slug = slugify(name)
            if name in existing_names or category_slug in existing_slugs:
                continue
            categories_to_create.append(
                Category(
                    name=name,
                    slug=category_slug,
                )
            )
        Category.objects.bulk_create(categories_to_create)
        return len(categories_to_create)

    def _create_tags(self) -> int:
        existing_names = set(Tag.objects.values_list("name", flat=True))
        existing_slugs = set(Tag.objects.values_list("slug", flat=True))
        tags_to_create: list[Tag] = []

        for name in TAG_NAMES:
            tag_slug = slugify(name)
            if name in existing_names or tag_slug in existing_slugs:
                continue
            tags_to_create.append(
                Tag(
                    name=name,
                    slug=tag_slug,
                )
            )
        Tag.objects.bulk_create(tags_to_create)
        return len(tags_to_create)

    def _create_posts(self, posts_count: int, fake: Faker) -> int:
        if posts_count == 0:
            return 0
        users = list(User.objects.all())
        categories = list(Category.objects.all())
        tags = list(Tag.objects.all())

        if not users:
            raise CommandError("Posts were requested, but no users exist.")

        used_slugs = set(Post.objects.values_list("slug", flat=True))
        posts_to_create: list[Post] = []

        for _ in range(posts_count):
            title = fake.sentence()
            post_slug = self._build_unique_post_slug(
                title,
                used_slugs,
            )

            status = (
                Post.Status.PUBLISHED
                if random() < PUBLISHED_PROBABILITY
                else Post.Status.DRAFT
            )

            category = None
            if categories and random() >= NO_CATEGORY_PROBABILITY:
                category = choice(categories)

            posts_to_create.append(
                Post(
                    author=choice(users),
                    title=title,
                    slug=post_slug,
                    body="\n\n".join(fake.paragraphs(nb=POST_BODY_PARAGRAPHS)),
                    category=category,
                    status=status,
                )
            )
        Post.objects.bulk_create(posts_to_create)

        for post in posts_to_create:
            tags_count = randint(
                MIN_POST_TAGS,
                min(MAX_POST_TAGS, len(tags)),
            )
            post.tags.set(sample(tags, tags_count))

        return len(posts_to_create)

    def _create_comments(
        self,
        comments_count: int,
        fake: Faker,
    ) -> int:
        if comments_count == 0:
            return 0
        users = list(User.objects.all())
        published_posts = list(Post.objects.filter(status=Post.Status.PUBLISHED))
        if not users:
            raise CommandError("Comments were requested but no users exist.")
        if not published_posts:
            raise CommandError("Comments were requested, but no published posts exist")
        comments_to_create: list[Comment] = []

        for _ in range(comments_count):
            sentences_count = randint(
                MIN_COMMENT_SENTENCES,
                MAX_COMMENT_SENTENCES,
            )
            comments_to_create.append(
                Comment(
                    post=choice(published_posts),
                    author=choice(users),
                    body=" ".join(fake.sentences(nb=sentences_count)),
                )
            )
        Comment.objects.bulk_create(comments_to_create)
        return len(comments_to_create)

    def handle(self, *args: Any, **options: Any) -> None:
        start_time = perf_counter()
        users_count: int = options["users"]
        posts_count: int = options["posts"]
        comments_count: int = options["comments"]
        clear: bool = options["clear"]

        counts = {
            "users": users_count,
            "posts": posts_count,
            "comments": comments_count,
        }

        for option_name in COUNT_OPTION_NAMES:
            if counts[option_name] < 0:
                raise CommandError(f"--{option_name} cannot be negative")

        if clear:
            self._clear_database()

        fake = Faker()

        created_users_count = self._create_users(
            users_count=users_count,
            fake=fake,
        )
        if (posts_count > 0 or comments_count > 0) and not User.objects.exists():
            raise CommandError("Posts or comments were requested, but no users exist.")
        created_categories_count = self._create_categories()
        created_tags_count = self._create_tags()

        created_posts_count = self._create_posts(
            posts_count=posts_count,
            fake=fake,
        )

        created_comments_count = self._create_comments(
            comments_count=comments_count,
            fake=fake,
        )

        elapsed_seconds = perf_counter() - start_time

        self.stdout.write(f"Users: {created_users_count:4} created")
        self.stdout.write(f"Categories: {created_categories_count:4} created")
        self.stdout.write(f"Tags: {created_tags_count:4} created")
        self.stdout.write(f"Posts: {created_posts_count:4} created")
        self.stdout.write(f"Comments: {created_comments_count:4} created")
        self.stdout.write(self.style.SUCCESS(f"Done in {elapsed_seconds:.2f} seconds"))
