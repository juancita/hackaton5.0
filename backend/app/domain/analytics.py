"""Analítica de movilidad: el tablero que ve el administrador y que se vende a las entidades.

Todo sale de lo que la app ya registra (consultas de ruta, viajes informales, cupos y reportes) y se
entrega AGREGADO y ANÓNIMO: ningún indicador identifica a una persona y los flujos con menos de
`K_ANONIMATO` consultas se agrupan (Ley 1581 de 2012). Las cifras y las conclusiones las calcula este
módulo; la IA (si está activa) solo redacta el resumen ejecutivo a partir de ellas.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Protocol

from pydantic import BaseModel

from app.domain.drivers import RouteEvent, SeatRequest, Trip
from app.domain.models import Network, TripPlan

BOGOTA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano
K_ANONIMATO = 5
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# Puntos por donde la gente sale de la localidad hacia el resto de Bogotá
SALIDAS: dict[str, tuple[str, str]] = {
    "tunal": ("Portal Tunal", "TransMilenio y TransMiCable"),
    "estperdomo": ("Estación Perdomo", "Autopista Sur"),
    "meissen": ("Meissen", "Av. Boyacá"),
    "hospital": ("Hospital Meissen", "Av. Boyacá"),
    "candelaria": ("Candelaria La Nueva", "Av. Villavicencio"),
    "udtecno": ("U. Distrital Tecnológica", "Av. Villavicencio"),
    "ensueno": ("C.C. El Ensueño", "Av. Villavicencio"),
}

# A dónde sigue el viaje después de salir de la localidad (zona declarada por la persona)
DESTINOS_FINALES: dict[str, tuple[str, float, float]] = {
    "centro": ("Centro", 4.6010, -74.0730),
    "norte": ("Chapinero y Norte", 4.6480, -74.0620),
    "industrial": ("Puente Aranda (zona industrial)", 4.6150, -74.1050),
    "kennedy": ("Kennedy y Américas", 4.6280, -74.1530),
    "soacha": ("Soacha", 4.5790, -74.2170),
    "usme": ("Tunjuelito y Usme", 4.5350, -74.1180),
    "local": ("Dentro de Ciudad Bolívar", 4.5600, -74.1500),
}

CATEGORIA_MODO = {
    "cable": "cable", "troncal": "transmilenio", "alimentador": "transmilenio", "sitp": "sitp",
    "jeep": "informal", "colectivo": "informal", "veredal": "informal",
}
NOMBRE_CATEGORIA = {
    "cable": "TransMiCable", "transmilenio": "TransMilenio", "sitp": "Bus SITP", "informal": "Informal",
}
NOMBRE_CANAL = {"telegram": "Telegram (chat con IA)", "web": "App web", "camara": "Cámaras", "admin": "Administrador"}
ESPERA_EVITADA_MIN = 12  # supuesto: minutos de espera que ahorra apartar cupo en vez de esperar en la esquina


class ReporteResumen(BaseModel):
    """Un reporte ciudadano o de cámara, sin identidad."""
    tipo: str
    canal: str
    estado: str
    de_id: str
    creado_en: datetime


class AnalyticsSource(Protocol):
    """Puerto de lectura: lo que el tablero necesita de la base (solo lectura)."""

    def consultas(self, desde: datetime) -> list[RouteEvent]: ...
    def viajes(self, desde: datetime) -> list[Trip]: ...
    def cupos(self, desde: datetime) -> list[SeatRequest]: ...
    def reportes(self, desde: datetime) -> list[ReporteResumen]: ...
    def usuarios(self) -> dict[str, int]: ...


JERARQUIA_MODO = ["jeep", "colectivo", "veredal", "cable", "troncal", "alimentador", "sitp"]


def modo_principal(plan: TripPlan) -> str | None:
    """Medio que define la ruta recomendada: si usa algún tramo informal, informal (la dependencia que el
    Distrito necesita ver); si no, TransMiCable; si no, TransMilenio; si no, SITP."""
    if not plan.opciones:
        return None
    modos = {t.modo for t in plan.opciones[plan.recomendada].tramos}
    return next((m for m in JERARQUIA_MODO if m in modos), "caminando")


def _pct(n: float, total: float) -> float:
    return round(100 * n / total, 1) if total else 0.0


def _hora_texto(h: int) -> str:
    return f"{h % 12 or 12} {'a.m.' if h < 12 else 'p.m.'}"


class AnalyticsService:
    def __init__(self, network: Network, source: AnalyticsSource, clock, ttl_s: int = 60):
        self._net = network
        self._src = source
        self._now = clock
        self._ttl = ttl_s
        self._cache: dict[int, tuple[datetime, dict]] = {}

    def _nombre(self, pid: str) -> str:
        lugar = self._net.lugar(pid)
        return lugar.nombre if lugar else pid

    def _coords(self, pid: str) -> tuple[float, float] | None:
        lugar = self._net.lugar(pid)
        return (lugar.lat, lugar.lng) if lugar else None

    def _zona(self, pid: str) -> str:
        lugar = self._net.lugar(pid)
        return lugar.zona if lugar else ""

    def invalidar(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------ tablero
    def tablero(self, dias: int = 30) -> dict:
        dias = max(7, min(dias, 90))
        ahora = self._now()
        hit = self._cache.get(dias)
        if hit and (ahora - hit[0]).total_seconds() < self._ttl:
            return hit[1]
        data = self._calcular(dias, ahora)
        self._cache[dias] = (ahora, data)
        return data

    def _calcular(self, dias: int, ahora: datetime) -> dict:
        desde = ahora - timedelta(days=dias)
        evs = self._src.consultas(desde)
        viajes = self._src.viajes(desde)
        cupos = self._src.cupos(desde)
        reportes = self._src.reportes(desde)
        usuarios = self._src.usuarios()
        local = lambda d: d.astimezone(BOGOTA)  # noqa: E731

        # --- Dirección de cada consulta: sale de la localidad, regresa o se mueve adentro
        def direccion(e: RouteEvent) -> str:
            if e.destino_id in SALIDAS and e.origen_id not in SALIDAS:
                return "salida"
            if e.origen_id in SALIDAS and e.destino_id not in SALIDAS:
                return "regreso"
            return "interno"

        salida_h, regreso_h, interno_h = [0] * 24, [0] * 24, [0] * 24
        heat = [[0] * 24 for _ in range(7)]
        for e in evs:
            t = local(e.creado_en)
            {"salida": salida_h, "regreso": regreso_h, "interno": interno_h}[direccion(e)][t.hour] += 1
            heat[t.weekday()][t.hour] += 1
        oferta_h, viajes_h, llenos_h = [0] * 24, [0] * 24, [0] * 24
        for v in viajes:
            try:
                h = int(v.hora[:2]) % 24
            except ValueError:
                continue
            oferta_h[h] += v.cupos_total
            viajes_h[h] += 1
            llenos_h[h] += bool(v.lleno or v.cupos_libres == 0)
        llenos_pct_h = [_pct(llenos_h[h], viajes_h[h]) for h in range(24)]

        # --- Semanas (adopción): ventanas de 7 días completos contadas hacia atrás desde hoy
        n_sem = dias // 7
        semanas: dict[int, set] = defaultdict(set)
        consultas_sem: Counter = Counter()
        for e in evs:
            k = int((ahora - e.creado_en).total_seconds() // (7 * 86400))
            if k < n_sem:
                semanas[k].add(e.reporter_id)
                consultas_sem[k] += 1
        semanal = [{"semana": local(ahora - timedelta(days=7 * (k + 1))).date().isoformat(),
                    "usuarios": len(semanas[k]), "consultas": consultas_sem[k]} for k in range(n_sem - 1, -1, -1)]
        crecimiento = 0.0
        if len(semanal) >= 2 and semanal[0]["usuarios"]:
            crecimiento = _pct(semanal[-1]["usuarios"] - semanal[0]["usuarios"], semanal[0]["usuarios"])

        # --- Salidas, destinos finales y flujos
        sal = Counter(e.destino_id for e in evs if direccion(e) == "salida")
        total_sal = sum(sal.values())
        salidas = [{"id": s, "nombre": SALIDAS[s][0], "corredor": SALIDAS[s][1], "consultas": n, "pct": _pct(n, total_sal)}
                   for s, n in sal.most_common()]
        fin = Counter(e.destino_final for e in evs if e.destino_final in DESTINOS_FINALES)
        total_fin = sum(fin.values())
        destinos_finales = [{"id": f, "nombre": DESTINOS_FINALES[f][0], "consultas": n, "pct": _pct(n, total_fin),
                             "lat": DESTINOS_FINALES[f][1], "lng": DESTINOS_FINALES[f][2]} for f, n in fin.most_common()]
        fuera = sum(n for f, n in fin.items() if f != "local")

        flujos = []
        for (o, s), n in Counter((e.origen_id, e.destino_id) for e in evs if direccion(e) == "salida").most_common(40):
            a, b = self._coords(o), self._coords(s)
            if n >= K_ANONIMATO and a and b:
                flujos.append({"origen_id": o, "origen": self._nombre(o), "salida_id": s, "salida": SALIDAS[s][0],
                               "n": n, "de": a, "a": b})
        flujos_finales = []
        for (s, f), n in Counter((e.destino_id, e.destino_final) for e in evs
                                 if direccion(e) == "salida" and e.destino_final in DESTINOS_FINALES
                                 and e.destino_final != "local").most_common(30):
            a = self._coords(s)
            if n >= K_ANONIMATO and a:
                flujos_finales.append({"salida_id": s, "salida": SALIDAS[s][0], "final_id": f,
                                       "final": DESTINOS_FINALES[f][0], "n": n, "de": a,
                                       "a": (DESTINOS_FINALES[f][1], DESTINOS_FINALES[f][2])})

        # --- Medios, prioridades y canales
        cat = Counter(CATEGORIA_MODO.get(e.modo or "", "") for e in evs if e.modo)
        cat.pop("", None)
        total_cat = sum(cat.values())
        medios = [{"modo": m, "nombre": NOMBRE_CATEGORIA[m], "n": n, "pct": _pct(n, total_cat)} for m, n in cat.most_common()]
        pri = Counter(e.prioridad for e in evs if e.prioridad)
        prioridades = {p: _pct(pri[p], sum(pri.values())) for p in ("rapido", "barato", "transbordos")}
        can = Counter(e.canal for e in evs)
        canales = [{"canal": k, "nombre": NOMBRE_CANAL.get(k, k), "n": n, "pct": _pct(n, len(evs))} for k, n in can.most_common()]

        # --- Pares origen → destino y barrios que más dependen del informal
        pares_c = Counter((e.origen_id, e.destino_id) for e in evs)
        inf_par = Counter((e.origen_id, e.destino_id) for e in evs if CATEGORIA_MODO.get(e.modo or "") == "informal")
        pares = [{"origen_id": o, "origen": self._nombre(o), "destino_id": d, "destino": self._nombre(d), "n": n,
                  "informal_pct": _pct(inf_par[(o, d)], n)}
                 for (o, d), n in pares_c.most_common(10) if n >= K_ANONIMATO]
        por_barrio = Counter(e.origen_id for e in evs if e.origen_id not in SALIDAS)
        inf_barrio = Counter(e.origen_id for e in evs if e.origen_id not in SALIDAS
                             and CATEGORIA_MODO.get(e.modo or "") == "informal")
        barrios = [{"id": b, "nombre": self._nombre(b), "zona": self._zona(b), "n": n,
                    "informal_pct": _pct(inf_barrio[b], n)} for b, n in por_barrio.most_common(10) if n >= K_ANONIMATO]

        # --- Rutas informales: ocupación, cortes y bajadas antes del final
        por_viaje_cupos: dict[str, list[SeatRequest]] = defaultdict(list)
        for c in cupos:
            por_viaje_cupos[c.trip_id].append(c)
        rutas: dict[str, dict] = {}
        for v in viajes:
            r = rutas.setdefault(v.ruta, {"ruta": v.ruta, "viajes": 0, "cupos": 0, "ocupados": 0, "llenos": 0,
                                          "cortados": 0, "cortes": Counter(), "reservas": 0, "bajan_antes": 0,
                                          "horas": Counter(), "conductores": set(), "desvios": 0, "tramos": False})
            r["viajes"] += 1
            r["cupos"] += v.cupos_total
            r["ocupados"] += v.cupos_total - v.cupos_libres
            r["llenos"] += bool(v.lleno or v.cupos_libres == 0)
            r["desvios"] += bool(v.desvio)
            r["horas"][v.hora[:2]] += 1
            r["conductores"].add(v.driver_id)
            r["tramos"] |= len(v.paradas) > 2
            if v.corta_en:
                r["cortados"] += 1
                r["cortes"][v.corta_en] += 1
            for s in por_viaje_cupos.get(v.id, []):
                r["reservas"] += 1
                r["bajan_antes"] += bool(s.baja_en and s.baja_en != v.destino_id)
        rutas_informales = []
        for r in sorted(rutas.values(), key=lambda x: -x["viajes"]):
            corte = r["cortes"].most_common(1)
            hora = r["horas"].most_common(1)
            rutas_informales.append({
                "ruta": r["ruta"], "viajes": r["viajes"], "conductores": len(r["conductores"]),
                "ocupacion_pct": _pct(r["ocupados"], r["cupos"]), "llenos_pct": _pct(r["llenos"], r["viajes"]),
                "cortados_pct": _pct(r["cortados"], r["viajes"]),
                "corte_frecuente": self._nombre(corte[0][0]) if corte else None,
                "bajan_antes_pct": _pct(r["bajan_antes"], r["reservas"]) if r["reservas"] and r["tramos"] else None,
                "hora_pico": f"{hora[0][0]}:00" if hora else None, "desvios": r["desvios"],
            })

        # --- Reportes (vecinos, chat con IA y cámaras)
        tipos = Counter(r.tipo for r in reportes)
        canal_rep = Counter(r.canal for r in reportes)
        tramo_rep = Counter(r.de_id for r in reportes)
        rep = {
            "total": len(reportes),
            "por_tipo": [{"tipo": t, "n": n} for t, n in tipos.most_common()],
            "por_canal": [{"canal": k, "nombre": NOMBRE_CANAL.get(k, k), "n": n, "pct": _pct(n, len(reportes))}
                          for k, n in canal_rep.most_common()],
            "zonas": [{"id": z, "nombre": self._nombre(z), "n": n} for z, n in tramo_rep.most_common(5)],
            "verificados_pct": _pct(sum(r.estado == "verificado" for r in reportes), len(reportes)),
        }

        # --- KPIs
        activos = {e.reporter_id for e in evs} | {c.passenger_id for c in cupos}
        conductores = {v.driver_id for v in viajes}
        cupos_tot = sum(v.cupos_total for v in viajes)
        ocupados = sum(v.cupos_total - v.cupos_libres for v in viajes)
        reservas = len(cupos)  # cupos apartados por la app
        kpis = {
            "usuarios_activos": len(activos), "usuarios_total": usuarios.get("total", 0),
            "conductores_activos": len(conductores), "consultas": len(evs),
            "consultas_dia": round(len(evs) / dias), "viajes_informales": len(viajes),
            "cupos_apartados": reservas, "pasajeros_informales": ocupados, "ocupacion_pct": _pct(ocupados, cupos_tot),
            "cortados_pct": _pct(sum(bool(v.corta_en) for v in viajes), len(viajes)),
            "reportes": len(reportes), "reportes_chat_pct": _pct(canal_rep.get("telegram", 0), len(reportes)),
            "horas_espera_evitadas": round(reservas * ESPERA_EVITADA_MIN / 60),
            "crecimiento_usuarios_pct": crecimiento, "fuera_localidad_pct": _pct(fuera, total_fin),
        }
        data = {
            "generado_en": ahora.isoformat(), "dias": dias,
            "datos_demo": any(e.reporter_id.startswith("demo:") for e in evs[:200]),
            "kpis": kpis,
            "por_hora": {"salida": salida_h, "regreso": regreso_h, "interno": interno_h, "oferta_cupos": oferta_h,
                         "viajes_informales": viajes_h, "llenos_pct": llenos_pct_h},
            "heatmap": {"dias": DIAS, "matriz": heat},
            "semanal": semanal, "salidas": salidas, "destinos_finales": destinos_finales,
            "flujos": flujos, "flujos_finales": flujos_finales, "medios": medios, "prioridades": prioridades,
            "canales": canales, "pares": pares, "barrios": barrios, "rutas_informales": rutas_informales,
            "reportes": rep,
        }
        data["insights"] = self.insights(data)
        return data

    # ------------------------------------------------------------------ conclusiones
    def insights(self, d: dict) -> list[dict]:
        """Conclusiones calculadas con reglas (siempre disponibles, con cifras exactas)."""
        out: list[dict] = []
        k = d["kpis"]
        sal = d["por_hora"]["salida"]
        if sum(sal):
            pico = max(range(22), key=lambda h: sal[h] + sal[h + 1] + sal[h + 2])
            pct = _pct(sal[pico] + sal[pico + 1] + sal[pico + 2], sum(sal))
            out.append({"icono": "schedule", "titulo": "La loma sale de madrugada",
                        "texto": f"El {pct}% de los viajes hacia fuera de la localidad se piden entre las "
                                 f"{_hora_texto(pico)} y las {_hora_texto(pico + 3)}",
                        "accion": "Reforzar frecuencias de SITP y TransMiCable en esa franja."})
        llenos = [(d["por_hora"]["llenos_pct"][h], h) for h in range(24) if d["por_hora"]["viajes_informales"][h] >= 20]
        if llenos:
            p, h = max(llenos)
            if p >= 30:
                out.append({"icono": "trending_up", "titulo": "Demanda sin cubrir",
                            "texto": f"A las {_hora_texto(h)} el {p}% de los viajes informales sale lleno: "
                                     "hay más gente que cupos",
                            "accion": "Oportunidad para una ruta zonal o más frecuencia del alimentador en esa hora."})
        dep = [b for b in d["barrios"] if b["n"] >= 30]
        if dep:  # el barrio con MÁS viajes que dependen del informal (volumen × proporción)
            b = max(dep, key=lambda x: x["n"] * x["informal_pct"])
            if b["informal_pct"] >= 30:
                out.append({"icono": "airport_shuttle", "titulo": f"{b['nombre']} depende del transporte informal",
                            "texto": f"El {b['informal_pct']}% de las rutas que se piden desde {b['nombre']} "
                                     "usan jeep, colectivo o veredal",
                            "accion": "Priorizar ahí la formalización o una ruta SITP complementaria."})
        cort = [r for r in d["rutas_informales"] if r["viajes"] >= 20 and r["cortados_pct"] > 0]
        if cort:
            r = max(cort, key=lambda x: x["cortados_pct"])
            extra = (f" y el {r['bajan_antes_pct']}% de los pasajeros se baja antes del final"
                     if r.get("bajan_antes_pct") else "")
            out.append({"icono": "content_cut", "titulo": "Viajes que se cortan a mitad de camino",
                        "texto": f"En «{r['ruta']}» el {r['cortados_pct']}% de los viajes se corta"
                                 + (f" en {r['corte_frecuente']}" if r["corte_frecuente"] else "") + extra,
                        "accion": "Paradero oficial y tarifa por tramo en ese punto."})
        if d["destinos_finales"]:
            top = [x for x in d["destinos_finales"] if x["id"] != "local"][:2]
            if top:
                out.append({"icono": "alt_route", "titulo": "A dónde va la loma",
                            "texto": f"El {k['fuera_localidad_pct']}% sigue hacia otra zona de Bogotá; los destinos "
                                     f"principales son {' y '.join(x['nombre'] for x in top)}",
                            "accion": "Integración tarifaria en "
                                      f"{d['salidas'][0]['nombre'] if d['salidas'] else 'Portal Tunal'}."})
        if d["reportes"]["total"] and d["reportes"]["zonas"]:
            z = d["reportes"]["zonas"][0]
            out.append({"icono": "campaign", "titulo": "Dónde se complica la vía",
                        "texto": f"{z['nombre']} concentra {z['n']} de {d['reportes']['total']} reportes; el "
                                 f"{k['reportes_chat_pct']}% llegó por el chat con IA",
                        "accion": "Mantenimiento preventivo y monitoreo en ese tramo."})
        if k["crecimiento_usuarios_pct"] > 0:
            out.append({"icono": "group_add", "titulo": "La comunidad crece",
                        "texto": f"Los usuarios activos por semana crecieron {k['crecimiento_usuarios_pct']}% "
                                 "en el periodo",
                        "accion": "Cuantos más vecinos, más fino el mapa de la loma."})
        return out

    def hechos_para_ia(self, d: dict) -> dict:
        """Lo mínimo que la IA necesita para redactar el resumen (sin datos personales)."""
        return {
            "periodo_dias": d["dias"], "kpis": d["kpis"],
            "conclusiones": [f"{i['titulo']}: {i['texto']}. Acción sugerida: {i['accion']}" for i in d["insights"]],
            "salidas": d["salidas"][:4], "destinos_finales": d["destinos_finales"][:5], "medios": d["medios"],
            "rutas_informales": d["rutas_informales"][:4],
        }
