"""Simulador del modelo de negocio de Muévete CB (costos, precios, ingresos y punto de equilibrio).

Todos los SUPUESTOS están arriba: cámbialos y vuelve a correr para ver el efecto.
Uso:  python3 scripts/simular_negocio.py
Cifras en millones de pesos (COP M) salvo que diga USD. Son estimaciones para validar en el piloto.
"""

USD_COP = 4000  # tasa de cambio de referencia

# ---------------------------------------------------------------- PRECIOS (lo que cobramos)
PRECIO_TABLERO_MES = 10.0          # COP M por localidad al mes (suscripción de la entidad pública)
PRECIO_ESTUDIO = 20.0              # COP M por estudio agregado (rango 15–40 según alcance)
PRECIO_LICENCIA_PLATAFORMA = 150.0  # COP M al año por plataforma (capa del transporte informal)

# ---------------------------------------------------------------- ESCALA (clientes por año)
LOCALIDADES = [1, 4, 8]            # localidades/municipios con tablero contratado (año 1, 2, 3)
ESTUDIOS = [3, 12.5, 30]           # estudios vendidos al año (año 1 empiezan en el mes 7)
PLATAFORMAS = [0, 1, 3]            # alianzas con licencia (Moovit, Google, Waze…)
FONDOS = [100.0, 0, 0]             # convocatorias no reembolsables (MinTIC, innovación)
VECINOS_ACTIVOS = [30_000, 110_000, 250_000]  # usuarios activos al mes al final de cada año

# ---------------------------------------------------------------- INFRAESTRUCTURA (USD al mes)
# Piloto: 1 localidad, ~30.000 vecinos activos y ~300.000 mensajes/mes al chat.
INFRA_PILOTO_USD = {
    "Servidor de la app (2 contenedores, 2 vCPU / 4 GB)": 50,
    "Base de datos PostgreSQL gestionada + copias de seguridad": 70,
    "Mapas base (proveedor de teselas; OSM no permite uso masivo)": 50,
    "IA Gemini flash-lite (~300 mil llamadas de ~1.500 tokens)": 80,
    "Dominio, certificados, monitoreo y registros": 20,
    "Bot de Telegram": 0,
}

# ---------------------------------------------------------------- COSTOS ANUALES (COP M)
COSTOS = {
    "Equipo (desarrollo, datos e IA, ventas)": [130, 300, 600],
    "Gestores comunitarios (conductores y JAC)": [36, 70, 140],
    "Infraestructura y nube (incluye IA y mapas)": [18, 40, 80],
    "Legal y protección de datos (Ley 1581)": [16, 25, 40],
    "Comercial (demos, eventos, desplazamientos)": [15, 40, 90],
    "Imprevistos": [15, 25, 50],
}


def ingresos(anio: int) -> dict[str, float]:
    return {
        "Tablero para entidades públicas": LOCALIDADES[anio] * PRECIO_TABLERO_MES * 12,
        "Estudios de movilidad (datos agregados)": ESTUDIOS[anio] * PRECIO_ESTUDIO,
        "Alianzas con plataformas": PLATAFORMAS[anio] * PRECIO_LICENCIA_PLATAFORMA,
        "Fondos no reembolsables": FONDOS[anio],
    }


def main() -> None:
    infra_usd = sum(INFRA_PILOTO_USD.values())
    infra_cop_mes = infra_usd * USD_COP / 1e6
    print("=== Infraestructura del piloto (1 localidad) ===")
    for k, v in INFRA_PILOTO_USD.items():
        print(f"  {k:<62} USD {v:>5}")
    print(f"  {'TOTAL':<62} USD {infra_usd:>5} /mes  ≈ COP {infra_cop_mes:.1f} M/mes ≈ COP {infra_cop_mes * 12:.0f} M/año")
    print(f"  Costo por vecino activo: ≈ COP {infra_usd * USD_COP / VECINOS_ACTIVOS[0]:.0f} al mes\n")

    print("=== Estado de resultados (COP M) ===")
    acumulado = 0.0
    for a in range(3):
        ing = ingresos(a)
        cos = {k: v[a] for k, v in COSTOS.items()}
        ti, tc = sum(ing.values()), sum(cos.values())
        operativo = ti - FONDOS[a] - tc
        acumulado += ti - tc
        print(f"Año {a + 1}: ingresos {ti:,.0f} · costos {tc:,.0f} · resultado {ti - tc:+,.0f} "
              f"(sin fondos {operativo:+,.0f}) · acumulado {acumulado:+,.0f}")
        for k, v in ing.items():
            if v:
                print(f"    + {k:<45} {v:>7,.0f}")
        costo_localidad = tc / LOCALIDADES[a]
        print(f"    costo por localidad atendida ≈ {costo_localidad:,.0f} · ingreso por localidad ≈ {ti / LOCALIDADES[a]:,.0f}")

    # Punto de equilibrio operativo mes a mes (ingresos se reparten parejo en el año; año 1 los estudios empiezan en el mes 7)
    print("\n=== Punto de equilibrio operativo (sin fondos) ===")
    for mes in range(1, 37):
        a = (mes - 1) // 12
        loc = LOCALIDADES[a] if a == 0 else LOCALIDADES[a - 1] + (LOCALIDADES[a] - LOCALIDADES[a - 1]) * ((mes - 1) % 12 + 1) / 12
        est = (ESTUDIOS[0] / 6 if mes >= 7 else 0) if a == 0 else ESTUDIOS[a] / 12
        ing_mes = loc * PRECIO_TABLERO_MES + est * PRECIO_ESTUDIO + PLATAFORMAS[a] * PRECIO_LICENCIA_PLATAFORMA / 12
        cos_mes = sum(v[a] for v in COSTOS.values()) / 12
        if ing_mes >= cos_mes:
            print(f"  Mes {mes}: ingresos ≈ {ing_mes:.1f} ≥ costos ≈ {cos_mes:.1f} COP M/mes → equilibrio operativo")
            break


if __name__ == "__main__":
    main()
