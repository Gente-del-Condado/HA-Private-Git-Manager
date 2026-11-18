#!/usr/bin/env python3
"""Exportación revisada de PGM; el privado nunca ejecuta Actions."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

from check_mirror import inspect_archive, PUBLIC, REPOSITORY
from github_mirror import Mirror, SHA

CONTROL = Path(__file__).resolve().parent


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def allowed():
    paths = (CONTROL / 'public-files.txt').read_text().splitlines()
    if len(paths) != len(set(paths)) or not paths:
        raise ValueError('Lista pública vacía o repetida')
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or path.parts[0] in ('.git', '.github', '.publication'):
            raise ValueError('Ruta de publicación no autorizada')
    return paths


def output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(name + '=' + str(value).lower() + '\n')


def inventory(root):
    root = Path(root)
    actual = []
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('No se publican enlaces')
        if path.is_file():
            actual.append(path.relative_to(root).as_posix())
    if set(actual) - set(allowed()):
        raise ValueError('Contenido ajeno a la lista pública revisada')
    if not {'private_git_manager/config.yaml', 'manifest.toml', 'custom_components/pgm_forgejo_backup/manifest.json'} <= set(actual):
        raise ValueError('Paquete público incompleto')
    return {name: {'sha256': hashlib.sha256((root / name).read_bytes()).hexdigest(),
                   'mode': 0o755 if (root / name).stat().st_mode & 0o111 else 0o644}
            for name in sorted(actual)}


def export(archive_path, destination):
    inspect_archive(archive_path)
    destination = Path(destination)
    destination.mkdir(parents=True)
    paths = set(allowed())
    with tarfile.open(archive_path, 'r:gz') as archive:
        for entry in archive.getmembers():
            name = PurePosixPath(*PurePosixPath(entry.name).parts[1:]).as_posix()
            if entry.isfile() and name.startswith(('private_git_manager/', 'custom_components/', 'conf/', 'doc/', 'docs/', 'scripts/')) and name not in paths:
                raise ValueError('Archivo nuevo de distribución: revisar la lista pública antes de publicar')
            if not entry.isfile() or name not in paths:
                continue
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(entry).read())
            target.chmod(0o755 if entry.mode & 0o111 else 0o644)
    return inventory(destination)


def download(folder):
    folder.mkdir(parents=True)
    reader = Mirror(REPOSITORY)
    sha = reader.branch()
    archive = folder / 'main.tar.gz'
    archive.write_bytes(reader.archive(sha, limit=64 * 1024 * 1024).read())
    info = inspect_archive(archive)
    tag = 'v' + info['app_version']
    try:
        tag_sha = reader.tag(tag)
    except ValueError as error:
        if str(error) != 'Lectura del espejo rechazada (HTTP 404)':
            raise
        tag_sha = None
    if tag_sha:
        (folder / 'tag.tar.gz').write_bytes(reader.archive(tag_sha, limit=64 * 1024 * 1024).read())
    record = {'source_sha': sha, 'tag': tag, 'tag_sha': tag_sha}
    (folder / 'source.json').write_text(json.dumps(record))
    previous = Path('.publication/pgm.json')
    previous = json.loads(previous.read_text()) if previous.exists() else {}
    output('changed', any(previous.get(key) != value for key, value in record.items()))
    print('FUENTES_PGM:', sha, tag, tag_sha)


def prepare(folder, destination):
    record = json.loads((folder / 'source.json').read_text())
    record['main_files'] = export(folder / 'main.tar.gz', destination / 'main')
    if record['tag_sha']:
        record['tag_files'] = export(folder / 'tag.tar.gz', destination / 'tag')
    (destination / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')


def verify(folder):
    record = json.loads((folder / 'receipt.json').read_text())
    if not SHA.fullmatch(record['source_sha']):
        raise ValueError('SHA inválido')
    if inventory(folder / 'main') != record['main_files']:
        raise ValueError('Exportación principal alterada')
    if record['tag_sha']:
        if not SHA.fullmatch(record['tag_sha']) or inventory(folder / 'tag') != record['tag_files']:
            raise ValueError('Exportación etiquetada alterada')
    return record


def copy_files(source, root):
    for name in allowed():
        target, incoming = root / name, source / name
        if any(parent.is_symlink() for parent in (target, *target.parents)):
            raise ValueError('Destino enlazado')
        if incoming.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(incoming, target)
        elif target.exists():
            target.unlink()
    git(root, 'add', '--', *allowed())


def commit(root, message):
    if subprocess.run(['git', '-C', str(root), 'diff', '--cached', '--quiet']).returncode:
        git(root, '-c', 'user.name=github-actions[bot]',
            '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
            'commit', '-qm', message)


def publish(folder):
    record = verify(folder)
    subprocess.run(['gh', 'auth', 'setup-git'], check=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / 'public'
        subprocess.run(['git', 'clone', '--quiet', 'https://github.com/' + PUBLIC + '.git', str(root)], check=True)
        git(root, 'checkout', 'main')
        def version(path):
            value = re.search(r'^version:\s*[\"\']?(\d+)\.(\d+)\.(\d+)', path.read_text(), re.M)
            if not value:
                raise ValueError('Versión de aplicación inválida')
            return tuple(map(int, value.groups()))
        if version(folder / 'main/private_git_manager/config.yaml') < version(root / 'private_git_manager/config.yaml'):
            raise ValueError('No se retrocede la aplicación pública')
        copy_files(folder / 'main', root)
        receipt = root / '.publication/pgm.json'
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps(record, indent=2) + '\n')
        git(root, 'add', '.publication/pgm.json')
        commit(root, 'Publicar PGM desde espejo privado ' + record['source_sha'])
        main_sha = git(root, 'rev-parse', 'HEAD')
        if record['tag_sha']:
            existing = git(root, 'tag', '--list', record['tag'])
            if existing:
                # Las etiquetas históricas ya existían. Nunca se mueven ni se reescriben.
                for name in ('private_git_manager', 'custom_components/pgm_forgejo_backup', 'manifest.toml', 'scripts', 'conf', 'doc'):
                    git(root, 'checkout', record['tag'], '--', name)
                for name in record['tag_files']:
                    if name.startswith(('private_git_manager/', 'custom_components/', 'scripts/', 'conf/', 'doc/')) or name == 'manifest.toml':
                        data = subprocess.check_output(['git', '-C', str(root), 'show', record['tag'] + ':' + name])
                        if hashlib.sha256(data).hexdigest() != record['tag_files'][name]['sha256']:
                            raise ValueError('La etiqueta pública existente tiene otro contenido')
                git(root, 'reset', '--hard', main_sha)
            else:
                copy_files(folder / 'tag', root)
                receipt.write_text(json.dumps({'source_sha': record['tag_sha'], 'tag': record['tag'], 'files': record['tag_files']}, indent=2) + '\n')
                git(root, 'add', '.publication/pgm.json')
                commit(root, 'Exportar versión estable PGM ' + record['tag'])
                git(root, 'tag', record['tag'])
                git(root, 'reset', '--hard', main_sha)
        args = ['push', '--atomic', 'origin', 'HEAD:main']
        if record['tag_sha']:
            args.append('refs/tags/' + record['tag'])
        git(root, *args)
    print('PGM_PUBLICADO:', record['source_sha'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'prepare', 'check', 'publish'])
    parser.add_argument('--source', type=Path, default=Path('download'))
    parser.add_argument('--prepared', type=Path, default=Path('prepared'))
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY') != PUBLIC or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Solo publica el repositorio público autorizado')
    if args.action == 'download':
        download(args.source)
    elif args.action == 'prepare':
        prepare(args.source, args.prepared)
    elif args.action == 'check':
        record = verify(args.prepared)
        reader = Mirror(REPOSITORY)
        if reader.branch() != record['source_sha'] or (record['tag_sha'] and reader.tag(record['tag']) != record['tag_sha']):
            raise ValueError('Las referencias privadas cambiaron; repetir desde el inicio')
    else:
        publish(args.prepared)


if __name__ == '__main__':
    main()
