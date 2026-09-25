# Modelo de negocio, costos y cuándo vendemos los datos

> Todas las cifras salen del simulador `scripts/simular_negocio.py` (supuestos arriba del archivo: cámbialos y
> vuelve a correrlo). Son **estimaciones para validar en el piloto**. Pesos colombianos; 1 USD ≈ COP 4.000.

## 1. En una frase

> **"El pasajero nunca paga. Cobramos a quien necesita entender cómo se mueve la loma: la Secretaría de
> Movilidad y las alcaldías (tablero), empresas y universidades (estudios) y plataformas como Moovit o Google
> (licencia de la capa informal). Mantener la plataforma cuesta menos de 40 pesos al mes por vecino."**

## 2. ¿Cuánto cobramos?

| Qué vendemos | A quién | Precio | Qué recibe |
|---|---|---|---|
| **Tablero de movilidad** (suscripción) | Secretaría de Movilidad, Alcaldía Local, TransMilenio | **COP 10 M al mes por localidad** (120 M/año) | El tablero en vivo, descarga de datos, resumen mensual con IA y alertas de cierres |
| **Estudios de movilidad** (por proyecto) | Operadores del SITP, constructoras, centros comerciales, universidades | **COP 15–40 M por estudio** (promedio 20 M) | Informe agregado y anónimo: demanda por hora, orígenes y destinos, rutas informales |
| **Licencia de la capa informal** | Moovit, Google, Waze | **COP 150 M al año por plataforma y ciudad** | Rutas, horarios típicos y cupos del transporte informal, más intercambio de sus buses en tiempo real |
| App para vecinos y conductores | — | **Gratis, siempre** | Sin publicidad y sin plan de pago |

**¿Por qué 10 M al mes es razonable para una entidad?** Hoy la información de demanda sale de encuestas de
movilidad que cuestan mucho más, se hacen cada varios años y **no ven el transporte informal**. Nosotros la
entregamos todos los días, con el informal incluido.

## 3. ¿Cuánto cuesta mantener la infraestructura?

**Piloto: 1 localidad, unos 30.000 vecinos activos y unos 300.000 mensajes al chat al mes.**

| Componente | USD/mes |
|---|---|
| Servidor de la app (2 contenedores, 2 vCPU / 4 GB) | 50 |
| Base de datos PostgreSQL gestionada + copias de seguridad | 70 |
| Mapas base (proveedor de mapas; el servicio gratuito de OpenStreetMap no permite uso masivo) | 50 |
| IA Gemini flash-lite (~300 mil llamadas de ~1.500 tokens) | 80 |
| Dominio, certificados, monitoreo y registros | 20 |
| Bot de Telegram | 0 |
| **Total** | **≈ 270 (≈ COP 1,1 M al mes; ≈ 13 M al año)** |

- **Por vecino: ≈ COP 36 al mes.**
- Con 8 localidades (año 3) la nube sube a ≈ COP 80 M al año: crece menos que los usuarios.
- **La IA es barata** porque usamos el modelo liviano y solo cuando las reglas no entienden, con un tope de 5 s.
- **WhatsApp (futuro):** responder a quien escribe no tiene costo por mensaje en el esquema actual de Meta; los
  avisos que inicia la app (plantillas) sí se cobran. *(Verificar la tarifa vigente antes de activarlo.)*
- *Los precios de la nube y de Gemini son de referencia; se confirman con la cotización del proveedor.*

## 4. Costos totales por año (COP M)

| Rubro | Año 1 | Año 2 | Año 3 |
|---|---|---|---|
| Equipo (desarrollo, datos e IA, ventas) | 130 | 300 | 600 |
| Gestores comunitarios (conductores y JAC) | 36 | 70 | 140 |
| Infraestructura y nube (incluye IA y mapas) | 18 | 40 | 80 |
| Legal y protección de datos (Ley 1581) | 16 | 25 | 40 |
| Comercial (demos, eventos, desplazamientos) | 15 | 40 | 90 |
| Imprevistos | 15 | 25 | 50 |
| **Total** | **230** | **500** | **1.000** |

El costo grande es la **gente**, no la tecnología: la nube es menos del 10%.

## 5. Ingresos y resultado (COP M)

| | Año 1 | Año 2 | Año 3 |
|---|---|---|---|
| Localidades con tablero | 1 | 4 | 8 |
| Tablero para entidades | 120 | 480 | 960 |
| Estudios de movilidad | 60 (3) | 250 (~12) | 600 (30) |
| Alianzas con plataformas | — | 150 (1) | 450 (3) |
| Fondos no reembolsables | 100 | — | — |
| **Ingresos** | **280** | **880** | **2.010** |
| **Costos** | **230** | **500** | **1.000** |
| **Resultado** | **+50** (−50 sin fondos) | **+380** | **+1.010** |

- **Equilibrio mensual desde el mes 7**, cuando empiezan los estudios: ≈ 20 M de ingresos contra ≈ 19 M de costos.
- Los fondos no reembolsables cubren la pérdida del primer semestre, mientras se acumulan los datos.

## 6. ¿Cuándo podemos vender los datos que recolectamos?

| Momento | Qué pasa | ¿Se vende? |
|---|---|---|
| **Mes 0** | Convenio del piloto con la Alcaldía Local y fondos de innovación | La Alcaldía es el **primer cliente del tablero** (10 M/mes) |
| **Meses 1–3** | Entran 10–30 conductores y los primeros miles de vecinos; se acumulan los datos | No a terceros: aún no hay suficientes datos |
| **Meses 4–6** | Con 3 meses de historia ya se ven los patrones semanales y hay volumen para anonimizar | Tablero completo validado con la Alcaldía |
| **Meses 7–12** | **Primeros estudios a terceros** (operadores, comercio, universidades) | **Sí: 3 estudios ≈ 60 M** |
| **Año 2** | 4 localidades de ladera y la primera alianza con una plataforma | Tablero + estudios + licencia |
| **Año 3** | 8 localidades o municipios (Soacha, otras ciudades de ladera) | Las tres líneas a escala |

**Condiciones para vender un dato (siempre):**
1. **Agregado y anónimo**: nada que identifique a una persona. Los grupos de menos de 5 personas no se muestran.
2. **Autorizado**: el aviso de privacidad del ingreso informa el uso estadístico (Ley 1581 de 2012).
3. **Nunca** se venden teléfonos, ubicaciones individuales ni datos de un conductor en particular.

## 7. Respuestas cortas para el jurado

- **"¿Cuánto cuesta mantenerla?"** → *"Unos 270 dólares al mes para toda una localidad: menos de 40 pesos por
  vecino. Lo caro es la gente en territorio, no la tecnología."*
- **"¿Cuánto cobran?"** → *"10 millones al mes por localidad a la entidad, 15 a 40 millones por estudio y 150
  millones al año por plataforma. El pasajero y el conductor nunca pagan."*
- **"¿Cuándo venden los datos?"** → *"La Alcaldía paga el tablero desde el primer mes del piloto. A terceros
  vendemos desde el mes 7, cuando hay 3 meses de datos y suficiente volumen para que sean anónimos."*
- **"¿Cuándo son rentables?"** → *"Desde el mes 7 cada mes se paga solo; el primer año cierra en +50 millones
  con los fondos del piloto y el segundo en +380."*
- **"¿Y si la entidad no paga?"** → *"Tenemos otras dos líneas: estudios para empresas y la licencia a
  plataformas. Y el piloto se financia con fondos de innovación."*
