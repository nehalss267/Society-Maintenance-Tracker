#!/usr/bin/env bash
# Smoke tests against the SMT stack running inside kind (http://localhost:8080).
set -euo pipefail

BASE="http://localhost:8080"
SUFFIX="$(date +%s)"
EMAIL="ci.${SUFFIX}@smoke.test"
PASS="SmokeTest123"

echo "=== 1. API health through ingress ==="
curl -fsS "$BASE/health" | grep -q '"status":"ok"'
echo "OK"

echo "=== 2. Web SPA served ==="
curl -fsS "$BASE/" | grep -q '<div id="root">'
echo "OK"

echo "=== 3. Register + login ==="
curl -fsS -X POST "$BASE/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"CI Smoke\",\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" >/dev/null
TOKEN=$(curl -fsS -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ]
echo "OK"

echo "=== 4. Create complaint with PNG upload ==="
printf '\x89PNG\r\n\x1a\n%.0s' 1 > /tmp/ci.png && head -c 64 /dev/zero >> /tmp/ci.png
CID=$(curl -fsS -X POST "$BASE/api/complaints" \
  -H "Authorization: Bearer $TOKEN" \
  -F category=PLUMBING \
  -F "description=CI smoke test complaint with photo attachment." \
  -F "photo=@/tmp/ci.png;type=image/png" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
[ -n "$CID" ]
echo "OK (complaint $CID)"

echo "=== 5. Photo served back through nginx proxy ==="
PHOTO_URL=$(curl -fsS "$BASE/api/complaints/$CID" -H "Authorization: Bearer $TOKEN" | sed -n 's/.*"photo_url":"\([^"]*\)".*/\1/p')
[ -n "$PHOTO_URL" ]
curl -fsS "$BASE${PHOTO_URL}" -o /tmp/ci-out.bin
head -c 4 /tmp/ci-out.bin | grep -q $'\x89PNG'
echo "OK ($PHOTO_URL)"

echo "=== 6. RBAC wall holds in cluster ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/admin/notices" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"should fail","content":"nope"}')
[ "$code" = "403" ] || { echo "expected 403, got $code"; exit 1; }
echo "OK"

echo "=== 7. Prometheus scraping the API ==="
PROM_SVC=$(kubectl -n smt get svc -l "app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server" -o jsonpath='{.items[0].metadata.name}')
kubectl -n smt port-forward "svc/$PROM_SVC" 9090:9090 >/dev/null 2>&1 &
PF_PID=$!
sleep 4
curl -fsS http://localhost:9090/-/ready >/dev/null
UP=$(curl -fsS 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D~%22.smt-api.%7C.smt.%22%7D' || true)
kill $PF_PID 2>/dev/null || true
echo "$UP" | grep -q '"value"'
METRICS_DIRECT=$(curl -fsS "$BASE/metrics" | grep -c '^http_request_duration_seconds_count' || true)
[ "${METRICS_DIRECT:-0}" -ge 1 ]
echo "OK (prometheus svc: $PROM_SVC)"

echo "=== 8. Grafana API healthy ==="
GRAFANA_SVC=$(kubectl -n smt get svc -l "app.kubernetes.io/name=grafana" -o jsonpath='{.items[0].metadata.name}')
kubectl -n smt port-forward "svc/$GRAFANA_SVC" 3000:3000 >/dev/null 2>&1 &
GF_PID=$!
sleep 4
curl -fsS http://localhost:3000/api/health | grep -q '"database":"ok"'
kill $GF_PID 2>/dev/null || true
echo "OK (grafana svc: $GRAFANA_SVC)"

echo ""
echo "ALL SMOKE TESTS PASSED"
