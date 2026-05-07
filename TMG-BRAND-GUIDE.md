# TMG Brand Guide
### The Mallory Group — AI Agent & Copilot Implementation Reference
**Owner:** Ross Mallory | **Version:** 2.0

> **For AI agents (GitHub Copilot, Wix Velo AI, Claude, etc.):** This file is the single source of truth for all TMG visual design. When generating or editing any code in this repository, apply these standards without requiring further instruction. All styles, components, and layouts must conform to this guide.
>
> **CDN distribution:** Once `tmg.css` is published to `https://rmallorybpc.github.io/tmg-brand-guide/dist/tmg.css`, add the following to every repo's `<head>` instead of copying the CSS manually:
> ```html
> <link rel="stylesheet" href="https://rmallorybpc.github.io/tmg-brand-guide/dist/tmg.css">
> ```

---

## 1. Identity

| Property | Value |
|---|---|
| Full name | The Mallory Group |
| Abbreviation | TMG |
| Logo mark | `TM` + vertical sage divider line + `G` |
| Logo font | Inter or system stack — weight 500, 17px |
| Logo construction | `<span>TM</span><div class="tmg-logo-divider"></div><span>G</span>` |

**Logo divider spec:**
- Width: `2px`
- Height: `20px`
- Color: `#84A98C` (Sage)
- Border-radius: `2px`
- Margin: `0 1px`

---

## 2. Repo File Tree

When creating a new TMG repo or the central `tmg-brand-guide` repo, use this structure:

```
tmg-brand-guide/
├─ TMG-BRAND-GUIDE.md          ← this file (drop in every repo root)
├─ design-tokens.json          ← machine-readable tokens for Style Dictionary / Wix
├─ dist/
│  └─ tmg.css                  ← single distributable stylesheet (CDN link above)
├─ src/
│  ├─ css/
│  │  └─ _variables.css
│  ├─ react/
│  │  ├─ components/
│  │  │  ├─ Header.jsx
│  │  │  ├─ Footer.jsx
│  │  │  ├─ Card.jsx
│  │  │  ├─ MetricTile.jsx
│  │  │  ├─ FilterPanel.jsx
│  │  │  └─ ChartContainer.jsx
│  │  ├─ index.js
│  │  └─ types.d.ts
│  └─ snippets/
│     ├─ header.html
│     └─ footer.html
├─ storybook/
│  └─ stories/
│     └─ Card.stories.jsx
├─ prompts/
│  └─ copilot-templates.md
└─ migration-checklists/
   ├─ nflanalysis.md
   ├─ pdf-multi-agent-analysis.md
   ├─ housing-market-intel.md
   ├─ real-estate-report.md
   └─ recipes.md
```

---

## 3. Design Tokens (`design-tokens.json`)

Machine-readable source of truth. Tools like Style Dictionary, Wix token importer, and Figma Tokens can consume this directly.

```json
{
  "name": "tmg",
  "version": "2.0",
  "colors": {
    "cream":        "#FDFCF0",
    "charcoal":     "#2D3436",
    "sage":         "#84A98C",
    "sage-hover":   "#6B8F74",
    "white":        "#FFFFFF",
    "text-muted":   "rgba(45, 52, 54, 0.55)",
    "text-hint":    "rgba(45, 52, 54, 0.35)",
    "border":       "rgba(45, 52, 54, 0.12)",
    "border-hover": "rgba(132, 169, 140, 0.50)",
    "table-header": "rgba(132, 169, 140, 0.15)",
    "success":      "#2E8540",
    "warning":      "#C47F00",
    "error":        "#B00020"
  },
  "semantic": {
    "bg":      "#FDFCF0",
    "surface": "#FFFFFF",
    "text":    "#2D3436",
    "accent":  "#84A98C"
  },
  "typography": {
    "font-family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    "font-sizes": {
      "h1":         "28px",
      "h2":         "20px",
      "h3":         "16px",
      "body":       "16px",
      "body-sm":    "13px",
      "label":      "13px",
      "label-caps": "12px",
      "metric":     "28px"
    },
    "line-heights": {
      "body":    1.7,
      "heading": 1.3
    },
    "weights": {
      "regular": 400,
      "medium":  500
    }
  },
  "spacing": {
    "xs": "4px",
    "sm": "12px",
    "md": "20px",
    "lg": "24px",
    "xl": "32px"
  },
  "radii": {
    "bento":    "16px",
    "nav":      "8px",
    "button":   "8px",
    "dropdown": "10px"
  },
  "elevation": {
    "sm": "0 1px 3px rgba(45, 52, 54, 0.08)",
    "md": "0 2px 8px rgba(45, 52, 54, 0.10)"
  },
  "layout": {
    "nav-height":        "56px",
    "card-gap":          "24px",
    "card-padding":      "20px",
    "card-padding-wide": "24px",
    "page-padding":      "24px",
    "container-max":     "1280px",
    "bento-min-col":     "280px"
  }
}
```

---

## 4. Color Palette

All colors must be applied via CSS custom properties. **Never hardcode hex values inline** — always reference the variable.

```css
:root {
  /* ── Core palette ── */
  --tmg-cream:        #FDFCF0;   /* Page background */
  --tmg-charcoal:     #2D3436;   /* Primary text, primary buttons */
  --tmg-sage:         #84A98C;   /* Accent, hover states, table headers, dividers */
  --tmg-sage-hover:   #6B8F74;   /* Sage darkened ~15% for hover/active */
  --tmg-white:        #FFFFFF;   /* Card backgrounds, nav background */

  /* ── Semantic aliases ── */
  --tmg-bg:           var(--tmg-cream);
  --tmg-text:         var(--tmg-charcoal);
  --tmg-accent:       var(--tmg-sage);
  --tmg-surface:      var(--tmg-white);

  /* ── Status colors ── */
  --tmg-success:      #2E8540;
  --tmg-warning:      #C47F00;
  --tmg-error:        #B00020;

  /* ── Borders ── */
  --tmg-border:       1px solid rgba(45, 52, 54, 0.12);
  --tmg-border-hover: 1px solid rgba(132, 169, 140, 0.50);

  /* ── Radii ── */
  --tmg-bento-radius: 16px;
  --tmg-nav-radius:   8px;
  --tmg-btn-radius:   8px;

  /* ── Spacing ── */
  --tmg-gap:          24px;
  --tmg-gap-sm:       12px;

  /* ── Elevation ── */
  --tmg-shadow-sm:    0 1px 3px rgba(45, 52, 54, 0.08);
  --tmg-shadow-md:    0 2px 8px rgba(45, 52, 54, 0.10);
}
```

### Color usage rules

| Element | Value |
|---|---|
| Page / site background | `--tmg-cream` |
| Body text | `--tmg-charcoal` |
| Card / panel backgrounds | `--tmg-white` |
| Accent lines, tags, icons | `--tmg-sage` |
| Table header background | `rgba(132, 169, 140, 0.15)` |
| Primary button background | `--tmg-charcoal` |
| Primary button text | `--tmg-white` |
| Primary button hover | `#3D4446` |
| Ghost button border | `rgba(45, 52, 54, 0.20)` |
| Ghost button hover border + text | `--tmg-sage` / `--tmg-sage-hover` |
| Nav background | `--tmg-white` |
| Dropdown item hover bg | `rgba(132, 169, 140, 0.12)` |
| Muted / secondary text | `rgba(45, 52, 54, 0.55)` |
| Hint / disabled text | `rgba(45, 52, 54, 0.35)` |

---

## 5. Typography

| Property | Value |
|---|---|
| Font family | `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` |
| Font weights | **400** (regular), **500** (medium). Never use 600 or 700. |
| Base size | `16px` |
| Line height | `1.7` (body), `1.3` (headings) |
| Case | Sentence case always. Never ALL CAPS or Title Case in content. |

**Google Fonts import** (add to `<head>` whenever Inter is needed):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap" rel="stylesheet">
```

### Type scale classes

```css
.tmg-eyebrow    { font-size: 13px;  font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: var(--tmg-sage); }
.tmg-h1         { font-size: 28px;  font-weight: 500; line-height: 1.3; color: var(--tmg-charcoal); }
.tmg-h2         { font-size: 20px;  font-weight: 500; line-height: 1.3; color: var(--tmg-charcoal); }
.tmg-h3         { font-size: 16px;  font-weight: 500; line-height: 1.3; color: var(--tmg-charcoal); }
.tmg-body       { font-size: 16px;  font-weight: 400; line-height: 1.7; color: var(--tmg-charcoal); }
.tmg-body-sm    { font-size: 13px;  font-weight: 400; color: var(--tmg-charcoal); }
.tmg-label      { font-size: 13px;  font-weight: 500; color: var(--tmg-charcoal); }
.tmg-label-caps { font-size: 12px;  font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(45,52,54,0.50); }
.tmg-metric     { font-size: 28px;  font-weight: 500; color: var(--tmg-charcoal); }
.tmg-text-muted { color: rgba(45, 52, 54, 0.55); }
.tmg-text-accent{ color: var(--tmg-sage); }
```

---

## 6. Navigation Component

The nav appears on every page. Sticky, white background, fixed height of `56px`.

```
[TMG Logo]                              [TMG Tool Suite ▾]
```

### HTML
```html
<nav class="tmg-nav" role="banner">
  <div class="tmg-logo" aria-label="The Mallory Group">
    <span>TM</span>
    <div class="tmg-logo-divider" aria-hidden="true"></div>
    <span>G</span>
  </div>
  <div class="tmg-dropdown-wrap">
    <button class="tmg-dropdown-btn" id="tmgDdBtn"
            aria-haspopup="true" aria-expanded="false" aria-controls="tmgDdMenu">
      TMG Tool Suite
      <svg class="tmg-chevron" viewBox="0 0 12 12" fill="none" width="12" height="12" aria-hidden="true">
        <path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
    <div class="tmg-dropdown-menu" id="tmgDdMenu" role="menu">
      <a href="https://rmallorybpc.github.io/pdf-multi-agent-analysis/" target="_blank" rel="noreferrer" role="menuitem">PDF Multi-Agent Analysis</a>
      <a href="https://rmallorybpc.github.io/housing-market-intel/" target="_blank" rel="noreferrer" role="menuitem">Housing Market Intel</a>
      <a href="https://rmallorybpc.github.io/real-estate-report/" target="_blank" rel="noreferrer" role="menuitem">Real Estate Report</a>
      <a href="https://rmallorybpc.github.io/nflanalysis/dashboard/src/" target="_blank" rel="noreferrer" role="menuitem">NFL Analysis</a>
      <a href="https://rmallorybpc.github.io/recipes/" target="_blank" rel="noreferrer" role="menuitem">Recipe Book</a>
      <!-- ADD NEW TOOLS HERE — also update section 14 manifest -->
    </div>
  </div>
</nav>
```

### CSS
```css
.tmg-nav {
  position: sticky; top: 0; z-index: 100;
  background: var(--tmg-white); border-bottom: var(--tmg-border);
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.tmg-logo {
  display: flex; align-items: center;
  font-size: 17px; font-weight: 500; letter-spacing: 0.02em;
  color: var(--tmg-charcoal); text-decoration: none;
}
.tmg-logo-divider {
  width: 2px; height: 20px;
  background: var(--tmg-sage); border-radius: 2px; margin: 0 1px;
}
.tmg-dropdown-wrap { position: relative; }
.tmg-dropdown-btn {
  background: transparent; border: 1px solid rgba(45,52,54,0.20);
  border-radius: var(--tmg-btn-radius); padding: 7px 14px;
  font-size: 13px; font-weight: 500; color: var(--tmg-charcoal);
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  font-family: inherit; transition: background 0.15s;
}
.tmg-dropdown-btn:hover,
.tmg-dropdown-btn.open       { background: rgba(132,169,140,0.10); }
.tmg-dropdown-btn:focus-visible { outline: 3px solid rgba(132,169,140,0.35); outline-offset: 2px; }
.tmg-chevron                 { transition: transform 0.2s; flex-shrink: 0; }
.tmg-dropdown-btn.open .tmg-chevron { transform: rotate(180deg); }
.tmg-dropdown-menu {
  display: none; position: absolute; right: 0; top: calc(100% + 6px);
  background: var(--tmg-white); border: var(--tmg-border);
  border-radius: 10px; padding: 6px; min-width: 220px;
  z-index: 200; box-shadow: var(--tmg-shadow-md);
}
.tmg-dropdown-menu.open { display: block; }
.tmg-dropdown-menu a {
  display: block; padding: 8px 12px; border-radius: 6px;
  font-size: 13px; color: var(--tmg-charcoal); text-decoration: none;
  transition: background 0.12s, color 0.12s;
}
.tmg-dropdown-menu a:hover { background: rgba(132,169,140,0.12); color: var(--tmg-sage-hover); }
.tmg-dropdown-menu a:focus-visible { outline: 2px solid var(--tmg-sage); outline-offset: -2px; border-radius: 6px; }
```

### JavaScript
```javascript
(function () {
  const btn  = document.getElementById('tmgDdBtn');
  const menu = document.getElementById('tmgDdMenu');
  if (!btn || !menu) return;

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    const isOpen = menu.classList.toggle('open');
    btn.classList.toggle('open', isOpen);
    btn.setAttribute('aria-expanded', String(isOpen));
  });

  document.addEventListener('click', function () {
    menu.classList.remove('open');
    btn.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      menu.classList.remove('open');
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
      btn.focus();
    }
  });
})();
```

---

## 7. Layout & Bento Grid

All page content is organized into bento cards on a cream background.

```css
.tmg-page {
  background: var(--tmg-bg);
  min-height: 100vh;
  padding: var(--tmg-gap);
}

.tmg-container {
  max-width: 1280px;
  margin: 0 auto;
}

.tmg-bento-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--tmg-gap);
}

.tmg-card {
  background: var(--tmg-white);
  border: var(--tmg-border);
  border-radius: var(--tmg-bento-radius);
  padding: 20px;
}

.tmg-card-wide {
  background: var(--tmg-white);
  border: var(--tmg-border);
  border-radius: var(--tmg-bento-radius);
  padding: 24px;
  grid-column: 1 / -1;
}

.tmg-card-label  { font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(45,52,54,0.50); margin: 0 0 8px; }
.tmg-card-title  { font-size: 16px; font-weight: 500; color: var(--tmg-charcoal); margin: 0 0 14px; }
.tmg-card-value  { font-size: 28px; font-weight: 500; color: var(--tmg-charcoal); margin: 0 0 4px; }
.tmg-card-sub    { font-size: 12px; color: var(--tmg-sage); margin: 0; }
.tmg-trend-up    { color: var(--tmg-success); font-size: 13px; font-weight: 500; }
.tmg-trend-down  { color: var(--tmg-error);   font-size: 13px; font-weight: 500; }

.tmg-page-header { margin-bottom: var(--tmg-gap); }
.tmg-page-title  { font-size: 28px; font-weight: 500; color: var(--tmg-charcoal); margin: 0 0 8px; }
.tmg-page-desc   { font-size: 15px; color: rgba(45,52,54,0.60); margin: 0; }

.tmg-footer {
  padding: 20px 24px; text-align: center;
  font-size: 13px; color: rgba(45,52,54,0.50);
  border-top: var(--tmg-border); margin-top: var(--tmg-gap);
}
```

### Page header template
```html
<div class="tmg-page-header">
  <p class="tmg-eyebrow">The Mallory Group</p>
  <h1 class="tmg-page-title">Tool name here</h1>
  <p class="tmg-page-desc">One sentence describing what this tool does.</p>
</div>
```

### Metric card template
```html
<div class="tmg-card" role="group" aria-label="[Metric name]">
  <div class="tmg-card-label">Active tools</div>
  <div class="tmg-card-value">5</div>
  <div class="tmg-card-sub">Across all domains</div>
</div>
```

---

## 8. Buttons

Two button types only.

```css
.tmg-btn {
  background: var(--tmg-charcoal); color: var(--tmg-white);
  border: none; border-radius: var(--tmg-btn-radius);
  padding: 10px 16px; font-size: 13px; font-weight: 500;
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  font-family: inherit; transition: background 0.15s;
}
.tmg-btn:hover          { background: #3D4446; }
.tmg-btn:active         { transform: scale(0.98); }
.tmg-btn:focus-visible  { outline: 3px solid rgba(45,52,54,0.20); outline-offset: 2px; }

.tmg-btn-ghost {
  background: transparent; color: var(--tmg-charcoal);
  border: 1px solid rgba(45,52,54,0.20); border-radius: var(--tmg-btn-radius);
  padding: 10px 16px; font-size: 13px; font-weight: 500;
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  font-family: inherit; transition: border-color 0.15s, color 0.15s;
}
.tmg-btn-ghost:hover        { border-color: var(--tmg-sage); color: var(--tmg-sage-hover); }
.tmg-btn-ghost:active       { transform: scale(0.98); }
.tmg-btn-ghost:focus-visible{ outline: 3px solid rgba(132,169,140,0.35); outline-offset: 2px; }
```

---

## 9. Data Tables

```css
.tmg-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tmg-table th {
  background: rgba(132,169,140,0.15); color: var(--tmg-charcoal);
  font-weight: 500; font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.04em; padding: 9px 14px; text-align: left;
  border-bottom: 1px solid rgba(132,169,140,0.25);
}
.tmg-table td          { padding: 9px 14px; border-bottom: 1px solid rgba(45,52,54,0.07); color: var(--tmg-charcoal); }
.tmg-table tr:last-child td { border-bottom: none; }
.tmg-table tr:hover td { background: rgba(132,169,140,0.04); }
```

Always wrap tables in a `.tmg-card` and add `scope="col"` to `<th>` elements:
```html
<div class="tmg-card">
  <table class="tmg-table">
    <thead><tr><th scope="col">Column A</th><th scope="col">Column B</th></tr></thead>
    <tbody><tr><td>Value</td><td>Value</td></tr></tbody>
  </table>
</div>
```

---

## 10. Form Inputs

```css
.tmg-input, .tmg-select, .tmg-textarea {
  width: 100%; background: var(--tmg-white); color: var(--tmg-charcoal);
  border: var(--tmg-border); border-radius: var(--tmg-btn-radius);
  padding: 9px 12px; font-size: 14px; font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s; box-sizing: border-box;
}
.tmg-input:focus,
.tmg-select:focus,
.tmg-textarea:focus   { outline: none; border-color: var(--tmg-sage); box-shadow: 0 0 0 3px rgba(132,169,140,0.15); }
.tmg-input::placeholder { color: rgba(45,52,54,0.35); }
.tmg-field-label      { display: block; font-size: 13px; font-weight: 500; color: var(--tmg-charcoal); margin-bottom: 6px; }
```

---

## 11. Accessibility

TMG targets **WCAG 2.1 AA**. Apply these base rules to every page.

```css
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0;
  margin: -1px; overflow: hidden; clip: rect(0,0,0,0);
  white-space: nowrap; border: 0;
}
:focus-visible {
  outline: 3px solid rgba(132,169,140,0.40);
  outline-offset: 2px;
}
```

### Accessibility checklist (run before shipping any tool)

- [ ] All images have descriptive `alt` text (`alt=""` for decorative).
- [ ] All form inputs have associated `<label>` elements — not just placeholders.
- [ ] All interactive elements are keyboard-operable.
- [ ] `:focus-visible` ring is visible on all focusable elements.
- [ ] Body text contrast: `#2D3436` on `#FDFCF0` = 12.1:1 ✓ passes AA.
- [ ] Sage on white (`#84A98C` / `#FFFFFF` = 3.0:1) — decorative and large text only, not body copy.
- [ ] `aria-label` or `aria-labelledby` on all landmark regions.
- [ ] Nav dropdown: `aria-expanded` + `aria-haspopup="true"` on button.
- [ ] Tables: `scope="col"` on all `<th>` elements.
- [ ] No information conveyed by color alone — pair with text or icon.
- [ ] Single `<h1>` per page matching the tool name.
- [ ] `role="group"` + `aria-label` on all metric cards.
- [ ] Charts include a text alternative (`description` prop or linked data table).

### NFL analysis contrast fix (priority migration)

```css
/* Add to nflanalysis/src/styles.css */
body        { background: var(--tmg-bg); color: var(--tmg-text); }
.site-bg,
.page-bg    { background: var(--tmg-cream) !important; }
canvas      { background: var(--tmg-white); border-radius: var(--tmg-bento-radius); }
```

---

## 12. React Component Scaffolds

Copy into `src/react/components/` in any React-based TMG repo.

### Header.jsx
```jsx
import React from "react";
import PropTypes from "prop-types";

export default function Header({ brand = "The Mallory Group", links = [] }) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const close = () => setOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  return (
    <header className="tmg-nav" role="banner">
      <div className="tmg-logo" aria-label={brand}>
        <span>TM</span>
        <div className="tmg-logo-divider" aria-hidden="true" />
        <span>G</span>
      </div>
      <nav aria-label="TMG Tool Suite">
        <div className="tmg-dropdown-wrap">
          <button
            className={`tmg-dropdown-btn${open ? " open" : ""}`}
            aria-haspopup="true"
            aria-expanded={open}
            onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
          >
            TMG Tool Suite
            <svg className="tmg-chevron" viewBox="0 0 12 12" fill="none" width="12" height="12" aria-hidden="true">
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          {open && (
            <div className="tmg-dropdown-menu open" role="menu">
              {links.map(l => (
                <a key={l.href} href={l.href} target="_blank" rel="noreferrer" role="menuitem">{l.label}</a>
              ))}
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}

Header.propTypes = {
  brand: PropTypes.string,
  links: PropTypes.arrayOf(PropTypes.shape({ label: PropTypes.string, href: PropTypes.string }))
};
```

### Card.jsx
```jsx
import React from "react";
import PropTypes from "prop-types";

export default function Card({ children, title, wide = false }) {
  const id = title ? `card-${title.toLowerCase().replace(/\s+/g, "-")}` : undefined;
  return (
    <section className={wide ? "tmg-card-wide" : "tmg-card"} aria-labelledby={id}>
      {title && <h3 id={id} className="tmg-card-title">{title}</h3>}
      {children}
    </section>
  );
}

Card.propTypes = { title: PropTypes.string, wide: PropTypes.bool, children: PropTypes.node };
```

### MetricTile.jsx
```jsx
import React from "react";
import PropTypes from "prop-types";

export default function MetricTile({ label, value, sub, trend }) {
  return (
    <div className="tmg-card" role="group" aria-label={label}>
      <div className="tmg-card-label">{label}</div>
      <div className="tmg-card-value">{value}</div>
      {sub && <div className="tmg-card-sub">{sub}</div>}
      {trend !== undefined && (
        <div className={trend >= 0 ? "tmg-trend-up" : "tmg-trend-down"} aria-live="polite">
          {trend >= 0 ? `▲ ${trend}%` : `▼ ${Math.abs(trend)}%`}
        </div>
      )}
    </div>
  );
}

MetricTile.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  sub: PropTypes.string,
  trend: PropTypes.number
};
```

### ChartContainer.jsx
```jsx
import React from "react";
import PropTypes from "prop-types";

export default function ChartContainer({ title, description, children }) {
  return (
    <div className="tmg-card-wide" role="region" aria-label={title}>
      {title && <h4 className="tmg-card-title">{title}</h4>}
      {description && <p className="sr-only">{description}</p>}
      <div className="chart-area">{children}</div>
    </div>
  );
}

ChartContainer.propTypes = {
  title: PropTypes.string,
  description: PropTypes.string,
  children: PropTypes.node
};
```

### FilterPanel.jsx
```jsx
import React from "react";
import PropTypes from "prop-types";

export default function FilterPanel({ filters = [], onFilter }) {
  return (
    <div className="tmg-card" role="search" aria-label="Filter panel">
      {filters.map(f => (
        <div key={f.key} style={{ marginBottom: "16px" }}>
          <label className="tmg-field-label" htmlFor={`filter-${f.key}`}>{f.label}</label>
          <select
            id={`filter-${f.key}`}
            className="tmg-select"
            defaultValue={f.default}
            onChange={e => onFilter?.(f.key, e.target.value)}
          >
            {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      ))}
    </div>
  );
}

FilterPanel.propTypes = {
  filters: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string,
    label: PropTypes.string,
    default: PropTypes.string,
    options: PropTypes.arrayOf(PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }))
  })),
  onFilter: PropTypes.func
};
```

### types.d.ts
```typescript
export interface NavLink        { label: string; href: string; }
export interface FilterOption   { value: string; label: string; }
export interface Filter         { key: string; label: string; default?: string; options: FilterOption[]; }

export interface HeaderProps         { brand?: string; links?: NavLink[]; }
export interface CardProps           { title?: string; wide?: boolean; children?: React.ReactNode; }
export interface MetricTileProps     { label: string; value: string | number; sub?: string; trend?: number; }
export interface ChartContainerProps { title?: string; description?: string; children?: React.ReactNode; }
export interface FilterPanelProps    { filters?: Filter[]; onFilter?: (key: string, value: string) => void; }
```

---

## 13. Spacing & Layout Reference

| Token | Value | Usage |
|---|---|---|
| `--tmg-gap` | `24px` | Between bento cards |
| `--tmg-gap-sm` | `12px` | Within cards, between small elements |
| `--tmg-bento-radius` | `16px` | Card border-radius |
| `--tmg-btn-radius` | `8px` | Buttons, inputs, dropdowns |
| Page padding | `24px` all sides | `.tmg-page` |
| Card padding | `20px` | `.tmg-card` |
| Card padding (wide) | `24px` | `.tmg-card-wide` |
| Container max-width | `1280px` | `.tmg-container` |
| Nav height | `56px` | Fixed |

---

## 14. Tool Manifest

Update this table and the nav HTML (section 6) whenever a new tool is added.

| Tool name | URL | Category |
|---|---|---|
| PDF Multi-Agent Analysis | `https://rmallorybpc.github.io/pdf-multi-agent-analysis/` | AI / Document |
| Housing Market Intel | `https://rmallorybpc.github.io/housing-market-intel/` | Real Estate |
| Real Estate Report | `https://rmallorybpc.github.io/real-estate-report/` | Real Estate |
| NFL Analysis | `https://rmallorybpc.github.io/nflanalysis/dashboard/src/` | Sports |
| Recipe Book | `https://rmallorybpc.github.io/recipes/` | Home / Lifestyle |

> **For Copilot:** All nav links use `target="_blank" rel="noreferrer"`. When adding a tool, add a row here AND an `<a role="menuitem">` in the nav HTML in section 6.

---

## 15. Copilot Prompt Templates

Paste these verbatim into GitHub Copilot Chat (`Ctrl+I` / `Cmd+I`).

### Prompt A — Apply design tokens
```
Read TMG-BRAND-GUIDE.md. Import or inline the CSS variables from section 4 into the :root of this project's main stylesheet. Apply --tmg-cream as the body background and --tmg-charcoal as the default text color. Add the Inter Google Font import to <head>.
```

### Prompt B — Add the global nav
```
Read TMG-BRAND-GUIDE.md section 6. Add the sticky TMG navigation header to this page using the exact HTML, CSS, and JavaScript shown. Preserve all tool URLs exactly as listed. Add aria-expanded and aria-haspopup="true" to the dropdown button. Use target="_blank" rel="noreferrer" on all links.
```

### Prompt C — Bento-ify the layout
```
Read TMG-BRAND-GUIDE.md sections 7–10. Refactor this page's main content into the TMG bento box layout. Wrap each distinct section in a .tmg-card. Apply a CSS grid with grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)) and 24px gap. Apply .tmg-btn to primary actions, .tmg-btn-ghost to secondary, and .tmg-table to all data tables. Add scope="col" to table headers.
```

### Prompt D — New React component
```
Read TMG-BRAND-GUIDE.md section 12. Create a React component named [ComponentName] using the patterns shown. Include PropTypes matching types.d.ts, relevant aria attributes, and use only tmg-* CSS classes for styling. Export a Storybook story showing the default state and at least one variant.
```

### Prompt E — New tool page scaffold
```
Read TMG-BRAND-GUIDE.md. Generate a complete index.html for a new TMG tool called "[TOOL NAME]". Include: Inter font import, link to tmg.css, the sticky nav with all current tool links from section 14, a .tmg-page-header with eyebrow/title/description, a .tmg-bento-grid with at least 2 metric cards and 1 .tmg-card-wide, the nav dropdown JavaScript, and the .sr-only accessibility class.
```

### Prompt F — Accessibility audit
```
Read TMG-BRAND-GUIDE.md section 11. Audit this file against the TMG accessibility checklist. Report each failing item with the element selector and the required fix. Then apply all fixes automatically.
```

---

## 16. Wix / Velo Implementation Notes

Wix does not support CSS custom properties in its global scope. Use raw hex values in all Velo code.

| Token | Hex / value | Wix usage |
|---|---|---|
| `--tmg-cream` | `#FDFCF0` | Site Background color in Design panel |
| `--tmg-charcoal` | `#2D3436` | Primary text color |
| `--tmg-sage` | `#84A98C` | Accent 1, button hover |
| `--tmg-white` | `#FFFFFF` | Card/box backgrounds |
| `--tmg-bento-radius` | `16px` | Box corner radius |
| Border | `rgba(45,52,54,0.12)` | Box border color, 1px width |

### Wix element mappings

- **Site background:** Design panel → Colors → Background → `#FDFCF0`
- **Body font:** Design panel → Text → Inter (Google Fonts), weights 400 and 500 only
- **TMG logo:** Text `TM` + vertical Line (color `#84A98C`, 2px × 20px) + Text `G`, grouped
- **Bento card:** Box → Background `#FFFFFF`, Border 1px `rgba(45,52,54,0.12)`, Corner radius `16px`
- **Primary button:** Fill `#2D3436`, Text `#FFFFFF`, hover fill `#3D4446`
- **Ghost button:** Fill transparent, Border `rgba(45,52,54,0.20)`, hover border `#84A98C`

### Velo nav dropdown code
```javascript
import wixWindow from "wix-window";

$w.onReady(function () {
  let menuOpen = false;

  $w("#btnToolSuite").onClick(e => {
    e.preventDefault();
    menuOpen = !menuOpen;
    menuOpen ? $w("#boxToolMenu").show() : $w("#boxToolMenu").hide();
    $w("#btnToolSuite").style.backgroundColor = menuOpen
      ? "rgba(132,169,140,0.10)"
      : "transparent";
  });

  $w("#sectionPage").onClick(() => {
    if (menuOpen) { menuOpen = false; $w("#boxToolMenu").hide(); }
  });
});
```

---

*Version 2.0 — 2026 — The Mallory Group*
*To add a new tool: update section 14 (manifest) + section 6 (nav HTML) + commit this file to the new repo.*
