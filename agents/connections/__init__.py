"""Shared connections for the Evergreen agents: DB, Gemini (LLM + embeddings), Airtable.

Importing this package loads .env once so every agent shares the same config.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load the agents/.env first, then fall back to the repo-root .env for anything
# not set locally (the root .env holds the shared AIRTABLE token). Local values win.
_AGENTS_ENV = Path(__file__).resolve().parent.parent / ".env"
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_AGENTS_ENV)
load_dotenv(_ROOT_ENV, override=False)
