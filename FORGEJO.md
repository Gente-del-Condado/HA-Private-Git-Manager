# Conectar Forgejo con Private Git Manager

Usa la URL **SSH** del botón **Clonar** del repositorio. Si el servidor usa un puerto personalizado, conserva el usuario, puerto y ruta indicados por Forgejo.

```text
ssh://forgejo@git.example.org:2233/equipo/catalogo.git
```

El catálogo público [Mis_componente_ha](https://github.com/Gente-del-Condado/Mis_componente_ha)
se distribuye exclusivamente en GitHub. Para él utiliza su URL de clonación de
GitHub y sus permisos correspondientes; el ejemplo anterior representa un
catálogo privado propio de Forgejo, no una segunda copia de esa tienda.

## Conectar un catálogo

1. Abre **Claves SSH** en Private Git Manager y crea una clave Ed25519.
2. Copia su parte pública y añádela en **Ajustes → Claves de despliegue** del repositorio de Forgejo. Para que el gestor descargue el catálogo basta con permiso de lectura.
3. En el gestor, añade el repositorio, elige la clave y selecciona la rama `main` o la referencia que quieras seguir.
4. Verifica la huella del servidor SSH con su administrador por un canal de confianza. Registra la huella en el gestor y pulsa **Sincronizar**.
5. Usa **Componentes** para las integraciones de Home Assistant Core. Para las aplicaciones, abre la ficha del repositorio. Revisa el commit antes de instalar.

Si el servidor rechaza la clave, comprueba que la parte pública está registrada en el repositorio correcto y que seleccionaste la clave correspondiente en el gestor. Si cambia la huella, confirma primero la rotación con el administrador.

## Distinguir los repositorios y las claves

- **Mis_app_ha** distribuye las aplicaciones de la tienda de Home Assistant.
- **Mis_componente_ha** distribuye las integraciones que instalas desde el gestor. Tu instancia usa una clave de lectura.
- **Repositorio de copias** es el destino privado de Forgejo Backup. La integración genera una clave propia y necesita escritura para subir y aplicar la retención.
- **Repositorio de código fuente** es donde se desarrolla el proyecto. GitHub Actions publica en los catálogos con claves de despliegue de escritura específicas de cada destino.

Para configurar el destino de copias, sigue la [guía de Forgejo Backup](FORGEJO_BACKUPS.md). Para publicar o mantener el código y los catálogos, consulta [Publicación](PUBLISHING.md).
