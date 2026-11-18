# Publicación desde Forgejo y consumidores públicos

Forgejo es la fuente. Su réplica SSH escribe únicamente en
`HA-Private-Git-Manager-private`, que tiene Actions desactivado.
El público `HA-Private-Git-Manager` lee ese espejo con `MIRROR_READ_TOKEN`
(Contents y Metadata de lectura, solo ese privado), exporta rutas revisadas,
valida el producto sin credenciales de escritura y publica con su GITHUB_TOKEN.
Los workflows/controladores requieren revisión y traslado explícito al público;
no se importan automáticamente del privado.

El publicador conserva main, etiquetas inmutables, raíz YunoHost y Pages.
`.publication/pgm.json` registra el SHA privado y los hashes/modos exportados.
`ENABLE_MIRROR_PUBLICATION=true` activa la consulta horaria y publicación; el
modo manual permite validar sin publicar. Una revisión sin cambios no repite
pruebas costosas ni publicaciones. Los archivos nuevos requieren revisar
`.github/pgm-publication/public-files.txt`.

## Tiendas sin claves de escritura compartidas

- `Mis_app_ha` consume el main público de PGM, verifica recibo, hashes, modos,
  slug y versión; solo actualiza `private_git_manager/` en `build-source` y su
  recibo `.sources/pgm-public.json`. Después invoca su constructor de imágenes.
- `Mis_componente_ha` consume `custom_components/pgm_forgejo_backup/`, valida
  su manifiesto y sumas y conserva las demás integraciones.

Ambos leen anónimamente y escriben con el GITHUB_TOKEN de su propio repositorio.
Los consumidores canónicos están en `.github/pgm-publication/` y se exportan
expresamente a las tiendas. No ejecutan el código descargado.
Los publicadores SSH antiguos se han retirado: `MIS_APP_DEPLOY_KEY` y
`MIS_COMPONENT_GITHUB_DEPLOY_KEY` dejan de ser necesarios. Tampoco se necesitan
claves de publicación hacia Forgejo. La clave de las copias PGM es independiente
 y no se elimina como parte de la publicación.

## Actualizar la aplicación

Cambia `private_git_manager/`, incrementa la versión para cualquier cambio del
contexto de imagen y registra el cambio. Prueba según VALIDATION.md y fusiona
la revisión en Forgejo. Comprueba el recibo público, el consumidor de tienda y
las imágenes. La tienda mantiene la versión anterior hasta verificar las imágenes
amd64/arm64 anónimamente y añadir `image:` en main. No reemplaza una etiqueta
GHCR existente ni instala actualizaciones en equipos de usuarios.

La programación de cada consumidor es horaria; también admite ejecución manual.
El flujo de imágenes se llama explícitamente porque un push con GITHUB_TOKEN no
activa otros workflows por push. Su plan recupera imágenes pendientes aunque el
paquete no haya cambiado en esta ejecución.

## Manual y YunoHost

El publicador llama al workflow Pages después de publicar. El manual conserva
https://gente-del-condado.github.io/HA-Private-Git-Manager/.
YunoHost se instala desde la raíz de una etiqueta Git; coordina manifest.toml,
versión y changelog. Las notas nativas permanecen en doc/. Consulta YUNOHOST.md.

No se escribe de regreso en Forgejo. No se mueve ninguna etiqueta publicada.
