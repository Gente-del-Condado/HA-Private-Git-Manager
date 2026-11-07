# HA Private Git Manager 0.13.0

[Upload to Forgejo (Spanish)](FORGEJO.md)

A native Home Assistant OS app for private Git repositories and local apps, with Spanish and English UI, light/dark themes and an Ingress-only administration panel.

**Using YunoHost?** See the [installation guide and feature scope](YUNOHOST.md).

## Install

Copy the complete `private_git_manager` directory to `/addons/private_git_manager` on Home Assistant. Run `ha addons reload`, then install it from **Settings → Apps → Store → Local apps**. Start it and open its web UI. Initial image construction needs Internet access.

The app requests the Supervisor `manager` role and write access to local apps. It does not publish a host port, mount Home Assistant configuration or require disabling protection mode. Supported manifest architectures are aarch64 and amd64; see [validation status](VALIDATION.md) for what was actually executed.

## Connect

1. Generate an Ed25519 SSH key in **SSH keys**.
2. Register the public key as a **read-only deploy key** in GitHub, Forgejo or Gitea.
3. Add a repository using `ssh://user@server:port/owner/repo.git` or `git@github.com:owner/repo.git`, select a branch/tag and the key.
4. Fetch the host fingerprint, verify it using a trusted channel and paste the verified SHA256 fingerprint. Fetching a key does not establish its authenticity.
5. Save and sync. Choose a detected app and confirm the exact version/commit to install.
6. Use **Configure** to edit options and **App logs** to check startup. Start the app from the manager when ready. Initial installations are left stopped.

For HTTPS, enter a clean repository URL and an optional read-only token plus the username your provider requires. Public repositories do not need a token. Never put credentials in URLs. An empty token in the credentials form removes the stored token.

## Private single-app repositories and master catalogs

Both formats are supported. A single-app repository may keep its manifest and README in the root or an app subdirectory. A master repository can contain root `README.md` and `repository.yaml`, with one subdirectory per app. Every app still needs its own valid Home Assistant manifest.

Cards display repository type, catalog name, maintainer, summary and app count. Search also covers catalog/app identity. **View catalog** opens the root README and app presentations; **View README** opens an app presentation, and **Documentation** displays its `DOCS.md` when available.

Relative Markdown links stay inside the private reader. Local PNG/JPEG/GIF/WebP images use authenticated Ingress routes. Raw HTML is escaped, external images and SVG are not automatically loaded, and `.git`, keys, symlinks and paths outside the checkout are blocked. Documents are limited to 256 KiB and images to 8 MiB. Optional metadata can also use `repository.yml` or `repository.json`.

Previously downloaded repositories gain presentation metadata after upgrading. Sync again after changing README files in the remote repository.

## Existing local folders (0.2.1)

The manager itself lives in `/addons/private_git_manager`; each managed app uses `/addons/<slug>`. These are local app source folders, separate from official app container storage.

Click **Install** to inspect the destination. Empty folders can be reused. An existing app with the same slug can be adopted after reviewing its path/version and explicitly checking the consent box. **Adopt and apply** keeps the previous source during deployment. Different app slugs, ambiguous packages and symbolic links are refused. A changed folder requires a new review.

An already-installed local app is updated/rebuilt instead of installed twice; an identical installed version can be registered without rebuilding. Failed adoption restores source, and uncertain Supervisor results retain both trees for explicit recovery. This is not a backup of app images or data.

For a local installation, stop the manager, replace its program directory with the 0.13.0 package while preserving persistent data, reload apps and update/start `local_private_git_manager`. Store installations can use the update available after refreshing their repository.

## Updates and jobs

Sync downloads a new checkout without changing installed apps. Edit a repository to change its branch/tag or set a sync interval from 5 minutes to 7 days (`0` means manual). Scheduled sync never installs code automatically.

Installation and rebuilding run in a persistent background queue. Closing the UI does not cancel a job. Updates preserve the app's prior running/stopped state, and the manager checks the installed version before confirming success. Start, stop and restart are available for managed apps.

To rotate a key, create a new one, register its public part, update repository credentials, test sync, then revoke/delete the old key. In-use keys cannot be removed.

## Recovery

A lost Supervisor connection does not prove an operation failed. Both source trees and a transaction journal are preserved, and further deployments are blocked until recovery is reviewed.

Check Supervisor logs and ensure the build/update is no longer active. Select **Review recovery**, then restore previous source or accept the verified current version. Acceptance checks both installed version and source-tree digest. Restoring source does not roll back images or app data; rebuild or restart through Home Assistant as needed.

Hidden `.pgm-stage-*` and `.pgm-backup-*` folders under `/addons` may hold recovery data. Do not remove them during recovery. The journal is in `/config/private-git-manager/state.json`.

Manage the full lifecycle here: **Install** installs through Supervisor; **Uninstall** removes the installed app while keeping its source for reinstallation. **Delete app** removes the reviewed `/addons/<slug>` folder and record; when installed, its dialog offers **Uninstall and delete** with explicit consent. Other apps and the downloaded/remote Git repository are kept.

Uninstallation deletes the app’s internal data and options. The public `app_config` folder is kept by default; deleting it requires checking the separate option. The dialog explains the data loss before confirmation.

The optional **Also hide this app** checkbox keeps it out of this manager catalog across syncs and restarts. Use **Hidden apps → Show again** to restore its listing without installing it. Leave the checkbox unchecked to keep it available. **Release** only removes the manager record and keeps local files.

Deletion is a background job with a persistent journal. After a failure, **Review recovery → Finish deletion** retries cleanup of its `.pgm-remove-*` folder. Never delete these folders during pending operations. The manager verifies uninstallation before deleting source. Uncertain results preserve the source and journal. Recovery checks state without repeating an uninstall; an explicit additional authorization is required to retry it after checking that no operation is running. Restart never replays these operations. Repositories with managed apps cannot be deleted.

## App configuration and logs

**Configure** opens a form generated from the installed app’s native Supervisor `schema` and `translations`. It reuses field names, descriptions, types, limits and choices, including device selectors. Labels fall back to English when the selected language is unavailable. No additional app configuration format is needed.

The default form supports text, masked passwords with a visibility toggle, booleans, integers/floats, selects, optional fields, nested groups and editable lists of values or objects. Optional fields distinguish omission from `false`. Native startup, watchdog, update, network, Ingress and audio settings are also shown when available.

**Advanced YAML** remains available. Switching views preserves edits and unrepresented values; invalid YAML stays in the advanced editor. Existing `!secret name` references are preserved, including numeric/select fields. Unknown representations are retained with an explicit advanced-editor hint.

**Validate configuration** checks preliminarily. Saving validates through Supervisor and refuses stale edits if another window changed settings. Options apply at the next start; optionally restart a running app after saving. Stopped apps stay stopped. Failed saves keep the editor open, and closing unsaved edits requires explicit discard.

Option values are never stored in manager state, jobs, event history or browser local storage. Submitted representations are limited to 24,000 characters and HTTP requests to 32 KiB.

**App logs** provides recent plain-text output, search, automatic five-second refresh, pause, manual refresh and `.log` download. Reads are capped at 512 KiB. Refresh pauses while the page is hidden and stops on close. Known sensitive option values and manager tokens are redacted; arbitrary secrets printed by an app cannot all be detected. Logs stay in memory and remain readable during pending recovery.

## Open an app through Ingress

Installed apps declaring `ingress: true` offer **Open web interface**. Start the app first; the button is disabled while stopped or during pending operations. The manager rechecks Supervisor before opening Home Assistant’s app panel outside the manager iframe.

Home Assistant handles authentication and session renewal with the current user. No direct ports or external `webui` URLs are opened, and the manager does not return or store Ingress session tokens. Apps do not need to be pinned to the sidebar.

The destination is `/app/<slug>` on Core 2026.2 or later, or `/hassio/ingress/<slug>` on older versions, selected from Supervisor’s Core version. Use Home Assistant navigation or Back to return.

## Keeping manager data on reinstall

On first start, version 0.12.0 or later copies existing keys, repositories and state from `/data` to `/config/private-git-manager` in the app's dedicated configuration folder. Update in place before uninstalling an older version. To keep this folder, leave the removal option unchecked and reinstall the same app. Keep access to the folder restricted because it contains credentials.

If the store shows an update but clicking it fails to start the operation, check the installed app with `ha apps info APP_ID` and run `ha apps update APP_ID --backup` from the Home Assistant terminal. Older CLI versions use `ha addons`. Supervisor logs show any update errors.

## Per-app backups

**Backups** lists native Home Assistant backups containing the exact app slug, including general backups and backups created outside the manager. It shows name, date, size, location and password protection.

**Create backup** saves the installed app’s data and configuration to Home Assistant local backup storage. Name and encryption password are optional; passwords must be repeated to avoid typos. Without a password the backup is unencrypted. Supervisor may temporarily stop apps requiring cold backups. These native backups are also listed in Home Assistant.

**Restore backup** shows the saved app version and requires explicit consent to replace current data, with initial focus on **Cancel**. Encrypted backups require their password. Only the chosen app is restored, even from a full backup containing Core, folders and other apps. Uninstalled apps can be restored while still linked to the manager with their local source retained; creating a backup requires an installed app.

Restoring can stop/restart the app and change its installed version, shown on its card. Local Git source and commit are retained: review the version before updating or rebuilding again. Shared folders, Core and other apps are never included or restored by these controls. Existing backups on network storage restore from their location. Home Assistant Link (`.cloud_backup`) is exclusive to Core and unavailable here.

Both operations use background jobs with translated progress and history and continue after closing the manager. Passwords are kept only in memory during the operation, never in state, jobs, logs or browser storage; retain them securely because the manager cannot recover them. A lost Supervisor connection produces an uncertain outcome with no automatic retry. Refresh backups and check the app before repeating. Interrupted jobs are never replayed on restart.

These native data backups are separate from temporary `.pgm-backup-*` source trees used for deployment recovery.

### Backup before updating, import and schedules

The update review shows the installed and proposed versions plus the repository changelog when available. **Back up and update** creates a local unencrypted backup first. The update stops if the backup cannot be confirmed. **Changes from the last sync** groups added, changed and removed apps, including source changes with the same version.

Use **Backups → Import backup** to upload a native .tar archive up to 512 MiB. The manager checks that the archive contains the selected app and imports it into Supervisor. The restore review then shows its version and asks for the usual confirmation.

In **Schedule backups**, choose a 1–720 hour interval and keep 1–30 backups. Enter 0 hours to disable the schedule. The first backup becomes due after the interval. The next due time and last successful backup appear in the form. Scheduled copies are stored locally without encryption. After a successful backup, retention removes only local copies created by that schedule.

### Download and delete backups

Each backup offers **Download backup** and **Delete backup**, with a review of its name, date, size, encryption and whether it contains other data. **Both actions affect the whole archive**, including Core, folders or other apps in a general backup. Restore remains limited to the chosen app.

**Download backup** streams the original `.tar` archive from the displayed location, preserving encryption and requiring no password. No second archive is stored in the manager. Your browser handles progress and destination. Interrupted downloads must restart from the beginning; partial downloads and resuming are not offered. The manager records download start, without claiming completion in your browser.

**Delete backup** shows all accessible locations to remove, requires a consent checkbox and initially focuses **Cancel**. It deletes the whole archive from those locations, keeping installed apps and their current data. Downloaded copies and Home Assistant Link are excluded. Deletion cannot be undone. If reviewed metadata or locations change before execution, refresh and review again.

Deletion runs in the background and verifies the result. Unconfirmed or partial deletion is reported with no automatic retry. Downloading and deleting remain available for uninstalled apps that retain their manager link and local source.

## Logs and privacy

The UI provides filtering, search and JSONL export. It retains 500 events and up to 100 completed jobs. Container logs are Spanish JSONL; `/config/private-git-manager/manager.log` rotates at 1 MiB with three older copies.

Private data lives under `/data`: keys, repository checkouts, tokens, job records and transaction state. Directories use `0700`; state, private keys and logs use `0600`. Tokens are redacted from API responses and logs and passed to Git through `GIT_ASKPASS`. Secrets have filesystem protection, not additional encryption. Protect app backups: they contain credentials.

Ingress requests are accepted only from `172.30.32.2`; forwarded headers cannot bypass this. The administration panel is admin-only. Mutations require a custom CSRF header. No private-key export is available.

## Packages and limits

Repositories need valid Home Assistant `config.yaml`, `config.yml` or `config.json` app manifests plus a Dockerfile or prebuilt image. Root manifests and subdirectories up to five levels are supported. The manifest's containing directory becomes the build context.

Symlinks, special files, nested apps and local slug collisions are rejected. Git submodules and LFS objects are not materialized. Deployment packages are limited to 512 MiB with a free-space check; Git downloads have a timeout but no strict disk quota. Commit signatures are not verified.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
PGM_DEV=1 .venv/bin/uvicorn app.main:app --app-dir private_git_manager --host 127.0.0.1 --port 8099 --no-proxy-headers --no-access-log
.venv/bin/python -m pytest -q
```

Development mode supports keys, Git and discovery, without pretending Supervisor installations work. Run one process/worker per data directory. See the [Spanish manual](README.md) for build, container smoke testing, packaging and upgrading from 0.1.0.
