# Muévete CB 🚡🚌📹

**Asistente inteligente de movilidad para Ciudad Bolívar** — Hackathon Colombia 5.0
(MinTIC · TEVEANDINA · Universidad Distrital Francisco José de Caldas)

Integra en un solo punto el transporte **formal** (TransMiCable, SITP) y el
**informal** (jeeps, colectivos, rutas veredales) que hoy solo vive en el
"boca a boca", con un **mapa vivo tipo Waze**, **reporte ciudadano en tiempo real**
y **Edge AI** con cámaras. Funciona por **web** y por **WhatsApp**, incluso **sin internet**.

---

## 🎯 El diferenciador
Todos pueden consultar el SITP en Google Maps. **Nadie tiene mapeado el transporte
informal** ni un sistema colaborativo en tiempo real para la ladera. Esa es la brecha
del reto y es nuestro corazón:
1. **Digitalizamos lo informal** (jeeps de Quiba, colectivos a Paraíso, veredales).
2. **Tiempo real tipo Waze**: la comunidad reporta y todos ven al instante.
3. **Edge AI sobre fotodetección**: reutilizamos las cámaras de fotocomparendos que **ya existen** en los semáforos para detectar congestión **en el dispositivo** (sin nube, sin hardware nuevo).
4. **Inclusión real**: WhatsApp para quien solo usa WhatsApp; web para el resto. Mismo cerebro.
5. **Offline-first**: en las zonas altas no hay señal; la app igual funciona.

## ✅ Las 5 capacidades del reto → cómo las cubrimos
| # | Capacidad requerida | Implementación |
|---|---------------------|----------------|
| 1 | Integración formal + informal | Grafo multimodal + **datos oficiales en vivo** (`data.js`, `datasources.js`) |
| 2 | Agente de recomendación IA | Motor Dijkstra local + capa de lenguaje natural (`engine.js`, `ai.js`) |
| 3 | Visualización geográfica | **Mapa vivo Leaflet tipo Waze** + esquema offline (`app.js`) |
| 4 | Reporte ciudadano en tiempo real | Bus híbrido en tiempo real + incidentes geo (`realtime.js`, `reports.js`) |
| 5 | Canal de bajo umbral | **PWA + WhatsApp** (mismo backend) + Edge AI (`edge.js`) |

## 🚀 Cómo correr (sin instalar nada)
```bash
cd web
python3 -m http.server 8000     # abrir http://localhost:8000
```
Sin `npm install`, sin build, sin backend. Corre en cualquier portátil.
- **App:** http://localhost:8000/index.html
- **Sala en vivo (multiusuario):** http://localhost:8000/simulador.html

## 🗂️ Estructura
```
web/                 Prototipo funcional (PWA offline)
  index.html         App: Rutas · Asistente · Mapa · Reportar · Cámara
  simulador.html     Sala en vivo: 3–6 usuarios reportando a la vez
  css/styles.css
  js/data.js         Datos semilla: paraderos, rutas formal+informal, cámaras
  js/datasources.js  Fuentes OFICIALES en vivo (ArcGIS TM / datos.gov.co / IDECA)
  js/engine.js       Motor de rutas (grafo multimodal + Dijkstra)
  js/ai.js           Asistente de lenguaje natural (local + LLM opcional)
  js/realtime.js     Sincronización en tiempo real híbrida (Waze)
  js/reports.js      Reportes ciudadanos / incidentes geolocalizados
  js/edge.js         Edge AI: cámaras (webcam + TensorFlow.js) + simuladas
  js/app.js          Interfaz principal
  js/sim.js          Lógica de la Sala en vivo
  sw.js              Service worker (offline)
docs/                📚 Documentación del proyecto (empieza por aquí)
  ARQUITECTURA.md    Cómo está montado todo
  FUENTES_DATOS.md   Fuentes oficiales consumidas y cómo extenderlas
  ESTRATEGIA.md      Estrategia atada a la rúbrica
  PITCH.md           Guion del pitch de 5 min
  GUIA_EQUIPO.md     Cómo trabaja el equipo
backend/README.md    Producción: tiempo real real + WhatsApp + LLM
whatsapp/flujo.md    Diseño del bot de WhatsApp
CONTRIBUTING.md      Flujo de Git para trabajar en paralelo
```

## 👥 Para el equipo
Empieza por **[docs/GUIA_EQUIPO.md](docs/GUIA_EQUIPO.md)** y **[CONTRIBUTING.md](CONTRIBUTING.md)**.
La arquitectura completa está en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

## 🏆 Por qué gana
- **Innovación (20%)**: informal + tiempo real Waze + Edge AI = combinación no obvia.
- **Viabilidad (20%)**: offline, gama baja, costo casi cero, datos oficiales reales.
- **Pertinencia (25%)**: datos y actores reales de Ciudad Bolívar.
- **Impacto (20%)**: minutos devueltos × miles de personas; escalable y sostenible.
- **Presentación (15%)**: demo en vivo a prueba de fallos (funciona en modo avión).
