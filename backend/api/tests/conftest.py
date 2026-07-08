import os


# Local release setup can point config/.env at Atlas. Unit/API tests should stay
# deterministic and must not write to the real beta database unless a test opts in.
os.environ.setdefault("APP_STORAGE_PROVIDER", "demo")
