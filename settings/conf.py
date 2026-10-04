from decouple import config
BLOG_ENV_ID = config("BLOG_ENV_ID", default = "local")
BLOG_SECRET_KEY = config("BLOG_SECRET_KEY")