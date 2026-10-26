"""
4.0 — Os AIRMETs entram na decisão (decisão do Duarte a 26-out-2026).

Até à 3.10 um AIRMET em vigor era só mostrado ("a app mostra-o mas não o
interpreta"). Caso real de 25-out-2026: o GAMET 251500/252100 só tinha
BKN 006 a N de N4100 e W de W00800 (GO em todo o lado), e às 18:10/18:40Z o
IPMA emitiu dois AIRMETs para o N de N3930 — base 200 ft na costa e VIS
200 m (FG/BR) em costa e terra. A app dava 100% GO.

Regras (acordadas com o Duarte):
1. Cada AIRMET gera os mesmos fenómenos do GAMET, avaliados pela `decision`
   existente (limiares inalterados). TCU sozinho não conta; MOD TURB/ICE
   são informativos.
2. Área: qualificadores do GAMET (com LAN/MAR/COT), WI polígono/círculo,
   SEM a margem de 10 NM do SIGMET; MOV legível estende; MOV ilegível,
   ENTIRE FIR ou área ilegível → toda a FIR, com aviso.
3. Fenómeno ilegível → MARGINAL na área do AIRMET, com aviso.
4. Fontes: ipma / arquivo_recurso (active_bulletins, CNL) e arquivo_hist
   (boletins_do_periodo). Texto colado à mão: nada muda.
5. Os motivos dizem de onde vem ("AIRMET 2 — VIS 200m < 1500m").
6. Nunca mais permissivo do que sem AIRMET.
"""
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from conftest import build_gamet

# --- Casos reais ----------------------------------------------------------

G251500 = (
    "LPPC GAMET VALID 251500/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SIG CLD:N OF N4100 AND W OF W00800 LCA BKN 006-008/012HFT AGL SIGMET APPLICABLE: AT "
    "TIME OF ISSUE NIL SECN II PSYS:18 NIL CLD:N OF N3830 SCT/BKN SC/CU 012-030/040HFT AGL "
    "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL "
    "290/015KT PS15 320/003KT PS15 350/005KT PS13 2000FT AGL 310/011KT PS13 340/007KT PS13 "
    "350/003KT PS13 5000FT AGL 310/021KT PS11 300/016KT PS14 310/013KT PS14 FL100 280/020KT "
    "PS06 300/019KT PS06 290/015KT PS06 FL150 300/030KT MS01 290/023KT PS00 290/021KT PS00 "
    "FZLVL: 14800FT AMSL 14900FT AMSL 14800FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 "
    "W00752 N3700 W00800 1000FT AGL 360/019KT PS17 340/013KT PS18 340/005KT PS20 2000FT AGL "
    "020/017KT PS17 350/012KT PS16 010/011KT PS18 5000FT AGL 020/009KT PS16 030/008KT PS16 "
    "050/009KT PS18 FL100 360/004KT PS08 360/008KT PS09 060/008KT PS08 FL150 280/010KT "
    "MS01 290/006KT MS01 350/008KT MS01 FZLVL: 14700FT AMSL 14300FT AMSL 14700FT AMSL MNM "
    "QNH:1022HPA=")
AIR1_25 = ("LPPC AIRMET 1 VALID 251810/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BKN CLD OBS "
           "N OF N3930 COT 002HFT AGL STNR NC")
AIR2_25 = ("LPPC AIRMET 2 VALID 251840/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA SFC VIS "
           "0200-5000M FG/BR OBS N OF N3930 COT AND LAN STNR NC")

# Pontos a N de N3930 em terra ou na faixa costeira (AIRMET 2)
COD_AIR2 = {"LPPR", "LPVR", "LPBG", "LPBR", "LPCB", "LPCH", "LPCO", "LPIN", "LPJF", "LPLZ",
            "LPMI", "LPMU", "LPPN", "LPSE", "LPVL", "LPVZ", "LP53", "LP55", "LP62", "LP64",
            "LP66", "LP69", "LP71", "LP76", "LP80"}
# Pontos a N de N3930 na faixa costeira (AIRMET 1, base 200 ft)
COD_AIR1 = {"LPPR", "LPIN", "LP62"}

G170900 = (
    "LPPC GAMET VALID 170900/171500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC "
    "VIS:09/11 N OF N3840 AND W OF W00850 COT AND LAN LCA 0400-5000M FG/BR E OF W00800 LAN "
    "LCA 3000-5000M RA SIGWX:E OF W00800 LAN ISOL/EMBD TS SIG CLD::09/11 N OF N3840 AND W OF "
    "W00850 COT AND LAN LCA BKN 004-008/010HFT AGL E OF W00800 LAN ISOL/EMBD TCU/CB "
    "025-035/XXXHFT AGL TURB:09/11 N OF N4100 LAN LCA MOD SFC/FL070 SIGMET APPLICABLE: AT "
    "TIME OF ISSUE NIL SECN II PSYS:12 NIL CLD:FEW/SCT SC/CU 015-030/045HFT AGL N OF N3900 "
    "LAN FEW/SCT AC/AS 060-090/100-130HFT AMSL MNM QNH:1015HPA=")
AIR1_17 = ("LPPC AIRMET 1 VALID 171000/171300 LPPT- LPPC LISBOA FIR/MAINLAND AREA MOD TURB OBS "
           "WI 10NM OF N3845 W00930 FL015 STNR WKN")


def _t(dia, h, m=0):
    return datetime(2026, 10, dia, h, m, tzinfo=timezone.utc)


def _cod(nome):
    return nome[nome.index("(") + 1:nome.index(")")]


def _decisoes(eng, r):
    return {_cod(n): (eng.find_region_for_point(r["regioes"], la, lo) or {}).get("decision")
            for n, (la, lo) in eng.AERODROMES.items()}


def _r(eng, gamet, boletins, agora, fonte="ipma"):
    return eng.analisar_gamet(gamet, fonte, boletins=boletins, boletins_at=agora, agora=agora)


def _motivos(r):
    return "; ".join(m for g in r["regioes"] for m in g["reasons"])


def _avisos(r, chave):
    return [x for t, x in r["avisos"] if chave in x]


# --- O caso real de 25-out-2026 -------------------------------------------

def test_real_18h_ainda_sem_airmet_tudo_go(eng):
    r = _r(eng, G251500, [AIR1_25, AIR2_25], _t(25, 18, 0))
    assert set(_decisoes(eng, r).values()) == {"GO"}
    assert r["airmets"] == []


def test_real_1830_so_airmet_1_base_200_na_costa(eng):
    r = _r(eng, G251500, [AIR1_25, AIR2_25], _t(25, 18, 30))
    dec = _decisoes(eng, r)
    nogo = {c for c, d in dec.items() if d == "NO-GO"}
    assert nogo == COD_AIR1, sorted(nogo)
    assert {d for c, d in dec.items() if c not in COD_AIR1} == {"GO"}
    assert "AIRMET 1 — BASE 200ft < 300ft" in _motivos(r)


def test_real_19h_os_dois_airmets_25_pontos_no_go(eng):
    r = _r(eng, G251500, [AIR1_25, AIR2_25], _t(25, 19, 0))
    dec = _decisoes(eng, r)
    nogo = {c for c, d in dec.items() if d == "NO-GO"}
    assert nogo == COD_AIR2, (sorted(nogo - COD_AIR2), sorted(COD_AIR2 - nogo))
    assert {d for c, d in dec.items() if c not in COD_AIR2} == {"GO"}
    mot = _motivos(r)
    assert "AIRMET 2 — VIS 200m < 1500m" in mot and "AIRMET 1 — BASE 200ft < 300ft" in mot
    # Porto: os dois AIRMETs nos motivos da região
    porto = eng.find_region_for_point(r["regioes"], *eng.AERODROMES["Porto (LPPR)"])
    assert any(m.startswith("AIRMET 1 —") for m in porto["reasons"])
    assert any(m.startswith("AIRMET 2 —") for m in porto["reasons"])
    assert porto["vis"] == 200 and porto["base"] == 200
    # Interior a N de N3930 só tem o AIRMET 2
    bg = eng.find_region_for_point(r["regioes"], *eng.AERODROMES["Bragança (LPBG)"])
    assert not any(m.startswith("AIRMET 1") for m in bg["reasons"])
    # A faixa do SIGMET não muda: não há SIGMET
    assert r["faixa_sig"] == ("NIL", "GO")


def test_real_19h_aviso_lista_o_efeito_de_cada_airmet(eng):
    r = _r(eng, G251500, [AIR1_25, AIR2_25], _t(25, 19, 0))
    (aviso,) = _avisos(r, "2 AIRMET")
    assert "não o interpreta" not in aviso
    assert "AIRMET 1" in aviso and "AIRMET 2" in aviso
    assert "VIS 200 m" in aviso and "FG/BR" in aviso and "base 200 ft AGL" in aviso
    assert "NO-GO" in aviso
    assert "N OF N3930" in aviso
    assert not _avisos(r, "AIRMET não interpretado")
    assert not _avisos(r, "Área do AIRMET não reconhecida")


def test_real_2105_tudo_expirado_tudo_go(eng):
    r = _r(eng, G251500, [AIR1_25, AIR2_25], _t(25, 21, 5))
    assert set(_decisoes(eng, r).values()) == {"GO"}
    assert r["airmets"] == []


def test_real_arquivo_hist_conta_os_airmets_do_periodo(eng):
    FMT = "%Y-%m-%dT%H:%MZ"
    entrada = {"ficheiro": "g.txt", "inicio": _t(25, 15).strftime(FMT),
               "fim": _t(25, 21).strftime(FMT)}
    indice = {"gamets": [entrada], "sigmets": [
        {"texto": AIR1_25, "inicio": _t(25, 18, 10).strftime(FMT), "fim": _t(25, 21).strftime(FMT)},
        {"texto": AIR2_25, "inicio": _t(25, 18, 40).strftime(FMT), "fim": _t(25, 21).strftime(FMT)},
    ]}
    r = eng.analisar_gamet(G251500, "arquivo_hist", indice=indice, entrada=entrada,
                           agora=_t(25, 15))
    nogo = {c for c, d in _decisoes(eng, r).items() if d == "NO-GO"}
    assert nogo == COD_AIR2


def test_real_arquivo_recurso_igual_ao_ipma(eng):
    r = eng.analisar_gamet(G251500, "arquivo_recurso", boletins=[AIR1_25, AIR2_25],
                           boletins_at=_t(25, 19), boletins_fonte="arquivo", agora=_t(25, 19))
    assert {c for c, d in _decisoes(eng, r).items() if d == "NO-GO"} == COD_AIR2


def test_colado_a_mao_nada_muda(eng):
    r = eng.analisar_gamet(G251500, "manual", boletins=[AIR1_25, AIR2_25], agora=_t(25, 19))
    assert set(_decisoes(eng, r).values()) == {"GO"}
    assert "AIRMET" not in _motivos(r)


def test_airmet_cancelado_nao_conta(eng):
    cnl = ("LPPC AIRMET 3 VALID 251850/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA "
           "CNL AIRMET 2 251840/252100")
    r = _r(eng, G251500, [AIR1_25, AIR2_25, cnl], _t(25, 19, 0))
    nogo = {c for c, d in _decisoes(eng, r).items() if d == "NO-GO"}
    assert nogo == COD_AIR1
    assert "AIRMET 2" not in _motivos(r)


def test_real_17_out_mod_turb_nao_muda_decisoes(eng):
    agora = _t(17, 11)
    sem = _r(eng, G170900, [], agora)
    com = _r(eng, G170900, [AIR1_17], agora)
    assert _decisoes(eng, com) == _decisoes(eng, sem)
    (aviso,) = _avisos(com, "1 AIRMET")
    assert "informativo" in aviso and "TURB MOD" in aviso
    assert not _avisos(com, "AIRMET não interpretado")
    # A TURB MOD aparece na região de Lisboa (círculo de 10 NM, sem margem)
    lis = eng.find_region_for_point(com["regioes"], 38.75, -9.5)
    assert "MOD" in lis["turb"]


# --- Fenómenos (regra 1) ---------------------------------------------------

AGORA = _t(20, 18)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="201500/202100")
NORTE, SUL = (41.3, -7.5), (37.3, -8.0)          # interior N de N4000 / Algarve


def _a(corpo, n="5", val="201700/202100"):
    return f"LPPC AIRMET {n} VALID {val} LPPT- LPPC LISBOA FIR/MAINLAND AREA {corpo}"


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


@pytest.mark.parametrize("fen, esperado", [
    ("SFC VIS 0800M BR", "NO-GO"),
    ("SFC VIS 1,2KM BR", "NO-GO"),
    ("SFC VIS 2000M BR", "MARGINAL"),
    ("SFC VIS 4000M BR", "GO"),
    ("SFC VIS LCA 0800M BR", "MARGINAL"),
    ("ISOL TS", "MARGINAL"),
    ("OCNL TS", "NO-GO"),
    ("ISOL TSGR", "MARGINAL"),
    ("OCNL TSGR", "NO-GO"),
    ("ISOL CB", "MARGINAL"),
    ("OCNL CB", "NO-GO"),
    ("FRQ CB", "NO-GO"),
    ("ISOL TCU", "GO"),
    ("OCNL TCU", "GO"),
    ("MOD TURB", "GO"),
    ("MOD ICE", "GO"),
    ("MOD MTW", "MARGINAL"),
    ("MT OBSC", "NO-GO"),
    ("SFC WIND 250/35KT", "NO-GO"),
    ("SFC WIND 250/25KT", "GO"),
    ("SFC WSPD 35KT", "NO-GO"),
])
def test_fenomeno_antes_da_area(eng, fen, esperado):
    r = _r(eng, CALMO, [_a(f"{fen} OBS N OF N4000 STNR NC")], AGORA)
    assert _dec(eng, r, *NORTE) == esperado, _motivos(r)
    assert _dec(eng, r, *SUL) == "GO"
    assert not _avisos(r, "AIRMET não interpretado")
    assert not _avisos(r, "Área do AIRMET não reconhecida")


@pytest.mark.parametrize("fen, valor, esperado", [
    ("BKN CLD", "002HFT AGL", "NO-GO"),
    ("OVC CLD", "004HFT AGL", "MARGINAL"),
    ("BKN CLD", "004/010HFT AGL", "MARGINAL"),
    ("BKN CLD", "002-004/010HFT", "NO-GO"),        # sem referência = AGL
    ("OVC CLD", "006/015HFT AGL", "GO"),
    ("BKN CLD", "400/3000FT", "MARGINAL"),          # forma do Anexo 3
    ("BKN CLD", "060/300M", "NO-GO"),               # Anexo 3 em metros: 60 m ≈ 196 ft
    ("BKN CLD", "120/900M", "MARGINAL"),            # 120 m ≈ 393 ft
])
def test_nuvem_com_a_base_depois_da_area(eng, fen, valor, esperado):
    r = _r(eng, CALMO, [_a(f"{fen} OBS N OF N4000 {valor} STNR NC")], AGORA)
    assert _dec(eng, r, *NORTE) == esperado, _motivos(r)
    assert _dec(eng, r, *SUL) == "GO"


def test_base_amsl_contra_o_relevo(eng):
    # 3000 ft AMSL: no Marão/Estrela (MEF > 3300) fica < 300 ft AGL → NO-GO;
    # no litoral (MEF baixo) fica acima de 500 ft AGL → GO.
    r = _r(eng, CALMO, [_a("BKN CLD OBS N OF N4000 030HFT AMSL STNR NC")], AGORA)
    assert _dec(eng, r, 41.3, -7.8) == "NO-GO"
    assert _dec(eng, r, *SUL) == "GO"


def test_lca_no_texto_da_nuvem(eng):
    r = _r(eng, CALMO, [_a("BKN CLD OBS N OF N4000 LCA 002HFT AGL STNR NC")], AGORA)
    assert _dec(eng, r, *NORTE) == "NO-GO"     # base: LCA não alivia (como no GAMET)


# --- Área (regra 2) --------------------------------------------------------

POLI = "WI N3900 W00930 - N3900 W00900 - N3930 W00900 - N3930 W00930 - N3900 W00930"


def test_wi_poligono_sem_margem(eng):
    r = _r(eng, CALMO, [_a(f"SFC VIS 0500M FG OBS {POLI} STNR NC")], AGORA)
    assert _dec(eng, r, 39.25, -9.2) == "NO-GO"
    # 6 NM a leste do bordo W00900: no SIGMET ficava dentro da margem de 10 NM
    k = math.cos(math.radians(39.25))
    assert _dec(eng, r, 39.25, -9.0 + 6 / 60 / k) == "GO"
    assert _dec(eng, r, *NORTE) == "GO"


def test_wi_circulo(eng):
    r = _r(eng, CALMO, [_a("MT OBSC OBS WI 20NM OF N4100 W00800 STNR NC")], AGORA)
    assert _dec(eng, r, 41.0, -8.0) == "NO-GO"
    assert _dec(eng, r, 41.0, -8.0 + 30 / 60 / math.cos(math.radians(41))) == "GO"


def test_mov_estende_e_stnr_nao(eng):
    pequeno = "SFC VIS 0500M FG OBS WI N3900 W00930 - N3900 W00915 - N3915 W00915 - N3915 W00930"
    parado = _r(eng, CALMO, [_a(pequeno + " STNR NC")], AGORA)
    movel = _r(eng, CALMO, [_a(pequeno + " MOV E 20KT NC")], AGORA)   # 4 h × 20 kt
    ponto = (39.12, -8.2)
    assert _dec(eng, parado, *ponto) == "GO"
    assert _dec(eng, movel, *ponto) == "NO-GO"


@pytest.mark.parametrize("corpo", [
    "SFC VIS 0800M BR OBS N OF N4000 MOV E NC",              # MOV sem velocidade
    "SFC VIS 0800M BR OBS NW OF W00800 STNR NC",             # diagonal
    "SFC VIS 0800M BR OBS N OF LINE N3800 W01000 - N4000 W00700 STNR NC",
    "SFC VIS 0800M BR OBS STNR NC",                          # sem área
    "SFC VIS 0800M BR OBS WI N39 W07 - N40 W08 STNR NC",     # polígono ilegível
])
def test_area_ilegivel_toda_a_fir_com_aviso(eng, corpo):
    r = _r(eng, CALMO, [_a(corpo)], AGORA)
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    (aviso,) = _avisos(r, "Área do AIRMET não reconhecida")
    assert "toda a FIR" in aviso


def test_entire_fir_toda_a_fir(eng):
    r = _r(eng, CALMO, [_a("MOD MTW OBS ENTIRE FIR STNR NC")], AGORA)
    assert {g["decision"] for g in r["regioes"]} == {"MARGINAL"}
    (aviso,) = _avisos(r, "1 AIRMET")
    assert "toda a FIR" in aviso


def test_superficie_mar_nao_afecta_terra(eng):
    r = _r(eng, CALMO, [_a("SFC VIS 0500M FG OBS N OF N4000 MAR STNR NC")], AGORA)
    assert _dec(eng, r, *NORTE) == "GO"
    assert _dec(eng, r, 41.0, -9.0) == "NO-GO"         # mar dentro da FIR


def test_area_fora_da_fir_nao_conta_e_diz(eng):
    r = _r(eng, CALMO, [_a("SFC VIS 0500M FG OBS N OF N4300 STNR NC")], AGORA)
    assert {g["decision"] for g in r["regioes"]} == {"GO"}
    (aviso,) = _avisos(r, "1 AIRMET")
    assert "fora da área" in aviso
    assert not _avisos(r, "AIRMET não interpretado")


# --- Fenómeno ilegível (regra 3) -------------------------------------------

@pytest.mark.parametrize("corpo", [
    "XYZ OBS N OF N4000 STNR NC",
    "BKN CLD OBS N OF N4000 STNR NC",       # nuvem sem base legível
    "SFC VIS OBS N OF N4000 STNR NC",       # VIS sem valor
    "TURB OBS N OF N4000 STNR NC",          # sem intensidade
])
def test_fenomeno_ilegivel_marginal_na_area_com_aviso(eng, corpo):
    r = _r(eng, CALMO, [_a(corpo, n="7")], AGORA)
    assert _dec(eng, r, *NORTE) == "MARGINAL"
    assert _dec(eng, r, *SUL) == "GO"
    (aviso,) = _avisos(r, "AIRMET não interpretado")
    assert "MARGINAL" in aviso and corpo.split(" OBS")[0] in aviso
    assert "AIRMET 7 não interpretado" in _motivos(r)


def test_fenomeno_e_area_ilegiveis_marginal_em_toda_a_fir(eng):
    r = _r(eng, CALMO, [_a("XYZ OBS NW OF W00800 STNR NC")], AGORA)
    assert {g["decision"] for g in r["regioes"]} == {"MARGINAL"}
    assert _avisos(r, "AIRMET não interpretado")
    assert _avisos(r, "Área do AIRMET não reconhecida")


def test_ilegivel_nunca_alivia_um_no_go(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4000 0800M FG", validity="201500/202100")
    r = _r(eng, g, [_a("XYZ OBS N OF N4000 STNR NC")], AGORA)
    assert _dec(eng, r, *NORTE) == "NO-GO"


def test_decision_tipo_airmet_so_marginal(eng):
    assert eng.decision([("AIRMET", "7", "", "")])[0] == "MARGINAL"
    assert eng.decision([("AIRMET", "7", "", ""), ("VIS", 800, "", "")])[0] == "NO-GO"


# --- Nunca mais permissivo (regra 6) --------------------------------------

GAMETS_BASE = [
    G251500,
    G170900,
    CALMO,
    build_gamet("SECN I SFC VIS: N OF N4000 0800M FG SIGWX: S OF N3800 ISOL TS", validity="201500/202100"),
    build_gamet("SECN I SIG CLD: LCA BKN 002/010HFT AGL MT OBSC: N OF N4100", validity="201500/202100"),
    build_gamet("SECN I SFC VIS: LCA 1000M BR TURB: MOD SFC/FL050", validity="201500/202100"),
]
AIRMETS_VAR = [
    "SFC VIS 0800M BR OBS N OF N4000 STNR NC",
    "SFC VIS 2500M BR OBS S OF N3900 LAN STNR NC",
    "SFC VIS LCA 1000M BR OBS N OF N3800 COT STNR NC",
    "BKN CLD OBS N OF N3930 COT 002HFT AGL STNR NC",
    "OVC CLD OBS E OF W00800 040HFT AMSL STNR NC",
    "ISOL TS OBS BTN N3800 AND N4000 STNR NC",
    "ISOL CB OBS W OF W00830 STNR NC",
    "ISOL TCU OBS N OF N3900 STNR NC",
    "MOD TURB OBS WI 10NM OF N3845 W00930 FL015 STNR WKN",
    "MOD ICE OBS N OF N4000 FL050/FL100 STNR NC",
    "MOD MTW OBS N OF N4100 FL080 STNR NC",
    "XYZ OBS N OF N4000 STNR NC",
    "SFC VIS 0500M FG OBS " + POLI + " MOV NE 10KT NC",
]
PONTOS = [(la, lo) for la, lo in
          [(36.95 + 0.4 * i, -9.5 + 0.4 * j) for i in range(13) for j in range(8)]]


def test_nunca_mais_permissivo(eng):
    grav = {"GO": 0, "MARGINAL": 1, "NO-GO": 2, None: -1}
    agora = _t(20, 18)
    for g in GAMETS_BASE:
        ref = eng.parse_validity(g, agora)[0] or agora
        ref = ref + timedelta(hours=1)
        val = f"{ref - timedelta(hours=1):%d%H%M}/{ref + timedelta(hours=2):%d%H%M}"
        sem = _r(eng, g, [], ref)
        pts = list(eng.AERODROMES.values()) + PONTOS
        base = [_dec(eng, sem, la, lo) for la, lo in pts]
        for i, corpo in enumerate(AIRMETS_VAR):
            com = _r(eng, g, [_a(corpo, n=str(i + 1), val=val)], ref)
            for (la, lo), d0 in zip(pts, base):
                d1 = _dec(eng, com, la, lo)
                assert grav[d1] >= grav[d0], (g[:40], corpo, la, lo, d0, d1)
        todos = _r(eng, g, [_a(c, n=str(i + 1), val=val) for i, c in enumerate(AIRMETS_VAR)], ref)
        for (la, lo), d0 in zip(pts, base):
            assert grav[_dec(eng, todos, la, lo)] >= grav[d0]


def test_regioes_concordam_com_os_fenomenos(eng):
    """Oráculo: em cada aeródromo, a decisão da região = decision() sobre os
    blocos (GAMET + AIRMET, só AGL) que contêm o ponto."""
    from shapely.geometry import Point
    g = build_gamet("SECN I SFC VIS: N OF N4000 2000M BR SIGWX: S OF N3800 ISOL TS",
                    validity="201500/202100")
    airs = [_a(c, n=str(i + 1)) for i, c in enumerate([
        "SFC VIS 0800M BR OBS N OF N4030 STNR NC",
        "BKN CLD OBS N OF N3930 COT 004HFT AGL STNR NC",
        "OCNL CB OBS S OF N3730 STNR NC",
        "MOD MTW OBS E OF W00800 STNR NC",
        "XYZ OBS BTN N3830 AND N3900 STNR NC"])]
    r = _r(eng, g, airs, AGORA)
    blocos, *_ = eng.parse_gamet(g)
    ablocos, _ = eng.blocos_airmet(airs, AGORA)
    for nome, (la, lo) in eng.AERODROMES.items():
        p = Point(lo, la)
        ev = [("BASE" if b.phenomenon == "BASE_AGL" else b.phenomenon, b.value, b.qualifier, b.layer)
              for b in blocos + ablocos if b.polygon.buffer(-1e-6).contains(p)]
        if any(b.polygon.boundary.distance(p) < 2e-3 for b in blocos + ablocos):
            continue                                    # ponto em cima de uma fronteira
        assert _dec(eng, r, la, lo) == eng.decision(ev)[0], nome


# --- As duas interfaces ----------------------------------------------------

def test_app_streamlit_mostra_o_aviso_novo(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    gamet = build_gamet("SECN I SFC VIS:N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    air = _a("SFC VIS 0200-5000M FG/BR OBS N OF N3930 COT AND LAN STNR NC", n="2",
             val=f"{agora - timedelta(hours=1):%d%H%M}/{agora + timedelta(hours=2):%d%H%M}")
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = gamet
    at.session_state["_active_gamet_text"] = gamet
    at.session_state["ipma_boletins"] = [air]
    at.session_state["ipma_boletins_at"] = agora
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    avisos = [w.value for w in at.warning if "AIRMET" in w.value]
    assert avisos and "não o interpreta" not in " ".join(avisos)
    assert any("VIS 200 m" in a and "NO-GO" in a for a in avisos), avisos


def test_nicegui_mostra_o_aviso_novo():
    pytest.importorskip("nicegui")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nicegui_app"))
    import main as ng
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    gamet = build_gamet("SECN I SFC VIS:N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    air = _a("SFC VIS 0200-5000M FG/BR OBS N OF N3930 COT AND LAN STNR NC", n="2",
             val=f"{agora - timedelta(hours=1):%d%H%M}/{agora + timedelta(hours=2):%d%H%M}")
    r = ng.analisar(gamet, "ipma", [air], agora, "página do IPMA")
    assert any("AIRMET 2" in x and "VIS 200 m" in x for t, x in r["avisos"])
    porto = M_dec = None
    for g in r["regioes"]:
        if any(m.startswith("AIRMET 2 —") for m in g["reasons"]):
            porto = g
    assert porto is not None and porto["decision"] == "NO-GO"
