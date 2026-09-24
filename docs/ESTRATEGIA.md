# Estrategia para el primer puesto — "Muévete CB"

> Objetivo: maximizar la rúbrica. Cada decisión de producto está atada a un criterio.

## La rúbrica y nuestra jugada

| Criterio | Peso | Qué evalúan | Nuestra jugada ganadora |
|---|---|---|---|
| **Pertinencia territorial** | 25% | Problema real, contexto local, actores concretos | Datos reales de C. Bolívar. Nombrar actores: TransMiCable (Tunal, Juan Pablo II, Manitas, Mirador), JAC de Paraíso, jeeperos de Quiba/Pasquilla, comerciantes de Meissen. Citar el dato del reto: **2–3 horas por trayecto**. |
| **Innovación** | 20% | Enfoque novedoso, uso no obvio de IA | El **giro no obvio**: digitalizar el transporte *informal* (nadie lo tiene) + IA que cruza fuentes formales/informales. La IA no es un chatbot genérico: es un agente que razona sobre un grafo multimodal territorial. |
| **Viabilidad técnica** | 20% | ¿Se puede desplegar en el territorio real? | **Offline-first + gama baja + sin backend costoso.** Explicar explícitamente: zonas altas sin señal → app funciona sin internet. Costo de operación casi cero (estático + PWA). |
| **Impacto** | 20% | Transformación real, medible, escalable | Métricas: min ahorrados por viaje, # de personas, reducción de incertidumbre. Escalable a Usme, Suba rural, otros municipios de ladera. |
| **Presentación** | 15% | Claridad, demo en vivo, respuestas al jurado | Demo en vivo que **no depende del wifi**. Pitch de 5 min con hilo conductor. Todos hablan. |

## Los 3 mensajes que el jurado debe recordar
1. **"Integramos lo que nadie ha integrado: el transporte informal."**
2. **"Funciona sin internet, en el celular más sencillo."** (viabilidad real en ladera)
3. **"Le devolvemos tiempo de calidad a la comunidad"** — X minutos por viaje × miles de personas.

## Anti-riesgos (defensa ante el jurado)
- *"¿Y si no hay señal en el pitch?"* → El motor corre local; lo demostramos en modo avión.
- *"¿De dónde salen los datos informales?"* → Modelo de captura comunitaria: reporte
  ciudadano + validación de JAC. En el prototipo van semillados con datos realistas.
- *"¿Quién lo sostiene?"* → PWA estática = costo casi cero. Alcaldía Local /
  Secretaría de Movilidad + JAC como validadores. Datos abiertos de datos.gov.co e IDECA.
- *"¿Es solo un mapa más?"* → No: cruza formal+informal, funciona offline, y aprende del
  reporte ciudadano en tiempo real.

## Alcance de las 5 horas (qué construir sí o sí)
1. ✅ Planeador origen→destino con motor multimodal (formal+informal) — **núcleo**
2. ✅ Chat en lenguaje natural (modo WhatsApp) — el "agente"
3. ✅ Mapa esquemático offline con paraderos y rutas
4. ✅ Reporte ciudadano que afecta las recomendaciones en vivo
5. ✅ PWA instalable / offline
6. 🎁 Si sobra tiempo: conexión LLM real, mapa Leaflet online, más datos.

## Reparto sugerido del equipo (3–4 personas)
- **Producto/Territorio**: valida datos reales, arma el guion del pitch, actores locales.
- **Desarrollo**: ajusta datos semilla y motor, prepara el demo en modo avión.
- **Diseño/Comunicación**: pulir UI, slides del pitch, ensayo de 5 min.
- **Capitán**: nodo de comunicación + cierre del pitch + responder al jurado.
