# QuantPilot Operations Runbook

Step-by-step procedures for running, monitoring, controlling, and emergency handling during the live hackathon demo.

---

## 1. Prerequisites Check
1. Python 3.10+ installed.
2. Virtual environment created and activated:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Testnet API keys created in Delta India Demo Portal:
   - Ensure Trading and Read permissions are checked.
   - Verify that your demo machine's public IP is whitelisted on the key.

---

## 2. Environment Setup
Copy the example environment file:
```bash
cp .env.example .env
```
Populate `.env` with:
- `TARGET_ENV=testnet`
- `DELTA_API_KEY=<your_key>`
- `DELTA_API_SECRET=<your_secret>`
- `CONTROL_PLANE_SECRET=<strong_shared_secret>`

---

## 3. Running Diagnostics & Smoke Tests
Run Phase 0 diagnostics to verify connectivity, clock synchronization, and key permissions without opening real risk:
```bash
python scripts/diagnostics.py
python scripts/smoke_test.py
```

---

## 4. Starting the Trading Engine & Control Plane
Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Access the dashboard at:
`http://localhost:8000/dashboard`

---

## 5. Emergency Procedures (Kill Switch)

If unexpected behavior, network anomalies, or erroneous fills are detected:

### Option A: Via Dashboard
1. Click the large red **EMERGENCY KILL SWITCH** button.
2. Enter the `CONTROL_PLANE_SECRET`.
3. Confirm immediate halt.

### Option B: Via HTTP Curl
```bash
curl -X POST http://localhost:8000/api/control/kill \
  -H "X-Control-Secret: change_me_to_a_secure_token" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual operator intervention"}'
```

### Option C: Verifying Flat State
Check positions endpoint:
```bash
curl http://localhost:8000/api/positions
```
The response must show 0 open positions and all working orders cancelled.
