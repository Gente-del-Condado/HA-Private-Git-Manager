# Publicación automática en Mis_app_ha

## Transición a Forgejo → privado → público

El privado `Gente-del-Condado/HA-Private-Git-Manager-private` recibe main,
ramas y etiquetas de Forgejo por su propia deploy key SSH. Actions permanece
**deshabilitado** en ese privado. El workflow manual **Comprobar espejo privado
de PGM** valida identidad, privacidad, SHA de Forgejo y sumas desde el público.

**Publicar PGM desde espejo privado** se instala inicialmente desactivado.
Una ejecución manual con `publish=false` descarga main y la etiqueta de versión,
exporta únicamente los 126 archivos enumerados en
`.github/pgm-publication/public-files.txt` y ejecuta las pruebas del producto sin
credenciales. Los archivos nuevos dentro de una distribución requieren revisar
esa lista. Las fuentes privadas completas nunca se suben como artefacto.

Después de validar la prueba se desactiva la réplica directa de Forgejo al
público y se activa `ENABLE_MIRROR_PUBLICATION=true` en el público. La ejecución
manual con `publish=true`, y después la consulta horaria, publican main y las
etiquetas nuevas con el token efímero del propio repositorio. Las etiquetas
anteriores nunca se mueven; se comprueba que su paquete sigue coincidiendo. Un
recibo en `.publication/pgm.json` identifica el origen y sus sumas. Si main y
la etiqueta privada no cambian, no se repiten pruebas ni publicaciones.

La comprobación previa al push rechaza cambios de referencia. El exportador
no reemplaza los workflows ni su controlador: esos cambios se revisan en Forgejo
y se despliegan expresamente al público, como parte del mantenimiento de CI.
No se ejecuta código descargado en el job que posee permiso de escritura.

El workflow llama explícitamente a los publicadores de la app, componente y
manual después del push, porque el GITHUB_TOKEN no encadena workflows por push.
Se conservan la raíz YunoHost, los tags y la URL de Pages. Todo Actions corre
en repositorios públicos. La aplicación conserva su versión, datos y permisos.

`MIRROR_READ_TOKEN` solo lee Contents/Metadata del nuevo privado. Las claves
`MIS_APP_DEPLOY_KEY` y `MIS_COMPONENT_GITHUB_DEPLOY_KEY` siguen siendo necesarias
para los dos publicadores de tienda en esta fase. No retirarlas hasta sustituir
esos enlaces por consumidores autónomos y comprobar sus resultados.

La ruta antigua descrita abajo se mantiene operativa hasta completar este corte.

El código se desarrolla en el origen de
[Forgejo](https://gentedelcondado.es/forgejo/wolfbelmi88/HA-Private-Git-Manager).
[GitHub](https://github.com/Gente-del-Condado/HA-Private-Git-Manager) es su espejo
público y ejecuta los publicadores. Sube y fusiona las revisiones en Forgejo;
no edites el espejo. No hay publicación de regreso a Forgejo. La tienda pública de Home Assistant es
[Mis_app_ha](https://github.com/Gente-del-Condado/Mis_app_ha).

Al subir cambios a `main` dentro de `private_git_manager/`, GitHub Actions ejecuta
**Publicar en Mis_app_ha** y copia esa carpeta completa a la raíz de la tienda.
También se puede ejecutar desde **Actions → Publicar en Mis_app_ha → Run workflow**.
Los cambios en el script de publicación o en el workflow también lo ejecutan.
No hace falta ejecutar ningún programa en tu ordenador después del push.

La sincronización incluye archivos añadidos, modificados y eliminados. Solo toca
`private_git_manager/`; conserva las demás apps y los archivos de la tienda.
Si no hay diferencias, no crea ningún commit. La copia siempre toma el último
`main` al empezar para evitar publicar una versión antigua de una ejecución en cola.
No edites esta carpeta en Mis_app_ha: la siguiente publicación la sustituirá.

## Credencial de GitHub Actions (una sola vez)

El `GITHUB_TOKEN` normal solo escribe en su propio repositorio. Para publicar en
la tienda se utiliza una clave SSH de despliegue independiente:

1. Genera una clave Ed25519 dedicada sin contraseña.
2. En **Mis_app_ha → Settings → Deploy keys**, registra su parte pública y marca
   **Allow write access**. Esta clave solo concede acceso a Mis_app_ha.
3. En **HA-Private-Git-Manager → Settings → Secrets and variables → Actions**,
   crea el secreto `MIS_APP_DEPLOY_KEY` con el contenido completo de la clave
   privada, incluidas las líneas `BEGIN` y `END`.

No uses tu clave SSH personal para esta automatización. La clave privada nunca
se incorpora a un commit. GitHub Actions debe estar habilitado y `main` de Mis_app_ha
debe admitir los pushes de esta clave; si se protege esa rama, hay que adaptar
la política de publicación.

## Publicar una actualización

1. Modifica la app en `private_git_manager/`.
2. Cambia `version` en `private_git_manager/config.yaml` cuando quieras que Home
   Assistant ofrezca una actualización y documenta el cambio en `CHANGELOG.md`.
3. Fusiona la revisión en `main` de Forgejo, verifica su réplica y comprueba que **Publicar en Mis_app_ha** termina en verde.
4. Home Assistant detectará la versión al comprobar actualizaciones de la tienda.
   La publicación no instala ni actualiza automáticamente las instancias de los usuarios.

Para contrastar una publicación reciente, consulta el SHA actual de `main` con
`git ls-remote` y lee los archivos de ese commit. Las URL RAW que siguen el
nombre de una rama pueden conservar temporalmente una respuesta anterior en caché.

La app se prepara en GitHub Actions para `amd64` y `aarch64`; Home Assistant
descarga de GHCR la imagen ya compilada que anuncia la tienda.

Para generar el archivo de instalación local, ejecuta `python3 scripts/package.py`
y verifica el SHA-256 que acompaña al archivo de `dist/`. El contenido parte de
una lista explícita y excluye datos de ejecución.

## Manual en GitHub Pages

En el repositorio de código, abre **Settings → Pages → Build and deployment**
y elige **GitHub Actions** como origen. Luego ejecuta **Publicar el manual en
GitHub Pages** desde Actions. Los siguientes cambios en `docs/` publicados a
`main` activan el mismo flujo. El artefacto contiene solo el manual estático.

La URL prevista es [gente-del-condado.github.io/HA-Private-Git-Manager](https://gente-del-condado.github.io/HA-Private-Git-Manager/).
Comprueba que la ejecución terminó y abre el enlace de su despliegue.

## YunoHost

El paquete se instala desde la raíz de una etiqueta de Git. Coordina
`manifest.toml`, la versión de la aplicación y el changelog. Las notas que
aparecen en la administración de YunoHost están en `doc/`. Revisa los
comandos de instalación y actualización en [YUNOHOST.md](YUNOHOST.md).

## Catálogo Mis_componente_ha

El catálogo público https://github.com/Gente-del-Condado/Mis_componente_ha se
conecta como repositorio Git en Private Git Manager. El publicador actualiza
solo custom_components/pgm_forgejo_backup/ y conserva los demás componentes.
Utiliza `MIS_COMPONENT_GITHUB_DEPLOY_KEY`, limitado a ese destino de GitHub.
El publicador de la aplicación utiliza `MIS_APP_DEPLOY_KEY`. Son independientes;
comprueba ambas ejecuciones cuando cambien los dos productos. Estos flujos se
activan por cambios en `main`; no dependen del flujo de calidad de Headscale,
PiVigia o JackSignal. Ejecuta primero las pruebas indicadas en VALIDATION.md.


## Imágenes precompiladas de Home Assistant

Forgejo sigue siendo el origen y GitHub el espejo. El publicador entrega el
contenido aprobado a `build-source` de `Mis_app_ha`. Un único workflow de esa
tienda construye imágenes nativas `amd64` y `aarch64`, ejecuta las pruebas de
arranque con datos desechables y crea un índice multi arquitectura en GHCR.
Solo después de verificar su descarga anónima actualiza la aplicación en `main`
y añade `image:`. La versión anterior sigue instalable mientras se prepara la nueva.

Los Dockerfile y fuentes se conservan; Home Assistant descarga la imagen preparada.
No se cambian slugs, opciones, volúmenes, permisos, datos ni credenciales. Una imagen
ya distribuida no se sustituye con otro contenido: aumenta la versión al cambiar
el contexto de compilación. El cambio inicial publica las versiones actuales sin
forzar actualizaciones ni reinstalaciones de los equipos existentes.

El controlador común se mantiene en `packaging/homeassistant-store/` de
`headscale_gateway` en Forgejo y se exporta a `.github/ha-images/` y al workflow
de `Mis_app_ha`. No escribe en los principales ni devuelve cambios a Forgejo.
