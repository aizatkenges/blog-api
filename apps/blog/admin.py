from django.contrib import admin
from apps.blog.models import Category, Comment, Post, Tag
admin.site.register(Category)
admin.site.register(Comment)
admin.site.register(Post)
admin.site.register(Tag)