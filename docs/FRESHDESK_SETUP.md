# Freshdesk Webhook Setup Guide

## How to connect Freshdesk to the Triage Engine

### Step 1 — Get your Freshdesk API key

1. Log into Freshdesk
2. Click your profile avatar (top right) → **Profile Settings**
3. Your API key is shown in the right-hand panel under **Your API Key**
4. Copy it into your `.env` file as `FRESHDESK_API_KEY`

Your domain is the part before `.freshdesk.com`, e.g. for `acme.freshdesk.com` set `FRESHDESK_DOMAIN=acme.freshdesk.com`

---

### Step 2 — Start the triage engine

```bash
# With Docker
docker-compose up -d

# Without Docker (local dev)
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
cd src && python main.py --serve
```

The API will be running at `http://localhost:8000`.

---

### Step 3 — Install and configure ngrok (first time only)

Freshdesk needs a public URL to POST webhook events. Use ngrok to expose your local server.

**Install ngrok (Windows)**

Option A — via winget:
```powershell
winget install ngrok.ngrok
```

Option B — manual:
1. Download the Windows ZIP from [ngrok.com/download](https://ngrok.com/download)
2. Extract `ngrok.exe` into your project folder
3. Use `.\ngrok.exe` instead of `ngrok` in the commands below

**Create a free account and add your auth token**

1. Sign up at [dashboard.ngrok.com](https://dashboard.ngrok.com)
2. Copy your authtoken from the dashboard
3. Run once to save it:
```powershell
ngrok config add-authtoken YOUR_TOKEN_HERE
```

**Start the tunnel**
```powershell
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL — this is your webhook base URL. Keep this terminal open while testing.

> **Note:** The free ngrok URL changes every time you restart ngrok. Update the Freshdesk webhook URL each session, or upgrade to a paid ngrok plan for a stable domain.

For production, deploy the container to Railway, Render, Fly.io, or any VPS instead.

---

### Step 4 — Create the Freshdesk webhook automation

1. In Freshdesk, go to **Admin** → **Workflows** → **Automation**
2. Click **Ticket Creation** tab → **New Rule**
3. Set conditions:
   - **When**: A ticket is created
   - **Conditions**: Any ticket (or filter by group/type as needed)
4. Under **Actions**, choose **Trigger Webhook**
5. Fill in:
   - **Request Type**: POST
   - **URL**: `https://your-public-url/webhook/freshdesk`
   - **Encoding**: JSON
   - **Content**: Select all fields, or use **Advanced** and paste:

```json
{
  "freshdesk_webhook": {
    "ticket_id": "{{ticket.id}}",
    "ticket_subject": "{{ticket.subject}}",
    "ticket_description": "{{ticket.description}}",
    "ticket_status": "{{ticket.status}}",
    "ticket_priority": "{{ticket.priority}}",
    "requester_email": "{{ticket.from_email}}"
  }
}
```

6. Save and enable the rule.

---

### Step 5 — Test it

Create a test ticket in Freshdesk. Within seconds you should see:

- **Priority** updated to match the severity (Urgent/High/Medium/Low)
- **Tags** added: `ai-triaged`, `triage:high`, `category:api-oauth` etc.
- **Private note** added with the full triage summary

You can also test manually:

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"ticket": "Webhook deliveries failing with 401 after OAuth token rotation"}'
```

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| 401 from Freshdesk API | Check `FRESHDESK_API_KEY` — must be the API key, not your password |
| Webhook not firing | Check the automation rule is enabled and the condition matches |
| Note not appearing | Check API key has agent permissions (not just view) |
| DB connection error | `docker-compose up -d postgres` then restart the API |

---

### Architecture notes

- Webhook responds immediately (200 OK) and classifies asynchronously via `BackgroundTasks`
- Freshdesk has a 10-second timeout on webhooks — this ensures we never miss it
- All classifications are persisted to `triage_log` — view at `GET /logs`
- Priority mapping: CRITICAL→Urgent(4), HIGH→High(3), MEDIUM→Medium(2), LOW→Low(1)

---

### Common issues encountered during setup

| Symptom | Fix |
|---|---|
| `API error 404` on classification | Wrong model name — set `CLAUDE_MODEL=claude-sonnet-4-5` in `.env`, then `docker-compose down && docker-compose up -d` |
| `ngrok: not recognized` | Install via `winget install ngrok.ngrok`, reopen PowerShell, then run `ngrok config add-authtoken YOUR_TOKEN` |
| ngrok URL changed | Free ngrok URLs reset on restart — update the webhook URL in Freshdesk Automation each session |
| Classification fallback (confidence 0.0) | API key not reaching container — run `docker-compose exec api env | findstr ANTHROPIC` to verify, then `docker-compose down && docker-compose up -d` |
| Dockerfile empty error | The Dockerfile was not saved correctly — manually create it with the contents from the README |
