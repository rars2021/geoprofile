# Mejoras de geoprofile

## Hechas en la versión 0.2, a partir de la primera ronda de pruebas

| Fallo encontrado | Arreglo |
|---|---|
| Columna sin símbolos de arenisca, lutita, dolomía ni esquisto | 23 tramas al estilo FGDC (`scripts/tramas.py`), que giran con el buzamiento |
| Rótulos de discordancia encimados sobre la litología | Los rótulos de la columna se reparten solos y llevan guía cuando se mueven |
| Edad y nombre de la unidad pegados en nombres largos | Ancho de las columnas de texto calculado según lo que llevan |
| Sección con una sola capa y una sola falla, sin discordancias | `secuencias` con discordancias que truncan, varias `fallas` por bloques, `sella` |
| El salto de falla dejaba «dientes» en los contactos | Las capas se cortan por el plano de falla (polígonos con shapely) |
| La veta no se podía quitar | `veta: null`; `nombre`, `color` y estilo de ramales configurables |
| Halos que solo se abren hacia arriba; techo plano bajo la topografía | `z_fin` para cerrar zonas; halos y veta llegan a la topografía |
| Mena siempre continua | `cuerpos`: lentes, brechas y diques con trama |
| Alteración solo alrededor de vetas | `aureolas` concéntricas de intrusivos (núcleo potásico, fílica, propilítica) |
| Rótulos fuera del marco o sobre la escala | Rótulos dentro de la capa solo si caben y no pisan a otro; leyenda y escala debajo |
| Eje siempre en m s. n. m. | `eje: relativo` o `profundidad` |
| Texto que desaparece por debajo de ~17 px (Calibri) | Siempre se dibuja a 220 dpi como mínimo y se reduce después |
| Los configs heredaban todo el ejemplo de Arcata | `"plantilla": "vacia"` |
| Leyenda con cuadros de hatch que no coincidían con la figura | Leyenda con las mismas tramas, en columnas, con texto envuelto |

## Propuestas pendientes

Ordenadas por lo que más se nota en las comparaciones.

1. **Pliegues y arrastre**: las capas solo buzan en un sentido; no se doblan contra un intrusivo ni forman
   anticlinales (pruebas 5 y 7).
2. **Variación lateral de espesor**: cuñas y acuñamientos de capas (Temple Butte, Surprise Canyon en la prueba 1).
3. **Sembrar lentes a lo largo de una estructura**: hoy cada lente se ubica a mano (prueba 2).
4. **Trama de stockwork** para el pórfido y vetillas de bajo ángulo para el hot-spring (pruebas 5 y 6).
5. **Rótulos con menos cruces**: el reparto vertical evita encimarse, pero las guías se cruzan cuando hay muchos
   elementos a distintas alturas (pruebas 5 y 6).
6. **Columna**: números en círculo y encabezado por conjuntos, como en la figura del USGS (prueba 3).
7. **Minerales dentro de la veta** como bandas internas, en lugar de halos laterales (prueba 4).
