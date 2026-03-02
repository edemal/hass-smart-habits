/**
 * Smart Habits Panel - Sidebar panel web component for Home Assistant.
 *
 * This is a minimal stub that HA can load as a custom panel.
 * It will be fully replaced with the feature-complete panel in Plan 02.
 *
 * Registered as: smart-habits-panel
 * Served from: /smart_habits_frontend/smart-habits-panel.js
 */

class SmartHabitsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._initialized = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._render();
    }
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          padding: 16px;
          box-sizing: border-box;
        }
        .loading {
          text-align: center;
          padding: 48px;
          color: var(--secondary-text-color);
        }
      </style>
      <div class="loading">Smart Habits panel loading...</div>
    `;
  }
}

customElements.define("smart-habits-panel", SmartHabitsPanel);
