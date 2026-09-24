# Backend de producción (opcional) — Muévete CB

> El demo **no necesita backend**: el tiempo real funciona local (BroadcastChannel +
> localStorage). Este documento describe cómo llevarlo a producción para sincronizar
> dispositivos distintos por internet y habilitar el bot de WhatsApp.

## Qué falta para producción
1. **Sincronización entre dispositivos** (hoy es por navegador/red local).
2. **Bot de WhatsApp** real (hoy simulado en la app).
3. **LLM** para el asistente (hoy local, con esqueleto listo).

## Opción recomendada (rápida y barata): Firebase
- **Firestore / Realtime DB** para incidentes compartidos.
- **Cloud Functions** para el webhook de WhatsApp.
- Costo casi cero en volumen de hackathon/piloto.

### Enganche del tiempo real (una función)
En el front ya está el punto de conexión en [`web/js/realtime.js`](../web/js/realtime.js):
```js
Realtime.conectarBackend(
  (evento) => db.ref('incidentes').push(evento),        // enviar
  (onEvento) => db.ref('incidentes').on('child_added',   // recibir
     (snap) => onEvento({ action: 'add', incidente: snap.val() }))
);
```
No hay que tocar nada más: el mapa, la app y el simulador ya reaccionan a ese bus.

## Bot de WhatsApp
Dos caminos:
- **WhatsApp Cloud API (Meta)**: gratis para volúmenes bajos, número propio.
- **Twilio for WhatsApp**: más fácil de arrancar, sandbox inmediato.

Flujo del webhook (Node/Express, pseudocódigo):
```js
app.post('/webhook', async (req, res) => {
  const texto = req.body.message.text;
  const r = await AI.responder(texto, 'whatsapp', req.body.from); // reusa ai.js portado
  await enviarWhatsApp(req.body.from, r.texto);
  res.sendStatus(200);
});
```
- Reutiliza `engine.js`, `reports.js` y `ai.js` (portarlos a módulos Node es directo).
- **Mantener siempre el fallback local**: si el LLM no responde, se envía la respuesta del motor.
- Ver el guion en [`../whatsapp/flujo.md`](../whatsapp/flujo.md).

## LLM (asistente natural)
En [`web/js/ai.js`](../web/js/ai.js) está `LLM = { habilitado, endpoint, modelo }`.
Para activarlo, apunta `endpoint` a un **proxy propio** hacia la API de Claude
(`claude-sonnet-5`) — nunca pongas la API key en el front. El proxy recibe `{prompt}` y
devuelve `{texto}`.

> ⚠️ Seguridad: ninguna clave/API key va en el repositorio ni en el cliente. Usa variables
> de entorno en el backend.

## Despliegue del front (PWA)
Cualquier hosting estático: **GitHub Pages**, Netlify, Vercel, Firebase Hosting.
```bash
# GitHub Pages: publicar la carpeta web/ (Settings → Pages)
```
La app es 100% estática, así que el costo de operación es prácticamente cero — argumento
clave de sostenibilidad para el jurado.
