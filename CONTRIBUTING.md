# Cómo contribuir — Muévete CB

Trabajamos varios en paralelo. Estas reglas evitan conflictos y mantienen `main` estable.

## Ramas
- `main` → siempre funcional (es lo que demostramos). **No se hace push directo.**
- Ramas de trabajo por tarea:
  - `feat/...` nueva funcionalidad (ej. `feat/mapa-heatmap`)
  - `fix/...` corrección (ej. `fix/rutas-informal`)
  - `docs/...` documentación
  - `data/...` cambios de datos del territorio

## Flujo
```bash
git pull origin main
git checkout -b feat/mi-tarea
# ...trabajar...
git add -A
git commit -m "feat: agrega heatmap de congestión en el mapa"
git push -u origin feat/mi-tarea
# Abrir Pull Request en GitHub → alguien revisa → merge a main
```

## Mensajes de commit (en español, claros)
Formato: `tipo: descripción breve en presente`
- `feat:` nueva funcionalidad
- `fix:` corrección
- `docs:` documentación
- `style:` estilos/formato
- `data:` datos del territorio
- `refactor:` reorganización sin cambiar comportamiento

Ejemplos:
```
feat: detección de vehículos con la cámara real
fix: corrige penalización de tramos bloqueados
data: agrega rutas de jeep de Quiba y Pasquilla
```

## Antes de hacPull Request
- [ ] La app corre en `http://localhost:8000` sin errores en consola.
- [ ] `simulador.html` sigue funcionando.
- [ ] No subiste claves/API keys ni archivos personales.

## Convivencia de código
- JS vainilla, sin frameworks ni build (para que corra en cualquier lado, offline).
- Comentarios en español.
- Un archivo = una responsabilidad (ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)).
