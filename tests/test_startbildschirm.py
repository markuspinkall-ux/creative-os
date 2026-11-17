"""Startbildschirm (Plymouth): Rakete muss sofort erscheinen, auch mit NVIDIA.

Ohne UseSimpledrm wartet Plymouth bis zu 8 s auf den „richtigen“ Grafiktreiber.
NVIDIA kommt erst nach dem Wechsel ins System – kurz bevor Plymouth endet –,
der Bildschirm blieb deshalb den ganzen Start über schwarz.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CF = (ROOT / "image" / "Containerfile").read_text(encoding="utf-8")


def _plymouth_block():
    start = CF.index("plymouth-set-default-theme creative")
    return CF[start:CF.index("10-creative-splash.toml", start)]


def test_simpledrm_vor_dracut():
    block = _plymouth_block()
    assert "UseSimpledrm=1" in block
    assert block.index("UseSimpledrm=1") < block.index("dracut ")


def test_kernelparameter():
    assert '"plymouth.use-simpledrm"' in CF
    qb = (ROOT / "image" / "quiet-boot" / "creative-quiet-boot").read_text(encoding="utf-8")
    assert "plymouth.use-simpledrm" in qb.split('args="', 1)[1].split('"', 1)[0]
