#!/bin/bash

install_private_git() {
    # Application source is bundled in this package.
    ynh_safe_rm "$install_dir/app"
    cp -a ../private_git_manager/app "$install_dir/app"
    install -m 0644 ../private_git_manager/requirements.txt "$install_dir/requirements.txt"

    python3 -m venv --clear "$install_dir/venv"
    "$install_dir/venv/bin/python" -m pip install --disable-pip-version-check --no-input --no-cache-dir \
        --only-binary=:all: -r "$install_dir/requirements.txt"
    "$install_dir/venv/bin/python" -m pip check

    chown -R root:"$app" "$install_dir"
    chmod 0750 "$install_dir"

    ynh_config_add_systemd
    ynh_config_add_nginx
    yunohost service add "$app" --description="Private Git Manager"
    ynh_systemctl --service="$app" --action=start --wait_until="Application startup complete" --log_path=systemd
}
