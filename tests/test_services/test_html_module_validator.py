"""The shipped module template must parse cleanly with the validator."""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'html_module'))

from validate_module import validate  # noqa: E402

TEMPLATE = ROOT / 'tools' / 'html_module' / 'module_template.html'


def test_template_is_clean_once_its_picture_exists(tmp_path):
    target = tmp_path / 'My_Module.html'
    shutil.copy(TEMPLATE, target)
    errors, _, summary = validate(target)
    assert errors == ['c-boss: picture not found: images/portraits/c-boss.jpg']
    (tmp_path / 'images' / 'portraits').mkdir(parents=True)
    (tmp_path / 'images' / 'portraits' / 'c-boss.jpg').write_bytes(b'x')
    errors, warnings, summary = validate(target)
    assert errors == []
    assert 'scenes: 1  entities: 5' in summary[1]
    assert not any('no faction' in w for w in warnings)


def test_validator_flags_unknown_link_and_missing_faction(tmp_path):
    page = tmp_path / 'Bad.html'
    page.write_text('<html><body><h1>Bad</h1><div class="card" id="f-a"><h4>A</h4></div>'
                    '<details class="npc-card" id="c-x"><summary><div class="npc-name">X</div></summary>'
                    '<div class="card-body"><p>See <a href="#l-missing">it</a></p></div></details></body></html>',
                    encoding='utf-8')
    errors, warnings, _ = validate(page)
    assert 'c-x: links to unknown id #l-missing' in errors
    assert any('c-x: no faction line' in w for w in warnings)
