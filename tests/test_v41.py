"""
4.1 — "HH/HH" seguido de MAR/LAN/COT abre uma subentrada nova.

GAMET real 270900/271500 (recolhido a 27-out-2026 08:53Z):

    SFC VIS:09/11 W OF W00715 LCA 0200-5000M FG/BR 11/15 MAR AND COT LCA 0400-5000M FG/BR
    SIG CLD:09/11 W OF W00715 LCA BKN 001-004/008HFT AGL 11/15 MAR AND COT LCA BKN 004-006/008HFT AGL

Até à 4.0 só se injectavam quebras antes de N/S/E/W OF e BTN: o
"11/15 MAR AND COT" ficava na linha da subentrada 09/11, a linha inteira era
recortada por MAR∪COT e a janela 11/15 perdia-se. A VIS de 200 m e a base de
100 ft (09–11Z, a W de W00715) ficavam só no mar e na faixa costeira: 37
pontos do interior (LPPT, LPEV, LPCO, LPCB, LPCH, LPBJ…) davam GO, sem aviso.

Desde a 4.1 a 1.ª subentrada fica com a sua área inteira (W OF W00715, sem
recorte) e a janela 09–11Z; a 2.ª tem a janela 11–15Z e a área MAR∪COT em
TODA a FIR (leitura conservadora: contém a alternativa "W OF W00715 ∩
superfície"). Cada parte nunca fica com menos área do que a linha inteira da
4.0 (a área é unida com a leitura da 4.0), por isso nenhuma decisão fica mais
permissiva — verificado contra o motor da 4.0 (`tests/referencia/app_4_0.py`,
cópia fixa do app.py do main c37fba3; não editar), no arquivo e em subentradas
geradas. Semente: GAMET_SEMENTE (por omissão 41); GAMET_CASOS (por omissão 300).
"""
import os
import random
import types
from pathlib import Path

import pytest
from shapely.geometry import Point

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
RAIZ = Path(__file__).resolve().parent.parent
REF = Path(__file__).resolve().parent / "referencia" / "app_4_0.py"
ARQUIVO = RAIZ / "dados" / "gamets"
FICHEIRO = ARQUIVO / "2026" / "10" / "20261027T0853Z_270900-271500_c8fefbd089.txt"

G270900 = (
    "LPPC GAMET VALID 270900/271500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:09/11 W OF W00715 LCA 0200-5000M FG/BR 11/15 MAR AND COT LCA 0400-5000M FG/BR "
    "SIG CLD:09/11 W OF W00715 LCA BKN 001-004/008HFT AGL 11/15 MAR AND COT LCA BKN "
    "004-006/008HFT AGL SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:12 COLD FRONT "
    "N3900 W01200 - N4200 W00800 MOV ESE WKN CLD:W OF W00715 SCT/BKN SC 012-030/040HFT AGL "
    "N OF LINE N3900 W01200 - N4200 W00800 SCT/BKN AS/AC 060-090/100-130HFT AMSL WIND/T: "
    "BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 260/009KT PS13 "
    "200/010KT PS14 280/005KT PS14 2000FT AGL 290/008KT PS11 210/009KT PS13 310/006KT PS11 "
    "5000FT AGL 310/009KT PS07 270/011KT PS09 320/011KT PS09 FL100 270/014KT PS02 280/020KT "
    "PS02 290/015KT PS02 FL150 260/021KT MS08 280/022KT MS08 270/022KT MS09 FZLVL: 11200FT "
    "AMSL 11500FT AMSL 11600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 "
    "1000FT AGL 260/005KT PS17 330/010KT PS16 340/007KT PS19 2000FT AGL 300/009KT PS14 "
    "330/011KT PS13 350/008KT PS15 5000FT AGL 320/013KT PS11 280/013KT PS13 290/011KT PS15 "
    "FL100 290/012KT PS03 280/012KT PS04 270/013KT PS04 FL150 290/022KT MS06 290/018KT MS05 "
    "310/013KT MS05 FZLVL: 12100FT AMSL 11800FT AMSL 12100FT AMSL MNM QNH:1020HPA=")


@pytest.fixture(scope="module")
def eng40():
    mod = types.ModuleType("motor_4_0")
    exec(compile(conftest._extract_engine(REF.read_text(encoding="utf-8")), str(REF), "exec"),
         mod.__dict__)
    assert mod.APP_VERSION == "4.0"
    return mod


def _nome(eng, icao):
    return next(n for n in eng.AERODROMES if f"({icao})" in n)


def _decisoes(e, texto):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    out = {}
    for nome, (la, lo) in e.AERODROMES.items():
        r = e.find_region_for_point(regioes, la, lo)
        out[nome] = r["decision"] if r else None
    return out


def _comparar(eng, eng40, texto):
    """Nos 52 aeródromos a 4.1 nunca é mais permissiva do que a 4.0, e cada
    bloco da 4.0 tem um da 4.1 com o mesmo fenómeno e valor e área que o contém."""
    novo, antigo = _decisoes(eng, texto), _decisoes(eng40, texto)
    piores = [(n, antigo[n], novo[n]) for n in antigo
              if antigo[n] and (novo[n] is None or GRAV[novo[n]] < GRAV[antigo[n]])]
    assert not piores, (texto[90:260], piores[:5])
    bn, *_ = eng.parse_gamet(texto)
    bv, *_ = eng40.parse_gamet(texto)
    for b in bv:
        # Um "SQL/FZDZ" da linha inteira pode vir agora em blocos separados,
        # e "ISOL TS … OCNL TS" em ISOL e OCNL: compara-se componente a
        # componente (WX) ou pelo risco (TS/CB), sempre com área que contém
        # a da 4.0. VIS/bases/resto: o mesmo valor (ou pior: menor).
        if b.phenomenon == "WX":
            comps = [(c, "WX") for c in b.value.split("/")]
        else:
            comps = [(b.value, b.phenomenon)]
        for val, fen in comps:
            def serve(n):
                if n.phenomenon != fen or not n.polygon.buffer(1e-6).contains(b.polygon):
                    return False
                if fen == "WX":
                    return val in n.value.split("/")
                if fen in ("TS", "CB"):
                    return eng.TS_RISK.get(n.value, 1) >= eng.TS_RISK.get(val, 1)
                if fen in ("VIS", "BASE_AGL", "BASE_AMSL"):
                    return n.value <= val
                return n.value == val
            assert any(serve(n) for n in bn), (texto[90:260], "bloco da 4.0 perdido", fen, val)
    return novo, antigo


# --- O GAMET real ------------------------------------------------------------

def test_texto_real_igual_ao_arquivo():
    if not FICHEIRO.exists():
        pytest.skip("arquivo (ramo dados) não disponível")
    assert " ".join(FICHEIRO.read_text(encoding="utf-8").split()) == G270900


def test_versao(eng):
    # 4.1 ou posterior (a 4.2 só acrescenta o "resto do período")
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 1)


@pytest.mark.parametrize("icao", ["LPPT", "LPCO", "LPEV", "LPCB", "LPCH", "LPBJ"])
def test_interior_a_w_de_w00715_no_go(eng, icao):
    d = _decisoes(eng, G270900)
    assert d[_nome(eng, icao)] == "NO-GO"


@pytest.mark.parametrize("icao", ["LPBG", "LPMI", "LPMU", "LP66"])
def test_e_de_w00715_go(eng, icao):
    d = _decisoes(eng, G270900)
    assert d[_nome(eng, icao)] == "GO"


def test_blocos_e_janelas(eng):
    blocos, *_ = eng.parse_gamet(G270900)
    fir = eng.FIR_POLYGON
    w = eng.extract_polygon("W OF W00715")
    sup = eng._clean_poly(fir.intersection(eng.surface_polygon("COT/MAR")))
    lpev = Point(eng.AERODROMES[_nome(eng, "LPEV")][::-1])

    def so(fen, val):
        r = [b for b in blocos if b.phenomenon == fen and b.value == val]
        assert len(r) == 1, (fen, val, [(b.phenomenon, b.value) for b in blocos])
        return r[0]

    for fen, val in (("VIS", 200), ("BASE_AGL", 100)):
        b = so(fen, val)
        assert b.window == "09–11Z"
        assert b.surface == ""
        assert b.qualifier == "LCA"
        assert b.polygon.symmetric_difference(w).area < 1e-6
        assert b.polygon.contains(lpev)
    for fen, val in (("VIS", 400), ("BASE_AGL", 400)):
        b = so(fen, val)
        assert b.window == "11–15Z"
        assert b.surface == "COT/MAR"
        assert b.qualifier == "LCA"
        # Só no mar e na costa, mas em toda a FIR (também a E de W00715)
        assert b.polygon.symmetric_difference(sup).area < 1e-6
        assert not b.polygon.contains(lpev)
    assert len(blocos) == 4


def test_sem_avisos_falsos(eng, eng40):
    assert eng.campos_nao_interpretados(G270900) == []
    assert eng.subentradas_sem_area(G270900) == []
    assert eng.subentradas_alargadas(G270900) == []
    # A Secção II deste GAMET não tem "HH/HH" + superfície: a nota (AS/AC
    # AMSL contra o MEF, 3.8) fica igual à da 4.0
    assert eng.nuvens_baixas_secn2(G270900) == eng40.nuvens_baixas_secn2(G270900)


def test_contra_40_no_gamet_real(eng, eng40):
    novo, antigo = _comparar(eng, eng40, G270900)
    mudou = {n for n in novo if novo[n] != antigo[n]}
    assert _nome(eng, "LPPT") in mudou and _nome(eng, "LPBG") not in mudou


# --- Secção II (nuvens_baixas_secn2 usa a mesma máquina) ----------------------

def test_secn2_janela_superficie(eng):
    t = ("LPPC GAMET VALID 270900/271500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
         "SECN I SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II CLD:09/11 W OF W00715 "
         "SCT ST 002/006HFT AGL 11/15 MAR AND COT SCT ST 004/008HFT AGL MNM QNH:1020HPA=")
    _c, nuvens = eng.nuvens_baixas_secn2(t)
    por_base = {n[0]: n for n in nuvens}
    assert set(por_base) == {200, 400}
    assert por_base[200][2] == "09–11Z" and por_base[200][3] == ""
    assert _nome(eng, "LPEV") in por_base[200][4]
    assert por_base[400][2] == "11–15Z" and por_base[400][3] == "COT/MAR"
    assert _nome(eng, "LPEV") not in por_base[400][4]
    assert all(n[5] for n in nuvens)          # áreas lidas


# --- Casos que ficam como na 4.0 ----------------------------------------------

@pytest.mark.parametrize("corpo", [
    # janela + superfície no fim, sem nada a seguir
    "SIG CLD:W OF W00715 BKN 002/006HFT AGL 11/15 MAR",
    # janela + superfície a abrir o campo
    "SIG CLD:11/15 MAR AND COT BKN 002/006HFT AGL",
    "SIG CLD 11/15 MAR BKN 002/006HFT AGL",
    # superfície sem janela
    "SFC VIS:W OF W00715 0800M BR MAR AND COT",
])
def test_inalterados(eng, eng40, corpo):
    t = build_gamet(corpo, validity="270900/271500")
    novo, antigo = _comparar(eng, eng40, t)
    assert novo == antigo
    assert eng.campos_nao_interpretados(t) == eng40.campos_nao_interpretados(t)


def test_primeira_parte_com_superficie_nunca_perde_area(eng, eng40):
    # "09/11 MAR … 11/15 LAN …": a 4.0 punha as duas bases em MAR∪LAN; cada
    # parte fica com pelo menos essa área (nunca mais permissivo).
    t = build_gamet("SIG CLD:N OF N4000 09/11 MAR BKN 002/006HFT AGL 11/15 LAN BKN "
                    "004/008HFT AGL", validity="270900/271500")
    _comparar(eng, eng40, t)
    blocos, *_ = eng.parse_gamet(t)
    jan = {b.value: b.window for b in blocos if b.phenomenon == "BASE_AGL"}
    assert jan == {200: "09–11Z", 400: "11–15Z"}


def test_tres_partes(eng, eng40):
    t = build_gamet("SFC VIS:09/11 W OF W00800 0800M FG 11/13 MAR 1200M BR 13/15 LAN "
                    "AND COT 2000M BR", validity="270900/271500")
    _comparar(eng, eng40, t)
    blocos, *_ = eng.parse_gamet(t)
    vis = {b.value: b for b in blocos if b.phenomenon == "VIS"}
    assert {v: b.window for v, b in vis.items()} == {800: "09–11Z", 1200: "11–13Z",
                                                     2000: "13–15Z"}
    # 1.ª parte: a sua área inteira, sem recorte
    w = eng.extract_polygon("W OF W00800")
    assert vis[800].polygon.symmetric_difference(w).area < 1e-6
    # As outras: a sua superfície em toda a FIR, unida com a área que a 4.0
    # dava à linha inteira (W OF W00800 ∩ MAR∪LAN∪COT) — nunca menos.
    antigo = eng._clean_poly(w.intersection(eng.surface_polygon("COT/LAN/MAR")))
    for v, sup in ((1200, "MAR"), (2000, "COT/LAN")):
        p = vis[v].polygon.buffer(1e-6)
        assert p.contains(antigo)
        assert p.contains(eng._clean_poly(eng.FIR_POLYGON.intersection(eng.surface_polygon(sup))))
    assert eng.campos_nao_interpretados(t) == []


# --- Contra o motor da 4.0: arquivo e subentradas geradas ----------------------

def test_arquivo_contra_40(eng, eng40):
    if not ARQUIVO.exists():
        pytest.skip("arquivo (ramo dados) não disponível")
    fich = sorted(ARQUIVO.rglob("*.txt"))
    assert fich
    for p in fich:
        t = p.read_text(encoding="utf-8").strip()
        _comparar(eng, eng40, t)
        # Nenhum aviso "Campo não interpretado" novo
        if not eng40.campos_nao_interpretados(t):
            assert eng.campos_nao_interpretados(t) == [], p.name


QUALS = ["", "W OF W00715 ", "N OF N4000 ", "S OF N3900 AND W OF W00800 ",
         "BTN N3840 AND N4000 ", "E OF W00800 "]
SUPS = ["MAR", "LAN", "COT", "MAR AND COT", "COT AND LAN", "LAN AND MAR", "COT MAR"]
VALORES = {
    "SFC VIS": ["LCA 0200-5000M FG/BR", "0800M BR", "3000M RA", "LCA 1,5KM BR", "1200M BR"],
    "SIG CLD": ["LCA BKN 001-004/008HFT AGL", "BKN 004/010HFT AGL", "OVC 002/006HFT",
                "ISOL TCU/CB 020/XXXHFT AGL", "BKN 008/015HFT AMSL", "OCNL CB 030/XXXHFT AGL"],
    "SIGWX": ["ISOL TS", "OCNL TSRA", "SQL", "FZDZ"],
    "TURB": ["SEV SFC/FL080", "MOD SFC/FL050"],
    "ICE": ["SEV FL060/FL120", "MOD FL050/FL100"],
}


def _subentrada(rng):
    campo = rng.choice(list(VALORES))
    h = rng.choice([9, 10, 11])
    partes = []
    jan0 = rng.choice(["", f"{h:02d}/{h + 2:02d} "])
    sup0 = rng.choice(["", "", f"{rng.choice(SUPS)} "])
    partes.append(f"{jan0}{rng.choice(QUALS)}{sup0}{rng.choice(VALORES[campo])}")
    for _ in range(rng.choice([1, 1, 2])):
        h = min(h + 1, 13)
        sep = rng.choice(["", "", "AND "])
        partes.append(f"{sep}{h:02d}/{h + 2:02d} {rng.choice(SUPS)} "
                      f"{rng.choice(VALORES[campo])}")
    if rng.random() < 0.2:
        partes.append(f"{rng.choice(QUALS[1:])}{rng.choice(VALORES[campo])}")
    sep_campo = rng.choice([":", ": ", " "])
    return f"{campo}{sep_campo}" + " ".join(partes)


def test_geradas_contra_40(eng, eng40):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "41")))
    n = int(os.environ.get("GAMET_CASOS", "300"))
    mudaram = 0
    for _ in range(n):
        corpo = " ".join(_subentrada(rng) for _ in range(rng.choice([1, 1, 2])))
        t = build_gamet(corpo, validity="270900/271500")
        novo, antigo = _comparar(eng, eng40, t)
        mudaram += novo != antigo
        if not eng40.campos_nao_interpretados(t):
            assert eng.campos_nao_interpretados(t) == [], corpo
    # O gerador exercita de facto a mudança
    assert mudaram > n // 10
