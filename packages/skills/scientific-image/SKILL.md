---
name: scientific-image
description: Generate a publication-quality scientific diagram or schematic (pathway, network, workflow, comparison, architecture, heatmap, tree) via the MCP's image generator and register it as a figure on a paper. Use when the user says "draw the pathway," "make a schematic," "generate a figure showing X," "diagram the workflow," "show me a model of …".
---

# /scientific-image

**Triggers:** "draw a pathway diagram of …", "schematic of …", "show
the model architecture," "make a figure of the workflow," "diagram
the relationship between …".

## What it does

A staged pipeline around `mcp__co_scientist__generate_image`:

1. **Classify** the diagram type (pathway / network / workflow /
   comparison / architecture / heatmap / tree / freeform schematic).
2. **Blueprint** the entities, relationships, and spatial layout
   BEFORE generating — pinning structure prevents the LLM-painter
   from inventing relationships that don't exist.
3. **Generate** with a structured prompt that bakes in the blueprint.
4. **Critique** the result against style rules; iterate up to 3
   times if needed.
5. **Register** as a figure on the paper (or save as asset for
   exploratory shots).

`generate_image` routes through the Pro Cloud Function (gpt-image-2)
or falls back to the user's local Gemini key for free tier — the
skill is provider-agnostic.

## Hard rules

- **NEVER skip the blueprint step**, even for simple diagrams. The
  blueprint is your source of truth — the painter LLM lies; the
  blueprint doesn't.
- **NEVER chain >3 edits**. After three iterations on the same image
  the text fidelity degrades visibly. Start fresh with a tightened
  prompt instead.
- **NEVER inline-render data values** (numbers, p-values, gene names)
  if the audience needs precision — the painter mis-spells. Use
  numbered labels in the figure and a real key in the caption.
- **ALWAYS register through `add_figure` if it's going in the
  manuscript**. Otherwise it sits as an asset (use `figure_number`
  unset; the tool stores it under `papers/{slug}/assets/`).

## Flow

### 1. Classify diagram type

Quick keyword sniff:

| Type           | Keywords / cue                                       |
| -------------- | ---------------------------------------------------- |
| `pathway`      | "pathway," "signaling," gene/metabolite cascade      |
| `network`      | "interaction," "graph," "PPI"                        |
| `workflow`     | "pipeline," "flowchart," "steps," "method overview"  |
| `comparison`   | "vs," "before/after," "wild-type vs mutant"          |
| `architecture` | "model," "system," "block diagram"                   |
| `heatmap`      | "expression heatmap" (better produced via `analysis-run` + matplotlib, NOT this skill) |
| `tree`         | "phylogeny," "lineage," "hierarchy"                  |

If the user wants real data plots (heatmap, scatter, bar) — defer to
`/analysis-run`; this skill is for SCHEMATICS only.

### 2. Blueprint

Spell out before generating:

```
Title: <figure title>
Type: pathway
Aspect: 16:9
Background: clean white, scientific journal style

Entities (each gets a label, a position, a glyph):
  A. EGF (ligand, top-left, blue receptor-shaped)
  B. EGFR (membrane receptor, top-center, blue)
  C. RAS (small GTPase, mid-center, green diamond)
  D. ERK (kinase, mid-right, orange rounded rect)
  E. Nucleus (bottom-right, gray ellipse)

Relationships (each gets an arrow style):
  A → B: binding (solid black, T-shape)
  B → C: activation (solid black, →)
  C → D: phosphorylation, multi-step (dashed black, → with "P")
  D → E: translocation (curved arrow into nucleus)

Spatial:
  - Membrane runs horizontally across the top third
  - Cytoplasm fills middle
  - Nucleus is bottom-right with thick boundary
  - Labels outside elements, not inside, to keep text crisp
```

Show this to the user, ask for confirmations / tweaks. THEN generate.

### 3. Build the prompt + generate

From the blueprint, write a single prompt for the painter:

```
"A clean schematic pathway diagram, scientific journal style, white
background. Show EGF (blue ligand glyph, top-left) binding to EGFR
(blue receptor crossing a horizontal membrane line). EGFR activates
RAS (green diamond, mid-center) which activates ERK (orange rounded
rectangle, mid-right). ERK phosphorylates and translocates into the
nucleus (gray ellipse, bottom-right). Solid black arrows for direct
activation, dashed arrow with 'P' label for phosphorylation. Labels
outside each element. 16:9 aspect, minimal color palette."
```

Then:

```
result = mcp__co_scientist__generate_image(
  slug,
  prompt=<full prompt>,
  figure_number=<N>,                    # if registering immediately
  asset_filename=<name.png>,            # if exploring (no fig number)
  aspect_ratio="16:9",
  caption="<draft caption matching blueprint>",
)
```

### 4. Critique + iterate (max 3)

Inspect the output:
- All entities present? Spelled correctly?
- Relationships go the right direction?
- Spatial layout matches blueprint?
- Labels outside, not inside?

If something's off, tighten the prompt — call out the SPECIFIC
problem the painter introduced. E.g., "the previous version put EGFR
inside the nucleus; instead, put it on the membrane line at the top".
Re-generate. After 3 attempts, change tactic: simplify the blueprint
(fewer entities) and start fresh.

### 5. Save the final version

If exploring with `asset_filename`: the user can promote one to a
figure later via `add_figure(local_path=...)`.

If `figure_number` was set: the figure doc + storage blob are
already in place. Update the caption with the polished version:

```
mcp__co_scientist__update_figure(
  slug, figure_number,
  caption="<polished caption>",
  legend="<full legend for the manuscript>"
)
```

The dashboard's Paper page shows it under Figures with a
download/preview button.

## Anti-patterns

- **"Make a heatmap of gene expression"** → wrong skill. Use
  `/analysis-run` with matplotlib/seaborn; the painter LLM hallucinates
  cell colors and labels.
- **Skipping the blueprint** → painter improvises; you spend more
  iterations correcting than blueprinting would have cost.
- **Inlining precise numbers / gene names you care about** → painter
  mis-spells; use numbered labels + a caption legend.
- **Edit chain >3** → quality degrades. Restart with a tighter prompt.

## Aspect ratios + sizes

Defaults that work:
- `1:1` for single-cell schematics, isolated components
- `16:9` for multi-stage pathways, workflows, comparisons (most common)
- `4:3` for tree / hierarchy figures

Larger sizes can be requested but the Cloud Function caps at the
model's native sizes (1024x1024 / 1536x1024 / 1024x1536).
