# Administer Private Git Manager

1. Open the manager over HTTPS on the domain where you are signed in to the YunoHost admin interface.
2. Generate an SSH key, register its public part in Forgejo as a read-only deploy key, and verify the host fingerprint. Connect and sync the repository.
3. Check for a format 2 `manifest.toml` at the root and scripts for installation, upgrade and removal. Select **Install** and complete the package form.
4. To upgrade, select the installed instance and review the commit. YunoHost runs the scripts with administrative privileges and applies its normal safety backup. Uninstall does not request data purging.

If your session expires, sign in again through YunoHost. If a request is interrupted, check installed applications and YunoHost logs before retrying. Packages requiring a file upload use the native admin interface.

Backups of **Private Git Manager** contain its data and credentials. Restrict access to the archives. Upgrade the manager itself through YunoHost using a new tagged package.

[Illustrated Spanish manual](https://gente-del-condado.github.io/HA-Private-Git-Manager/#yunohost) · [Maintenance commands](https://github.com/Gente-del-Condado/HA-Private-Git-Manager/blob/main/YUNOHOST.md)
