"""Simulador del modelo de negocio de Muévete CB: precios, costo REAL de mantener la aplicación,
ingresos, resultado y punto de equilibrio.

Todos los SUPUESTOS están arriba: cámbialos y vuelve a correr para ver el efecto.
Uso:  python3 scripts/simular_negocio.py
Montos en pesos colombianos (COP). Son estimaciones para validar en el piloto.
"""

USD_COP = 4_000  # tasa de cambio de referencia

# ---------------------------------------------------------------- PRECIOS (lo que cobramos)
PRECIO_TABLERO_MES = 10_000_000          # por localidad al mes (suscripción de la entidad pública)
PRECIO_ESTUDIO = 20_000_000              # por estudio agregado (rango 15–40 M según alcance)
PRECIO_LICENCIA_PLATAFORMA = 150_000_000  # al año por plataforma (capa del transporte informal)

# ---------------------------------------------------------------- ESCALA (por año)
LOCALIDADES = [1, 4, 8]      # localidades/municipios con tablero contratado al cierre de cada año
ESTUDIOS = [3, 12.5, 30]     # estudios vendidos al año (año 1: desde el mes 7)
PLATAFORMAS = [0, 1, 3]      # alianzas con licencia (Moovit, Google, Waze…)
FONDOS = [100_000_000, 0, 0]  # convocatorias no reembolsables (MinTIC, innovación)
VECINOS_ACTIVOS = [30_000, 110_000, 250_000]

# ---------------------------------------------------------------- MANTENER LA APLICACIÓN (COP al mes)
# A) Plataforma central: una sola instalación sirve a todas las localidades.
NUBE_BASE_USD = {  # producción con alta disponibilidad + entorno de pruebas
    "Servidores de la app (2 instancias + balanceador)": 160,
    "Base de datos gestionada con réplica y copias automáticas": 250,
    "Entorno de pruebas (staging)": 80,
    "Almacenamiento, copias de seguridad y transferencia": 60,
    "Mapas y geocodificación": 150,
    "IA Gemini (chat, análisis del tablero)": 150,
    "Monitoreo, registros y alertas": 120,
    "Seguridad: firewall web, CDN, certificados y secretos": 80,
    "Dominio y correo": 20,
}
PLATAFORMA_MES = {
    "Nube e infraestructura (detalle arriba)": sum(NUBE_BASE_USD.values()) * USD_COP,
    "Ingeniero de operación y seguridad (DevOps, medio tiempo)": 4_500_000,
    "Desarrollador de mantenimiento (correctivo y evolutivo, medio tiempo)": 4_000_000,
    "Protección de datos y cumplimiento Ley 1581 (horas)": 1_200_000,
    "Pruebas de seguridad anuales y seguro cibernético (prorrateo)": 2_000_000,
    "Licencias y herramientas (código, integración continua, oficina)": 400_000,
}
# B) Por cada localidad atendida
POR_LOCALIDAD_MES = {
    "Nube adicional (usuarios, IA y mapas)": 1_500_000,
    "Soporte a vecinos y conductores (media persona)": 1_500_000,
    "Gestor comunitario en territorio": 3_000_000,
}
WHATSAPP_POR_LOCALIDAD_MES = 600_000  # desde el año 2 (plataforma + mensajes de aviso)
GESTORES_EXTRA_ANIO1 = 1              # el primer año hacen falta 2 gestores para arrancar
# C) Crecimiento: equipo de producto y comercial/administración (COP al mes por año)
PRODUCTO_MES = [10_000_000, 25_000_000, 45_000_000]   # desarrollo nuevo, datos e IA
COMERCIAL_MES = [4_000_000, 10_000_000, 18_000_000]   # ventas, contador, legal, desplazamientos
PLATAFORMA_EXTRA_MES = [0, 0, 5_600_000]              # año 3: operación de tiempo completo
IMPREVISTOS = 0.10


def fmt(n: float) -> str:
    return f"$ {n:,.0f}".replace(",", ".")


def costo_mantener_mes(anio: int, localidades: int) -> float:
    base = sum(PLATAFORMA_MES.values()) + PLATAFORMA_EXTRA_MES[anio]
    por_loc = sum(POR_LOCALIDAD_MES.values()) + (WHATSAPP_POR_LOCALIDAD_MES if anio > 0 else 0)
    extra = GESTORES_EXTRA_ANIO1 * POR_LOCALIDAD_MES["Gestor comunitario en territorio"] if anio == 0 else 0
    return (base + localidades * por_loc + extra) * (1 + IMPREVISTOS)


def costos_anio(anio: int) -> dict[str, float]:
    return {
        "Mantener la aplicación (plataforma, soporte, gestores, nube)": costo_mantener_mes(anio, LOCALIDADES[anio]) * 12,
        "Equipo de producto (desarrollo nuevo, datos e IA)": PRODUCTO_MES[anio] * 12 * (1 + IMPREVISTOS),
        "Comercial y administración": COMERCIAL_MES[anio] * 12 * (1 + IMPREVISTOS),
    }


def ingresos_anio(anio: int) -> dict[str, float]:
    return {
        "Tablero para entidades públicas": LOCALIDADES[anio] * PRECIO_TABLERO_MES * 12,
        "Estudios de movilidad": ESTUDIOS[anio] * PRECIO_ESTUDIO,
        "Alianzas con plataformas": PLATAFORMAS[anio] * PRECIO_LICENCIA_PLATAFORMA,
        "Fondos no reembolsables": FONDOS[anio],
    }


def main() -> None:
    print("=== Mantener la aplicación: 1 localidad (piloto) ===")
    nube = sum(NUBE_BASE_USD.values())
    for k, v in NUBE_BASE_USD.items():
        print(f"   nube · {k:<58} USD {v:>5}  {fmt(v * USD_COP):>14}")
    for k, v in PLATAFORMA_MES.items():
        print(f"  {k:<66} {fmt(v):>14}")
    for k, v in POR_LOCALIDAD_MES.items():
        print(f"  {k:<66} {fmt(v):>14}")
    print(f"  {'Gestor adicional de arranque (año 1)':<66} {fmt(GESTORES_EXTRA_ANIO1 * 3_000_000):>14}")
    m = costo_mantener_mes(0, 1)
    print(f"  {'TOTAL con 10% de imprevistos':<66} {fmt(m):>14} al mes · {fmt(m * 12)} al año")
    print(f"  Nube: USD {nube:,}/mes = {fmt(nube * USD_COP)} · por vecino activo: {fmt(m / VECINOS_ACTIVOS[0])} al mes\n")

    print("=== Estado de resultados ===")
    acumulado = 0.0
    for a in range(3):
        ing, cos = ingresos_anio(a), costos_anio(a)
        ti, tc = sum(ing.values()), sum(cos.values())
        acumulado += ti - tc
        print(f"Año {a + 1} ({LOCALIDADES[a]} localidades): ingresos {fmt(ti)} · costos {fmt(tc)} · "
              f"resultado {fmt(ti - tc)} · acumulado {fmt(acumulado)}")
        for k, v in cos.items():
            print(f"    - {k:<60} {fmt(v):>16}")
        print(f"    mantener la app por localidad: {fmt(costo_mantener_mes(a, LOCALIDADES[a]) / LOCALIDADES[a])} al mes")

    print("\n=== Punto de equilibrio mensual ===")
    for mes in range(1, 37):
        a = (mes - 1) // 12
        loc = 1 if a == 0 else LOCALIDADES[a - 1] + (LOCALIDADES[a] - LOCALIDADES[a - 1]) * ((mes - 1) % 12 + 1) / 12
        est = (ESTUDIOS[0] / 6 if mes >= 7 else 0) if a == 0 else ESTUDIOS[a] / 12
        ing = loc * PRECIO_TABLERO_MES + est * PRECIO_ESTUDIO + PLATAFORMAS[a] * PRECIO_LICENCIA_PLATAFORMA / 12
        cos = costo_mantener_mes(a, loc) + (PRODUCTO_MES[a] + COMERCIAL_MES[a]) * (1 + IMPREVISTOS)
        if ing >= cos:
            print(f"  Mes {mes}: ingresos {fmt(ing)} ≥ costos {fmt(cos)} → equilibrio")
            break
    else:
        print("  No se alcanza en 36 meses con estos supuestos")


if __name__ == "__main__":
    main()
