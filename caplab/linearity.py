"""Code-to-capacitance linearity of a switched-capacitor array (derived from saved results; no simulation).

For each curve (one observation frequency and fixed other registers) the points are
ordered by the code axis:

* C step(k) = C(k) - C(k_prev): the capacitance change from the previous code
  (fF in the plot; it is negative when C falls with code).
* LSB = (C_last - C_first) / (code_last - code_first): endpoint-fit LSB per code unit.
* DNL(k) = C step(k) / ((k - k_prev) * LSB) - 1   (LSB)
* INL(k) = (C(k) - C_first - (k - k_first) * LSB) / LSB   (LSB, endpoint fit)
"""
import math

from .plotting import curve_groups


def linearity_rows(rows, axis, names, mode, filters=None, include_frequency=True):
    """Copies of rows with C_step_F, DNL_LSB and INL_LSB added (None where undefined)."""
    out = []
    for label, series in curve_groups(rows, axis, names, mode, filters, include_frequency):
        pts = [r for r in series if isinstance(r.get(axis), (int, float)) and r.get('C_F') is not None
               and math.isfinite(r['C_F'])]
        pts.sort(key=lambda r: r[axis])
        lsb = None
        if len(pts) >= 2 and pts[-1][axis] != pts[0][axis]:
            lsb = (pts[-1]['C_F'] - pts[0]['C_F']) / (pts[-1][axis] - pts[0][axis])
            if not lsb:
                lsb = None
        prev = None
        for r in pts:
            item = dict(r, C_step_F=None, DNL_LSB=None, INL_LSB=None)
            if prev is not None:
                item['C_step_F'] = r['C_F'] - prev['C_F']
                if lsb:
                    item['DNL_LSB'] = item['C_step_F'] / ((r[axis] - prev[axis]) * lsb) - 1
            if lsb:
                item['INL_LSB'] = (r['C_F'] - pts[0]['C_F'] - (r[axis] - pts[0][axis]) * lsb) / lsb
            out.append(item)
            prev = r
    return out


def summary(rows):
    """Worst |DNL| / |INL| and the LSB-normalized step range over the given linearity rows."""
    dnl = [abs(r['DNL_LSB']) for r in rows if r.get('DNL_LSB') is not None]
    inl = [abs(r['INL_LSB']) for r in rows if r.get('INL_LSB') is not None]
    return {'max_abs_DNL_LSB': max(dnl) if dnl else None, 'max_abs_INL_LSB': max(inl) if inl else None}
