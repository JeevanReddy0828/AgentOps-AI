"""
Root conftest — sets required environment variables before any src imports.
"""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
