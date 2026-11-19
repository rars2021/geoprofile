---
name: geoprofile
description: Dibuja perfiles y secciones geológicas, cortes de alteración alrededor de vetas, modelos de yacimiento (pórfido, skarn, epitermal, hot-spring) y columnas estratigráficas con aspecto de informe real (contactos irregulares, tramas litológicas FGDC que siguen el buzamiento, secuencias truncadas por discordancias, bloques fallados, intrusivos con aureolas de alteración, halos con trama, veta con pinch & swell y ramales, lentes de mena, perfil supérgeno, cotas, orientación, escala gráfica, leyenda con tramas y rótulos con líneas guía), en PNG listo para una lámina o un informe. Úsala cuando pidan un perfil geológico, una sección, un corte de alteración, un modelo de yacimiento, una columna estratigráfica o «geoprofile», o cuando una figura de geología «se ve demasiado limpia», «muy recta» o «irreal» para un curso o un informe de geología.
---

# geoprofile

Figuras de geología con aspecto de informe real, no de diagrama escolar. La primera versión, un corte de alteración
de la mina Arcata (Perú) para una exposición de curso, se rehízo porque los rectángulos y trapecios lisos se veían
irreales: de ahí la regla de que nada va recto ni liso y de copiar la presentación de figuras publicadas.

La versión 0.2 se puso a prueba contra 7 figuras públicas del USGS y del NPS (`pruebas/`). La primera ronda salió mal
(columna sin tramas reales, rótulos encimados, sección sin discordancias); de esos fallos salen el modelo de
secuencias y fallas, las tramas FGDC y las aureolas.

## Cómo se usa

```bash
python scripts\geoprofile.py ejemplo carpeta                   # perfil y columna de Arcata
python scripts\geoprofile.py perfil  config.json salida.png    # sección, corte de alteración o modelo de yacimiento
python scripts\geoprofile.py columna config.json salida.png    # columna estratigráfica
python scripts\geoprofile.py tramas  muestrario.png            # las 23 tramas litológicas
```

Requiere numpy, matplotlib, shapely y Pillow. El `config.json` lleva solo lo que cambia. Sin `plantilla` hereda el
ejemplo de Arcata (`PERFIL_ARCATA`, `COLUMNA_ARCATA`); con `"plantilla": "vacia"` parte de una figura en blanco, que es
lo que conviene para cualquier yacimiento que no sea Arcata. Las claves están comentadas al inicio del script, y hay
siete configs completos que sirven de modelo en `pruebas/configs/`.

**Siempre** abre el PNG con Read después de generarlo y míralo: rótulos que se cruzan, un halo que tapa una capa o un
lente mal ubicado son lo que más falla. Cambia la `semilla` si un contacto quedó feo.

### Qué se puede dibujar (perfil)

| Clave | Para qué |
|---|---|
| `topo` (`cota`, `ondulacion`, `pendiente`) o `topo.puntos` | Topografía; con puntos se dibujan cañones, conos y escarpes |
| `caja` | Roca que rellena todo (con `trama` y `ang` para la foliación) |
| `secuencias` | Paquetes de capas de la más antigua a la más joven; `base` es la discordancia sobre la que se apoya cada una y trunca a las anteriores; `pendiente` inclina capas y tramas |
| `fallas` | Varias; `salto` desplaza el bloque derecho, `sella` = índice de la secuencia que la tapa, `posmineral` también mueve veta y halos |
| `intrusivos` | Stocks y plutones que cortan todo; `aureolas` = halos concéntricos (`distancia` > 0 afuera, < 0 núcleo) |
| `veta`, `halos`, `clavo` | Corte de alteración epitermal; halos con `z_ini` y `z_fin`; `veta` admite `nombre`, `color`, `estilo_ramales`, o `null` |
| `cuerpos` | Lentes de mena, brechas, diques; uno sin `nombre` hereda estilo del anterior |
| `mantos` | Capas que siguen la topografía: cobertura, morrena, sínter, casquete lixiviado, enriquecimiento |
| `nivel_freatico`, `ebullicion`, `intervalos`, `franja` | Líneas de referencia, intervalos metálicos al margen y franja de alteración encima |
| `eje` | `cota` (m s. n. m.), `profundidad` o `relativo` (cuando la referencia no tiene cotas, no las inventes) |

Una capa cuyo nombre empieza con `_` no sale en leyenda ni rótulos (franjas auxiliares).

### Columna

Cada unidad: `[espesor dibujado, nombre, edad, litología, resistencia 0-1, color, trama, espesor real]` y, opcional,
`{"buz": grados, "cortada": true}`. `discordancias` lleva tipo (`erosional`, `angular`, `inconformidad`,
`paraconformidad`); `edades` dibuja barras de era y periodo. Los rótulos se reparten solos y llevan guía si se movieron.

## Antes de dibujar: mira figuras reales

En `references/img/publicas/` están las figuras de dominio público que sirvieron de modelo. Antes de dibujar un
yacimiento concreto, busca figuras publicadas de ese mismo yacimiento (tesis, boletines del servicio geológico,
informes técnicos) y copia la estructura de presentación, no los colores. Las figuras que no se pueden redistribuir
van en `references/img/privadas/`, que git ignora.

| Archivo | Qué enseña |
|---|---|
| `publicas\fgdc37_p1-3.png` | Estándar FGDC (USGS): tramas litológicas sedimentarias, metamórficas e ígneas |
| `publicas\ref1_seccion_grand_canyon_nps2021.jpg` | Discordancias, bloques fallados y sellados, capas horizontales encima |
| `publicas\ref2_fay_ace_verna_usgs_ofr81-166.png` | Lentes de mena a lo largo de una falla |
| `publicas\ref3_columna_grand_canyon_usgs.jpg` | Columna con perfil de meteorización y barras de edad |
| `publicas\ref4` a `ref8` (USGS Bulletin 1693) | Modelos de Creede, pórfido Cu, hot-spring Au-Ag, skarn Cu y pórfido Cu-Mo |

## Reglas de dibujo (lo que se aprendió)

**Nada recto ni liso.** Todo contacto, borde de halo, topografía y veta lleva `rugoso()`: camino aleatorio con media
móvil, no seno ni ruido blanco. Las capas buzan; las vetas tienen 75-85° y cambian de grosor (pinch & swell).

**Tramas como en el estándar FGDC.** Caliza en ladrillo, dolomía en ladrillo oblicuo, arenisca en puntos, lutita en
guiones, esquisto ondulado, granito en trazos sueltos, pórfido en «+», andesita en «v». Van en filas escalonadas con
algo de desorden (así las dibuja el USGS) y **giran con el buzamiento** de su secuencia. La leyenda usa las mismas
tramas. Cada halo tiene color **y** trama para que se lea impreso en gris.

**Corte de alteración (epitermal de veta).** De afuera hacia adentro: propilítica (ancha, se abre hacia arriba),
argílica (embudo sobre el nivel de ebullición, nunca con base plana), sílice-adularia pegada a la veta, veta. Clavo en
el horizonte de ebullición con brecha. Ramales hacia la superficie. Una zona que no llega a la superficie lleva `z_fin`.

**Pórfido y skarn.** Alteración en `aureolas` del intrusivo: potásica al centro (distancia negativa), fílica,
propilítica afuera; argílica avanzada en el techo. Perfil supérgeno con `mantos` y `nivel_freatico`.

**Coherencia geológica.** Una falla que no corta a la secuencia de arriba se marca con `sella`. Si desplaza capas y no
halos, es premineral; si desplaza halos, `posmineral`. La cobertura posmineral va fresca y tapa los halos.

**Marco de sección.** Eje de cotas reales (miles con espacio) solo si la fuente las tiene; si no, `eje: relativo`.
Orientación arriba, rejilla punteada tenue, marco solo alrededor de la sección, rótulos en columna a la derecha con
guías, leyenda y escala gráfica debajo. «Potencia exagerada» si la veta se dibujó más gruesa que la escala.

**Columna estratigráfica.** El ancho sigue la resistencia (perfil de meteorización); discordancias según su tipo;
tramos `cortada` cuando el espesor dibujado no es el real (la escala avisa «≈ tramos cortados»).

**Orden por edad, siempre.** Error real de la primera versión: la Fm. Alpabamba (10–13 Ma) quedó encima de la caja de
Arcata (~6 Ma). Ordena por edad radiométrica, no por el nombre de la tesis; si nombre y edad chocan, manda la edad y
el nombre va con asterisco y nota. `columna()` avisa si encuentra una inversión; si es real (falla inversa), dibújala
como contacto por falla.

**Tamaño en la lámina.** La figura ocupa al menos la mitad del ancho. Si el PNG se va a reducir, achica `figsize` en vez
de bajar las letras. Pie de figura: «Perfil interpretativo [...], elaborado sobre [fuente]», nunca «esquema».

## Trampas

- Con Calibri, el texto de menos de ~17 px desaparece (matplotlib usa los mapas de bits incrustados de la fuente). El
  script dibuja siempre a 220 dpi como mínimo y reduce la imagen si se pide menos; no lo quites.
- En Windows, editar el script con heredoc por consola daña acentos y barras invertidas. Usa Edit o Write, o un
  script de Python en un archivo.
- Las tramas se dibujan al final, cuando ya se conoce la escala del papel; si agregas un elemento con trama, mételo
  en la lista `pend`, no lo dibujes antes de `tight_layout`.
- Un `hatch` de matplotlib (`"//"`, `".."`) sigue valiendo donde se espera una trama; un nombre de `TRAMAS` usa la trama FGDC.

## Fuentes de las cifras del ejemplo (Arcata)

Horizonte de mena de 240-300 m con tope a 4 600-4 450 m: Valdivia (2017) y Vera (2017). Edades: Condori (2020),
Valdivia (2017), Candiotti et al. (1990) en Acosta et al. (2009). Fm. Ichucollo: Salas et al. (2002). Espesores:
Vera (2017, Lámina 01). El modelo de halos sigue a Buchanan (1981).
