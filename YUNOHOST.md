# Private Git Manager en YunoHost

[Manual ilustrado](https://gente-del-condado.github.io/HA-Private-Git-Manager/#yunohost) · [Ayuda integrada en español](doc/ADMIN_es.md) · [English admin guide](doc/ADMIN.md)

La edición de YunoHost permite crear claves SSH, verificar la huella del servidor, conectar repositorios privados por SSH o HTTPS, sincronizar ramas y etiquetas y consultar los README y catálogos detectados. También puedes revisar los cambios de cada sincronización y programar la descarga de cambios.

Puedes conectar las mismas URLs de Forgejo, GitHub o Gitea en YunoHost y Home Assistant. Cada instalación mantiene su propio estado y claves. Registra la clave pública que genere YunoHost en los repositorios que quieras consultar.

Los paquetes nativos de YunoHost se pueden instalar, actualizar y desinstalar desde el gestor. Los repositorios de Home Assistant siguen disponibles como catálogo; sus complementos se administran en la edición conectada al Supervisor.

## Gestionar aplicaciones privadas de Forgejo

1. Abre el gestor por HTTPS en el mismo dominio donde accedes a la administración de YunoHost e inicia sesión como administrador en esa consola. El gestor usa esa sesión en el navegador.
2. Genera una clave SSH en el gestor y añade su clave pública a Forgejo como clave de despliegue con permiso de lectura. Conecta el repositorio, verifica la huella SSH y sincroniza la rama o etiqueta que quieras usar.
3. El gestor detecta un paquete de formato 2 con `manifest.toml` en la raíz y los scripts de instalación, actualización y desinstalación en `scripts/`. Usa un repositorio por paquete de YunoHost.
4. Elige **Instalar** para rellenar las preguntas del paquete, **Actualizar** para aplicar el commit sincronizado a una instancia existente, o **Desinstalar** para quitar la instancia que selecciones.

Revisa el commit y sus scripts antes de confirmar: YunoHost los ejecuta con permisos de administrador. Las claves de Forgejo se quedan en el gestor y YunoHost recibe una copia local del paquete. Las actualizaciones dejan activa la copia de seguridad de YunoHost y la desinstalación no solicita purgar los datos. Los registros de estas operaciones están en la administración de YunoHost. Si se interrumpe la conexión, comprueba allí el resultado antes de repetir.

Los paquetes con preguntas de carga de archivos requieren usar la administración nativa. Si la instalación del propio gestor necesita actualizarse, hazlo desde YunoHost.

## Instalación

Requiere YunoHost 12.1.17 o posterior y arquitectura amd64 o arm64. Desde la terminal de tu servidor, ejecuta:

```sh
sudo yunohost app install https://github.com/Gente-del-Condado/HA-Private-Git-Manager/tree/v0.15.1
```

Elige el dominio y la ruta. La propuesta es `/private-git`. Abre **Private Git Manager** desde el portal de YunoHost. El permiso inicial corresponde al grupo **admins**. Puedes revisar el grupo autorizado en **Usuarios → Grupos y permisos**.

## Datos y mantenimiento

La instalación usa el usuario de servicio de la aplicación y el almacenamiento de datos de YunoHost. El servidor de Private Git escucha en un socket Unix al que accede Nginx. YunoHost aplica el permiso de la aplicación a esa ruta.

Las copias de YunoHost incluyen las claves, credenciales, catálogos y actividad. Protege el archivo de copia y usa la opción de conservar datos si vas a reinstalar. Para actualizar, selecciona una etiqueta posterior del proyecto:

```sh
sudo yunohost app upgrade privategit -u https://github.com/Gente-del-Condado/HA-Private-Git-Manager/tree/ETIQUETA
```

Sustituye `ETIQUETA` por la versión nueva y usa el identificador real si instalaste más de una instancia.

La edición de Home Assistant se publica por separado en Mis-app.

## Diagnóstico rápido

- Si la sesión ha caducado, abre la administración de YunoHost en el mismo dominio por HTTPS, inicia sesión y vuelve al gestor.
- Si no aparecen las operaciones nativas, comprueba que el manifiesto de formato 2 y los scripts están en la raíz de la rama sincronizada.
- Si el portal no responde, revisa el estado de la aplicación en la administración y los registros del servicio. Desde terminal puedes usar `sudo journalctl -u privategit -n 100 --no-pager`, adaptando el identificador a tu instancia.
- Si el resultado de una operación es incierto, comprueba las aplicaciones instaladas y los registros de YunoHost antes de volver a confirmar.
