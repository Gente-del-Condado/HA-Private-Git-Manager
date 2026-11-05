# Subir el proyecto a Forgejo

El proyecto ya es un repositorio Git local con rama `main`, commit inicial y etiqueta `v0.2.0`. No se ha creado ningun repositorio remoto ni se ha subido contenido.

## 1. Crear un repositorio vacio

En tu Forgejo crea un repositorio llamado, por ejemplo, **HA-Private-Git-Manager**. Elige su visibilidad y deja desmarcadas las opciones de inicializar con README, licencia o `.gitignore`, porque esos archivos e historial ya estan en tu copia local.

Copia la URL SSH que te muestre Forgejo. Puede tener esta forma, si ese es el nombre y propietario que elegiste:

```text
ssh://forgejo@gentedelcondado.es:2233/wolfbelmi88/HA-Private-Git-Manager.git
```

Usa la URL real de tu repositorio. No introduzcas tokens ni claves privadas en ella.

## 2. Configurar el remoto y subir

Desde la carpeta del proyecto, sustituye `URL_SSH_DE_TU_REPOSITORIO` por la URL copiada:

```sh
git remote add origin 'URL_SSH_DE_TU_REPOSITORIO'
git remote -v
git push -u origin main
git push origin v0.2.0
```

Si ya configuraste `origin` anteriormente, cambia su URL con `git remote set-url origin 'URL_SSH_DE_TU_REPOSITORIO'`.

Las credenciales SSH para publicar son las de tu PC. Las claves de despliegue creadas por la aplicacion de Home Assistant son independientes y deben seguir siendo de solo lectura.

## 3. Publicar el paquete de la version (opcional)

Genera el paquete localmente:

```sh
python3 scripts/package.py
```

En Forgejo crea una publicacion a partir de la etiqueta `v0.2.0` y adjunta estos archivos de `dist/`:

- `ha-private-git-manager-0.2.0.tar.gz`
- `ha-private-git-manager-0.2.0.tar.gz.sha256`

Los paquetes generados no se versionan en Git. Tampoco se incluyen entornos Python, caches, registros, configuracion local, claves ni datos de desarrollo. Los iconos y el logotipo de la aplicacion si forman parte del codigo fuente.

## Siguientes cambios

```sh
git status
git add -- archivos_que_has_modificado
git commit -m 'Describe el cambio'
git push
```

La autoria del commit inicial utiliza la misma identidad Git configurada localmente en tu proyecto Pivigia. Puedes revisar o cambiar la identidad de este repositorio con `git config user.name` y `git config user.email`; no se modifico la configuracion global.

El repositorio privado de Forgejo guarda el codigo. La instalacion inicial del gestor en Home Assistant sigue el procedimiento de aplicaciones locales descrito en `README.md`.
