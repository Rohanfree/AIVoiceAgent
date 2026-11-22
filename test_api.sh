#!/usr/bin/env bash
# =============================================================================
# DEPRECATED — test_api.sh targets the removed legacy Vapi paths (/health,
# /agent-tools/*) and does NOT pass against the current app. Do not use as a
# health signal. See mapping below for the current ElevenLabs equivalents.
#
# Current equivalents (all under $BASE_URL, live server + Firestore required):
#   GET  /health                                        -> GET  /automiteaiapplication/health
#   POST /agent-tools/get-services-and-prices           -> removed (no equivalent)
#   POST /agent-tools/get-client-by-mobile              -> POST /automiteaiapplication/elevenlabs-tools/get-customer
#   POST /agent-tools/check-availability                -> POST /automiteaiapplication/elevenlabs-tools/check-availability
#   POST /agent-tools/book-appointment                  -> POST /automiteaiapplication/elevenlabs-tools/book-appointment
#   POST /agent-tools/save-call-log                     -> POST /automiteaiapplication/elevenlabs-tools/save-call-summary
# NOTE: elevenlabs-tools endpoints require an X-Client-Token JWT (scope=tool);
# plain curl without a token returns 401/403. For automated checks use the
# mocked pytest suite (test_*.py) instead — no live server needed.
# =============================================================================

BASE_URL="http://localhost:8090"
CLIENT_ID="test-client-001"
CUSTOMER_PHONE="+919876543210"
CUSTOMER_NAME="Rohan Sharma"
SERVICE="Haircut"
# Use tomorrow's date at 10:00 AM UTC
APPT_TIME="2026-02-28T10:00:00+00:00"

# Pretty-print helper
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

sep() { echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
title() { echo -e "${YELLOW}▶ $1${NC}"; }
ok() { echo -e "${GREEN}✓ $1${NC}"; }
err() { echo -e "${RED}✗ $1${NC}"; }

call_api() {
  local method="$1"
  local path="$2"
  local body="$3"

  if [ -z "$body" ]; then
    curl -s -X "$method" "$BASE_URL$path" \
      -H "Content-Type: application/json"
  else
    curl -s -X "$method" "$BASE_URL$path" \
      -H "Content-Type: application/json" \
      -d "$body"
  fi
}

# =============================================================================
sep
title "0) Health Check — GET /health"
sep
RESP=$(call_api GET /health)
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "1) Get Services & Prices — POST /agent-tools/get-services-and-prices"
echo "   (Creates test client in Firestore if not present; fetches services)"
sep
RESP=$(call_api POST /agent-tools/get-services-and-prices \
  "{\"client_id\": \"$CLIENT_ID\"}")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "2) Get Client by Mobile — POST /agent-tools/get-client-by-mobile"
echo "   (Looks up customer '$CUSTOMER_PHONE' under client '$CLIENT_ID')"
sep
RESP=$(call_api POST /agent-tools/get-client-by-mobile \
  "{\"client_id\": \"$CLIENT_ID\", \"customer_phone\": \"$CUSTOMER_PHONE\"}")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "3) Check Availability — POST /agent-tools/check-availability"
echo "   (Checks if '$SERVICE' is available on $APPT_TIME)"
sep
RESP=$(call_api POST /agent-tools/check-availability \
  "{\"client_id\": \"$CLIENT_ID\", \"service_name\": \"$SERVICE\", \"date_time\": \"$APPT_TIME\"}")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "4) Book Appointment — POST /agent-tools/book-appointment"
echo "   (Books '$SERVICE' for '$CUSTOMER_NAME' at $APPT_TIME)"
echo "   → This writes to Firestore: appointments + customers collections"
sep
RESP=$(call_api POST /agent-tools/book-appointment \
  "{
    \"client_id\": \"$CLIENT_ID\",
    \"customer_name\": \"$CUSTOMER_NAME\",
    \"customer_phone\": \"$CUSTOMER_PHONE\",
    \"service_name\": \"$SERVICE\",
    \"date_time\": \"$APPT_TIME\"
  }")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "5) Check Availability AGAIN — same slot should now be unavailable"
echo "   (Verifies the booked appointment is being read back from Firestore)"
sep
RESP=$(call_api POST /agent-tools/check-availability \
  "{\"client_id\": \"$CLIENT_ID\", \"service_name\": \"$SERVICE\", \"date_time\": \"$APPT_TIME\"}")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "6) Save Call Log — POST /agent-tools/save-call-log"
echo "   (Writes to call_logs + updates customers collection in Firestore)"
sep
RESP=$(call_api POST /agent-tools/save-call-log \
  "{
    \"client_id\": \"$CLIENT_ID\",
    \"caller_phone\": \"$CUSTOMER_PHONE\",
    \"transcript\": \"Agent: Hello, how can I help you?\\nCustomer: I'd like to book a haircut.\",
    \"summary\": \"Customer called to book a haircut appointment.\",
    \"extracted_customer_name\": \"$CUSTOMER_NAME\"
  }")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

# =============================================================================
sep
title "7) Get Client by Mobile AGAIN — should now return customer data"
echo "   (Verifies customers collection was written/updated correctly)"
sep
RESP=$(call_api POST /agent-tools/get-client-by-mobile \
  "{\"client_id\": \"$CLIENT_ID\", \"customer_phone\": \"$CUSTOMER_PHONE\"}")
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

sep
echo -e "${GREEN}✔  All tests completed. Check the Firestore Console to verify documents.${NC}"
echo -e "   → https://console.firebase.google.com — Firestore Database"
echo -e "     Collections to check: appointments | customers | call_logs"
sep
