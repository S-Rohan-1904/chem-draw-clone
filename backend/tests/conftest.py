import os

# Tests hammer the API from one client; the limiter is exercised explicitly in test_limits.
os.environ.setdefault("RATE_LIMIT_PER_MIN", "0")

# Name lookups need the network; tests enable them explicitly with mocked HTTP.
os.environ.setdefault("CHEM_NAME_LOOKUP", "0")
# Do not import the prebuilt cache into test databases.
os.environ.setdefault("CHEM_PREWARM_PATH", "/nonexistent/prewarm.db")
