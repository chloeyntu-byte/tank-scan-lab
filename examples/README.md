# Synthetic offline examples

Generate from the repository root:

```bash
python3 -m caplab.demo
python3 app.py --project examples/ideal_array.json
```

`ideal_array.json` is a portable v3 workbook with inline spectra and hashed C/Q result tables. Its workspace is empty. No PDK, native device master, measured data, tool history or private path is included.

- **Ideal capacitor array:** eight codes `BANK=0..7`. Coupling capacitance is `Cbank = 0.5 pF + BANK × 0.125 pF`; each ground shunt is `0.1 pF`. The two shunts form a series ground-path equivalent of `0.05 pF`. Total differential capacitance is therefore `0.55 pF + BANK × 0.125 pF`.
- Each capacitor uses a fixed parallel conductance `G = 2π × 1 GHz × C / 80`. Its Q equals `80 × f / 1 GHz`. This is an analytic pedagogical model, not a transistor-switch model.
- **Parallel LC resonance:** adds a lossless 2 nH branch across P/N. The exact resonance is `1 / (2π sqrt(2 nH × Ctotal))`. The UI estimates crossings from saved complex Y samples, so its result need not equal this closed form exactly. The canvas inductor is illustrative; no native simulation is used.
- Each code has 101 linearly spaced samples from 0.5 to 8 GHz. C/Q observations are at 1, 2 and 3 GHz. `caplab.spectrum.resample` and the existing decomposition/resonance routines process these generated samples without special numerical shortcuts.
- Native module loss currents are intentionally absent. Their loss shares remain **unavailable**, not zero.

`ideal_array.s2p` contains the code-0 capacitor pi network (101 samples, RI format, 50-ohm reference). It uses `S = (I - 50Y) (I + 50Y)^-1`. It is independent of any process or extracted layout. Importing this file into a native RF circuit still needs the user's Cadence symbol environment; the offline workbook already contains the same analytic model's results and needs no import.

**Load example** opens the bundled workbook. **Run SP / Measure C + Q** on its pages runs a cancellable synthetic replay. The model, code range and grid are fixed; circuit/register edits are not passed to a solver. Observation frequency edits can reuse the saved spectrum inside its range. Native measurements use a new workbook configured for the user's environment.

## Tank example

`ideal_tank.json` (`python3 -m caplab.tank_example`): analytic centre-tapped inductor (0.5 nH + 1.2 Ω per half), switched C (0.25 pF × (2 + code), 0.4 mS) and a cross-coupled pair (gm 20 mS, gds 1.5 mS, Cg 0.15 pF per side), codes 0–3, 2–8 GHz plus the 10 MHz gm reference point. The records follow the native module-current format, so the full Resonance / tank analysis (module split, margin, loop gain, loss shares) runs on them. Open it with `python3 app.py --tank --project examples/ideal_tank.json`.

## 8-bit thermometer examples

`python3 -m caplab.thermo_example [--tank] [OUT_DIR]` builds a synthetic 8-bit thermometer-coded array (codes 0–255): 255 unit cells switched on in order, each a series Cu (8.2 fF nominal, 1.5 % random spread and a 1 % linear gradient along the array, fixed seed) and a 900 Ω switch; an off cell leaves 15 % of Cu; fixed 0.6 pF and small ground shunts.

- `thermo8_cq.json` (committed, about 4.8 MB): the array alone, 1–6 GHz, observed at 2/3/4 GHz. Use Capacitance mode and **Show → C / Q, C step, INL / DNL**.
- `thermo8_tank.json` (about 45 MB, **not committed**; generate with `--tank`): the same array in an LC tank (0.5 nH + 1 Ω per half) with a cross-coupled gm (30 mS, gds 1.5 mS, Cg 0.15 pF), 2.85–5.25 GHz, 111 points per code, with module currents for every code.

The generator is deterministic; `thermo8_cq.json` is identical on Python 3.6 and 3.13.
