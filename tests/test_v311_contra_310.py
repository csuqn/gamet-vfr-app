"""
3.11 — "ENTIRE FIR" a meio da linha nunca pode ser mais permissivo do que a
3.10, verificado CONTRA O MOTOR DA 3.10 (não dentro do motor novo).

O revisor rejeitou o 979aeeb: a quebra antes de ENTIRE FIR tirava à linha a
leitura da 3.10 ("SIGWX: N OF N4100 OCNL TS ENTIRE FIR SW OF W00800 ISOL TS":
a diagonal dava OCNL TS em toda a FIR, com aviso; partida, o OCNL TS ficava
só a N de N4100 e o aviso desaparecia). Desde então a linha é lida inteira
como na 3.10 e as partes ENTIRE FIR são lidas a mais.

`tests/referencia/app_3_10.py` é uma cópia fixa do app.py do main d2ccf2e
(3.10). Não editar. Os casos gerados não activam as outras duas correcções da
3.11 (abertura vazia de MT OBSC/VA e NIL exacto): a linha que abre o campo
tem sempre conteúdo e não há NIL. Verifica-se, nos 52 aeródromos e numa
grelha sobre a FIR, que a decisão nunca é mais permissiva do que a da 3.10, e
que os avisos "Área não reconhecida" e "Área alargada" da 3.10 se mantêm.
"""
import random
import types
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
REF = Path(__file__).resolve().parent / "referencia" / "app_3_10.py"


@pytest.fixture(scope="module")
def eng310():
    mod = types.ModuleType("motor_3_10")
    exec(compile(conftest._extract_engine(REF.read_text(encoding="utf-8")), str(REF), "exec"),
         mod.__dict__)
    assert mod.APP_VERSION == "3.10"
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


CAMPOS = [("SIGWX:", ["OCNL TS", "ISOL TS", "FRQ TS", "ISOL EMBD TS", "SEV SQL"]),
          ("SIG CLD:", ["BKN 002HFT AGL", "LCA BKN 004HFT AGL", "BKN 040HFT AGL",
                        "OCNL CB 020/XXXHFT AGL", "BKN 030HFT AMSL"]),
          ("SFC VIS:", ["1000M FG", "LCA 0800M FG", "4000M RA", "2000-5000M BR"]),
          ("TURB:", ["SEV SFC/FL080", "MOD FL050/FL100"]),
          ("ICE:", ["SEV FL050/FL100", "MOD FL080/FL120"]),
          ("MTW:", ["SEV SFC/FL100", "MOD FL080"]),
          ("SFC WSPD:", ["35KT", "25KT"]),
          ("MT OBSC:", [""]), ("VA:", [""])]
QUAL = ["N OF N4100", "S OF N3800", "BTN N3840 AND N4100", "E OF W00800", "W OF W00830",
        "N OF N4000 AND E OF W00800", "BTN W00800 - W00700", "N OF N4300",
        "SW OF W00800", "NE OF N3900", "S BTN N3720 - N3800", "BTN N3900 ~ N3800",
        "N4000 W00800"]
DEPOIS = ["", "", "SW OF W00800", "NE OF N3900", "N4000 W00800", "BTN W00800 - W00700",
          "WI N3900 W00900 - N3900 W00800 - N4000 W00800"]
SUP = ["", "", " LAN", " MAR", " COT", " MAR AND COT"]
JANELA = ["", "", "19/21 "]
LIGA = [" ", " ", " AND "]


def _casos(n=400, semente=311):
    rnd = random.Random(semente)
    casos = [
        "SIGWX: N OF N4100 OCNL TS ENTIRE FIR SW OF W00800 ISOL TS",
        "SIGWX: S OF N3800 LAN OCNL TS ENTIRE FIR MAR ISOL TS",
        "SIG CLD: S OF N3800 LAN BKN 002HFT AGL ENTIRE FIR MAR BKN 040HFT AGL",
        "SFC VIS: N OF N4100 1000M FG ENTIRE FIR NE OF N3900 4000M RA",
        "MT OBSC: N OF N4100 LAN ENTIRE FIR",
        "TURB: SEV SFC/FL050 ENTIRE FIR",
        "SIGWX: N OF N4100 FRQ ENTIRE FIR ISOL TS",
        "SIG CLD: N OF N4100 OCNL ENTIRE FIR ISOL TCU/CB 030/XXXHFT AGL",
    ]
    while len(casos) < n:
        campo, fens = rnd.choice(CAMPOS)
        anterior = ""
        if rnd.random() < .3:
            anterior = f"{rnd.choice(QUAL)}{rnd.choice(SUP)} {rnd.choice(fens)} "
        janela1 = rnd.choice(JANELA) if anterior else ""
        partes = [f"{janela1}{rnd.choice(QUAL)}{rnd.choice(SUP)} {rnd.choice(fens)}"]
        for _ in range(rnd.choice([1, 1, 1, 2])):
            depois = rnd.choice(DEPOIS)
            fen = rnd.choice(fens) if rnd.random() < .8 else ""
            partes.append(f"{rnd.choice(JANELA)}ENTIRE FIR"
                          f"{' ' + depois if depois else ''}{rnd.choice(SUP)} {fen}")
        corpo = campo + " " + anterior + rnd.choice(LIGA).join(partes)
        casos.append(" ".join(corpo.split()))
    return casos


CASOS = _casos()


def test_casos_nao_activam_as_outras_correcoes():
    for c in CASOS:
        assert "NIL" not in c
        assert not c.split(":", 1)[1].lstrip()[:2].isdigit(), c


@pytest.mark.parametrize("corpo", CASOS)
def test_nunca_mais_permissivo_que_a_3_10(eng, eng310, pontos, corpo):
    texto = build_gamet("SECN I " + corpo)
    novo = _decisoes(eng, texto, pontos)
    antigo = _decisoes(eng310, texto, pontos)
    piores = [(pontos[i], a, n) for i, (a, n) in enumerate(zip(antigo, novo))
              if a and (n is None or GRAV[n] < GRAV[a])]
    assert not piores, piores[:5]
    # Os avisos de área da 3.10 mantêm-se
    assert set(eng310.subentradas_sem_area(texto)) <= set(eng.subentradas_sem_area(texto))
    assert set(eng310.subentradas_alargadas(texto)) <= set(eng.subentradas_alargadas(texto))


def test_referencia_e_a_3_10_do_main():
    """A cópia fixa tem de ser a 3.10 tal como está no main d2ccf2e."""
    src = REF.read_text(encoding="utf-8")
    assert 'APP_VERSION = "3.10"' in src
    assert "_partes_entire" not in src and "_CAMPO_NIL_RE" not in src
