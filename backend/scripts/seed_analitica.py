"""Datos FICTICIOS para el tablero de analítica del administrador (demo del producto para entidades).

Genera ~60 días de uso simulado con patrones realistas de Ciudad Bolívar:
  · ~1.400 vecinos (Telegram y web) con barrio, hora de salida y destino habitual;
  · ~30 conductores informales con viajes diarios, ocupación por hora y cortes a mitad de camino;
  · consultas de ruta: salida de madrugada hacia Portal Tunal, Autopista Sur, Av. Boyacá y Av. Villavicencio,
    regreso en la tarde y a qué zona de Bogotá sigue cada viaje (destino final);
  · reportes históricos (lluvias con derrumbes en la parte alta, un día de manifestación en la Distrital).

El medio de cada consulta NO se inventa: se calcula con el mismo motor de rutas de la app.
Todo lo ficticio queda marcado: usuarios `demo:*` e incidentes `demo-*`. Es idempotente: borra lo ficticio
anterior y lo vuelve a generar (fechas relativas a hoy). No toca usuarios ni datos reales.

Uso (desde backend/):  python -m scripts.seed_analitica
En Docker:             docker compose exec backend python -m scripts.seed_analitica
"""

import json
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, insert, or_, select

from app.adapters.outbound.pg.db import make_session_factory
from app.adapters.outbound.pg.tables import (
    IncidentRow,
    ReporterRow,
    ReportRow,
    RouteEventRow,
    SeatRequestRow,
    TripRow,
    VoteRow,
)
from app.config import get_settings
from app.container import build_container
from app.domain.analytics import BOGOTA, modo_principal
from app.domain.reports import utcnow

DIAS = 60
N_USUARIOS = 1400
SEMILLA = 2026

# Barrio de residencia (peso ~ población que usa la app)
BARRIOS = {
    "paraiso": 9, "mirador": 6, "lucero": 10, "jerusalen": 8, "potosi": 9, "sierramorena": 9,
    "arborizadora": 7, "bellaflor": 6, "caracoli": 6, "santodomingo": 5, "tesoro": 5, "candelaria": 6,
    "perdomo": 5, "meissen": 4, "manitas": 5, "juanpablo": 4, "quiba": 2, "mochuelo": 2, "pasquilla": 1,
    "quibaalta": 1, "mochueloalto": 1,
}
CABLE = {"paraiso", "mirador", "manitas", "juanpablo", "lucero", "bellaflor"}
ENSUENO = {"potosi", "sierramorena"}
AUTOPISTA = {"caracoli", "santodomingo", "perdomo"}
RURAL = {"quiba", "mochuelo", "pasquilla", "quibaalta", "mochueloalto"}


def salida_para(barrio: str) -> dict[str, int]:
    if barrio in CABLE:
        return {"tunal": 62, "meissen": 12, "candelaria": 10, "estperdomo": 8, "udtecno": 8}
    if barrio in ENSUENO:
        return {"ensueno": 45, "tunal": 18, "estperdomo": 17, "udtecno": 12, "candelaria": 8}
    if barrio in AUTOPISTA:
        return {"estperdomo": 55, "ensueno": 15, "tunal": 12, "udtecno": 18}
    if barrio in RURAL:
        return {"tunal": 70, "meissen": 30}
    return {"tunal": 35, "meissen": 22, "candelaria": 18, "estperdomo": 15, "udtecno": 10}


DESTINO_FINAL = {
    "tunal": {"centro": 30, "norte": 26, "industrial": 13, "kennedy": 8, "usme": 13, "local": 10},
    "estperdomo": {"soacha": 28, "centro": 22, "kennedy": 22, "industrial": 20, "local": 8},
    "ensueno": {"kennedy": 30, "soacha": 18, "industrial": 12, "local": 40},
    "meissen": {"local": 35, "kennedy": 30, "usme": 35},
    "hospital": {"local": 80, "kennedy": 10, "usme": 10},
    "candelaria": {"local": 30, "kennedy": 35, "industrial": 35},
    "udtecno": {"local": 70, "kennedy": 15, "industrial": 15},
}
INTERNOS = {"plaza": 30, "hospital": 30, "sena": 15, "ensueno": 25}

# Conductores ficticios por ruta informal (nombre de la ruta en la red → cuántos)
CONDUCTORES_POR_RUTA = {
    "Colectivo El Ensueño - Sierra Morena - Potosí": 5, "Jeep Paraíso": 4, "Colectivo Lucero": 3,
    "Colectivo Tunal - Lucero": 4, "Colectivo Santo Domingo": 3, "Colectivo Caracolí": 3,
    "Colectivo Jerusalén": 2, "Colectivo El Tesoro": 2, "Jeep Bella Flor": 2, "Jeep Alto": 1,
    "Jeep Quiba": 1, "Veredal Mochuelo": 1, "Veredal Pasquilla": 1,
}
HORAS_CONDUCTOR = ["05:00", "05:30", "06:00", "06:30", "07:15", "09:30", "12:30", "16:30", "17:30", "18:15", "19:00"]
NOTAS = {
    "trancon": ["Trancón fuerte", "No avanza nada", "Represado desde la bajada"],
    "lleno": ["El bus pasó lleno y no paró", "Cable con fila larga", "Jeep lleno desde arriba"],
    "derrumbe": ["Derrumbe por la lluvia", "Cayó tierra en la vía", "Paso a un solo carril por derrumbe"],
    "bloqueo": ["Manifestación en la Distrital", "Vía bloqueada por protesta", "Tropel, no pasan buses"],
    "sinservicio": ["No ha pasado ninguna ruta", "El SITP no está entrando", "Sin jeeps en el paradero"],
    "novedad": ["Cambiaron el paradero", "Obra en la vía", "Desvío por pavimentación"],
}
TIPOS_NORMALES = {"trancon": 34, "lleno": 22, "sinservicio": 14, "novedad": 18, "derrumbe": 7, "bloqueo": 5}


def elegir(r: random.Random, pesos: dict):
    return r.choices(list(pesos), weights=list(pesos.values()))[0]


def en_hora(dia_local: datetime, horas: float) -> datetime:
    """Día local (00:00 Bogotá) + horas decimales → datetime UTC-aware."""
    return dia_local + timedelta(hours=max(0.0, min(23.98, horas)))


class Generador:
    def __init__(self, c, ahora: datetime, semilla: int = SEMILLA, dias: int = DIAS):
        self.c, self.net, self.ahora, self.dias = c, c.network, ahora, dias
        self.r = random.Random(semilla)
        self._planes: dict = {}
        self.filas: dict[str, list[dict]] = {k: [] for k in ("reporters", "events", "trips", "seats", "incidents", "reports")}
        hoy = ahora.astimezone(BOGOTA).replace(hour=0, minute=0, second=0, microsecond=0)
        self.dias_locales = [hoy - timedelta(days=d) for d in range(dias - 1, -1, -1)]
        # Días especiales: manifestación en la Distrital (un martes o miércoles reciente) y lluvias fuertes
        candidatos = [i for i, d in enumerate(self.dias_locales) if d.weekday() in (1, 2) and 8 <= dias - i <= 16]
        self.protesta = candidatos[0] if candidatos else dias - 12
        self.lluvias = set(self.r.sample(range(dias - 3), 7))

    # --- motor de rutas: el medio de cada consulta sale del mismo algoritmo de la app
    def modo_de(self, o: str, d: str, prioridad: str) -> str | None:
        clave = (o, d, prioridad)
        if clave not in self._planes:
            try:
                plan = self.c.trip.ejecutar(o, d, prioridad)
                alternos = [modo_principal(plan.model_copy(update={"recomendada": i})) for i in range(len(plan.opciones))]
                self._planes[clave] = (modo_principal(plan), [m for m in alternos if m])
            except Exception:  # noqa: BLE001
                self._planes[clave] = (None, [])
        principal, alternos = self._planes[clave]
        if alternos and self.r.random() < 0.22:  # parte de la gente elige otra opción de las que se le ofrecen
            return self.r.choice(alternos)
        return principal

    def adopcion(self, i: int) -> float:
        return 0.38 + 0.62 * (i / max(1, self.dias - 1)) ** 0.85

    def generar(self) -> dict[str, list[dict]]:
        r = self.r
        # --- Vecinos
        usuarios = []
        for n in range(N_USUARIOS):
            barrio = elegir(r, BARRIOS)
            salida = elegir(r, salida_para(barrio))
            estudiante = salida in ("udtecno",) or r.random() < 0.08
            u = {
                "id": f"demo:u{n:04d}", "barrio": barrio, "salida": salida,
                "final": elegir(r, DESTINO_FINAL[salida]), "canal": "telegram" if r.random() < 0.58 else "web",
                "hora_sale": r.gauss(6.6 if estudiante else 5.7, 0.55), "hora_vuelve": r.gauss(18.2, 1.1),
                "prioridad": elegir(r, {"barato": 55, "rapido": 38, "transbordos": 7} if barrio in RURAL | ENSUENO
                                    else {"rapido": 55, "barato": 38, "transbordos": 7}),
                "alta": r.random(),  # desde qué punto del periodo usa la app (adopción)
                "frecuencia": r.uniform(0.18, 0.55),
            }
            usuarios.append(u)
            self.filas["reporters"].append({
                "id": u["id"], "canal": u["canal"], "rol": "usuario", "nombre": None, "modo": "pasajero",
                "aciertos": r.randint(0, 6), "fallos": r.randint(0, 1),
                "creado_en": self.ahora - timedelta(days=self.dias * (1 - u["alta"]) + 1), "ultimo_en": self.ahora,
            })

        # --- Consultas de ruta
        for i, dia in enumerate(self.dias_locales):
            fin_de_semana = {5: 0.62, 6: 0.42}.get(dia.weekday(), 1.0)
            for u in usuarios:
                if u["alta"] > self.adopcion(i) + 0.05 or r.random() > u["frecuencia"] * fin_de_semana:
                    continue
                pri = u["prioridad"] if r.random() < 0.8 else elegir(r, {"rapido": 50, "barato": 42, "transbordos": 8})
                salida, final = u["salida"], u["final"]
                if i == self.protesta and salida in ("udtecno", "candelaria") and r.random() < 0.7:
                    salida, final = "ensueno", "kennedy"
                h = u["hora_sale"] + r.gauss(0, 0.35) + (1.4 if dia.weekday() >= 5 else 0)
                self.evento(u, u["barrio"], salida, final, pri, en_hora(dia, h), i)
                if r.random() < 0.55:
                    self.evento(u, salida, u["barrio"], None, pri, en_hora(dia, u["hora_vuelve"] + r.gauss(0, 0.5)), i)
                if r.random() < 0.12:
                    destino = elegir(r, INTERNOS)
                    if destino != u["barrio"]:
                        self.evento(u, u["barrio"], destino, "local", pri, en_hora(dia, r.uniform(9.5, 15.5)), i)

        # --- Conductores y viajes
        tramos_inf = [t for t in self.net.tramos if not self.net.modos[t.modo].formal]
        pasajeros = [u["id"] for u in usuarios]
        n = 0
        for ruta, cuantos in CONDUCTORES_POR_RUTA.items():
            tramo = next((t for t in tramos_inf if t.ruta == ruta), None)
            if not tramo:
                continue
            if ruta.startswith("Colectivo El Ensueño"):
                alto, bajo = "potosi", "ensueno"
            else:
                zonas = {"baja": 0, "media": 1, "alta": 2, "rural": 3}
                a, b = self.net.lugar(tramo.de), self.net.lugar(tramo.a)
                alto, bajo = (tramo.de, tramo.a) if zonas.get(a.zona, 1) >= zonas.get(b.zona, 1) else (tramo.a, tramo.de)
            cupos = {"jeep": 8, "colectivo": 12, "veredal": 14}.get(tramo.modo, 10)
            for k in range(cuantos):
                n += 1
                did = f"demo:c{n:02d}"
                nombre = f"Conductor {n:02d}"
                self.filas["reporters"].append({
                    "id": did, "canal": "telegram", "rol": "usuario", "nombre": nombre, "modo": "conductor",
                    "aciertos": r.randint(3, 15), "fallos": 0,
                    "creado_en": self.ahora - timedelta(days=self.dias + 5), "ultimo_en": self.ahora,
                })
                horas = sorted(r.sample(HORAS_CONDUCTOR[:5], 3) + r.sample(HORAS_CONDUCTOR[5:], 2))
                for i, dia in enumerate(self.dias_locales):
                    factor = {5: 0.7, 6: 0.35}.get(dia.weekday(), 1.0) * (0.6 + 0.4 * self.adopcion(i))
                    for hora in horas:
                        if r.random() > factor:
                            continue
                        hh, mm = map(int, hora.split(":"))
                        sale = en_hora(dia, hh + mm / 60 + r.uniform(0, 0.15))
                        if sale >= self.ahora - timedelta(minutes=30):
                            continue
                        manana = hh < 12
                        origen, destino = (alto, bajo) if manana else (bajo, alto)
                        self.viaje(did, nombre, ruta, origen, destino, hora, cupos, sale, i, pasajeros)

        # --- Reportes históricos (hasta hace 3 horas: nunca aparecen como alertas vigentes)
        tramos = [t for t in self.net.tramos if t.modo != "caminando"]
        altos = [t for t in tramos if {t.de, t.a} & {"paraiso", "mirador", "bellaflor", "lucero", "jerusalen"}]
        cerca_ud = [t for t in tramos if {t.de, t.a} & {"udtecno", "candelaria"}]
        camaras = [f"demo:cam{j}" for j in range(1, 5)]
        for cid in camaras:
            self.filas["reporters"].append({"id": cid, "canal": "camara", "rol": "usuario", "nombre": None,
                                            "modo": "pasajero", "aciertos": 40, "fallos": 1,
                                            "creado_en": self.ahora - timedelta(days=self.dias + 5),
                                            "ultimo_en": self.ahora})
        for i, dia in enumerate(self.dias_locales):
            base = 5 + 6 * self.adopcion(i)
            extra = []
            if i in self.lluvias:
                extra += [("derrumbe", r.choice(altos)) for _ in range(r.randint(4, 8))]
                extra += [("trancon", r.choice(altos)) for _ in range(r.randint(3, 6))]
            if i == self.protesta:
                extra += [("bloqueo", r.choice(cerca_ud)) for _ in range(r.randint(10, 14))]
            normales = [(elegir(r, TIPOS_NORMALES), r.choice(tramos)) for _ in range(int(r.gauss(base, 2)))]
            for tipo, tramo in normales + extra:
                h = r.choice([r.gauss(6.3, 0.9), r.gauss(18, 1.2), r.uniform(9, 16)])
                creado = en_hora(dia, h)
                if creado > self.ahora - timedelta(hours=3):
                    continue
                self.incidente(tipo, tramo, creado, usuarios, camaras)
        return self.filas

    def evento(self, u: dict, o: str, d: str, final: str | None, pri: str, cuando: datetime, i: int) -> None:
        if o == d or cuando > self.ahora:
            return
        modo = self.modo_de(o, d, pri)
        if i == self.protesta and self.r.random() < 0.45:
            modo = "colectivo"  # ese día la gente se fue en informal para esquivar el bloqueo
        self.filas["events"].append({"reporter_id": u["id"], "origen_id": o, "destino_id": d, "canal": u["canal"],
                                     "prioridad": pri, "modo": modo, "destino_final": final, "creado_en": cuando})

    def viaje(self, did, nombre, ruta, origen, destino, hora, cupos, sale, i, pasajeros) -> None:
        r = self.r
        hh = int(hora[:2])
        pico = 5 <= hh <= 7 or 17 <= hh <= 19
        llenado = (r.uniform(0.9, 1.2) if hh in (5, 6) else r.uniform(0.8, 1.05) if pico else r.uniform(0.35, 0.72))
        ocupados = min(cupos, max(1, round(cupos * llenado)))
        paradas = self.c.drivers.recorrido(origen, destino)
        corta = None
        if len(paradas) > 2 and r.random() < (0.2 if pico else 0.1):
            corta = paradas[1]
        desvio = "Desvío por la manifestación en la Distrital" if i == self.protesta and r.random() < 0.5 else None
        tid = str(uuid.uuid4())
        self.filas["trips"].append({
            "id": tid, "driver_id": did, "driver_nombre": nombre, "ruta": ruta, "origen_id": origen,
            "destino_id": destino, "hora": hora, "cupos_total": cupos, "cupos_libres": cupos - ocupados,
            "estado": "finalizado", "lleno": ocupados == cupos, "lat": None, "lng": None, "salio_en": sale,
            "desvio": desvio, "paradas": None if len(paradas) <= 2 else json.dumps(paradas),
            "corta_en": corta, "creado_en": sale - timedelta(minutes=r.randint(20, 90)),
        })
        # Cupos apartados por la app (el resto sube en la esquina). En rutas con paradas intermedias
        # se guarda dónde se baja cada pasajero.
        por_app = 0.6 if len(paradas) > 2 else 0.3
        for _ in range(ocupados):
            if r.random() > por_app:
                continue
            baja = destino
            if len(paradas) > 2 and (corta or r.random() < 0.34):
                baja = paradas[1]
            self.filas["seats"].append({
                "id": str(uuid.uuid4()), "trip_id": tid, "passenger_id": r.choice(pasajeros),
                "passenger_nombre": "", "baja_en": baja, "estado": "reservado",
                "creado_en": sale - timedelta(minutes=r.randint(5, 60)),
            })

    def incidente(self, tipo, tramo, creado, usuarios, camaras) -> None:
        r = self.r
        a, b = self.net.lugar(tramo.de), self.net.lugar(tramo.a)
        iid = f"demo-{len(self.filas['incidents']):05d}"
        estado = elegir(r, {"verificado": 42, "expirado": 53, "rechazado": 5})
        self.filas["incidents"].append({
            "id": iid, "tipo": tipo, "de_id": tramo.de, "a_id": tramo.a, "modo": tramo.modo,
            "lat": (a.lat + b.lat) / 2, "lng": (a.lng + b.lng) / 2, "nota": r.choice(NOTAS[tipo]),
            "estado": estado, "confianza": round(r.uniform(0.55, 1.0), 2), "creado_en": creado,
            "expira_en": creado + timedelta(hours=2), "verificado_por": None, "resuelto": True,
        })
        for k in range(r.choice([1, 1, 2, 2, 3, 4])):
            if tipo == "trancon" and k == 0 and r.random() < 0.3:
                rid, canal = r.choice(camaras), "camara"
            else:
                u = r.choice(usuarios)
                rid, canal = u["id"], ("telegram" if r.random() < 0.55 else "web")
            self.filas["reports"].append({"incident_id": iid, "reporter_id": rid, "peso": 1.0, "nota": "",
                                          "canal": canal, "creado_en": creado + timedelta(minutes=4 * k)})


def borrar_ficticios(s) -> None:
    viajes_demo = select(TripRow.id).where(TripRow.driver_id.like("demo:%"))
    s.execute(delete(SeatRequestRow).where(or_(SeatRequestRow.passenger_id.like("demo:%"),
                                               SeatRequestRow.trip_id.in_(viajes_demo))))
    s.execute(delete(TripRow).where(TripRow.driver_id.like("demo:%")))
    s.execute(delete(RouteEventRow).where(RouteEventRow.reporter_id.like("demo:%")))
    s.execute(delete(VoteRow).where(VoteRow.reporter_id.like("demo:%")))
    s.execute(delete(ReportRow).where(or_(ReportRow.reporter_id.like("demo:%"), ReportRow.incident_id.like("demo-%"))))
    s.execute(delete(IncidentRow).where(IncidentRow.id.like("demo-%")))
    s.execute(delete(ReporterRow).where(ReporterRow.id.like("demo:%")))


def main() -> None:
    settings = get_settings()
    c = build_container(settings)
    ahora = utcnow()
    filas = Generador(c, ahora).generar()
    sessions = make_session_factory(settings.database_url)
    tablas = [("reporters", ReporterRow), ("incidents", IncidentRow), ("reports", ReportRow),
              ("trips", TripRow), ("seats", SeatRequestRow), ("events", RouteEventRow)]
    with sessions.begin() as s:
        borrar_ficticios(s)
        for clave, tabla in tablas:
            lote = filas[clave]
            for j in range(0, len(lote), 5000):
                s.execute(insert(tabla), lote[j:j + 5000])
    print("✅ Datos ficticios del tablero cargados (marcados demo:* / demo-*):")
    for clave, _ in tablas:
        print(f"   · {clave}: {len(filas[clave]):,}".replace(",", "."))


if __name__ == "__main__":
    main()
