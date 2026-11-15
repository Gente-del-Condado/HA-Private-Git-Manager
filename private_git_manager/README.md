# HA Private Git Manager

![Private Git Manager](logo.png)

Gestiona repositorios Git privados y aplicaciones locales desde Home Assistant mediante Ingress.

[![Añadir mi tienda a Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FGente-del-Condado%2FMis_app_ha)

Instala esta app desde [Mis_app_ha](https://github.com/Gente-del-Condado/Mis_app_ha),
el repositorio oficial de aplicaciones de Gente del Condado. Añade la tienda con
el botón anterior y selecciona **HA Private Git Manager**.

Esta carpeta distribuye la aplicación para Home Assistant OS, no el paquete
YunoHost ni la integración Forgejo Backup. El desarrollo se mantiene en
[Forgejo](https://gentedelcondado.es/forgejo/wolfbelmi88/HA-Private-Git-Manager),
se replica en [GitHub](https://github.com/Gente-del-Condado/HA-Private-Git-Manager)
y Actions publica esta carpeta en Mis_app_ha. La integración de copias se
publica por separado en Mis_componente_ha. No edites las copias generadas.

- Interfaz en español e inglés, temas claro/oscuro y diseño adaptable.
- Presentaciones README/DOCS, iconos y catálogos maestros privados con `repository.yaml`.
- Claves SSH Ed25519, identidades de servidor verificadas y HTTPS con token.
- Instalación, desinstalación y actualización desde el gestor, control de ejecución y sincronización programada.
- Borrado individual de copias locales y ocultación reversible de aplicaciones del catálogo maestro.
- Formulario generado desde el esquema nativo de Home Assistant, traducciones de cada aplicación y YAML avanzado opcional.
- Copias nativas por aplicación: crear, cifrar, restaurar, descargar y borrar con confirmación desde el gestor.
- Logs de cada aplicación con búsqueda, refresco automático y descarga.
- Botón para abrir las aplicaciones mediante Ingress y la sesión de Home Assistant.
- Trabajos en segundo plano, recuperación explícita y registros filtrables/exportables.

Abre la pestaña **Documentación** o el [manual web ilustrado](https://gente-del-condado.github.io/HA-Private-Git-Manager/#home-assistant) para comenzar. Compatible con aarch64 y amd64. Requiere Supervisor.

Spanish/English UI, SSH keys, private Git repositories and local apps, with background jobs, recovery and logs. See **Documentation** for setup and recovery instructions.
