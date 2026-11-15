"""Optional second measurement port (P2/N2).

Port 1 is always the differential P/N port (the tank / drain side).  Port 2 is an
optional differential port on two other nets (e.g. the gate side of a transformer
core, or an output).  With port 2 the SP analysis has four ground-referenced
ports in the order P, N, P2, N2 and the full 4x4 Y of the DUT is saved as X keys.
The usual Y11..Y22 keys then hold port 1 with port 2 left OPEN (Kron reduction),
so every one-port result (C/Q, resonance, Z11, tank scan) keeps its meaning.
"""
import math

from .linalg import kron_reduce, solve

NETS = ('CAL_P', 'CAL_N', 'CAL_P2', 'CAL_N2')


def x_key(i, j, part):
    return 'X{}{}_{}_S'.format(i + 1, j + 1, part)


def has_port2(row):
    return x_key(0, 0, 'G') in row


def full_matrix(row):
    return [[complex(row[x_key(i, j, 'G')], row[x_key(i, j, 'B')]) for j in range(4)] for i in range(4)]


def row_fields(matrix):
    """Spectrum fields for one sample: X keys and the port-1 Y keys with port 2 open."""
    out = {}
    for i in range(4):
        for j in range(4):
            v = complex(matrix[i][j])
            out[x_key(i, j, 'G')], out[x_key(i, j, 'B')] = v.real, v.imag
    red = kron_reduce(matrix, [0, 1])
    if red is None:
        raise ValueError('Port 2 nets have no admittance to the rest of the circuit (open port 2 is undefined).')
    for (i, j), ij in zip(((0, 0), (0, 1), (1, 0), (1, 1)), ('11', '12', '21', '22')):
        out['Y{}_G_S'.format(ij)], out['Y{}_B_S'.format(ij)] = red[i][j].real, red[i][j].imag
    return out


def drive(matrix, port=1):
    """Node voltages for a floating 1 A differential drive at port 1 (or 2), other port open."""
    t = [1, -1, 0, 0] if port == 1 else [0, 0, 1, -1]
    return solve(matrix, t)


def z_pair(matrix):
    """(Z11, Z21) differential: V(P-N) and V(P2-N2) per 1 A into P / out of N, port 2 open."""
    v = drive(matrix)
    if v is None:
        return None
    return v[0] - v[1], v[2] - v[3]


def z21_curve(samples):
    """(f, Z11, Z21) complex for the samples of one point that carry the port-2 matrix."""
    out = []
    for s in sorted(samples, key=lambda r: r['frequency_Hz']):
        if not has_port2(s):
            continue
        z = z_pair(full_matrix(s))
        if z is not None and all(math.isfinite(abs(v)) for v in z):
            out.append((float(s['frequency_Hz']), z[0], z[1]))
    return out
