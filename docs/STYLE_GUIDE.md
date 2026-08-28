# Feather style guide

This guide records the visual and CSS decisions for the Article Contest Tool. The current product direction is a light, quiet interface built around the slate/navy palette used by `/review-v2`.

## Visual direction

Use an airy editorial layout with clear reading order. Pages should feel like one product: a soft blue-gray canvas, white working surfaces, navy text, restrained shadows, and blue actions. Avoid dark panels, high-contrast decorative textures, heavy gradients, and unrelated visual treatments between routes.

The home page is one continuous surface. Its welcome area flows directly into contest discovery; do not add a wave, hard divider, or second background band. Contest dashboards may use purposeful panels, but their spacing, borders, and colors should come from the same tokens.

## Core tokens

These variables live in `frontend-vue/src/styles/light-theme.css`:

| Token | Value | Use |
| --- | --- | --- |
| `--feather-bg` | `#e7f0f8` | Page canvas |
| `--feather-surface` | `#ffffff` | Cards, panels, forms |
| `--feather-surface-alt` | `#f4f8fb` | Table headers, secondary strips |
| `--feather-border` | `#c7d6e3` | Borders and separators |
| `--feather-text` | `#20364d` | Headings and primary text |
| `--feather-muted` | `#47637c` | Supporting text and metadata |
| `--feather-accent` | `#355b80` | Links and primary actions |

Semantic colors remain limited to status meaning: green for accepted/active, red for rejected/errors, and amber for pending/warnings. Status colors should use a pale background with readable dark text in light mode.

## Typography and geometry

- Use Inter for interface text, with the existing system fallbacks.
- Use Linux Libertine, Georgia, or Times for editorial contest titles when a page already uses that treatment.
- Keep body text around `0.85rem–1rem`; labels and metadata can be smaller but must remain readable.
- Use 8–14px radii for controls and panels. Reserve larger radii for prominent hero surfaces.
- Prefer 1px borders and soft shadows such as `0 8px 24px rgba(32,54,77,.08)`.
- Use generous whitespace and avoid stacking several nested cards around the same content.

## Navigation

The app navbar is defined in `frontend-vue/src/styles/App.css`. It uses a white translucent shell, a blue-gray brand mark, a pale active route state, a compact account pill, and a light outlined sign-out action. Keep the navbar height and horizontal rhythm consistent across routes. On small screens, hide secondary navigation and retain the account and sign-out controls.

Contest-level navigation belongs to `ContestLayout.css`. It should visually belong to the same shell, while the full-screen review routes use their own top bar.

## CSS ownership

- `frontend-vue/src/style.css` contains only structural defaults, base typography, box sizing, and scrollbar defaults.
- `frontend-vue/src/styles/light-theme.css` is the single shared light-theme layer. Put cross-route tokens and common Codex/form/table overrides here.
- `frontend-vue/src/styles/App.css` owns the app shell, navbar, login state, overload notice, and cookie-consent panel.
- `frontend-vue/src/styles/views/*.css` owns styles for individual views. Every view should use an external `<style scoped src="...">` reference.
- `ReviewQueue.css` owns the review shell. Keep its light/dark theme variables and its dynamic iframe CSS isolated from the rest of the application.

Do not add large `<style>` blocks back into Vue files. Do not duplicate global tokens or copy the same button/card rules into multiple views. Add a shared rule only when at least two routes genuinely need it.

## Component rules

Cards and panels use white surfaces, `--feather-border`, and a low-opacity navy shadow. Primary buttons use `--feather-accent` with white text. Secondary buttons use white backgrounds, a border, and accent text. Inputs and selects are white with navy text, light borders, and a blue focus ring.

Tables should use a pale alternate header and a very light alternating row state. Links use `--feather-accent`; do not use gray links for interactive content. Empty states should be quiet and centered, with a pale icon container instead of a dark block.

## Review route exception

`/jury/review` and `/jury/review-v2` are full-screen workspaces. They may use the ReviewQueue theme switch and review-specific tokens. Normal application rules must exclude `.rq-app`, and normal page redesigns must not change the review workflow, queue density, iframe preview, bulk comment panel, or review action bar.

## Maintenance workflow

1. Put new shared visual decisions in `light-theme.css` and view-specific decisions in the owning external CSS file.
2. Check desktop and mobile widths before finishing a visual change.
3. Search for hard-coded dark values (`#0a0a0a`, `#111`, dark navy surfaces, or white-on-dark controls) in the affected route.
4. Run `npm.cmd run build` from `frontend-vue`.
5. Update `AGENTS.md` for every code or style change, including new files and architecture changes.
6. Rebuild `frontend-vue/dist` when the deployed SPA bundle is part of the repository workflow.

The visual redesign work used the `frontend-app-builder` skill, with `/review-v2` treated as the existing visual reference. The prose and editing pass for this guide used the `human-writing-style` skill.
