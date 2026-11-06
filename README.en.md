# HA Private Git Manager 0.8.0

[Upload to Forgejo (Spanish)](FORGEJO.md)

A native Home Assistant OS app for private Git repositories and local apps, with Spanish and English UI, light/dark themes and an Ingress-only administration panel.

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

For a local installation, stop the manager, replace its program directory with the 0.8.0 package while preserving persistent data, reload apps and rebuild/start `local_private_git_manager`. Store installations can use the update available after refreshing their repository.

## Updates and jobs

Sync downloads a new checkout without changing installed apps. Edit a repository to change its branch/tag or set a sync interval from 5 minutes to 7 days (`0` means manual). Scheduled sync never installs code automatically.

Installation and rebuilding run in a persistent background queue. Closing the UI does not cancel a job. Updates preserve the app's prior running/stopped state, and the manager checks the installed version before confirming success. Start, stop and restart are available for managed apps.

To rotate a key, create a new one, register its public part, update repository credentials, test sync, then revoke/delete the old key. In-use keys cannot be removed.

## Recovery

A lost Supervisor connection does not prove an operation failed. Both source trees and a transaction journal are preserved, and further deployments are blocked until recovery is reviewed.

Check Supervisor logs and ensure the build/update is no longer active. Select **Review recovery**, then restore previous source or accept the verified current version. Acceptance checks both installed version and source-tree digest. Restoring source does not roll back images or app data; rebuild or restart through Home Assistant as needed.

Hidden `.pgm-stage-*` and `.pgm-backup-*` folders under `/addons` may hold recovery data. Do not remove them during recovery. The journal is in `/data/state.json`.

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

## Logs and privacy

The UI provides filtering, search and JSONL export. It retains 500 events and up to 100 completed jobs. Container logs are Spanish JSONL; `/data/manager.log` rotates at 1 MiB with three older copies.

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
