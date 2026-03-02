/**
 * Smart Habits Panel - Full sidebar panel web component for Home Assistant.
 *
 * Displays pattern suggestions grouped by category with accept/dismiss/customize
 * actions and optimistic UI updates. Also shows stale automations section.
 *
 * Registered as: smart-habits-panel
 * Served from: /smart_habits_frontend/smart-habits-panel.js
 */

class SmartHabitsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = { patterns: [], accepted_patterns: [], stale_automations: [] };
    this._loading = false;
    this._error = null;
    this._customizing = null;
    this._customizeData = null;
    this._customizeHour = 0;
    this._allPatterns = [];
  }

  set hass(hass) {
    const isFirst = this._hass === null;
    this._hass = hass;
    if (isFirst) {
      this._loadData();
    }
  }

  connectedCallback() {
    this._render();
  }

  async _loadData() {
    this._loading = true;
    this._render();
    try {
      const result = await this._hass.callWS({ type: "smart_habits/get_patterns" });
      this._data = {
        patterns: result.patterns || [],
        accepted_patterns: result.accepted_patterns || [],
        stale_automations: result.stale_automations || [],
      };
      this._error = null;
    } catch (err) {
      this._error = err.message || String(err);
    }
    this._loading = false;
    this._render();
  }

  async _acceptPattern(pattern, overrides = {}) {
    // Optimistic removal
    this._data.patterns = this._data.patterns.filter((p) => p !== pattern);
    this._render();

    try {
      const response = await this._hass.callWS({
        type: "smart_habits/accept_pattern",
        entity_id: pattern.entity_id,
        pattern_type: pattern.pattern_type,
        peak_hour: pattern.peak_hour,
        secondary_entity_id: pattern.secondary_entity_id || null,
        trigger_hour: overrides.trigger_hour !== undefined ? overrides.trigger_hour : pattern.peak_hour,
        trigger_entities: overrides.trigger_entities || [],
      });
      if (response && response.yaml_for_manual_copy) {
        alert(
          "Automation file could not be written automatically. " +
          "Please copy the following YAML into your automations.yaml:\n\n" +
          response.yaml_for_manual_copy
        );
      }
    } catch (err) {
      // Restore on error
      await this._loadData();
    }
  }

  async _dismissPattern(pattern) {
    // Optimistic removal
    this._data.patterns = this._data.patterns.filter((p) => p !== pattern);
    this._render();

    try {
      await this._hass.callWS({
        type: "smart_habits/dismiss_pattern",
        entity_id: pattern.entity_id,
        pattern_type: pattern.pattern_type,
        peak_hour: pattern.peak_hour,
        secondary_entity_id: pattern.secondary_entity_id || null,
      });
    } catch (err) {
      // Restore on error
      await this._loadData();
    }
  }

  async _openCustomize(pattern) {
    this._customizing = pattern;
    this._customizeData = null;
    this._customizeHour = pattern.peak_hour;
    this._render();

    try {
      const result = await this._hass.callWS({
        type: "smart_habits/preview_automation",
        entity_id: pattern.entity_id,
        pattern_type: pattern.pattern_type,
        peak_hour: pattern.peak_hour,
        secondary_entity_id: pattern.secondary_entity_id || null,
        trigger_hour: pattern.peak_hour,
      });
      this._customizeData = result;
      this._render();
    } catch (err) {
      this._customizeData = { description: "Preview unavailable: " + (err.message || String(err)) };
      this._render();
    }
  }

  _closeCustomize() {
    this._customizing = null;
    this._customizeData = null;
    this._render();
  }

  _acceptCustomized() {
    const pattern = this._customizing;
    const hour = this._customizeHour;
    this._closeCustomize();
    this._acceptPattern(pattern, { trigger_hour: hour });
  }

  // ---- Helpers ----

  _groupPatterns(patterns) {
    const CATEGORY_ORDER = [
      ["daily_routine", "Daily Routines"],
      ["temporal_sequence", "Device Chains"],
      ["presence_arrival", "Arrival Sequences"],
    ];

    const groups = {};
    for (const p of patterns) {
      if (!groups[p.pattern_type]) groups[p.pattern_type] = [];
      groups[p.pattern_type].push(p);
    }

    // Sort within each group by confidence descending
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => b.confidence - a.confidence);
    }

    const result = [];
    for (const [type, label] of CATEGORY_ORDER) {
      if (groups[type] && groups[type].length > 0) {
        result.push([label, groups[type]]);
      }
    }
    return result;
  }

  _formatHour(h) {
    return String(h).padStart(2, "0") + ":00";
  }

  _formatDate(iso) {
    if (!iso) return "Never";
    try {
      return new Date(iso).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch (e) {
      return iso;
    }
  }

  // ---- Rendering ----

  _render() {
    const patterns = this._data.patterns || [];
    const staleAutomations = this._data.stale_automations || [];

    // Rebuild flat pattern list for data-index mapping
    this._allPatterns = [];
    const groups = this._groupPatterns(patterns);
    for (const [, groupPatterns] of groups) {
      for (const p of groupPatterns) {
        this._allPatterns.push(p);
      }
    }

    const isEmpty = patterns.length === 0 && staleAutomations.length === 0;

    let patternsHtml = "";
    if (!this._loading && !this._error) {
      if (isEmpty) {
        patternsHtml = `
          <div class="empty-state">
            No patterns discovered yet. Smart Habits analyzes your device history over time.
            Patterns will appear here once enough data is collected.
          </div>
        `;
      } else {
        // Pattern sections
        for (const [label, groupPatterns] of groups) {
          const cardsHtml = groupPatterns
            .map((p) => {
              const idx = this._allPatterns.indexOf(p);
              const pct = Math.round(p.confidence * 100);
              const secondaryHtml = p.secondary_entity_id
                ? `<div class="secondary">With: ${this._escapeHtml(p.secondary_entity_id)}</div>`
                : "";
              return `
                <div class="pattern-card">
                  <div class="card-header">
                    <span class="entity-name">${this._escapeHtml(p.entity_id)}</span>
                    <span class="confidence">${pct}%</span>
                  </div>
                  <div class="confidence-bar">
                    <div class="confidence-bar-fill" style="width:${pct}%"></div>
                  </div>
                  <div class="card-body">
                    <div class="evidence">${this._escapeHtml(p.evidence || "")}</div>
                    <div class="peak-time">Peak: ${this._formatHour(p.peak_hour)}</div>
                    ${secondaryHtml}
                  </div>
                  <div class="card-actions">
                    <button class="action-accept" data-action="accept" data-index="${idx}">Accept</button>
                    <button class="action-customize" data-action="customize" data-index="${idx}">Customize</button>
                    <button class="action-dismiss" data-action="dismiss" data-index="${idx}">Dismiss</button>
                  </div>
                </div>
              `;
            })
            .join("");

          patternsHtml += `
            <div class="category-section">
              <div class="category-header">${this._escapeHtml(label)} (${groupPatterns.length})</div>
              ${cardsHtml}
            </div>
          `;
        }

        // Stale automations section
        if (staleAutomations.length > 0) {
          const staleCardsHtml = staleAutomations
            .map((s) => {
              const lastTriggered = s.last_triggered
                ? this._formatDate(s.last_triggered)
                : "Never";
              const daysAgo = s.days_since_triggered != null
                ? `${s.days_since_triggered} days ago`
                : "Never triggered";
              return `
                <div class="stale-card">
                  <div class="stale-name">${this._escapeHtml(s.friendly_name || s.entity_id)}</div>
                  <div class="stale-entity">${this._escapeHtml(s.entity_id)}</div>
                  <div class="stale-info">Last triggered: ${this._escapeHtml(lastTriggered)} — ${this._escapeHtml(daysAgo)}</div>
                </div>
              `;
            })
            .join("");

          patternsHtml += `
            <div class="stale-section">
              <div class="category-header">Stale Automations (${staleAutomations.length})</div>
              <p class="stale-subtitle">Automations that haven't triggered in 30+ days</p>
              ${staleCardsHtml}
            </div>
          `;
        }
      }
    }

    // Customize overlay
    let customizeHtml = "";
    if (this._customizing) {
      const desc = this._customizeData
        ? this._escapeHtml(this._customizeData.description || "Loading preview...")
        : "Loading preview...";
      customizeHtml = `
        <div class="customize-overlay">
          <div class="customize-panel">
            <h3>Customize Automation</h3>
            <p class="preview-description">${desc}</p>
            <label>Trigger hour:
              <input type="number" min="0" max="23" value="${this._customizeHour}" data-action="hour-change">
            </label>
            <div class="customize-actions">
              <button class="action-accept" data-action="accept-custom">Accept</button>
              <button class="action-dismiss" data-action="cancel-custom">Cancel</button>
            </div>
          </div>
        </div>
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          overflow-y: auto;
          padding: 0;
        }
        .panel-container { max-width: 800px; margin: 0 auto; padding: 16px; }
        .header h1 { font-size: 24px; font-weight: 400; margin: 0 0 4px; }
        .header .subtitle { color: var(--secondary-text-color); font-size: 14px; margin: 0 0 24px; }
        .category-header {
          color: var(--secondary-text-color);
          font-size: 12px; font-weight: 500;
          text-transform: uppercase; letter-spacing: 0.08em;
          padding: 16px 0 8px;
        }
        .pattern-card, .stale-card {
          background: var(--card-background-color);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          padding: 16px; margin-bottom: 12px;
        }
        .card-header { display: flex; justify-content: space-between; align-items: center; }
        .entity-name { font-weight: 500; font-size: 16px; }
        .confidence { font-size: 14px; font-weight: 500; color: var(--primary-color); }
        .confidence-bar { background: var(--divider-color); height: 4px; border-radius: 2px; margin: 8px 0; }
        .confidence-bar-fill { background: var(--primary-color); height: 4px; border-radius: 2px; }
        .evidence { color: var(--secondary-text-color); font-size: 14px; }
        .peak-time { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
        .secondary { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; }
        .card-actions { display: flex; gap: 8px; margin-top: 12px; }
        button.action-accept {
          background: var(--primary-color); color: var(--text-primary-color);
          border: none; border-radius: 4px; padding: 6px 16px; cursor: pointer; font-size: 14px;
        }
        button.action-customize {
          background: transparent; color: var(--primary-color);
          border: 1px solid var(--primary-color); border-radius: 4px; padding: 6px 16px; cursor: pointer; font-size: 14px;
        }
        button.action-dismiss {
          background: transparent; color: var(--secondary-text-color);
          border: 1px solid var(--divider-color); border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 14px;
        }
        .loading, .error, .empty-state { padding: 32px; text-align: center; color: var(--secondary-text-color); }
        .error { color: var(--error-color, #db4437); }
        .stale-section { margin-top: 32px; }
        .stale-subtitle { color: var(--secondary-text-color); font-size: 13px; margin: 0 0 12px; }
        .stale-name { font-weight: 500; font-size: 15px; }
        .stale-entity { color: var(--secondary-text-color); font-size: 13px; }
        .stale-info { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
        .customize-overlay {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10;
        }
        .customize-panel {
          background: var(--card-background-color); border-radius: 12px;
          padding: 24px; max-width: 400px; width: 90%;
        }
        .customize-panel h3 { margin: 0 0 12px; font-weight: 500; }
        .preview-description { color: var(--secondary-text-color); font-size: 14px; margin-bottom: 16px; }
        .customize-panel label { display: block; font-size: 14px; margin-bottom: 16px; }
        .customize-panel input {
          width: 60px; padding: 4px 8px; border: 1px solid var(--divider-color);
          border-radius: 4px; font-size: 14px; margin-left: 8px;
        }
        .customize-actions { display: flex; gap: 8px; }
      </style>
      <div class="panel-container">
        <div class="header">
          <h1>Smart Habits</h1>
          <p class="subtitle">Discovered patterns from your smart home</p>
        </div>

        ${this._loading ? '<div class="loading">Loading patterns...</div>' : ""}
        ${this._error ? `<div class="error">Error: ${this._escapeHtml(this._error)}</div>` : ""}
        ${!this._loading ? patternsHtml : ""}
      </div>
      ${customizeHtml}
    `;

    this._attachEventListeners();
  }

  _attachEventListeners() {
    const root = this.shadowRoot;
    const elements = root.querySelectorAll("[data-action]");
    for (const el of elements) {
      const action = el.getAttribute("data-action");
      const indexAttr = el.getAttribute("data-index");
      const idx = indexAttr !== null ? parseInt(indexAttr, 10) : null;

      if (action === "accept") {
        el.addEventListener("click", () => {
          const pattern = this._allPatterns[idx];
          if (pattern) this._acceptPattern(pattern);
        });
      } else if (action === "dismiss") {
        el.addEventListener("click", () => {
          const pattern = this._allPatterns[idx];
          if (pattern) this._dismissPattern(pattern);
        });
      } else if (action === "customize") {
        el.addEventListener("click", () => {
          const pattern = this._allPatterns[idx];
          if (pattern) this._openCustomize(pattern);
        });
      } else if (action === "accept-custom") {
        el.addEventListener("click", () => this._acceptCustomized());
      } else if (action === "cancel-custom") {
        el.addEventListener("click", () => this._closeCustomize());
      } else if (action === "hour-change") {
        el.addEventListener("input", (e) => {
          const val = parseInt(e.target.value, 10);
          if (!isNaN(val) && val >= 0 && val <= 23) {
            this._customizeHour = val;
          }
        });
      }
    }
  }

  _escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
}

customElements.define("smart-habits-panel", SmartHabitsPanel);
