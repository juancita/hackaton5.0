# 05 · Reportes con roles (usuario / admin) y reputación

## Objetivo
Que los reportes ciudadanos pesen según quién los envía:
- los reportes de **usuarios** ganan peso a medida que sus reportes resultan ciertos;
- los reportes de **admin** pesan mucho.

No hace falta crear una cuenta: la identidad sale del canal. Todo el feedback se guarda en **PostgreSQL**.

## Estado actual
- `web/js/realtime.js` guarda los incidentes en localStorage. `votar()` suma `votos`, pero ese número no afecta nada.
- `autor` es texto libre, no hay roles y cualquiera puede ejecutar `limpiarTodo`.
- Los tipos de incidente (`TIPOS`) están en `web/js/reports.js:13-20`.

## Requisitos funcionales
### R1 · Identidad sin cuenta
| Canal | Id externo | Lo aporta |
|---|---|---|
| Telegram | `message.from.id` | el webhook |
| WhatsApp | `contacts[0].wa_id` (el teléfono) | el webhook |
| Web | un `client_id` UUID generado una vez en el navegador (localStorage) | el header `X-Client-Id` |

- `reporter_id = sha256(ID_SALT + canal + ":" + id_externo)`. Así no se guarda el teléfono en claro.
- El reportero se crea con **upsert** en su primer reporte o voto.
- Si no llega `X-Client-Id` desde la web, se responde `400`.

### R2 · Roles
- **admin:** peticiones con `X-Admin-Key == ADMIN_API_KEY`. Si el header opcional `X-Admin-Name` existe, se registran como el reportero `admin:<nombre>`.
- **usuario:** todos los demás.

### R3 · Reputación y peso
- `rep = (aciertos + 1) / (aciertos + fallos + 2)`. Un reportero nuevo tiene 0.5.
- Peso de un usuario: `w = 0.1 + 0.6 · rep`, entre 0.1 y 0.7. Un usuario nuevo pesa 0.4.
- Peso de un admin: `w = 1.0`.
- El peso se **guarda en el momento del reporte**, para poder auditarlo.

### R4 · Fusión y confianza
- Un reporte nuevo del mismo `tipo` sobre el mismo tramo (`de/a`, en cualquier sentido) con un incidente `activo` o `verificado` y vigente se **agrega** a ese incidente.
- Un mismo reportero no suma dos veces al mismo incidente.
- `conf = 1 − Π(1 − w_i)` sobre los reportes, más los votos `confirma`.
- Cada voto `niega` con peso `w_d` hace `conf ← conf · (1 − w_d)`.
- Un admin que reporta verifica el incidente de inmediato.

### R5 · Efecto en rutas
- Sin efecto si `conf < 0.4`.
- Si no, `factor_ef = 1 + (factor − 1) · conf`.
- Los tipos que bloquean (`derrumbe`, `bloqueo`, `sinservicio`) solo bloquean con `conf ≥ 0.7` o si un admin los verificó. Por debajo de eso penalizan con un factor de 2.5.

### R6 · Moderación y aprendizaje
- **verificar (admin):** `estado=verificado`, `conf=1`. Reporteros y votos `confirma` suman +1 acierto; votos `niega` suman +1 fallo.
- **rechazar (admin):** `estado=rechazado`, se saca de las rutas. Reporteros y votos `confirma` suman +1 fallo; votos `niega` suman +1 acierto.
- Los admin no acumulan aciertos ni fallos: su peso siempre es 1.0.
- **Expiración:** un incidente sin moderación que expira con `conf ≥ 0.7` suma +1 acierto a sus reporteros. Se resuelve de forma perezosa al consultar.
- **Límite anti-spam:** como mucho 1 reporte por reportero, tramo y tipo cada 10 min. Si se supera, se responde `429`.

### R7 · Persistencia (PostgreSQL en Docker)
```
reporters(id pk varchar(64), canal, rol, aciertos int, fallos int, creado_en, ultimo_en)
incidents(id uuid pk, tipo, de_id, a_id, modo, lat, lng, nota, estado, confianza float,
          creado_en, expira_en, verificado_por fk null, resuelto bool)
reports(id serial pk, incident_id fk, reporter_id fk, peso float, nota, canal, creado_en)
votes(id serial pk, incident_id fk, reporter_id fk, valor, peso float, creado_en,
      unique(incident_id, reporter_id))
índices: incidents(de_id, a_id, tipo, estado), incidents(expira_en), reports(reporter_id, creado_en)
```
Las migraciones se hacen con Alembic, y la BD se levanta con `docker compose up -d db`.

## Contrato API
| Método | Ruta | Auth | Body / respuesta |
|---|---|---|---|
| POST | `/incidents` | `X-Client-Id` o `X-Admin-Key` | `{tipo, de_id, a_id, modo?, nota?}` → `IncidentView` (201) |
| GET | `/incidents` | — | `[IncidentView]` vigentes, sin los rechazados |
| POST | `/incidents/{id}/votos` | `X-Client-Id` | `{valor: "confirma"\|"niega"}` → `IncidentView` |
| POST | `/admin/incidents/{id}/verificar` | `X-Admin-Key` | → `IncidentView` |
| POST | `/admin/incidents/{id}/rechazar` | `X-Admin-Key` | → `IncidentView` |
| DELETE | `/admin/incidents` | `X-Admin-Key` | → `{eliminados: n}` |
| GET | `/reporters/me` | `X-Client-Id` | → `{rol, aciertos, fallos, reputacion, peso}` |
| GET | `/incident-types` | — | los `TIPOS` |

`IncidentView`:
```json
{"id":"…","tipo":"trancon","label":"Trancón fuerte","icono":"🐢","de_id":"perdomo","a_id":"sierramorena",
 "modo":"sitp","lat":4.596,"lng":-74.1595,"nota":"","estado":"activo","confianza":0.4,
 "n_reportes":1,"n_confirma":0,"n_niega":0,"afecta_rutas":true,"creado_en":"…","expira_en":"…"}
```

## Casos borde
- Si el tramo no existe (`de/a` sin una arista), se responde `422`. Si no se envía `modo`, se toma el del primer tramo que coincida.
- Un voto sobre un incidente vencido o rechazado responde `409`. Un voto repetido del mismo reportero reemplaza el valor anterior; no se duplica.
- Una clave de admin incorrecta en `/admin/*` responde `401`. En `/incidents`, una clave incorrecta hace que la petición se trate como de usuario solo si trae `X-Client-Id`; si no, `401`.

## Criterios de aceptación
- Un usuario nuevo reporta un trancón: `conf=0.4` y el incidente afecta las rutas con `factor_ef = 1.32`.
- Un segundo usuario reporta el mismo trancón: `conf = 1 − 0.6² = 0.64` y no se crea un incidente nuevo.
- Un admin reporta un derrumbe: queda `verificado` y bloquea el tramo de inmediato.
- Un admin rechaza un incidente: los reporteros suben `fallos`, y su reputación y su peso bajan.
- Un usuario con 5 aciertos pesa `0.1 + 0.6·(6/7) ≈ 0.61`.
- Reiniciar la API no pierde los reporteros ni su reputación.

## Fuera de alcance
Panel web de admin, notificaciones push y moderación con IA.
