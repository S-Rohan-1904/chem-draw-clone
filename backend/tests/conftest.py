import os

# Tests hammer the API from one client; the limiters are exercised explicitly in test_limits.
os.environ.setdefault("RATE_LIMIT_PER_MIN", "0")
os.environ.setdefault("TYPING_RATE_LIMIT_PER_MIN", "0")
os.environ.setdefault("AUTH_RATE_LIMIT_PER_MIN", "0")

# Name lookups need the network; tests enable them explicitly with mocked HTTP.
os.environ.setdefault("CHEM_NAME_LOOKUP", "0")
# Do not import the prebuilt cache into test databases.
os.environ.setdefault("CHEM_PREWARM_PATH", "/nonexistent/prewarm.db")
os.environ.setdefault("CHEM_SPECTRA_LOOKUP", "0")
