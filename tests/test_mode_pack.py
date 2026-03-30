import json
import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from export_mode_pack import export_mode_pack
from install_mode_pack import install_mode_pack


def test_export_and_install_mode_pack(tmp_path):
    pack_dir = export_mode_pack('content_creation', tmp_path / 'exports')
    manifest = json.loads((pack_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['mode']['key'] == 'content_creation'
    assert (pack_dir / 'agents' / 'chief_of_staff' / 'SOUL.md').exists()

    installed = install_mode_pack(pack_dir, tmp_path / 'installed')
    assert (installed / 'manifest.json').exists()
    assert json.loads((installed / 'installed.json').read_text(encoding='utf-8'))['modeKey'] == 'content_creation'
