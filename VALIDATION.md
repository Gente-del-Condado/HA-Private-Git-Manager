# Validación de HA Private Git Manager 0.2.1

Fecha: **6 de noviembre de 2026**.

Este informe distingue las comprobaciones ejecutadas de la compatibilidad declarada. No certifica una instalación en Home Assistant OS ni en una Raspberry Pi real.

## Comprobaciones ejecutadas

| Comprobación | Resultado | Alcance |
| --- | --- | --- |
| Pruebas Python | **75 superadas** | API, credenciales, Git, trabajos, programación, recuperación y distribución |
| Análisis de Python | **Correcto** | Ruff: sintaxis, importaciones, errores comunes y código sin uso |
| Formato de Python | **Correcto** | 17 archivos comprobados |
| Sintaxis JavaScript | **Correcta** | `node --check` sobre el módulo de interfaz |
| Dependencias instaladas | **Correctas** | `pip check` sin requisitos rotos |
| SSH real | **Correcto** | Clonación contra sshd temporal en localhost con Ed25519 y puerto personalizado |
| Identidad SSH | **Correcta** | La clonación rechaza una clave de host distinta de la fijada |
| HTTPS Git real | **Correcto** | Servidor Git autenticado con TLS, CA de prueba y `GIT_ASKPASS` |
| Autenticación rechazada | **Correcta** | Token incorrecto detectado; ningún token aparece en estado público, logs o `.git/config` |
| Integridad de checkout | **Correcta** | Cambios de archivos o commit incompatibles bloquean la instalación |
| Corte durante sincronización | **Correcto** | Se recupera la copia que coincide con el commit persistido |
| Supervisor simulado | **Correcto** | Instalación, reconstrucción, parada/inicio, errores y resultados inciertos |
| Trabajos largos | **Correctos** | HTTP 202 inmediato y consulta del estado sin bloquear el trabajo |
| Reinicio | **Correcto** | Los trabajos en curso se marcan interrumpidos y no se repiten automáticamente |
| Recuperación | **Correcta** | Restauración de código; bloqueo si falta una copia verificable; aceptación exige versión y huella |
| Programación | **Correcta** | Solo sincroniza; respeta el intervalo y evita duplicados |
| Prefijo Ingress | **Correcto** | Página, API, JavaScript y catálogos bajo `/api/hassio_ingress/test-token/` |
| Seguridad HTTP | **Correcta** | CSRF, origen cruzado, límite real de cuerpo y errores que no reflejan credenciales |
| Contenedor Docker amd64 | **Construido y arrancado** | Python 3.13 Alpine, Git, OpenSSH y tini |
| Ingress en red de contenedores | **Correcto** | Origen `172.30.32.2` aceptado; origen `172.30.32.4` denegado incluso con X-Forwarded-For falsificado |
| Contenedor: API y datos | **Correctos** | Claves reales, tokens ocultos, catálogos ES/EN, exportación de registros y salud |
| Imagen base arm64 | **Disponible** | Manifest oficial de Python incluye arm64 |
| Dependencias aarch64 | **Disponibles** | Descarga binaria completa para CPython 3.13/musl aarch64, incluida PyYAML y pydantic-core |
| Interfaz de escritorio | **Revisada** | Pantalla principal, preferencias, temas, cambio de idioma, registros y errores de formularios |
| Interfaz móvil | **Revisada a 390 × 844** | Sin desbordamiento horizontal; formulario dentro del ancho disponible |
| Distribución | **Reproducible** | Dos empaquetados producen el mismo SHA256; sin estado, claves, logs ni datos de desarrollo |

La suite muestra una advertencia de deprecación de la combinación Starlette TestClient/httpx. No supone fallo de prueba ni interviene en el servidor de producción.

## Regresión corregida en 0.2.1: carpeta local existente

Se reprodujo el bloqueo al instalar sobre una carpeta ya presente en `/addons/<slug>`. Se añadió una revisión previa y consentimiento explícito para adoptar aplicaciones con el mismo identificador, manteniendo el rechazo de carpetas ajenas.

- 14 pruebas nuevas de carpetas vacías, adopción con y sin instalación previa, consentimiento, cambio de huella, carpeta ajena, enlaces, errores y recuperación.
- Una prueba adicional del endpoint de revisión previa sin toma de propiedad ni modificación de archivos.
- Dos pruebas de navegador completo (español e inglés), con perfil Chrome aislado y Supervisor simulado: foco inicial en Cancelar, consentimiento nativo obligatorio y aplicación efectiva del código después de confirmar.
- La adopción idéntica de una instalación con imagen precompilada no solicita una actualización de imagen innecesaria.

El usuario ha confirmado la descarga real de un repositorio privado de Forgejo mediante SSH en Home Assistant. La corrección de adopción se ha verificado localmente; su comprobación final en esa instalación sigue pendiente.

## Límites de lo comprobado

- La API del Supervisor se contrastó con su documentación y código oficial. Las operaciones se verificaron con simulaciones y transporte HTTP controlado; **no se ejecutaron contra un Supervisor real**.
- El contenedor ejecutado es **amd64**. La presencia de imagen base y dependencias **aarch64** se comprobó, pero no se ejecutó en una Raspberry Pi ni bajo emulación ARM.
- No se conectó al Forgejo real del usuario, no se generaron claves de despliegue en su cuenta ni se instalaron aplicaciones en su Home Assistant.
- El modo de desarrollo muestra explícitamente que no hay Supervisor y bloquea las instalaciones.
- La recuperación restaura código, no imágenes ni datos de aplicaciones. Un resultado incierto exige revisar el Supervisor antes de recuperar.

## Verificación pendiente en la instalación de destino

1. Instalar la carpeta `private_git_manager` como aplicación local y comprobar la construcción en la arquitectura del host.
2. Abrirla desde Ingress y comprobar panel de administración, watchdog y persistencia tras reinicio.
3. Registrar una clave pública de solo lectura en el Forgejo real y verificar la huella del servicio SSH.
4. Sincronizar una aplicación de prueba compatible, instalarla y configurarla desde Home Assistant.
5. Aplicar una nueva versión y comprobar versión, commit y estado de ejecución en el Supervisor.
6. Crear y restaurar una copia de seguridad de la aplicación, protegiendo sus credenciales.

## Repetir las comprobaciones

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check private_git_manager/app tests scripts/package.py
.venv/bin/ruff format --check private_git_manager/app tests scripts/package.py
node --check private_git_manager/app/static/app.js
.venv/bin/pip check
podman build --format docker -t localhost/ha-private-git-manager:0.2.1 private_git_manager
scripts/container-smoke.sh
python3 scripts/package.py
```

La vista previa local se ejecuta en un contenedor separado, sin datos del usuario montados ni acceso a Supervisor. Para detenerla:

```sh
podman stop ha-private-git-manager-preview-final
```
