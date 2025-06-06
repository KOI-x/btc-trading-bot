import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/database.db")
