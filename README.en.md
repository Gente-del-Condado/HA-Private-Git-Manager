# Private Git Manager

Connect private Git repositories and manage native applications on Home Assistant OS or YunoHost. Sync over SSH or HTTPS, read private Markdown and catalogs, and review the selected commit before applying changes.

- [Illustrated manual in Spanish](https://gente-del-condado.github.io/HA-Private-Git-Manager/)
- [Home Assistant documentation](private_git_manager/DOCS.md#english-quick-start)
- [YunoHost admin guide](doc/ADMIN.md) · [Full guide in Spanish](YUNOHOST.md)

## Source and distribution

Development starts in [Forgejo](https://gentedelcondado.es/forgejo/wolfbelmi88/HA-Private-Git-Manager).
Its public [GitHub mirror](https://github.com/Gente-del-Condado/HA-Private-Git-Manager)
runs Actions which publish the application to Mis_app_ha and the Forgejo Backup
integration to Mis_componente_ha. These are separate products: the application
manages repositories and installations; the integration saves encrypted Home
Assistant backups. Distribution workflows never write back to Forgejo. Users
can still choose Forgejo or GitHub as their private backup destination.

## Get started

1. On Home Assistant OS, add [Mis_app_ha](https://github.com/Gente-del-Condado/Mis_app_ha) to the app store, install and start **HA Private Git Manager**, then open its web interface. The app requires Supervisor and supports amd64 and aarch64. For YunoHost, install a tagged package using the [YunoHost guide](YUNOHOST.md).
2. Generate an SSH identity and register only the public key as a read-only deploy key. Add the repository URL, branch or tag, and select the key. A custom-port URL looks like `ssh://forgejo@git.example.org:2233/team/apps.git`.
3. Compare the SSH host fingerprint with a trusted source, then sync. HTTPS repositories may use a separate read-only token.
4. Review the native package, version and commit. Home Assistant offers configuration, logs, Ingress and backups. YunoHost uses your native admin session to install, upgrade and remove app instances.

Use the platform guides for backup and recovery procedures. See [CONTRIBUTING.md](CONTRIBUTING.md) for the source layout, [VALIDATION.md](VALIDATION.md) for test coverage and [PUBLISHING.md](PUBLISHING.md) for deployment.
