# Changelog

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con SemVer.

## [0.2.0] - 2026-11-19

### Añadido
- 23 tramas litológicas al estilo del estándar FGDC, que giran con el buzamiento, y un muestrario (`tramas`).
- Secuencias de capas con discordancias que truncan, varias fallas por bloques con `sella` y `posmineral`.
- Intrusivos con aureolas de alteración concéntricas; cuerpos (lentes, brechas, diques); mantos que siguen la
  topografía; nivel freático; franja de alteración; topografía por puntos; eje relativo o en profundidad.
- Columna con barras de edad, tramos cortados y tipos de discordancia.
- Siete pruebas contra figuras del USGS y del NPS (`pruebas/`).

### Cambiado
- Leyenda y escala gráfica debajo de la sección, con las mismas tramas que la figura.
- Los rótulos de la columna se reparten solos y llevan guía cuando se mueven.
- `"plantilla": "vacia"` para no heredar el ejemplo de Arcata.

### Arreglado
- Texto que desaparecía al guardar con pocos dpi.
- Halos y veta que terminaban en un techo plano bajo la topografía.
- Contactos con «dientes» en el salto de falla.
- Rótulos encimados en unidades delgadas y rótulos fuera del marco.

## [0.1.0] - 2026-11-16

### Añadido
- Primera versión: corte de alteración epitermal y columna estratigráfica de la mina Arcata.
