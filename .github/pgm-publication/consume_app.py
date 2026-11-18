#!/usr/bin/env python3
"""La tienda pública consume la aplicación PGM sin credenciales entre repositorios."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import urllib.request
import yaml

SOURCE = 'Gente-del-Condado/HA-Private-Git-Manager'
TARGET = 'Gente-del-Condado/Mis_app_ha'
COMPONENT = 'private_git_manager'


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def validate(raw):
    files, seen, roots = {}, set(), set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        entries = archive.getmembers()
        if len(entries) > 10000 or sum(x.size for x in entries) > 128 * 1024 * 1024:
            raise ValueError('Archivo demasiado grande')
        for item in entries:
            path = PurePosixPath(item.name)
            if (not path.parts or path.is_absolute() or '..' in path.parts or '\\' in item.name
                    or not (item.isdir() or item.isfile()) or item.name in seen):
                raise ValueError('Ruta o enlace no autorizado')
            seen.add(item.name)
            roots.add(path.parts[0])
            name = PurePosixPath(*path.parts[1:]).as_posix()
            if item.isfile() and (name.startswith(COMPONENT + '/') or name == '.publication/pgm.json'):
                if name in files:
                    raise ValueError('Archivo duplicado')
                files[name] = archive.extractfile(item).read()
    if len(roots) != 1:
        raise ValueError('Archivo sin raíz única')
    record = json.loads(files.pop('.publication/pgm.json'))
    if not re.fullmatch(r'[0-9a-f]{40}', record['source_sha']):
        raise ValueError('Origen inválido')
    expected = {name: value for name, value in record['main_files'].items() if name.startswith(COMPONENT + '/')}
    if not files or files.keys() != expected.keys():
        raise ValueError('Inventario del aplicación incompleto')
    for name, data in files.items():
        if (hashlib.sha256(data).hexdigest() != expected[name]['sha256']
                or expected[name]['mode'] not in (0o644, 0o755)):
            raise ValueError('Aplicación alterado')
    manifest = yaml.safe_load(files[COMPONENT + '/config.yaml'])
    version = str(manifest.get('version', ''))
    if (manifest.get('slug') != COMPONENT or not re.fullmatch(r'\d+\.\d+\.\d+', version)
            or set(manifest.get('arch', [])) != {'amd64', 'aarch64'}
            or not {COMPONENT + '/Dockerfile', COMPONENT + '/requirements.txt'} <= files.keys()):
        raise ValueError('Manifiesto de aplicación no autorizado')
    return record, files, version


def main():
    if os.environ.get('GITHUB_REPOSITORY') != TARGET or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Solo escribe el repositorio de tienda autorizado')
    ref = git('ls-remote', '--heads', 'https://github.com/' + SOURCE + '.git', 'refs/heads/main').split()
    if len(ref) != 2 or not re.fullmatch(r'[0-9a-f]{40}', ref[0]):
        raise ValueError('Referencia pública inválida')
    # Lectura anónima: no se adjunta el token de escritura del catálogo.
    with urllib.request.urlopen('https://api.github.com/repos/' + SOURCE + '/tarball/' + ref[0], timeout=120) as response:
        raw = response.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError('Descarga demasiado grande')
    record, files, version = validate(raw)
    target = Path(COMPONENT)
    for attempt in range(3):
        git('fetch', 'origin', 'main', 'build-source')
        git('checkout', '-B', 'pgm-app', 'origin/build-source')
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Destino enlazado')
        old = target / 'config.yaml'
        if old.exists() and tuple(map(int, str(yaml.safe_load(old.read_text())['version']).split('.'))) > tuple(map(int, version.split('.'))):
            raise ValueError('No se retrocede el aplicación')
        if target.exists():
            shutil.rmtree(target)
        for name, data in files.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(record['main_files'][name]['mode'])
        receipt = Path('.sources/pgm-public.json')
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps({'source_repository': SOURCE, 'public_sha': ref[0],
            'source_sha': record['source_sha'], 'version': version}, indent=2) + '\n')
        git('add', '--', COMPONENT, str(receipt))
        if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
            print('TIENDA_PGM_YA_ACTUALIZADO')
            return
        git('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
            'commit', '-qm', 'Consumir PGM público verificado ' + record['source_sha'])
        if subprocess.run(['git', 'push', 'origin', 'HEAD:build-source']).returncode == 0:
            print('TIENDA_PGM_PUBLICADO:', record['source_sha'])
            return
    raise ValueError('No se pudo publicar sin forzar el historial')


if __name__ == '__main__':
    main()
