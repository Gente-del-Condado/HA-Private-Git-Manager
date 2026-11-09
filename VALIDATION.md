# Validación

Ejecuta las comprobaciones de [CONTRIBUTING.md](CONTRIBUTING.md) desde la raíz. Los tests de navegador usan Chrome o Chromium y una instancia local con datos temporales.

| Área | Verificación |
| --- | --- |
| Git y SSH | URL y huella, credenciales, sincronización, integridad del commit y descubrimiento de manifiestos |
| Supervisor | Instalación, adopción, recuperación, configuración, Ingress y copias con Supervisor simulado |
| YunoHost | Guardia del socket y proxy, preparación del commit, formularios y llamadas a la API nativa simulada |
| Distribución | Paquete reproducible y sin datos de ejecución, versiones y publicación |
| Manual | Rutas de imágenes y enlaces internos, navegación por teclado, móvil y escritorio |

Para comprobar el contenedor con Podman, construye la imagen a partir de `private_git_manager/` y pasa su nombre a `bash scripts/container-smoke.sh`. El script comprueba Ingress, bloqueo de accesos externos y recursos de interfaz.

Las pruebas simuladas no sustituyen la aceptación en un equipo real. En Home Assistant OS comprueba la instalación desde Mis-app, un complemento privado, una copia y la recuperación. En YunoHost comprueba la sesión de administrador en el mismo dominio, la instalación, actualización y desinstalación de un paquete privado, y la copia del propio gestor. Usa paquetes de prueba sin datos importantes.

## Aceptación en YunoHost

En desarrollo se comprueba el socket Unix de Uvicorn, la preparación de una
copia aislada del commit y el diálogo en Chromium con la API administrativa
simulada. La simulación cubre la sesión caducada, el rechazo de requisitos,
la instalación, la selección de instancia y la respuesta incierta del proxy.

En una VM con Debian 12, YunoHost 12.1.41.2 y SSOwat 12.1.1, se verificó
Private Git Manager 0.15.3. El navegador confirmó que el acceso anónimo quedaba
bloqueado y que el administrador podía abrir el portal. Se sincronizó por SSH
un paquete de un Forgejo privado, se instaló la versión 1.0 y se actualizó a
2.0 desde el portal. Se conservó un dato introducido en el formulario.
Después se cambió la subruta, se hizo una copia nativa del gestor, se retiró la
instancia de prueba con sus datos y se restauró la copia. Se recuperaron la
nueva URL, la clave, el repositorio y la sincronización SSH.

Para validar una versión en una instancia desechable de YunoHost, comprueba
este recorrido con un paquete y unas claves de prueba:

1. Instala el gestor en una subruta. Abre el portal con una cuenta administradora
   y comprueba el rechazo con una cuenta ajena al grupo autorizado.
2. Conecta por SSH un paquete privado. Instálalo, actualízalo y desinstálalo
   desde el portal. Comprueba el resultado y los registros de YunoHost.
3. Crea una copia del gestor, actualízalo y cambia su URL. Verifica que conserva
   las claves y los repositorios y que el portal abre en la nueva ubicación.
4. Restaura la copia en un entorno de prueba y verifica que puedes sincronizar
   de nuevo por SSH. Las copias incluyen credenciales.

## Copia externa en Forgejo

En un laboratorio con Home Assistant Container 2026.11.0 y Forgejo 17 se probó el alta con clave de despliegue SSH y la verificación de huella. Se generó una copia con la configuración automática y el cifrado nativo activado, se descargó desde Forgejo con la API de Home Assistant y se importó en una segunda instancia limpia. La clave incorrecta fue rechazada. Con la clave correcta se recuperaron el archivo de prueba y la configuración original.

Para repetir la prueba, usa la [guía de Forgejo](FORGEJO_BACKUPS.md) y crea antes un archivo de prueba identificable en la configuración. Después de restaurar, comprueba que reaparece con el mismo contenido. Home Assistant Container cubre la restauración de Core en una instancia limpia.

En Home Assistant OS 18.5, con Core 2026.11.0 y Supervisor 2026.10.5, se probó la misma integración contra Forgejo 17.0.1. La copia automática cifrada incluía Core, una aplicación local y las carpetas `share`, `media`, `ssl` y código de aplicaciones locales. Se descargó el `.tar` desde Forgejo y se verificó su indicador de cifrado. En la misma VM se desinstaló la aplicación y se retiraron cuatro marcadores. La restauración nativa desde Forgejo rechazó la clave incorrecta y recuperó la aplicación 1.0.0, su archivo de datos y los cuatro marcadores con la clave correcta.

El historial de versiones se mantiene en el [changelog](private_git_manager/CHANGELOG.md) y en Git.

## Instalar y actualizar integraciones por SSH

En Home Assistant OS 18.5, con Core 2026.11.0 y Supervisor 2026.10.5, se instaló Private Git Manager 0.15.0 como aplicación local. Desde el panel por Ingress se sincronizó un repositorio privado de Forgejo 17.0.1 con una clave de despliegue Ed25519 de lectura. Se instaló Forgejo Backup 0.1.0 y se actualizó a 0.1.1 tras publicar un segundo commit de prueba. En ambas operaciones se comprobó el commit en el diálogo. En disco quedaron la nueva versión y la anterior. Tras reiniciar Core, la API nativa volvió a listar el agente Forgejo de la configuración existente.
