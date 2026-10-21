"""
3.11 — "ENTIRE FIR" a meio da linha nunca pode ser mais permissivo do que a
3.10, verificado CONTRA O MOTOR DA 3.10 (não dentro do motor novo).

O revisor rejeitou o 979aeeb: a quebra antes de ENTIRE FIR tirava à linha a
leitura da 3.10 ("SIGWX: N OF N4100 OCNL TS ENTIRE FIR SW OF W00800 ISOL TS":
a diagonal dava OCNL TS em toda a FIR, com aviso; partida, o OCNL TS ficava
só a N de N4100 e o aviso desaparecia). Desde então a linha é lida inteira
como na 3.10 e as partes ENTIRE FIR são lidas a mais.

`tests/referencia/app_3_10.py` é uma cópia fixa do app.py do main d2ccf2e
(3.10). Não editar. Os casos incluem MT OBSC/VA com NIL e com a linha de
abertura vazia (só janela), que ficam como na 3.10 (decisão do Duarte a
21-out-2026: mais vale conservador). Verifica-se, sem excepções,, nos 52 aeródromos e numa
grelha sobre a FIR, que a decisão nunca é mais permissiva do que a da 3.10, e
que os avisos "Área não reconhecida" e "Área alargada" da 3.10 se mantêm.
"""
import random
import re
import types
from pathlib import Path

import pytest
from shapely.prepared import prep

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
JANELA = ["", "", "19/21 ", "17/18 "]
# Linhas seguintes sem qualificador (herdam área, janela e subentrada)
SEGUINTES = {"SIGWX:": ["SEV SQL", "OCNL TS", "20/21 SEV SQL"],
             "SIG CLD:": ["OVC 002HFT AGL", "16/17 OVC 002HFT AGL", "BKN 004HFT AGL"],
             "SFC VIS:": ["0800M FG", "16/17 1000M FG"],
             "TURB:": ["SEV SFC/FL050", "16/17 SEV SFC/FL050"],
             "ICE:": ["SEV FL050/FL080"], "MTW:": ["SEV SFC/FL080"],
             "SFC WSPD:": ["40KT", "16/17 40KT"], "MT OBSC:": ["LAN"], "VA:": ["MAR"]}
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
        # 2.ª revisão do PR #24: herança da janela pelas linhas seguintes
        "SIGWX: N OF N4100 LAN ISOL TS 19/21 ENTIRE FIR ISOL TS\nSEV SQL",
        "SIG CLD: N OF N4100 BKN 010HFT AGL 17/18 ENTIRE FIR BKN 030HFT AGL\nOVC 002HFT AGL",
        "TURB: N OF N4100 MOD FL050/FL100 19/21 ENTIRE FIR\nSEV SFC/FL050",
        # Linha descartada na 3.10 (E OF W00800 ∩ COT vazio) alargada pela
        # parte sem fenómeno: as seguintes herdam a janela da 3.10
        "MTW: 17/19 N OF N4000 AND E OF W00800 SEV SFC/FL100 ENTIRE FIR AND "
        "ENTIRE FIR COT SEV SFC/FL100\nMOD FL080\nSEV SFC/FL100",
        "SIG CLD: N OF N4100 BKN 010HFT AGL\n17/19 E OF W00700 COT BKN 004HFT AGL ENTIRE FIR"
        "\nOVC 002HFT AGL",
        "SIGWX: 19/21 N OF N4300 OCNL TS ENTIRE FIR\nSEV SQL",
        # MT OBSC / VA: NIL e abertura vazia (ficam como na 3.10)
        "MT OBSC: NIL", "VA: NIL", "MT OBSC: 17/19 NIL", "MT OBSC: NIL N OF N4100",
        "MT OBSC:17/19 N OF N4100 LAN", "MT OBSC S OF N3900", "VA:17/19 N OF N4100 LAN",
        "MT OBSC:17/19 N OF N4100 LAN 19/21 S OF N3800 LAN",
        "MT OBSC:17/19 N OF N4100 LAN ENTIRE FIR", "VA: 19/21 ENTIRE FIR",
        "MT OBSC: NIL ENTIRE FIR", "MT OBSC:\nNIL", "VA:19/21 S OF N3800 MAR 17/19 ENTIRE FIR",
    ]
    while len(casos) < n:
        campo, fens = rnd.choice(CAMPOS)
        anterior = ""
        if rnd.random() < .3:
            anterior = f"{rnd.choice(QUAL)}{rnd.choice(SUP)} {rnd.choice(fens)} "
        janela1 = rnd.choice(JANELA)
        if campo in ("MT OBSC:", "VA:") and rnd.random() < .3:
            anterior = rnd.choice(["NIL ", "17/19 NIL ", "", "NIL\n"]) + anterior
        partes = [f"{janela1}{rnd.choice(QUAL)}{rnd.choice(SUP)} {rnd.choice(fens)}"]
        for _ in range(rnd.choice([1, 1, 1, 2])):
            depois = rnd.choice(DEPOIS)
            fen = rnd.choice(fens) if rnd.random() < .8 else ""
            partes.append(f"{rnd.choice(JANELA)}ENTIRE FIR"
                          f"{' ' + depois if depois else ''}{rnd.choice(SUP)} {fen}")
        corpo = campo + " " + anterior + rnd.choice(LIGA).join(partes)
        corpo = " ".join(corpo.split())
        for _ in range(rnd.choice([0, 0, 1, 2])):
            corpo += "\n" + rnd.choice(SEGUINTES[campo])
        casos.append(corpo)
    return casos


CASOS = _casos()


def test_casos_cobrem_nil_abertura_vazia_e_linhas_seguintes():
    mv = [c for c in CASOS if c.startswith(("MT OBSC", "VA"))]
    assert sum("NIL" in c for c in mv) > 10
    assert sum(re.match(r"(?:MT OBSC|VA):?\s*\d{2}/\d{2} [NSEWB]", c) is not None
               for c in mv) > 10
    assert sum("\n" in c for c in CASOS) > 100


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


# ---- Oráculo por hora ----
# A decisão por regiões ignora as janelas HH/HH. Aqui, por ponto e por hora da
# validade (15–20Z), junta-se os blocos em vigor que contêm o ponto e aplica-se
# decision(); pontos a menos de ~1 km de uma fronteira de bloco saltam-se.
HORAS = range(15, 21)


def _em_vigor(janela, h):
    m = re.match(r"(\d{2})–(\d{2})Z", janela or "")
    if not m:
        return True
    a, b = int(m.group(1)), int(m.group(2))
    return (a <= h < b) if a < b else (h >= a or h < b)


def _preparar(blocos):
    return [(b, prep(b.polygon.buffer(0.01)), prep(b.polygon.buffer(-0.01))) for b in blocos]


def _eventos(e, blocos, lo, la, h):
    p = e.Point(lo, la)
    ev = []
    for b, fora, dentro in blocos:
        if not _em_vigor(b.window, h) or not fora.contains(p):
            continue
        if not dentro.contains(p):
            return None                     # na fronteira: não se compara
        if b.phenomenon == "BASE_AMSL":
            ev.append(("BASE", max(0, round(b.value - e._terrain_elevation_ft(lo, la))),
                       b.qualifier, b.layer))
        elif b.phenomenon == "BASE_AGL":
            ev.append(("BASE", b.value, b.qualifier, b.layer))
        else:
            ev.append((b.phenomenon, b.value, b.qualifier, b.layer))
    return ev


@pytest.fixture(scope="module")
def pontos_hora(eng):
    pts = [(la, lo) for la, lo in eng.AERODROMES.values()]
    minx, miny, maxx, maxy = eng.FIR_POLYGON.bounds
    interior = eng.FIR_POLYGON.buffer(-0.03)
    y = miny + 0.12
    while y < maxy:
        x = minx + 0.12
        while x < maxx:
            if interior.contains(eng.Point(x, y)):
                pts.append((y, x))
            x += 0.3
        y += 0.3
    return pts


@pytest.mark.parametrize("corpo", CASOS)
def test_nunca_mais_permissivo_que_a_3_10_por_hora(eng, eng310, pontos_hora, corpo):
    texto = build_gamet("SECN I " + corpo)
    bn = _preparar(eng.parse_gamet(texto)[0])
    bo = _preparar(eng310.parse_gamet(texto)[0])
    piores = []
    for la, lo in pontos_hora:
        for h in HORAS:
            eo, en = _eventos(eng310, bo, lo, la, h), _eventos(eng, bn, lo, la, h)
            if eo is None or en is None:
                continue
            do, dn = eng310.decision(eo)[0], eng.decision(en)[0]
            if GRAV[dn] < GRAV[do]:
                piores.append(((la, lo, h), do, dn))
    assert not piores, piores[:5]


def test_referencia_e_a_3_10_do_main():
    """A cópia fixa tem de ser a 3.10 tal como está no main d2ccf2e."""
    src = REF.read_text(encoding="utf-8")
    assert 'APP_VERSION = "3.10"' in src
    assert "_partes_entire" not in src and "_CAMPO_NIL_RE" not in src
