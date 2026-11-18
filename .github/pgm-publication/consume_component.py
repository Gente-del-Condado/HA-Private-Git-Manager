#!/usr/bin/env python3
"""El catálogo público consume PGM sin credenciales entre repositorios."""
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

SOURCE = 'Gente-del-Condado/HA-Private-Git-Manager'
TARGET = 'Gente-del-Condado/Mis_componente_ha'
COMPONENT = 'custom_components/pgm_forgejo_backup'


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
        raise ValueError('Inventario del componente incompleto')
    for name, data in files.items():
        if (hashlib.sha256(data).hexdigest() != expected[name]['sha256']
                or expected[name]['mode'] not in (0o644, 0o755)):
            raise ValueError('Componente alterado')
    manifest = json.loads(files[COMPONENT + '/manifest.json'])
    if manifest.get('domain') != 'pgm_forgejo_backup' or not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        raise ValueError('Manifiesto no autorizado')
    return record, files, manifest['version']


def main():
    if os.environ.get('GITHUB_REPOSITORY') != TARGET or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Solo escribe el catálogo público autorizado')
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
        git('fetch', 'origin', 'main')
        git('checkout', '-B', 'pgm-component', 'origin/main')
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Destino enlazado')
        old = target / 'manifest.json'
        if old.exists() and tuple(map(int, json.loads(old.read_text())['version'].split('.'))) > tuple(map(int, version.split('.'))):
            raise ValueError('No se retrocede el componente')
        if target.exists():
            shutil.rmtree(target)
        for name, data in files.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(record['main_files'][name]['mode'])
        receipt = Path('.publication/pgm_forgejo_backup.json')
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps({'source_repository': SOURCE, 'public_sha': ref[0],
            'source_sha': record['source_sha'], 'version': version}, indent=2) + '\n')
        git('add', '--', COMPONENT, str(receipt))
        if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
            print('CATALOGO_PGM_YA_ACTUALIZADO')
            return
        git('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
            'commit', '-qm', 'Consumir PGM público verificado ' + record['source_sha'])
        if subprocess.run(['git', 'push', 'origin', 'HEAD:main']).returncode == 0:
            print('CATALOGO_PGM_PUBLICADO:', record['source_sha'])
            return
    raise ValueError('No se pudo publicar sin forzar el historial')


if __name__ == '__main__':
    main()
