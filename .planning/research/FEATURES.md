# Feature Research

**Domain:** Smart home automation suggestion / behavioral pattern mining (Home Assistant custom integration)
**Researched:** 2026-02-22
**Confidence:** MEDIUM — Competitor integrations analyzed directly; UX principles from multiple sources; some claims LOW confidence where smart home ML research is the only support.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Pattern detection from historical state data | Core value: "learns from my behavior" — without this, nothing else matters | HIGH | Must query Recorder DB, handle SQLite + MariaDB, do real statistical analysis; not just counting |
| Confidence score per pattern | Users need a signal of quality; patterns without scores feel arbitrary and untrustworthy | MEDIUM | Score = frequency × consistency; 30-minute time-window bucketing is a known working approach (Danm72 integration) |
| Dismiss / reject suggestions permanently | Users must be able to say "don't show this again" without it reappearing on every scan | LOW | Persistence across restarts required; HA storage helpers work well for this |
| Configurable lookback period | Users have different data depths; some have 7 days, others 6 months. Fixed period = wrong for everyone | LOW | Common values: 7/14/30/90 days. Default 14 days is reasonable |
| Configurable analysis schedule / manual trigger | Users can't wait a week to see if patterns changed; need on-demand scan plus a background cadence | LOW | Service call for on-demand; configurable interval for background. Both are expected |
| Filter by entity domain | Users don't want AC suggestions if they only care about lights; domain filtering is expected | LOW | "Include only" and "Exclude" modes; e.g., only analyze `light`, `switch`, `cover` |
| Exclude specific users / personas | Kids, guests, and service accounts pollute patterns. Users expect this control | LOW | Map HA user IDs to exclusion list; logbook stores context per user |
| Skip patterns already covered by existing automations | Users don't want to create a duplicate of something that already runs; deduplication is assumed | MEDIUM | Must query automation registry; match by entity + time window; heuristic not perfect |
| Dedicated review UI (not just notifications) | A notification is not enough. Users expect a panel to browse, compare, and manage all suggestions | HIGH | HA sidebar panel with WebSocket updates; tabbed interface (suggestions + stale automations) |
| Accept suggestion → creates real HA automation | Core value: "one-click to create." If accepting produces YAML to paste, friction is too high | HIGH | Must call `automation.create` service or write to automations.yaml via config_entries; this is the hardest feature |
| Show pattern examples / evidence | Users won't trust a pattern they can't verify. "Lights on 8/10 mornings at 7:05am" builds trust | MEDIUM | Show last N occurrences, times, days of week, triggering entity state |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but create real competitive advantage.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Presence-based pattern detection | Time-based patterns are expected; presence-based are rare in community tools. "When person arrives → devices activate" is a class most integrations miss | HIGH | Must correlate `person` or `device_tracker` state changes with downstream entity changes; requires join across entity event streams |
| Temporal sequence detection (A → B) | Detecting that "TV on → lights dim within 2 min" is the most sophisticated and useful pattern class; no community tool does this well | HIGH | Window-based co-occurrence; must distinguish causal sequence from coincidence via consistency scoring |
| Stale automation detection | No other integration proactively surfaces automations that have never fired or haven't fired in 30+ days. This is a useful housekeeping feature | MEDIUM | Query `last_triggered` from automation registry; flag disabled or long-inactive automations |
| Pattern preview before accepting | Show the user what the automation will look like in human-readable form before creating it — "Turns on kitchen lights every weekday at 07:05" not raw YAML | MEDIUM | Render YAML as human-readable description; must handle multiple trigger types |
| Customize suggestion before accepting | Let users tweak the time window, threshold, or affected entities before creating. Reduces post-creation edits | HIGH | UI form pre-populated from pattern; writes modified version; requires editing a proposed YAML object |
| Learn from feedback (dismiss trains future analysis) | If a user dismisses "TV on at 9pm" 3 times, the system should stop surfacing similar patterns. Dismissal as implicit negative training signal | MEDIUM | Requires pattern fingerprinting and a blacklist store; improves signal/noise ratio over time |
| Confidence threshold configuration | Users with noisy households need a higher bar (70%+); users with consistent routines want to see even 40% patterns. Configurable = adaptable to household | LOW | Single slider or number input in config flow; changes which patterns surface |
| Pattern category display | Grouping suggestions as "Morning Routines," "Arrival Sequences," "Evening Wind-Down" — domain language that users understand | MEDIUM | Requires classification of detected pattern type; presentation-layer feature more than detection complexity |
| Multi-entity routine detection | "Every morning: coffee maker on, then lights on, then TV on" detected as a single routine block rather than 3 separate suggestions | HIGH | Sequence clustering; requires time-ordered event joining across entities; advanced ML territory |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like good ideas but create significant problems in this context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-create automations without user review | "Set it and forget it" sounds great; reduce friction to zero | Privacy violation (creates rules without consent); wrong patterns get baked in; no trust built; users feel out of control; researched UX literature consistently says user control is non-negotiable in smart home | Always require explicit accept/confirm step. Make it one click, never zero clicks |
| Cloud ML / external API processing | Access to better models; more sophisticated pattern detection | Violates privacy expectation of HA users; requires internet dependency; breaks air-gapped installs; cloud API costs; data sovereignty issues; explicitly out of scope per PROJECT.md | Run everything locally. Use lightweight statistical methods (frequency + consistency scoring) rather than complex cloud models |
| Real-time / streaming pattern detection | Detect patterns as they form, not in batch | HA hardware (RPi 4) can't sustain continuous background inference; real-time scanning would spike CPU and compete with HA itself; no user-visible benefit since patterns form over days | Scheduled batch analysis (background job). On-demand scan for impatient users. Batch is correct architecture |
| Natural language automation description input | "Turn on lights when I get home" typed by user | This is LLM territory; requires AI that doesn't run locally on RPi 4 without serious constraints; scope creep away from pattern mining into chatbot; HA already has voice/LLM features in 2026 | Surface patterns in human-readable language on output side, not input side. Accept suggestions, don't generate from text |
| Lovelace card (in addition to panel) | More flexible placement | Duplicates work; users already embedded in the sidebar panel workflow; cards require separate component lifecycle; increases maintenance surface for marginal placement benefit | Sidebar panel only for v1. Cards can be v2+ if demand is proven |
| Mobile push notifications for new patterns | "Notify me when new patterns are found" | HA's notification system is complex to get right across all notify platforms; patterns are discovered in batch jobs — the timing rarely lines up with user context; notification fatigue is real | Persistent badge/count in sidebar panel. User visits panel when curious. Opt-in notify is v1.x if requested |
| Per-user pattern profiles | Track patterns per household member | Requires reliable user attribution in Recorder (not always present); automation creation targets the home, not a person; massive complexity increase; HA's user model doesn't map cleanly | Single household pattern model for v1. User exclusion (not per-user analysis) addresses the dirty data problem |
| Energy optimization suggestions | "Your TV uses too much standby power" | Different problem domain — energy analysis, not behavioral pattern mining; requires energy data from power monitoring devices (not universal); likely no overlap with auto-pattern's Recorder query model | Stay in behavioral pattern mining lane. Energy patterns are a separate product |

---

## Feature Dependencies

```
[Recorder DB Query Layer]
    └──requires──> [Pattern Detection Engine]
                       └──requires──> [Confidence Scoring]
                                          └──requires──> [Suggestion Storage]
                                                             └──requires──> [Review Panel UI]
                                                                                └──requires──> [Accept → Create Automation]

[Existing Automation Registry Query]
    └──requires──> [Deduplication Filter]
                       └──enhances──> [Pattern Detection Engine] (suppresses redundant suggestions)

[Dismiss / Reject Action]
    └──requires──> [Suggestion Storage] (persistent dismissed list)
    └──enhances──> [Pattern Detection Engine] (optional: learn from dismissals)

[User / Domain Filters]
    └──requires──> [Recorder DB Query Layer] (applied at query time)

[Presence-Based Pattern Detection]
    └──requires──> [Pattern Detection Engine]
    └──requires──> [person / device_tracker entity state data in Recorder]

[Temporal Sequence Detection (A → B)]
    └──requires──> [Pattern Detection Engine]
    └──conflicts──> [Simple frequency counting] (different algorithm path)

[Stale Automation Detection]
    └──requires──> [Existing Automation Registry Query]
    └──independent of──> [Pattern Detection Engine] (separate analysis type)

[Customize Before Accept]
    └──requires──> [Accept → Create Automation]
    └──requires──> [Review Panel UI]

[Learn from Dismissals]
    └──requires──> [Dismiss / Reject Action]
    └──enhances──> [Pattern Detection Engine]
```

### Dependency Notes

- **Recorder DB Query Layer must come first:** Every other feature depends on it. Schema differences between SQLite and MariaDB must be handled at this layer.
- **Confidence Scoring gates Suggestion Storage:** Patterns without scores should not be stored or surfaced. Score is the primary filter before anything reaches the user.
- **Deduplication requires Automation Registry access:** Must be queried during analysis, not just at display time, or deduplication logic is unreliable.
- **Accept → Create Automation is the hardest dependency:** It depends on understanding HA's automation registry API, the YAML structure for each pattern type, and the config entry lifecycle. Plan a full phase around this.
- **Sequence detection conflicts with simple frequency analysis:** These are different algorithm paths. Implement time-based patterns first (simpler), then add sequence detection in a later phase.
- **Stale Automation Detection is independent:** It reads from the automation registry and displays in a separate tab. Can be built in parallel with or after pattern detection.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — validates the core concept: "analyze behavior, surface suggestions, create automations with one click."

- [ ] **Recorder DB query layer** — must handle both SQLite and MariaDB schema; lookback configurable
- [ ] **Time-based routine detection** — lights/switches on at consistent times (frequency + time-window bucketing). The simplest and most universal pattern class.
- [ ] **Confidence score per suggestion** — frequency × consistency; configurable minimum threshold
- [ ] **Existing automation deduplication** — query registry, suppress already-automated patterns
- [ ] **User and domain filtering** — exclude accounts and entity domains from analysis
- [ ] **Persistent dismiss** — dismissed suggestions don't reappear
- [ ] **Sidebar review panel** — shows all suggestions with confidence, entity, time, evidence; manual scan trigger
- [ ] **Accept → real automation creation** — one click creates an active HA automation entity

### Add After Validation (v1.x)

Features to add once core concept is proven working and users are engaging.

- [ ] **Presence-based pattern detection** — add `person`/`device_tracker` correlation; adds a high-value pattern class users ask for most
- [ ] **Temporal sequence detection (A → B)** — when demand for "sequence" patterns is confirmed by user feedback; significant algorithm complexity
- [ ] **Customize before accepting** — edit time, entities, threshold before creating; add when users report they want to tweak before accepting
- [ ] **Stale automation detection tab** — surface unused automations; can ship as soon as registry query layer is stable
- [ ] **Pattern preview in human language** — render suggestion as "Turns on X every weekday at 07:05" before accepting; improves trust

### Future Consideration (v2+)

Features to defer until product-market fit is established and user demand is confirmed.

- [ ] **Multi-entity routine clustering** — "morning routine" as a single block; very high complexity; only worth building if users explicitly ask for it
- [ ] **Learn from dismissals (implicit training)** — pattern fingerprinting + blacklist; adds sophistication; defer until dismiss volume is measurable
- [ ] **Pattern category display** — cosmetic grouping; only worth the work when suggestion volume is high enough to need it
- [ ] **State correlation patterns (temperature → heater)** — explicitly out of scope in PROJECT.md v1; different data model needed

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Time-based routine detection | HIGH | MEDIUM | P1 |
| Confidence scoring | HIGH | LOW | P1 |
| Sidebar review panel | HIGH | MEDIUM | P1 |
| Accept → create automation | HIGH | HIGH | P1 |
| Persistent dismiss | HIGH | LOW | P1 |
| Recorder DB query layer | HIGH | MEDIUM | P1 (foundation) |
| Existing automation deduplication | HIGH | MEDIUM | P1 |
| User/domain filtering | MEDIUM | LOW | P1 |
| Configurable lookback period | MEDIUM | LOW | P1 |
| On-demand / manual scan trigger | MEDIUM | LOW | P1 |
| Presence-based pattern detection | HIGH | HIGH | P2 |
| Stale automation detection | MEDIUM | LOW | P2 |
| Pattern preview in human language | MEDIUM | MEDIUM | P2 |
| Customize before accepting | MEDIUM | HIGH | P2 |
| Temporal sequence detection | HIGH | HIGH | P2 |
| Learn from dismissals | LOW | MEDIUM | P3 |
| Multi-entity routine clustering | MEDIUM | HIGH | P3 |
| Pattern category grouping | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Danm72/automation-suggestions | ITSpecialist111/ai_automation_suggester | TaraHome (Sherrin) | Our Approach |
|---------|-------------------------------|----------------------------------------|-------------------|--------------|
| Pattern source | Logbook history (manual actions) | AI analysis of entity list (no history) | HA action log (manual actions) | Recorder DB historical states (more comprehensive) |
| Detection method | Frequency + time-window bucketing | LLM prompt engineering | Repetition detection (algorithm unspecified) | Statistical frequency + consistency scoring; extend to sequences |
| Confidence score | Yes (consistency %) | No (AI subjective) | Not documented | Yes — central to UX |
| Presence-based patterns | No | No | Not documented | Yes (v1.x) |
| Sequence detection (A→B) | No | No | No | Yes (v1.x) |
| One-click create automation | No (points to Settings > Automations) | No (generates YAML to paste) | Yes (generates YAML automatically) | Yes (direct creation via HA API) |
| Customize before accepting | No | No | Not documented | Yes (v1.x) |
| Persistent dismiss | Yes | No | Not documented | Yes |
| Dedup against existing automations | No | Partially (reads existing automations for context) | No | Yes |
| Stale automation detection | Yes | No | No | Yes (v1.x) |
| Privacy / local only | Yes | No (cloud AI providers) | Yes | Yes (strictly local) |
| Panel UI | Yes (Lovelace card) | No (notifications only) | Not documented | Yes (sidebar panel) |
| Hardware constraint awareness | Not documented | No | Yes | Yes (lightweight algorithms, RPi 4 budget) |

**Key gaps our integration fills:**
1. Presence-based and sequence pattern detection — no competitor does this
2. One-click real automation creation (not YAML-paste) — only TaraHome attempts this
3. Deduplication against existing automations — no competitor does this
4. Strictly local, lightweight ML — ai_automation_suggester requires cloud

---

## Sources

- [GitHub: Danm72/home-assistant-automation-suggestions](https://github.com/Danm72/home-assistant-automation-suggestions) — MEDIUM confidence (direct code/README analysis)
- [GitHub: ITSpecialist111/ai_automation_suggester](https://github.com/ITSpecialist111/ai_automation_suggester) — MEDIUM confidence (direct README analysis)
- [Hackaday: Habit Detection for Home Assistant (TaraHome)](https://hackaday.com/2026/02/08/habit-detection-for-home-assistant/) — MEDIUM confidence (secondary reporting)
- [Home Assistant Roadmap 2025H1](https://www.home-assistant.io/blog/2025/05/09/roadmap-2025h1/) — HIGH confidence (official source)
- [Home Assistant 2026.2 Release Notes](https://www.home-assistant.io/blog/2026/02/04/release-20262) — HIGH confidence (official source)
- [PMC: Personalized Smart Home Automation Using ML](https://pmc.ncbi.nlm.nih.gov/articles/PMC12526510/) — MEDIUM confidence (peer-reviewed research, general domain not HA-specific)
- [FasterCapital: UX in Smart Homes](https://www.fastercapital.com/content/User-experience--UX---UX-in-Smart-Homes--Creating-Intuitive-Smart-Home-Experiences-with-UX.html) — LOW confidence (secondary source, principles only)
- [Tandfonline: Understanding User Experience with Smart Home Products](https://www.tandfonline.com/doi/full/10.1080/08874417.2024.2408006) — MEDIUM confidence (peer-reviewed, UX principles)
- [Rootly: Alert Fatigue Guide](https://rootly.com/on-call-software/alert-fatigue) — LOW confidence (adjacent domain, applied as analogy for notification noise)

---

*Feature research for: Home Assistant behavioral pattern mining / automation suggestion integration*
*Researched: 2026-02-22*
