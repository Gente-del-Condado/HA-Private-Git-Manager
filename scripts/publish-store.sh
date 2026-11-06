#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
STORE_ROOT=$(cd -- "${1:?Indica la carpeta del repositorio Mis-app}" && pwd)
APP=private_git_manager

test "$SOURCE_ROOT" != "$STORE_ROOT"
test -f "$STORE_ROOT/repository.yaml"
for required in config.yaml Dockerfile requirements.txt; do
  test -s "$SOURCE_ROOT/$APP/$required"
done
test -d "$SOURCE_ROOT/$APP/app"
if [ -n "$(find "$SOURCE_ROOT/$APP" -type l -print -quit)" ]; then
  echo 'No se publican aplicaciones con enlaces simbólicos.' >&2
  exit 1
fi
if [ -L "$STORE_ROOT/$APP" ]; then
  echo 'La carpeta de destino no puede ser un enlace simbólico.' >&2
  exit 1
fi

# --delete se limita a esta app; las demás apps y repository.yaml se conservan.
rsync -a --delete -- "$SOURCE_ROOT/$APP/" "$STORE_ROOT/$APP/"
