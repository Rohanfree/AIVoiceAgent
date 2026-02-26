#!/usr/bin/env python3
"""
seed_firestore.py — Seeds a test client document into Firestore so the
API tests have real data to work with.

Run: python3 seed_firestore.py
"""

import sys
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

CRED_PATH = os.getenv("FIREBASE_CREDENTIAL_PATH", "./firebase-service-account.json")

cred = credentials.Certificate(CRED_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

CLIENT_ID = "test-client-001"

client_data = {
    "id": CLIENT_ID,
    "business_name": "Rohan's Salon",
    "working_hours": {
        "start": "09:00",
        "end": "19:00"
    },
    "services": [
        {"name": "Haircut",     "duration": 30, "price": 250.0},
        {"name": "Beard Trim",  "duration": 20, "price": 150.0},
        {"name": "Hair Color",  "duration": 90, "price": 800.0},
        {"name": "Facial",      "duration": 60, "price": 500.0},
    ]
}

db.collection("clients").document(CLIENT_ID).set(client_data)
print(f"✅ Test client '{CLIENT_ID}' seeded into Firestore.")
print(f"   Services: {[s['name'] for s in client_data['services']]}")
