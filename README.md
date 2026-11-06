# HA Private Git Manager

[Subir a Forgejo](FORGEJO.md)

**Versión 0.8.0 · Español / English · Aplicación nativa de Home Assistant OS**

Gestor privado de repositorios Git y aplicaciones locales. Genera claves SSH, verifica servidores, descarga código de GitHub, Forgejo o Gitea y solicita la instalación o actualización al Supervisor. La interfaz se abre dentro de Home Assistant mediante **Ingress**, sin publicar puertos del host.

![Identidad de la aplicación](private_git_manager/logo.png)

[English documentation](README.en.md) · [Guía dentro de Home Assistant](private_git_manager/DOCS.md) · [Validación técnica](VALIDATION.md)

## Qué incluye

| Área | Funciones |
| --- | --- |
| Interfaz | Español e inglés completos, tema claro/oscuro/sistema, diseño adaptable y navegación por teclado |
| SSH | Claves Ed25519, pública copiable y descargable, rotación y bloqueo de eliminación de claves en uso |
| Confianza | Identidad Ed25519 fijada por servidor y puerto; comparación explícita de huella SHA256 |
| Git | SSH con puertos personalizados, HTTPS con token, ramas y etiquetas, edición de referencias |
| Aplicaciones | Detección de manifiestos, instalación, actualización/reconstrucción y registro del commit |
| Ejecución | Inicio, parada y reinicio a través del Supervisor; primera instalación detenida |
| Operaciones | Cola en segundo plano, progreso persistente, reconexión de la interfaz y bloqueo de duplicados |
| Recuperación | Diario anterior a la sustitución de archivos, detección de interrupciones y recuperación explícita |
| Programación | Sincronización por repositorio cada 5 minutos o más; nunca instala código automáticamente |
| Registros | Niveles, búsqueda, exportación JSONL, historial traducido y registros del contenedor en español |

Arquitecturas declaradas: **aarch64** y **amd64**. Para Raspberry Pi 4 utiliza HA OS de 64 bits y aplicaciones que admitan `aarch64`. La compatibilidad final de cada aplicación depende de su propio manifiesto y del Supervisor.

## Instalación desde mi tienda

Añade [Mis-app a Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FGente-del-Condado%2FMis-app) e instala **HA Private Git Manager**. El repositorio de la tienda es `https://github.com/Gente-del-Condado/Mis-app`.

La carpeta de la app se publica automáticamente con GitHub Actions al actualizar `main`. Consulta [Publicación automática](PUBLISHING.md).

## Instalación inicial en Home Assistant

1. Extrae el paquete de distribución. Copia la carpeta `private_git_manager` completa a **`/addons/private_git_manager`** en Home Assistant mediante Samba o una aplicación de terminal con acceso a `/addons`.
2. Comprueba que existe `/addons/private_git_manager/config.yaml`, junto al `Dockerfile`, los requisitos y la carpeta `app`.
3. Recarga la tienda:

   ```sh
   ha addons reload
   ```

4. Abre **Ajustes → Aplicaciones → Tienda → Aplicaciones locales → HA Private Git Manager**. Activa el modo avanzado de tu perfil si hace falta para ver aplicaciones locales.
5. Instala, inicia y pulsa **Abrir interfaz web**. Puedes activar su entrada del panel lateral.

La construcción inicial requiere Internet. El gestor utiliza el rol `manager`, acceso de escritura a aplicaciones locales y su carpeta privada `/data`. Su panel está reservado a administradores. No requiere abrir SSH ni otro puerto del gestor en el host, desactivar el modo de protección ni montar `/config`.

### Actualizar desde la versión 0.1.0

Detén el gestor desde Home Assistant, reemplaza **solo sus archivos de programa** en `/addons/private_git_manager` por los de esta versión y reconstruye:

```sh
ha addons reload
ha addons rebuild local_private_git_manager
ha addons start local_private_git_manager
```

Conserva su `/data`: los registros existentes de claves, repositorios y despliegues se migran al arrancar. Realiza una copia de seguridad de la aplicación antes de reemplazarla. Si tu instalación asignó otro identificador, utiliza el mostrado por `ha addons list`.

## Repositorios individuales y catálogos maestros privados

Puedes conectar cualquiera de estos formatos por SSH o HTTPS:

```text
Una aplicación:                 Un catálogo maestro:
README.md                       README.md
config.yaml                     repository.yaml
Dockerfile                      primera_app/
                                segunda_app/
```

Cada carpeta de aplicación de un catálogo contiene su propio `config.yaml`, Dockerfile o imagen precompilada y, opcionalmente, `README.md`, `DOCS.md` e `icon.png`. También se admiten manifiestos de aplicaciones en subcarpetas de un repositorio individual.

El gestor detecta el formato y muestra **Aplicación individual** o **Repositorio maestro**, número de aplicaciones, nombre del catálogo, mantenedor y resumen del README. La búsqueda encuentra repositorios por esos datos y por los nombres y descripciones de sus aplicaciones.

- **Ver catálogo** abre el README general y permite seleccionar la presentación de cada aplicación.
- **Ver README** abre la presentación de una aplicación o un repositorio individual.
- **Documentación** muestra `DOCS.md` cuando existe.
- Los enlaces a otros Markdown del mismo repositorio permanecen dentro del lector privado. Las imágenes PNG, JPEG, GIF y WebP locales se sirven mediante Ingress, sin publicar el repositorio ni utilizar sus claves en el navegador.

`repository.yaml`, `repository.yml` y `repository.json` son opcionales. Se leen los campos de texto `name`, `maintainer`, `url` y `description`; si no hay manifiesto se sigue detectando cada aplicación por su configuración. No hace falta convertir un repositorio individual en maestro para utilizar el gestor. Si el catálogo incluye al propio HA Private Git Manager, se puede consultar su documentación y gestionar las demás aplicaciones; el gestor se actualiza desde Home Assistant.

Los README se presentan con formato Markdown, tablas y bloques de código. El HTML sin procesar se muestra como texto para impedir la ejecución de contenido del repositorio. Las imágenes externas, SVG y contenidos incrustados no se cargan automáticamente. Los documentos tienen un límite de 256 KiB y las imágenes de 8 MiB; no se permite leer `.git`, claves, rutas externas o enlaces simbólicos.

Los cambios se comparan por aplicación: modificar el README general del catálogo no marca como actualizables las aplicaciones cuyo código sigue igual.

Al actualizar, se recupera la información de presentación de las copias ya descargadas. Si modificas la documentación en Forgejo o GitHub, pulsa **Sincronizar** para verla actualizada.

## Carpetas locales que ya existen

El gestor se instala en `/addons/private_git_manager`. Cada aplicación privada utiliza su propia carpeta `/addons/<slug>`. Todas aparecen en la tienda de Home Assistant, pero `/addons` es el directorio de código de las aplicaciones locales: no es el almacén de los contenedores oficiales.

Desde **0.2.1**, al pulsar **Instalar** se revisa la carpeta de destino antes de confirmar:

- Si no existe, se instala normalmente.
- Si está vacía, se reutiliza sin borrar archivos de otra aplicación.
- Si contiene una aplicación con el mismo identificador, se muestra su ruta, versión y estado instalado. Marca el consentimiento y pulsa **Adoptar y aplicar** para gestionarla desde este repositorio.
- Si contiene otra aplicación, enlaces simbólicos o una estructura ambigua, no se sobrescribe.

Durante la adopción se conserva una copia del código anterior hasta confirmar el resultado. Si falla, el código se restaura; si el Supervisor pierde la conexión, ambas copias se conservan para recuperación explícita. Esto no sustituye una copia de seguridad de los datos ni de la imagen de la aplicación. Si la carpeta cambia después de revisarla, hay que revisarla de nuevo.

Si ya estaba instalada como aplicación local, se actualiza/reconstruye en vez de intentar instalarla otra vez. Si código y versión ya coinciden exactamente, basta con registrar su gestión. No hace falta borrar la carpeta existente ni eliminar la aplicación desde Home Assistant para resolver este caso.

### Aplicar la corrección a un gestor instalado localmente

Detén HA Private Git Manager, extrae el paquete **0.8.0** y reemplaza los archivos de `/addons/private_git_manager` con la carpeta del mismo nombre del paquete. Conserva sus datos persistentes. Después ejecuta en una terminal de Home Assistant:

```sh
ha addons reload
ha addons rebuild local_private_git_manager
ha addons start local_private_git_manager
```

Si lo instalaste desde un repositorio de la tienda, recarga la tienda y actualiza el gestor a **0.8.0** desde su ficha. Usa el identificador real mostrado por `ha addons list` si es distinto del ejemplo local.

## Primer repositorio de Forgejo

1. En **Claves SSH**, crea una identidad, por ejemplo `Forgejo HA`.
2. Registra su parte pública en **Forgejo → Repositorio → Configuración → Claves de despliegue**, con permiso de **solo lectura**.
3. En **Repositorios → Añadir repositorio**, introduce nombre, rama y URL:

   ```text
   ssh://forgejo@gentedelcondado:223/usuari/repositorio.git
   ```

   La URL es un ejemplo: el repositorio debe existir y contener una aplicación válida. Selecciona la clave creada.
4. Pulsa **Verificar servidor SSH → Obtener huella**. Comprueba la huella por un canal de confianza y pega la huella verificada `SHA256:...`.
5. Guarda, sincroniza y elige una aplicación detectada. Antes de instalar se muestran versión y commit para confirmarlos.
6. Usa **Configurar** para editar sus opciones y **Logs de la aplicación** para comprobar el arranque. La primera instalación queda detenida; puedes iniciarla desde el gestor.

En un servidor OpenSSH administrado por ti puedes obtener la huella con:

```sh
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Si Forgejo usa SSH integrado o un contenedor, comprueba la clave de ese servicio y puerto concreto. `ssh-keyscan` solo presenta una clave: no demuestra que sea la del servidor legítimo.

Para GitHub se admite `git@github.com:usuario/repositorio.git`; verifica su identidad con las [huellas oficiales de GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints).

### HTTPS y tokens

Introduce una URL limpia (`https://servidor/usuario/repo.git`), el usuario requerido por el proveedor y un token de lectura en **Credenciales HTTPS**. Los repositorios públicos no necesitan token. Nunca pegues credenciales en la URL. Al cambiar credenciales, dejar el token vacío elimina el token guardado.

### Rotación de claves

Crea una clave nueva, registra la pública, selecciona la nueva en **Credenciales** y sincroniza para probarla. Después revoca la anterior en el proveedor y elimínala del gestor. Las claves en uso no se pueden eliminar.

## Sincronización y actualizaciones

**Sincronizar** descarga la rama o etiqueta configurada en una copia de trabajo nueva. No cambia una aplicación ya instalada. Si falla la descarga o la validación, se conserva la copia anterior.

En **Editar** puedes cambiar la referencia y configurar un intervalo en minutos. `0` desactiva la programación. El mínimo es 5 minutos y el máximo 7 días. Cambiar la referencia invalida la detección anterior y exige sincronizar otra vez.

**Actualizar / reconstruir** verifica que el commit siga siendo el confirmado, prepara los archivos, guarda el diario de operación y solicita instalar, actualizar o reconstruir al Supervisor. Si la aplicación estaba iniciada, se detiene durante la sustitución y se solicita su inicio al finalizar. Si estaba detenida, se mantiene detenida. La versión instalada se consulta antes de marcar el trabajo como completado.

Los trabajos continúan al cerrar la interfaz. Su estado y progreso reaparecen al volver. Las operaciones se serializan y hay un máximo de 20 trabajos pendientes; no se encola dos veces un recurso ocupado.

### Recuperación

Si el Supervisor devuelve un resultado incierto o el gestor se interrumpe durante un despliegue, **no se supone que la instalación haya fallado**: podría seguir construyendo una imagen. Se conservan el diario y los archivos disponibles, y se bloquean nuevos despliegues de esa aplicación.

1. Comprueba desde Home Assistant que ya no hay una construcción o actualización activa. Consulta los registros del Supervisor.
2. Pulsa **Revisar recuperación** en el gestor.
3. Elige **Restaurar código anterior** o **Aceptar versión actual verificada** y confirma que revisaste el Supervisor.
4. La aceptación exige comprobar la versión instalada y la huella del árbol de archivos. La restauración comprueba la copia anterior cuando tiene su huella registrada.
5. Si restauraste código, puede ser necesario reconstruir o iniciar la aplicación desde Home Assistant. El gestor no revierte imágenes ni datos de aplicaciones.

El diario está en `state.json`; las carpetas temporales `.pgm-stage-*` y `.pgm-backup-*` están ocultas bajo `/addons` para que el Supervisor no las registre como aplicaciones. No las borres durante una recuperación. Si falta una copia verificable, el gestor se detiene y conserva la información para recuperación manual.

### Configuración y logs de una aplicación

Pulsa **Configurar** en una aplicación instalada. La vista principal es un **Formulario** generado a partir de `schema` y `translations` que devuelve el Supervisor para esa aplicación. Reutiliza sus campos, nombres y ayudas traducidas, con alternativa en inglés si falta la traducción elegida. No necesitas definir un formato adicional en tus aplicaciones.

Incluye texto, contraseñas ocultas con opción de mostrarlas, casillas, números con sus límites, selectores (incluidos dispositivos) y grupos o listas anidados. Puedes añadir o quitar elementos y activar o desactivar opciones opcionales, conservando la diferencia entre un valor `false` y una opción ausente. También muestra los ajustes disponibles de arranque, watchdog, actualizaciones automáticas, puertos, panel Ingress y audio.

**YAML avanzado** permite editar la representación completa cuando lo necesites. Puedes volver al formulario sin perder los cambios; si el YAML no es válido, se conserva el texto y la vista avanzada. Los valores no representables permanecen intactos y muestran una indicación para editarlos en la vista avanzada. Las referencias existentes `!secret nombre` se conservan, también en campos numéricos y selectores.

**Validar configuración** hace una comprobación preliminar y **Guardar configuración** vuelve a validarla mediante el Supervisor. Los cambios se aplican al próximo inicio; puedes marcar **Reiniciar después de guardar si la aplicación está en marcha**. Una aplicación detenida no se inicia automáticamente.

El editor conserva los cambios si falla el guardado y avisa antes de descartarlos. Si otra ventana modifica la configuración, se rechaza el guardado para evitar sobrescribirla. Las opciones no se guardan en el estado, trabajos, historial ni almacenamiento local del navegador. La representación enviada está limitada a 24.000 caracteres y cada petición HTTP a 32 KiB.

**Logs de la aplicación** abre su salida reciente como texto. Incluye búsqueda, actualización cada cinco segundos, pausa, refresco manual y descarga `.log`. El refresco se detiene al cerrar el visor y se pausa mientras la página está oculta. Los logs permanecen en memoria, se limitan a 512 KiB por lectura y se ocultan valores conocidos de opciones sensibles y tokens del gestor; no se garantiza detectar todas las credenciales que una aplicación pueda imprimir. También se pueden consultar durante una recuperación pendiente.

### Abrir la interfaz web por Ingress

Las aplicaciones que declaran `ingress: true` muestran **Abrir interfaz web** cuando están instaladas. Inícialas primero: el botón permanece desactivado mientras estén detenidas o tengan una operación pendiente.

Al pulsarlo, el gestor comprueba el estado y la disponibilidad de Ingress mediante el Supervisor y abre el panel de la aplicación en Home Assistant, fuera del marco del gestor. Home Assistant se encarga de crear y renovar la sesión con tu usuario actual. No se abren puertos directos ni URLs externas de `webui`, y no se devuelven ni guardan tokens de Ingress en el gestor.

Se usa `/app/<slug>` desde Home Assistant 2026.2 y `/hassio/ingress/<slug>` en versiones anteriores, según la versión que informa el Supervisor. Funciona también si la aplicación no está fijada a la barra lateral. Puedes volver al gestor con la navegación de Home Assistant o el botón Atrás.

### Retirar un repositorio

Puedes realizar el ciclo completo desde este gestor:

- **Instalar** descarga/prepara la aplicación y solicita su instalación al Supervisor. **Actualizar / reconstruir** aplica una nueva versión.
- **Desinstalar** solicita al Supervisor la desinstalación y conserva el código local para instalarla de nuevo.
- **Borrar aplicación** elimina `/addons/<slug>` y su registro. Si sigue instalada, el diálogo ofrece **Desinstalar y borrar** con autorización explícita. También funciona con copias previamente desvinculadas.

La desinstalación elimina los datos internos y las opciones de la aplicación; no se pueden recuperar desde el gestor. La carpeta pública `app_config` se conserva por defecto y solo se borra si marcas esa opción. El diálogo avisa de esta diferencia antes de confirmar. No se borran el repositorio Git descargado, el remoto ni las demás aplicaciones del catálogo maestro.

La casilla **Ocultar también esta aplicación del catálogo del gestor** evita que siga apareciendo como disponible después de borrarla. La preferencia se conserva al sincronizar y reiniciar; puedes revertirla desde **Aplicaciones ocultas → Volver a mostrar**. Mostrarla de nuevo no la instala. Desmarca la casilla si quieres conservarla visible para una futura instalación.

**Desvincular** conserva la carpeta local y solo retira el registro del gestor. Usa **Borrar aplicación** si también quieres retirar sus archivos de la tienda local. Solo los repositorios sin aplicaciones gestionadas se pueden eliminar.

El borrado se ejecuta en segundo plano con un diario persistente. Si falla, **Revisar recuperación → Terminar borrado** reintenta la limpieza de su carpeta temporal `.pgm-remove-*`. No la borres manualmente durante una operación pendiente. El gestor verifica que la aplicación esté desinstalada antes de retirar su carpeta. Una desinstalación con resultado incierto conserva el código y el diario: **Revisar recuperación** permite comprobar el estado sin repetirla. Reintentar la desinstalación requiere marcar una autorización adicional después de comprobar que no hay una operación activa. Reiniciar el gestor nunca repite automáticamente estas operaciones.

## Formato de las aplicaciones

```text
repositorio/
  mi_aplicacion/
    config.yaml
    Dockerfile
    run.sh
```

Se admiten manifiestos en la raíz o en subcarpetas hasta cinco niveles, con nombre `config.yaml`, `config.yml` o `config.json`. El paquete debe incluir los campos obligatorios de Home Assistant y un `Dockerfile` o una imagen precompilada.

Se copia la carpeta que contiene el manifiesto. Un Dockerfile que depende de archivos externos a esa carpeta necesita adaptar su contexto. Los paquetes no pueden contener otras aplicaciones anidadas, enlaces simbólicos ni archivos especiales. No se materializan submódulos ni objetos Git LFS. Un slug no puede colisionar con otra carpeta local; `private_git_manager` está reservado.

El límite de un paquete desplegado es 512 MiB y se exige margen libre antes de copiarlo. La descarga Git tiene tiempo máximo, pero no una cuota estricta de almacenamiento: evita repositorios gigantes.

## Registros y datos privados

| Ruta | Contenido |
| --- | --- |
| `/data/keys` | Claves privadas y públicas |
| `/data/repos` | Copias de trabajo privadas |
| `/data/state.json` | Metadatos, tokens y diario de recuperación |
| `/data/jobs.json` | Trabajos y errores persistentes |
| `/data/manager.log` | Registro JSONL; rotación a 1 MiB con tres copias anteriores |

Las carpetas privadas utilizan permisos `0700`; los archivos de estado, claves privadas, trabajos y registros, `0600`. Los tokens no se devuelven por la API, no se guardan en la configuración Git y no se incorporan a mensajes de procesos. La autenticación HTTPS utiliza `GIT_ASKPASS`.

Los secretos están protegidos por permisos, **sin cifrado adicional**. Las copias de seguridad contienen credenciales. El gestor no exporta claves privadas. Instalar aplicaciones implica confiar en su código y en los permisos que soliciten al Supervisor; no se verifican firmas de commits.

La interfaz conserva 500 eventos y hasta 100 trabajos terminados. Los textos del historial se traducen al idioma elegido; los registros originales de versiones anteriores pueden conservar su idioma. Los registros estándar del contenedor se escriben en español.

## Desarrollo y verificación

Requisitos: Python 3.11 o posterior, Git y OpenSSH. Las pruebas de transporte completo también utilizan `sshd` y `openssl`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
PGM_DEV=1 .venv/bin/uvicorn app.main:app --app-dir private_git_manager --host 127.0.0.1 --port 8099 --no-proxy-headers --no-access-log
```

Abre `http://127.0.0.1:8099`. En desarrollo se permiten claves, repositorios y detección; la instalación exige un Supervisor real. No publiques este modo en la red ni establezcas `SUPERVISOR_TOKEN` para simular una conexión.

```sh
.venv/bin/python -m pytest -q
node --check private_git_manager/app/static/app.js
podman build --format docker -t localhost/ha-private-git-manager:0.8.0 private_git_manager
scripts/container-smoke.sh
python3 scripts/package.py
```

La prueba de contenedores crea una red aislada con el proxy de prueba en `172.30.32.2` y comprueba acceso permitido, tráfico ajeno denegado, salud, activos, idiomas, claves, ocultación de tokens y registros. No monta datos del usuario ni publica puertos y elimina sus contenedores al terminar.

No ejecutes varias instancias o varios workers compartiendo `/data`. No hay coordinación entre procesos ni instalación automática, webhooks, importación de claves privadas, verificación de firmas o rollback de imágenes/datos. La prueba definitiva en HA OS y en hardware aarch64 se documenta por separado de las comprobaciones locales.

## Referencias

- [Configuración de aplicaciones](https://contributors.home-assistant.io/apps/reference/configuration/)
- [Ingress y sus rutas](https://contributors.home-assistant.io/apps/guides/ingress/)
- [API de la tienda](https://contributors.home-assistant.io/apps/supervisor-api/store/)
- [API de aplicaciones](https://contributors.home-assistant.io/apps/supervisor-api/apps/)
# HA-Private-Git-Manager
