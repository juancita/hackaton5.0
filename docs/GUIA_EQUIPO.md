# Guía del equipo — Muévete CB

> Cómo trabajamos varios en paralelo sin pisarnos. Léelo antes de empezar.

## Puesta en marcha (5 minutos)
```bash
git clone https://github.com/juancita/hackaton5.0.git
cd hackaton5.0/web
python3 -m http.server 8000        # abre http://localhost:8000
```
No hay que instalar nada más. Todo es HTML/CSS/JS.

- **App principal:** http://localhost:8000/index.html
- **Sala en vivo (demo multiusuario):** http://localhost:8000/simulador.html

> Probar en el celular: corre el server en tu portátil y entra desde el celular a
> `http://IP-DEL-PORTATIL:8000` (misma red wifi).

## Mapa de archivos (quién toca qué)
| Archivo | Responsable sugerido | Qué es |
|---------|----------------------|--------|
| `backend/scripts/build_network.py` | Producto/Territorio | Fuente de verdad: paraderos, rutas, informal, cámaras. Genera `web/js/data.js` y `backend/data/network.json` desde las fuentes oficiales (ver `docs/FUENTES_DATOS.md`). |
| `web/js/datasources.js` | Dev backend/datos | Conexión a fuentes oficiales en vivo |
| `web/js/engine.js` | Dev algoritmos | Motor de rutas (Dijkstra) |
| `web/js/ai.js` | Dev IA | Asistente en lenguaje natural + LLM |
| `web/js/realtime.js` | Dev tiempo real | Bus de sincronización |
| `web/js/reports.js` | Dev | Reportes/incidentes |
| `backend/` | Dev backend | API FastAPI: rutas, asistente, reportes (ver `docs/specs/`) |
| `web/js/app.js` | Dev frontend | UI de la app |
| `web/js/sim.js` + `simulador.html` | Dev frontend | Sala en vivo |
| `web/css/styles.css` | Diseño | Estilos |
| `docs/PITCH.md` | Comunicación/Capitán | Guion del pitch |

## Flujo de trabajo con Git (importante — trabajamos en paralelo)
Ver [../CONTRIBUTING.md](../CONTRIBUTING.md) para el detalle. Resumen:
1. `git pull` antes de empezar.
2. Crea una rama por tarea: `git checkout -b feat/mapa-heatmap`.
3. Commits pequeños y claros en español.
4. `git push -u origin tu-rama` y abre un Pull Request.
5. Otro compañero revisa y hace merge a `main`.

**Regla de oro:** cambios grandes → en tu rama. `main` siempre debe correr.

## Reparto de roles (rúbrica)
| Rol | Foco | Entregable |
|-----|------|-----------|
| **Capitán / Comunicación** | Nodo de contacto, cierre del pitch, responder al jurado | Pitch ensayado |
| **Producto / Territorio** | Datos reales, actores locales, validar contexto | `data.js` fiel + argumentos |
| **Dev 1 (core)** | Motor, datos oficiales, tiempo real | App estable |
| **Dev 2 (frontend/IA)** | UI, mapa, asistente | Demo pulido |
| **Diseño** | UI/UX, slides, identidad | Materiales del pitch |

*(Si son 3–4, combinen roles. No hace falta que todos programen.)*

## Checklist antes del pitch
- [ ] `main` corre sin errores en un portátil limpio.
- [ ] Demo probado en **modo avión** (offline).
- [ ] Sala en vivo probada con 3–6 "usuarios".
- [ ] Backend + Postgres arriba (`docker compose up -d db`) y `GEMINI_API_KEY` probada.
- [ ] Datos oficiales cargando (badge 🟢) al menos una vez para llenar caché.
- [ ] Guion de 5 min cronometrado, todos hablan.
- [ ] Respuestas a preguntas trampa repasadas ([PITCH.md](PITCH.md)).

## Consejos de demo
- Abre `simulador.html` en pantalla grande: es el momento "wow".
- Ten `index.html` en un celular y el `simulador` en el portátil → muestran sincronización real.
- Si el wifi del evento falla: **mejor**, es tu argumento de viabilidad. Sigue en offline.
