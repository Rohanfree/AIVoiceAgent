"""Run the suite in development mode so placeholder secrets stay accepted.

Must run before any `app.*` import, since `app.config` builds Settings at import time.
"""

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef-not-for-prod")
