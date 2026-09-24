# Canal WhatsApp — "Muévete CB" (bajo umbral de adopción)

WhatsApp es el canal de menor fricción en Ciudad Bolívar: casi todos lo tienen y
consume pocos datos. La **misma lógica** de la web app (motor + IA) se expone por WhatsApp.

## Arquitectura de producción
```
Usuario (WhatsApp)
   │
   ▼
WhatsApp Cloud API (Meta)  ó  Twilio for WhatsApp
   │  webhook
   ▼
Servicio Muévete CB (Node/Python)  ──► mismo engine.js + ai.js
   │
   ├─► LLM (Claude) para lenguaje natural   [opcional, con fallback local]
   └─► Base de rutas + reportes ciudadanos
```
- **Costo bajo**: un número, un webhook, hosting mínimo. Sostenible por la Alcaldía Local.
- **Reporte ciudadano** también entra por WhatsApp (el usuario escribe "reporto bloqueo en...").

## Conversación de ejemplo (guion para el pitch / demo simulada)

> **Usuario:** Hola
> **Muévete CB:** ¡Hola! 👋 Soy tu asistente de movilidad de Ciudad Bolívar. Dime a dónde vas. Ej: *"de Meissen a Paraíso"*.
>
> **Usuario:** de meissen a paraiso lo más barato
> **Muévete CB:**
> 🚀 La más económica: ~35 min · $2.000 · 1 transbordo
> 1. 🚶 A pie: Meissen → Lucero Alto · 8 min
> 2. 🚙 Jeep Alto: Lucero Alto → Paraíso Alto · 27 min (con espera) · $2.000
> 💡 Esta ruta usa transporte comunitario (jeep) que no aparece en las apps tradicionales.
>
> **Usuario:** reporto que el jeep de paraíso no está subiendo
> **Muévete CB:** Gracias 🙌 Registré la novedad. Avisaré a quienes vayan por esa ruta y buscaré alternativas.

## Menú rápido (botones de WhatsApp)
- 🔎 Planear viaje
- 📣 Reportar novedad
- 🚡 Estado del Cable
- ℹ️ Ayuda

## Notas de implementación
- El webhook reusa `Engine.opciones()` y `AI.responder()` (portar a backend).
- Mantener SIEMPRE el fallback local: si el LLM no responde, se envía la respuesta del motor.
- Cumplir política de plantillas de WhatsApp para mensajes iniciados por el negocio.
