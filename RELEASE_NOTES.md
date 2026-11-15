# Tank Scan Lab v1.2.0

Resonance and tank scan are now one measurement mode, **Resonance / tank**. Tick what the canvas contains and, optionally, **Module loss split**; one small-signal run reports f0, Rp(LC), Rp(LC+loading), terminal gm/gds, G_neg, startup margin, loop gain, Q and per-module loss shares for every code. Old Resonance and Tank scan pages open in the new mode.

New in this release:

- **Optional port 2** (pin roles P2 / N2) for Z21 and transformer-coupled cores with their gates on port 2; their loop gain is gm·Z21.
- **Plot manager**: add plot tabs, each with its own quantity and x axis; click a curve to select its row; hover for values.
- **Refine sweep at each f0** for bracket-level accuracy, even across 256 codes.
- **C step / INL / DNL** in Capacitance mode.
- **Dark / Light** theme and anti-aliased plots (Pillow optional; plain Tk canvas otherwise, forced with `CAPLAB_ANTIALIAS=0`).
- A synthetic 8-bit thermometer example (`examples/thermo8_cq.json`; `python -m caplab.thermo_example --tank` writes the 256-code tank workbook).

Try it offline: `python3 app.py --tank --project examples/ideal_tank.json` or `python3 app.py --tank --project examples/thermo8_cq.json`. Definitions and validation: [docs/TANK_SCAN.md](docs/TANK_SCAN.md), [docs/VALIDATION.md](docs/VALIDATION.md).

The analysis is a small-signal startup analysis; steady-state frequency and swing need HB / transient simulation. Running new scans requires your own Cadence/Spectre environment, models and licenses. Existing workbooks open as before.
