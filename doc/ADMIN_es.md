# Administración de Private Git Manager

1. Abre el gestor por HTTPS en el mismo dominio donde tienes una sesión en la administración de YunoHost.
2. Genera una clave SSH, registra su parte pública en Forgejo con permiso de lectura y verifica la huella del servidor. Añade y sincroniza el repositorio.
3. Comprueba que el paquete tiene un `manifest.toml` de formato 2 en la raíz y los scripts de instalación, actualización y desinstalación. Abre **Instalar** y completa su formulario.
4. Para actualizar, selecciona una instancia y revisa el commit. YunoHost ejecuta los scripts con permisos de administrador y aplica su copia de seguridad habitual. La desinstalación no solicita purgar los datos.

Si la sesión caduca, vuelve a iniciar sesión en la administración nativa. Si se interrumpe una operación, consulta las aplicaciones y los registros de YunoHost antes de repetirla. Los paquetes que piden cargar un archivo requieren la interfaz nativa.

La copia de seguridad de **Private Git Manager** incluye su estado y sus credenciales. Guárdala con acceso restringido. Actualiza el propio gestor desde la administración de YunoHost usando una etiqueta nueva.

[Manual ilustrado](https://gente-del-condado.github.io/HA-Private-Git-Manager/#yunohost) · [Comandos de mantenimiento](https://github.com/Gente-del-Condado/HA-Private-Git-Manager/blob/main/YUNOHOST.md)
