# -*- coding: utf-8 -*-
"""Tramas litológicas al estilo FGDC (USGS, FGDC-STD-013-2006, sección 37), dibujadas en milímetros de papel.

Cada trama es una función (R, rng, k) -> (segmentos, puntos) en un cuadrado [-R, R]² de mm, con k = escala.
`trama()` la gira según el buzamiento aparente, la pasa a coordenadas de datos y la recorta a un parche.
"""
import numpy as np
from matplotlib.collections import LineCollection

VACIO = np.zeros((0, 2, 2))


def _rejilla(R, dx, dy, rng, jit=0.0, escalon=True):
    """Puntos en filas escalonadas (columnas x, y, nº de fila), con desorden opcional."""
    P = []
    for i, y in enumerate(np.arange(-R, R + dy, dy)):
        xs = np.arange(-R + (dx / 2 if escalon and i % 2 else 0), R + dx, dx)
        P.append(np.column_stack([xs, np.full(len(xs), y), np.full(len(xs), i)]))
    P = np.vstack(P)
    if jit:
        P[:, 0] += rng.uniform(-jit, jit, len(P)) * dx
        P[:, 1] += rng.uniform(-jit, jit, len(P)) * dy
    return P


def _seg(P, a, b):
    return np.stack([P[:, :2] + np.asarray(a), P[:, :2] + np.asarray(b)], axis=1)


def _v(P, s):
    return np.concatenate([_seg(P, (-s / 2, s / 2), (0, -s / 2)), _seg(P, (0, -s / 2), (s / 2, s / 2))])


def _vi(P, s):
    return np.concatenate([_seg(P, (-s / 2, -s / 2), (0, s / 2)), _seg(P, (0, s / 2), (s / 2, -s / 2))])


def _mas(P, s):
    return np.concatenate([_seg(P, (-s / 2, 0), (s / 2, 0)), _seg(P, (0, -s / 2), (0, s / 2))])


def _x(P, s):
    h = s / 2
    return np.concatenate([_seg(P, (-h, -h), (h, h)), _seg(P, (-h, h), (h, -h))])


def _guion(P, L):
    return _seg(P, (-L / 2, 0), (L / 2, 0))


def _tic(P, L, rng, medio=0.0, abanico=180.0):
    a = np.radians(medio + rng.uniform(-abanico / 2, abanico / 2, len(P)))
    d = np.column_stack([np.cos(a), np.sin(a)]) * L / 2
    return np.stack([P[:, :2] - d, P[:, :2] + d], 1)


def _poligono(P, r, n, rng, desorden=0.0):
    """Contorno de n lados alrededor de cada punto (círculos con n alto, clastos angulosos con n = 3-5)."""
    if not len(P):
        return VACIO
    th = rng.uniform(0, 2 * np.pi, len(P))[:, None] + np.linspace(0, 2 * np.pi, n + 1)[None, :]
    rr = np.asarray(r)[:, None] * (1 + rng.uniform(-desorden, desorden, (len(P), n + 1)))
    rr[:, -1] = rr[:, 0]
    X, Y = P[:, 0, None] + rr * np.cos(th), P[:, 1, None] + rr * np.sin(th)
    a = np.stack([X[:, :-1], Y[:, :-1]], -1)
    b = np.stack([X[:, 1:], Y[:, 1:]], -1)
    return np.stack([a, b], 2).reshape(-1, 2, 2)


def _lineas(R, dy):
    return np.array([[[-R, y], [R, y]] for y in np.arange(-R, R + dy, dy)])


def _ondas(R, dy, amp, lam, rng, paso=0.6):
    u = np.arange(-R, R + paso, paso)
    out = []
    for y in np.arange(-R, R + dy, dy):
        v = y + amp * np.sin(2 * np.pi * u / lam + rng.uniform(0, 2 * np.pi)) + rng.normal(0, amp * 0.12, len(u))
        p = np.column_stack([u, v])
        out.append(np.stack([p[:-1], p[1:]], 1))
    return np.concatenate(out)


# ------------------------------------------------------------------ tramas (FGDC entre paréntesis)
def t_caliza(R, rng, k, oblicua=False):  # 627 caliza, 642 dolomía
    dy, dx = 2.1 * k, 4.4 * k
    P = _rejilla(R, dx, dy, rng, 0.03)
    tic = _seg(P, (0, 0), (0.55 * dy, dy)) if oblicua else _seg(P, (0, 0), (0, dy))
    return np.concatenate([_lineas(R, dy), tic]), None


def t_dolomia(R, rng, k):
    return t_caliza(R, rng, k, oblicua=True)


def t_marga(R, rng, k):  # 638 caliza arcillosa
    seg, _ = t_caliza(R, rng, k * 1.15)
    P = _rejilla(R, 4.4 * k * 1.15, 2.1 * k * 1.15, rng, 0.04)
    return np.concatenate([seg, _guion(P[:, :2] + [2.4 * k, 1.2 * k], 1.3 * k)]), None


def t_arenisca(R, rng, k):  # 607
    return VACIO, _rejilla(R, 1.35 * k, 1.15 * k, rng, 0.32)[:, :2]


def t_arenisca_cruzada(R, rng, k):  # 609
    h, sep = 4.6 * k, 1.5 * k
    P = _rejilla(R, 0.5 * k, 0.5 * k, rng, 0.1)[:, :2]
    yl = np.mod(P[:, 1], h)
    keep = np.mod(P[:, 0] - yl / np.tan(np.radians(28)), sep) < 0.3 * k
    return _lineas(R, h), P[keep]


def t_limolita(R, rng, k):  # 616
    P = _rejilla(R, 1.2 * k, 2.4 * k, rng, 0.2)
    G = _rejilla(R, 3.0 * k, 2.4 * k, rng, 0.05)[:, :2] + [0, 1.2 * k]
    return _guion(G, 1.6 * k), P[:, :2]


def t_lutita(R, rng, k):  # 620
    return _guion(_rejilla(R, 3.2 * k, 1.25 * k, rng, 0.06), 2.0 * k), None


def t_conglomerado(R, rng, k):  # 601
    P = _rejilla(R, 2.6 * k, 2.3 * k, rng, 0.35)
    puntos = _rejilla(R, 1.6 * k, 1.4 * k, rng, 0.4)[:, :2]
    return _poligono(P, rng.uniform(0.3, 0.85, len(P)) * k, 9, rng, 0.08), puntos[::2]


def t_brecha(R, rng, k):  # 605
    P = _rejilla(R, 2.8 * k, 2.5 * k, rng, 0.35)
    puntos = _rejilla(R, 1.8 * k, 1.6 * k, rng, 0.4)[:, :2]
    return _poligono(P, rng.uniform(0.55, 1.0, len(P)) * k, 3, rng, 0.25), puntos[::3]


def t_esquisto(R, rng, k):  # 705
    return _ondas(R, 1.3 * k, 0.28 * k, 3.2 * k, rng), None


def t_gneis(R, rng, k):  # 708
    P = _rejilla(R, 2.4 * k, 1.7 * k, rng, 0.3)[:, :2] + [0, 0.85 * k]
    return np.concatenate([_ondas(R, 1.7 * k, 0.45 * k, 4.5 * k, rng), _tic(P, 0.6 * k, rng, 60, 20)]), None


def t_granito(R, rng, k):  # 718
    return _tic(_rejilla(R, 1.9 * k, 1.7 * k, rng, 0.45), 0.75 * k, rng), None


def t_intrusivo(R, rng, k):  # 721 (pórfido)
    return _mas(_rejilla(R, 2.5 * k, 2.1 * k, rng, 0.06), 1.0 * k), None


def t_batolito(R, rng, k):  # 725
    return _x(_rejilla(R, 2.2 * k, 2.0 * k, rng, 0.05), 0.8 * k), None


def t_andesita(R, rng, k):  # «v» de los informes andinos (731)
    return _v(_rejilla(R, 2.6 * k, 2.3 * k, rng, 0.38), 0.9 * k), None


def t_toba(R, rng, k):  # 711
    P = _rejilla(R, 2.0 * k, 1.8 * k, rng, 0.25)
    par = P[:, 2] % 2 == 0
    puntos = _rejilla(R, 1.7 * k, 1.5 * k, rng, 0.45)[:, :2]
    return np.concatenate([_v(P[par], 0.65 * k), _vi(P[~par], 0.65 * k)]), puntos[::4]


def t_brecha_volcanica(R, rng, k):  # 715
    P = _rejilla(R, 2.7 * k, 2.4 * k, rng, 0.35)
    tri = P[P[:, 2] % 2 == 0]
    cir = P[P[:, 2] % 2 == 1]
    puntos = _rejilla(R, 1.4 * k, 1.2 * k, rng, 0.45)[:, :2]
    return np.concatenate([_poligono(tri, rng.uniform(0.5, 0.95, len(tri)) * k, 3, rng, 0.25),
                           _poligono(cir, rng.uniform(0.25, 0.5, len(cir)) * k, 8, rng, 0.1)]), puntos[::2]


def t_basalto(R, rng, k):  # 717
    P = _rejilla(R, 0.5 * k, 2.4 * k, rng, 0.0, escalon=False)
    a = rng.uniform(0.2, 0.5, len(P)) * k
    b = 2.4 * k - rng.uniform(0.2, 0.5, len(P)) * k
    return np.stack([P[:, :2] + np.column_stack([np.zeros(len(P)), a]),
                     P[:, :2] + np.column_stack([np.zeros(len(P)), b])], 1), None


def t_lava_fresca(R, rng, k):
    return _x(_rejilla(R, 2.6 * k, 2.4 * k, rng, 0.4), 0.8 * k), None


def t_metamorfico(R, rng, k):  # 701
    return _tic(_rejilla(R, 2.0 * k, 1.6 * k, rng, 0.4), 0.9 * k, rng, 0, 40), None


def t_cuarcita(R, rng, k):  # 702
    return VACIO, _rejilla(R, 0.85 * k, 0.8 * k, rng, 0.4)[:, :2]


def t_sinter(R, rng, k):
    return _ondas(R, 0.9 * k, 0.12 * k, 2.5 * k, rng), None


def t_skarn(R, rng, k):  # granate + piroxeno
    P = _rejilla(R, 1.8 * k, 1.6 * k, rng, 0.3)
    return np.concatenate([_poligono(P[::2], np.full(len(P[::2]), 0.35 * k), 6, rng),
                           _tic(P[1::2], 0.7 * k, rng)]), None


TRAMAS = {  # nombre -> (función, color de la trama)
    "caliza": (t_caliza, "#4f5d6b"), "dolomia": (t_dolomia, "#4f5d6b"), "marga": (t_marga, "#4f5d6b"),
    "arenisca": (t_arenisca, "#6b5a3a"), "arenisca_cruzada": (t_arenisca_cruzada, "#6b5a3a"),
    "limolita": (t_limolita, "#5a5446"), "lutita": (t_lutita, "#4a4a4a"),
    "conglomerado": (t_conglomerado, "#8a744a"), "brecha": (t_brecha, "#55663f"),
    "esquisto": (t_esquisto, "#4a4a4a"), "gneis": (t_gneis, "#4a4a4a"), "granito": (t_granito, "#7a3e3e"),
    "intrusivo": (t_intrusivo, "#9b4b4b"), "batolito": (t_batolito, "#7a3e3e"),
    "andesita": (t_andesita, "#6f7a62"), "toba": (t_toba, "#7a6640"),
    "brecha_volcanica": (t_brecha_volcanica, "#55663f"), "basalto": (t_basalto, "#3f4d63"),
    "lava_fresca": (t_lava_fresca, "#3f4d63"), "metamorfico": (t_metamorfico, "#4a4a4a"),
    "cuarcita": (t_cuarcita, "#6b5a3a"), "sinter": (t_sinter, "#5a6b7a"), "skarn": (t_skarn, "#5a4a6b"),
}
ALIAS = {"grava": "conglomerado", "morrena": "conglomerado", "suelo": "conglomerado", "porfido": "intrusivo",
         "pórfido": "intrusivo", "dolomía": "dolomia", "lava": "basalto", "marmol": "caliza", "mármol": "caliza",
         "hornfels": "metamorfico", "pizarra": "esquisto", "filita": "esquisto", "ignimbrita": "toba",
         "diorita": "granito", "granodiorita": "granito", "tonalita": "granito", "lodolita": "lutita"}


def es_trama(nombre):
    return bool(nombre) and (nombre in TRAMAS or nombre in ALIAS)


def escala_mm(ax):
    """Unidades de datos por milímetro de papel en x y en y."""
    bb = ax.get_window_extent()
    dpi = ax.figure.dpi
    (xa, xb), (ya, yb) = ax.get_xlim(), ax.get_ylim()
    return (xb - xa) / (bb.width / dpi * 25.4), (yb - ya) / (bb.height / dpi * 25.4)


def trama(ax, nombre, clip, mm, rng, ang=0.0, color=None, escala=1.0, lw=0.45, zorder=1.5, extension=None):
    """Dibuja la trama `nombre` recortada a `clip` (un parche ya agregado a `ax`), girada `ang` grados en el papel."""
    if not es_trama(nombre) or clip is None:
        return
    fn, col0 = TRAMAS[ALIAS.get(nombre, nombre)]
    e = extension or clip.get_path().transformed(clip.get_patch_transform()).get_extents()
    x0, y0, x1, y1 = e.x0, e.y0, e.x1, e.y1
    mx, my = mm
    W, H = (x1 - x0) / mx, (y1 - y0) / my
    if W <= 0 or H <= 0:
        return
    R = min(np.hypot(W, H) / 2 + 4 * escala, 600)
    segs, puntos = fn(R, rng, escala)
    c, s = np.cos(np.radians(ang)), np.sin(np.radians(ang))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def a_datos(A):
        u, v = A[..., 0] * c - A[..., 1] * s, A[..., 0] * s + A[..., 1] * c
        return np.stack([cx + u * mx, cy + v * my], -1)

    col = color or col0
    if segs is not None and len(segs):
        S = a_datos(segs)
        ok = (S[:, :, 0].max(1) >= x0) & (S[:, :, 0].min(1) <= x1) & (S[:, :, 1].max(1) >= y0) & (S[:, :, 1].min(1) <= y1)
        lc = LineCollection(S[ok], colors=col, linewidths=lw, zorder=zorder, capstyle="round")
        ax.add_collection(lc, autolim=False)
        lc.set_clip_path(clip)
    if puntos is not None and len(puntos):
        D = a_datos(puntos)
        ok = (D[:, 0] >= x0) & (D[:, 0] <= x1) & (D[:, 1] >= y0) & (D[:, 1] <= y1)
        sc = ax.scatter(D[ok, 0], D[ok, 1], s=1.6 * lw / 0.45, c=col, lw=0, zorder=zorder)
        sc.set_clip_path(clip)
