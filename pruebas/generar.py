# -*- coding: utf-8 -*-
"""Repite las pruebas: dibuja cada config con geoprofile y arma la comparación «referencia vs geoprofile».

    python pruebas/generar.py

Lee pruebas/casos.json y pruebas/configs/*.json; escribe pruebas/salidas/ y pruebas/comparaciones/.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent / ".claude" / "skills" / "geoprofile"
REFERENCIAS = SKILL / "references" / "img" / "publicas"
sys.path.insert(0, str(SKILL / "scripts"))
from geoprofile import columna, muestrario, perfil  # noqa: E402

CASOS = json.loads((AQUI / "casos.json").read_text(encoding="utf-8"))


def comparar(caso):
    ref = Image.open(REFERENCIAS / caso["referencia"]).convert("RGB")
    gen = Image.open(AQUI / "salidas" / (caso["id"] + ".png")).convert("RGB")
    fig = plt.figure(figsize=(14, 8.6), dpi=170)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.2], hspace=0.08, wspace=0.04,
                          left=0.02, right=0.98, top=0.93, bottom=0.02)
    for k, (im, titulo) in enumerate([(ref, "Referencia"), (gen, "geoprofile")]):
        ax = fig.add_subplot(gs[0, k])
        ax.imshow(im)
        ax.set_title(titulo, fontsize=13, fontweight="bold", loc="left")
        ax.axis("off")
    fig.suptitle(caso["titulo"], fontsize=14, x=0.02, ha="left")
    nota = fig.add_subplot(gs[1, :])
    nota.axis("off")
    lineas = [f"Fuente: {caso['fuente']} — {caso['licencia']}"]
    lineas += [f"+ {t}" for t in caso["bien"]] + [f"– {t}" for t in caso["falla"]]
    nota.text(0, 1, "\n".join(lineas), va="top", fontsize=10, linespacing=1.35)
    fig.savefig(AQUI / "comparaciones" / (caso["id"] + "_comparacion.png"))
    plt.close(fig)


if __name__ == "__main__":
    for d in ("salidas", "comparaciones"):
        (AQUI / d).mkdir(exist_ok=True)
    for caso in CASOS:
        cfg = json.loads((AQUI / "configs" / (caso["id"] + ".json")).read_text(encoding="utf-8"))
        {"perfil": perfil, "columna": columna}[caso["tipo"]](cfg, str(AQUI / "salidas" / (caso["id"] + ".png")))
        comparar(caso)
        print("ok", caso["id"])
    muestrario(str(AQUI / "salidas" / "muestrario_tramas.png"))
    print("ok muestrario")
