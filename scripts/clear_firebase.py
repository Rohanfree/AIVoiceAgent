"""
clear_firebase.py — Deletes all documents from client-related Firestore collections.
Usage: .venv/bin/python scripts/clear_firebase.py
"""

import firebase_admin
from firebase_admin import credentials, firestore

COLLECTIONS = ["clients", "call_logs", "appointments", "customers", "users"]


def main():
    cred = credentials.Certificate("./firebase-service-account.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    for col in COLLECTIONS:
        docs = list(db.collection(col).stream())
        for doc in docs:
            doc.reference.delete()
        if docs:
            print(f"Deleted {len(docs)} from '{col}'")

    print("Done.")


if __name__ == "__main__":
    main()
