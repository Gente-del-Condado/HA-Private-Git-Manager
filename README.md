# Private Git Manager

![Icono de Private Git Manager](icon.png)

Gestiona repositorios Git privados y aplicaciones nativas de **Home Assistant OS** o **YunoHost**. El gestor sincroniza por SSH o HTTPS, muestra README y catálogos privados, y permite revisar el commit antes de aplicar cambios.

- [Manual web ilustrado](https://gente-del-condado.github.io/HA-Private-Git-Manager/) · [fuente del manual](docs/index.html)
- [Documentación de Home Assistant](private_git_manager/DOCS.md) · [Documentación de YunoHost](YUNOHOST.md)
- [Conectar Forgejo](FORGEJO.md) · [Copias completas en Forgejo](FORGEJO_BACKUPS.md)

## Origen y distribución

El código completo se mantiene primero en
[Forgejo](https://gentedelcondado.es/forgejo/wolfbelmi88/HA-Private-Git-Manager)
y se replica a [GitHub](https://github.com/Gente-del-Condado/HA-Private-Git-Manager).
GitHub Actions publica private_git_manager/ en Mis_app_ha y
custom_components/pgm_forgejo_backup/ en Mis_componente_ha, conservando las demás
aplicaciones. No devuelve esas distribuciones a Forgejo. El manual se publica
con el flujo **Publicar el manual en GitHub Pages** de este proyecto; consulta [PUBLISHING.md](PUBLISHING.md).

Esta cadena distribuye el software. Las instalaciones del gestor siguen
utilizando sus propias credenciales para sincronizar repositorios y guardar
copias cifradas en los destinos Forgejo o GitHub elegidos por cada usuario.

## Instalar

**Home Assistant OS.** Añade [Mis_app_ha](https://github.com/Gente-del-Condado/Mis_app_ha) a la tienda de aplicaciones. Instala e inicia **HA Private Git Manager** y abre su interfaz web. Requiere Supervisor y admite `amd64` y `aarch64`.

**YunoHost.** Instala una etiqueta publicada mediante `yunohost app install`. Para operar sobre paquetes desde el gestor, inicia sesión en la administración de YunoHost en el mismo dominio. Los comandos y requisitos están en la [guía de YunoHost](YUNOHOST.md).

## Primer repositorio

1. Crea una clave SSH Ed25519 en el gestor y añade su parte pública a Forgejo como clave de despliegue de solo lectura.
2. Añade la URL, la rama o etiqueta y la clave. Para un puerto SSH personalizado usa `ssh://forgejo@git.example.org:2233/equipo/apps.git`.
3. Verifica la huella del servidor por un canal de confianza y sincroniza.
4. Revisa el paquete, la versión y el commit antes de instalar. Cada plataforma instala sus propios paquetes nativos.

Home Assistant ofrece configuración, logs, Ingress y copias nativas por aplicación. En YunoHost las operaciones de instalación, actualización y desinstalación usan la sesión nativa de administración.

## Componentes y copias completas

En Home Assistant OS, añade **Mis_componente_ha** por SSH dentro del gestor y sincroniza la rama `main`. En **Componentes** puedes instalar o actualizar integraciones de Core y revisar el commit. Reinicia Core después de aplicar un cambio. El catálogo público está en [Mis_componente_ha de GitHub](https://github.com/Gente-del-Condado/Mis_componente_ha).

**Forgejo Backup** añade destinos privados de Forgejo y GitHub para las copias cifradas de Home Assistant. El repositorio de copias usa una clave propia con escritura. El README automático enlaza las últimas copias y sus descargas. Consulta la [guía de instalación y recuperación](FORGEJO_BACKUPS.md).

## Mantener el proyecto

- [CONTRIBUTING.md](CONTRIBUTING.md) describe la arquitectura, los datos y el entorno de desarrollo.
- [AGENTS.md](AGENTS.md) resume los contratos que deben respetar las herramientas de código y los agentes.
- [VALIDATION.md](VALIDATION.md) explica las comprobaciones automáticas y las que necesitan equipos reales.
- [PUBLISHING.md](PUBLISHING.md) explica GitHub Pages, Mis_app_ha y el paquete YunoHost.
- [CHANGELOG.md](private_git_manager/CHANGELOG.md) recoge los cambios por versión.
