#!/usr/bin/env python3
"""
seed_firestore.py — Seeds test data into Firestore:
  1. A test client document (services, working hours)
  2. The admin user account (with Argon2-hashed password)

Run: python3 seed_firestore.py
"""

import sys
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

# Hash the admin password
try:
    from argon2 import PasswordHasher
    ph = PasswordHasher()
except ImportError:
    print("❌ argon2-cffi not installed. Run: pip install argon2-cffi")
    sys.exit(1)

CRED_PATH = os.getenv("FIREBASE_CREDENTIAL_PATH", "./firebase-service-account.json")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "automite_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Aut0m!te@Secure#2026")

cred = credentials.Certificate(CRED_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ── 1. Seed test client ────────────────────────────────────────────────────

CLIENT_ID = "test-client-001"

client_data = {
    "id": CLIENT_ID,
    "business_name": "Rohan's Salon",
    "assistant_name": "Sofia",
    "working_hours": {
        "start": "09:00",
        "end": "19:00"
    },
    "operating_hours": {
        "monday": {"open": "09:00", "close": "19:00"},
        "tuesday": {"open": "09:00", "close": "19:00"},
        "wednesday": {"open": "09:00", "close": "19:00"},
        "thursday": {"open": "09:00", "close": "19:00"},
        "friday": {"open": "09:00", "close": "19:00"},
        "saturday": {"open": "10:00", "close": "17:00"},
        "sunday": {"open": "closed", "close": "closed"},
    },
    "services": [
        {"name": "Haircut",     "category": "Hair", "duration": 30, "price": 250.0, "description": "Standard haircut"},
        {"name": "Beard Trim",  "category": "Grooming", "duration": 20, "price": 150.0, "description": "Beard trimming"},
        {"name": "Hair Color",  "category": "Hair", "duration": 90, "price": 800.0, "description": "Full hair coloring"},
        {"name": "Facial",      "category": "Skin", "duration": 60, "price": 500.0, "description": "Deep cleansing facial"},
    ],
    "currency": "INR",
    "is_active": True,
    "subscription_status": "active",
}

db.collection("clients").document(CLIENT_ID).set(client_data)
print(f"✅ Test client '{CLIENT_ID}' seeded into Firestore.")
print(f"   Services: {[s['name'] for s in client_data['services']]}")

# ── 2. Seed admin user ─────────────────────────────────────────────────────

from datetime import datetime, timezone

admin_doc = {
    "id": "admin",
    "username": ADMIN_USERNAME,
    "hashed_password": ph.hash(ADMIN_PASSWORD),
    "is_admin": True,
    "subscription_status": "admin",
    "client_id": None,
    "created_at": datetime.now(tz=timezone.utc).isoformat(),
}

db.collection("users").document("admin").set(admin_doc)
print(f"✅ Admin user '{ADMIN_USERNAME}' seeded into Firestore.")
print(f"   Password: {ADMIN_PASSWORD} (change in .env before deploying!)")

