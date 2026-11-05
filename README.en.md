# HA Private Git Manager 0.2.0

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
6. Configure app options in Home Assistant, then start the app. Initial installations are left stopped.

For HTTPS, enter a clean repository URL and an optional read-only token plus the username your provider requires. Public repositories do not need a token. Never put credentials in URLs. An empty token in the credentials form removes the stored token.

## Updates and jobs

Sync downloads a new checkout without changing installed apps. Edit a repository to change its branch/tag or set a sync interval from 5 minutes to 7 days (`0` means manual). Scheduled sync never installs code automatically.

Installation and rebuilding run in a persistent background queue. Closing the UI does not cancel a job. Updates preserve the app's prior running/stopped state, and the manager checks the installed version before confirming success. Start, stop and restart are available for managed apps.

To rotate a key, create a new one, register its public part, update repository credentials, test sync, then revoke/delete the old key. In-use keys cannot be removed.

## Recovery

A lost Supervisor connection does not prove an operation failed. Both source trees and a transaction journal are preserved, and further deployments are blocked until recovery is reviewed.

Check Supervisor logs and ensure the build/update is no longer active. Select **Review recovery**, then restore previous source or accept the verified current version. Acceptance checks both installed version and source-tree digest. Restoring source does not roll back images or app data; rebuild or restart through Home Assistant as needed.

Hidden `.pgm-stage-*` and `.pgm-backup-*` folders under `/addons` may hold recovery data. Do not remove them during recovery. The journal is in `/data/state.json`.

Uninstall apps through Home Assistant. **Release** then removes the manager record while keeping the local source folder. Repositories with managed apps cannot be deleted.

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
