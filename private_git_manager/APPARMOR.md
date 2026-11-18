# AppArmor de Private Git Manager

`apparmor.txt` protege el proceso Python y sus hijos Git, OpenSSH y age en modo
**enforce**. Se distribuye también en el archivo de instalación local. Mantiene
el rol `manager`: reducirlo rompería la gestión de aplicaciones y copias nativas.
No requiere desactivar la protección ni acceder al socket Docker.

## Límites y permisos necesarios

- El código de `/app` y las bibliotecas se leen, pero no se modifican.
- El estado, las claves y los checkouts están en `/config/private-git-manager`;
  se conserva `/data` para migrar instalaciones anteriores y las carpetas de
  preparación `.pgm-migrate-*` para realizar el intercambio sin perder datos.
- Git necesita enlaces duros para sus objetos y acceso a objetos de solo
  lectura. `dac_override` conserva ese comportamiento dentro de las rutas
  permitidas; no elimina las restricciones de archivos de AppArmor.
- El shell es necesario para `GIT_SSH_COMMAND`. El ayudante generado
  `/config/private-git-manager/askpass.sh` conserva permiso de ejecución para
  HTTPS con token. Las copias Git no reciben ese permiso y sus hooks siguen desactivados.
- `/addons` permite preparar aplicaciones locales. En Core solo se permite
  escribir dentro de `/homeassistant/custom_components`, incluidas las carpetas
  de intercambio y recuperación del gestor. `.storage` y los secretos de Core
  no están autorizados.
- Se conservan DNS, Git SSH/HTTPS, Supervisor y transferencias cifradas.

AppArmor no sustituye la verificación de huella SSH, TLS, revisión del commit,
CSRF, confirmaciones ni recuperación de operaciones inciertas.

## Laboratorio desechable

Instala `private_git_manager_apparmor_lab` con configuración y datos separados.
No montes la configuración real de Core: crea una carpeta ficticia dentro de la
imagen, con `custom_components/.apparmor-lab` igual a `isolated-core-fixture`.
La marca `/data/.apparmor-lab` debe contener `disposable-lab`. Usa repositorios,
claves y aplicaciones de prueba, sin credenciales de producción.

`python scripts/check_apparmor.py --confirm-disposable-lab`, ejecutado con Python dentro
del proceso protegido, prueba Git, claves Ed25519, age, el ayudante HTTPS,
DNS/TLS y denegaciones. El programa rechaza una instalación ajena al laboratorio.
La aceptación desde Ingress añade sincronización SSH/HTTPS, revisión y despliegue,
actualización y recuperación de una integración ficticia, y una copia/restauración
nativa cifrada de una aplicación desechable. No restaura Core ni otras apps.

Repite en amd64 y aarch64 y revisa `_TRANSPORT=audit` en el diario. Distingue las
denegaciones deliberadas de las operaciones legítimas. Comprueba después del
reinicio que se conservan estado y claves. Los resultados se registran en
`VALIDATION.md`; una compilación cruzada no equivale a ejecutarlo en esa arquitectura.

La configuración actual puede mostrar 7/8 instalada: el perfil suma un punto,
pero el rol manager sigue siendo necesario. [Cálculo oficial de la puntuación](https://contributors.home-assistant.io/apps/reference/security-rating/).

## ABI de la política

Se declara `abi <abi/3.0>,` explícitamente. En HAOS 18.4 con parser 3.1.7, omitirlo puede dejar sin mediar las reglas de red aunque el perfil figure en enforce. Las pruebas incluyen permisos efectivos, no solo la puntuación. No retires esa declaración ni desactives la protección para evitar una denegación.

## Ejecutar el ayudante desde el clon

Sustituye `haos-lab` por el acceso SSH de tu laboratorio y prepara primero la
instalación desechable descrita arriba. El código se envía por stdin a Python;
no necesita permiso de ejecución sobre archivos del contenedor:

```sh
ssh root@haos-lab \
  'docker exec -i app_local_private_git_manager_apparmor_lab python - --confirm-disposable-lab' \
  < scripts/check_apparmor.py
```
