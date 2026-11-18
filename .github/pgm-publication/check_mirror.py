#!/usr/bin/env python3
"""Diagnóstico de lectura; nunca publica ni ejecuta fuentes del espejo."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

from github_mirror import Mirror, SHA

REPOSITORY = 'HA-Private-Git-Manager-private'
PUBLIC = 'Gente-del-Condado/HA-Private-Git-Manager'


def inspect_archive(path):
    files, roots = {}, set()
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        if not members or len(members) > 10000 or sum(x.size for x in members) > 128 * 1024 * 1024:
            raise ValueError('Archivo fuera de límites')
        seen = set()
        for item in members:
            name = PurePosixPath(item.name)
            if (name.is_absolute() or '..' in name.parts or '.git' in name.parts
                    or '\\' in item.name or not name.parts
                    or not (item.isfile() or item.isdir()) or item.name in seen):
                raise ValueError('Ruta, enlace o entrada repetida no permitida')
            seen.add(item.name)
            roots.add(name.parts[0])
            if item.isfile():
                relative = PurePosixPath(*name.parts[1:]).as_posix()
                if relative == '.' or relative in files:
                    raise ValueError('Archivo sin ruta única')
                files[relative] = archive.extractfile(item).read()
        if len(roots) != 1:
            raise ValueError('Se exige una sola raíz')
    app = {p: v for p, v in files.items() if p.startswith('private_git_manager/')}
    component = {p: v for p, v in files.items() if p.startswith('custom_components/pgm_forgejo_backup/')}
    required = {'private_git_manager/config.yaml', 'private_git_manager/Dockerfile',
                'private_git_manager/app/main.py', 'manifest.toml',
                'custom_components/pgm_forgejo_backup/manifest.json'}
    if not required <= files.keys():
        raise ValueError('Faltan las distribuciones esperadas')
    manifest = json.loads(files['custom_components/pgm_forgejo_backup/manifest.json'])
    if manifest.get('domain') != 'pgm_forgejo_backup':
        raise ValueError('Dominio de integración inesperado')
    version = re.search(rb'^version:\s*[\"\']?(\d+\.\d+\.\d+)[\"\']?\s*$',
                        files['private_git_manager/config.yaml'], re.M)
    if not version or not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        raise ValueError('Versión no válida')
    for name, data in (app | component).items():
        if (set(PurePosixPath(name).parts) & {'data', 'keys', '.env', '__pycache__'}
                or re.search(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{50,}|gh[pousr]_[A-Za-z0-9]{30,}', data)):
            raise ValueError('Material privado en el contexto distribuible')
    return {'app_version': version.group(1).decode(), 'component_version': manifest['version'],
            'app_files': len(app), 'component_files': len(component),
            'files': {p: hashlib.sha256(v).hexdigest() for p, v in sorted((app | component).items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'check'])
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY') != PUBLIC or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Solo se permite el diagnóstico desde el main público')
    receipt = args.archive.with_suffix('.json')
    if args.action == 'download':
        expected = os.environ.get('EXPECTED_SHA', '')
        if not SHA.fullmatch(expected):
            raise ValueError('Indica el SHA completo comprobado en Forgejo')
        reader = Mirror(REPOSITORY)
        if reader.branch() != expected:
            raise ValueError('El espejo no coincide con el SHA esperado de Forgejo')
        data = reader.archive(expected, limit=64 * 1024 * 1024).read()
        args.archive.write_bytes(data)
        receipt.write_text(json.dumps({'source_sha': expected, 'archive_sha256': hashlib.sha256(data).hexdigest()}))
    else:
        record = json.loads(receipt.read_text())
        if hashlib.sha256(args.archive.read_bytes()).hexdigest() != record['archive_sha256']:
            raise ValueError('Archivo alterado después de la descarga')
        record.update(inspect_archive(args.archive))
        print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
