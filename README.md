# BLOG API
A Blog REST API project build  with Django and Django REST Framework

## Project Structure
- 'apps/auths' - custom user model and authentication
- 'apps/blog' - posts, comments, categories and tags
- 'settings' - project configuration
- 'requirements' - dependencies for developers


#ERD
docs/

## Seeding

Install development dependencies and apply migrations:

```bash
python -m pip install -r requirements/dev.txt
python manage.py migrate
```

Generate fake data:

```bash
python manage.py seed
```

| Argument | Default | Purpose |
|---|---|---|
| `--users` | 20 | New users |
| `--posts` | 100 | New posts |
| `--comments` | 500 | New comments |
| `--clear` | Off | Delete existing data, preserving superusers |

Example:

```bash
python manage.py seed --users 50 --posts 300 --comments 1500
```

Generated users share the development password `SeedPassword123!`.
Repeated runs add users, posts, and comments while skipping existing
categories and tags.

## Admin

```bash
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/.

The Unfold admin includes a dashboard, search, filters, publication
actions, tabbed forms, and inline comments.
