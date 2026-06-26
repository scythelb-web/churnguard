#!/usr/bin/env python3
"""Initialize the ChurnGuard database."""
from app.database import init_db
init_db()
print("Database initialized at churnguard.db")
