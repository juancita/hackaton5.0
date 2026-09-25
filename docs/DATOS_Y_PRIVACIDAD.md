# Tratamiento de datos y privacidad — Muévete CB

> Resumen para el equipo y para responder al jurado. No es asesoría legal: antes de un piloto real,
> validar con un abogado y registrar la base de datos donde corresponda.

## Marco legal (Colombia)
- **Ley 1581 de 2012** (Habeas Data) y **Decreto 1377 de 2013**: se requiere **autorización previa,
  expresa e informada**, finalidad clara, y derechos del titular a **conocer, actualizar, rectificar y
  suprimir** sus datos.
- Si la base supera los umbrales, registro en el **RNBD** (Superintendencia de Industria y Comercio).

## Qué hacemos
| Principio | Cómo se cumple en el producto |
|---|---|
| **Autorización** | El login muestra el aviso de la Ley 1581; al entrar, la persona autoriza. En Telegram, compartir el número es un acto voluntario (botón). |
| **Minimización** | Solo pedimos **celular + un nombre** (puede ser un apodo). Sin cédula, sin correo, sin contraseña. |
| **Seudonimización** | El número **nunca** se guarda en claro: se guarda `sha256(sal + número)`. Tampoco guardamos el id de Telegram en claro. |
| **Finalidad** | Reconocer a la persona entre app y chat, organizar viajes/cupos y mejorar la movilidad del territorio. |
| **Datos agregados** | Lo que se comparte o vende a terceros son **estadísticas agregadas y anónimas** (p. ej. "300 personas piden Meissen→Paraíso entre 5 y 6 a.m."), nunca datos de una persona. |
| **Cámaras** | La cámara solo envía un **nivel de congestión**. No se transmite video ni placas. |
| **Ubicación** | Solo cuando la persona la comparte (reportar, "Ya salí", origen por GPS). |
| **Supresión** | Derecho a pedir borrado (a implementar: comando "borrar mis datos" en app y Telegram). |

## Importante (honestidad técnica)
Un hash con sal es **seudónimo, no anónimo**: quien tenga la sal y el número podría re-identificar.
Por eso la sal (`ID_SALT`) es un secreto de servidor y nunca sale del backend.

## Cómo explicarlo en el pitch (15 segundos)
> *"No pedimos cédula ni contraseña: solo el celular, y lo guardamos cifrado. Cumplimos la Ley 1581
> de Habeas Data. Lo que vendemos son estadísticas agregadas y anónimas de movilidad, nunca datos de
> una persona. Y las cámaras solo mandan un número: cuántos carros hay, no quién pasa."*
