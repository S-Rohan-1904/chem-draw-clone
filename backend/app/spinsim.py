"""1H spectra simulated from the full spin Hamiltonian, at several spectrometer frequencies.

First-order multiplets (n+1 rule) assume coupled protons are far apart compared
with their coupling. At low field they are not, and the spectrum shows roofing,
extra lines and AB quartets. Here every hydrogen is a spin-1/2 with its chemical
shift and its couplings to the others (app.couplings), split into clusters of
mutually coupled spins; each cluster's Hamiltonian

    H = sum_i nu_i Iz_i + sum_{i<j} J_ij (Iz_i Iz_j + (I+_i I-_j + I-_i I+_j) / 2)

is diagonalised exactly, block by block of total Fz, and the allowed transitions
(F- between neighbouring blocks) give line positions and intensities. A cluster
of more than MAX_SPINS spins (2^N states) is drawn first order instead.
Exchangeable O-H / N-H protons are broad singlets.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

FIELDS = (60, 100, 300, 400, 600)  # MHz
MAX_SPINS = 10
MIN_INTENSITY = 2e-3


def _clusters(n: int, j: np.ndarray, min_j: float) -> list[list[int]]:
    seen, out = set(), []
    for start in range(n):
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            i = stack.pop()
            group.append(i)
            for k in range(n):
                if k not in seen and abs(j[i, k]) >= min_j:
                    seen.add(k)
                    stack.append(k)
        out.append(sorted(group))
    return out


def _exact(nu: np.ndarray, j: np.ndarray) -> list[tuple[float, float]]:
    """(frequency in Hz, intensity) of the allowed transitions of one cluster."""
    n = len(nu)
    blocks: dict[int, list[int]] = defaultdict(list)  # number of alpha spins -> basis states (bit set = alpha)
    for s in range(1 << n):
        blocks[bin(s).count("1")].append(s)
    m = lambda s, i: 0.5 if s >> i & 1 else -0.5  # noqa: E731
    eig: dict[int, tuple[np.ndarray, np.ndarray, dict[int, int]]] = {}
    for k, states in blocks.items():
        index = {s: a for a, s in enumerate(states)}
        h = np.zeros((len(states), len(states)))
        for a, s in enumerate(states):
            h[a, a] = sum(nu[i] * m(s, i) for i in range(n)) + sum(j[p, q] * m(s, p) * m(s, q) for p, q in combinations(range(n), 2))
            for p, q in combinations(range(n), 2):
                if j[p, q] and (s >> p & 1) != (s >> q & 1):
                    flipped = s ^ (1 << p) ^ (1 << q)
                    h[a, index[flipped]] += j[p, q] / 2
        energies, vectors = np.linalg.eigh(h)
        eig[k] = (energies, vectors, index)
    lines = []
    for k in range(1, n + 1):
        e_hi, v_hi, idx_hi = eig[k]
        e_lo, v_lo, idx_lo = eig[k - 1]
        lower = np.zeros((len(idx_lo), len(idx_hi)))  # F- = sum_i I-_i, taking an alpha spin to beta
        for s, a in idx_hi.items():
            for i in range(n):
                if s >> i & 1:
                    lower[idx_lo[s ^ (1 << i)], a] = 1.0
        amp = v_lo.T @ lower @ v_hi
        inten = amp ** 2 / (1 << (n - 1))  # the transitions of n spins sum to n: each proton counts once
        for b, a in zip(*np.nonzero(inten > MIN_INTENSITY / 10)):
            lines.append((float(e_hi[a] - e_lo[b]), float(inten[b, a])))
    return lines


def _first_order(nu: float, couplings: list[dict]) -> list[tuple[float, float]]:
    lines = [(nu, 1.0)]
    for c in couplings:
        for _ in range(c["n"]):
            lines = [(f + s * c["J"] / 2, w / 2) for f, w in lines for s in (-1, 1)]
    return lines


def _merge(lines: list[tuple[float, float]], field: float) -> list[list[float]]:
    """Lines within 0.05 Hz merged (degenerate transitions come out of the solver separately), in ppm."""
    acc: dict[int, float] = defaultdict(float)
    for f, w in lines:
        acc[round(f * 20)] += w
    return [[round(k / 20 / field, 6), round(w, 4)] for k, w in sorted(acc.items()) if w > MIN_INTENSITY]


def simulate(h_shift: dict[int, float], j: dict[tuple[int, int], float], broad: list[tuple[float, int]],
             first_order: dict[int, list[dict]], min_j: float = 0.8) -> dict:
    """h_shift: {hydrogen atom: ppm} for the non-exchangeable protons; j: {(h1, h2): Hz};
    broad: [(ppm, count)] exchangeable protons; first_order: {hydrogen: its coupling list}, used
    for clusters too big to solve. Returns {fields, lines: {MHz: [[ppm, intensity]]}, broad, exact}."""
    hs = sorted(h_shift)
    pos = {h: i for i, h in enumerate(hs)}
    jm = np.zeros((len(hs), len(hs)))
    for (a, b), value in j.items():
        if a in pos and b in pos:
            jm[pos[a], pos[b]] = jm[pos[b], pos[a]] = value
    clusters = _clusters(len(hs), jm, min_j)
    exact = all(len(c) <= MAX_SPINS for c in clusters)
    out = {}
    for field in FIELDS:
        lines: list[tuple[float, float]] = []
        for c in clusters:
            nu = np.array([h_shift[hs[i]] * field for i in c])
            if len(c) <= MAX_SPINS:
                lines += _exact(nu, jm[np.ix_(c, c)])
            else:
                for i, f in zip(c, nu):
                    lines += _first_order(float(f), first_order.get(hs[i], []))
        out[str(field)] = _merge(lines, field)
    return {"fields": list(FIELDS), "lines": out, "broad": [[round(p, 3), n] for p, n in broad], "exact": exact,
            "largest": max((len(c) for c in clusters), default=0)}
