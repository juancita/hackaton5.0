# Look & feel — Muévete CB

Guía visual de la interfaz web. Sigue la identidad de **Colombia 5.0** tal como aparece en la
carta oficial del evento (`material_reto/Carta_evento_Hackathon.pdf`): morado institucional,
verde neón de acento, navy para bloques de datos y tipografía Aptos.

Los tokens viven en `web/css/styles.css` (`:root`). Nunca uses un color o una fuente sueltos:
usa el token.

---

## 1. Color

### Marca

| Token | Hex | Origen en la carta | Uso |
|---|---|---|---|
| `--morado` | `#770092` | Logo "Colombia", franja del pie | Color primario: barra superior, botones, estados activos, enlaces |
| `--morado-700` | `#5C0072` | — (derivado) | Hover / pressed del primario |
| `--indigo` | `#3D0080` | Subtítulos "Niveles de desempeño" | Títulos de sección, texto de énfasis |
| `--morado-100` | `#EFE0F4` | — (derivado) | Fondos de chips, pills y botones secundarios |
| `--morado-50` | `#F8F1FA` | — (derivado) | Hover suave, fondo de sugerencias, notas |
| `--verde` | `#00F346` | "5.0", bloque "En alianza con" | Acento **solo sobre morado o navy** (nunca texto sobre blanco: no tiene contraste) |
| `--navy` | `#1F3864` | Encabezado de tablas | Superficies oscuras: tooltips, avisos sobre mapa, botones de admin |
| `--celeste` | `#EBF5FB` | Celdas de la tabla de criterios | Superficie informativa (ubicación, datos) |
| `--naranja` | `#E8531C` | Pesos "25%", "20%" | Cifras clave: minutos, precio, conteos |

### Semánticos (niveles de desempeño de la rúbrica)

| Token | Hex | Nivel en la carta | Uso |
|---|---|---|---|
| `--ok` | `#1A6B00` | Excelente | Verificado, éxito |
| `--info` | `#005888` | Bueno | Información, GPS |
| `--warn` | `#7B4500` | Regular | Advertencias, pin fuera de zona |
| `--danger` | `#8A0000` | Insuficiente | Rechazar, borrar, errores |

Cada semántico tiene su fondo claro `--ok-bg`, `--info-bg`, `--warn-bg`, `--danger-bg`.

### Neutros

| Token | Hex | Uso |
|---|---|---|
| `--texto` | `#1B1B1F` | Texto principal (la carta usa negro) |
| `--gris` | `#5F6170` | Texto secundario, etiquetas |
| `--borde` | `#E3DDE8` | Bordes de inputs y separadores |
| `--bg` | `#F6F4F8` | Fondo de la app |
| `--card` | `#FFFFFF` | Tarjetas |

### Colores de datos (no son de marca)

Los colores de cada **modo de transporte** (`MODOS` en `data.js`: TransMiCable, TransMilenio,
SITP, jeep…) y de cada **tipo de alerta** (`Reports.TIPOS`) son semánticos del sistema de
transporte y se mantienen: el usuario los reconoce en la calle. Van en líneas del mapa,
leyenda, borde de tarjetas de alerta e iconos de paso.

---

## 2. Tipografía

- **Familia:** `Aptos` (la de la carta). Como Aptos no está en Google Fonts, el respaldo web es
  **Figtree** (humanista geométrica, métricas muy parecidas), luego `system-ui`.
  `--font: "Aptos", "Figtree", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;`
- **Pesos:** 400 texto, 600 etiquetas, 700 títulos y botones, 800 marca.
- **Escala (móvil):**

| Rol | Tamaño / peso |
|---|---|
| Marca (barra superior) | 20px / 800 |
| Título de tarjeta (`h2`) | 17px / 700, color `--indigo` |
| Título de sección (`h3`) | 15px / 700 |
| Texto | 14–15px / 400, interlineado 1.45 |
| Etiqueta de campo | 12px / 600, `--gris` |
| Pill / badge | 11px / 700 |

- Las etiquetas de sección pueden ir en MAYÚSCULAS con `letter-spacing: .04em`
  (como "CONTEXTO:" en la carta), solo en textos cortos.

---

## 3. Iconografía

- **Librería:** [Material Symbols Rounded](https://fonts.google.com/icons), cargada desde
  Google Fonts. Ejes: `FILL 0` (1 en estados activos), `wght 500`, `GRAD 0`, `opsz 24`.
- **Nada de emojis en la interfaz.** Excepción: el texto de los mensajes del asistente (web,
  WhatsApp y Telegram comparten el mismo texto del backend, y en esos canales no hay iconos).
- Uso en HTML: `<span class="ms" aria-hidden="true">directions_bus</span>`.
  En JS: `ico('directions_bus')` (definido en `js/icons.js`).
- El icono siempre acompaña a un texto o lleva `aria-label` en su botón.

| Concepto | Icono |
|---|---|
| Marca / TransMiCable | `gondola_lift` |
| Rutas | `route` |
| Asistente | `chat` |
| Reportar | `campaign` |
| Admin | `shield_person` |
| Intercambiar origen/destino | `swap_vert` |
| Mapa | `map` |
| Ubicación / GPS | `my_location` |
| Tiempo · Precio · Transbordos | `schedule` · `payments` · `sync_alt` |
| Recomendada | `star` |
| Alerta en la ruta | `warning` |
| Verificado / Confirmar / Negar | `verified` · `thumb_up` · `thumb_down` |
| Rechazar / Borrar | `block` · `delete_sweep` |
| Canales: Web · WhatsApp · Telegram | `public` · `chat` · `send` |

Iconos por modo y por tipo de alerta: `js/icons.js` (`ICONO_MODO`, `ICONO_TIPO`).

---

## 4. Forma, espacio y elevación

- **Radios:** `--r-sm: 8px` (chips internos, notas), `--r: 12px` (inputs, botones, tarjetas
  pequeñas), `--r-lg: 14px` (tarjetas y mapa). Pills: `999px`.
- **Espaciado:** múltiplos de 4px; padding de tarjeta 16px; separación entre tarjetas 12–14px.
- **Sombras** (tintadas en morado, suaves): `--sombra: 0 4px 14px rgba(119,0,146,.08)`;
  hover `--sombra-hover: 0 8px 22px rgba(119,0,146,.14)`.
- **Foco:** `outline: 2px solid var(--morado); outline-offset: 2px` en todo elemento interactivo.

---

## 5. Motivo gráfico

La carta usa bloques planos y **cortes diagonales** (el bloque verde del pie se encuentra con
el morado en diagonal) y líneas finas tipo circuito.

- **Barra superior:** morado plano (sin degradados) con una franja inferior de 4px:
  verde neón en el primer tramo, cortada en diagonal, y morado oscuro el resto.
- **Marca:** "Muévete" en blanco + "**CB**" en verde neón (eco del "5.0").
- Tarjetas con **borde izquierdo de color** (4–5px) para indicar tipo (modo o alerta).
- Sin degradados de color en superficies; los únicos degradados son del mapa de respaldo.

---

## 6. Componentes

| Componente | Regla |
|---|---|
| Botón primario | Fondo `--morado`, texto blanco 700, radio `--r`, alto ≥ 46px. Hover `--morado-700`. Deshabilitado `--borde` |
| Botón secundario (`.linkbtn.ghost`, `.voto`) | Fondo `--morado-100`, texto `--morado` |
| Botón peligro | Fondo `--danger-bg`, texto `--danger` |
| Input / select | Borde 1.5px `--borde`, foco `--morado`, fondo blanco |
| Pill de conteo | Fondo `--morado-100`, texto `--morado` 700 |
| Badge "Recomendada" | Fondo `--morado`, texto blanco; badge "informal" fondo `--verde`, texto `--navy` |
| Barra inferior (tabs) | Blanco; activo en `--morado` con icono relleno (`FILL 1`) |
| Chat | Cabecera morada; burbuja propia `--morado-100`, burbuja del bot blanca, fondo `--bg` |
| Toast | Blanco, borde izquierdo del color del evento, sombra `--sombra-hover` |
| Cifras (min, $) | `--naranja` 700 |

---

## 7. Accesibilidad

- Contraste AA: texto blanco sobre `--morado` (≈ 10:1), `--indigo` y `--navy` sobre blanco
  pasan AA. El verde neón **no** se usa como color de texto sobre fondos claros.
- Objetivos táctiles ≥ 40px.
- Los iconos decorativos llevan `aria-hidden="true"`.
