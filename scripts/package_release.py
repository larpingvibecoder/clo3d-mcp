"""Assemble the GitHub source ZIP and Python packages without local runtime files.
Run after tests and uv build. Outputs to the sibling release-assets directory.
"""
from pathlib import Path
import hashlib
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'release-assets'
OUT.mkdir(exist_ok=True)
ROOT_FILES = {'README.md', 'LICENSE', 'CHANGELOG.md', 'SECURITY.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md', 'pyproject.toml', 'uv.lock', '.gitignore', '.gitattributes'}
FOLDERS = {'src', 'bridge', 'tests', 'scripts', 'docs', 'examples', '.github'}
files = []
for path in sorted(ROOT.rglob('*')):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if '__pycache__' in rel.parts or path.suffix in {'.pyc', '.pyo'}:
        continue
    if str(rel) in ROOT_FILES or rel.parts[0] in FOLDERS:
        files.append((path, rel))
for path, rel in files:
    assert path.suffix not in {'.zprj', '.avt', '.obj', '.fbx', '.blend', '.png', '.jpg'}, rel
    text = path.read_text(encoding='utf-8')
    # Actual personal paths must never appear in the distributable source.
    assert (str(Path.home()).rstrip('/') + '/') not in text, rel
archive = OUT / 'clo3d-mcp-v0.1.0-alpha.1.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for path, rel in files:
        z.write(path, 'clo3d-mcp/' + rel.as_posix())
assets = [archive]
for name in ('clo3d_mcp-0.1.0a1-py3-none-any.whl', 'clo3d_mcp-0.1.0a1.tar.gz'):
    source = ROOT / 'dist' / name
    assert source.is_file(), 'Run uv build first'
    target = OUT / name
    shutil.copy2(source, target)
    assets.append(target)
(OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in assets))
print(f'Packaged {len(files)} source files into {archive.name}')
print(f'Assets: {OUT}')
