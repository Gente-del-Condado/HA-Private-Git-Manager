# Instrucciones para contribuir con un agente

Lee [CONTRIBUTING.md](CONTRIBUTING.md) para localizar el módulo, [VALIDATION.md](VALIDATION.md) para elegir pruebas y [PUBLISHING.md](PUBLISHING.md) antes de preparar una entrega.

- Trabaja desde el repositorio principal. La carpeta de la tienda Mis-app se publica desde `private_git_manager/`.
- Usa fixtures con datos ficticios. Protege `PGM_DATA`, credenciales, estados y registros. No uses el estado real para pruebas ni capturas.
- Preserva la revisión del commit y la recuperación de operaciones inciertas. Comprueba qué plataforma usa cada entrada antes de modificar una ruta.
- Mantén las traducciones ES/EN del portal y explica en español las decisiones de implementación que requieran contexto.
- Si cambia un flujo de usuario, revisa el manual web, la documentación nativa de la plataforma y el changelog. Indica en el resultado qué se probó y qué necesita un entorno real.
