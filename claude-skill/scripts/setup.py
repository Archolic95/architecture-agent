"""Install the source beta's libraries into a project-local Python environment."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', type=Path, required=True)
    args = parser.parse_args()
    if not (3, 12) <= sys.version_info[:2] <= (3, 13):
        parser.error('Use Python 3.12–3.13; this beta has not validated newer runtimes.')
    target = args.venv.expanduser().absolute()
    if target.is_symlink():
        parser.error('Choose a real environment directory, not a symlink.')
    if target.exists() and not (target / 'pyvenv.cfg').is_file() and any(target.iterdir()):
        parser.error('Refusing to replace a nonempty directory that is not a Python environment.')
    venv.EnvBuilder(with_pip=True).create(target)
    python = target / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    requirements = Path(__file__).with_name('requirements.txt')
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                    '--only-binary=:all:', '-r', str(requirements)], check=True)
    print(str(python))


if __name__ == '__main__':
    main()
