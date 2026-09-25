# Preguntas difíciles del jurado — respuestas listas

Cada pregunta trae una **respuesta corta para decir en voz alta** (20–30 segundos) y, debajo, los **datos de
respaldo** por si el jurado insiste. Regla de oro: responder corto, con un número y cerrar con el beneficio.
Si no sabes algo: *"Buena pregunta; eso lo validamos en el piloto"*. Nunca inventes una cifra.

---

## 1. ¿Dónde va a vivir la aplicación?

> **"En la nube. Hoy corre en tres contenedores —la base de datos, el servidor y la web— y se despliega en
> cualquier nube con un solo comando. El vecino no descarga nada: entra por Telegram o por un enlace web que
> funciona hasta sin señal."**

**Respaldo:**

- Está empaquetada con **Docker**: base de datos PostgreSQL, servidor (FastAPI) y web. Lo que corre en el
  portátil del demo es exactamente lo que se sube al servidor.
- Ya está preparada para **Railway** (una plataforma en la nube) y sirve igual en AWS, Google Cloud o Azure.
- Para el piloto recomendamos un servidor en la región (por ejemplo São Paulo) por latencia y por la
  **Ley 1581**: el responsable del tratamiento debe garantizar la seguridad si los datos se guardan fuera del país.
- La app web es **instalable** (PWA) y guarda rutas y horarios típicos para funcionar **sin señal** en la loma.

## 2. ¿Quién la costea y cómo?

> **"Por etapas. El prototipo lo pusimos nosotros. El piloto de 6 meses cuesta unos 150 millones y lo
> financiamos con convocatorias de innovación y un convenio con la Alcaldía Local. Desde ahí se sostiene
> sola: la Secretaría de Movilidad paga una suscripción por el tablero que acaban de ver. El pasajero nunca paga."**

**Respaldo:**

| Etapa | Quién paga | Con qué |
|---|---|---|
| Prototipo (hoy) | El equipo | Tiempo del equipo; la infraestructura cuesta casi cero |
| Piloto 6 meses (≈ COP 150 M) | Fondos no reembolsables (MinTIC, convocatorias de innovación) + convenio con la Alcaldía Local | Operación, gestores comunitarios, formación de conductores |
| Operación (año 1 en adelante) | Entidades públicas, empresas, universidades y plataformas | Tablero (≈ COP 10 M/mes por localidad), estudios de datos agregados y alianzas |

- **Costos año 1 ≈ COP 230 M.** La mayor parte es equipo y trabajo de campo con los conductores; la nube y la IA
  son la parte pequeña. *(Estimado, se valida en el piloto.)*
- La IA es barata porque usamos el modelo liviano de Gemini (*flash-lite*), **solo cuando las reglas no
  entienden** el mensaje, y con un tope de 5 segundos.
- **Telegram es gratis.** WhatsApp cobra por conversación: por eso el demo va por Telegram y WhatsApp queda
  para cuando haya financiación.
- Ingresos proyectados: ≈ 280 M (año 1), ≈ 880 M (año 2), ≈ 2.010 M (año 3). *(Están en la diapositiva.)*

## 3. ¿Cómo convencemos a los conductores informales de usarla?

> **"Porque les hace ganar plata. Con la app saben cuántas personas los esperan y dónde se bajan, salen
> llenos y no cortan el viaje a ciegas. No pagan nada, no pagan comisión y no tienen que aprender otra app:
> le escriben a un bot de Telegram. Entramos por los líderes de cada ruta."**

**Respaldo:**

- **Beneficio concreto:** en el tablero, el colectivo El Ensueño–Sierra Morena–Potosí tiene un **15%** de viajes
  cortados en Sierra Morena y casi la **mitad** de los pasajeros se baja antes. Si Wilson sabe eso antes de
  salir, organiza el recorrido y deja de perder pasajeros.
- **Cero fricción:** Telegram, botones grandes y frases como *"salgo 6:30 de El Ensueño a Potosí con 10 cupos"*.
- **Estrategia de entrada:** el *cabeza de ruta* o el dueño de las rutas convence a sus conductores. Piloto con
  **10 conductores** del Ensueño, gestores comunitarios en el paradero y un conductor que le cuenta a otro.
- **Reputación:** los pasajeros apartan cupo con quien cumple la hora.

## 4. La brecha legal: un vehículo particular prestando transporte público

> **"Es el punto más delicado y no lo escondemos. Nosotros no prestamos el servicio, no ponemos tarifas, no
> cobramos comisión y no manejamos pagos: somos información, como los grupos de WhatsApp que ya usan hoy.
> El transporte informal existe porque el formal no sube la loma; ignorarlo no lo desaparece. Lo que hacemos es
> volverlo visible para que el Distrito tenga evidencia para formalizarlo. Por eso el piloto se hace CON la
> Secretaría de Movilidad, no a sus espaldas."**

**Respaldo:**

- El marco es la **Ley 336 de 1996** (Estatuto Nacional de Transporte), el **Decreto 1079 de 2015** (decreto único
  del sector transporte) y el **Código Nacional de Tránsito (Ley 769 de 2002)**: prestar servicio público en
  un vehículo sin habilitación es sancionable.
- **Qué hacemos distinto:** no intermediamos ni recibimos dinero. La app informa horarios y cupos que el vecino
  ya pregunta de voz a voz.
- **El dato sirve para formalizar:** el tablero muestra dónde el informal cubre lo que el SITP no cubre
  (Potosí: **72%** de las rutas pedidas dependen del informal). Con eso la entidad decide dónde extender una ruta
  zonal o habilitar a una cooperativa o asociación.
- **Configurable:** si la entidad lo exige, el módulo de conductores se limita a vehículos habilitados o a
  asociaciones que entren en un proceso de formalización.
- **Lo honesto:** la revisión jurídica es parte del piloto.

## 5. Los conductores pueden desconfiar: "¿y si esto sirve para multarme?"

> **"Esa es la primera pregunta que nos harían y por eso lo diseñamos así: nunca entregamos datos de un
> conductor en particular a nadie, ni a las autoridades. No pedimos placa ni cédula, solo el celular, que se
> guarda cifrado. Lo que se vende es siempre agregado y anónimo. Y el conductor decide cuándo compartir su
> ubicación: solo cuando dice «ya salí»."**

**Respaldo:**

- **Identidad cifrada:** el número se guarda como un código irreversible, no en claro.
- **Anonimato en el tablero:** ningún indicador identifica a una persona y los flujos con menos de **5 personas**
  se agrupan (k-anonimato).
- **Control del conductor:** comparte ubicación solo al salir y puede pedir que borren su cuenta (Ley 1581:
  derecho de supresión).
- **Confianza de la comunidad:** la entrada es por líderes de ruta y juntas de acción comunal, no por la autoridad.

## 6. ¿La base de datos ya está lista para recoger la información?

> **"Sí. Hoy ya se guarda cada consulta de ruta —por la web y por el chat—, cada viaje de los conductores, los
> cupos apartados, dónde se baja cada pasajero, los viajes que se cortan, los desvíos y los reportes de la vía.
> Todo con fecha y hora y sin datos personales en claro. Eso es lo que alimenta el tablero."**

**Respaldo — qué guarda la base (PostgreSQL):**

| Tabla | Qué guarda |
|---|---|
| Usuarios | Código cifrado, canal (Telegram/web), rol, pasajero o conductor, reputación |
| Consultas de ruta | Origen, destino, hora, prioridad (rápido/barato), medio principal, destino final, canal |
| Viajes | Ruta, hora, cupos, ocupación, salida, si se llenó, dónde se cortó, desvíos, paradas |
| Cupos | Viaje, pasajero (cifrado) y parada donde se baja |
| Lugares guardados | Casa y paradero (con autorización) |
| Reportes | Tipo, tramo, canal (chat con IA, web o cámara), votos y verificación |

- **Destino final** (a qué zona de Bogotá sigue el viaje): en el demo es simulado; en el piloto se pregunta en el
  chat (*"¿vas más lejos?"*) o se infiere del transbordo en Portal Tunal.

## 7. ¿La IA hace los reportes que ve el administrador?

> **"Sí, de tres formas. Uno: cuando un vecino escribe «nada que baja el carro en Paraíso, hay derrumbe»,
> Gemini lo entiende y lo convierte en un reporte en el mapa; más de la mitad de los reportes llegan así.
> Dos: las cámaras generan reportes verificados solas. Y tres: en el tablero, Gemini lee los datos y redacta
> el resumen ejecutivo para el gerente."**

**Respaldo:**

- En el tablero, *"¿Por dónde llegan los reportes?"* muestra el **53%** por el chat con IA, el **42%** por la web y
  el **5%** por cámaras.
- La IA **no inventa cifras:** las calcula el sistema y Gemini solo las redacta. Si Gemini no responde, el
  tablero muestra las conclusiones calculadas.

## 8. ¿Para qué sirve el modo administrador? ¿Tiene contraseña?

> **"Tiene dos pestañas. En «Tablero de movilidad» se ve el análisis de toda la localidad con la lectura de
> la IA: es exactamente lo que le vendemos a la Secretaría. En «Moderar alertas» se verifican o rechazan los
> reportes. Y sí: se entra con una clave que solo tiene el equipo."**

**Respaldo:**

- La clave vive en la configuración del servidor (`ADMIN_API_KEY` en `.env`), **no** en el código ni en GitHub.
- La sesión queda abierta solo en esa pestaña del navegador.
- En producción: una cuenta por funcionario, con doble factor. Está en la hoja de ruta.

## 9. ¿Los datos del tablero son reales?

> **"El tablero es real y calcula en vivo; los datos de estos 60 días son simulados con patrones realistas de
> la loma, y la pantalla lo dice. En el piloto se llena solo: la app ya registra cada consulta y cada viaje."**

**Respaldo:** los datos simulados están marcados en la base (`demo:`) y se regeneran con
`bash scripts/reset_demo.sh`. El medio de transporte de cada consulta **no es inventado**: se calcula con el
mismo motor de rutas de la app.

## 10. Otras que pueden salir

- **"¿Y si la IA se equivoca?"** → No calcula rutas ni precios: entiende y redacta. Las cifras vienen del motor.
- **"¿En qué se diferencian de Moovit o Google?"** → Ellos ven la ciudad formal; nosotros la loma: jeeps,
  colectivos, cupos y cortes. Queremos ser su aliado y venderles esa capa.
- **"¿Qué pasa sin internet?"** → La app guarda los horarios típicos que aprendió y sigue funcionando.
- **"¿Cómo escala a otras localidades?"** → Cargar la red de la nueva zona (paraderos y rutas) y entrar con sus
  líderes de ruta. El resto es igual.
- **"¿Qué necesitan de nosotros?"** → Respaldo para el piloto en El Ensueño–Sierra Morena–Potosí y el
  corredor del cable, con la Alcaldía Local y la Secretaría de Movilidad.
