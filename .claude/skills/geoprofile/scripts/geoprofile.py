# -*- coding: utf-8 -*-
"""geoprofile: perfiles, secciones y columnas estratigráficas con aspecto de informe geológico real.

Uso:
    python geoprofile.py perfil  config.json salida.png
    python geoprofile.py columna config.json salida.png
    python geoprofile.py ejemplo carpeta_salida        # los dos ejemplos de Arcata
    python geoprofile.py tramas  salida.png            # muestrario de tramas FGDC

El config.json solo lleva lo que cambia. Con "plantilla": "arcata" (por defecto) el resto sale de
PERFIL_ARCATA / COLUMNA_ARCATA; con "plantilla": "vacia" parte de una sección o columna en blanco.
Requiere numpy, matplotlib, shapely y Pillow.
"""
import copy
import json
import os
import re
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.transforms as mtrans
import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon as SPoly
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tramas import ALIAS, TRAMAS, es_trama, escala_mm, trama  # noqa: E402

plt.rcParams.update({"font.family": ["Calibri", "DejaVu Sans"], "font.size": 9, "hatch.linewidth": 0.5})
DPI_MIN = 220  # por debajo, Calibri usa sus mapas de bits incrustados y matplotlib pierde el texto


# ------------------------------------------------------------------ piezas comunes
def rugoso(rng, n, amp, suave=9):
    """Ruido suavizado (camino aleatorio con media móvil): contactos que no son rectas."""
    if amp == 0:
        return np.zeros(n)
    r = np.cumsum(rng.normal(0, 1, n + suave))
    r = np.convolve(r, np.ones(suave) / suave, mode="valid")[:n]
    r -= np.linspace(r[0], r[-1], n)
    return amp * r / (np.abs(r).max() + 1e-9)


def fusionar(base, cambios):
    out = copy.deepcopy(base)
    for k, v in (cambios or {}).items():
        out[k] = fusionar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def envolver(texto, ancho):
    return "\n".join(textwrap.fill(l, ancho, break_long_words=False) if len(l) > ancho else l for l in str(texto).split("\n"))


def guardar(fig, salida, dpi):
    """Guarda a `dpi`; si es bajo, dibuja a DPI_MIN y reduce la imagen (así el texto no desaparece)."""
    fig.savefig(salida, dpi=max(dpi, DPI_MIN))
    if dpi < DPI_MIN:
        from PIL import Image
        im = Image.open(salida)
        f = dpi / DPI_MIN
        im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS).save(salida)


def a_parche(geom, **kw):
    """Geometría de shapely (Polygon o MultiPolygon, con huecos) -> PathPatch de matplotlib."""
    if geom is None or geom.is_empty:
        return None
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
    verts, codes = [], []
    for p in polys:
        for anillo in [p.exterior, *p.interiors]:
            c = np.asarray(anillo.coords)
            if len(c) < 4:
                continue
            verts += c.tolist()
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY]
    return PathPatch(MPath(verts, codes), **kw) if verts else None


def poligonos(geom):
    if geom is None or geom.is_empty:
        return []
    return [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]


def lineas(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if g.geom_type == "LineString"]


def repartir(items, paso, z_min, z_max):
    """items: [z, n_lineas, ...]. Separa los rótulos según su alto y los mantiene dentro de [z_min, z_max]."""
    items.sort(key=lambda g: -g[0])
    alto = lambda i, j: paso * (items[i][1] + items[j][1]) / 2 + paso * 0.35
    for i in range(len(items)):
        items[i][0] = min(items[i][0], z_max - paso * items[i][1] / 2)
        if i:
            items[i][0] = min(items[i][0], items[i - 1][0] - alto(i - 1, i))
    if items and items[-1][0] - paso * items[-1][1] / 2 < z_min:
        items[-1][0] = z_min + paso * items[-1][1] / 2
        for i in range(len(items) - 2, -1, -1):
            items[i][0] = max(items[i][0], items[i + 1][0] + alto(i, i + 1))
    return items


def estilo_linea(ls):
    """Estilo de línea desde JSON: "-", "--" o [desfase, [trazo, hueco]]."""
    return (ls[0], tuple(ls[1])) if isinstance(ls, list) else ls


def nl(texto):
    return str(texto).count("\n") + 1


def pintar_relleno(ax, geom, color, trama_, mm, rng, ang=0.0, borde="#3a3a3a", lw=0.6, zorder=1.0, alpha=1.0,
                   color_trama=None, escala=1.0, pendientes=None):
    """Relleno de color + trama FGDC (o hatch de matplotlib si `trama_` no es una trama conocida)."""
    hatch = None if es_trama(trama_) else (trama_ or None)
    p = a_parche(geom, facecolor=color, edgecolor=borde, lw=lw, zorder=zorder, alpha=alpha, hatch=hatch,
                 transform=ax.transData)
    if p is None:
        return None
    ax.add_patch(p)
    if es_trama(trama_):
        pendientes.append((ax, trama_, p, ang, color_trama, escala, zorder + 0.05))
    return p


# ------------------------------------------------------------------ perfil / sección
PERFIL_ARCATA = {
    "semilla": 7,
    "figsize": [7.6, 5.6], "dpi": 240,
    "x": [-420, 420], "z": [4150, 5010], "orientacion": ["SW", "NE"],
    "topo": {"cota": 4860, "ondulacion": 35, "pendiente": -0.06, "rugosidad": 18},
    "caja": {"color": "#eef0e4", "simbolo": "andesita", "nombre": "Flujos andesíticos (caja)"},
    "intercalada": {"base": 4505, "espesor": 55, "pendiente": -0.10, "color": "#e6dcc6", "trama": "toba",
                    "nombre": "Piroclásticos"},
    "veta": {"x": -40, "buzamiento": 80, "ancho": 5, "hinchamiento": 3.5, "ramales": [[4640, -1], [4700, 1], [4590, 1]]},
    "clavo": {"z": [4340, 4600], "texto": "Clavo de Ag (sulfosales,\nbrecha hidrotermal)", "brecha": True},
    "halos": [  # de afuera hacia adentro; z_ini > base: el halo nace ahí y se abre hacia arriba
        {"nombre": "Propilítica", "rotulo": "Propilítica: clorita–\ncalcita–epidota", "ancho": [70, 330],
         "rugosidad": 40, "color": "#9cc58f", "borde": "#4f7a45", "trama": "---", "alpha": 0.55, "rotulo_z": 4660},
        {"nombre": "Argílica", "rotulo": "Argílica: caolinita dentro,\nmontmorillonita fuera", "ancho": [0, 230],
         "rugosidad": 22, "z_ini": 4545, "color": "#e7c46d", "borde": "#9a7420", "trama": "////", "alpha": 0.75,
         "rotulo_z": 4790},
        {"nombre": "Sílice–adularia", "rotulo": "Sílice–adularia", "ancho": [12, 32], "rugosidad": 8,
         "color": "#c9c9c9", "borde": "#7a7a7a", "trama": "||", "alpha": 0.85, "rotulo_z": 4400},
    ],
    "falla": {"x_base": 250, "inclinacion": 0.35, "salto": 30, "texto": "Falla normal NW (premineral)"},
    "ebullicion": {"z": 4590, "texto": "Nivel de ebullición inferido"},
    "intervalos": [[4600, 4340, "Ag"], [4400, 4160, "Pb–Zn–Cu"]],
    "cobertura": {"desde_x": 120, "espesor": 40, "nombre": "Gr. Barroso (posmineral)",
                  "rotulo": "Gr. Barroso: lavas frescas, posminerales"},
    "morrena": {"x": [-330, -150], "rotulo": "Morrena"},
    "escala_m": 100,
}

PERFIL_VACIO = {
    "semilla": 7, "figsize": [7.6, 5.6], "dpi": 240, "x": [-500, 500], "z": [0, 1000], "orientacion": ["W", "E"],
    "topo": {"cota": 900, "ondulacion": 20, "pendiente": 0.0, "rugosidad": 15},
    "caja": {"color": "#eef0e4", "trama": None, "nombre": "Roca caja"},
    "escala_m": 100,
}
# Claves de la plantilla vacía (todas opcionales):
#  eje: "cota" | "profundidad" | "relativo";  columna_rotulos: fracción del ancho para los rótulos (0.36)
#  topo.puntos: [[x, z], ...] para una topografía dibujada a mano (cañones, conos)
#  secuencias: [{nombre, base: {z, pendiente, rugosidad, nombre, color} | null, z0, pendiente, rugosidad,
#               capas: [{espesor, color, trama, nombre, rotulo}]}]  de la más antigua a la más joven;
#               «base» es la discordancia sobre la que se apoya la secuencia (trunca a las anteriores)
#  fallas: [{x_base, inclinacion, salto, texto, sella, posmineral}]  sella = índice de la secuencia que la tapa
#  intrusivos: [{x, ancho_base, ancho_techo, z_techo, color, trama, nombre, rotulo, rugosidad}]
#  cuerpos: [{x, z, largo, ancho, angulo, color, trama, nombre}]  lentes de mena o de reemplazo
#  mantos: [{desde, hasta, x, color, trama, nombre, rotulo}]  capas que siguen la topografía (lixiviado, cobertura)
#  nivel_freatico: {prof, texto};  franja: [[x0, x1, "texto"], ...] encima de la sección
#  veta (o null), clavo {z, texto, brecha, lentes}, halos [{..., z_ini, z_fin}], ebullicion, intervalos


def normalizar_perfil(c):
    """Lleva las claves antiguas (intercalada, falla, cobertura, morrena, simbolo) al modelo nuevo."""
    c = copy.deepcopy(c)
    caja = c.setdefault("caja", {})
    caja.setdefault("trama", caja.get("simbolo"))
    secs = c.setdefault("secuencias", [])
    ic = c.pop("intercalada", None)
    if ic:
        secs.insert(0, {"base": None, "z0": ic["base"], "pendiente": ic.get("pendiente", 0), "rugosidad": 12,
                        "capas": [{"espesor": ic["espesor"], "color": ic["color"], "trama": ic.get("trama"),
                                   "nombre": ic["nombre"], "borde": "#7d6e4e"}]})
    fl = c.setdefault("fallas", [])
    f = c.pop("falla", None)
    if f:
        fl.insert(0, f)
    mantos = c.setdefault("mantos", [])
    cb = c.pop("cobertura", None)
    if cb:
        mantos.append({"x": [cb["desde_x"], None], "desde": 0, "hasta": cb["espesor"], "rampa": 60,
                       "color": "#7f8fa6", "trama": cb.get("trama", "lava_fresca"), "borde": "#3e4a5c",
                       "nombre": cb["nombre"], "rotulo": cb.get("rotulo")})
    mo = c.pop("morrena", None)
    if mo:
        mantos.append({"x": mo["x"], "desde": 0, "hasta": 16, "lente": True, "color": "#f2ead0",
                       "trama": "conglomerado", "borde": "#a08c5a", "nombre": mo.get("nombre", "Morrena"),
                       "rotulo": mo.get("rotulo"), "rotulo_arriba": True})
    return c


def perfil(cfg_usuario, salida):
    cfg_usuario = cfg_usuario or {}
    base = PERFIL_VACIO if cfg_usuario.get("plantilla") == "vacia" else PERFIL_ARCATA
    c = normalizar_perfil(fusionar(base, cfg_usuario))
    rng = np.random.default_rng(c["semilla"])
    X0, X1 = c["x"]; ZB, ZT = c["z"]
    span, alto_z = X1 - X0, ZT - ZB
    XC = X1 + span * 0.024  # columna de rótulos a la derecha de la sección
    n = 500
    x = np.linspace(X0, X1, n)
    t = c["topo"]
    if t.get("puntos"):
        P = np.asarray(t["puntos"], float)
        topo = np.interp(x, P[:, 0], P[:, 1]) + rugoso(rng, n, t.get("rugosidad", 0), 15)
    else:
        topo = t["cota"] + t.get("ondulacion", 0) * np.sin((x + 80) / 170) + t.get("pendiente", 0) * x + \
            rugoso(rng, n, t.get("rugosidad", 0), 15)
    topo = np.minimum(topo, ZT - alto_z * 0.03)
    suelo = SPoly(np.column_stack([np.r_[x, X1, X0], np.r_[topo, ZB, ZB]])).buffer(0)
    BAJO, ALTO = ZB - alto_z * 3, ZT + alto_z * 3
    por_debajo = lambda curva: SPoly(np.column_stack([np.r_[x, X1, X0], np.r_[curva, BAJO, BAJO]])).buffer(0)
    por_encima = lambda curva: SPoly(np.column_stack([np.r_[x, X1, X0], np.r_[curva, ALTO, ALTO]])).buffer(0)

    # ---- figura: sección arriba, leyenda y escala abajo
    items_ley = []
    filas_ley = 1
    ncol = c.get("columnas_leyenda", 3)
    fig = plt.figure(figsize=c["figsize"], dpi=c["dpi"])
    ax = fig.add_subplot(111)
    pend = []  # tramas que se dibujan cuando ya se conoce la escala del papel
    fr = c.get("columna_rotulos", 0.36)
    ax.set_xlim(X0, X1 + span * fr); ax.set_ylim(ZB, ZT)
    mm = escala_mm(ax)  # provisional; se recalcula tras tight_layout
    def ang_papel(a, m=None):
        """Ángulo en el papel: grados tal cual, o («p», pendiente dz/dx) según la escala del papel."""
        m = m or mm
        return float(np.degrees(np.arctan(a[1] * m[0] / m[1]))) if isinstance(a, tuple) else float(a or 0)

    # ---- fallas -> bloques
    fallas = []
    fz_v = np.linspace(ZB - alto_z * 0.05, ZT + alto_z * 0.05, 78)
    fz = np.r_[BAJO, fz_v, ALTO]  # tramo visible con ruido; los extremos solo cierran los bloques
    for f in c.get("fallas", []):
        fx = f["x_base"] - (fz_v - ZB) * f["inclinacion"] + rugoso(rng, 78, span * 0.004, 5)
        fx = np.r_[fx[0], fx, fx[-1]]
        fallas.append({**f, "fx": fx, "x_med": np.interp((ZB + ZT) / 2, fz, fx)})
    fallas.sort(key=lambda f: f["x_med"])
    izq = np.full(80, X0 - span)
    bloques = []
    for f in fallas + [None]:
        der = f["fx"] if f else np.full(80, X1 + span)
        bloques.append(SPoly(np.column_stack([np.r_[izq, der[::-1]], np.r_[fz, fz[::-1]]])).buffer(0))
        izq = der if f else izq
    secs = c.get("secuencias", [])
    nsec = len(secs)

    def desplaz(b, k):
        """Salto acumulado del bloque b para la secuencia k (k = nsec: lo mineral, si la falla es posmineral)."""
        d = 0.0
        for f in fallas[:b]:
            corta = (k < f["sella"]) if f.get("sella") is not None else True
            if k == nsec:
                corta = bool(f.get("posmineral"))
            d -= f.get("salto", 0) * corta
        return d

    # ---- caja
    caja = c["caja"]
    zc_caja = 0.5
    pintar_relleno(ax, suelo, caja["color"], caja.get("trama"), mm, rng, borde="none", zorder=zc_caja, pendientes=pend,
                   ang=caja.get("ang", 0), color_trama=caja.get("color_trama"))
    items_ley.append({"nombre": caja["nombre"], "color": caja["color"], "trama": caja.get("trama"), "ang": caja.get("ang", 0)})

    # ---- secuencias, truncadas por las discordancias y desplazadas por las fallas
    sup = []  # curva de la base (discordancia) de cada secuencia, o None
    for s in secs:
        bs = s.get("base")
        sup.append(None if not bs else bs["z"] + bs.get("pendiente", 0) * x + rugoso(rng, n, bs.get("rugosidad", 0), 21))
    ocupado = []
    rotulos_capa = []
    for k, s in enumerate(secs):
        p = s.get("pendiente", 0.0)
        bordes = [s["z0"] + p * x + rugoso(rng, n, s.get("rugosidad", 10), 21)]
        for cp in s["capas"]:
            bordes.append(bordes[-1] + cp["espesor"] + rugoso(rng, n, cp.get("rugosidad", s.get("rugosidad", 10) * 0.8), 17))
        rellena = sup[k] is not None or s.get("rellena", False)
        trozos = [[] for _ in s["capas"]]  # una capa = unión de sus trozos en todos los bloques
        for b, blq in enumerate(bloques):
            d = desplaz(b, k)
            region = blq.intersection(suelo)
            if sup[k] is not None:
                region = region.intersection(por_encima(sup[k] + d))
            for j in range(k + 1, nsec):
                if sup[j] is not None:
                    region = region.intersection(por_debajo(sup[j] + desplaz(b, j)))
            if region.is_empty:
                continue
            for i, cp in enumerate(s["capas"]):
                lo = bordes[i] + d if not (rellena and i == 0) else np.full(n, BAJO)
                hi = bordes[i + 1] + d if not (rellena and i == len(s["capas"]) - 1) else np.full(n, ALTO)
                hi = np.maximum(hi, lo + 0.5)
                banda = SPoly(np.column_stack([np.r_[x, x[::-1]], np.r_[lo, hi[::-1]]])).buffer(0)
                g = banda.intersection(region)
                if not g.is_empty:
                    trozos[i].append(g)
        for i, cp in enumerate(s["capas"]):
            if not trozos[i]:
                continue
            g = unary_union([t_.buffer(0.01) for t_ in trozos[i]]).buffer(-0.01)
            pintar_relleno(ax, g, cp["color"], cp.get("trama"), mm, rng, ang=("p", p), zorder=1 + 0.1 * k,
                           borde=cp.get("borde", "#5a5a5a"), lw=0.55, pendientes=pend,
                           color_trama=cp.get("color_trama"), escala=cp.get("escala_trama", 1.0))
            ocupado.append(g)
            rotulos_capa.append((cp, g, ("p", p)))
    for k, s in enumerate(secs):
        for cp in s["capas"]:
            if not cp["nombre"].startswith("_") and all(it["nombre"] != cp["nombre"] for it in items_ley):
                items_ley.append({"nombre": cp["nombre"], "color": cp["color"], "trama": cp.get("trama"),
                                  "ang": ("p", s.get("pendiente", 0)), "borde": cp.get("borde", "#5a5a5a")})

    # ---- intrusivos (cortan a las secuencias)
    encima = []  # lo que tapa a las capas (para no rotularlas debajo)
    for i_it, it in enumerate(c.get("intrusivos", [])):
        zz = np.linspace(ZB - alto_z * 0.05, it["z_techo"], 120)
        t_ = np.clip((zz - ZB) / max(it["z_techo"] - ZB, 1), 0, 1)
        a = it["ancho_base"] / 2 + (it["ancho_techo"] / 2 - it["ancho_base"] / 2) * t_
        a = a + np.abs(rugoso(rng, 120, it.get("rugosidad", span * 0.01), 11))
        cupula = np.linspace(-1, 1, 40)
        xs = np.r_[it["x"] - a, it["x"] + it["ancho_techo"] / 2 * cupula, (it["x"] + a)[::-1]]
        zs = np.r_[zz, it["z_techo"] + it.get("domo", alto_z * 0.03) * (1 - cupula ** 2), zz[::-1]]
        cuerpo = SPoly(np.column_stack([xs, zs])).buffer(0)
        g = cuerpo.intersection(suelo)
        pintar_relleno(ax, g, it.get("color", "#f2d0c8"), it.get("trama", "intrusivo"), mm, rng,
                       zorder=3 + 0.1 * i_it, borde=it.get("borde", "#7a3e3e"), lw=0.7, pendientes=pend)
        ocupado.append(g)
        encima.append(g)
        items_ley.append({"nombre": it["nombre"], "color": it.get("color", "#f2d0c8"), "trama": it.get("trama", "intrusivo")})
        if it.get("rotulo"):
            rotulos_capa.append(({"nombre": it["nombre"], "rotulo": it["rotulo"]}, g, 0))
        # aureolas de alteración: capas concéntricas de afuera hacia adentro; distancia < 0 = núcleo dentro del cuerpo
        aur = it.get("aureolas", [])
        conchas = []
        for au in aur:
            ga = cuerpo.buffer(au["distancia"], join_style=1)
            for p_ in poligonos(ga)[:1]:
                xy = np.asarray(p_.exterior.coords)
                k_ = len(xy)
                amp = au.get("rugosidad", abs(au["distancia"]) * 0.18 + span * 0.004)
                xy = xy + np.column_stack([rugoso(rng, k_, amp, 9), rugoso(rng, k_, amp, 9)])
                xy[-1] = xy[0]
                ga = SPoly(xy).buffer(0)
            conchas.append(ga.intersection(suelo))
        for j, (au, ga) in enumerate(zip(aur, conchas)):
            anillo = ga.difference(conchas[j + 1]) if j + 1 < len(conchas) else ga
            zo = (2.9 - 0.01 * (len(aur) - j)) if au["distancia"] >= 0 else (3.3 + 0.1 * i_it + 0.01 * j)
            p = a_parche(ga, facecolor=au["color"], alpha=au.get("alpha", 0.6), edgecolor=au.get("borde", "#555555"),
                         hatch=au.get("trama"), lw=0.6, zorder=zo, transform=ax.transData)
            if p is not None:
                ax.add_patch(p)
            ocupado.append(ga)
            items_ley.append({"nombre": au["nombre"], "color": au["color"], "trama": au.get("trama"),
                              "borde": au.get("borde", "#555555"), "alpha": au.get("alpha", 0.6)})
            if au.get("rotulo"):
                rotulos_capa.append(({"nombre": au["nombre"], "rotulo": au["rotulo"]}, anillo, 0))

    # ---- veta, halos, clavo, ramales (lo mineral; se desplaza solo con fallas posminerales)
    z = np.linspace(ZB - alto_z * 0.2, ZT + alto_z * 0.05, 400)
    v = c.get("veta")
    zt_viejo = min(ZT - 110 * alto_z / 860, topo.max() + 30)
    ztope = min(topo.max() + alto_z * 0.01, ZT)
    mineral = []  # (geom, estilo)
    xv = w = None
    if v:
        zc_v = v.get("z_ref", (ZB + zt_viejo) / 2)
        xv = v["x"] + (z - zc_v) / np.tan(np.radians(v["buzamiento"])) + rugoso(rng, 400, span * 0.011, 13)
        w = v["ancho"] + v["hinchamiento"] * np.abs(np.sin((z - ZB) / (alto_z * 0.052))) + rugoso(rng, 400, v["ancho"] * 0.24, 7)
        w = np.maximum(w, 0.5)
    for h in c.get("halos", []):
        if xv is None:
            break
        z_ini = h.get("z_ini", ZB)
        z_fin = h.get("z_fin")
        zz = z[(z >= z_ini) & (z <= (z_fin if z_fin else ALTO))]
        if z_fin:
            tt = (zz - z_ini) / max(z_fin - z_ini, 1)
            a = h["ancho"][0] + (h["ancho"][1] - h["ancho"][0]) * np.sin(np.pi * tt) ** 0.7
        else:
            a = np.interp(zz, [z_ini, ztope], h["ancho"])
        xc = np.interp(zz, z, xv)
        l_ = xc - a - np.abs(rugoso(rng, len(zz), h["rugosidad"], 15))
        r_ = xc + a + np.abs(rugoso(rng, len(zz), h["rugosidad"], 15))
        g = SPoly(np.column_stack([np.r_[l_, r_[::-1]], np.r_[zz, zz[::-1]]])).buffer(0)
        mineral.append((g, dict(facecolor=h["color"], alpha=h["alpha"], edgecolor=h["borde"], hatch=h["trama"],
                                lw=0, zorder=4)))
        ocupado.append(g)
    if v:
        g = SPoly(np.column_stack([np.r_[xv - w / 2, (xv + w / 2)[::-1]], np.r_[z, z[::-1]]])).buffer(0)
        mineral.append((g, dict(facecolor=v.get("color", "#3c3c3c"), edgecolor="none", zorder=6)))
    cl = c.get("clavo")
    if cl and v:
        if cl.get("lentes"):
            zs_l = np.sort(rng.uniform(cl["z"][0], cl["z"][1], cl["lentes"]))
            for zl in zs_l:
                L = (cl["z"][1] - cl["z"][0]) / cl["lentes"] * rng.uniform(0.35, 0.7)
                k_ = (z > zl - L / 2) & (z < zl + L / 2)
                if k_.sum() < 3:
                    continue
                gros = np.sin(np.linspace(0, np.pi, k_.sum())) * (w[k_] / 2 + span * 0.006)
                g = SPoly(np.column_stack([np.r_[xv[k_] - gros, (xv[k_] + gros)[::-1]], np.r_[z[k_], z[k_][::-1]]])).buffer(0)
                mineral.append((g, dict(facecolor="#b3261e", edgecolor="none", zorder=7)))
        else:
            k_ = (z > cl["z"][0]) & (z < cl["z"][1])
            g = SPoly(np.column_stack([np.r_[xv[k_] - w[k_] / 2 - span * 0.0036, (xv[k_] + w[k_] / 2 + span * 0.0036)[::-1]],
                                       np.r_[z[k_], z[k_][::-1]]])).buffer(0)
            mineral.append((g, dict(facecolor="#b3261e", edgecolor="none", zorder=7)))
    ramales = []
    if v:
        for z0, sgn in v.get("ramales", []):
            zs = np.linspace(z0, ZT + alto_z * 0.05, 60)
            xs = np.interp(z0, z, xv) + sgn * (zs - z0) * (0.45 if sgn > 0 else 0.6) + rugoso(rng, 60, span * 0.006, 9)
            ramales.append(LineString(np.column_stack([xs, zs])))
    previo = {"nombre": "Cuerpo mineralizado", "color": "#1f1f1f"}
    for cu in c.get("cuerpos", []):  # un cuerpo sin nombre es del mismo tipo (y estilo) que el anterior
        if "nombre" not in cu:
            for k_ in ("nombre", "color", "trama", "borde"):
                if k_ in previo and k_ not in cu:
                    cu[k_] = previo[k_]
        previo = cu
    for cu in c.get("cuerpos", []):
        th = np.linspace(0, 2 * np.pi, 60)
        rr = 1 + rugoso(rng, 60, 0.25, 7)
        rr[-1] = rr[0]
        ex, ez = cu["largo"] / 2 * rr * np.cos(th), cu["ancho"] / 2 * rr * np.sin(th) * (1 + 0.5 * np.cos(th))
        a_ = np.radians(cu.get("angulo", 0))
        g = SPoly(np.column_stack([cu["x"] + ex * np.cos(a_) - ez * np.sin(a_),
                                   cu["z"] + ex * np.sin(a_) + ez * np.cos(a_)])).buffer(0)
        mineral.append((g, dict(facecolor=cu.get("color", "#1f1f1f"), edgecolor=cu.get("borde", "none"), zorder=7.5,
                                trama=cu.get("trama"))))
    nombres_cuerpos = {}
    for cu in c.get("cuerpos", []):
        nombres_cuerpos.setdefault(cu["nombre"], (cu.get("color", "#1f1f1f"), cu.get("trama")))

    for b, blq in enumerate(bloques):
        d = desplaz(b, nsec)
        for g, est in mineral:
            est = dict(est)
            tr = est.pop("trama", None)
            gg = translate(g, yoff=d).intersection(blq).intersection(suelo)
            p = a_parche(gg, transform=ax.transData, **est)
            if p is not None:
                ax.add_patch(p)
                if tr:
                    pend.append((ax, tr, p, 0, "#ffffff", 0.8, est["zorder"] + 0.05))
        for ln in ramales:
            for seg in lineas(translate(ln, yoff=d).intersection(blq).intersection(suelo)):
                xy = np.asarray(seg.coords)
                ax.plot(xy[:, 0], xy[:, 1], color=v.get("color", "#3c3c3c"), lw=v.get("grosor_ramales", 1.4),
                        ls=estilo_linea(v.get("estilo_ramales", "-")), zorder=6)
    if cl and cl.get("brecha") and v:
        bz = rng.uniform(cl["z"][0] + (cl["z"][1] - cl["z"][0]) * 0.3, cl["z"][1] - (cl["z"][1] - cl["z"][0]) * 0.15, 40)
        ax.scatter(np.interp(bz, z, xv) + rng.normal(0, span * 0.007, 40), bz, s=4, marker="^", color="#f1d6d0",
                   zorder=8, lw=0)

    # ---- mantos que siguen la topografía (cobertura posmineral, morrenas, lixiviado, enriquecimiento)
    for m in c.get("mantos", []):
        xa = m.get("x", [X0, X1])
        xa = [X0 if xa[0] is None else xa[0], X1 if xa[1] is None else xa[1]]
        k_ = (x >= xa[0]) & (x <= xa[1])
        if k_.sum() < 3:
            continue
        xm, tm = x[k_], topo[k_]
        esp = np.full(k_.sum(), float(m["hasta"]))
        if m.get("lente"):
            esp = m["hasta"] * (0.4 + 0.6 * np.sin(np.linspace(0, np.pi, k_.sum())))
        elif m.get("rampa"):
            esp = esp * np.clip((xm - xa[0]) / m["rampa"], 0, 1)
        esp = esp + rugoso(rng, k_.sum(), max(m["hasta"] - m.get("desde", 0), 1) * 0.15, 9)
        techo = tm - m.get("desde", 0) + (0.5 if not m.get("desde") else 0)
        piso = np.minimum(tm - np.maximum(esp, m.get("desde", 0) + 1), techo - 0.5)
        g = SPoly(np.column_stack([np.r_[xm, xm[::-1]], np.r_[piso, techo[::-1]]])).buffer(0).intersection(
            suelo.buffer(1))
        pintar_relleno(ax, g, m["color"], m.get("trama"), mm, rng, zorder=10 + 0.01 * len(ocupado),
                       borde=m.get("borde", "#555555"), lw=0.7, pendientes=pend, color_trama=m.get("color_trama"))
        ocupado.append(g)
        encima.append(g)
        items_ley.append({"nombre": m["nombre"], "color": m["color"], "trama": m.get("trama"),
                          "borde": m.get("borde", "#555555")})
    nf = c.get("nivel_freatico")
    if nf:
        yf = topo - nf["prof"] + rugoso(rng, n, nf["prof"] * 0.1, 31)
        yf = np.convolve(np.r_[np.full(30, yf[0]), yf, np.full(30, yf[-1])], np.ones(61) / 61, mode="valid")
        ax.plot(x, yf, color="#1f5fa8", lw=1.0, ls=(0, (5, 2)), zorder=11.5)
        items_ley.append({"nombre": nf.get("texto", "Nivel freático"), "linea": dict(color="#1f5fa8", lw=1.0, ls=(0, (5, 2)))})

    # ---- fallas y discordancias (líneas)
    guias = []

    def guia(xy, z_txt, texto, color="#222222"):
        texto = envolver(texto, c.get("ancho_rotulos", 30))
        guias.append([z_txt, nl(texto), xy, texto, color])

    for i_f, f in enumerate(fallas):
        linea = LineString(np.column_stack([f["fx"], fz])).intersection(suelo)
        if f.get("sella") is not None and sup[f["sella"]] is not None:
            linea = linea.intersection(por_debajo(sup[f["sella"]] + desplaz(i_f, f["sella"])))
        segs = lineas(linea)
        for sg in segs:
            xy = np.asarray(sg.coords)
            ax.plot(xy[:, 0], xy[:, 1], color="#222222", lw=1.1, ls=(0, (6, 3)), zorder=9)
        if segs and f.get("texto"):
            larga = max(segs, key=lambda s_: s_.length)
            pt = larga.interpolate(0.62, normalized=True)
            guia((pt.x, pt.y), pt.y + alto_z * 0.07, f["texto"])
    if fallas:
        items_ley.append({"nombre": c.get("nombre_falla", "Falla"), "linea": dict(color="#222222", lw=1.1, ls=(0, (6, 3)))})
    for k, s in enumerate(secs):
        bs = s.get("base")
        if not bs:
            continue
        col = bs.get("color", "#c0392b")
        visibles = []
        for b, blq in enumerate(bloques):
            curva = sup[k] + desplaz(b, k)
            ln = LineString(np.column_stack([x, curva])).intersection(blq).intersection(suelo.buffer(0.5))
            for j in range(k + 1, nsec):
                if sup[j] is not None:
                    ln = ln.intersection(por_debajo(sup[j] + desplaz(b, j) + 0.5))
            for sg in lineas(ln):
                xy = np.asarray(sg.coords)
                ax.plot(xy[:, 0], xy[:, 1], color=col, lw=bs.get("grosor", 2.0), zorder=9.5, solid_capstyle="round")
                visibles.append(sg)
        if visibles and bs.get("nombre"):
            larga = max(visibles, key=lambda s_: s_.length)
            pt = larga.interpolate(bs.get("rotulo_pos", 0.7), normalized=True)
            guia((pt.x, pt.y), pt.y + alto_z * 0.04, bs["nombre"], col)
            items_ley.append({"nombre": bs.get("leyenda", "Discordancia"), "linea": dict(color=col, lw=2.0)})

    # ---- topografía
    ax.plot(x, topo, color="#5b4a2f", lw=1.6, zorder=11)

    # ---- rótulos
    por_nombre, puestos = {}, []
    for cp, g, ang in rotulos_capa:
        if cp["nombre"].startswith("_"):  # capa auxiliar: sin rótulo ni leyenda
            continue
        por_nombre.setdefault(cp["nombre"], [cp, [], ang])[1].extend(poligonos(g))
    for cp, piezas, ang in por_nombre.values():
        ang = ang_papel(ang) if isinstance(ang, tuple) else ang
        tapa = unary_union(encima + [g_ for g_, _ in mineral]) if (encima or mineral) else None
        if tapa is not None and not cp.get("rotulo"):  # el rótulo con guía apunta a la unidad misma
            piezas = [q for p_ in piezas for q in poligonos(p_.difference(tapa))]
        piezas = sorted(piezas, key=lambda p_: -p_.area)
        if not piezas:
            continue
        pz = piezas[0]
        if cp.get("rotulo"):
            pt = pz.representative_point()
            guia((pt.x, pt.y), pt.y, cp["rotulo"])
            continue
        if c.get("rotulos_en_capa", True):
            pt = polylabel(pz, tolerance=span * 0.002)
            r_ins = pz.exterior.distance(pt) if pz.exterior else 0
            radio = len(cp["nombre"]) * 7.8 * 0.5 * 0.3528 / 2  # mm, medio largo del rótulo
            choca = any(np.hypot((pt.x - q[0]) / mm[0], (pt.y - q[1]) / mm[1]) < radio + q[2] for q in puestos)
            if r_ins * 2 / mm[1] > 2.8 and not choca:  # cabe un renglón de ~8 pt y no pisa a otro rótulo
                puestos.append((pt.x, pt.y, radio))
                ax.text(pt.x, pt.y, cp["nombre"], fontsize=7.8, color="#3d3424", style="italic", ha="center",
                        va="center", rotation=ang, rotation_mode="anchor", zorder=12,
                        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.55))
    # nombre de la caja en su parte más grande libre
    libre = suelo.difference(unary_union(ocupado)) if ocupado else suelo
    piezas = sorted(poligonos(libre.buffer(-span * 0.01)), key=lambda p_: -p_.area)
    if piezas and c.get("rotulo_caja", True):
        pt = polylabel(piezas[0], tolerance=span * 0.003)
        ax.text(pt.x, pt.y, caja["nombre"], fontsize=7.8, color="#4c5640", style="italic", ha="center", va="center",
                zorder=12, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.5))
    for m in c.get("mantos", []):
        if not m.get("rotulo"):
            continue
        xa = m.get("x", [X0, X1])
        xa = [X0 if xa[0] is None else xa[0], X1 if xa[1] is None else xa[1]]
        xm = (xa[0] + xa[1]) / 2 if m.get("lente") else min(X1 - span * 0.1, xa[0] + span * 0.25)
        ym = np.interp(xm, x, topo) - max(m["hasta"] * 0.4, 3)
        if m.get("rotulo_arriba"):
            ax.annotate(m["rotulo"], xy=(xm, ym), xytext=(xm - span * 0.06, ZT - alto_z * 0.064), fontsize=8.3,
                        arrowprops=dict(arrowstyle="-", lw=0.55, color="#555555"), zorder=12)
        else:
            guia((xm, ym), np.interp(xm, x, topo) + alto_z * 0.05, m["rotulo"])
    v_ = c.get("veta")
    if v_:
        for h in c.get("halos", []):
            zr = h["rotulo_z"]
            a = np.interp(zr, [h.get("z_ini", ZB), ztope], h["ancho"])
            guia((np.interp(zr, z, xv) + max(a * 0.6, span * 0.021), zr), zr + alto_z * 0.006, h["rotulo"])
        if cl:
            zr = (cl["z"][0] + cl["z"][1]) / 2 + (cl["z"][1] - cl["z"][0]) * 0.1
            guia((np.interp(zr, z, xv) + 3, zr), zr - alto_z * 0.006, cl["texto"], "#b3261e")
    for cu in c.get("cuerpos", []):
        if cu.get("rotulo"):
            guia((cu["x"], cu["z"]), cu["z"], cu["rotulo"] if isinstance(cu["rotulo"], str) else cu["nombre"],
                 cu.get("color_rotulo", "#222222"))
    eb = c.get("ebullicion")
    if eb:
        ax.plot([X0, X1], [eb["z"], eb["z"]], color="#1f5fa8", lw=0.9, ls=(0, (1, 2)), zorder=12)
        guia((X1, eb["z"]), eb["z"] + alto_z * 0.012, eb["texto"], "#1f5fa8")
    if nf and nf.get("texto"):
        xn = X0 + span * 0.85
        guia((xn, np.interp(xn, x, topo) - nf["prof"]), np.interp(xn, x, topo) - nf["prof"], nf["texto"], "#1f5fa8")
    paso = alto_z * 0.042 * 5.6 / c["figsize"][1]
    repartir(guias, paso, ZB + paso * 0.3, ZT - paso * 0.3)
    for z_txt, _, xy, texto, color in guias:
        ax.annotate(texto, xy=xy, xytext=(XC + span * 0.014, z_txt), fontsize=8.3, color=color, va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.55, color="#555555", shrinkA=2, shrinkB=0),
                    annotation_clip=False, zorder=12)
    for i_, (z_a, z_b, t_) in enumerate(c.get("intervalos", [])):
        xo = X0 - span * (0.185 + 0.05 * i_)
        ax.annotate("", xy=(xo, z_a), xytext=(xo, z_b), arrowprops=dict(arrowstyle="<->", lw=0.8),
                    annotation_clip=False)
        ax.text(xo - span * 0.015, (z_a + z_b) / 2, t_, rotation=90, ha="right", va="center", fontsize=8.3)

    # ---- marco, eje, orientación, franja
    ax.set_xticks([])
    eje = c.get("eje", "cota")
    paso_t = next((p for p in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000) if alto_z / p <= 11), 5000)
    ref = c["topo"].get("cota", ZT) if eje == "profundidad" else ZB
    tk = [v_ for v_ in np.arange(np.ceil(ZB / paso_t) * paso_t, ZT - paso_t * 0.4, paso_t)]
    if eje == "profundidad":
        tk = [ref - d_ for d_ in np.arange(0, ref - ZB + 1, paso_t) if ZB <= ref - d_ <= ZT]
        etiquetas = [f"{ref - v_:,.0f}".replace(",", " ") for v_ in tk]
        rotulo_eje = "Profundidad (m)"
    elif eje == "relativo":
        etiquetas = [f"{v_ - ZB:,.0f}".replace(",", " ") for v_ in tk]
        rotulo_eje = "Altura (m)"
    else:
        etiquetas = [f"{v_:,.0f}".replace(",", " ") for v_ in tk]
        rotulo_eje = "Cota (m s. n. m.)"
    ax.set_yticks(tk)
    ax.set_yticklabels(etiquetas, fontsize=8)
    ax.set_ylabel(rotulo_eje, fontsize=8.5, labelpad=70 if c.get("intervalos") else 8)
    for v_ in tk:
        ax.plot([X0, X1], [v_, v_], color="#bbbbbb", lw=0.4, ls=":", zorder=0.7)
    mix = mtrans.blended_transform_factory(ax.transData, ax.transAxes)
    ax.text(X0 + span * 0.01, 0.985, c["orientacion"][0], fontsize=10, fontweight="bold", va="top", transform=mix,
            zorder=15, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.8))
    ax.text(X1 - span * 0.01, 0.985, c["orientacion"][1], fontsize=10, fontweight="bold", va="top", ha="right",
            transform=mix, zorder=15, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.8))
    for x0_, x1_, txt in c.get("franja", []):
        ax.text((x0_ + x1_) / 2, 1.012, txt, transform=mix, ha="center", va="bottom", fontsize=8, clip_on=False)
        for xs_ in (x0_, x1_):
            if X0 < xs_ < X1:
                ax.plot([xs_, xs_], [1.0, 1.09], transform=mix, color="#555555", lw=0.7, clip_on=False)
    for nombre, s in ax.spines.items():
        s.set_visible(nombre == "left")
        s.set_linewidth(0.8)
    ax.add_patch(Rectangle((X0, ZB), span, alto_z, fill=False, lw=0.9, zorder=14))

    # ---- leyenda (con las tramas reales) y escala gráfica, debajo de la sección
    if v:
        items_ley.insert(0, {"nombre": v.get("nombre", "Veta (potencia exagerada)"), "color": v.get("color", "#3c3c3c"), "trama": None})
    for h in reversed(c.get("halos", [])) if v else []:
        items_ley.append({"nombre": h["nombre"], "color": h["color"], "trama": h["trama"], "borde": h["borde"],
                          "alpha": h["alpha"]})
    for nom, (col, tr) in nombres_cuerpos.items():
        items_ley.append({"nombre": nom, "color": col, "trama": tr})
    vistos_l, ley = set(), []
    for it in items_ley:
        if it["nombre"] not in vistos_l:
            vistos_l.add(it["nombre"])
            ley.append(it)
    # texto de la leyenda envuelto al ancho de su columna (Calibri 7,3 pt ≈ 1,2 mm por carácter)
    col_mm = c["figsize"][0] * 25.4 * 0.8 / ncol - 13
    for it in ley:
        it["texto"] = envolver(it["nombre"], max(int(col_mm / 1.2), 12))
    filas = [max(nl(it["texto"]) for it in ley[i:i + ncol]) for i in range(0, len(ley), ncol)]
    altos = [0.17 + 0.115 * (f_ - 1) for f_ in filas]
    alto_ley = sum(altos) + 0.42 + 0.06 * len(filas)
    W_in, H_in = c["figsize"]
    fig.set_size_inches(W_in, H_in + alto_ley)
    fig.subplots_adjust(bottom=(alto_ley + 0.12) / (H_in + alto_ley))
    fig.tight_layout(rect=(0, (alto_ley + 0.05) / (H_in + alto_ley), 1, 1))
    pos = ax.get_position()
    axl = fig.add_axes([pos.x0, 0.01, pos.width, (alto_ley - 0.02) / (H_in + alto_ley)])
    axl.set_xlim(0, 1); axl.set_ylim(0, 1); axl.axis("off")
    mm = escala_mm(ax)
    mml = escala_mm(axl)
    # escala gráfica
    e = c.get("escala_m")
    if e:
        largo = e / mm[0] * mml[0]
        y0 = 1 - 0.30 / alto_ley
        for j in range(4):
            axl.add_patch(Rectangle((j * largo / 4, y0), largo / 4, 0.07 / alto_ley,
                                    facecolor="k" if j % 2 == 0 else "w", edgecolor="k", lw=0.5))
        axl.text(0, y0 + 0.1 / alto_ley, "0", fontsize=7, ha="center")
        axl.text(largo, y0 + 0.1 / alto_ley, f"{e} m", fontsize=7, ha="center")
        if c.get("nota_escala"):
            axl.text(largo + 0.03, y0, c["nota_escala"], fontsize=7, va="bottom", color="#555555")
    caja_w, caja_h = 9 * mml[0], 3.6 * mml[1]
    techo_fila = [1 - 0.42 / alto_ley - sum(a_ + 0.06 for a_ in altos[:f_]) / alto_ley for f_ in range(len(filas))]
    for i, it in enumerate(ley):
        fil, col = divmod(i, ncol)
        x0_ = col / ncol
        fila_h = (altos[fil] + 0.06) / alto_ley
        y0_ = techo_fila[fil] - fila_h / 2 - caja_h / 2
        if "linea" in it:
            axl.plot([x0_, x0_ + caja_w], [y0_ + caja_h / 2] * 2, **it["linea"])
        else:
            hatch = None if es_trama(it.get("trama")) else it.get("trama")
            r = Rectangle((x0_, y0_), caja_w, caja_h, facecolor=it["color"], edgecolor=it.get("borde", "#555555"),
                          lw=0.6, hatch=hatch, alpha=it.get("alpha", 1))
            axl.add_patch(r)
            if es_trama(it.get("trama")):
                trama(axl, it["trama"], r, mml, rng, ang=ang_papel(it.get("ang", 0), mm), zorder=3,
                      extension=mtrans.Bbox([[x0_, y0_], [x0_ + caja_w, y0_ + caja_h]]))
        axl.text(x0_ + caja_w + 1.5 * mml[0], y0_ + caja_h / 2, it["texto"], fontsize=7.3, va="center",
                 linespacing=1.0)
    # tramas de la sección, ya con la escala definitiva del papel
    for ax_, nombre, p, ang, ct, esc, zo in pend:
        trama(ax_, nombre, p, mm, rng, ang=ang_papel(ang, mm), color=ct, escala=esc, zorder=zo)
    guardar(fig, salida, c["dpi"])
    plt.close(fig)


# ------------------------------------------------------------------ columna estratigráfica
COLUMNA_ARCATA = {
    "semilla": 11,
    "figsize": [5.9, 5.4], "dpi": 240,
    # de base a techo, SIEMPRE ordenadas por edad (la más antigua abajo): espesor dibujado (m), nombre, edad,
    # litología, resistencia 0-1, color, trama, rótulo de espesor y, opcional, {"buz": grados, "cortada": true}
    "unidades": [
        [430, "Fm. Alpabamba", "Mioceno medio\n10–13 Ma", "Andesitas, dacitas, tobas y brechas", 0.72, "#dde8cf",
         "brecha_volcanica", "430 m"],
        [600, "Secuencia Arcata\n(Fm. Ichucollo*)", "Mioceno tardío\n6,5–5,4 Ma",
         "Flujos andesíticos porfiríticos,\nignimbritas en la base.\nCAJA DE LAS VETAS", 0.82, "#c9dcb8", "andesita",
         "500–700 m"],
        [150, "Volc. Sencca", "Plioceno", "Tobas dacíticas a riolíticas", 0.5, "#efe6d2", "toba", "150 m"],
        [660, "Gr. Barroso", "Plioceno sup.–\nPleistoceno", "Inferior: lavas y tufos.\nSuperior: conos lávicos\n"
         "andesítico-basálticos.\nFrescos (posminerales)", 0.9, "#b9c4d4", "lava_fresca", "310 + 350 m"],
        [180, "Cuaternario", "Pleistoceno–\nreciente", "Morrenas y fluvioglaciares;\naluviales y bofedales", 0.6,
         "#f3ecd6", "conglomerado", "120 + 60 m"],
    ],
    "resaltar": 1,  # índice de la unidad huésped (rótulo en verde y negrita)
    # base de la unidad i: [i, texto, tipo]; tipo = erosional (ondulada), angular (ondulada gruesa),
    # inconformidad (ondulada gruesa, sobre ígneo o metamórfico) o paraconformidad (recta discontinua)
    "discordancias": [[1, "discordancia"], [2, "discordancia angular", "angular"], [3, "discordancia erosional"]],
    "intrusivos": [{"texto": "Dique riolítico 5,7 Ma", "x": 0.25, "z": [430, 990], "rotulo_z": 965}],
    "vetas": [{"texto": "Vetas de Ag–Au ≈ 5,4 Ma", "x": 0.55, "z": [430, 950], "rotulo_z": 885}],
    "notas": [{"z": 560, "texto": "* Nombre en discusión: «Gr. Tacaza» en las tesis\n"
                                  "de la mina; Fm. Ichucollo en Salas et al. (2002)"}],
    "escala_m": 200,
}
COLUMNA_VACIA = {"semilla": 11, "figsize": [5.9, 7.0], "dpi": 240, "unidades": [], "resaltar": None,
                 "discordancias": [], "intrusivos": [], "vetas": [], "notas": [], "escala_m": 100}
# edades: [[[i_desde, i_hasta, "Paleozoico"], ...], [[...periodos...]]]  barras a la izquierda, de afuera hacia adentro


def edad_max(texto):
    """Mayor número de la edad si el rótulo trae «Ma», o None si no hay cifra."""
    t = re.sub(r"(?<=\d)[  ](?=\d{3}\b)", "", str(texto))  # 1 100 Ma -> 1100 Ma
    if not re.search(r"\d\s*Ma", t):
        return None
    nums = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:,\d+)?", t)]
    return max(nums) if nums else None


def revisar_orden(unidades):
    """Avisa si una unidad más antigua quedó encima de una más joven (inversión estratigráfica)."""
    previa = None
    for u in unidades:
        e = edad_max(u[2])
        if e is not None and previa is not None and e > previa[1] + 1e-9:
            print(f"AVISO: «{u[1].splitlines()[0]}» ({e} Ma) está encima de «{previa[0]}» ({previa[1]} Ma): "
                  "inversión estratigráfica; revisa el orden o márcalo como contacto por falla.")
        if e is not None:
            previa = (u[1].splitlines()[0], e)


def columna(cfg_usuario, salida):
    cfg_usuario = cfg_usuario or {}
    base = COLUMNA_VACIA if cfg_usuario.get("plantilla") == "vacia" else COLUMNA_ARCATA
    c = fusionar(base, cfg_usuario)
    U = c["unidades"]
    revisar_orden(U)
    rng = np.random.default_rng(c["semilla"])
    extra = [u[8] if len(u) > 8 else {} for u in U]
    bases, b = [], 0.0
    for u in U:
        bases.append(b); b += u[0]
    total = b
    barras = c.get("edades") or []
    # anchos de las columnas de texto según lo que llevan (Calibri ≈ 0,5 em por carácter)
    largo = lambda textos, fs: max([len(l) for t_ in textos for l in str(t_).split("\n")] or [0]) * fs * 0.52
    w_uni, w_edad = largo([u[1] for u in U], 8.6), largo([u[2] for u in U], 7.8)
    w_lit = largo([u[3] for u in U] + [n_["texto"] for n_ in c.get("notas", [])], 8.2)
    w_esp = largo([u[7] for u in U], 7.8)
    X_UNI, X_LIT = -0.06, 1.05
    x_izq, x_der = -2.2, 3.1
    for _ in range(3):  # el ancho de los textos en datos depende del rango x, que depende de los textos
        u_pt = (x_der - x_izq) / (c["figsize"][0] * 0.96 * 72)
        X_EDAD = X_UNI - w_uni * u_pt - 0.15
        x_izq = X_EDAD - w_edad * u_pt - 0.12 - (0.34 * len(barras) + 0.05 if barras else 0.35)
        X_ESP = X_LIT + (w_lit + w_esp) * u_pt + 0.2
        x_der = X_ESP + 0.08 + (0.45 if barras else 0)
    fig, ax = plt.subplots(figsize=c["figsize"], dpi=c["dpi"])
    ax.set_xlim(x_izq, x_der); ax.set_ylim(-20, total + 80)
    ax.axis("off")
    pt_dato = (total + 100) / (c["figsize"][1] * 0.92 * 72)  # unidades de datos por punto tipográfico
    paso = 8.2 * 1.22 * pt_dato
    mm = escala_mm(ax)
    pend = []
    tope_prev = None
    filas_der = []
    filas_izq = []
    for k, u in enumerate(U):
        esp, nom, edad, lit, ancho, col, sim, esp_txt = u[:8]
        b, t = bases[k], bases[k] + esp
        zz = np.linspace(b, t, 40)
        der = ancho + rugoso(rng, 40, 0.025, 6)
        xs = np.linspace(0, 1, 60)
        base_c = tope_prev if tope_prev is not None else np.full(60, b)
        tope = t + (rugoso(rng, 60, min(9, esp * 0.12), 6) if k < len(U) - 1 else np.zeros(60))
        tope_prev = tope
        ib = xs <= ancho
        px = np.r_[xs[ib], der, xs[::-1][xs[::-1] <= ancho]]
        pz = np.r_[base_c[ib], zz, tope[::-1][xs[::-1] <= ancho]]
        p = ax.fill(px, pz, facecolor=col, edgecolor="#3a3a3a", lw=0.9, zorder=1)[0]
        pend.append((sim, p, extra[k].get("buz", 0), extra[k].get("color_trama")))
        if extra[k].get("cortada"):
            zm_ = (b + t) / 2
            xx = np.linspace(-0.04, ancho + 0.06, 30)
            zig = np.where(np.arange(30) % 2, 1, -1) * min(4, esp * 0.05)
            sep = min(9, esp * 0.12)
            ax.fill_between(xx, zm_ - sep / 2 + zig, zm_ + sep / 2 + zig, color="white", zorder=4, lw=0)
            for s_ in (-1, 1):
                ax.plot(xx, zm_ + s_ * sep / 2 + zig, color="#3a3a3a", lw=0.8, zorder=4.1)
        zm = (b + t) / 2
        res = k == c.get("resaltar")
        filas_izq.append([zm, max(nl(nom), nl(edad), nl(esp_txt)), zm, nom, edad, esp_txt])
        filas_der.append([zm, nl(lit), ("lit", zm, ancho), lit, "#1f4d2a" if res else "#222222",
                          "bold" if res else "normal", "normal", 8.2])
    for d in c.get("discordancias", []):
        i_, txt = d[0], d[1]
        tipo = d[2] if len(d) > 2 else "erosional"
        zc = bases[i_]
        xx = np.linspace(-0.03, 1.0, 120)
        if tipo == "paraconformidad":
            ax.plot(xx, np.full(120, zc), color="#8b1e1e", lw=1.0, ls=(0, (5, 3)), zorder=3)
        else:
            amp = min(6, (U[i_][0] + U[i_ - 1][0]) * 0.05)
            ax.plot(xx, zc + amp * np.sin(xx * 45), color="#8b1e1e", lw=1.8 if tipo in ("angular", "inconformidad") else 1.0,
                    zorder=3)
        filas_der.append([zc, nl(txt), ("disc", zc, 1.0), txt, "#8b1e1e", "normal", "italic", 7.4])
    for d in c.get("intrusivos", []):
        dz = np.linspace(*d["z"], 40)
        dx = d["x"] + 0.04 * np.sin(dz / 60) + rugoso(rng, 40, 0.01, 6)
        ax.fill_betweenx(dz, dx, dx + 0.07, facecolor="#f2c6c6", edgecolor="#9b4b4b", lw=0.6, hatch="++", zorder=4)
        filas_der.append([d["rotulo_z"], nl(d["texto"]), ("pt", d["x"] + 0.05, d["rotulo_z"]), d["texto"], "#7a2e2e",
                          "normal", "normal", 7.6])
    for v in c.get("vetas", []):
        vz = np.linspace(*v["z"], 40)
        vx = v["x"] + 0.03 * np.sin(vz / 40) + rugoso(rng, 40, 0.012, 6)
        ax.plot(vx, vz, color="#b3261e", lw=2.2, zorder=5)
        filas_der.append([v["rotulo_z"], nl(v["texto"]), ("pt", v["x"] + 0.02, v["rotulo_z"]), v["texto"], "#b3261e",
                          "normal", "normal", 7.6])
    for nt in c.get("notas", []):
        filas_der.append([nt["z"], nl(nt["texto"]), None, nt["texto"], "#555555", "normal", "italic", 6.8])
    # rótulos de la derecha repartidos; guía al contacto o a la unidad cuando se movieron
    for f in filas_der:
        f.append(f[0])
    repartir(filas_der, paso, 0, total + 20)
    for z_txt, _, ancla, texto, color, peso, estilo, fs, z0 in filas_der:
        ax.text(X_LIT, z_txt, texto, ha="left", va="center", fontsize=fs, color=color, fontweight=peso, style=estilo,
                zorder=6)
        if ancla is None:
            continue
        if ancla[0] == "pt":
            ax.plot([ancla[1], X_LIT - 0.03], [ancla[2], z_txt], color=color, lw=0.5, zorder=5)
        elif abs(z_txt - z0) > paso * 0.3 or ancla[0] == "disc":
            x_a = 1.0 if ancla[0] == "disc" else ancla[2] + 0.02
            if ancla[0] == "disc" and abs(z_txt - z0) <= paso * 0.3:
                continue
            ax.plot([x_a, X_LIT - 0.03], [ancla[1], z_txt], color=color, lw=0.5, zorder=5)
    # rótulos de la izquierda (unidad, edad, espesor) en la misma fila
    repartir(filas_izq, paso * 1.0, 0, total + 20)
    for z_txt, _, zm, nom, edad, esp_txt in filas_izq:
        ax.text(X_UNI, z_txt, nom, ha="right", va="center", fontsize=8.6, fontweight="bold")
        ax.text(X_EDAD, z_txt, edad, ha="right", va="center", fontsize=7.8, color="#555555")
        ax.text(X_ESP, z_txt, esp_txt, ha="right", va="center", fontsize=7.8, color="#555555")
        if abs(z_txt - zm) > paso * 0.3:
            ax.plot([X_UNI + 0.01, -0.01], [z_txt, zm], color="#777777", lw=0.5)
    # barras de edad (eras, periodos)
    for j, col_b in enumerate(barras):
        xb0 = x_izq + 0.1 + 0.34 * j
        for i0, i1, txt in col_b:
            z0_, z1_ = bases[i0], bases[i1] + U[i1][0]
            ax.add_patch(Rectangle((xb0, z0_), 0.3, z1_ - z0_, facecolor="#f4f4f4", edgecolor="#555555", lw=0.6))
            fs = min(7.4, (z1_ - z0_) / pt_dato / max(len(txt) * 0.52, 1) * 0.9)
            if fs >= 5:  # si no cabe ni a 5 pt, la barra queda sin texto
                ax.text(xb0 + 0.15, (z0_ + z1_) / 2, txt, rotation=90, ha="center", va="center", fontsize=fs)
    e = c.get("escala_m")
    if e:
        xe = x_der - 0.12 if barras else x_izq + 0.25
        ax.plot([xe, xe], [0, e], color="k", lw=1.2)
        for v_ in (0, e / 2, e):
            ax.plot([xe - 0.03, xe + 0.03], [v_, v_], color="k", lw=1)
        ax.text(xe - 0.07, e / 2, f"{e} m", fontsize=7.5, rotation=90, ha="right", va="center")
        if any(x_.get("cortada") for x_ in extra):
            ax.text(xe - 0.07, e + 8, "≈ tramos\ncortados", fontsize=6.5, ha="center", va="bottom", color="#555555")
    zh = total + 35
    ax.text(X_UNI, zh, "Unidad", fontsize=8, fontweight="bold", ha="right")
    ax.text(X_EDAD, zh, "Edad", fontsize=8, fontweight="bold", ha="right", color="#555555")
    ax.text(X_LIT, zh, "Litología", fontsize=8, fontweight="bold")
    ax.text(X_ESP, zh, "Espesor", fontsize=8, fontweight="bold", ha="right", color="#555555")
    fig.tight_layout()
    mm = escala_mm(ax)
    for sim, p, buz, ct in pend:
        trama(ax, sim, p, mm, rng, ang=buz, color=ct, zorder=2)
    guardar(fig, salida, c["dpi"])
    plt.close(fig)


# ------------------------------------------------------------------ muestrario de tramas
def muestrario(salida):
    nombres = list(TRAMAS)
    ncol = 6
    filas = int(np.ceil(len(nombres) / ncol))
    fig, ax = plt.subplots(figsize=(8, 1.25 * filas), dpi=240)
    ax.set_xlim(0, ncol); ax.set_ylim(0, filas); ax.axis("off")
    fig.tight_layout()
    mm = escala_mm(ax)
    rng = np.random.default_rng(1)
    for i, nom in enumerate(nombres):
        f, c_ = divmod(i, ncol)
        y = filas - f - 1
        r = Rectangle((c_ + 0.08, y + 0.3), 0.84, 0.62, facecolor="white", edgecolor="#333333", lw=0.6)
        ax.add_patch(r)
        trama(ax, nom, r, mm, rng, zorder=3)
        ax.text(c_ + 0.5, y + 0.14, nom, ha="center", fontsize=8)
    guardar(fig, salida, 240)
    plt.close(fig)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    orden = sys.argv[1]
    if orden == "ejemplo":
        os.makedirs(sys.argv[2], exist_ok=True)
        perfil({}, os.path.join(sys.argv[2], "perfil_arcata.png"))
        columna({}, os.path.join(sys.argv[2], "columna_arcata.png"))
    elif orden == "tramas":
        muestrario(sys.argv[2])
    else:
        cfg = json.load(open(sys.argv[2], encoding="utf-8"))
        {"perfil": perfil, "columna": columna}[orden](cfg, sys.argv[3])
    print("ok")
