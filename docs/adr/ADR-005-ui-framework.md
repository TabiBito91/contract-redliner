# ADR-005: UI Framework & Component Library

## Status: Accepted

## Context

The frontend requires complex interactive components (PRD Section 10):
- Side-by-side diff panels with synchronized scrolling
- Inline/unified diff view with red/blue change highlighting
- Change navigation ("Previous/Next Change" controls)
- Expandable change detail panels with AI summaries and risk badges
- Version selector tabs for multi-document sessions
- Drag-and-drop file upload zone
- Summary dashboard with charts and filterable lists
- Data tables for the change summary export configuration
- Must meet WCAG 2.1 AA accessibility standards (NFR-07)

Per ADR-001, the frontend is React 18+ with TypeScript, built with Vite.

## Options Considered

### Option A: React + shadcn/ui (Radix primitives + Tailwind CSS)

Headless UI primitives from Radix UI, styled with Tailwind CSS via shadcn/ui's copy-paste component model.

| Dimension | Assessment |
|---|---|
| Component richness | Good base set (dialog, tabs, dropdown, tooltip, accordion). No built-in diff viewer or side-by-side panels - must be custom-built. |
| Bundle size | Excellent - tree-shakable, only imports what's used. Tailwind purges unused CSS. |
| Accessibility | Excellent - Radix primitives are WAI-ARIA compliant by default. |
| Customization | Excellent - full control, components are local source code. |
| Dev velocity | Medium - need to build diff-specific components from scratch. |
| Ecosystem | Large - most popular React component system in 2025-2026. |

### Option B: React + Ant Design

Full-featured enterprise component library with 60+ components.

| Dimension | Assessment |
|---|---|
| Component richness | Excellent - tables, tabs, upload, collapse panels, badges, charts (via Ant Charts). Built-in diff viewer: no. |
| Bundle size | Large (~1MB+ for full import). Tree-shakable but still heavy. |
| Accessibility | Moderate - improving but historically weaker than Radix. |
| Customization | Moderate - theme system exists but overriding deeply is painful. |
| Dev velocity | High for standard UI patterns, but custom diff views still needed. |
| Ecosystem | Large - popular in enterprise React apps. |

### Option C: React + Mantine

Modern React component library with hooks-first approach, built-in dark mode, and rich component set.

| Dimension | Assessment |
|---|---|
| Component richness | Very good - 100+ components, good tables, tabs, file input, notifications. |
| Bundle size | Medium (~500KB). Better than Ant Design, worse than shadcn. |
| Accessibility | Good - follows WAI-ARIA practices. |
| Customization | Good - CSS-in-JS with full theme override support. |
| Dev velocity | High - many ready-to-use components, good documentation. |
| Ecosystem | Growing - active development, good community. |

### Option D: React + Headless UI + Custom CSS

Headless UI from Tailwind Labs + fully custom CSS. Minimal library approach.

| Dimension | Assessment |
|---|---|
| Component richness | Minimal - only a few primitives (Dialog, Menu, Listbox, Tabs, Switch). Everything else custom. |
| Bundle size | Smallest possible. |
| Accessibility | Good - Headless UI components are accessible. |
| Customization | Total - everything is custom. |
| Dev velocity | Low - must build most components from scratch. |
| Ecosystem | Small - Headless UI has fewer components than Radix. |

## Comparison Matrix

| Criterion (Weight) | A: shadcn/ui | B: Ant Design | C: Mantine | D: Headless UI |
|---|---|---|---|---|
| Diff UI capability (25%) | 7/10 | 6/10 | 7/10 | 7/10 |
| Dev velocity (25%) | 8/10 | 8/10 | 9/10 | 5/10 |
| Bundle size (15%) | 9/10 | 4/10 | 7/10 | 10/10 |
| Accessibility (15%) | 10/10 | 6/10 | 8/10 | 8/10 |
| Customization (10%) | 10/10 | 5/10 | 7/10 | 10/10 |
| Ecosystem/community (10%) | 9/10 | 8/10 | 7/10 | 5/10 |
| **Weighted Score** | **8.35** | **6.40** | **7.70** | **6.90** |

## Decision: Option A - React + shadcn/ui (Radix + Tailwind CSS)

## Rationale

1. **Best accessibility out of the box.** Radix primitives are WAI-ARIA compliant by default, directly supporting NFR-07 (WCAG 2.1 AA). No extra work needed for keyboard navigation, screen reader support, or focus management on dialogs/dropdowns/tabs.

2. **Optimal bundle size.** Tailwind CSS purges unused styles. shadcn/ui components are source code in the project (not node_module dependencies), so only what's used ships. This keeps the app fast for the "upload to redline in 60 seconds" UX goal (NFR-06).

3. **Full customization.** The diff viewer, side-by-side panels, and synchronized scrolling are all custom components regardless of library choice. shadcn/ui gives us the best primitives (Tabs, Dialog, Tooltip, Accordion, Dropdown) while leaving full control for the custom diff rendering.

4. **Largest ecosystem.** shadcn/ui is the dominant React component system, meaning abundant community examples, patterns, and extensions.

5. **No diff view exists in any library.** Since the core diff rendering (red strikethrough / blue underline, side-by-side panels, connecting lines) must be custom-built regardless, the library choice matters primarily for surrounding UI (navigation, upload, settings, summary dashboard). shadcn/ui excels at these "standard" UI patterns while staying out of the way for custom work.

## Consequences

- Frontend built with React 18 + TypeScript + Vite
- UI components from shadcn/ui (Radix + Tailwind CSS)
- Custom components needed: DiffViewer (side-by-side + inline), ChangeNavigator, SyncScrollPanel, RiskBadge, VersionTabs
- Tailwind CSS for styling with custom theme tokens for the red/blue color system
- All standard UI (dialogs, tabs, dropdowns, tooltips, tables) from shadcn/ui
- File upload via react-dropzone (lightweight, accessible)
