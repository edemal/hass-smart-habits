---
status: testing
phase: 08-sidebar-panel
source: 08-01-SUMMARY.md, 08-02-SUMMARY.md
started: 2026-03-02T09:00:00Z
updated: 2026-03-02T09:00:00Z
---

## Current Test

number: 1
name: Panel appears in sidebar
expected: |
  After installing the integration, a "Smart Habits" entry appears in the HA sidebar navigation with a brain icon (mdi:brain). Clicking it opens the panel.
awaiting: user response

## Tests

### 1. Panel appears in sidebar
expected: After installing the integration, a "Smart Habits" entry appears in the HA sidebar navigation with a brain icon (mdi:brain). Clicking it opens the panel.
result: [pending]

### 2. Pattern suggestions load and display
expected: The panel loads pattern data via WebSocket and displays pattern cards. Each card shows entity name, confidence bar (colored green/yellow/orange), evidence text (e.g. "happened 8 of last 10 days"), and peak hour.
result: [pending]

### 3. Patterns grouped by category
expected: Pattern cards are organized under category headers — "Daily Routines", "Device Chains", "Arrival Sequences". Patterns within each group are sorted by confidence (highest first).
result: [pending]

### 4. Accept a pattern suggestion
expected: Clicking Accept on a pattern card immediately removes the card from the list (no page reload). A real automation is created and visible in Settings > Automations.
result: [pending]

### 5. Dismiss a pattern suggestion
expected: Clicking Dismiss on a pattern card immediately removes the card from the list (no page reload). The pattern does not reappear after refreshing the panel.
result: [pending]

### 6. Customize before accepting
expected: Clicking Customize opens an overlay showing a human-readable description of the automation (e.g. "Turns on kitchen lights every weekday at 07:05") and an editable trigger hour field. Changing the hour and clicking Accept creates the automation with the customized time.
result: [pending]

### 7. Stale automations section
expected: Below the pattern suggestions, a "Stale Automations" section shows automations that haven't fired in 30+ days. Each entry displays the automation's friendly name, entity ID, last triggered date, and days since last triggered.
result: [pending]

### 8. Empty state
expected: When no pattern suggestions exist, the panel shows a friendly message indicating patterns will appear over time (not a blank screen or error).
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Gaps

[none yet]
