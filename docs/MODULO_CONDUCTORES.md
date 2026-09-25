# Módulo de conductores informales, login por celular y cámaras

> Qué se construyó, cómo se usa (app y Telegram) y dónde está el código.

## 1. Idea
Hoy los jeeperos y colectiveros de Ciudad Bolívar organizan sus salidas **a mano y de boca en boca**:
gritan la ruta, esperan a llenar y los pasajeros no saben a qué hora sale el siguiente.
Muévete CB **automatiza esa logística**:

- El **conductor** anuncia a qué hora sale, por qué ruta y con cuántos cupos.
- El **pasajero** ve los próximos viajes y **aparta su cupo**; el conductor sabe cuántos lo esperan.
- El conductor avisa **"Ya salí"** y comparte ubicación → los pasajeros lo ven moverse; si no quedan
  cupos, el viaje queda **"lleno"** automáticamente.
- Si hay protesta o cierre, el conductor avisa su **desvío** y los pasajeros lo ven.
- Se guarda el **historial** de cada conductor → se calcula su **tendencia de horarios**
  (p. ej. "suele salir 6:00, 6:30 y 17:30, ~4 viajes/día"). Eso alimenta el **modo offline**
  (horarios típicos guardados en el celular) y el asistente de IA.

## 2. Identidad: login solo con celular + nombre
- Sin contraseñas. En la app: celular + nombre + **¿pasajero o conductor?** (botones grandes;
  se puede cambiar cuando quiera).
- En Telegram: botón **"📱 Compartir mi número"** (Telegram envía el número verificado).
- El número se normaliza (últimos 10 dígitos) y se guarda **hasheado con sal**: el mismo número es la
  **misma persona en la app y en Telegram** (mañana en WhatsApp, mismo código).

## 3. Cómo se usa

### App web — pestaña **Viajes**
| Pasajero | Conductor |
|---|---|
| Ve próximos viajes (ruta, hora, cupos, desvíos) | Publica viaje: ruta, sale de, va a, hora, cupos |
| **Apartar cupo** (pide login si no ha entrado) | **Ya salí** (comparte ubicación), **Lleno**, **Desvío**, **Finalizar** |
| Sin conexión: ve los **horarios típicos** | Ve cuántos pasajeros lo esperan |

### Telegram (pensado para personas mayores)
```
/start                      → elegir 🧍 Pasajero o 🚙 Conductor (+ 📱 Compartir mi número)
Conductor:
  salgo 6:30 de Mirador a Paraíso con 8 cupos
  ✅ Ya salí   (luego 📍 Enviar mi ubicación)
  🚫 Lleno  ·  ↪️ desvío por la 68 porque hay protesta  ·  🏁 Terminé  ·  cuantos esperan
Pasajero:
  🕒 Ver viajes  ·  jeep a Paraíso  ·  Apartar 1
```
Todo lo que no es de viajes (p. ej. "de Meissen a Paraíso") sigue yendo al asistente de rutas.

## 4. Cámaras de fotodetección (Edge AI)
- Las cámaras de fotocomparendos ya instaladas en los semáforos cuentan vehículos **en el borde**
  y envían **solo un número**: el nivel de congestión (nunca video ni placas).
- `POST /cameras/{id}/lectura {nivel: 0..1, vehiculos}`:
  - < 60 %: flujo normal, no pasa nada.
  - 60–95 %: **trancón** en el tramo de la cámara.
  - ≥ 95 %: **bloqueo** (tráfico detenido).
- La cámara reporta como **sensor verificado** (confianza 100 %) y se **suma** a los reportes de los
  vecinos sobre el mismo tramo → el motor penaliza/evita ese tramo y **recalcula alternativas**.
- Demo: en `simulador.html` → botón **"Cámaras de fotodetección"**.

## 5. Alternativas cuando algo se cierra
- Reporte de vecinos, cámara o desvío de conductor ⇒ el tramo queda penalizado o bloqueado.
- El planeador muestra: *"Hay N cierres en la zona: te mostramos X rutas alternativas que los evitan"*
  y la lista de **desvíos de conductores informales**.
- En Telegram: botón **"🔀 Ver alternativas"** del asistente.

## 6. Datos que se capturan (con permiso)
| Dato | Tabla | Para qué |
|---|---|---|
| Nombre de usuario, modo | `reporters` | Personalizar, saber quién es conductor |
| Viajes anunciados (hora, ruta, cupos, salida, ubicación) | `trips` | Logística + tendencia + offline |
| Cupos apartados | `seat_requests` | Demanda real por ruta y hora |
| Casa / paradero de salida | `saved_places` | Origen rápido; mapa de demanda por barrio |
| Rutas consultadas | `route_events` | Demanda agregada (dato de negocio) |
| Vínculo Telegram ↔ celular | `identity_links` | Misma persona en todos los canales |

Política completa: [DATOS_Y_PRIVACIDAD.md](DATOS_Y_PRIVACIDAD.md).

## 7. Endpoints nuevos
| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/auth/login` | Login celular + nombre + modo → `client_id = tel:<num>` |
| POST | `/me/perfil` | Cambiar nombre o modo |
| GET/POST | `/me/lugares` | Lugares guardados (casa, paradero) |
| POST | `/conductores/perfil` | Registrar ruta del conductor |
| POST | `/conductores/viajes` | Anunciar viaje |
| GET | `/conductores/mios` | Mis viajes |
| POST | `/conductores/viajes/{id}/salir` · `/lleno` · `/desvio` · `/finalizar` | Gestionar viaje |
| GET | `/conductores/{id}/tendencia` | Tendencia de horarios (heurística + redacción con Gemini si hay) |
| GET | `/conductores/horarios` | Horarios típicos por ruta (para offline) |
| GET | `/viajes/proximos` · POST `/viajes/{id}/reservar` · GET `/viajes/demanda` | Pasajeros |
| POST | `/cameras/{id}/lectura` | Lectura de cámara de fotodetección |
| GET | `/stats/rutas` | Rutas más pedidas (agregado, anónimo) |
| GET | `/integraciones/buses_tiempo_real` | Punto preparado para GTFS-realtime / alianza Moovit |

## 8. Código
- Dominio: `backend/app/domain/drivers.py`, `backend/app/domain/ride_chat.py`
- Identidad por teléfono: `backend/app/domain/reports.py` (`reporter_id_por_telefono`)
- API: `backend/app/adapters/inbound/driver_api.py`
- Persistencia: `backend/app/adapters/outbound/pg/` + migración `alembic/versions/0002_drivers.py`
- Web: `web/js/rides.js` (login + vista Viajes), `web/js/sim.js` (cámaras)
- Pruebas: `backend/tests/test_drivers.py`
- Datos de demo: `docker compose exec backend python -m scripts.seed_demo` · Reiniciar demo: `bash scripts/reset_demo.sh`
