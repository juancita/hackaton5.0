"""Datos de demostración del módulo de conductores: 3 conductores informales con ~2 semanas de
historial (para que la TENDENCIA y los HORARIOS TÍPICOS offline tengan datos) y viajes publicados hoy.

Uso (desde backend/):
    python -m scripts.seed_demo
En Docker:
    docker compose exec backend python -m scripts.seed_demo

Es idempotente: si el conductor ya tiene historial, no lo duplica.
"""

import random
import uuid
from datetime import timedelta

from app.config import get_settings
from app.container import build_container
from app.domain.drivers import Trip
from app.domain.models import Actor
from app.domain.reports import reporter_id_por_telefono, utcnow

CONDUCTORES = [
    # (teléfono ficticio, nombre, ruta = nombre del tramo informal en la red, horas habituales, cupos)
    ("3000000001", "Don Pedro", "Jeep Paraíso", ["05:30", "06:00", "06:30", "12:00", "17:30"], 8),
    ("3000000002", "Doña Marta", "Colectivo Lucero", ["05:45", "06:15", "07:00", "18:00"], 12),
    ("3000000003", "Jairo", "Jeep Quiba", ["05:00", "06:00", "14:00"], 7),
    ("3000000004", "Don Álvaro", "Colectivo Santo Domingo", ["05:15", "06:00", "06:45", "19:00"], 10),
]


def main() -> None:
    s = get_settings()
    c = build_container(s)
    repo = c.drivers._repo
    tramos_inf = [t for t in c.network.tramos if not c.network.modos[t.modo].formal]
    ahora = utcnow()
    random.seed(7)
    for tel, nombre, ruta, horas, cupos in CONDUCTORES:
        rid = reporter_id_por_telefono(tel, s.id_salt)
        actor = Actor(reporter_id=rid, canal="web")
        c.reports.registrar_perfil(actor, nombre, "conductor")
        tramo = next((t for t in tramos_inf if t.ruta == ruta), tramos_inf[0])
        c.drivers.registrar_conductor(rid, ruta, tramo.de)
        if repo.driver_trips(rid, 1):
            print(f"· {nombre}: ya tenía historial, no se duplica")
            continue
        n = 0
        for d in range(14, 0, -1):  # historial: 2 semanas, viajes finalizados
            for h in horas:
                if random.random() < 0.85:
                    hh, mm = map(int, h.split(":"))
                    creado = (ahora - timedelta(days=d)).replace(hour=hh, minute=mm, second=0, microsecond=0)
                    repo.create_trip(Trip(
                        id=str(uuid.uuid4()), driver_id=rid, driver_nombre=nombre, ruta=ruta,
                        origen_id=tramo.de, destino_id=tramo.a, hora=h, cupos_total=cupos, cupos_libres=0,
                        estado="finalizado", lleno=True, creado_en=creado,
                    ))
                    n += 1
        for h in horas[:2]:  # viajes publicados HOY (visibles para pasajeros)
            c.drivers.anunciar(rid, nombre, tramo.de, tramo.a, h, cupos, ruta)
        print(f"· {nombre} ({ruta}): {n} viajes de historial + {len(horas[:2])} publicados hoy")
    print("\nHorarios típicos (modo offline):")
    for r, hs in c.drivers.horarios_tipicos().items():
        print(f"  {r}: {', '.join(hs)}")


if __name__ == "__main__":
    main()
