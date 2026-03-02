# Smart Habits

**Discover your real smart home habits and turn them into automations — automatically.**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-blue.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Smart Habits watches your smart home history, finds patterns in how you actually use your devices, and surfaces them as suggestions in a dedicated sidebar panel. When you see a pattern you like, one click turns it into a real Home Assistant automation — no YAML, no rule editor, no manual setup required.

---

## Features

### Pattern Detection

Smart Habits detects three types of behavioral patterns from your state history:

**Daily Routines**
Recurring device activations at consistent times of day. For example: kitchen lights turn on every weekday around 7:05 AM, or the coffee maker switches on every morning between 6:50 and 7:10.

**Temporal Sequences**
One device activates, then another follows within a short time window. For example: the TV turns on and the soundbar follows within 2 minutes, or the bedroom lamp turns on and the fan follows within 5 minutes.

**Presence Arrivals**
A person arrives home and devices activate shortly after. For example: you arrive home and the hallway lights turn on, or your partner arrives and the heating bumps up.

### Smart Ranking and Management

- **Confidence scoring** — patterns are ranked by how consistently they occur. A pattern that fires 9 out of 10 times scores higher than one that fires 4 out of 10.
- **Evidence strings** — each suggestion shows how many times the pattern was observed and over what period.
- **One-click automation creation** — accept a suggestion and Smart Habits writes a real HA automation entity to your `automations.yaml` file and reloads it immediately.
- **Customizable suggestions** — before accepting, adjust the trigger time, entities, or conditions to match your preferences exactly.
- **Dismiss patterns** — hide suggestions you don't want; dismissed patterns will not reappear.
- **Stale automation detection** — the panel flags automations created by Smart Habits that haven't fired in 30 or more days, so you can review and clean them up.

---

## Prerequisites

- **Home Assistant 2024.11 or later** — required for the sidebar panel (uses `StaticPathConfig`)
- **Recorder integration enabled** — enabled by default in all standard HA installations
- **At least 7 days of state history** — more history means more reliable pattern detection; 30 days is recommended

---

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three-dot menu in the top right and select **Custom repositories**
3. Add `edemal/hass-smart-habits` as an **Integration**
4. Search for "Smart Habits" in HACS and click **Download**
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** and search for "Smart Habits"

### Manual

1. Download or clone this repository
2. Copy the `custom_components/smart_habits/` directory into your HA configuration directory:
   ```
   <config>/custom_components/smart_habits/
   ```
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** and search for "Smart Habits"

---

## Configuration

### Initial Setup

During the initial setup wizard, you select how far back Smart Habits should look when analyzing your history:

| Option | Description |
|--------|-------------|
| Lookback Days | How many days of history to analyze (7 / 14 / **30** / 90) |

The default of 30 days works well for most households. Use 90 days if your routines vary seasonally.

### Options (Reconfigure after install)

Go to **Settings → Devices & Services → Smart Habits → Configure** to adjust:

| Option | Default | Choices | Description |
|--------|---------|---------|-------------|
| Lookback Days | 30 days | 7, 14, 30, 90 | How far back to analyze state history |
| Analysis Interval | 1 day | 1, 3, 7 days | How often Smart Habits re-analyzes your history |
| Sequence Window | 300 s (5 min) | 60, 120, 300, 600, 900 s | Maximum gap between events to be considered a temporal sequence |

**Lookback Days:** Longer lookback periods detect more patterns but take slightly more time to analyze. If you have a powerful machine, 90 days gives the most robust results.

**Analysis Interval:** Every 1 day means Smart Habits runs a fresh analysis each day, which keeps suggestions current. If analysis is too frequent, bump this to 3 or 7 days.

**Sequence Window:** Controls how tightly coupled two events must be to form a sequence. A 300-second window means Device B must activate within 5 minutes of Device A. Tighten this if you're getting false positives, or expand it for slower routines.

---

## Usage

### Opening the Panel

Click the **brain icon** (`mdi:brain`) in the Home Assistant sidebar. If you don't see it, ensure the integration is installed and HA has been restarted after installation.

### Reading Pattern Cards

The panel groups suggestions into three categories: **Morning Routines**, **Arrival Sequences**, and **Device Chains**. Each card shows:

- **Pattern description** — a plain-English summary of what was detected
- **Confidence percentage** — how consistently this pattern occurs in your history
- **Evidence string** — how many times the pattern was observed (e.g., "Observed 27 times over 30 days")

### Acting on Suggestions

Each card has three actions:

| Action | What it does |
|--------|--------------|
| **Accept** | Creates a real HA automation immediately and adds it to `automations.yaml` |
| **Dismiss** | Hides this pattern permanently — it won't appear again |
| **Customize** | Opens an edit form to adjust the trigger time or entities before accepting |

### Stale Automations

At the bottom of the panel, Smart Habits lists any automations it previously created that haven't triggered in 30 or more days. You can delete them directly from the panel or leave them if the routine is just seasonal.

### Manual Scan

By default, Smart Habits re-analyzes your history on its configured interval. To trigger a scan immediately:

- **Developer Tools → Services → `smart_habits.trigger_scan`**

---

## How It Works

Smart Habits reads your state change history directly from the Recorder database — the same database HA uses for history graphs and logbook entries. No external APIs, no cloud services, no data leaves your home.

**Analysis process:**

1. Load state changes for the configured lookback period
2. Filter to relevant entity domains (lights, switches, sensors, people, device trackers)
3. Run three independent detectors in background threads — never blocking the HA event loop
4. Score and deduplicate results, filtering out patterns below the confidence threshold (60% by default)
5. Persist results to HA's built-in storage so they survive restarts

The analysis runs in executor threads and is designed to be lightweight enough to run comfortably on a Raspberry Pi 4.

---

## Technical Details

For advanced users and contributors:

- **Zero external dependencies** — pure Python standard library only
- **WebSocket API** — 5 commands: `smart_habits/get_patterns`, `smart_habits/dismiss_pattern`, `smart_habits/accept_pattern`, `smart_habits/preview_automation`, `smart_habits/trigger_scan`
- **Deterministic automation IDs** — each accepted pattern maps to a stable ID (prefixed `smart_habits_`), preventing duplicate automations if you accept the same pattern twice
- **Storage versioning** — pattern and acceptance data stored via HA's `helpers.storage.Store` with version tracking for future migrations
- **Panel** — a single-file web component (`panel.js`) registered via `StaticPathConfig`; no build step required

---

## Troubleshooting

**No patterns are being suggested**

- Smart Habits needs at least 5 occurrences of a pattern before surfacing it. If your installation is new, wait a few days and trigger a manual scan.
- Confirm the Recorder integration is active: **Settings → System → Logs** should show no Recorder errors.
- Check that your devices use the supported entity domains: `light`, `switch`, `binary_sensor`, `input_boolean`, `person`, `device_tracker`. Entities in other domains (e.g., `number`, `climate`) are not analyzed.
- Try increasing the Lookback Days option to 90 days for more data.

**An automation was not created after accepting a pattern**

- Check that `automations.yaml` is writable by the HA process. If your config uses `!include_dir_merge_list` instead of a single `automations.yaml`, the write will fail — Smart Habits requires a flat `automations.yaml` file.
- Check HA logs (**Settings → System → Logs**) for any error from `smart_habits.automation_creator`.
- After fixing the issue, you can re-accept the same pattern — Smart Habits will not create a duplicate.

**The sidebar panel does not appear**

- Confirm you are running Home Assistant 2024.11 or later.
- Restart Home Assistant fully after installation (not just a configuration reload).
- Check logs for any error mentioning `smart_habits` and `StaticPathConfig`.

**Triggering a manual scan**

Go to **Developer Tools → Services**, select `smart_habits.trigger_scan`, and click **Call Service**. The analysis runs in the background; refresh the panel after a few seconds to see updated results.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Issues and feature requests: [github.com/edemal/hass-smart-habits/issues](https://github.com/edemal/hass-smart-habits/issues)
