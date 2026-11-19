# Fuentes de las figuras de referencia

Las figuras están en `.claude/skills/geoprofile/references/img/publicas/`. Todas son obras del Gobierno de EE. UU.
(USGS o NPS) en dominio público. Se copiaron sin cambios, salvo el recorte de página en la figura 2, la página del
estándar FGDC pasada a PNG y la conversión de GIF a PNG en las del Boletín 1693.

| Archivo | Figura | Fuente | Licencia |
|---|---|---|---|
| `ref1_seccion_grand_canyon_nps2021.jpg` | Sección de las tres series de rocas del Grand Canyon | Karlstrom, K., Crossey, L., Mathis, A. y Bowman, C. (2021). *Telling time at Grand Canyon National Park: 2020 update.* Natural Resource Report NPS/GRCA/NRR—2021/2246. National Park Service. Copia en Wikimedia Commons: «Grand Canyon Uncomformities and Missing Time.jpg» | Dominio público (NPS), etiqueta PD-USGov en Commons |
| `ref2_fay_ace_verna_usgs_ofr81-166.png` | Fig. 24, sección compuesta de los cuerpos Verna y Fay, mina Eldorado | Nash, J. T. (1981). *Geology and genesis of major world hardrock uranium deposits — an overview.* USGS Open-File Report 81-166, p. 63. https://pubs.usgs.gov/of/1981/0166/ | Dominio público (USGS). La figura dice «modificada de Little et al. (1972)»: el redibujo es del USGS |
| `ref3_columna_grand_canyon_usgs.jpg` | Columna estratigráfica de las rocas del Grand Canyon | USGS, galería de imágenes: «Stratigraphic column of Grand Canyon rocks». https://www.usgs.gov/media/images/stratigraphic-column-grand-canyon-rocks | Dominio público (la página lo indica en «Sources/Usage») |
| `ref4_creede_usgs_b1693_fig106.png` | Fig. 106, veta epitermal tipo Creede | Mosier, D. L., Sato, T., Page, N. J., Singer, D. A. y Berger, B. R. (1986). Descriptive model of Creede epithermal veins. En Cox, D. P. y Singer, D. A. (eds.), *Mineral Deposit Models*, USGS Bulletin 1693. https://pubs.usgs.gov/bul/b1693/ | Dominio público (USGS) |
| `ref5_porfido_cu_usgs_b1693_fig50.png` | Fig. 50, modelo general de pórfido de cobre | Cox, D. P. (1986). Descriptive model of porphyry Cu. USGS Bulletin 1693 | Dominio público (USGS) |
| `ref6_hotspring_auag_usgs_b1693_fig105.png` | Fig. 105, depósito hot-spring de Au-Ag | Berger, B. R. (1986). Descriptive model of hot-spring Au-Ag. USGS Bulletin 1693 | Dominio público (USGS) |
| `ref7_skarn_cu_usgs_b1693_fig57.png` | Fig. 57, skarn de cobre | Cox, D. P. y Theodore, T. G. (1986). Descriptive model of Cu skarn deposits. USGS Bulletin 1693 | Dominio público (USGS) |
| `ref8_porfido_cumo_usgs_b1693_fig82.png` | Fig. 82, pórfido de Cu-Mo | Cox, D. P. (1986). Descriptive model of porphyry Cu-Mo. USGS Bulletin 1693 | Dominio público (USGS) |
| `fgdc37_p1.png` a `fgdc37_p3.png` | Sección 37, tramas litológicas | Federal Geographic Data Committee (2006). *FGDC Digital Cartographic Standard for Geologic Map Symbolization*, FGDC-STD-013-2006. USGS Techniques and Methods 11-A2. https://pubs.usgs.gov/tm/2006/11A02/ | Dominio público (USGS). Las tramas de `tramas.py` están redibujadas a partir de él, no copiadas |

## Ideas citadas sin figura

- Lowell, J. D. y Guilbert, J. M. (1970): orden de las aureolas en pórfidos (potásica, fílica, propilítica).
- Buchanan, L. J. (1981): zonación de vetas epitermales, usada en el ejemplo de Arcata.

## Ejemplo de Arcata del script

Los valores por defecto del script (sección y columna de la mina Arcata, Perú) son una interpretación propia con
cifras de tesis y boletines citados en el mismo script. No se incluye ninguna figura de esas tesis.
