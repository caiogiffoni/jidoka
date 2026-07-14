---
name: Jidoka
description: Kanban board driven by hand or by an LLM agent - automation with a human touch.
colors:
  electric-violet: "oklch(0.541 0.281 293.009)"
  electric-violet-dark: "oklch(0.606 0.25 292.717)"
  violet-wash: "oklch(0.943 0.029 294.588)"
  violet-ink: "oklch(0.432 0.232 292.759)"
  ring-violet: "oklch(0.702 0.183 293.541)"
  paper-white: "oklch(1 0 0)"
  ink: "oklch(0.145 0 0)"
  machine-gray: "oklch(0.97 0 0)"
  gray-voice: "oklch(0.556 0 0)"
  hairline: "oklch(0.922 0 0)"
  alarm-red: "oklch(0.577 0.245 27.325)"
  andon-sky: "oklch(0.685 0.169 237.323)"
  andon-amber: "oklch(0.769 0.188 70.08)"
  andon-emerald: "oklch(0.696 0.17 162.48)"
typography:
  headline:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.375
  label:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
  data:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 500
rounded:
  md: "0.5rem"
  lg: "0.625rem"
  xl: "0.875rem"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.electric-violet}"
    textColor: "oklch(0.985 0 0)"
    rounded: "{rounded.lg}"
    height: "2rem"
    padding: "0 10px"
  button-primary-hover:
    backgroundColor: "oklch(0.541 0.281 293.009 / 80%)"
  button-outline:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "2rem"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "2rem"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "2rem"
    padding: "4px 10px"
  task-card:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "12px"
  count:
    typography: "{typography.data}"
    textColor: "{colors.gray-voice}"
---

# Design System: Jidoka

## 1. Overview

**Creative North Star: "The Andon Line"**

Jidoka's interface is a factory line running at speed, with a human hand on the cord. Toyota's andon board is the metaphor, kept at its minimum: each column is a station marked by a small status light (sky for queued, amber for running, emerald for done) - the light, not the wall. Work moves visibly between stations, and the operator can stop, redirect, or approve anything the machine proposes. The system's confident energy comes from responsiveness - optimistic drags, streaming agent actions, cards landing live - never from decoration.

The canvas is near-monochrome and high-contrast (white paper, near-black ink, quiet gray panels), which makes the three andon dots and the single Electric Violet accent read as _signals_, the way status lights read on a quiet factory floor. Electric Violet belongs to action and agency: primary buttons, focus rings, the agent's presence. It is a solid, vivid voice used sparingly - explicitly not the purple-gradient "AI magic" wash of chatbot products, an anti-reference this system rejects by name, along with Jira-style enterprise chrome.

Both a light and a dark theme ship as first-class citizens (class-toggled, system default); the dark theme keeps the same doctrine on near-black surfaces with the violet stepped up in lightness to hold contrast.

**Key Characteristics:**

- High-contrast neutral canvas; color only ever means something
- Column status reduced to a single small dot per station; column surfaces stay neutral
- One accent (Electric Violet) reserved for action, focus, and agent activity
- Flat at rest; shadow and lift are responses to touch
- Fast, tactile motion: ≤150ms transitions, 1px button press, 2° card tilt in flight

## 2. Colors

A near-monochrome canvas where every chromatic value is a signal with a job.

### Primary

- **Electric Violet** (oklch(0.541 0.281 293.009); dark theme: oklch(0.606 0.25 292.717)): the color of action and agency. Primary buttons, focus/selection rings (as **Ring Violet**, oklch(0.702 0.183 293.541), at 50% alpha), links, and anywhere the agent is present or acting. Always solid, never a gradient.
- **Violet Wash** (oklch(0.943 0.029 294.588)) with **Violet Ink** text (oklch(0.432 0.232 292.759)): the quiet tint pair for selected/accented surfaces that need violet identity without full saturation.

### Secondary

The andon lights - column status colors, applied only as the 6px status dot in each column header. Never as surface fills, borders, or text tints:

- **Andon Sky** (oklch(0.685 0.169 237.323)): To do - work queued at the station.
- **Andon Amber** (oklch(0.769 0.188 70.08)): In progress - the line is running.
- **Andon Emerald** (oklch(0.696 0.17 162.48)): Done - the station cleared.

### Neutral

- **Paper White** (oklch(1 0 0)): body and card background in light theme.
- **Ink** (oklch(0.145 0 0)): primary text; also the dark theme's body background.
- **Machine Gray** (oklch(0.97 0 0)): secondary surfaces - column panels (at 50% alpha; 30% in dark), muted fills, hover states, footers.
- **Gray Voice** (oklch(0.556 0 0)): secondary text (descriptions, metadata, counts). Never used on tinted or colored backgrounds.
- **Hairline** (oklch(0.922 0 0)): borders and dividers; in dark theme, white at 10% alpha.
- **Alarm Red** (oklch(0.577 0.245 27.325)): destructive actions and errors only. Rendered as a 10–20% tint fill with red text, not a solid red slab.

### Named Rules

**The Andon Rule.** Sky, amber, and emerald belong to the stations, and only as the header dot. They mark column status and nothing else - never wash a surface with them, never tint text with them, and never let a status color leak onto an action.

**The One Lever Rule.** Electric Violet is the operator's lever: it appears only where a human acts (buttons, focus, selection) or where the agent does (streaming activity, proposals). If violet is on more than ~10% of the screen, something is decoration pretending to be a signal.

## 3. Typography

**UI Font:** Geist (with system-ui, sans-serif fallback)
**Data Font:** Geist Mono (with ui-monospace fallback)

**Character:** One family carries everything. Geist is technical without being cold - tight tracking on headings, medium weights for scannable card titles, and the mono cut reserved for numbers so counts read like instrument readouts.

### Hierarchy

- **Headline** (600, 0.875rem, tracking -0.025em): the app title and top-level page headers, in Ink. There is exactly one per screen; identity comes from restraint, not size.
- **Title** (500–600, 0.875rem, tracking -0.025em): column headers (500) and dialog titles (600), always in Ink - never tinted.
- **Body** (500, 0.875rem, line-height 1.375): card titles - the most-read text in the product. Medium weight keeps them scannable at density.
- **Label** (400, 0.75rem): descriptions, metadata, empty-state hints, in Gray Voice. Clamped to 2 lines on cards.
- **Data** (Geist Mono 500, 0.6875rem, tabular-nums): card counts and any live number. Tabular figures so counts don't jitter as they change.

### Named Rules

**The Instrument Rule.** Every number that can change while you watch (counts, timers, positions) is set in Geist Mono with `tabular-nums`. Prose is never mono; numbers are never proportional.

## 4. Elevation

Flat until touched. Surfaces at rest sit on 1px rings (`ring-1` at foreground/10%) with no shadow at all. Depth is a _response_: hovering a card raises it to a small shadow, and picking one up snaps it to a real drop shadow with a 2° rotation - the signature move of the whole system, the moment the board feels physical. Dropdowns and dialogs earn real shadows because they genuinely float. Nothing else does.

### Shadow Vocabulary

- **Rest**: none. Cards and columns at rest are perfectly flat; the hairline ring is the only edge.
- **Hover-lift** (`box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)`): interactive surfaces under the pointer, paired with the ring darkening to foreground/20% - neutral, not violet; violet waits for commitment.
- **In-flight** (`box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)` + `rotate: 2deg` + 1px Ring Violet at 40%): the dragged card overlay only.

### Named Rules

**The Flat-Until-Touched Rule.** Shadows appear only as a response to state - hover, drag, open. If a surface at rest casts a visible shadow, it's lying about being touched.

## 5. Components

Tactile and quick: everything responds within 150ms, buttons physically press, cards have grab-weight. Consistency is the vocabulary - the same control never dresses differently on two screens.

### Buttons

- **Shape:** gently rounded (0.625rem radius), 2rem tall (default), 0.875rem medium text.
- **Primary:** Electric Violet fill, near-white text; hover dims the fill to 80% opacity.
- **Outline / Ghost / Secondary:** hairline border on paper, or borderless; both hover to Machine Gray.
- **Destructive:** Alarm Red at a 10% tint with red text; hover deepens to 20%. Never a solid red slab.
- **Press:** `active:translate-y-px` - every button physically depresses 1px.
- **Focus:** 3px Ring Violet at 50% alpha plus a violet border. Focus is always visible, never suppressed.
- **Disabled:** 50% opacity, pointer events off.

### Cards (Task Cards)

- **Corner Style:** 0.875rem radius (rounded-xl).
- **Background:** Paper White with a 1px ring at foreground/10% and no shadow at rest.
- **Shadow Strategy:** the flat-until-touched ladder - flat rest → hover-lift → in-flight (see Elevation).
- **Cursor:** `grab` at rest, `grabbing` in flight - the affordance is honest.
- **Internal Padding:** 12px; title in Body style, description in Label style clamped to 2 lines.
- **Drag placeholder:** the vacated slot renders as a dashed muted outline with contents hidden - a chalk outline where the card was.

### Columns

- **Style:** 18rem wide, 0.875rem radius, Machine Gray panel at 50% alpha (30% in dark), borderless, 8px internal padding. The panel recedes; the cards are the content.
- **Header:** status dot (6px circle in the station's solid color - the only color on the column), name in Ink at Title weight, plain mono count in Gray Voice pushed to the far edge. No badge pill.
- **Drop feedback:** a 1px Ring Violet ring at 50% while a card hovers over - the one moment the column speaks violet.
- **Empty state:** a dashed hairline slot reading "Drop tasks here" in Gray Voice - the empty state teaches the gesture.

### Inputs / Fields

- **Style:** transparent background, hairline border, 0.625rem radius, 2rem tall.
- **Focus:** border shifts to Ring Violet with a 3px violet ring at 50% - identical to button focus.
- **Error:** Alarm Red border with a 20% red ring (`aria-invalid`), same geometry as focus.
- **Placeholder:** Gray Voice.

### Dialogs & Menus

- Real floating surfaces: popover background, hairline border, genuine shadow (they earn it), 0.875rem radius. Used for task detail and creation; menus for small action sets.

### The Drag Overlay (signature component)

The card in flight is the system's proof of physicality: rendered in a `DragOverlay` above everything, rotated 2°, in-flight shadow, Ring Violet at 40%. When the agent later moves cards itself, the same visual grammar shows the machine's hand doing what yours does.

## 6. Do's and Don'ts

### Do:

- **Do** keep Electric Violet solid and scarce - actions, focus, selection, agent presence, per the One Lever Rule.
- **Do** keep every surface neutral; the status dot is the only place a station color appears (the Andon Rule).
- **Do** give every interactive element the full state set: default, hover, focus-visible, active, disabled - and honest cursors (`grab`/`grabbing` on draggables).
- **Do** keep transitions between 100–150ms with standard easing; motion conveys state, not decoration.
- **Do** set live numbers in Geist Mono with `tabular-nums` (the Instrument Rule).
- **Do** maintain WCAG 2.1 AA: ≥4.5:1 body contrast, visible focus everywhere, keyboard-operable drag-and-drop, `prefers-reduced-motion` alternatives for the drag tilt and any streaming animation.
- **Do** ship both themes with every new surface - dark is class-toggled, not an afterthought.

### Don't:

- **Don't** use purple gradients, sparkle emoji, or "AI magic" glow. PRODUCT.md names _AI-chatbot-first UI_ as an anti-reference; the agent's presence is shown by the board moving, not by branding.
- **Don't** add Jira-style enterprise chrome - no toolbar stacks, no nested settings surfaces, no blue-gray corporate density. The board stays a board.
- **Don't** let station colors (sky/amber/emerald) appear anywhere but the column-header dot (the Andon Rule) - no washes, no tinted borders, no colored text.
- **Don't** cast shadows at rest (the Flat-Until-Touched Rule) - and never use `border-left` stripes as accents.
- **Don't** use spinners in content areas; loading is skeletons shaped like the cards they become.
- **Don't** exceed 150ms on UI transitions or add entrance choreography to page loads - this is a tool, users load into a task.
- **Don't** put Gray Voice text on tinted or colored backgrounds; it reads washed out and fails contrast.
