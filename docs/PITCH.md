# 🎤 Pitch ganador — "Muévete CB"
### Hackathon Colombia 5.0 · Reto Muévete CB · 5 jurados · estilo Shark Tank · 5 minutos · **un solo expositor**

> **Cómo usar este documento:** léelo una vez, memoriza **palabra por palabra** los primeros 45 segundos
> y el cierre, y ensaya cronometrado **mínimo 3 veces**. Las cifras NO se memorizan: están en las
> diapositivas (`Presentacion_MueveteCB`). Lo que gana no es la app: es cómo la **vendes**.

---

## 0) La idea en una frase
> **"Muévete CB junta en un solo lugar toda la movilidad de la loma: el TransMiCable y el SITP con los jeeps
> y colectivos, y usa inteligencia artificial para organizarles a los conductores informales sus cupos y
> horarios. Funciona por Telegram —mañana WhatsApp— y en la app, hasta sin señal."**

---

## 1) Estrategia
1. **La imagen del taller (9 bloques):** cada bloque responde una pregunta del jurado antes de que la haga.
2. **La rúbrica:** Pertinencia territorial **25%** · Innovación 20% · Viabilidad 20% · Impacto 20% · Presentación 15%.
3. **Shark Tank:** el jurado tiene que salir convencido de que esto **genera dinero** (lo recalcaron en el
   evento) sin cobrarle nunca al pasajero: **vendemos datos y hacemos alianzas con plataformas**.
4. **La IA tiene que verse** (en el taller y en la rúbrica de innovación): se explica en qué partes está y
   se muestra funcionando.

> ¿"GovTech"? Son empresas de tecnología que le venden soluciones al Estado. **No uses la palabra**; di:
> *"le vendemos a las entidades públicas la información de movilidad que hoy no tienen"*.

---

## 2) Dónde está la IA (apréndetelo: el jurado lo va a preguntar)

| Agente / componente | Qué hace | Dónde se ve |
|---|---|---|
| **1. Agente conversacional (Gemini)** | Entiende lo que la gente escribe como habla ("ando por el hospital y voy donde mi tía en Potosí"), saca origen, destino, prioridad o tipo de reporte, y redacta la respuesta de forma cálida. | Chat de Telegram y asistente de la app |
| **2. Agente de análisis de conductores y pasajeros** | Aprende del historial: a qué horas sale cada conductor, cuántos viajes hace al día, cuánta gente pide cada ruta y a qué hora, dónde se bajan. Gemini lo explica en lenguaje natural. | Tendencia de horarios · horarios típicos en modo offline · tablero de demanda |
| **3. Visión por computador en el borde (cámaras)** | Cuenta vehículos en la imagen de las cámaras de fotocomparendos y manda solo el nivel de congestión. | Sala en vivo: "Cámara detectó 58 vehículos → bloqueo" |
| **4. Motor de decisión en tiempo real** | Combina los reportes de los vecinos (con reputación y confianza), las cámaras y los desvíos de los conductores, y recalcula rutas alternativas al instante. | Planeador: "Hay 1 cierre, te mostramos alternativas" |

**La frase clave de la IA (diferenciador):**
> *"La IA entiende y explica; el motor calcula. Por eso nunca inventa una ruta ni un precio: si Gemini
> cambia una cifra, el sistema la descarta y usa la respuesta verificada."*

*(Honestidad técnica, por si preguntan: el cálculo de rutas es un algoritmo de optimización con un modelo
de confianza; Gemini no calcula rutas a propósito, para no "alucinar". Las cámaras en el demo son
simuladas; en producción requieren convenio con la Secretaría de Movilidad.)*

---

## 3) Pitch en solitario — claves
- Narras y operas el demo. Nunca te quedes callado mirando la pantalla: **narra lo que tocas**.
- Si puedes, que **un compañero tenga el celular de "Wilson"** (el conductor) y lo muestre: se ve genial.
- Ritmo: historia lenta → demo ágil → números **leyéndolos de la diapositiva** → cierre lento.

---

## 4) EL GUION — 5:00

### 🎬 BLOQUE 1 — PROBLEMA · [0:00–0:45] · *Diapositiva 1–2*
> **"Son las 5:30 de la tarde en el Centro Comercial El Ensueño. Rosa sale de trabajar y vive en Potosí,
> arriba en la loma. Wilson, el colectivero, sale de ahí hacia Sierra Morena y Potosí. Pero Rosa no sabe
> a qué hora sale, Wilson no sabe cuántos lo esperan, y muchas veces él corta el viaje en Sierra Morena
> porque no le da la gente para subir. Los que iban a Potosí quedan a pie. Todos los días."**
>
> **"En Ciudad Bolívar vivimos cerca de 700.000 personas, en la montaña. El cable y el SITP llegan hasta
> cierto punto; de ahí para arriba mandan los jeeps y colectivos, y esa información no está en ningún mapa.
> Por eso la gente gasta entre dos y tres horas por trayecto."**

### BLOQUE 2 — SOLUCIÓN + IA · [0:45–1:15] · *Diapositiva 3–4*
> **"Muévete CB junta lo formal y lo informal en un solo lugar y le organiza el trabajo al conductor
> informal. Y usa inteligencia artificial en cuatro partes: un agente con Gemini que entiende a la gente
> como habla; un agente que aprende de los horarios de cada conductor y de la demanda de los pasajeros;
> visión por computador en las cámaras de los semáforos; y un motor que recalcula rutas en tiempo real.
> Sin contraseñas: solo el celular. La abuela por el chat, el joven por la app."**

### 🔥 DEMO EN VIVO · [1:15–2:45] (90 s) · *Diapositiva 5 de respaldo*
1. **Wilson publica por Telegram (15 s).** En su celular: `salgo 6:30 de El Ensueño a Potosí con 10 cupos`
   → *"Viaje publicado: El Ensueño → Sierra Morena → Potosí"*.
   > *"Wilson no aprende ninguna app: le escribe al bot como a un vecino."*
2. **Rosa aparta cupo en la app (20 s).** Portátil → **Viajes** → viaje de Wilson → **Apartar cupo** →
   *¿Hasta dónde vas?* → **Me bajo en Sierra Morena** (o Voy hasta Potosí). **Al celular de Wilson le llega:**
   *"Rosa apartó cupo…"*.
   > *"Wilson ya sabe cuántos lo esperan y dónde se baja cada uno."*
3. **Ya salí / corte (15 s).** Wilson toca **✅ Ya salí** → a Rosa le aparece *"¡Tu colectivo ya salió!"*. Si
   quieres mostrar el corte: **✂️ Cortar viaje → Llego hasta Sierra Morena** → solo se avisa a quienes iban
   más allá.
4. **Cámaras + ruta alternativa (30 s).** **Sala en vivo** → **Cámaras de fotodetección** → *"subida a
   Paraíso: 58 vehículos → bloqueo"* → app, **Rutas**: Paraíso Alto → Portal Tunal → *"Hay 1 cierre, te
   mostramos rutas alternativas"*.
   > *"Las cámaras de fotocomparendos ya están en los semáforos. Contamos carros con visión por computador y
   > mandamos solo el número, nunca video ni placas. Se cruza con los reportes de los vecinos y el sistema te
   > da otra ruta."*
5. **Remate (10 s).** *"Y si en la loma se cae la señal, la app sigue funcionando con los horarios que la IA
   aprendió de cada conductor."*

### BLOQUE 3 — MERCADO · [2:45–3:05] · *Diapositiva 6 (lee las cifras)*
> **"Empezamos en Ciudad Bolívar: 700.000 personas. La Bogotá de ladera son casi 2 millones con el mismo
> problema, y Soacha, Medellín o Cali tienen lomas y jeeps igualitos."** *(Señala TAM/SAM/SOM en pantalla.)*

### BLOQUE 4 — MODELO DE NEGOCIO · [3:05–3:35] · *Diapositiva 7 (lee los precios verdes)*
> **"El pasajero nunca paga. Ganamos con datos y con alianzas.**
> **Uno: la Secretaría de Movilidad y la Alcaldía no saben cómo se mueve la gente en la loma; nosotros sí: les
> vendemos un tablero con la demanda real por 10 millones al mes por localidad. Dos: estudios agregados y
> anónimos para operadores, comercio y universidades, de 15 a 40 millones cada uno. Tres: a Moovit, Google o
> Waze les licenciamos la capa informal, unos 150 millones al año por plataforma. El pasajero y el conductor
> nunca pagan."**
>
> *(Si hay 10 segundos: cambia a la pestaña **Admin → Tablero de movilidad** y señala el análisis de la IA.)*
> **"Esto es lo que compra la Secretaría: a qué hora sale la loma, por dónde sale, a dónde va, qué rutas se
> cortan… y la IA se lo resume al gerente."**

### BLOQUE 5 — COMPETENCIA Y ALIANZAS · [3:35–3:50]
> **"No competimos con Moovit ni Google: son buenos para la ciudad formal, pero no tienen la loma. Queremos
> ser su socio para el informal. Nuestro sistema ya está preparado para recibir sus datos por conexión directa."**

### BLOQUE 6 — EQUIPO · [3:50–4:00]
> **"Hoy les hablo yo, pero detrás hay un equipo: [nombres]. En horas construimos esto funcionando: app, bot,
> base de datos, cámaras e IA. Las ideas no mueven a nadie; los equipos que ejecutan, sí."**

### BLOQUE 7 — FINANZAS · [4:00–4:15] · *Diapositiva 8 (lee la tabla)*
> **"Somos realistas: mantener la app bien hecha cuesta unos 28 millones al mes. Los dos primeros años
> invertimos para llegar a 4 y luego a 8 localidades; en el mes 25 la operación se paga sola y el tercer año
> deja unos 190 millones. Para llegar ahí necesitamos unos 400 millones entre fondos e inversión."**
>
> *(Costos y "¿cuándo venden los datos?": diapositivas de **anexo** al final; solo si preguntan.
> Detalle completo en [MODELO_NEGOCIO.md](MODELO_NEGOCIO.md).)*

### BLOQUE 8 — IMPACTO Y DATOS · [4:15–4:40] · *Diapositiva 9*
> **"El impacto es tiempo de vida: 30 minutos menos por viaje es una hora al día por persona. Los conductores
> llenan más rápido y no cortan viajes a ciegas. Y sin cédula ni contraseña —solo el celular, cifrado y con
> la Ley 1581— construimos el mapa de cómo se mueve la loma. Lo que vendemos es siempre agregado y anónimo."**

### 🎯 BLOQUE 9 — PEDIDO Y CIERRE · [4:40–5:00] · *Diapositiva 10*
> **"Les pedimos su respaldo para un piloto real en El Ensueño, Sierra Morena, Potosí y el corredor del cable,
> con la Alcaldía Local, la Secretaría de Movilidad y los conductores. El cable ya está. Los colectivos ya
> están. Las cámaras ya están. La comunidad ya está. Solo falta conectarlos. El momento es ahora."**
> *(Silencio 2 s.)* **"Gracias."**

---

## 5) Factores psicológicos
| Arma | Cómo la usas |
|---|---|
| **Historia con dos caras** | Rosa (pasajera) y Wilson (colectivero): todos ganan |
| **Ejemplo real del barrio** | El Ensueño → Sierra Morena → Potosí, y "el viaje que se corta": el jurado lo reconoce |
| **Mostrar, no contar** | Al celular de Wilson le llega el aviso en vivo |
| **IA explicable** | "La IA entiende y explica; el motor calcula": confianza |
| **Anclaje numérico** | 700.000 → 2–3 horas → millones de horas (en pantalla) |
| **Dinero claro y sin cobrarle al pobre** | Datos + alianzas; el pasajero nunca paga |
| **Aliado, no enemigo** | Moovit/Google/Waze como socios |
| **Urgencia** | "Todo ya está. Solo falta conectarlos." |
| **Cierre con silencio** | Terminar y callar transmite seguridad |

## 6) Voz, cuerpo y vestuario
- **Vestuario:** smart casual limpio (jean oscuro, camiseta o camisa lisa morada o verde, zapatos cerrados). Ni desarreglado ni de traje.
- **Voz:** más lento de lo que crees; pausa después de cada cifra.
- **Cuerpo:** mira a los 5 jurados; manos visibles; en el demo señala y vuelve a mirarlos.
- **Palabras que SÍ:** vecinos, la loma, colectivero, apartar el cupo, se baja en Sierra Morena, devolver tiempo, ya funciona, sin señal, el pasajero nunca paga, cifrado, alianza, inteligencia artificial.
- **Palabras que NO:** GovTech, backend, Dijkstra, endpoint, hash, API, "vamos a", "sería".

## 7) Demo a prueba de fallos — 30 min antes
- [ ] `docker compose ps` → 3 servicios **healthy**.
- [ ] **Gemini (ya activado):** `.env` con `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.5-flash-lite` y la clave; `backend/.env` con `LLM_TIMEOUT_S=5`. El bot responde en 2–6 s. Frase para lucirlo: *«ando por el hospital y voy donde mi tía en Potosí, lo más barato»*.
- [ ] `bash scripts/reset_demo.sh` → demo limpio con conductores de ejemplo.
- [ ] `bash scripts/telegram_demo.sh` → deja esa terminal abierta.
- [ ] **Celular de Wilson:** escribir al bot `/start` → **Soy conductor** (así el bot sabe a dónde mandarle los avisos).
- [ ] Portátil: pestaña *Viajes*, pestaña *Sala en vivo* y pestaña **Admin → Tablero de movilidad** ya abierta con la clave (así el análisis de la IA ya está listo). Batería, brillo, notificaciones en silencio.
- [ ] Video de respaldo del demo grabado.

**Plan B:** Telegram falla → publica el viaje desde la app (Viajes → Soy conductor) · Wifi falla → todo corre local; *"justo por esto funciona sin señal"* · Proyector falla → demo en el portátil · Todo falla → video.

## 8) Preguntas del jurado
> Las difíciles (dónde vive la app, quién la paga, la brecha legal, cómo convencer a los conductores, la base
> de datos, el modo administrador) están desarrolladas en **[PREGUNTAS_JURADO.md](PREGUNTAS_JURADO.md)**.

- **"¿Dónde está la IA?"** → Los 4 componentes de la sección 2. Remata con *"la IA entiende y explica; el motor calcula"*.
- **"¿Cómo ganan plata?"** → Venta de datos a entidades públicas (tablero de demanda), estudios agregados para empresas y universidades, y alianzas con plataformas. El pasajero nunca paga.
- **"¿Por qué un colectivero lo usaría?"** → Llena más rápido, sabe cuántos lo esperan y dónde se bajan, y no corta viajes a ciegas. No aprende ninguna app: le escribe al bot.
- **"¿Cómo detectan el tráfico las cámaras?"** → Visión por computador cuenta vehículos en la imagen, en el mismo equipo; solo se envía el nivel de congestión. En el demo es simulado; en producción, convenio con la Secretaría.
- **"¿Y los datos personales?"** → Solo celular y un nombre; el número se guarda cifrado; Ley 1581; vendemos solo datos agregados y anónimos.
- **"¿La alianza con Moovit es real?"** → Aún no; es la propuesta. El sistema ya está preparado para recibir sus datos; les ofrecemos lo que no tienen: el informal.
- **"¿Y si la IA se equivoca?"** → No calcula rutas ni precios: solo entiende y redacta. Si cambia una cifra, se descarta.
- **"¿Y si no hay internet?"** → La app guarda los horarios típicos que aprendió y sigue funcionando.
- **"¿Cuánto necesitan?"** → Piloto de 6 meses en El Ensueño–Sierra Morena–Potosí y el corredor del cable: unos $ 260 millones; para llegar al equilibrio (mes 25), unos $ 400 millones entre fondos e inversión.

## 9) Tarjeta de bolsillo
1. **Rosa sale del Ensueño; Wilson no sabe cuántos lo esperan y corta en Sierra Morena.**
2. **Formal + informal; la IA organiza cupos y horarios.**
3. **4 IAs: Gemini que entiende, agente que aprende horarios, cámaras que cuentan carros, motor que recalcula.**
4. **DEMO: Wilson publica → Rosa aparta (me bajo en Sierra Morena) → aviso a Wilson → Ya salí → cámara → alternativa.**
5. **Mercado y finanzas: léelos de la diapositiva.**
6. **El pasajero nunca paga: datos + alianzas (Moovit, Google, Waze).**
7. **"La IA entiende y explica; el motor calcula."**
8. **"Todo ya está. Solo falta conectarlos. El momento es ahora."** → silencio → "Gracias."

---

### Cifras de referencia (van en las diapositivas; no memorizar)
| | Año 1 | Año 2 | Año 3 |
|---|---|---|---|
| Tablero para entidades (1 → 4 → 8 localidades) | $ 120.000.000 | $ 480.000.000 | $ 960.000.000 |
| Estudios de movilidad | $ 60.000.000 | $ 250.000.000 | $ 600.000.000 |
| Alianzas con plataformas | — | $ 150.000.000 | $ 450.000.000 |
| Fondos no reembolsables | $ 100.000.000 | — | — |
| **Ingresos** | **$ 280.000.000** | **$ 880.000.000** | **$ 2.010.000.000** |
| **Costos** | $ 519.816.000 | $ 1.026.696.000 | $ 1.818.696.000 |
| **Resultado** | −$ 239.816.000 | −$ 146.696.000 | +$ 191.304.000 |

Mantener la app: $ 27.918.000 al mes con 1 localidad (nube $ 4.280.000) · $ 10.282.250 por localidad con 8.
Equilibrio mensual en el mes 25 · Financiación necesaria ≈ $ 400.000.000 · Piloto de 6 meses ≈ $ 260.000.000.
Simulador con los supuestos: `python3 scripts/simular_negocio.py`.

TAM: ~20 localidades/municipios con ladera × COP 120 M/año ≈ COP 2.400 M/año en tableros + datos y alianzas ·
SAM: Bogotá de ladera (~1,9 M personas, 4 localidades) ≈ COP 880 M/año · SOM año 1: Ciudad Bolívar ≈ COP 280 M.
*(Proyecciones a validar en el piloto.)*
