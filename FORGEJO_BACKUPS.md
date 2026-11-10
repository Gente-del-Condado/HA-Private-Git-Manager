# Copias nativas de Home Assistant en Forgejo y GitHub

![Icono de Forgejo Backup](custom_components/pgm_forgejo_backup/brand/icon.png)

**Private Git Manager · Forgejo Backup** es una integración complementaria del proyecto. Registra un destino en **Ajustes → Sistema → Copias de seguridad**. Home Assistant crea, cifra y restaura los archivos. El módulo los guarda en un repositorio Forgejo privado usando Git por SSH.

## Instalar y conectar

En Home Assistant 2026.11 o posterior, abre [Forgejo Backup en el Marketplace](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Gente-del-Condado&repository=HA-Private-Git-Manager&category=integration). Si se solicita, conecta GitHub, añade el repositorio como **Integración** y pulsa **Instalar**. Después sigue desde el paso 2 para configurar el destino.

1. En Private Git Manager 0.15.0 o posterior, añade por SSH y sincroniza la rama `main` de **Mis-component** en [Forgejo](https://gentedelcondado.es/forgejo/wolfbelmi88/Mis-component) o [GitHub](https://github.com/Gente-del-Condado/Mis-component). El catálogo usa una clave de despliegue de lectura. Busca **Forgejo Backup** en **Componentes** (o en la ficha del repositorio en la versión 0.15.0) y pulsa **Instalar integración**, revisa el commit y espera el resultado del trabajo. Reinicia Core. Para una instalación manual, copia `custom_components/pgm_forgejo_backup` a `/config/custom_components/`. Usa Home Assistant 2026.11 o posterior con Git y OpenSSH en Core.
2. Crea un repositorio **privado y dedicado a copias** en Forgejo. Puedes dejarlo vacío. Forgejo Backup 0.1.1 o posterior crea la rama `main` y un README al subir la primera copia si el repositorio carece de ramas. La misma inicialización se aplica en la próxima subida a repositorios que solo tienen etiquetas de copias. Si ya hay una rama, se conserva. Copia la URL SSH de clonación, por ejemplo `ssh://git@forgejo.example.org:2222/equipo/copias.git`.
3. En **Ajustes → Dispositivos y servicios → Añadir integración**, busca **Private Git Manager · Forgejo Backup** e introduce la URL.
4. Añade la clave pública que muestra el asistente en **Ajustes del repositorio → Claves de despliegue**, con permiso de escritura. La clave es exclusiva de este destino. Conserva las claves de lectura del gestor para los repositorios de aplicaciones.
5. Obtén por un canal de confianza una huella SHA256 del servidor SSH de Forgejo e introdúcela en el asistente. La integración fija esa clave de servidor y verifica el acceso con la identidad generada.
6. En **Ajustes → Sistema → Copias de seguridad**, configura las copias automáticas, marca Forgejo como ubicación y deja activado el cifrado para esa ubicación. Selecciona los datos que quieras incluir, como aplicaciones, base de datos y carpetas en HA OS. Guarda el **kit de emergencia** en un lugar independiente.

Home Assistant conserva la programación y la retención. Puedes mantener la ubicación local y Forgejo a la vez. La integración rechaza la subida cuando Home Assistant le entrega una copia sin cifrado. El registro Git contiene también los metadatos de inventario, como nombre, fecha y versiones. La privacidad de esos metadatos depende de los permisos del repositorio.

## Usar GitHub como destino

Desde **Forgejo Backup 0.2.0**, puedes añadir un repositorio **privado** de
GitHub.com como otra ubicación. Crea un repositorio dedicado a las copias y
sigue el mismo asistente SSH. Puedes pegar la URL de clonación
`git@github.com:equipo/copias-ha.git` o `ssh://git@github.com/equipo/copias-ha.git`.
Registra la clave de despliegue generada con **Allow write access** en ese
repositorio y compara la huella con la documentación oficial de GitHub.
Selecciona **GitHub** como ubicación de la copia en Home Assistant y activa
el cifrado para esa ubicación.

Para habilitar **Descargar backup.tar** desde el README, abre **Configurar**
en la entrada de GitHub. Usa la URL web del repositorio y un token de acceso
personal detallado, limitado a ese repositorio privado, con **Contents → Read
and write**. GitHub publica el TAR cifrado como adjunto de un lanzamiento.
El navegador descarga el archivo con tu sesión de GitHub iniciada. GitHub
también conserva los fragmentos por SSH y el enlace al ZIP como alternativa.
El índice muestra la zona horaria de Home Assistant.

El límite del proveedor GitHub es **1900 MiB por copia**, para dejar margen
dentro de los límites de GitHub por envío Git y por adjunto. GitHub y Forgejo
se configuran como entradas separadas y pueden utilizarse a la vez. Las
copias de aplicaciones individuales siguen gestionándose desde el Supervisor.

- [Huellas SSH de GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)
- [Permisos de la API de adjuntos de GitHub](https://docs.github.com/en/rest/releases/assets)
- [Límite por envío Git](https://docs.github.com/en/get-started/using-git/troubleshooting-the-2-gb-push-limit)

## Descargar y restaurar

Si Forgejo está configurado en Home Assistant, abre la copia y elige restaurarla desde esa ubicación. Introduce la clave del kit de emergencia y marca las aplicaciones y carpetas que quieras recuperar.

En la lista de copias de Home Assistant, abre la copia y elige descargarla desde la ubicación Forgejo. Selecciona la descarga cifrada si vas a conservar el archivo. En una instalación limpia, carga el `.tar` descargado y usa la clave del kit de emergencia para restaurar.

### Desde la web de Forgejo

**Descarga directa del TAR cifrado (0.1.4 o posterior).** En Home Assistant,
abre **Ajustes → Dispositivos y servicios → Forgejo Backup → Configurar**.
Introduce la URL web HTTPS del mismo repositorio de copias y un token de
Forgejo limitado a ese repositorio, con permiso `write:repository`. Conserva
la clave SSH de la integración. El token se usa desde Home Assistant para
publicar el adjunto y nunca se incorpora al README.

Si Forgejo está detrás de YunoHost, la integración necesita que las peticiones a
`/forgejo/api/` lleguen a Forgejo para que pueda comprobar el token. Si esa ruta
redirige al portal de YunoHost, abre **Usuarios → Grupos y permisos** y
comprueba que **Forgejo API** está permitido para **Visitantes**.
El [paquete oficial de Forgejo para YunoHost](https://github.com/YunoHost-Apps/forgejo_ynh/blob/master/manifest.toml)
declara acceso de visitantes únicamente para esa ruta. Forgejo sigue validando
el token y los permisos del repositorio privado. Prueba `/forgejo/api/v1/version`
en una ventana privada. Si llega a Forgejo, devuelve JSON. Usa la URL del repositorio
sin `.git` en 0.1.4. Desde 0.1.5 se admiten ambas formas.

Las nuevas copias mostrarán **Descargar backup.tar** cuando se publique el
adjunto. Abre el enlace con tu sesión web de Forgejo y verifica el SHA-256
de **Ficha** antes de importar el archivo. El adjunto conserva el cifrado de
Home Assistant y ocupa espacio adicional en Forgejo. Si el servidor o el
proxy rechaza su tamaño, revisa los registros y usa la descarga por ZIP.
Las copias anteriores conservan su enlace al ZIP. Mantén configurado el
token para que Home Assistant pueda retirar los adjuntos al aplicar la retención.

Desde la versión 0.1.2, Forgejo Backup actualiza su README automático al subir o
eliminar copias. En **Copias recientes** aparecen las 20 últimas, con fecha,
nombre, tamaño y enlaces a su ficha y al ZIP. Desde la versión 0.1.4, la fecha
usa la zona horaria de Home Assistant y muestra el desfase respecto a UTC. La integración escribe el índice
por SSH. Si el repositorio ya tiene un README propio, lo conserva y puedes
acceder a las copias desde **Código → Etiquetas**.

1. Abre **Ficha** y anota el SHA-256 de la copia que quieras recuperar.
2. Pulsa **Descargar ZIP** para la misma copia. Extrae el ZIP en una carpeta nueva.
3. Abre una terminal en la carpeta que contiene `part-000000`, `part-000001`,
   etc. Ejecuta `LC_ALL=C cat part-* > backup.tar` y luego `sha256sum backup.tar`.
4. Compara la huella con la ficha. Si coincide, importa `backup.tar` en Home
   Assistant y usa la clave del kit de emergencia.

### Por SSH desde otro equipo

Si solo tienes acceso a Forgejo, puedes recuperar el `.tar` desde otro equipo con Git y una clave SSH autorizada. Sustituye la URL y el identificador por tus valores. Verifica primero la huella SSH por un canal de confianza.

```sh
git init copias-ha
cd copias-ha
git remote add origin ssh://git@forgejo.example.org:2222/equipo/copias.git
git ls-remote --tags origin 'refs/tags/pgm-data-*'

id=IDENTIFICADOR_DE_LA_COPIA
git fetch --no-tags --depth=1 origin "refs/tags/pgm-meta-$id"
git show FETCH_HEAD:metadata.json
git fetch --no-tags --depth=1 origin "refs/tags/pgm-data-$id"
git archive FETCH_HEAD | tar -xf -
LC_ALL=C cat part-* > backup.tar
sha256sum backup.tar
```

Ejecuta estos pasos en una carpeta de trabajo nueva y compara el SHA-256 con el campo `sha256` de los metadatos antes de importar el archivo. La copia se restaura desde el asistente nativo de Home Assistant.

## Resolver problemas

- **La copia se subió pero falta en el README.** El índice se refresca al subir o borrar copias. Solo actualiza el README creado por Forgejo Backup. Usa **Código → Etiquetas** para encontrar la ficha y los datos si tienes un README propio o si la copia queda fuera de las 20 recientes.
- **Forgejo rechaza la subida.** Comprueba el permiso de escritura de la clave de despliegue, la huella registrada y el espacio disponible. Consulta los registros de Home Assistant para ver el error concreto.
- **Home Assistant no acepta el archivo.** Comprueba que importas el `.tar` reconstruido, que el SHA-256 coincide y que la clave de emergencia corresponde a esa copia.

## Almacenamiento y mantenimiento

El proveedor Git y SSH está en `custom_components/pgm_forgejo_backup/providers/forgejo.py`. `backup.py` implementa el contrato nativo de Home Assistant y exige el indicador de cifrado antes de abrir el flujo. El proveedor divide el archivo cifrado en bloques de 16 MiB, conserva su SHA-256 y publica dos referencias Git por copia de forma atómica. La descarga reconstruye y verifica el archivo original. La retención elimina ambas referencias. Forgejo recupera el espacio de los objetos sin referencias según su mantenimiento Git.

El límite del módulo es de 8 GiB por copia. Los límites de Forgejo pueden ser inferiores. Reserva espacio local temporal para el archivo y los objetos Git durante la transferencia. Para cambiar de clave de servidor o de despliegue, vuelve a configurar la integración y selecciona de nuevo su ubicación de copia. Mantén acceso de recuperación al repositorio independiente del equipo de Home Assistant.

- [Interfaz BackupAgent de Home Assistant](https://contributors.home-assistant.io/core/integrations/backup/)
- [Copias de seguridad y kit de emergencia](https://www.home-assistant.io/common-tasks/general/backups/)
- [Autenticación SSH de Forgejo](https://forgejo.org/docs/latest/user/repo-mirror/#mirror-via-ssh)

La [validación en Home Assistant OS](VALIDATION.md#copia-externa-en-forgejo) cubre la restauración de una aplicación local, sus datos y las carpetas de Supervisor.
