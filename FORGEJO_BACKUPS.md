# Copias nativas de Home Assistant en Forgejo

**Private Git Manager · Forgejo Backup** es una integración complementaria del proyecto. Registra un destino en **Ajustes → Sistema → Copias de seguridad**. Home Assistant crea, cifra y restaura los archivos. El módulo los guarda en un repositorio Forgejo privado usando Git por SSH.

## Instalar y conectar

1. Copia la carpeta `custom_components/pgm_forgejo_backup` de este repositorio a `/config/custom_components/pgm_forgejo_backup` en Home Assistant. Reinicia Core. Usa Home Assistant 2026.11 o posterior con Git y las herramientas de OpenSSH en el entorno de Core.
2. Crea un repositorio **privado y dedicado a copias** en Forgejo. Inicialízalo con un README. Copia la URL SSH de clonación, por ejemplo `ssh://git@forgejo.example.org:2222/equipo/copias.git`.
3. En **Ajustes → Dispositivos y servicios → Añadir integración**, busca **Private Git Manager · Forgejo Backup** e introduce la URL.
4. Añade la clave pública que muestra el asistente en **Ajustes del repositorio → Claves de despliegue**, con permiso de escritura. La clave es exclusiva de este destino. Conserva las claves de lectura del gestor para los repositorios de aplicaciones.
5. Obtén por un canal de confianza una huella SHA256 del servidor SSH de Forgejo e introdúcela en el asistente. La integración fija esa clave de servidor y verifica el acceso con la identidad generada.
6. En **Ajustes → Sistema → Copias de seguridad**, configura las copias automáticas, marca Forgejo como ubicación y deja activado el cifrado para esa ubicación. Selecciona los datos que quieras incluir, como aplicaciones, base de datos y carpetas en HA OS. Guarda el **kit de emergencia** en un lugar independiente.

Home Assistant conserva la programación y la retención. Puedes mantener la ubicación local y Forgejo a la vez. La integración rechaza la subida cuando Home Assistant le entrega una copia sin cifrado. El registro Git contiene también los metadatos de inventario, como nombre, fecha y versiones. La privacidad de esos metadatos depende de los permisos del repositorio.

## Descargar y restaurar

Si Forgejo está configurado en Home Assistant, abre la copia y elige restaurarla desde esa ubicación. Introduce la clave del kit de emergencia y marca las aplicaciones y carpetas que quieras recuperar.

En la lista de copias de Home Assistant, abre la copia y elige descargarla desde la ubicación Forgejo. Selecciona la descarga cifrada si vas a conservar el archivo. En una instalación limpia, carga el `.tar` descargado y usa la clave del kit de emergencia para restaurar.

Si solo tienes acceso a Forgejo, puedes recuperar el `.tar` desde otro equipo con Git y una clave SSH autorizada. Sustituye la URL y el identificador por tus valores. Verifica primero la huella SSH por un canal de confianza.

```sh
git clone --no-tags --depth=1 ssh://git@forgejo.example.org:2222/equipo/copias.git copias-ha
cd copias-ha
git ls-remote --tags origin 'refs/tags/pgm-data-*'

id=IDENTIFICADOR_DE_LA_COPIA
git fetch --no-tags --depth=1 origin "refs/tags/pgm-meta-$id"
git show FETCH_HEAD:metadata.json
git fetch --no-tags --depth=1 origin "refs/tags/pgm-data-$id"
git archive FETCH_HEAD | tar -xf -
cat part-* > backup.tar
sha256sum backup.tar
```

Ejecuta estos pasos en una carpeta de trabajo nueva y compara el SHA-256 con el campo `sha256` de los metadatos antes de importar el archivo. La copia se restaura desde el asistente nativo de Home Assistant.

## Almacenamiento y mantenimiento

El proveedor Git y SSH está en `custom_components/pgm_forgejo_backup/providers/forgejo.py`. `backup.py` implementa el contrato nativo de Home Assistant y exige el indicador de cifrado antes de abrir el flujo. El proveedor divide el archivo cifrado en bloques de 16 MiB, conserva su SHA-256 y publica dos referencias Git por copia de forma atómica. La descarga reconstruye y verifica el archivo original. La retención elimina ambas referencias. Forgejo recupera el espacio de los objetos sin referencias según su mantenimiento Git.

El límite del módulo es de 8 GiB por copia. Los límites de Forgejo pueden ser inferiores. Reserva espacio local temporal para el archivo y los objetos Git durante la transferencia. Para cambiar de clave de servidor o de despliegue, vuelve a configurar la integración y selecciona de nuevo su ubicación de copia. Mantén acceso de recuperación al repositorio independiente del equipo de Home Assistant.

- [Interfaz BackupAgent de Home Assistant](https://contributors.home-assistant.io/core/integrations/backup/)
- [Copias de seguridad y kit de emergencia](https://www.home-assistant.io/common-tasks/general/backups/)
- [Autenticación SSH de Forgejo](https://forgejo.org/docs/latest/user/repo-mirror/#mirror-via-ssh)

La [validación en Home Assistant OS](VALIDATION.md#copia-externa-en-forgejo) cubre la restauración de una aplicación local, sus datos y las carpetas de Supervisor.
