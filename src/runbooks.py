"""
runbooks.py — Runbook ID → title + doc URL mapping
"""

RUNBOOK_MAP: dict[str, dict] = {
    "RB-001": {
        "title": "API Key Invalid or Expired",
        "url": "",
        "steps": [
            "Verify key exists in API settings",
            "Check expiry date and rotation policy",
            "Regenerate key and update all consumers",
            "Confirm successful auth with new key",
        ],
    },
    "RB-002": {
        "title": "OAuth Token Rotation Failure",
        "url": "",
        "steps": [
            "Verify token expiry window configuration",
            "Check webhook signing secret was rotated simultaneously",
            "Confirm refresh token is valid and not revoked",
            "Test auth flow end-to-end in staging",
        ],
    },
    "RB-003": {
        "title": "Webhook Delivery Failure",
        "url": "",
        "steps": [
            "Check webhook endpoint returns 2xx within timeout",
            "Review delivery logs for HTTP status codes",
            "Verify firewall / IP allowlist for webhook source IPs",
            "Test endpoint manually with sample payload",
        ],
    },
    "RB-004": {
        "title": "Rate Limit Exceeded",
        "url": "",
        "steps": [
            "Review current rate limit tier and usage",
            "Identify burst causing the spike",
            "Implement exponential backoff in client",
            "Consider upgrading plan or requesting limit increase",
        ],
    },
    "RB-005": {
        "title": "Database Replication Lag",
        "url": "",
        "steps": [
            "Check replication lag metrics on replica",
            "Review write load on primary",
            "Identify long-running transactions blocking replication",
            "Consider promoting replica if lag is critical",
        ],
    },
    "RB-006": {
        "title": "Database Connection Pool Exhausted",
        "url": "",
        "steps": [
            "Check active connections vs pool max",
            "Look for connection leaks in application logs",
            "Increase pool size if server allows",
            "Add connection timeout / retry logic",
        ],
    },
    "RB-007": {
        "title": "Database Query Performance",
        "url": "",
        "steps": [
            "Run EXPLAIN ANALYZE on slow query",
            "Check for missing indexes",
            "Review recent schema changes or data volume growth",
            "Add query timeout and cache where appropriate",
        ],
    },
    "RB-008": {
        "title": "Docker Container Crash Loop",
        "url": "",
        "steps": [
            "Run: docker logs <container_id> --tail 100",
            "Check resource limits (memory, CPU)",
            "Verify environment variables and secrets are mounted",
            "Check health check configuration",
        ],
    },
    "RB-009": {
        "title": "Network Connectivity / DNS",
        "url": "",
        "steps": [
            "Test DNS resolution from affected host",
            "Check security group / firewall rules",
            "Verify VPC peering or private link configuration",
            "Use traceroute to identify routing issues",
        ],
    },
    "RB-010": {
        "title": "SSO / SAML Misconfiguration",
        "url": "",
        "steps": [
            "Verify Entity ID and ACS URL in IdP matches SP config",
            "Check certificate expiry on both sides",
            "Review attribute mapping (email, name, groups)",
            "Test with SAML tracer browser extension",
        ],
    },
    "RB-011": {
        "title": "Permission / Role Misconfiguration",
        "url": "",
        "steps": [
            "Audit user's current role and permission set",
            "Compare against expected access for their plan/tier",
            "Check for recent role changes or org structure changes",
            "Apply correct role and confirm access",
        ],
    },
    "RB-012": {
        "title": "Data Import Failure",
        "url": "",
        "steps": [
            "Review import error log / failure report",
            "Validate file format and encoding (UTF-8, CSV headers)",
            "Check row count vs imported count for partial failures",
            "Retry with corrected file",
        ],
    },
    "RB-013": {
        "title": "Service Deployment Failure",
        "url": "",
        "steps": [
            "Check deployment logs for error at failing step",
            "Verify image tag / artifact exists",
            "Check resource quotas in target environment",
            "Roll back to last known good version if blocking",
        ],
    },
    "RB-014": {
        "title": "Billing / Subscription Issue",
        "url": "",
        "steps": [
            "Verify payment method is valid and not expired",
            "Check invoice status in billing portal",
            "Confirm subscription tier matches expected features",
            "Escalate to billing team if charge dispute",
        ],
    },
    "RB-000": {
        "title": "Unknown / No Matching Runbook",
        "url": "",
        "steps": [
            "Review ticket manually",
            "Route to appropriate specialist",
            "Document resolution for future runbook creation",
        ],
    },
}
