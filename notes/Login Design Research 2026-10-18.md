# Login design research and options

The user wants a professional, easy-to-navigate, pleasant login page and visual
options before choosing a direction. The recommendation is **Quiet focus**, a
compact centered sign-in card that fits the app's existing warm, restrained style.

## Current page findings

`login.html` reuses `.start-panel`, whose desktop columns are 110px, flexible,
and 220px. The login supplies only one child, so its copy and button occupy the
110px first column. At intermediate widths that first column becomes 90px. A
dedicated login layout would fix this instead of changing workout-panel styling.
The page also repeats its introduction, lacks a recognizable Google logo in the
sign-in action, and retains workout-specific footer information before sign-in.

## Research applied

- Use a recognizable Google sign-in control with its standard multicolor logo,
  approved colors, and clear action label. The existing server redirect can be
  retained; Google's branding guide provides HTML and downloadable button assets.
  Final implementation should use the current approved asset/font specification.
  [Google branding guidelines](https://developers.google.com/identity/branding-guidelines)
- Target at least 4.5:1 contrast for normal text and 3:1 for large text. Avoid pale
  gray helper copy on light cards. These are minimum contrast targets, not a claim
  that a complete implementation is already WCAG conformant.
  [WCAG contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- Use a 48px sign-in target and visible focus. This is a comfortable design target;
  WCAG 2.2 AA's minimum target-size criterion is 24px with specific exceptions.
  [WCAG target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- Keep the sign-in journey focused. The current task has one next action, so
  workout/history/dashboard navigation is unnecessary before authentication.
  [GOV.UK navigation guidance](https://design-system.service.gov.uk/patterns/navigate-a-service/)

The sources inform interaction and accessibility constraints. The three visual
directions and their recommendation are design judgments for this app, rather
than evidence that one aesthetic has been user-tested or improves conversion.

## Options

| Direction | Appearance | Benefit | Tradeoff |
| --- | --- | --- | --- |
| 01 Quiet focus — recommended | Ivory/sage canvas, white centered card, serif greeting, standard Google button | Clear next action, calm presentation, fits the existing app | Less brand storytelling |
| 02 Training journal | Sage editorial panel plus a simple sign-in section; compact stacked mobile layout | Warmer identity and an introduction to what the app does | More copy and desktop space |
| 03 After hours | Charcoal/slate, restrained mint, bold sans-serif type, centered card | Distinct fitness identity and comfortable dark appearance | A larger visual departure from the light workout app |

All options use one Google sign-in action, a short account-privacy statement,
and a truthful approved-account access note. They omit owner email, real workout
previews, invented performance claims, unavailable registration links, password
fields, and speculative navigation. Error and unavailable-state copy is included
in the preview for review. No public invitation workflow is implied.

## Review artifacts and verification

Open [the interactive local preview](Login%20Design%20Options%202026-10-18.html).
It includes all three designs, desktop/mobile width controls, and error-state copy.
The sign-in buttons are intentionally inactive in this visual study.

Desktop and mobile screenshots are in ignored `data/reports/login-design-options/`,
including `comparison.png`. Browser verification exercised each design/width
control, checked 375px viewport layouts for horizontal overflow, checked the 48px
sign-in target, and checked for JavaScript errors. Final production implementation
still needs its own contrast, keyboard, error-state, Google-asset, and browser checks.

The user selected Quiet focus after reviewing these options. It is now implemented
and deployed; the other concepts remain design-study alternatives. Production
verification covered normal/error/unavailable states at desktop and mobile widths,
keyboard focus, text contrast, the current official Google artwork, and live
browser behavior. Details are in the session notes.
