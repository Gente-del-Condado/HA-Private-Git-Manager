# Publicación automática en Mis-app

El código se desarrolla en este repositorio. La tienda pública de Home Assistant es
[Mis-app](https://github.com/Gente-del-Condado/Mis-app).

Al subir cambios a `main` dentro de `private_git_manager/`, GitHub Actions ejecuta
**Publicar en Mis-app** y copia esa carpeta completa a la raíz de la tienda.
También se puede ejecutar desde **Actions → Publicar en Mis-app → Run workflow**.
Los cambios en el script de publicación o en el workflow también lo ejecutan.
No hace falta ejecutar ningún programa en tu ordenador después del push.

La sincronización incluye archivos añadidos, modificados y eliminados. Solo toca
`private_git_manager/`; conserva las demás apps y los archivos de la tienda.
Si no hay diferencias, no crea ningún commit. La copia siempre toma el último
`main` al empezar para evitar publicar una versión antigua de una ejecución en cola.
No edites esta carpeta en Mis-app: la siguiente publicación la sustituirá.

## Credencial de GitHub Actions (una sola vez)

El `GITHUB_TOKEN` normal solo escribe en su propio repositorio. Para publicar en
la tienda se utiliza una clave SSH de despliegue independiente:

1. Genera una clave Ed25519 dedicada sin contraseña.
2. En **Mis-app → Settings → Deploy keys**, registra su parte pública y marca
   **Allow write access**. Esta clave solo concede acceso a Mis-app.
3. En **HA-Private-Git-Manager → Settings → Secrets and variables → Actions**,
   crea el secreto `MIS_APP_DEPLOY_KEY` con el contenido completo de la clave
   privada, incluidas las líneas `BEGIN` y `END`.

No uses tu clave SSH personal para esta automatización. La clave privada nunca
se incorpora a un commit. GitHub Actions debe estar habilitado y `main` de Mis-app
debe admitir los pushes de esta clave; si se protege esa rama, hay que adaptar
la política de publicación.

## Publicar una actualización

1. Modifica la app en `private_git_manager/`.
2. Cambia `version` en `private_git_manager/config.yaml` cuando quieras que Home
   Assistant ofrezca una actualización y documenta el cambio en `CHANGELOG.md`.
3. Sube los cambios a `main` y comprueba que **Publicar en Mis-app** termina en verde.
4. Home Assistant detectará la versión al comprobar actualizaciones de la tienda.
   La publicación no instala ni actualiza automáticamente las instancias de los usuarios.

La app se construye en Home Assistant desde su `Dockerfile` para `amd64` o
`aarch64`. Esta publicación copia código; no genera imágenes precompiladas.
