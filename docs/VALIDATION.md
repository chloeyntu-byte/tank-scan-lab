# Release validation

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
bash -n launch.sh cadence-child.sh caplab/z11/z11_launch
bash launch.sh --help
```

For Tk coverage, set `DISPLAY` to the private display assigned to your session. Do not use another user's desktop. Full Z11 window coverage also requires the optional NumPy/Matplotlib environment. This release used a private 1600×1000 Xvnc display and checked 1280×800 layouts.

The original 128 tests passed before packaging changes. The release suite has 140 tests: under Python 3.6, 139 pass and one optional Z11 GUI test skips because Matplotlib is not installed in that interpreter; under the modern Z11 environment, all 140 pass. The added coverage includes closed-form capacitance/Q and LC resonance checks, inline-workbook integrity, Touchstone metadata, visible Tk table rows, replay cancellation/restart, launch argument checks using a fake native executable, and Z11 nodal results versus an independent closed-form solution.

A read-only comparison of the original and bundled Z11 on a generic 101-frequency example produced identical complex results, parameter labels, optimization score and serialized schematic plan. Native EDA tools were not run. The full source-tree pre/post manifest comparison found no content, size or modification-time changes in either source tree.

The theme module is copied verbatim. Product-side font fallback handles Tk builds that return family names in lower case; the kit itself is unchanged. C/Q Canvas plots use the kit palette; Z11 uses the shared Matplotlib theme.

## v1.1.0 tank scan

`tests/test_tank_scan.py` adds analytic checks of the tank-scan analysis (f0, negative conductance, core loading, Rp(LC), Rp(LC+loading), margin, gm·Rp, LC-only f0, loss shares; a frequency-dependent gm for the cancellation definition), role/mode selection, review edge cases (reference point outside the resonance search, f0 on the first sweep sample, exact zero crossings), the low reference frequency and the bundled `examples/ideal_tank.json`. The full suite has 151 tests; under Python 3.6 with a private display, 150 pass and one optional Z11 GUI test skips. `python3 -m caplab.tank_example` regenerates the tank example byte-for-byte numerically (`scripts/compare_numeric_tree.py`). Native tank scans were cross-checked during development (see docs/TANK_SCAN.md) and are not part of this repository.

## v1.2.0 resonance / tank, port 2, themes, linearity

New tests: `tests/test_tank_port2.py` (analytic transformer-coupled core with its gates on port 2 against the gm-cancelled four-port algebra; one-port results with port 2 open; a packaged core reproducing gm·Z11), `tests/test_linearity.py` (C step / INL / DNL on ideal and bowed arrays, one curve per frequency), refinement-grid and refined-bracket cases in `tests/test_tank_scan.py`, and `tests/test_tank_ui_smoke.py` (Tank Scan Lab window on the bundled tank example: merged mode, legacy view names, plot manager, Dark/Light switch with live recolouring; Capacitance C step and INL/DNL views).

The suite has 162 tests:

| Interpreter | Pillow | Result |
|---|---|---|
| Python 3.6.8 / Tk 8.5 (system) | yes | 161 pass, 1 optional Z11 GUI test skips (no Matplotlib) |
| Python 3.6.8 / Tk 8.5, `CAPLAB_ANTIALIAS=0` | forced off | 161 pass, 1 skip |
| Python 3.13 / Tk 8.6, no Pillow, no NumPy | no | 159 pass, 1 skip; `test_z11_numeric` needs NumPy (optional Z11 dependency) |
| Python 3.11 / Tk 8.6 with NumPy, Matplotlib, Pillow | yes | all 162 pass |

All Tk runs used a private 1600×1000 TigerVNC Xvnc display. `python -m caplab.thermo_example` produces byte-identical `examples/thermo8_cq.json` under Python 3.6 and 3.13 (fixed-seed generator). The 8-bit tank workbook (`--tank`, about 45 MB) was generated and opened in the GUI (256 codes analyzed, no callback errors); it is not committed.

Native cross-checks during development used the developer's own device models (not part of this repository). Each compares this tool's analysis of one native SP run with an independent netlist-level gm-cancellation simulation (AC-only controlled sources, pure floating 1 A drive), code 0:

| Case | Quantity | This tool | Independent run |
|---|---|---|---|
| Inductor + cap array + cross-coupled core, 2 % sweep bracket | G_loss | 8.1896 mS | 8.1882 mS |
| | Rp(LC+loading) | 122.11 Ω | 122.13 Ω |
| | G_neg | 52.986 mS | 52.986 mS |
| | Startup margin | 6.470 | 6.471 |
| Same circuit, wide log sweep + **Refine sweep at each f0** (bracket 0.10 %) | Rp(LC+loading) | 122.12 Ω | 122.13 Ω |
| | Startup margin | 6.4708 | 6.471 |
| Transformer tank (k = 0.7), core gates on port 2, port 2 open | G_loss | 6.1959 mS | 6.1959 mS |
| | G_neg | 60.738 mS | 60.738 mS |
| | Startup margin | 9.80297 | 9.80293 |
| | Re Z21 | 180.681 Ω | 180.682 Ω |
| | Loop gain gm·Z21 | 18.407 | 18.407 |

The same canvas with the gates tied inside the core cell and port 2 on the secondary reproduced the one-port result (Rp 122.12 Ω, margin 6.47, gm·Z11). Terminal gm/gds read by the tool were 0.923× the transistor's intrinsic operating-point values, the expected series-resistance degeneration of the RF device model; the terminal value is the one that loads the tank.

Screenshots:

- `screenshots/01-empty.png`: empty workbench and Load example.
- `screenshots/02-example.png`: synthetic circuit canvas.
- `screenshots/03-running.png`: live synthetic replay and progress.
- `screenshots/04-cq-results.png`: per-code C/Q and decomposition.
- `screenshots/05-z11-results.png`: saved LC Z11 magnitude/phase.
- `screenshots/06-compact.png`: 1280×800 controls and footer.
- `screenshots/07-z11-studio.png`: bundled standalone Z11 example.
- `screenshots/08-tank-scan.png`: Resonance / tank results, KPI tiles, |Z11| curves with one highlighted code and the hover readout (dark).
- `screenshots/09-tank-canvas.png`: synthetic tank circuit canvas with setup panels.
- `screenshots/10-tank-roles.png`: Canvas contains, roles and options, startup margin per code.
- `screenshots/11-tank-plot-manager.png`: plot manager on the 8-bit tank (f0 per code; margin, gain, |Z11|, |T| and loss-share tabs).
- `screenshots/12-tank-loss-share.png`: loss share by module with the results and loss tables.
- `screenshots/13-cq-8bit.png`: 8-bit thermometer array, C/Q over 256 codes.
- `screenshots/14-inl-dnl-8bit.png`: 8-bit thermometer array, DNL and INL (endpoint fit).
- `screenshots/15-tank-light.png`: Light theme.
- `screenshots/16-tank-8bit.png`: |Z11| of all 256 codes of the 8-bit tank.

Screenshots 08–16 were taken from this repository's application on a TigerVNC Xvnc display with the synthetic examples only.

The core plot area occupies more than 60% of the main horizontal pane at 1600×1000. The footer and measurement controls remain mapped inside a 1280×800 window. Large settings lists retain their scrollbars. Empty, running and completed states were inspected in the real GUI.

Native library/PDK compatibility, licensed simulation and real Maestro menu callbacks remain user-environment validation items. The Z11 GUI combination of Python 3.6 / Tk 8.5 / compatible Matplotlib was not available here. Core UI tests passed on Python 3.6.8 / Tk 8.5.13; the full GUI suite passed on Python 3.11.15 / Tk 8.6.13. Z11 numerical paths also passed on Python 3.6. No package or system component was installed.
