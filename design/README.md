# ichosynth — design system (Claude Design)

Local component library for the ichosynth visual identity, synced to a
**Claude Design** project on claude.ai/design.

Each `.html` here is a self-contained preview **card**: its first line is a
`<!-- @dsCard group="..." -->` marker so the Claude Design pane indexes it.

```
foundations/   colors.html · typography.html   — palette + type tokens
brand/         logo.html · badges.html          — lockup + badge style
diagrams/      *.html                           — the assets/*.svg, inlined as cards
```

## Regenerate

```sh
python design/_build_design.py
```

Rebuilds every card from the design tokens and the current `assets/*.svg`
(diagram SVGs are inlined so the cards render standalone).

## Sync to Claude Design

Pushed with the `DesignSync` tool / `/design-sync` skill (claude.ai login with
design-system scope). The live project is named **ichosynth**. Push is
incremental — one component at a time, never a wholesale replace. After editing a
card here, re-run the build and push only the changed paths.
