"""Tablero de analítica para el administrador (y producto para entidades): cifras agregadas y anónimas.

Solo con X-Admin-Key. Las cifras y conclusiones las calcula el dominio (analytics.py); Gemini solo redacta
el resumen ejecutivo y, si no responde a tiempo, el tablero muestra las conclusiones calculadas.
"""

import asyncio
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from app.adapters.inbound.deps import get_container, require_admin
from app.container import Container
from app.domain.models import Actor

router = APIRouter(tags=["admin"])

RESUMEN_TIMEOUT_S = 15.0   # el análisis es más largo que una respuesta de chat
RESUMEN_TTL_S = 30 * 60
_resumenes: dict[int, tuple[datetime, dict]] = {}


@router.get("/admin/tablero")
async def tablero(dias: int = Query(30, ge=7, le=90), _: Actor = Depends(require_admin),
                  c: Container = Depends(get_container)) -> dict:
    return await run_in_threadpool(c.analytics.tablero, dias)


@router.get("/admin/tablero/resumen")
async def resumen(dias: int = Query(30, ge=7, le=90), nuevo: bool = False, _: Actor = Depends(require_admin),
                  c: Container = Depends(get_container)) -> dict:
    """Resumen ejecutivo redactado por la IA a partir de las cifras del tablero (se guarda 30 min)."""
    ahora = datetime.now().astimezone()
    hit = _resumenes.get(dias)
    if hit and not nuevo and (ahora - hit[0]).total_seconds() < RESUMEN_TTL_S:
        return hit[1]
    d = await run_in_threadpool(c.analytics.tablero, dias)
    texto, fuente = "", "reglas"
    if c.analista and c.settings.llm_provider == "gemini":
        try:
            texto = await asyncio.wait_for(c.analista.resumir(c.analytics.hechos_para_ia(d)), RESUMEN_TIMEOUT_S)
            fuente = "gemini" if texto else "reglas"
        except Exception:  # noqa: BLE001 — sin IA el tablero sigue con las conclusiones calculadas
            texto = ""
    if not texto:
        texto = "\n".join(f"• {i['texto']} {i['accion']}" for i in d["insights"][:3])
    out = {"fuente": fuente, "texto": texto, "modelo": c.settings.gemini_model if fuente == "gemini" else None,
           "generado_en": ahora.isoformat()}
    if fuente == "gemini":
        _resumenes[dias] = (ahora, out)
    return out


@router.get("/admin/tablero.csv")
async def tablero_csv(dias: int = Query(30, ge=7, le=90), _: Actor = Depends(require_admin),
                      c: Container = Depends(get_container)) -> Response:
    """Datos agregados y anónimos para descargar (lo que recibiría una entidad)."""
    d = await run_in_threadpool(c.analytics.tablero, dias)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["seccion", "item", "valor", "detalle"])
    for k, v in d["kpis"].items():
        w.writerow(["indicador", k, v, ""])
    for h in range(24):
        w.writerow(["consultas_por_hora", f"{h:02d}:00",
                    d["por_hora"]["salida"][h] + d["por_hora"]["regreso"][h] + d["por_hora"]["interno"][h],
                    f"cupos_ofrecidos={d['por_hora']['oferta_cupos'][h]}"])
    for s in d["salidas"]:
        w.writerow(["salida_de_la_localidad", s["nombre"], s["consultas"], s["corredor"]])
    for f in d["destinos_finales"]:
        w.writerow(["destino_final", f["nombre"], f["consultas"], f"{f['pct']}%"])
    for f in d["flujos"]:
        w.writerow(["flujo_barrio_salida", f"{f['origen']} -> {f['salida']}", f["n"], ""])
    for m in d["medios"]:
        w.writerow(["medio_principal", m["nombre"], m["n"], f"{m['pct']}%"])
    for r in d["rutas_informales"]:
        w.writerow(["ruta_informal", r["ruta"], r["viajes"],
                    f"ocupacion={r['ocupacion_pct']}% cortados={r['cortados_pct']}% corte={r['corte_frecuente'] or ''}"])
    for t in d["reportes"]["por_tipo"]:
        w.writerow(["reportes_por_tipo", t["tipo"], t["n"], ""])
    return Response(
        content="﻿" + buf.getvalue(),  # BOM: Excel abre bien las tildes
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="muevete_cb_tablero_{dias}d.csv"'},
    )
