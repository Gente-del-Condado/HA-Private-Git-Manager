#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
catalog_root=$(cd -- "${1:?Indica la carpeta del repositorio Mis-component}" && pwd)
component=custom_components/pgm_forgejo_backup

test "$source_root" != "$catalog_root"
test "$(git -C "$catalog_root" rev-parse --show-toplevel)" = "$catalog_root"
git -C "$source_root" cat-file -e "HEAD:$component/manifest.json"
git -C "$source_root" cat-file -e "HEAD:$component/__init__.py"

# Extrae solo los archivos versionados. Los archivos locales y las demás integraciones quedan fuera.
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
git -C "$source_root" archive HEAD -- "$component" | tar -x -C "$stage"
if [ -n "$(find "$stage/$component" -type l -print -quit)" ]; then
  echo 'No se publican integraciones con enlaces simbólicos.' >&2
  exit 1
fi
for path in "$catalog_root/custom_components" "$catalog_root/$component"; do
  if [ -L "$path" ]; then
    echo 'El destino de la integración no puede ser un enlace simbólico.' >&2
    exit 1
  fi
done

mkdir -p -- "$catalog_root/$component"
rsync -a --delete -- "$stage/$component/" "$catalog_root/$component/"
