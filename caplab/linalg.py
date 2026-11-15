"""Small dense complex linear algebra (pure Python; no numpy in the conda runtime)."""


def solve(a, b, rtol=1e-12):
    """Solve A x = b (A n x n nested lists, b a vector or an n x m nested list).

    Gaussian elimination with complete pivoting.  A rank-deficient A is allowed
    when b lies in its range (e.g. a floating network): null directions are set to
    zero and the residual is checked.  Returns None when there is no solution.
    """
    n = len(a)
    vector = not isinstance(b[0], (list, tuple))
    cols = [[x] for x in b] if vector else [list(r) for r in b]
    m = len(cols[0])
    aug = [list(map(complex, a[i])) + list(map(complex, cols[i])) for i in range(n)]
    scale = max((abs(x) for row in a for x in row), default=0.0) or 1.0
    order = list(range(n))  # column permutation
    rank = 0
    for k in range(n):
        best, bi, bj = 0.0, k, k
        for i in range(k, n):
            for j in range(k, n):
                v = abs(aug[i][j])
                if v > best:
                    best, bi, bj = v, i, j
        if best <= rtol * scale:
            break
        aug[k], aug[bi] = aug[bi], aug[k]
        if bj != k:
            for row in aug:
                row[k], row[bj] = row[bj], row[k]
            order[k], order[bj] = order[bj], order[k]
        piv = aug[k][k]
        for i in range(k + 1, n):
            f = aug[i][k] / piv
            if f:
                for j in range(k, n + m):
                    aug[i][j] -= f * aug[k][j]
        rank += 1
    x = [[0j] * m for _ in range(n)]
    for k in range(rank - 1, -1, -1):
        for c in range(m):
            s = aug[k][n + c] - sum(aug[k][j] * x[j][c] for j in range(k + 1, rank))
            x[k][c] = s / aug[k][k]
    out = [None] * n
    for k in range(n):
        out[order[k]] = x[k]
    # residual check (consistency of a rank-deficient system)
    for i in range(n):
        for c in range(m):
            r = sum(complex(a[i][j]) * out[j][c] for j in range(n)) - complex(cols[i][c])
            ref = max(abs(complex(cols[i][c])), max(abs(complex(a[i][j]) * out[j][c]) for j in range(n)), 1e-300)
            if abs(r) > 1e-7 * ref and abs(r) > 1e-9 * scale * max(abs(out[j][c]) for j in range(n)):
                return None
    return [row[0] for row in out] if vector else out


def inverse(a):
    n = len(a)
    return solve(a, [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)])


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def matvec(a, x):
    return [sum(a[i][k] * x[k] for k in range(len(x))) for i in range(len(a))]


def kron_reduce(y, keep):
    """Admittance seen at nodes `keep` with the other nodes left open (no injection)."""
    n = len(y)
    drop = [i for i in range(n) if i not in keep]
    if not drop:
        return [[y[i][j] for j in keep] for i in keep]
    ybb = [[y[i][j] for j in drop] for i in drop]
    yba = [[y[i][j] for j in keep] for i in drop]
    x = solve(ybb, yba)
    if x is None:
        return None
    return [[y[i][j] - sum(y[i][d] * x[k][jj] for k, d in enumerate(drop))
             for jj, j in enumerate(keep)] for i in keep]
