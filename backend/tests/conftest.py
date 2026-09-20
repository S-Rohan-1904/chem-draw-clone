import os

# Tests hammer the API from one client; the limiter is exercised explicitly in test_limits.
os.environ.setdefault("RATE_LIMIT_PER_MIN", "0")
