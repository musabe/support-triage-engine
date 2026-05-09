"""
tests/test_classifier.py — Integration tests for the triage classifier
Run: pytest tests/ -v
"""

import asyncio
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from classifier import classify_ticket


SAMPLE_TICKETS = [
    {
        "text": "Webhook deliveries failing with 401 after OAuth token rotation",
        "expected_severity": "HIGH",
        "expected_category_contains": "OAuth",
    },
    {
        "text": "Database completely unreachable — all users blocked from logging in. Production down.",
        "expected_severity": "CRITICAL",
        "expected_category_contains": "Database",
    },
    {
        "text": "How do I export my data to CSV?",
        "expected_severity": "LOW",
        "expected_category_contains": "How-To",
    },
    {
        "text": "API rate limit errors appearing sporadically — some requests succeed, others fail with 429",
        "expected_severity_in": ["MEDIUM", "HIGH"],
        "expected_category_contains": "Rate",
    },
    {
        "text": "Docker container keeps crashing on startup — crash loop in production k8s cluster",
        "expected_severity": "HIGH",
        "expected_category_contains": "Docker",
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLE_TICKETS)
async def test_classify_ticket(sample):
    """Test that each sample ticket returns a valid classification."""
    result = await classify_ticket(sample["text"])

    # Must have required fields
    assert "severity" in result
    assert "category" in result
    assert "confidence" in result
    assert "runbook_id" in result
    assert "next_step" in result

    # Severity must be valid
    assert result["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    # Confidence must be in range
    assert 0.0 <= result["confidence"] <= 1.0

    # Check severity expectation
    if "expected_severity" in sample:
        assert result["severity"] == sample["expected_severity"], \
            f"Expected {sample['expected_severity']}, got {result['severity']}"

    if "expected_severity_in" in sample:
        assert result["severity"] in sample["expected_severity_in"], \
            f"Expected one of {sample['expected_severity_in']}, got {result['severity']}"

    # Check category
    if "expected_category_contains" in sample:
        assert sample["expected_category_contains"].lower() in result["category"].lower(), \
            f"Expected category to contain '{sample['expected_category_contains']}', got '{result['category']}'"


@pytest.mark.asyncio
async def test_empty_ticket_does_not_crash():
    """Edge case: empty string should return a safe fallback."""
    result = await classify_ticket("")
    assert "severity" in result
    assert result["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
