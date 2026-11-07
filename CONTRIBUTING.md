# Mantener Private Git Manager

## Entorno de desarrollo

Requisitos locales: Python 3.11 o posterior, Git y OpenSSH. Chrome o Chromium permite ejecutar las regresiones de navegador.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m ruff check private_git_manager/app tests
.venv/bin/python -m ruff format --check private_git_manager/app tests
```

Para probar el portal en local, usa directorios temporales para el estado y las aplicaciones. `PGM_DEV=1` habilita el modo de desarrollo. Mantén el servidor en loopback.

```sh
pgm_dev=$(mktemp -d)
PGM_DEV=1 PGM_DATA="$pgm_dev/data" PGM_ADDONS="$pgm_dev/addons" \
  .venv/bin/python -m uvicorn --app-dir private_git_manager app.main:app --host 127.0.0.1 --port 8099
```

Las operaciones nativas requieren Supervisor o una sesión real de YunoHost. Para reproducirlas en desarrollo consulta las pruebas con dobles de ambas plataformas.

## Mapa del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| `private_git_manager/app/main.py` | Entrada FastAPI, protección de peticiones, validación de entradas y rutas |
| `private_git_manager/app/core.py` | Git y SSH, inventario, estado, despliegues y cliente del Supervisor |
| `private_git_manager/app/jobs.py` | Cola de trabajos y programación |
| `private_git_manager/app/application.py` y `backups.py` | Operaciones nativas de Home Assistant y copias |
| `private_git_manager/app/yunohost.py` | Detección y preparación de paquetes para la API nativa de YunoHost |
| `private_git_manager/app/documentation.py` | Lectura y entrega segura del Markdown y sus recursos |
| `private_git_manager/app/storage.py` | Migración y conservación del estado persistente |
| `private_git_manager/app/static/` | Portal sin compilador, esquema de formularios y traducciones ES/EN |
| `private_git_manager/config.yaml`, `Dockerfile` y `DOCS.md` | Distribución y ayuda de Home Assistant |
| `manifest.toml`, `conf/`, `scripts/` y `doc/` | Paquete, servicio, ciclo de vida y ayuda nativa de YunoHost |
| `docs/` | Manual web estático y capturas de demostración |
| `tests/` | Contratos de API, estado, seguridad, empaquetado y navegador |

## Contratos a respetar

- Git se sincroniza en una copia temporal. El cambio de rama o el fallo de una descarga deben mantener el estado coherente. Instalar usa el commit revisado.
- En Home Assistant, conserva el origen de la petición por Ingress y el rol de Supervisor. Una operación incierta debe quedar recuperable. No repitas por tu cuenta una desinstalación, restauración o actualización interrumpida.
- YunoHost usa Nginx y un socket Unix. El portal llama a la API nativa del mismo dominio con la sesión de administrador del navegador. El servicio del gestor prepara archivos con su usuario dedicado.
- Los secretos y las copias requieren el mismo cuidado que los datos de producción. Usa datos ficticios en tests, ejemplos y capturas. Conserva los códigos de error y añade ambos idiomas cuando aparezca un mensaje nuevo.
- Documenta en español el motivo de las decisiones de seguridad y recuperación. Actualiza los ejemplos cuando cambie una ruta, un permiso o una etiqueta de la interfaz.

## Datos y diagnóstico

`PGM_DATA` contiene `state.json` (repositorios, credenciales y diario de recuperación), `jobs.json` (trabajos), `manager.log` (registro rotatorio), `keys/` y `repos/`. Home Assistant lo monta dentro de la configuración dedicada del gestor. YunoHost asigna el directorio desde el recurso de datos de su manifiesto. Trata también los archivos de copia como credenciales.

`PGM_ADDONS` señala la carpeta de complementos locales. Las carpetas temporales de despliegue y el diario de recuperación están relacionados. Revisa el estado del Supervisor y la documentación de recuperación antes de retirar una carpeta de un trabajo interrumpido.

## Editar el manual

Edita `docs/index.html` para cambiar el texto y `docs/assets/manual.css` para ajustar la presentación. Mantén las rutas de recursos relativas para que funcionen bajo la subruta de GitHub Pages. Sirve la carpeta con `python3 -m http.server 8080 --bind 127.0.0.1 --directory docs`.

Las capturas proceden del portal real con un Supervisor simulado y datos de ejemplo, como los de `tests/test_adoption_ui.py`. Reemplaza la imagen, sus dimensiones y su texto alternativo juntos. Revisa el manual en escritorio y móvil. Actualiza también la ayuda correspondiente en `private_git_manager/DOCS.md` o `doc/ADMIN*.md`.
