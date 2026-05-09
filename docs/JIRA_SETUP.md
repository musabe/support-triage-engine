# Jira Cloud Webhook Setup Guide

## How to connect Jira Cloud to the Triage Engine

---

### Step 1 — Get your Jira API token

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Name it `support-triage-engine`
4. Copy the token — you won't see it again

Add to your `.env`:
```
JIRA_DOMAIN=yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your_token_here
```

Your domain is the part before `.atlassian.net`.

---

### Step 2 — Create a Jira project (if you don't have one)

1. In Jira, click **Projects** → **Create project**
2. Choose **Scrum** or **Service management** (either works)
3. Name it e.g. `Support` or `Triage Test`
4. Note your project key (e.g. `SUP`, `TRIAGE`) — you'll see it in issue keys like `SUP-1`

---

### Step 3 — Start the triage engine

```bash
docker-compose down
docker-compose up -d
```

Confirm it's running:
```bash
curl http://localhost:8000/
```

---

### Step 4 — Expose your local server

```powershell
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL.

> **Reminder:** Free ngrok URLs reset on restart. Update the Jira webhook URL each session.

---

### Step 5 — Create the Jira webhook

1. In Jira, go to **Settings** (⚙️ bottom left) → **System**
2. Under **Advanced**, click **WebHooks**
3. Click **Create a WebHook**
4. Fill in:
   - **Name**: `AI Triage Engine`
   - **URL**: `https://xxxx.ngrok-free.app/webhook/jira`
   - **Events**: tick **Issue → created**
   - **JQL filter** (optional — limits which issues trigger it):
     ```
     issuetype in (Bug, Support)
     ```
5. Click **Create**

---

### Step 6 — Test it

Create a test issue in Jira (type: Bug or Support). Within seconds you should see:

- **Priority** updated — CRITICAL→Highest, HIGH→High, MEDIUM→Medium, LOW→Low
- **Labels** added — `ai-triaged`, `triage-high`, `triage-api-webhook`
- **Comment** posted with the full triage summary in Jira's rich text format
- **Status transitioned** to In Progress (for CRITICAL and HIGH issues)

You can also test the endpoint directly:
```bash
curl -X POST http://localhost:8000/webhook/jira \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "issue": {
      "key": "SUP-1",
      "fields": {
        "summary": "Webhook deliveries failing with 401 after OAuth token rotation",
        "description": "All webhook deliveries returning 401 since token was rotated this morning.",
        "issuetype": {"name": "Bug"}
      }
    }
  }'
```

---

### Issue type filtering

By default only `Bug` and `Support` issue types are triaged. Others return:
```json
{"status": "skipped", "reason": "Issue type 'Task' not in triage list"}
```

To change the allowed types, update `.env`:
```
JIRA_ISSUE_TYPES=Bug,Support,Incident
```

Then restart: `docker-compose down && docker-compose up -d`

---

### Status transitions

By default:
- **CRITICAL** and **HIGH** issues → transitioned to `In Progress`
- **MEDIUM** and **LOW** issues → left as `To Do` / `Open`

If your Jira project uses custom status names, update `SEVERITY_TO_TRANSITION` in `src/jira_client.py`:
```python
SEVERITY_TO_TRANSITION = {
    "CRITICAL": "In Progress",   # must match your Jira status name exactly
    "HIGH":     "In Progress",
    "MEDIUM":   None,            # None = no transition
    "LOW":      None,
}
```

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| 401 from Jira API | Check `JIRA_API_TOKEN` and `JIRA_EMAIL` are correct |
| Issue not updating | Confirm issue type is in `JIRA_ISSUE_TYPES` |
| Transition not firing | Check status name matches exactly (case-sensitive) in `jira_client.py` |
| Comment not appearing | API token may not have write permissions — check token scope |
| Webhook not firing | Confirm JQL filter matches the issue you created |
| ngrok URL expired | Restart ngrok, update webhook URL in Jira Settings → WebHooks |
