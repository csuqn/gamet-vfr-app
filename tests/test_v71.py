"""
7.1 — "MT ABV nnnHFT AMSL" a meio da linha (decisão do Duarte a 25-nov-2026;
mudança de leitura, limiares iguais).

GAMETs reais de 24/25-nov-2026 (SFC VIS):

    241500/242100  LAN LCA 3000-5000M BR/RA/DZ MT ABV 035HFT AMSL 0200-5000M SN
    242100/250300  LAN LCA 3000-5000M RA/DZ/BR MT ABV 035HFT AMSL 0200-5000M SN/FG/BR
    250300/250900  N OF N3830 LAN LCA 3000-5000M RA/BR MT ABV 035HFT AMSL 0200-5000M SN/FG/BR
    250900/251500  LCA 3000-5000M RA MT ABV 045HFT AMSL 0200-5000M SN/FG/BR

Até à 7.0 os dois valores ficavam na área da subentrada, os dois com o LCA:
VIS 200 m LCA → MARGINAL em toda a terra, e o "montanha acima de 3500 ft"
perdia-se. Desde a 7.1 o "MT ABV …" abre uma parte nova: o que vem antes fica
como estava; o que vem depois fica na área da subentrada ∩ a superfície da
linha ∩ as quadrículas de relevo (MEF, `_TERRAIN_MAX_FT`) ≥ o limiar, sem o LCA
(só se estiver escrito depois do "MT ABV") e com a janela da parte. Na dúvida,
fica como na 7.0, com aviso.

Fora das quadrículas de montanha o valor do "MT ABV" deixa de contar: num texto
hipotético "LAN 6000M MT ABV 035HFT AMSL 0200M" a 7.1 dá GO fora do relevo,
onde a 7.0 dava NO-GO — **mais permissivo do que a 7.0 só fora do relevo, por
leitura** (aceite pelo Duarte). Dentro das quadrículas ≥ limiar nunca é mais
permissivo. Comparado com o motor da 7.0 (`tests/referencia/app_7_0.py`, cópia
fixa do app.py do main 810bd55; não editar).
"""
import json
import random
import re
import types
from pathlib import Path

import pytest
from shapely.geometry import Point, box
from shapely.ops import unary_union

import conftest
from conftest import build_gamet

REF70 = Path(__file__).resolve().parent / "referencia" / "app_7_0.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "GO COND.": 0.5, "MARGINAL": 1, "NO-GO": 2, None: -1}

G241500_F = DADOS / "gamets/2026/11/20261124T1454Z_241500-242100_96df58cc0f.txt"
G241500 = (
    'LPPC GAMET VALID 241500/242100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I '
    'SFC VIS:LAN LCA 3000-5000M BR/RA/DZ MT ABV 035HFT AMSL 0200-5000M SN SIG CLD:N OF '
    'N4000 LAN LCA BKN 004-008/010HFT AGL N OF N4000 MAR AND COT TCU/CB 018/XXXHFT AGL '
    'ICE:N OF N4100 LCA MOD ABV FL070 TURB:N OF N4000 LCA MOD SFC/FL050 SIGMET '
    'APPLICABLE:AT TIME OF ISSUE NIL SECN II PSYS:18 N3730 W00830 - N4230 W00830 COLD FRONT'
    ' MOV E NC CLD:SCT/BKN SC/CU 012-035/050HFT AGL SCT/BKN AS/AC 060-090/100-130HFT AMSL '
    'WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL '
    '260/020KT PS04 280/022KT PS11 280/020KT PS06 2000FT AGL 270/023KT PS02 280/025KT PS08 '
    '280/027KT PS04 5000FT AGL 270/039KT MS04 280/030KT PS01 280/033KT MS01 FL100 270/041KT'
    ' MS08 280/038KT MS09 270/037KT MS08 FL150 270/051KT MS17 280/054KT MS17 290/055KT MS15'
    ' FZLVL: 5900FT AMSL 5700FT AMSL 5900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 '
    'W00752 N3700 W00800 1000FT AGL 310/018KT PS13 310/018KT PS11 330/018KT PS14 2000FT AGL'
    ' 310/021KT PS10 310/020KT PS08 330/018KT PS12 5000FT AGL 310/026KT PS03 300/021KT PS03'
    ' 290/017KT PS08 FL100 280/032KT MS02 270/038KT MS01 270/036KT PS01 FL150 280/048KT '
    'MS11 270/049KT MS10 280/044KT MS10 FZLVL: 8400FT AMSL 8900FT AMSL 10500FT AMSL MNM '
    'QNH:1012HPA=')

G242100_F = DADOS / "gamets/2026/11/20261124T2040Z_242100-250300_741fc34128.txt"
G242100 = (
    'LPPC GAMET VALID 242100/250300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I '
    'SFC VIS:LAN LCA 3000-5000M RA/DZ/BR MT ABV 035HFT AMSL 0200-5000M SN/FG/BR SIG CLD:N '
    'OF N4000 LAN LCA BKN 002-008/010HFT AGL N OF N4000 TCU/CB 018/XXXHFT AGL ICE:N OF '
    'N4000 LCA MOD ABV FL070 TURB:N OF N4000 LCA MOD SFC/FL050 SIGMET APPLICABLE:AT TIME OF'
    ' ISSUE NIL SECN II PSYS:00 NIL CLD:SCT/BKN SC/CU 012-030/045HFT AGL FEW/SCT AS/AC '
    '060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 '
    'W00750 1000FT AGL 270/023KT PS03 300/028KT PS09 290/024KT PS05 2000FT AGL 280/031KT '
    'PS00 300/033KT PS06 290/029KT PS03 5000FT AGL 280/044KT MS05 300/035KT MS00 290/045KT '
    'MS03 FL100 270/053KT MS10 290/043KT MS11 270/049KT MS08 FL150 270/054KT MS21 290/060KT'
    ' MS19 280/068KT MS17 FZLVL: 4700FT AMSL 5200FT AMSL 4800FT AMSL LISBOA EVORA FARO '
    'N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 300/023KT PS12 280/021KT PS10 '
    '320/022KT PS13 2000FT AGL 300/025KT PS09 290/024KT PS08 320/023KT PS11 5000FT AGL '
    '300/030KT PS03 290/032KT PS02 310/019KT PS06 FL100 290/045KT MS02 280/044KT MS02 '
    '280/031KT PS01 FL150 280/050KT MS11 270/052KT MS11 270/040KT MS10 FZLVL: 6600FT AMSL '
    '7100FT AMSL 10600FT AMSL MNM QNH:1011HPA=')

G250300_F = DADOS / "gamets/2026/11/20261125T0241Z_250300-250900_98469ed44c.txt"
G250300 = (
    'LPPC GAMET VALID 250300/250900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I '
    'SFC VIS:N OF N3830 LAN LCA 3000-5000M RA/BR MT ABV 035HFT AMSL 0200-5000M SN/FG/BR SIG'
    ' CLD:N OF N4000 LAN LCA BKN 002-008/010HFT AGL N OF N4000 TCU 018/XXXHFT AGL ICE:N OF '
    'N3715 LCA MOD FL070/130 TURB:N OF N3930 LCA MOD SFC/FL050 SIGMET APPLICABLE: AT TIME '
    'OF ISSUE NIL SECN II PSYS:06 N4645 E00445 L 1000HPA MOV SE WKN 06 N3715 W03600 H STNR '
    'NC CLD:SCT/BKN SC/CU 012-030/045HFT AGL 03/06 FEW/SCT AS/AC 060-090/100-130HFT AMSL '
    '06/09 N OF N3730 SCT/BKN AS/AC 060-090/120-150HFT AMSL WIND/T: BRAGANCA PORTO VISEU '
    'N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 280/032KT PS02 330/013KT PS08 '
    '300/021KT PS05 2000FT AGL 290/040KT PS00 310/024KT PS06 300/031KT PS03 5000FT AGL '
    '310/044KT MS03 310/033KT PS01 300/034KT MS02 FL100 310/041KT MS07 310/031KT MS09 '
    '310/034KT MS08 FL150 330/034KT MS18 310/040KT MS19 310/041KT MS18 FZLVL: 5000FT AMSL '
    '5700FT AMSL 5100FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 '
    '1000FT AGL 310/020KT PS12 310/019KT PS09 330/019KT PS12 2000FT AGL 310/024KT PS09 '
    '320/024KT PS07 330/023KT PS10 5000FT AGL 310/029KT PS02 310/029KT PS01 310/027KT PS04 '
    'FL100 310/038KT MS03 300/041KT MS04 290/034KT MS01 FL150 310/053KT MS11 290/056KT MS11'
    ' 280/045KT MS10 FZLVL: 6600FT AMSL 6100FT AMSL 7800FT AMSL MNM QNH:1013HPA=')

G250900_F = DADOS / "gamets/2026/11/20261125T0842Z_250900-251500_3317039a14.txt"
G250900 = (
    'LPPC GAMET VALID 250900/251500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I '
    'SFC VIS:LCA 3000-5000M RA MT ABV 045HFT AMSL 0200-5000M SN/FG/BR SIG CLD:N OF N4000 '
    'LAN LCA BKN 002-008/010HFT AGL N OF N3930 TCU/CB 018-025/XXXHFT AGL ICE:N OF N3700 LCA'
    ' MOD ABV FL050 TURB:09/11 N OF N3930 AND E OF W00800 LCA MOD SFC/FL040 SIGMET '
    'APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:12 N4500 W00300 L 1004HPA MOV SE NC 12 '
    'N3630 W03400 H 1033HPA STNR NC CLD:SCT/BKN SC/CU 012-030/040-050HFT AGL SCT/BKN AS/AC '
    '060-090/120-150HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 '
    'W00750 1000FT AGL 290/024KT PS06 310/007KT PS09 300/016KT PS07 2000FT AGL 300/026KT '
    'PS03 330/017KT PS07 310/019KT PS04 5000FT AGL 320/037KT MS03 320/025KT PS01 310/026KT '
    'MS01 FL100 320/034KT MS07 310/027KT MS08 320/026KT MS07 FL150 320/019KT MS16 320/046KT'
    ' MS14 330/046KT MS15 FZLVL: 5600FT AMSL 5700FT AMSL 5900FT AMSL LISBOA EVORA FARO '
    'N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 330/011KT PS11 300/012KT PS10 '
    '310/013KT PS13 2000FT AGL 330/014KT PS09 310/015KT PS07 310/014KT PS10 5000FT AGL '
    '310/024KT PS03 310/023KT PS01 320/025KT PS04 FL100 320/041KT MS04 320/040KT MS04 '
    '310/022KT MS02 FL150 310/046KT MS10 310/043KT MS12 310/037KT MS11 FZLVL: 6600FT AMSL '
    '6100FT AMSL 7800FT AMSL MNM QNH:1013HPA=')

# (texto, ficheiro, limiar em pés, área da subentrada (lat mínima), superfície)
REAIS = {
    "241500": (G241500, G241500_F, 3500, None, "LAN"),
    "242100": (G242100, G242100_F, 3500, None, "LAN"),
    "250300": (G250300, G250300_F, 3500, 38.5, "LAN"),
    "250900": (G250900, G250900_F, 4500, None, ""),
}

GRELHA = [(36.95 + 0.3 * i, -9.85 + 0.3 * j) for i in range(18) for j in range(12)]

# Pontos que passam a NO-GO em cada GAMET real (modo manual, decisão principal)
# — os que estão em quadrículas com MEF ≥ limiar dentro da área da VIS e que a
# 7.0 não dava já NO-GO. Calculados à parte em test_gamets_reais_52_pontos.
MUDAM = {
    "241500": ["LPCB", "LPPN", "LP57"],
    "242100": ["LPCB", "LPPN", "LP57"],
    "250300": ["LPCB", "LPPN", "LP57"],
    "250900": [],
}


@pytest.fixture(scope="module")
def eng70():
    mod = types.ModuleType("motor_7_0")
    mod.__dict__["__file__"] = str(REF70)
    exec(compile(conftest._extract_engine_ref(REF70.read_text(encoding="utf-8")), str(REF70),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_7_0(eng, eng70):
    assert eng70.APP_VERSION == "7.0"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (7, 1)


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_copia_do_gamet_real_igual_ao_arquivo(nome):
    texto, f, *_ = REAIS[nome]
    if not f.exists():
        pytest.skip("sem dados/")
    assert f.read_text(encoding="utf-8").strip() == texto


def _icao(nome):
    return nome.split("(")[-1].rstrip(")")


def _decisoes(e, texto, pontos=None):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    pontos = pontos if pontos is not None else list(e.AERODROMES.items())
    return {k: (e.find_region_for_point(regioes, la, lo) or {}).get("decision")
            for k, (la, lo) in pontos}


def _montanha(eng, limiar):
    """União das quadrículas com MEF ≥ limiar (calculada aqui, à parte)."""
    return unary_union([box(lo, la, lo + 1.0, la + 0.5)
                        for (la, lo), v in eng._TERRAIN_MAX_FT.items() if v >= limiar])


def _area_vis(eng, lat_min, sup):
    a = eng.FIR_POLYGON
    if lat_min is not None:
        a = a.intersection(box(-30, lat_min, 10, 60))
    if sup:
        a = a.intersection(eng.surface_polygon(sup))
    return a


def _na_montanha(eng, nome, la, lo):
    _t, _f, limiar, lat_min, sup = REAIS[nome]
    if eng._terrain_elevation_ft(lo, la) < limiar:
        return False
    if lat_min is not None and la <= lat_min:
        return False
    return not sup or eng.surface_polygon(sup).contains(Point(lo, la))


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamets_reais_blocos(eng, nome):
    texto, _f, limiar, lat_min, sup = REAIS[nome]
    vis = [b for b in eng.parse_gamet(texto)[0] if b.phenomenon == "VIS"]
    assert sorted((b.value, b.qualifier) for b in vis) == [(200, ""), (3000, "LCA")]
    antes = next(b for b in vis if b.value == 3000)
    mt = next(b for b in vis if b.value == 200)
    area = _area_vis(eng, lat_min, sup)
    # A parte de antes fica como estava (área da subentrada e superfície, LCA)
    assert antes.polygon.symmetric_difference(area).area < 1e-6
    assert antes.surface == sup and antes.window == "" and getattr(antes, "relevo", 0) == 0
    # A parte do MT ABV: área ∩ quadrículas ≥ limiar, sem LCA, sem janela
    esperada = area.intersection(_montanha(eng, limiar))
    assert esperada.area > 0.5
    assert mt.polygon.symmetric_difference(esperada).area < 1e-6
    assert mt.surface == sup and mt.window == "" and not mt.janela_ambigua
    assert mt.relevo == limiar


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamets_reais_52_pontos(eng, eng70, nome):
    texto = REAIS[nome][0]
    novo, velho = _decisoes(eng, texto), _decisoes(eng70, texto)
    mudam = []
    for k, (la, lo) in eng.AERODROMES.items():
        if _na_montanha(eng, nome, la, lo):
            assert novo[k] == "NO-GO", (k, novo[k])
            if velho[k] != "NO-GO":
                mudam.append(_icao(k))
        else:
            assert novo[k] == velho[k], (k, novo[k], velho[k])
    if MUDAM[nome] is not None:
        assert sorted(mudam) == sorted(MUDAM[nome])
    print(nome, sorted(mudam))


def _assin(blocos):
    return sorted((b.phenomenon, str(b.value), b.qualifier, b.surface, b.window,
                   b.janela_ambigua, round(b.polygon.area, 7)) for b in blocos)


def _g(corpo, val="241500/242100"):
    return build_gamet(f"SECN I {corpo}", validity=val)


# ---------------------------------------------------------------- avisos e notas

@pytest.mark.parametrize("nome", sorted(REAIS))
def test_gamets_reais_aviso(eng, nome):
    texto, _f, limiar, *_ = REAIS[nome]
    r = eng.analisar_gamet(texto, "manual")
    av = [(t, md) for t, md in r["avisos"] if "Valor só junto ao relevo" in md]
    assert len(av) == 1, r["avisos"]
    tipo, md = av[0]
    assert tipo == "aviso"
    assert eng.titulo_aviso(md) == "Valor só junto ao relevo"
    assert eng.etiqueta_aviso(tipo, md) == "conta para a decisão"
    assert f"≥ **{limiar} ft**" in md and "MT ABV" in md
    assert "junto às serras, não necessariamente na pista" in md
    # Os aeródromos abrangidos: os da área da parte (calculada à parte)
    cod = re.search(r"aeródromos abrangidos: ([A-Z0-9, ]+)\.", md).group(1).split(", ")
    assert sorted(cod) == sorted(_icao(k) for k, (la, lo) in eng.AERODROMES.items()
                                 if _na_montanha(eng, nome, la, lo))
    # Sem avisos de área nem de campo não interpretado
    assert not any("Área não reconhecida" in md or "Campo não interpretado" in md
                   for _t, md in r["avisos"]), r["avisos"]


def test_gamet_real_motivo_normal_e_nota_de_alcance(eng):
    """O motivo é o de sempre ("VIS 200m < 1500m", que classificar_motivo já
    conhece); o alcance vai nas notas da região."""
    r = eng.analisar_gamet(G241500, "manual")
    reg = eng.find_region_for_point(r["regioes"], 39.8483, -7.4417)   # LPCB
    assert reg["decision"] == "NO-GO"
    assert any(m.startswith("VIS 200m < 1500m") for m in reg["reasons"]), reg["reasons"]
    assert any("VIS: apenas junto ao relevo com MEF ≥ 3500 ft" in n for n in reg["notas"])
    for m in reg["reasons"]:
        assert eng.classificar_motivo(m)["nivel"] is not None, m
    fora = eng.find_region_for_point(r["regioes"], 38.7742, -9.1342)  # LPPT
    assert fora["decision"] == "MARGINAL"
    assert not any("relevo" in n for n in fora.get("notas", []))


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_nota_de_relevo_plena_vale_em_cada_ponto(eng, nome):
    """Oráculo: numa região com a nota de relevo plena (sem "parte da zona"),
    cada ponto (aeródromos e grelha, longe das fronteiras das quadrículas) está
    numa quadrícula com MEF ≥ limiar; sem a nota, a VIS 200 não conta lá."""
    texto, _f, limiar, *_ = REAIS[nome]
    regioes = eng.compute_dynamic_regions(eng.parse_gamet(texto)[0])
    nota = f"VIS: apenas junto ao relevo com MEF ≥ {limiar} ft"
    n = 0
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        if not eng.FIR_POLYGON.buffer(-0.02).contains(Point(lo, la)):
            continue
        reg = eng.find_region_for_point(regioes, la, lo)
        plena = any(x.startswith(nota) for x in reg["notas"])
        if plena:
            assert eng._terrain_elevation_ft(lo, la) >= limiar, (la, lo)
            n += 1
        if not any(nota in x for x in reg["notas"]):
            assert not any(m.startswith("VIS 200m") for m in reg["reasons"]), (la, lo)
    assert n > 10


def test_app_streamlit_mostra_o_aviso(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = "outro texto"
    at.session_state["_active_gamet_text"] = G241500
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    avisos = [w.value for w in at.warning if "Valor só junto ao relevo" in w.value]
    assert len(avisos) == 1 and "LPCB" in avisos[0], [w.value for w in at.warning]
    assert any(e.label.startswith("Valor só junto ao relevo") for e in at.expander), \
        [e.label for e in at.expander]


def test_analisar_py_sem_alertas(eng):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    for nome, (texto, *_r) in REAIS.items():
        alertas = analisar.analisar(eng, texto)["alertas"]
        assert not any("MT" in a or "Área" in a or "Oráculo" in a or "Campo" in a
                       for a in alertas), (nome, alertas)
    t = _g("SFC VIS:LAN LCA 3000-5000M BR MT ABV XXXHFT AMSL 0200-5000M SN")
    assert any(a.startswith("Área não reconhecida (MT ABV") for a in analisar.analisar(eng, t)["alertas"])


# ------------------------------------------------------- na dúvida, como na 7.0

DUVIDA = [
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV XXXHFT AMSL 0200-5000M SN",      # limiar ilegível
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 35HFT AMSL 0200-5000M SN",       # 2 algarismos
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT 0200-5000M SN",           # sem AMSL
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT AGL 0200-5000M SN",       # AGL
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HTF AMSL 0200-5000M SN",      # gralha
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT AMSL",                    # sem valor
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT AMSL =",
    "SFC VIS:MT ABV 035HFT AMSL 0200-5000M SN",                            # início do campo
    "SFC VIS:LAN LCA MT ABV 035HFT AMSL 0200-5000M SN",                    # só área antes
    "SFC VIS:N OF N4000 LAN LCA 3000M BR S OF N3900 LAN MT ABV 035HFT AMSL 0200M SN",
    "SFC VIS:LAN LCA 3000-5000M BR 11/15 MT ABV 035HFT AMSL 0200M SN",     # depois da janela
    "SFC VIS:LAN LCA 3000-5000M BR MAR MT ABV 035HFT AMSL 0200M SN",
    "SFC VIS:LAN 3000M BR MT ABV 035HFT AMSL 0200M SN MT ABV 050HFT AMSL 0100M FG",  # dois
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT AMSL 0200M SN 13/15 0800M FG",
    "SFC VIS:LAN 3000M BR MT ABV 035HFT AMSL MAR 0200M SN",                # superfície depois
    "SFC VIS:LAN 3000M BR MT ABV 035HFT AMSL 0200M SN WI 30NM OF N4000 W00800",
    "SFC VIS:LAN 3000M BR MT ABV 035HFT AMSL 0200M SN NW OF W00800",
    "SFC VIS:S OF N3800 LAN LCA 3000-5000M BR MT ABV 050HFT AMSL 0200M SN",  # intersecção vazia
    "SFC VIS:LAN LCA 3000-5000M BR MT ABV 080HFT AMSL 0200M SN",           # nenhuma quadrícula
    "SIG CLD:LAN BKN 012-020/030HFT AGL MT ABV 035HFT 002HFT AGL",
    "SIG CLD:S OF N3800 BKN 012HFT AGL MT ABV 060HFT AMSL BKN 002HFT AGL",  # vazia (CLD)
]


@pytest.mark.parametrize("corpo", DUVIDA)
def test_na_duvida_como_na_7_0_com_aviso(eng, eng70, corpo):
    t = _g(corpo)
    assert _assin(eng.parse_gamet(t)[0]) == _assin(eng70.parse_gamet(t)[0])
    assert _decisoes(eng, t) == _decisoes(eng70, t)
    assert not any(getattr(b, "relevo", 0) for b in eng.parse_gamet(t)[0])
    r = eng.analisar_gamet(t, "manual")
    av = [md for _t, md in r["avisos"] if "o `MT ABV` não foi lido" in md]
    assert len(av) == 1, r["avisos"]
    assert "área da subentrada" in av[0]
    assert not any("Valor só junto ao relevo" in md for _t, md in r["avisos"])
    # Os outros avisos são os da 7.0
    assert [a for a in r["avisos"] if "o `MT ABV` não foi lido" not in a[1]] == \
        eng70.analisar_gamet(t, "manual")["avisos"]


def test_mt_abv_sem_valor_lido_avisa_campo_nao_interpretado(eng):
    t = _g("SFC VIS:LAN LCA 3000-5000M BR MT ABV 035HFT AMSL SN")
    assert [b.value for b in eng.parse_gamet(t)[0]] == [3000]
    assert eng.campos_nao_interpretados(t) == ["SFC VIS: MT ABV 035HFT AMSL SN"]


def test_mt_obsc_nao_muda(eng, eng70):
    for corpo in ("MT OBSC:N OF N4000 LAN", "MT OBSC:MT ABV 035HFT AMSL",
                  "SFC VIS:LAN 3000M BR MT OBSC:N OF N4100"):
        t = _g(corpo)
        assert _assin(eng.parse_gamet(t)[0]) == _assin(eng70.parse_gamet(t)[0]), corpo


# ------------------------------------------------------------ formas que mudam

def _parte_mt(eng, t):
    return [b for b in eng.parse_gamet(t)[0] if getattr(b, "relevo", 0)]


def test_lca_depois_do_mt_abv(eng):
    t = _g("SFC VIS:LAN 6000M BR MT ABV 035HFT AMSL LCA 0200-5000M SN")
    mt = _parte_mt(eng, t)
    assert [(b.value, b.qualifier) for b in mt] == [(200, "LCA")]
    d = _decisoes(eng, t)
    for k, (la, lo) in eng.AERODROMES.items():
        dentro = (eng._terrain_elevation_ft(lo, la) >= 3500
                  and eng.surface_polygon("LAN").contains(Point(lo, la)))
        assert d[k] == ("MARGINAL" if dentro else "GO"), k


def test_mais_permissivo_que_a_7_0_so_fora_do_relevo(eng, eng70):
    """Leitura literal aceite pelo Duarte (25-nov-2026): fora das quadrículas de
    montanha o valor do MT ABV não conta. A 7.0 dava NO-GO em toda a terra."""
    t = _g("SFC VIS:LAN 6000M MT ABV 035HFT AMSL 0200M")
    novo, velho = _decisoes(eng, t), _decisoes(eng70, t)
    lan = eng.surface_polygon("LAN")
    n_perm = 0
    for k, (la, lo) in eng.AERODROMES.items():
        if not lan.contains(Point(lo, la)):
            continue
        assert velho[k] == "NO-GO"
        if eng._terrain_elevation_ft(lo, la) >= 3500:
            assert novo[k] == "NO-GO", k
        else:
            assert novo[k] == "GO", k
            n_perm += 1
    assert n_perm > 10


def test_sig_cld_com_base(eng, eng70):
    """Noutro campo: a base depois do MT ABV só no relevo. O nível do MT ABV
    não é base de nuvem (a 7.0 lia "035HFT AMSL" como base de 3500 ft AMSL)."""
    t = _g("SIG CLD:LAN BKN 012-020/030HFT AGL MT ABV 035HFT AMSL BKN 002-005/010HFT AGL")
    blocos = eng.parse_gamet(t)[0]
    assert sorted((b.phenomenon, b.value, b.relevo) for b in blocos) == [
        ("BASE_AGL", 200, 3500), ("BASE_AGL", 1200, 0)]
    assert ("BASE_AMSL", 3500) in [(b.phenomenon, b.value) for b in eng70.parse_gamet(t)[0]]
    mt = next(b for b in blocos if b.relevo)
    esperada = _area_vis(eng, None, "LAN").intersection(_montanha(eng, 3500))
    assert mt.polygon.symmetric_difference(esperada).area < 1e-6
    d = _decisoes(eng, t)
    for k, (la, lo) in eng.AERODROMES.items():
        dentro = (eng._terrain_elevation_ft(lo, la) >= 3500
                  and eng.surface_polygon("LAN").contains(Point(lo, la)))
        assert d[k] == ("NO-GO" if dentro else "GO"), k
    assert eng.campos_nao_interpretados(t) == []


def test_sig_cld_sem_a_base_fantasma_da_7_0(eng, eng70):
    """Sem caso real: no SIG CLD a 7.0 lia o nível do MT ABV como base de 3500 ft
    AMSL (NO-GO nas quadrículas com MEF > 3000 ft). A 7.1 não o lê como base —
    aqui fica mais permissiva também no relevo (documentado no CLAUDE.md)."""
    t = _g("SIG CLD:LAN BKN 012HFT AGL MT ABV 035HFT AMSL BKN 020HFT AGL")
    novo, velho = _decisoes(eng, t), _decisoes(eng70, t)
    assert novo["Seia (LPSE)"] == "GO" and velho["Seia (LPSE)"] == "NO-GO"
    assert all(GRAV[novo[k]] <= GRAV[velho[k]] for k in novo)


def test_em_pes_e_outros_limiares(eng):
    for txt, lim in (("3500FT", 3500), ("045HFT", 4500), ("050HFT", 5000), ("060HFT", 6000)):
        t = _g(f"SFC VIS:LAN LCA 3000-5000M BR MT ABV {txt} AMSL 0200-5000M SN")
        mt = _parte_mt(eng, t)
        assert [b.relevo for b in mt] == [lim], txt
        esperada = _area_vis(eng, None, "LAN").intersection(_montanha(eng, lim))
        assert mt[0].polygon.symmetric_difference(esperada).area < 1e-6, txt


def test_area_da_subentrada_e_superficie(eng):
    t = _g("SFC VIS:N OF N4000 COT LCA 3000M BR MT ABV 040HFT AMSL 0400M FG")
    mt = _parte_mt(eng, t)
    esperada = (eng.FIR_POLYGON.intersection(box(-30, 40, 10, 60))
                .intersection(eng.surface_polygon("COT")).intersection(_montanha(eng, 4000)))
    assert len(mt) == 1 and mt[0].surface == "COT" and mt[0].qualifier == ""
    assert mt[0].polygon.symmetric_difference(esperada).area < 1e-6


def test_janela(eng):
    val = "250900/251500"
    t = _g("SFC VIS:09/12 LAN LCA 3000-5000M BR MT ABV 035HFT AMSL 0200-5000M SN", val)
    assert [(b.value, b.window, b.janela_ambigua) for b in _parte_mt(eng, t)] == [(200, "09–12Z", False)]
    # A janela da parte cortada por uma janela a meio da linha
    t = _g("SFC VIS:LAN 6000M BR 12/15 LAN LCA 3000M BR MT ABV 035HFT AMSL 0200M SN", val)
    assert [(b.value, b.window) for b in _parte_mt(eng, t)] == [(200, "12–15Z")]
    # Sem janela: todo o período; a linha seguinte com qualificador não herda
    t = _g("SFC VIS:LAN LCA 3000M BR MT ABV 035HFT AMSL 0200M SN N OF N4100 0800M FG", val)
    assert [(b.value, b.window) for b in _parte_mt(eng, t)] == [(200, "")]
    vis = sorted((b.value, b.relevo) for b in eng.parse_gamet(t)[0])
    assert vis == [(200, 3500), (800, 0), (3000, 0)]


def test_superficie_a_meio_da_linha_antes_do_mt(eng):
    """Com uma superfície a meio da linha (4.7.6), o MT ABV fica com a superfície
    da parte de onde vem."""
    t = _g("SIG CLD:LCA BKN 006-008/012HFT AGL MAR AND COT ISOL TCU/CB 020HFT AGL "
           "MT ABV 035HFT AMSL BKN 002HFT AGL")
    mt = [b for b in _parte_mt(eng, t) if b.phenomenon == "BASE_AGL"]
    assert [(b.value, b.surface) for b in mt] == [(200, "COT/MAR")]
    esperada = (eng.FIR_POLYGON.intersection(eng.surface_polygon("COT/MAR"))
                .intersection(_montanha(eng, 3500)))
    assert mt[0].polygon.buffer(1e-9).contains(esperada)


def test_seccao_ii_e_airmet_iguais_a_7_0(eng, eng70):
    t = (_g("SFC VIS:LAN 6000M BR")
         .replace(" SECN II ", " SECN II CLD:SCT ST 004-008/012HFT AGL MT ABV 035HFT AMSL "
                               "BKN ST 002HFT AGL "))
    assert eng.nuvens_baixas_secn2(t) == eng70.nuvens_baixas_secn2(t)
    assert eng.nuvens_baixas_secn2(t)[1]
    from datetime import datetime, timezone
    ref = datetime(2026, 11, 24, 17, 0, tzinfo=timezone.utc)
    a = ("LPPC AIRMET 5 VALID 241600/242000 LPPT- LPPC LISBOA FIR/MAINLAND AREA SFC VIS "
         "3000M BR MT ABV 035HFT AMSL 0200M SN OBS N OF N4000 STNR NC")
    rn, rv = eng.ler_airmet(a, ref), eng70.ler_airmet(a, ref)
    assert _assin(rn["blocos"]) == _assin(rv["blocos"])
    assert (rn["lido"], rn["descr"]) == (rv["lido"], rv["descr"])


# ------------------------------------------------- propriedade e linhas geradas

QUALS = ["", "N OF N4000", "S OF N3930", "E OF W00800", "N OF N3830 AND W OF W00800",
         "BTN N3800 AND N4100"]
SUPS = ["", "LAN", "COT", "MAR AND COT", "LAN"]
LIMS = ["030HFT", "035HFT", "045HFT", "050HFT", "3500FT", "060HFT", "070HFT"]
VIS = ["0200", "0800", "1200", "2000", "3000", "4000", "6000"]


def _corpo(rng):
    q, s = rng.choice(QUALS), rng.choice(SUPS)
    lca1 = rng.choice(["", "LCA "])
    lca2 = rng.choice(["", "", "LCA "])
    v1, v2 = rng.choice(VIS), rng.choice(VIS)
    lim = rng.choice(LIMS)
    corpo = "SFC VIS:" + " ".join(x for x in (q, s, f"{lca1}{v1}M BR") if x)
    return corpo, f" MT ABV {lim} AMSL {lca2}{v2}M SN"


def test_propriedade_nunca_mais_permissivo_no_relevo(eng, eng70):
    """Em linhas geradas: nas quadrículas com MEF ≥ limiar nunca mais permissivo
    do que a 7.0; fora delas, igual à 7.0 sem a parte do MT ABV (o valor não
    conta — leitura literal); em dúvida, igual à 7.0 em todo o lado."""
    rng = random.Random(71)
    pts = [("g", p) for p in GRELHA] + list(eng.AERODROMES.items())
    pts = [(f"{k}{i}", p) for i, (k, p) in enumerate(pts)
           if eng.FIR_POLYGON.contains(Point(p[1], p[0]))]
    n_ok = 0
    for _ in range(40):
        pre, mt = _corpo(rng)
        t, t_sem = _g(pre + mt), _g(pre)
        lim = int(re.search(r"ABV (\d+)", mt).group(1))
        lim = lim * 100 if "HFT" in mt else lim
        lido = [x for x in eng.leituras_relevo(t) if x[0] == "ok"]
        novo, velho = _decisoes(eng, t, pts), _decisoes(eng70, t, pts)
        sem = _decisoes(eng70, t_sem, pts) if lido else velho
        for k, (la, lo) in pts:
            if eng._terrain_elevation_ft(lo, la) >= lim:
                assert GRAV[novo[k]] >= GRAV[velho[k]], (t, k, novo[k], velho[k])
            else:
                assert novo[k] == sem[k], (t, k, novo[k], sem[k])
        n_ok += bool(lido)
    assert n_ok > 20


# ------------------------------------------------------------------- arquivo

# GAMETs do arquivo que a 7.1 lê de outra forma (a 25-nov-2026: os 4 com "MT
# ABV"). `conftest.mt_71` tira-os das comparações por igualdade com motores
# antigos; se aparecer outro, este teste falha de propósito: confirma a leitura
# e acrescenta-o aqui.
COM_MT = {G241500_F.name, G242100_F.name, G250300_F.name, G250900_F.name}


def _gamets():
    if not (DADOS / "gamets").exists():
        pytest.skip("sem dados/")
    return sorted((DADOS / "gamets").rglob("*.txt"))


def test_arquivo_conjunto_fixo(eng, eng70):
    diferentes, com_mt = set(), set()
    for p in _gamets():
        t = p.read_text(encoding="utf-8")
        if _assin(eng.parse_gamet(t)[0]) != _assin(eng70.parse_gamet(t)[0]):
            diferentes.add(p.name)
        if conftest.mt_71(t):
            com_mt.add(p.name)
        assert not [x for x in eng.leituras_relevo(t) if x[0] == "duvida"], p.name
    assert diferentes == COM_MT
    assert com_mt == COM_MT


def test_arquivo_manual_contra_7_0(eng, eng70):
    n = 0
    for p in _gamets():
        t = p.read_text(encoding="utf-8")
        pts = list(eng.AERODROMES.items()) + [(f"g{i}", q) for i, q in enumerate(GRELHA)
                                              if eng.FIR_POLYGON.contains(Point(q[1], q[0]))]
        dn, dv = _decisoes(eng, t, pts), _decisoes(eng70, t, pts)
        if p.name not in COM_MT:
            assert dn == dv, p.name
            assert eng.analisar_gamet(t, "manual")["avisos"] == \
                eng70.analisar_gamet(t, "manual")["avisos"], p.name
            assert eng.nuvens_baixas_secn2(t) == eng70.nuvens_baixas_secn2(t), p.name
        else:
            lido = [x for x in eng.leituras_relevo(t) if x[0] == "ok"]
            assert len(lido) == 1, p.name
            lim = lido[0][3]
            for k, (la, lo) in pts:
                if eng._terrain_elevation_ft(lo, la) >= lim:
                    assert GRAV[dn[k]] >= GRAV[dv[k]], (p.name, k)
                else:
                    assert dn[k] == dv[k], (p.name, k, dn[k], dv[k])
            assert eng.nuvens_baixas_secn2(t) == eng70.nuvens_baixas_secn2(t), p.name
        n += 1
    assert n > 150


def test_arquivo_hist_contra_7_0(eng, eng70):
    from datetime import timedelta
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        ini = eng._iso_utc(entrada.get("inicio"))
        if f.name not in COM_MT or not f.exists() or not ini:
            continue
        t = f.read_text(encoding="utf-8")
        agora = ini + timedelta(minutes=30)
        rn = eng.analisar_gamet(t, "arquivo_hist", indice=indice, entrada=entrada, agora=agora)
        rv = eng70.analisar_gamet(t, "arquivo_hist", indice=indice, entrada=entrada, agora=agora)
        lim = [x for x in eng.leituras_relevo(t) if x[0] == "ok"][0][3]
        for k, (la, lo) in eng.AERODROMES.items():
            a = (eng.find_region_for_point(rn["regioes"], la, lo) or {}).get("decision")
            b = (eng70.find_region_for_point(rv["regioes"], la, lo) or {}).get("decision")
            if eng._terrain_elevation_ft(lo, la) >= lim:
                assert GRAV[a] >= GRAV[b], (f.name, k)
            else:
                assert a == b, (f.name, k, a, b)
        n += 1
    assert n == len(COM_MT)
