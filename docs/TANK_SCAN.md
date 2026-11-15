# Resonance / tank mode

Start with `bash tank-scan-lab.sh` (or `python3 app.py --tank`). The same mode is available in the regular workbench as **Measurement results → Measurement mode → Resonance / tank**. It replaces the former separate *Resonance* and *Tank scan* modes; saved pages in either old mode open in it.

On the results tab the library and settings panels hide automatically (**Show setup panels** keeps them visible). Roles and the gm reference frequency are under **Roles & options**. KPI tiles summarize the selected point. Plots are on the left, the results table and the loss table on the right; all dividers can be dragged. The first row fills the tiles when results arrive, but curves are highlighted only after you pick a row or a curve.

## Workflow

1. Place the tank on the canvas: an N-port inductor (**RF devices / SNP**) or ideal inductors, the capacitor-array cell driven by a register, and optionally a cross-coupled gm cell (drains on P/N). Bias it as in normal operation, for example VDD through the inductor centre tap.
2. Under **Canvas contains**, tick *Inductor / N-port*, *Cap array* and/or *gm core*. With *gm core* ticked the active analysis runs. Without it the passive analysis runs: with **Module loss split** ticked (default) native module currents are captured for Rp(LC) and loss shares; unticked it is a fast resonance-only run (SP only: f0, Z11, Rp = Re Z at f0). A gm core always captures module currents.
3. Check the roles under **Roles & options**. They are auto-detected (N-port or inductor → inductor, register-driven cell → cap array, any other cell → gm core) and can be changed. Changing roles or ticks re-analyzes saved data only; it never reruns a simulation.
4. **Run** (tank toolbar) or **Run resonance / tank scan** (settings panel). With a gm core, a low reference frequency (**gm reference freq.**, default 10 MHz) is added below the sweep.
5. For bracket-level accuracy click **Refine sweep at each f0** and run again. The base sweep is kept and points are added within ±0.6 % of every code's own f0 with a 0.1 % relative step; overlapping windows of neighbouring codes are merged into one band, so 256 codes cost a few hundred extra points rather than 256 clusters. **Clear f0 refinement** (Roles & options) removes them. The status column warns when an f0 bracket is wider than 1 %.

## Optional port 2 (P2 / N2) and transformer-coupled cores

Port 1 is always the differential P/N port: the tank and the core's drains. Port 2 is optional: give two canvas pins the roles **P2** and **N2** (pin role list, or nets named P2 / N2). Typical uses are the gates of a transformer-coupled core (drains on the primary, gates on the secondary) or an output. Net names P2 / N2 are reserved for port 2.

- SP then has four DC-blocked ground ports (P, N, P2, N2). Maestro's own per-frequency C/Q outputs are not created in this mode (the 2×2 corner of the four-port Y would be port 2 shorted); every one-port value comes from the saved four-port matrix. One-port results (C/Q, f0, Z11, Rp, loss shares) are port 1 with **port 2 open**, so they mean the same as without port 2. With the module split (or a gm core), two more native excitations are run at port 2 (four in total).
- The gm core's admittance is identified on whichever of P, N, P2, N2 its pins touch:
  - gates tied to the opposite drains (inside the cell or on the canvas): loop gain **gm·Z11 = gm·Rp**;
  - gates exposed and connected to P2/N2: detected automatically (*gm gates: on port 2*); loop gain **gm·Z21**.
- gm is cancelled the same way in both cases (real cross terms at the low reference frequency), so G_neg, G_loss, Rp(LC+loading) and margin are read at port 1 with port 2 open. Everything the gate side absorbs (secondary winding, gate-side capacitors, gate input loss) is part of G_loss and appears in the loss shares.
- **Loop gain gm·Z21** = gm(f_ref) × Re Z21 of the gm-cancelled tank at f0 (drain current to gate voltage), from the saved four-port Y. With both kinds of core on the canvas each core adds its own path (gm·Re Z11 for gates on P/N, gm·Re Z21 for gates on port 2). A wrong gate polarity gives a negative gain. *V_gate / V_drain* = Re Z21 / Re Z11 (gm off).
- Transformer tanks can have two parallel resonances. With a gm core, f0 is the one with the larger startup margin and the status lists both.

## Plots

**+ Add plot** opens a new tab; each tab has a **Quantity** and an **X axis**, and **Remove plot** closes it. Tabs are saved with the page. Only quantities that the current canvas selection can produce are offered (gm, margin and loop gain need *gm core*; Rp(LC), Q, C_eff and loss shares need the module split; Z21 needs port 2).

| Kind | Quantities | X axis |
|---|---|---|
| One value per point | f0, f0 LC only, Rp(LC), Rp(LC+loading), margin, loop gain gm·Z, gm·Rp, gm, gds, G_neg, core loading, G_loss, Q LC, Q loaded, C_eff, L_eff | register value / scan point, or f0 |
| Curve per point | \|Z11\|, phase, Re, Im of Z11; \|Z21\| and phase (port 2); loop gain \|T\| and phase | frequency (sweep range only; the gm reference point is left out) |
| Per module | Loss share of G_loss at f0 | register value / scan point |

Curves versus frequency get one colour per scan point, with a dot and the code value at each point's f0. Clicking a curve selects that point in the table; selecting a table row highlights its curve (and marks it on the loss-share plot). Hovering a point shows its x / y. **Selected point only** hides the other curves.

Loop gain: `T(f) = G_neg(f) / Y_loss(f)`, with `Y_loss = Y_d + G_neg` the tank admittance with the core's negative conductance removed. At f0 the phase of T is zero and |T| equals the startup margin; the |T| peak can sit slightly off f0 because Re Y_loss varies with frequency, so startup is read at f0.

## Themes and rendering

**Theme** in the top bar switches the whole window, the circuit canvas and every plot between **Dark** (the shared RF-FIELDWORK palette; curves glow in the scope trace colours) and **Light** (grey chassis, white plots). The choice is stored in the workbook appearance.

Plots are drawn with Pillow when it is available: 2× supersampled anti-aliasing and, in Dark, a neon glow. Without Pillow, or on an X server whose Tk photo images are unreliable (for example a RealVNC-based server such as Cadence's cdsXvnc), the plots fall back to plain Tk canvas items with the same layout and interaction. `CAPLAB_ANTIALIAS=0` forces the plain canvas; `CAPLAB_ANTIALIAS=1` forces Pillow rendering. Pillow is optional.

## What is computed (per register point)

Every enabled instance is measured through 0 V probes on all of its terminals. Two independent AC excitations (P/N differential and P-to-ground) are combined into a floating 1 A P-N drive. By Tellegen's theorem the module admittances `Y_k = 2·conj(S_k)/|V_d|²` add up to the port admittance; the **module sum check** reports that residual (about 1e-13 on native runs).

The gm core's own 2×2 admittance on the P/N nets is identified from the excitations: `gm = Re(Y12+Y21)/2` and `gds = Re(Y11+Y22)/2`, per side, at the core terminals. The negative conductance follows the usual gm-cancellation tank scan: the low-frequency terminal gm is cancelled under the actual voltages at f0 (`G_neg = gm/2` for a symmetric pair). Everything else the core absorbs, including the RF roll-off of gm, counts as core loading. The alternative split with the cross terms evaluated at f0 is reported in separate columns; both give the same net Re(Y).

| Quantity | Definition |
|---|---|
| f0 | Im(Z11)=0 of the complete circuit including the core, port 2 open (startup frequency): the first crossing for a passive tank; with a gm core the parallel-resonance crossing with the largest startup margin (all crossings are listed) |
| f0 LC only | Zero of the inductor + array susceptance (estimate, core capacitance removed) |
| Rp(LC) | 1 / (G_inductor + G_array) at f0 |
| Rp(LC+loading) | 1 / G_loss, G_loss = G_LC + other loads + core loading |
| G_neg | Conductance supplied by the core's transconductance (low-frequency gm cancelled at the f0 voltages) |
| Core loading | Everything else the core absorbs at f0: gds, gate-input loss, RF roll-off of gm |
| Startup margin | G_neg / G_loss; > 1 starts (≈ gm·Rp/2 for a symmetric pair) |
| Loop gain gm·Z | gm(f_ref) × Rp(LC+loading) (= gm·Z11) for gates on P/N; gm(f_ref) × Re Z21 (gm off) for gates on port 2 |
| gm·Rp | gm(f_ref) × Rp(LC+loading) |
| gm, gds @f_ref / gm, g_load @f0 | Per side, at the core terminals, from the core's admittance on the nets it touches (P/N, plus P2/N2 with port 2): gates on P/N gm = Re(Y12+Y21)/2; gates on port 2 gm = the P2/N2→P/N transconductance; gds/g_load from the drain self terms |
| Q LC, Q loaded, C_eff, L_eff | From the susceptance slope at resonance, C_eff = ½·dB/dω |

Selecting a row lists each module (or coupled-winding group) with its loss conductance and share of G_loss at f0.

## Validation

- `tests/test_tank_scan.py` checks an analytic network: f0, G_neg = gm/2, core loading = gds/2, both Rp values, margin, gm·Rp, LC-only f0 and loss shares agree to 1e-5. A second network with frequency-dependent gm checks the cancellation definition. The bundled example is analyzed in the same test.
- `tests/test_tank_port2.py` checks an analytic transformer with a gates-on-port-2 core against the gm-cancelled four-port algebra (G_loss, G_neg, margin, Re Z21, gm·Z21), checks that one-port results use port 2 open, and that a packaged core with its gates on the drains reproduces the one-port gm·Z11 result.
- `tests/test_tank_scan.py` also covers the refinement grid (base sweep kept, merged clusters, a refined f0 bracket of about 0.1 %).
- During development the analysis was compared on native SP runs (the developer's own device models, not part of this repository) against an independent netlist-level gm-cancellation simulation (AC-only controlled sources, pure floating 1 A drive, port 2 open). Numbers are listed in [VALIDATION.md](VALIDATION.md).

## Limitations

- Values are small-signal at the DC operating point, i.e. the startup condition. Steady-state frequency, swing and gain compression need large-signal (HB / transient) simulation; self-biased cores whose DC current differs from steady state especially so.
- Values at f0 are linear interpolations between the two bracketing samples; use **Refine sweep at each f0** for bracket-level accuracy.
- An N-port whose data start above DC is extrapolated by the simulator for the DC bias and the low reference point.
