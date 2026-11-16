# VIN-15 AI Internship Support System — Project Brief

> **Status:** Draft for review · **Version:** 1.1 · **Date:** 2026-11-14 · **Track:** VIN-15, Higher Education & Academic Administration

## Problem

As more students go on company internships, lecturers and the academic affairs office are swamped by the same questions about procedures and credit, and by tracking registrations, weekly logs and evidence by hand. Late or non-compliant students are found too late. Students lose time when a registration is sent back for a missing field or a duration that breaks the rules.

## Solution

An internship portal with AI support that keeps every academic decision with a person.

| User | What the portal does for them |
|---|---|
| **Student** | Fills the registration form from the company's acceptance letter and checks it against the regulation before submission. Shows the milestones with a "next step" line. Handles weekly logs and extension requests. Answers policy questions from the regulation in force, citing the article. |
| **Lecturer** | One approval queue with AI summaries marked as suggestions. A filterable student list with CSV/Excel export. Early warnings for late, low-hours or missing-evidence cases. |
| **Academic affairs** *(optional role)* | Milestone templates, lecturer assignments, accounts, and the regulation library the assistant answers from. |

## Non-negotiables

1. **Human in the loop.** Approvals, exceptions and credit are decided by a lecturer or administrator. The AI may suggest, never decide; this is enforced in code.
2. **Correct citations.** Policy answers cite the regulation in force; without a source the assistant says it does not know.
3. **Privacy.** Data stay within each user's scope and are masked before reaching an AI provider.

## Scope

**In:**
- Sign-in, including SSO.
- Registration with AI extraction and rule checks; outline approval.
- Milestones, evidence, logs, and milestone extensions.
- The cited, streaming policy assistant.
- A monitor with warnings.
- The aggregated list with export, and an audit trail.
- HTTPS and rate limits.

**Out (for now):** company mentor grading, credit recognition, other exception types, LMS sync, analytics dashboard.

## Success measures (targets, not yet measured)

- ≥ 90% of sampled answers cite the right clause.
- ≥ 80% of overdue milestones were warned about first.
- ≤ 15% of warnings dismissed as wrong.
- Median decision time ≤ 3 working days.
- 100% of adversarial questions refused.

## Status and next step

- **Built and running** with demo data.
- **Verified with OpenAI:** all assistant checks pass, p95 2.0 s. Also verified with a self-hosted model and with Keycloak SSO.
- **145 automated tests pass.**
- **Deliverables:** PRD v0.6, wireframes (14 screens, desktop and mobile).
- **Next:** turn the AI features into agents that plan and use tools, with human confirmation for every write:
  - a proactive monitor that also detects work drifting from learning outcomes;
  - a student copilot;
  - a pre-review agent for lecturers.

**Open decisions for the school:** hosted vs self-hosted AI model, the production SSO provider, and the time zone for deadlines.
