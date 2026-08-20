"""Shared rate limiter instance.

Uses IP-based keys by default. For authenticated routes this is a pragmatic
first line of defense; per-user quotas can be layered later by keying on the
Authorization header or request state.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
