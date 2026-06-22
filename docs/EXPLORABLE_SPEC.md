# SPEC: justitia explorable explanation

An interactive, in-browser explanation of the finding: blind governance holds
only as **consequence-gated anti-concentration** — one coupled mechanism, not two
independent levers. The reader toggles the scales and the sword, picks a world,
and *watches* the ecosystem hold or collapse.

## Ethos (non-negotiable)

- **Replay real runs, do not re-simulate in the browser.** The page animates
  per-step trajectories *recorded from the validated Python model*. No JS
  re-implementation of the dynamics — that would reintroduce exactly the
  faithfulness risk this project guards against.
- **Show the distribution, not a lucky seed.** Line charts show a mean band over
  many seeds; the zone animation replays one clearly-labelled representative seed.
- **Stay honest.** It is a simulation / intuition pump, labelled as such, linking
  to `results/` and `docs/LIMITATIONS.md`. Never imply it proves anything about
  real institutions or real AI.

## Architecture

```
model/  --(emit)-->  web/data/*.json  --(static)-->  web/index.html + app.js + style.css
```

- A Python emitter records per-step metrics for a fixed set of showcase
  configurations and writes JSON into `web/data/`.
- The web app is **vanilla HTML/CSS/JS, no build step, no dependencies** (matches
  the repo's pure-stdlib, hand-rolled-SVG ethos). Hostable as-is on GitHub Pages.
- Charts/visuals use inline SVG or Canvas drawn by hand (no chart library).

## Model instrumentation (record-only; must not change dynamics)

Add an optional per-step recorder to the substrate run loop:

- A flag (e.g. `record_trajectory=True`) appends a per-step snapshot to a list
  and changes nothing else. Dynamics, RNG draws, and final summary metrics must be
  **identical** with and without recording.
- **Acceptance gate:** for several seeds/configs, assert every final summary
  metric is byte-identical with `record_trajectory` on vs off. If not, the hook is
  perturbing the model and must be fixed before proceeding.

Per-step snapshot fields (all already computed by the model; cheap to record):

```
step, welfare, minimum_zone_welfare, capture_index, collapse (bool),
exploitative_strategy_mass, cooperative_strategy_mass, resource_hhi,
containment_events_this_step,            # the sword firing, per step
zone_mass[9], zone_welfare[9]            # for the zone visual
```

## Emitter (`model/emit_explorable.py` or an `atlas.py --emit-web` flag)

For each showcase configuration, run `N_SEEDS` seeds (recommend 24) and write
`web/data/<config_id>.json`:

```json
{
  "config_id": "W6__scales_on__sword_on",
  "world": "W6_mutation_corridor",
  "scales": true, "sword": true, "gated": true,
  "label": "consequence-gated anti-concentration",
  "verdict": "holds",                 // holds | collapses (from permanence band)
  "steps": 100, "n_seeds": 24, "rep_seed": 16000,
  "band": {                            // per-step aggregate over seeds
    "welfare":              [{ "mean": .., "lo": .., "hi": .. }, ...],
    "minimum_zone_welfare": [ ... ],
    "capture_index":        [ ... ],
    "exploitative_strategy_mass": [ ... ]
  },
  "rep": {                             // one representative seed, for the animation
    "zone_mass":    [[9 floats] x 100],
    "zone_welfare": [[9 floats] x 100],
    "containment_events_this_step": [100 ints]
  }
}
```

Also write `web/data/index.json` listing the available configs and the narrative
ordering. Keep each file small (tens of KB); 9 zones × ~100 steps is fine.

## Showcase configurations

Map the levers to existing model families/variants — **no new mechanisms**:

| scales | sword | maps to | expected |
|---|---|---|---|
| off | off | no governance (run with control/no-control) | collapses |
| on  | off | family A (`anti_hhi_allocator`) | collapses |
| off | on  | family B (`delayed_harm_throttle`) | collapses |
| on  | on  | family C (`anti_concentration_plus_delayed_harm_throttle`) | holds |

Then the **twist** (BE), as a second section:

| variant | maps to | expected |
|---|---|---|
| scales that never wait for harm | `C_dyn_no_consequence` | collapses (never fires) |
| consequence-gated scales | `C_dyn_only` | holds |
| + redundant always-on cap | `C_full` | holds (no better) |

Worlds to emit: `W6_mutation_corridor` (clean robust), `W4_scavenger_catastrophe`,
`W3_catastrophe_ambiguity`, plus failure controls `W2_pure_capture` and
`W5_monoculture_shock`. For the boundary slider, emit the C kernel across
`adversarial_pressure ∈ {0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8}` in W6/W3/W4.

## Narrative (the page, top to bottom)

1. **The setup.** Blindfold = blind to internals; hidden exploiters; the two
   affordances (scales, sword). Short prose + the Justitia image idea.
2. **The playground (2×2).** Two toggles (scales / sword) + a world selector.
   On change, load the matching trajectory and animate: the 9-zone visual evolving
   over 100 steps, plus the welfare / minimum-zone-welfare / capture line bands. A
   verdict chip reads **holds** or **collapses**. The reader discovers, by hand,
   that only scales+sword together holds.
3. **The twist — they're not two levers.** Reveal `C_dyn_no_consequence`: scales
   that never wait for harm. Show `containment_events_this_step` flat at zero and
   the world collapsing, beside `C_dyn_only` where the sword's firing drives the
   scales and it holds. Land the line: *consequence-gated anti-concentration.*
   Note the always-on cap is redundant (`C_full` is no better).
4. **The boundary.** An `adversarial_pressure` slider; watch the robust kernel
   hold up to ~1.2× then break. Then switch to W2 / W5 and show that *no*
   configuration holds — honest failure.
5. **Close.** Tie to *Machines of Loving Grace*: `minimum_zone_welfare` is
   "paradise for the powerless," and here it is a number you can watch rise or
   fall. Links to the repo, `results/`, and `LIMITATIONS.md`.

## Visualization components

- **Zone visual:** 9 zones as a ring or 3×3 grid (Canvas/SVG). Per zone, area or
  colour encodes mass; a second channel (border / hue) encodes zone welfare. A
  pulse when `containment_events_this_step > 0` (the sword acting on that zone, if
  per-zone available; otherwise a global pulse). A play/scrub control over steps.
- **Line bands:** welfare, minimum-zone-welfare, capture — mean line with a
  shaded CI band, current step marked.
- **Verdict chip:** holds / collapses, coloured.
- **Controls:** two lever toggles, world selector, step play/scrub, adversarial
  slider (section 4).

## Acceptance

- `record_trajectory` determinism gate passes (recording changes no metric).
- `web/` opens with `python -m http.server` and runs with no network/deps.
- Toggling scales/sword/world swaps trajectories and the animation/verdict update
  to match the recorded data (spot-check a couple against `results/`).
- The twist section visibly shows `containment_events = 0` for
  `C_dyn_no_consequence` and a collapsing welfare/min-welfare trace.
- A short note + links make the simulation framing and limitations explicit.

## Out of scope (v1)

- No live in-browser re-simulation, no backend, no framework/build tooling.
- A faithful JS port of the substrate may be a later, clearly-separate experiment
  — only if validated to reproduce the recorded trajectories within tolerance.
