# Validación

Ejecuta las comprobaciones de [CONTRIBUTING.md](CONTRIBUTING.md) desde la raíz. Los tests de navegador usan Chrome o Chromium y una instancia local con datos temporales.

| Área | Verificación |
| --- | --- |
| Git y SSH | URL y huella, credenciales, sincronización, integridad del commit y descubrimiento de manifiestos |
| Supervisor | Instalación, adopción, recuperación, configuración, Ingress y copias con Supervisor simulado |
| YunoHost | Guardia del socket y proxy, preparación del commit, formularios y llamadas a la API nativa simulada |
| Distribución | Paquete reproducible y sin datos de ejecución, versiones y publicación |
| Manual | Rutas de imágenes y enlaces internos, navegación por teclado, móvil y escritorio |

Para comprobar el contenedor con Podman, construye la imagen a partir de `private_git_manager/` y pasa su nombre a `bash scripts/container-smoke.sh`. El script comprueba Ingress, bloqueo de accesos externos y recursos de interfaz.

Las pruebas simuladas no sustituyen la aceptación en un equipo real. En Home Assistant OS comprueba la instalación desde Mis-app, un complemento privado, una copia y la recuperación. En YunoHost comprueba la sesión de administrador en el mismo dominio, la instalación, actualización y desinstalación de un paquete privado, y la copia del propio gestor. Usa paquetes de prueba sin datos importantes.

El historial de versiones se mantiene en el [changelog](private_git_manager/CHANGELOG.md) y en Git.
