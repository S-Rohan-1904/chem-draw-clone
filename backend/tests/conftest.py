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
# The Open Reaction Database paper index is a local build; tests use their own fixtures.
os.environ.setdefault("CHEM_ORD_DB", "/nonexistent/ord_papers.db")
# Literature services too; tests that need them patch each module's enabled() and mock HTTP.
os.environ.setdefault("CHEM_LITERATURE_LOOKUP", "0")
# The NMR shift index is a local build; tests of the rules run without it and build their own.
os.environ.setdefault("CHEM_NMR_ENV_DB", "/nonexistent/nmr_env.db")
# xtb is a separate program; tests that need it ask for it explicitly (test_vibrations.py).
os.environ.setdefault("CHEM_XTB", "/nonexistent/xtb")
