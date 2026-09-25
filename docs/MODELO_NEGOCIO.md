# Modelo de negocio, costo real de mantener la aplicación y cuándo vendemos los datos

> Todas las cifras salen del simulador `scripts/simular_negocio.py` (supuestos arriba del archivo: cámbialos y
> vuelve a correrlo). Son **estimaciones para validar en el piloto**. Pesos colombianos; 1 USD ≈ $ 4.000.

## 1. En una frase

> **"El pasajero y el conductor nunca pagan. Cobramos a quien necesita entender cómo se mueve la loma: la
> Secretaría de Movilidad y las alcaldías (tablero), empresas y universidades (estudios) y plataformas como
> Moovit o Google (licencia de la capa informal). Mantener la aplicación bien hecha cuesta unos 28 millones al
> mes; por eso invertimos dos años y somos rentables desde el tercero."**

## 2. ¿Cuánto cobramos?

| Qué vendemos | A quién | Precio | Qué recibe |
|---|---|---|---|
| **Tablero de movilidad** (suscripción) | Secretaría de Movilidad, Alcaldía Local, TransMilenio | **$ 10.000.000 al mes por localidad** ($ 120.000.000 al año) | Tablero en vivo, descarga de datos, resumen mensual con IA y alertas de cierres |
| **Estudios de movilidad** (por proyecto) | Operadores del SITP, constructoras, centros comerciales, universidades | **$ 15.000.000 a $ 40.000.000 por estudio** (promedio $ 20.000.000) | Informe agregado y anónimo: demanda por hora, orígenes y destinos, rutas informales |
| **Licencia de la capa informal** | Moovit, Google, Waze | **$ 150.000.000 al año por plataforma y ciudad** | Rutas, horarios típicos y cupos del informal, a cambio de sus buses en tiempo real |
| App para vecinos y conductores | — | **Gratis, siempre** | Sin publicidad y sin plan de pago |

**¿Por qué $ 10.000.000 al mes es razonable para una entidad?** Hoy la información de demanda sale de encuestas
de movilidad que cuestan mucho más, se hacen cada varios años y **no ven el transporte informal**.

## 3. ¿Cuánto cuesta mantener la aplicación? (piloto: 1 localidad, ~30.000 vecinos)

Una aplicación en producción no es solo el servidor: hay que operarla, protegerla, corregirla, mejorarla y
atender a la gente.

| Rubro mensual | COP al mes |
|---|---|
| **Nube en producción** (detalle abajo) | **$ 4.280.000** |
| Operación y seguridad: ingeniero DevOps, medio tiempo | $ 4.500.000 |
| Mantenimiento correctivo y evolutivo: desarrollador, medio tiempo | $ 4.000.000 |
| Protección de datos y cumplimiento de la Ley 1581 (horas) | $ 1.200.000 |
| Pruebas de seguridad anuales y seguro cibernético (prorrateo) | $ 2.000.000 |
| Licencias y herramientas (código, integración continua, oficina) | $ 400.000 |
| Nube adicional de la localidad (usuarios, IA, mapas) | $ 1.500.000 |
| Soporte a vecinos y conductores (media persona) | $ 1.500.000 |
| Gestores comunitarios en territorio (2 en el arranque) | $ 6.000.000 |
| Imprevistos (10%) | $ 2.538.000 |
| **Total al mes** | **$ 27.918.000** |
| **Total al año** | **$ 335.016.000** |

**Detalle de la nube en producción (USD al mes):**

| Componente | USD | COP |
|---|---|---|
| Servidores de la app (2 instancias + balanceador: si uno cae, sigue el otro) | 160 | $ 640.000 |
| Base de datos gestionada con réplica y copias automáticas | 250 | $ 1.000.000 |
| Entorno de pruebas (staging) | 80 | $ 320.000 |
| Almacenamiento, copias de seguridad y transferencia | 60 | $ 240.000 |
| Mapas y geocodificación | 150 | $ 600.000 |
| IA Gemini (chat y análisis del tablero) | 150 | $ 600.000 |
| Monitoreo, registros y alertas | 120 | $ 480.000 |
| Seguridad: firewall web, CDN, certificados y secretos | 80 | $ 320.000 |
| Dominio y correo | 20 | $ 80.000 |
| **Total** | **1.070** | **$ 4.280.000** |

- **La nube es solo el 15%** del costo de mantener la app; el resto es gente.
- **Economía de escala:** la plataforma central se comparte. Con 4 localidades mantener cuesta
  **$ 11.764.500 por localidad al mes**; con 8, **$ 10.282.250**.
- **WhatsApp (desde el año 2):** ≈ $ 600.000 por localidad al mes (plataforma y mensajes de aviso). Responder a
  quien escribe no tiene costo por mensaje en el esquema actual de Meta; los avisos que inicia la app sí.
  *(Verificar la tarifa vigente.)* **Telegram es gratis.**
- *Los precios de la nube y de Gemini son de referencia; se confirman con la cotización del proveedor.*

## 4. Costos totales por año

| Rubro | Año 1 (1 localidad) | Año 2 (4) | Año 3 (8) |
|---|---|---|---|
| Mantener la aplicación (plataforma, soporte, gestores, nube) | $ 335.016.000 | $ 564.696.000 | $ 987.096.000 |
| Equipo de producto (desarrollo nuevo, datos e IA) | $ 132.000.000 | $ 330.000.000 | $ 594.000.000 |
| Comercial y administración (ventas, contador, legal) | $ 52.800.000 | $ 132.000.000 | $ 237.600.000 |
| **Total** | **$ 519.816.000** | **$ 1.026.696.000** | **$ 1.818.696.000** |

## 5. Ingresos y resultado

| | Año 1 | Año 2 | Año 3 |
|---|---|---|---|
| Tablero para entidades (1 → 4 → 8 localidades) | $ 120.000.000 | $ 480.000.000 | $ 960.000.000 |
| Estudios de movilidad (3 → 12 → 30) | $ 60.000.000 | $ 250.000.000 | $ 600.000.000 |
| Alianzas con plataformas (0 → 1 → 3) | — | $ 150.000.000 | $ 450.000.000 |
| Fondos no reembolsables | $ 100.000.000 | — | — |
| **Ingresos** | **$ 280.000.000** | **$ 880.000.000** | **$ 2.010.000.000** |
| **Costos** | **$ 519.816.000** | **$ 1.026.696.000** | **$ 1.818.696.000** |
| **Resultado** | **−$ 239.816.000** | **−$ 146.696.000** | **+$ 191.304.000** |
| Acumulado | −$ 239.816.000 | −$ 386.512.000 | −$ 195.208.000 |

- **Equilibrio mensual en el mes 25**: los ingresos del mes (≈ $ 130.800.000) superan los costos del mes
  (≈ $ 124.900.000).
- **Necesidad de financiación: ≈ $ 400.000.000** (la pérdida acumulada máxima es $ 386.512.000, al cierre del
  año 2), entre fondos de innovación, el convenio del piloto e inversión.
- **Piloto de 6 meses ≈ $ 260.000.000** (mantener la app + producto + comercial durante 6 meses).

## 6. ¿Cuándo podemos vender los datos que recolectamos?

| Momento | Qué pasa | ¿Se vende? |
|---|---|---|
| **Mes 0** | Convenio del piloto con la Alcaldía Local y fondos de innovación | La Alcaldía es el **primer cliente del tablero** ($ 10.000.000 al mes) |
| **Meses 1–3** | Entran conductores y los primeros miles de vecinos; se acumulan los datos | No a terceros: aún no hay suficientes datos |
| **Meses 4–6** | Con 3 meses de historia ya se ven los patrones semanales y hay volumen para anonimizar | Tablero completo validado con la Alcaldía |
| **Meses 7–12** | **Primeros estudios a terceros** (operadores, comercio, universidades) | **Sí: 3 estudios ≈ $ 60.000.000** |
| **Año 2** | 4 localidades de ladera y la primera alianza con una plataforma | Tablero + estudios + licencia |
| **Año 3** | 8 localidades o municipios | Las tres líneas a escala: la operación es rentable |

**Condiciones para vender un dato (siempre):**
1. **Agregado y anónimo**: nada que identifique a una persona. Los grupos de menos de 5 personas no se muestran.
2. **Autorizado**: el aviso de privacidad del ingreso informa el uso estadístico (Ley 1581 de 2012).
3. **Nunca** se venden teléfonos, ubicaciones individuales ni datos de un conductor en particular.

## 7. Respuestas cortas para el jurado

- **"¿Cuánto cuesta mantenerla?"** → *"Bien hecha, unos 28 millones al mes con una localidad. Solo 4,3 son
  nube; el resto es gente: quien la opera y la protege, quien la mantiene, quien atiende a los usuarios y los
  gestores en territorio. Con 8 localidades baja a unos 10 millones por localidad."*
- **"¿Cuánto cobran?"** → *"10 millones al mes por localidad a la entidad, de 15 a 40 millones por estudio y
  150 millones al año por plataforma. El pasajero y el conductor nunca pagan."*
- **"¿Cuándo venden los datos?"** → *"La Alcaldía paga el tablero desde el primer mes del piloto. A terceros
  vendemos desde el mes 7, cuando hay 3 meses de datos y suficiente volumen para que sean anónimos."*
- **"¿Cuándo son rentables?"** → *"Somos realistas: dos años de inversión. En el mes 25 la operación se paga
  sola y el tercer año deja unos 190 millones."*
- **"¿Cuánto necesitan?"** → *"El piloto de 6 meses cuesta unos 260 millones; para llegar al equilibrio
  necesitamos unos 400 millones entre fondos de innovación, el convenio con la Alcaldía e inversión."*
