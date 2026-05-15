"""
activate_all_clients.py — One-off script to activate all clients and restore
their ElevenLabs agent prompts from Firestore backup (if available).

Run from the project root:
    python scripts/activate_all_clients.py
"""

import asyncio
import sys
import os

# Make sure app imports resolve from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_firestore_client
from app.services.elevenlabs_service import reactivate_agent_prompt


async def activate_all():
    db = get_firestore_client()
    clients = db.collection("clients").stream()

    results = {"activated": [], "already_active": [], "failed": []}

    for doc in clients:
        data = doc.to_dict() or {}
        client_id = doc.id
        name = data.get("business_name", client_id)
        is_active = data.get("is_active", True)
        agent_id = data.get("elevenlabs_agent_id", "")

        if is_active:
            print(f"  [skip]   {name} — already active")
            results["already_active"].append(client_id)
            continue

        print(f"  [activate] {name} ({client_id}) ...", end=" ", flush=True)

        # Update Firestore
        db.collection("clients").document(client_id).set(
            {"is_active": True, "deactivation_reason": None},
            merge=True,
        )

        # Restore ElevenLabs agent
        if agent_id:
            business_info = data.get("knowledge_base_text", "")
            ok = await reactivate_agent_prompt(agent_id, client_id, business_info)
            if ok:
                print("done (agent restored)")
            else:
                print("Firestore updated but ElevenLabs restore failed")
                results["failed"].append(client_id)
                continue
        else:
            print("done (no agent ID configured)")

        results["activated"].append(client_id)

    print()
    print(f"Activated:      {len(results['activated'])}")
    print(f"Already active: {len(results['already_active'])}")
    print(f"Failed:         {len(results['failed'])}")
    if results["failed"]:
        print(f"Failed IDs: {results['failed']}")


if __name__ == "__main__":
    asyncio.run(activate_all())
