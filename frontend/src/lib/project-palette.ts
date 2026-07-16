// Categorical palette for project identity in the weekly time chart.
// Distinct in hue from Electric Violet (--primary, ~293deg, reserved for
// human/agent action) and the three andon status hues (sky ~237deg,
// amber ~70deg, emerald ~162deg, reserved for the column-header dot) per
// DESIGN.md's One Lever Rule and Andon Rule.
//
// Validated with the dataviz skill's six-checks validator against both
// chart surfaces used in this app - light #ffffff and dark #0a0a0a
// (matching --background: oklch(0.145 0 0) in .dark) - zero WARNs, zero
// FAILs on both runs, so one set of hex values covers both themes (no
// .dark override needed). Re-run before changing any of these:
//
//   node <dataviz-skill-dir>/scripts/validate_palette.js \
//     "#da4620,#009fa3,#3c79f0,#c547a3" --mode light --surface "#ffffff"
//   node <dataviz-skill-dir>/scripts/validate_palette.js \
//     "#da4620,#009fa3,#3c79f0,#c547a3" --mode dark --surface "#0a0a0a"
export const PROJECT_PALETTE = [
  "#da4620", // slot 0 - terracotta (oklch(0.60 0.19 35))
  "#009fa3", // slot 1 - teal       (oklch(0.60 0.19 195))
  "#3c79f0", // slot 2 - indigo     (oklch(0.60 0.19 262))
  "#c547a3", // slot 3 - rose       (oklch(0.60 0.19 340))
] as const;

// Index is the project's position in the created_at-ordered list (see
// weekly-chart.ts / chart-legend.tsx) - purely a display detail, not a
// persisted identity. Deleting or reordering projects can reassign colors;
// that's an accepted tradeoff, not a bug.
export function projectColor(index: number): string {
  return PROJECT_PALETTE[index % PROJECT_PALETTE.length];
}
