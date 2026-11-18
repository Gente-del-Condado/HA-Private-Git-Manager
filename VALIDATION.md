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

Las pruebas simuladas no sustituyen la aceptación en un equipo real. En Home Assistant OS comprueba la instalación desde Mis_app_ha, un complemento privado, una copia y la recuperación. En YunoHost comprueba la sesión de administrador en el mismo dominio, la instalación, actualización y desinstalación de un paquete privado, y la copia del propio gestor. Usa paquetes de prueba sin datos importantes.

## 0.17.2 — AppArmor en HAOS — 18 de noviembre de 2026

- HAOS 18.4, Supervisor 2026.11.0 y Core 2026.11.2, en dos VM independientes:
  amd64 y aarch64. Sin cambiar sus recursos ni la configuración de Core. El
  gestor de laboratorio usa datos propios y una configuración ficticia de Core.
- Perfil propio en **enforce**: puntuación instalada 7/8 y protección activada.
  Se conserva el rol manager. El ABI 3.0 explícito evita que las reglas de red
  queden sin mediar con el parser 3.1.7 del laboratorio.
- Suite nativa sin los archivos opcionales de navegador: **215 pruebas correctas
  en cada arquitectura**; un caso opcional de navegador omitido. Incluye Git SSH
  real y Git HTTPS con autenticación y TLS verificado contra servidores locales,
  migración, revisión del commit, recuperación, copias y paquete reproducible.
  El aviso de Starlette/httpx es de obsolescencia del cliente de pruebas.
- `python scripts/check_apparmor.py --confirm-disposable-lab` comprueba en el proceso
  confinado Git, Ed25519, age, askpass, DNS/TLS y denegaciones de secretos de Core,
  modificación del programa y ejecución de pip. Git HTTPS también consultó la
  tienda pública con validación de certificados, sin credenciales ni escritura.
- Desde la IP real de Ingress se sincroniza un repositorio SSH ficticio,
  verificando la huella, se revisa el commit y se instala una app desechable y
  una integración en Core ficticio. Se prueba la recuperación explícita de una
  instalación cuyo contenedor de laboratorio no pudo construir su imagen.
- La copia nativa cifrada y su restauración recuperan una opción de prueba.
  La actualización a 1.0.1 conserva esa opción; la integración también cambia de
  versión. El reinicio del gestor conserva repositorio y clave: una sincronización
  posterior vuelve a autenticarse por SSH. Este recorrido se repite en ambas VM.
- Ruff, formato, paquete y revisión de los archivos distribuidos. El paquete
  incluye `apparmor.txt` y `APPARMOR.md`. No se añaden credenciales ni fixtures
  privados a Git. El ayudante de tests espera la liberación del bloqueo después
  del estado terminal, sin cambiar la lógica de trabajos del producto.

La aceptación usa servicios ficticios y no acredita todos los proveedores
externos ni escenarios de navegador. No se instala ni restaura Core real,
YunoHost o aplicaciones del usuario con esta revisión. Para repetirla consulta
[AppArmor](private_git_manager/APPARMOR.md); nunca uses el estado de producción.

## Migración cifrada del catálogo

En un laboratorio con Forgejo 17.0.1 se exportó el catálogo por SSH desde la
imagen de Home Assistant con un estado nuevo y se importó en otro gestor
recién inicializado en modo YunoHost, por socket Unix. Chromium verificó la
revisión y la confirmación del portal. La clave age incorrecta fue rechazada
y repetir la importación conservó una sola entrada por repositorio y referencia.
También se comprobó el formato de envío por SSH a un GitHub privado con un
`push --dry-run`, sin escribir en ese catálogo.

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

## Copias cifradas de aplicaciones por SSH

### Aceptación con AppArmor — 18 de noviembre de 2026

Se probó la imagen pública `ghcr.io/gente-del-condado/ha-private-git-manager:0.17.2`
en HAOS 18.4 amd64, Supervisor 2026.11.0 y Core 2026.11.2. El gestor de
laboratorio usa su propio estado y no monta la configuración de Core. Conserva
el perfil distribuido, en modo **enforce**, y el rol manager.

Los destinos son un repositorio privado en Forgejo 17.0.1 desechable y un
repositorio privado real en GitHub. Cada uno utiliza una clave Ed25519 del
gestor registrada con escritura y una huella SSH comprobada. La clave temporal
de GitHub se registra como clave de despliegue. Las pruebas no necesitan
desactivar AppArmor ni usar un agente SSH.

- La programación conserva un intervalo de una hora. Para acelerar el ensayo,
  con el gestor detenido se adelanta únicamente `next_at` de la aplicación
  ficticia. Después del arranque, el programador real crea y envía la copia.
- Cada `.tar` cifrado ocupa 24 791 040 bytes e incluye un archivo de 20 MiB de
  datos aleatorios. El tamaño obliga a usar varios fragmentos en Git.
- Se verifica `protected: true` en la copia nativa y se retira el archivo local.
  La recuperación usa la referencia y el commit del destino privado. El SHA-256
  y el tamaño del `.tar` importado coinciden con los originales.
- La contraseña incorrecta es rechazada. Con la correcta se recuperan el
  archivo marcador, la suma SHA-256 del archivo aleatorio y la opción original.
- Se repite la recuperación después de desinstalar la aplicación ficticia y
  borrar otra vez su copia local. Cada proveedor permite reinstalar la versión
  1.0.0 y recuperar los mismos archivos y opciones.
- El proceso mantiene AppArmor en **enforce** durante ambas transferencias y
  restauraciones. El diario no registra denegaciones de ese perfil durante el
  ensayo. La instantánea pública del gestor no incluye la contraseña programada.

La comprobación de distribución compara los 36 archivos de la aplicación con
Mis_app_ha y los 13 del componente con Mis_componente_ha. Coinciden con Forgejo.
La tienda añade a `config.yaml` el campo `image:` esperado. La imagen 0.17.2
se descarga anónimamente de GHCR y su índice contiene amd64 y arm64. Al iniciar
la revisión, los publicadores estaban completados y no había Actions pendientes
ni en ejecución en esos dos catálogos.

### Pruebas anteriores


El flujo de Private Git Manager 0.17.0 se probó con un Supervisor simulado y un
repositorio privado desechable en Forgejo 17.0.1. Se verificó la programación,
el reintento tras un fallo de envío, la importación del mismo `.tar` byte por
byte y la restauración con la contraseña correcta. Chrome, con un ancho de
390 píxeles, cubrió el envío manual y la revisión de la restauración. Se
comprobó el envío de una etiqueta a GitHub privado en modo de simulación.

Para repetir el flujo con un Supervisor real, instala una aplicación de
prueba, añade un dato reconocible y programa una copia a un repositorio
privado. Espera a que termine el envío, cambia el dato y retira la copia
local. Recupera la copia desde Git y verifica que la contraseña incorrecta
falla y que la correcta recupera el dato original.

## Copia externa en Forgejo

En un laboratorio con Home Assistant Container 2026.11.0 y Forgejo 17 se probó el alta con clave de despliegue SSH y la verificación de huella. Se generó una copia con la configuración automática y el cifrado nativo activado, se descargó desde Forgejo con la API de Home Assistant y se importó en una segunda instancia limpia. La clave incorrecta fue rechazada. Con la clave correcta se recuperaron el archivo de prueba y la configuración original.

Para repetir la prueba, usa la [guía de Forgejo](FORGEJO_BACKUPS.md) y crea antes un archivo de prueba identificable en la configuración. Después de restaurar, comprueba que reaparece con el mismo contenido. Home Assistant Container cubre la restauración de Core en una instancia limpia.

En Home Assistant OS 18.5, con Core 2026.11.0 y Supervisor 2026.10.5, se probó la misma integración contra Forgejo 17.0.1. La copia automática cifrada incluía Core, una aplicación local y las carpetas `share`, `media`, `ssl` y código de aplicaciones locales. Se descargó el `.tar` desde Forgejo y se verificó su indicador de cifrado. En la misma VM se desinstaló la aplicación y se retiraron cuatro marcadores. La restauración nativa desde Forgejo rechazó la clave incorrecta y recuperó la aplicación 1.0.0, su archivo de datos y los cuatro marcadores con la clave correcta.

El historial de versiones se mantiene en el [changelog](private_git_manager/CHANGELOG.md) y en Git.

## Instalar y actualizar integraciones por SSH

En Home Assistant OS 18.5, con Core 2026.11.0 y Supervisor 2026.10.5, se instaló Private Git Manager 0.15.0 como aplicación local. Desde el panel por Ingress se sincronizó un repositorio privado de Forgejo 17.0.1 con una clave de despliegue Ed25519 de lectura. Se instaló Forgejo Backup 0.1.0 y se actualizó a 0.1.1 tras publicar un segundo commit de prueba. En ambas operaciones se comprobó el commit en el diálogo. En disco quedaron la nueva versión y la anterior. Tras reiniciar Core, la API nativa volvió a listar el agente Forgejo de la configuración existente.
