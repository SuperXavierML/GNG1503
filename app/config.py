import os


class Config:
    DATABASE = os.environ.get("DATABASE_PATH")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    TESTING = False
