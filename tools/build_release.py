"""Validate and package a deterministic source release, without workspace data."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', '.venv', '.architecture-venv', 'node_modules', '__pycache__'}
ROOT_FILES = {'README.md', 'LICENSE', 'THIRD-PARTY-NOTICES.md', 'CONTRIBUTING.md',
              'PRIVACY.md', 'TERMS.md', '.gitignore'}
EXTENSIONS = {'.md', '.py', '.json', '.mjs', '.js', '.css', '.html', '.txt', '.wasm', '.3dm', '.png'}


def sources():
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or rel.parts[0] in ('build', 'dist') or str(rel) == 'source-manifest.json':
            continue
        if path.is_symlink():
            raise ValueError('Source package may not contain symlinks: ' + str(rel))
        if not path.is_file():
            continue
        if not (str(rel) in ROOT_FILES or rel.parts[0] in ('plugins', 'docs', 'tools', '.agents')):
            raise ValueError('Unexpected release input: ' + str(rel))
        if str(rel) not in ROOT_FILES and path.name not in {'LICENSE', 'NOTICE'} and path.suffix not in EXTENSIONS:
            raise ValueError('Unexpected release file type: ' + str(rel))
        data = path.read_bytes()
        if len(data) > 8 * 1024 * 1024:
            raise ValueError('Unexpectedly large source asset: ' + str(rel))
        # The pinned upstream Emscripten JS creates its virtual /home/web_user.
        # Exempt only these exact public npm bytes; local source still gets scanned.
        public_npm = (rel.as_posix().endswith('/dist/vendor/rhino3dm.js') and
                      hashlib.sha256(data).hexdigest() == '7f3b804afda0cafbf456d5729f2980a6011cf90e882b8156c674e78696e2005a')
        if path.suffix not in ('.wasm', '.3dm', '.png') and not public_npm:
            value = data.decode('utf-8')
            # Catch concrete local paths/credentials, not generic examples or dependency URLs.
            if re.search(r'/' + 'Users' + r'/[^/\s]+/|/' + 'home' + r'/[^/\s]+/|sk-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', value):
                raise ValueError('Private path or credential-shaped value in ' + str(rel))
        yield rel.as_posix(), data


def archive(path, files):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    files = list(sources())
    names = {name for name, _ in files}
    plugin = 'plugins/architecture-agent/'
    required = [plugin + '.codex-plugin/plugin.json', plugin + 'skills/architecture-modeling/SKILL.md',
                plugin + 'skills/architecture-modeling/scripts/geometry_kit.py',
                plugin + 'skills/architecture-modeling/scripts/requirements.txt',
                plugin + 'skills/architecture-modeling/scripts/viewer/dist/index.html',
                plugin + 'skills/architecture-modeling/scripts/viewer/dist/preview.mjs',
                plugin + 'skills/architecture-modeling/scripts/viewer/dist/vendor/rhino3dm.wasm',
                '.agents/plugins/marketplace.json']
    missing = set(required) - names
    if missing:
        raise ValueError('Incomplete source package: ' + ', '.join(sorted(missing)))
    version = json.loads((ROOT / plugin / '.codex-plugin/plugin.json').read_text())['version']
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'version': version, 'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files]}
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
    (args.output / 'source-manifest.json').write_bytes(manifest_bytes)
    releases = [archive(args.output / f'architecture-agent-{version}-source.zip', files + [('source-manifest.json', manifest_bytes)])]
    skill_prefix = plugin + 'skills/'
    # A self-contained skill bundle contains its referenced source/assets and licenses.
    skill_files = [(name.removeprefix(skill_prefix), data) for name, data in files if name.startswith(skill_prefix)]
    skill_files += [('architecture-modeling/LICENSE', (ROOT / 'LICENSE').read_bytes()),
                    ('architecture-modeling/THIRD-PARTY-NOTICES.md', (ROOT / 'THIRD-PARTY-NOTICES.md').read_bytes())]
    releases.append(archive(args.output / f'architecture-agent-{version}-skill.zip', skill_files))
    (args.output / 'release.json').write_text(json.dumps({'version': version, 'source_files': len(files), 'archives': releases}, indent=2) + '\n')
    print(json.dumps({'source_files': len(files), 'archives': releases}))


if __name__ == '__main__':
    main()
