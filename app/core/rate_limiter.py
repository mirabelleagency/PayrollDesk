"""Rate limiting configuration using slowapi."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance with client IP as key
limiter = Limiter(key_func=get_remote_address)

# Rate limit constants
EXPORT_LIMIT = "5/minute"  # Prevent export abuse
IMPORT_LIMIT = "10/minute"  # Allow reasonable import frequency
AUTH_LIMIT = "10/minute"  # Prevent brute force
