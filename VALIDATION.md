# Validación de HA Private Git Manager 0.8.0

Fecha: **7 de noviembre de 2026**.

Este informe distingue las comprobaciones ejecutadas de la compatibilidad declarada. No certifica una instalación en Home Assistant OS ni en una Raspberry Pi real.

## Comprobaciones ejecutadas

| Comprobación | Resultado | Alcance |
| --- | --- | --- |
| Pruebas Python | **171 superadas** | API, credenciales, Git, trabajos, programación, recuperación y distribución |
| Análisis de Python | **Correcto** | Ruff: sintaxis, importaciones, errores comunes y código sin uso |
| Formato de Python | **Correcto** | 31 archivos comprobados |
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

## Catálogos y documentación privada en 0.3.0

- Repositorio de una sola aplicación en la raíz, catálogo maestro con README/repository.yaml y aplicaciones en subcarpetas, y catálogo que incluye al propio gestor.
- Metadatos y documentación distintos por aplicación; migración de copias descargadas antes de actualizar.
- Markdown formateado (tablas y código), enlaces internos y PNG local servida mediante las rutas privadas de la API.
- Rechazo de recorridos fuera del checkout, archivos de `.git`/`.ssh`, enlaces simbólicos, documentos demasiado grandes y formatos de archivo no autorizados.
- HTML de origen desactivado, protocolos activos bloqueados e imágenes externas/SVG sin carga automática.
- Dos recorridos completos de navegador Chrome 157: sanitizador nativo y alternativa DOMPurify forzada, con lectura de catálogo, README de aplicación, DOCS, enlace interno, imagen local y búsqueda por mantenedor.
- Cambio del README general de un catálogo real de prueba sin cambio de las huellas de sus aplicaciones.
- Dependencia Markdown incluida en la construcción Docker, junto con DOMPurify versionado y sus licencias para navegadores sin Sanitizer API.

## Borrado individual y catálogo en 0.4.0

- 15 pruebas de borrado: conservación de aplicaciones hermanas y checkout maestro, copia desvinculada, rechazo de aplicaciones instaladas, huella cambiada, carpeta ajena, enlaces, identificadores inseguros y protección del propio gestor.
- Diario persistente: recuperación después de reiniciar, corte entre renombrado y persistencia, y limpieza parcial interrumpida. Una carpeta nueva creada después en la ruta original se conserva.
- Preferencia de aplicaciones ocultas guardada en disco, conservada al sincronizar mediante SSH real y reversible sin instalación.
- Endpoint de borrado con confirmación, protección CSRF y trabajo HTTP 202; validación de su resultado y restauración de visibilidad.
- Dos recorridos Chrome con perfiles aislados (español e inglés): Cancelar recibe el foco, el consentimiento nativo es obligatorio, solo desaparece la aplicación seleccionada y se puede volver a mostrar.
- Reinstalación después de una desinstalación externa y consulta inmediata del Supervisor al terminar un trabajo. Los controles de ejecución se muestran para aplicaciones instaladas.

## Instalación y desinstalación desde el gestor en 0.5.0

- 16 pruebas adicionales: desinstalar conservando código, reinstalar desde el gestor, borrar junto con desinstalar, mantener otras aplicaciones y elegir `remove_config` explícitamente.
- Contrato HTTP del Supervisor con transporte controlado: autenticación Bearer, instalación mediante `/store/addons/local_<slug>/install`, desinstalación mediante `/addons/local_<slug>/uninstall` y cuerpo `remove_config: false` por defecto.
- Cortes antes y después de completar la desinstalación, persistencia del diario al reiniciar y recuperación que no repite automáticamente solicitudes destructivas.
- Reintento solo autorizado explícitamente, rechazo de confirmaciones con huella desactualizada y conservación de una instalación nueva aparecida después de apartar el código anterior.
- Endpoint de desinstalación con confirmación, CSRF, HTTP 202 y verificación de su resultado.
- Actualización local con cambio de versión mediante `/store/addons/<slug>/update`, y reconstrucción sin cambio de versión mediante `/addons/<slug>/rebuild`. El doble de Supervisor rechaza reconstrucciones con versiones distintas, como el Supervisor real.

Referencias oficiales: [desinstalación y `remove_config`](https://contributors.home-assistant.io/apps/supervisor-api/apps/#post-addonsappuninstall), [instalación desde la tienda](https://contributors.home-assistant.io/apps/supervisor-api/store/#post-storeaddonsappinstall) y [restricción de versión al reconstruir](https://github.com/home-assistant/supervisor/blob/main/supervisor/apps/manager.py).
- Dos recorridos completos de Chrome, español e inglés: consentimiento obligatorio, configuración pública desmarcada por defecto, desinstalación, reinstalación desde la interfaz y borrado combinado sin afectar a la aplicación hermana.

## Configuración y logs por aplicación en 0.6.0

- 22 pruebas adicionales: opciones anidadas, referencias !secret, rechazo de YAML ambiguo/inseguro, errores de esquema sin valores privados, conflicto de revisiones, guardado, reinicio opcional y fallo parcial explícito.
- Configuración sin valores persistidos en estado, trabajos o registros; control de acceso por repositorio, aplicación instalada y transacciones pendientes.
- Logs HTTP autenticados y limitados a 512 KiB; texto seguro, limpieza de códigos de terminal y ocultación de valores sensibles conocidos.
- API con confirmación y CSRF, configuración privada sin caché y descarga de logs como texto.
- Dos recorridos completos de Chrome (español/inglés): validar, guardar y reiniciar; conservar cambios ante un conflicto; confirmar el descarte; buscar, actualizar automática y manualmente y descargar logs; rechazo de ejecución de HTML y revisión de ancho móvil.

Referencias: [opciones y validación del Supervisor](https://contributors.home-assistant.io/apps/supervisor-api/apps/#post-addonsappoptions) y [logs de aplicaciones](https://contributors.home-assistant.io/apps/supervisor-api/apps/#get-addonsapplogs).

## Formulario basado en Home Assistant en 0.7.0

- Se reutilizan directamente `schema_ui` y `translations` del Supervisor: nombres, ayudas, tipos, formatos, límites, selectores y estructura anidada. El formato procede de [UiOptions del Supervisor](https://github.com/home-assistant/supervisor/blob/main/supervisor/apps/options.py) y [los archivos de traducción nativos](https://contributors.home-assistant.io/apps/reference/files/#translation-file).
- Seis pruebas adicionales: metadatos y traducciones de origen, conversión sin guardado, valores nulos nativos, API privada/CSRF y dos recorridos completos Chrome (español e inglés).
- Guardado directo desde el formulario sin abrir YAML; contraseña oculta/visible, rangos numéricos, decimales, casillas false frente a valores ausentes, selectores de dispositivos y estructuras anidadas.
- Alta/baja de listas y recuperación de opciones opcionales del objeto correcto después de eliminar otro elemento; referencias !secret, campos no representables y valores con nombres de propiedades especiales conservados.
- Alternancia formulario/YAML con ediciones en ambos sentidos, rechazo de YAML inválido sin pérdida de texto, validación del Supervisor y conservación de valores sensibles fuera del estado y trabajos del gestor.
- Formulario comprobado a 390 píxeles de ancho, acceso por etiquetas, foco al añadir/quitar elementos y selector de idioma protegido durante la carga inicial.

## Apertura de aplicaciones por Ingress en 0.8.0

- 16 pruebas adicionales: rutas de Core anterior y posterior a 2026.2, rechazo de aplicaciones detenidas o sin Ingress, propiedad, instalación, operaciones pendientes y versión desconocida.
- API privada que devuelve únicamente una ruta local fija de Home Assistant, sin tokens de `ingress_url`, URLs externas de `webui` ni creación de sesiones desde el gestor.
- Cuatro recorridos Chrome (español/inglés × ruta actual/anterior) desde un iframe bajo un prefijo Ingress simulado. Se comprueba que navega la ventana principal, evitando anidar Home Assistant dentro del gestor.
- Botón desactivado cuando la aplicación está detenida, y comprobación de disponibilidad de Ingress de nuevo al pulsar sin abandonar el gestor si ya no está disponible.
- El destino de Home Assistant se simula: se valida el enlace y la salida del iframe, no la creación de una sesión real contra una instalación de Home Assistant.

Referencias oficiales: [panel nativo de aplicaciones y renovación de sesiones](https://github.com/home-assistant/frontend/blob/dev/src/panels/app/ha-panel-app.ts) y registro del panel `app` en [Core 2026.2](https://github.com/home-assistant/core/blob/2026.2.0/homeassistant/components/hassio/__init__.py), ausente en [Core 2026.1](https://github.com/home-assistant/core/blob/2026.1.0/homeassistant/components/hassio/__init__.py).

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
4. Sincronizar una aplicación de prueba compatible, instalarla, configurarla y consultar sus logs desde el gestor.
5. Aplicar una nueva versión y comprobar versión, commit y estado de ejecución en el Supervisor.
6. Crear y restaurar una copia de seguridad de la aplicación, protegiendo sus credenciales.

## Repetir las comprobaciones

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check private_git_manager/app tests scripts/package.py
.venv/bin/ruff format --check private_git_manager/app tests scripts/package.py
node --check private_git_manager/app/static/app.js
.venv/bin/pip check
podman build --format docker -t localhost/ha-private-git-manager:0.8.0 private_git_manager
scripts/container-smoke.sh
python3 scripts/package.py
```

La vista previa local se ejecuta en un contenedor separado, sin datos del usuario montados ni acceso a Supervisor. Para detenerla:

```sh
podman stop ha-private-git-manager-preview-final
```
