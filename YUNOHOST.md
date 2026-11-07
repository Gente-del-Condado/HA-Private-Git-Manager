# Private Git Manager en YunoHost

La edición de YunoHost permite crear claves SSH, verificar la huella del servidor, conectar repositorios privados por SSH o HTTPS, sincronizar ramas y etiquetas y consultar los README y catálogos detectados. También puedes revisar los cambios de cada sincronización y programar la descarga de cambios.

Puedes conectar las mismas URLs de Forgejo, GitHub o Gitea en YunoHost y Home Assistant. Cada instalación mantiene su propio estado y claves. Registra la clave pública que genere YunoHost en los repositorios que quieras consultar.

La revisión de catálogos comprueba los manifiestos que detecta el gestor. Instalar, ejecutar y respaldar add-ons sigue siendo una función de la edición conectada al Supervisor de Home Assistant. El paquete YunoHost instala el gestor y ofrece el portal de catálogo.

## Instalación

Requiere YunoHost 12.1.17 o posterior y arquitectura amd64 o arm64. Desde la terminal de tu servidor, ejecuta:

```sh
sudo yunohost app install https://github.com/Gente-del-Condado/HA-Private-Git-Manager/tree/v0.13.0
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
