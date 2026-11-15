# Changelog

## v1.2.0

- Merge the Resonance and Tank scan measurement modes into **Resonance / tank**; pages saved in either old mode open in it. A **Module loss split** toggle selects the full module-current analysis or a fast resonance-only run.
- Optional **port 2** (pin roles P2 / N2): four-port SP with four native excitations, Z21, transformer-coupled gm cores with their gates on port 2 and loop gain gm·Z21; multi-resonance tanks use the mode with the larger startup margin. New `caplab/linalg.py` and `caplab/twoport.py`.
- **Plot manager** in the tank view: any number of tabs, each with a quantity and an x axis (per-code values, |Z11| / phase / Re / Im and |Z21| vs frequency, loop gain |T|, loss share by module); curves and table rows select each other; hover readout.
- Results layout: plots left, results table and loss table right (draggable); KPI tiles; the first row fills the tiles, only a user pick highlights curves.
- **Refine sweep at each f0**: a 0.1 % step band around every code's f0, overlapping windows merged; **Clear f0 refinement**.
- Capacitance mode **Show → C step / INL / DNL** (endpoint fit, per observation frequency) via `caplab/linearity.py`.
- Rendering: new `caplab/render.py` (Pillow anti-aliasing and neon glow, automatic plain-canvas fallback without Pillow or on RealVNC-based X servers, `CAPLAB_ANTIALIAS=0/1`); rewritten C/Q and frequency plots.
- Tank Scan Lab **Dark / Light** theme switch for the window, canvas and plots. Dark is the shared RF-FIELDWORK palette; Light is derived in the product (`product_theme.py`), the shared kit is unchanged.
- Synthetic 8-bit thermometer example generator `python -m caplab.thermo_example` (`examples/thermo8_cq.json`; the 8-bit tank workbook is generated on demand with `--tank`). The tank example opens in the merged mode; **Load example** in Tank Scan Lab opens it.
- New tests for port 2, linearity, refinement and the tank window; CI also runs the suite with the plain-canvas renderer and regenerates the thermometer example. New screenshots.

## v1.1.0

- Rename the product to Tank Scan Lab; the C/Q workbench, resonance view and Z11 Studio are unchanged.
- Add the Tank scan mode: N-port + capacitor array + cross-coupled gm startup analysis (f0, Rp(LC), Rp(LC+loading), terminal gm/gds, G_neg, startup margin, gm·Rp, Q, per-module loss shares). Canvas-content selection switches between the passive and active analysis.
- Add `tank-scan-lab.sh`, `--tank`, an optional low gm reference frequency, and a synthetic tank example (`examples/ideal_tank.json`, `python -m caplab.tank_example`).
- Tank view: KPI tiles, resizable plot / table / loss areas, collapsible roles and auto-hidden side panels on the results tab.
- Factor the floating-drive reconstruction in `loss_native` into a reusable function (behaviour unchanged).

## v1.0.0

- Prepare a clean MIT-licensed source release with bilingual documentation.
- Apply the RF-FIELDWORK cap theme, shared headers, primary actions, status chips, progress bars and dark plots.
- Bundle Z11 Studio and preserve the original numerical, workbook and native integration contracts.
- Replace site-specific defaults with user environment configuration.
- Add a reproducible synthetic eight-code capacitor/LC workbook and two-port Touchstone example.
- Add offline replay, compatibility, numerical and UI smoke checks.
