"""
3.5 — O cardinal solto antes de BTN nunca pode ser mais permissivo do que
a 3.4, verificado CONTRA O MOTOR DA 3.4 (não dentro do motor novo).

O revisor rejeitou o d043ce1: com um qualificador antes do cardinal na mesma
linha ("SIGWX:E OF W00800 S BTN N3720 - N3800 OCNL TS"), a 3.5 juntava-os por
AND e a área ficava E OF W00800 ∩ S OF N3800 — LP58 e LP78 passavam de NO-GO
a GO. Na 3.4 a quebra antes do BTN deixava o TS em toda a faixa.

`tests/referencia/app_3_4.py` é uma cópia fixa do app.py do main 46e8d8e
(3.4), só para este teste (o checkout do CI é raso, sem histórico). Gera-se
um conjunto determinístico de subentradas com qualificadores antes e depois
do cardinal (E/W/N/S OF, BTN em longitudes e latitudes, diagonais, AND ou
espaço, MAR/LAN/COT, janela HH/HH, subentrada anterior no mesmo campo) e
verifica-se, nos 52 aeródromos e numa grelha sobre a FIR, que a decisão da
3.5 nunca é mais permissiva do que a da 3.4.
"""
import random
import types
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
REF = Path(__file__).resolve().parent / "referencia" / "app_3_4.py"


@pytest.fixture(scope="module")
def eng34():
    mod = types.ModuleType("motor_3_4")
    exec(compile(conftest._extract_engine(REF.read_text(encoding="utf-8")), str(REF), "exec"),
         mod.__dict__)
    assert mod.APP_VERSION == "3.4"
    return mod


@pytest.fixture(scope="module")
def pontos(eng):
    pts = [(la, lo) for la, lo in eng.AERODROMES.values()]
    minx, miny, maxx, maxy = eng.FIR_POLYGON.bounds
    interior = eng.FIR_POLYGON.buffer(-0.03)
    y = miny + 0.1
    while y < maxy:
        x = minx + 0.1
        while x < maxx:
            if interior.contains(eng.Point(x, y)):
                pts.append((y, x))
            x += 0.2
        y += 0.2
    return pts


def _decisoes(e, texto, pontos):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    out = []
    for la, lo in pontos:
        r = e.find_region_for_point(regioes, la, lo)
        out.append(r["decision"] if r else None)
    return out


ANTES = ["", "E OF W00800", "W OF W00800", "N OF N3900", "S OF N3700", "E OF W00750",
         "W OF W00900", "BTN W00800 - W00700", "BTN W00900 AND W00830",
         "BTN N3900 AND N4000", "SW OF W00800", "NE OF N3900",
         "N OF N3840 AND W OF W00815"]
LIGA = [" ", " AND "]
CARD = ["N", "S", "E", "W"]
BTN = ["N3720 - N3800", "N3800 AND N3720", "N4000 - N3840", "W00800 - W00700",
       "W00900 AND W00830", "W00630 - W00730"]
DEPOIS = ["", " AND W OF W00800", " E OF W00800", " N OF N3730"]
SUP = ["", " MAR", " LAN", " COT", " MAR AND COT", " COT AND LAN"]
JANELA = ["", "23/03 "]
FEN = [("SIGWX:", "OCNL TS"), ("SIG CLD:", "LCA BKN 002HFT AGL"),
       ("SFC VIS:", "LCA 0800M FG")]
ANTERIOR = ["", "S OF N4100 LCA BKN 010HFT AGL ", "N OF N4000 ISOL TS "]


def _casos(n=400, semente=35):
    rnd = random.Random(semente)
    casos = []
    # Os casos do revisor, sempre presentes
    for pre in ("E OF W00800 ", "E OF W00800 AND ", "W OF W00800 ", "W OF W00800 AND ",
                "BTN W00800 - W00700 "):
        casos.append(f"SECN I SIGWX:{pre}S BTN N3720 - N3800 OCNL TS")
    casos.append("SECN I SIGWX:E OF W00800 S BTN N3720 - N3800 MAR OCNL TS")
    casos.append("SECN I SIGWX:E OF W00750 E BTN W00900 - W00800 OCNL TS")
    while len(casos) < n:
        campo, fen = rnd.choice(FEN)
        anterior = rnd.choice(ANTERIOR) if campo != "SFC VIS:" else ""
        if campo == "SIGWX:" and anterior.startswith("S OF N4100"):
            anterior = ""
        antes = rnd.choice(ANTES)
        liga = rnd.choice(LIGA) if antes else ""
        janela = rnd.choice(JANELA)
        sub = (f"{janela}{antes}{liga}{rnd.choice(CARD)} BTN {rnd.choice(BTN)}"
               f"{rnd.choice(DEPOIS)}{rnd.choice(SUP)} {fen}")
        casos.append(f"SECN I {campo}{anterior}{sub}".replace("  ", " "))
    return casos


CASOS = _casos()


@pytest.mark.parametrize("corpo", CASOS)
def test_nunca_mais_permissivo_que_a_3_4(eng, eng34, pontos, corpo):
    texto = build_gamet(corpo)
    novo = _decisoes(eng, texto, pontos)
    antigo = _decisoes(eng34, texto, pontos)
    piores = [(pontos[i], a, n) for i, (a, n) in enumerate(zip(antigo, novo))
              if a and (n is None or GRAV[n] < GRAV[a])]
    assert not piores, piores[:5]


def test_referencia_e_a_3_4_do_main():
    """A cópia fixa tem de ser a 3.4 tal como está no main 46e8d8e."""
    src = REF.read_text(encoding="utf-8")
    assert 'APP_VERSION = "3.4"' in src
    assert "_CARDINAL_BTN_RE" not in src
