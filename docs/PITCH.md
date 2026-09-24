# Pitch de 5 minutos — "Muévete CB"

> Regla de oro de la rúbrica: en los **primeros 2 minutos** el jurado debe entender
> el problema y la solución. Todos los integrantes hablan. Cierre con impacto medible.

---

## 🏗️ Estructura de pitch ganador (9 bloques del taller)
> Del taller Colombia 5.0: *"Todo pitch efectivo sigue una arquitectura de 9 bloques.
> Cada bloque responde una pregunta que tu audiencia ya tiene en mente — tu trabajo es
> anticiparla y responderla antes de que la formulen."*
>
> Como somos un proyecto **GovTech/social** (no lucrativo), adaptamos Mercado/Ingresos/
> Finanzas a **alcance, sostenibilidad y costos** — sin inventar ingresos. Sé honesto: eso convence.

| # | Bloque | Pregunta del jurado | Nuestra respuesta |
|---|--------|---------------------|-------------------|
| 01 | **Problema** | ¿Quién sufre y cuánto? | Habitantes de zonas altas/rurales de C. Bolívar pierden **2–3 h por trayecto**; la info del transporte informal solo existe en el "boca a boca". |
| 02 | **Solución** | ¿Qué hace y cómo se usa? | Asistente que cruza formal+informal y recomienda la mejor ruta. Se usa por **WhatsApp** (mi abuela) o **web** (experto). Sin tecnicismos. |
| 03 | **Mercado / Alcance** | ¿A cuántos llega? | TAM: ~**700.000** hab. de C. Bolívar. SAM: ~**200.000** en zonas altas/rurales dependientes del informal. SOM: piloto corredor TransMiCable + Paraíso/Quiba (año 1). |
| 04 | **Modelo (Ingresos→Sostenibilidad)** | ¿Cómo se sostiene? | **Gratis para el ciudadano.** Se sostiene con presupuesto de Alcaldía Local/MinTIC + datos abiertos; opción de alianzas con comercio local (plaza Perdomo) sin cobrar al usuario. |
| 05 | **Competencia** | ¿Quién más existe? | Moovit/Google: **no tienen el informal, no funcionan offline, no aprenden del reporte ciudadano en tiempo real**. Esa es nuestra ventaja. |
| 06 | **Equipo** | ¿Quién ejecuta? | *(Presenta a cada integrante y su rol: territorio, dev, diseño, capitán.)* Perfiles multidisciplinarios del propio territorio. |
| 07 | **Finanzas** | Costos y proyección 3 años | Operación **casi cero**: PWA estática + WhatsApp. Costo principal = validación comunitaria (JAC) y mantenimiento de datos. Proyección: piloto → localidad → réplica en Usme/Suba rural. |
| 08 | **Roadmap / Tracción** | ¿En qué punto están y qué sigue? | Hoy: prototipo funcional con datos oficiales en vivo. 3 meses: piloto con 1 JAC + GTFS real. 12 meses: cobertura localidad. |
| 09 | **Ask / Cierre** | ¿Qué piden? | Apoyo de Secretaría de Movilidad + Alcaldía Local para el piloto y acceso a validación comunitaria. *"El talento está aquí; el momento es ahora."* |

> ⚠️ Los bloques 08 y 09 no se alcanzaban a ver en la foto del taller (se infieren del formato
> estándar). **Confirmar con la organización** el contenido exacto de esos dos bloques.

---

## Guion (5:00)

### 0:00–1:00 — El problema (Pertinencia territorial · 25%)
> "En Ciudad Bolívar, subir a Paraíso, Sierra Morena o Quiba puede tomar **2 a 3 horas**.
> El SITP y el TransMiCable llegan hasta cierto punto; de ahí para arriba, la gente depende
> de **jeeps y colectivos** cuya información solo existe en el *boca a boca*: no hay horarios,
> no hay app, no hay certeza. Esa **brecha de información** es la que ataca Muévete CB."

*Actor real:* mencionar TransMiCable (Tunal, Juan Pablo II, Manitas, Mirador), jeeperos de Quiba, JAC de Paraíso.

### 1:00–1:45 — La solución en una frase (Innovación · 20%)
> "Muévete CB es el primer asistente que **integra el transporte formal con el informal**
> en un solo lugar, con un agente de IA que te dice la mejor ruta según tu origen, destino y tiempo.
> Lo que nadie ha digitalizado —los jeeps y colectivos— es justo nuestro corazón."

### 1:45–3:30 — DEMO EN VIVO (Viabilidad · 20% + Presentación · 15%)
> Ten dos pantallas: **portátil con `simulador.html`** (pantalla grande) + **celular con `index.html`**.

1. **Datos reales:** muestra el badge 🟢 *"paraderos oficiales en vivo"* → *"consumimos datos
   abiertos oficiales de TransMilenio/datos.gov.co/IDECA, y los cruzamos con lo informal."*
2. **Ruta mixta:** "de Meissen a Paraíso" → ruta SITP + TransMiCable + **jeep** (lo que nadie tiene).
3. **Inclusión:** en el celular, chat modo WhatsApp: *"cómo llego a Quiba lo más barato"*.
   *"Mi abuela solo sabe abrir WhatsApp; para ella la experiencia es la misma."*
4. **🔥 Sala en vivo (el wow):** en el portátil abre `simulador.html`, presiona **"Simular
   actividad"** → 6 vecinos (unos por WhatsApp, otros por web) reportan derrumbes/trancones y
   el **mapa se llena de alertas en tiempo real** con notificaciones. *"Es un Waze hecho por y
   para Ciudad Bolívar."*
5. **Edge AI:** ve a **Cámara** y enciende la webcam → detecta vehículos/personas **en el
   dispositivo** y calcula el índice de congestión. *"Visión por computador en el borde: el
   video nunca sale del equipo. Privacidad, sin datos, sin nube."*
6. **A prueba de fallos:** pon el portátil en **modo avión** y repite una búsqueda. *"Sin
   internet, sigue funcionando. Eso es viabilidad real en la ladera."*

> Frase clave: *"Corre en el celular más sencillo y sin señal. Eso es viabilidad real en la ladera."*

### 3:30–4:30 — Impacto (Impacto · 20%)
- **A quién**: ~700.000 habitantes de Ciudad Bolívar; foco en zonas altas y rurales.
- **Métrica**: si reducimos la incertidumbre y optimizamos transbordos, ahorramos
  **20–40 min por trayecto**. Con 2 trayectos/día = hasta **1 hora diaria** devuelta.
- **Escalable**: mismo modelo para Usme, San Cristóbal, Suba rural y municipios de ladera.
- **Sostenible**: PWA estática + WhatsApp = costo de operación casi cero. Datos abiertos
  (datos.gov.co, IDECA) + validación comunitaria (JAC).

### 4:30–5:00 — Cierre (el Capitán)
> "Muévete CB convierte el conocimiento de la comunidad en una herramienta GovTech de
> bajo umbral, que le **devuelve tiempo de calidad** a Ciudad Bolívar. El talento está aquí;
> el momento es ahora."

## Preguntas trampa del jurado (respuestas listas)
- **¿De dónde salen los datos informales?** Captura comunitaria + validación de JAC;
  en el prototipo van semillados con datos realistas.
- **¿Y si no hay señal?** Ya lo vieron: corre offline. El LLM es un extra, no una dependencia.
- **¿Quién lo mantiene?** Alcaldía Local / Secretaría de Movilidad + JAC. Costo casi cero.
- **¿No es solo otro Moovit?** No: Moovit no tiene el informal, no funciona offline y no
  aprende del reporte ciudadano en tiempo real.
- **¿Cómo se monetiza/sostiene?** No busca lucro: es GovTech. Puede sumar pauta local o
  alianzas con comercio (plaza de Perdomo) sin cobrar al usuario.

## Reparto de voces (4 personas)
1. Problema + territorio · 2. Solución + innovación · 3. Demo en vivo · 4. Capitán: impacto + cierre
