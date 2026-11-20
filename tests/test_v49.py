"""
4.9 — CB/TCU colado a outra nuvem em SIG CLD vale para toda a FIR (decisão do
Duarte a 15-nov-2026; mudança de leitura, não de limiares).

GAMET real 141500/142100 de 14-nov-2026
(dados/gamets/2026/11/20261114T1449Z_141500-142100_0b0ae4c2af.txt):

    SIG CLD:N OF N4000 LCA BKN 008-010/012HFT AGL
            18/21 N OF N3945 AND E OF W00830 LCA BKN 002-008/010HFT AGL
                  ISOL TCU/CB 018-030/XXXHFT AGL

Até à 4.8.1 o "ISOL TCU/CB" herdava a área (N de N3945 e E de W00830) e a
janela 18/21 da subentrada do BKN 002: 38 dos 52 pontos ficavam GO. O Anexo 3
da OACI (Tabela A5-3, Nota 3) pede que a localização dos CB/TCU seja dada além
das áreas de nuvem BKN/OVC, e o IPMA cola sistematicamente o CB à última linha
de nuvem baixa (121500, 122100, 130300, 130900, 140300, 140900, 141500). Desde
a 4.9 um grupo de CB/TCU sem qualificador próprio imediatamente antes, depois
de outro conteúdo de nuvem numa subentrada com área, vale em toda a FIR e em
todo o período (janela_ambigua). Os outros blocos ficam iguais; a Secção II e
o AIRMET sintético não mudam. Verificado contra o motor da 4.8.1
(`tests/referencia/app_4_8_1.py`, cópia fixa do app.py do main 26cec97; não
editar). Semente: GAMET_SEMENTE (por omissão 49); GAMET_CASOS (por omissão 300).
"""
import json
import os
import random
import re
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from shapely.geometry import Point

import conftest
from conftest import build_gamet

REF481 = Path(__file__).resolve().parent / "referencia" / "app_4_8_1.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
G141500_F = DADOS / "gamets/2026/11/20261114T1449Z_141500-142100_0b0ae4c2af.txt"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2, None: -1}
VAL = "141500/142100"

# O GAMET real, tal como foi recolhido (cópia, para correr sem `dados/`)
G141500 = (
    "LPPC GAMET VALID 141500/142100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:N OF N4000 LCA 3000-5000M RA 18/21 N OF N3945 AND E OF W00830 LCA 0800-5000M "
    "FG/BR SIG CLD:N OF N4000 LCA BKN 008-010/012HFT AGL 18/21 N OF N3945 AND E OF W00830 "
    "LCA BKN 002-008/010HFT AGL ISOL TCU/CB 018-030/XXXHFT AGL SIGMET APPLICABLE: AT TIME "
    "OF ISSUE NIL SECN II PSYS:18 N4940 W01650 L 992HPA STNR NC CLD:N OF N3945 SCT/BKN "
    "SC/CU 012-030/040HFT AGL S OF N3945 FEW/SCT SC/CU 012-030/040HFT AGL FEW/SCT AS/AC "
    "060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 "
    "W00750 1000FT AGL 260/021KT PS09 230/014KT PS13 250/012KT PS10 2000FT AGL 270/022KT "
    "PS07 250/018KT PS11 260/017KT PS08 5000FT AGL 270/027KT PS01 270/022KT PS06 270/025KT "
    "PS03 FL100 270/031KT MS03 270/028KT MS02 280/033KT MS01 FL150 280/032KT MS12 "
    "290/039KT MS11 290/038KT MS11 FZLVL: 8300FT AMSL 8500FT AMSL 8900FT AMSL LISBOA EVORA "
    "FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 290/016KT PS15 270/017KT PS14 "
    "290/016KT PS16 2000FT AGL 290/017KT PS12 280/018KT PS12 290/016KT PS13 5000FT AGL "
    "270/020KT PS07 280/019KT PS07 280/016KT PS08 FL100 290/022KT PS00 290/025KT PS01 "
    "300/022KT PS01 FL150 300/038KT MS09 300/041KT MS09 300/036KT MS08 FZLVL: 9800FT AMSL "
    "10300FT AMSL 10500FT AMSL MNM QNH:1015HPA=")

# Os 14 pontos NO-GO da 4.8.1 (N de N3945 e E de W00830: BASE 200, VIS LCA 800, CB)
NOGO_141500 = {"LPVR", "LPBG", "LPBR", "LPCB", "LPCH", "LPCO", "LPLZ", "LPMI", "LPMU",
               "LPSE", "LPVZ", "LP53", "LP66", "LP76"}
# (5.0) Pontos a N de N4000 com a base LCA 800 ft (< 1000 ft → MARGINAL)
BASE800_141500 = {"LPPR", "LPIN", "LPVL", "LP55", "LP62"}

GRELHA = [(36.95 + 0.3 * i, -9.55 + 0.3 * j) for i in range(18) for j in range(12)]


@pytest.fixture(scope="module")
def eng481(eng):
    mod = types.ModuleType("motor_4_8_1")
    mod.__dict__["__file__"] = str(REF481)
    exec(compile(conftest._extract_engine_ref(REF481.read_text(encoding="utf-8")), str(REF481),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_8_1(eng, eng481):
    assert eng481.APP_VERSION == "4.8.1"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 9)


def test_copia_do_gamet_real_igual_ao_arquivo():
    if not G141500_F.exists():
        pytest.skip("sem dados/")
    assert " ".join(G141500_F.read_text(encoding="utf-8").split()) == G141500


def _g(corpo, secn2="", validade=VAL):
    t = build_gamet(f"SECN I {corpo}", validity=validade)
    if secn2:
        t = t.replace(" SECN II ", f" SECN II CLD:{secn2} ")
    return t


def _icao(nome):
    return nome.split("(")[-1].rstrip(")")


def _pontos(eng, grelha=False):
    p = list(eng.AERODROMES.items())
    if grelha:
        p += [(f"grelha {la:.2f} {lo:.2f}", (la, lo)) for la, lo in GRELHA
              if eng.FIR_POLYGON.contains(Point(lo, la))]
    return p


def _regioes(e, texto):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    return regioes


def _decisoes(e, texto, pontos=None):
    regioes = _regioes(e, texto)
    pontos = pontos if pontos is not None else list(e.AERODROMES.items())
    return {k: (e.find_region_for_point(regioes, la, lo) or {}).get("decision")
            for k, (la, lo) in pontos}


def _motivos(e, texto):
    regioes = _regioes(e, texto)
    return {_icao(k): (e.find_region_for_point(regioes, la, lo) or {}).get("reasons")
            for k, (la, lo) in e.AERODROMES.items()}


def _assin(blocos):
    return sorted((b.phenomenon, str(b.value), b.qualifier, b.surface, b.window,
                   b.janela_ambigua, round(b.polygon.area, 9)) for b in blocos)


def _toda_fir(e, p):
    return p.buffer(1e-9).contains(e.FIR_POLYGON)


# ------------------------------------------------------------- GAMET real 141500

def test_141500_cb_em_toda_a_fir_e_todo_o_periodo(eng):
    blocos, *_ = eng.parse_gamet(G141500)
    (cb,) = [b for b in blocos if b.phenomenon == "CB"]
    assert cb.value == "ISOL"
    assert _toda_fir(eng, cb.polygon)
    assert cb.window == "" and cb.janela_ambigua and cb.surface == ""
    # A base do próprio CB (1800 ft) acompanha-o (leitura conservadora)
    (b18,) = [b for b in blocos if b.phenomenon == "BASE_AGL" and b.value == 1800]
    assert _toda_fir(eng, b18.polygon) and b18.window == "" and b18.janela_ambigua


def test_141500_outros_blocos_iguais_a_4_8_1(eng, eng481):
    novo = [b for b in eng.parse_gamet(G141500)[0]
            if b.phenomenon != "CB" and not (b.phenomenon == "BASE_AGL" and b.value == 1800)]
    velho = [b for b in eng481.parse_gamet(G141500)[0]
             if b.phenomenon != "CB" and not (b.phenomenon == "BASE_AGL" and b.value == 1800)]
    assert _assin(novo) == _assin(velho)
    # O BKN 002 continua só a N de N3945 e E de W00830, das 18 às 21Z
    (b2,) = [b for b in novo if b.phenomenon == "BASE_AGL" and b.value == 200]
    assert b2.window == "18–21Z" and not _toda_fir(eng, b2.polygon)


def test_141500_decisoes(eng, eng481):
    novo = {_icao(k): v for k, v in _decisoes(eng, G141500).items()}
    velho = {_icao(k): v for k, v in _decisoes(eng481, G141500).items()}
    assert {k for k, v in velho.items() if v == "NO-GO"} == NOGO_141500
    # (5.0) A 4.8.1 é lida com os limiares da 5.0 (conftest._limiares_5_0): a
    # base LCA 800 ft a N de N4000 dá MARGINAL nestes 5 pontos (até à 4.9 GO).
    assert {k for k, v in velho.items() if v == "MARGINAL"} == BASE800_141500
    assert {k for k, v in velho.items() if v == "GO"} == \
        set(velho) - NOGO_141500 - BASE800_141500
    assert len(velho) - len(NOGO_141500) == 38
    # Os 38 pontos GO passam a MARGINAL por "CB ISOL"; os 14 NO-GO ficam
    assert {k for k, v in novo.items() if v == "NO-GO"} == NOGO_141500
    assert {k for k, v in novo.items() if v == "MARGINAL"} == set(novo) - NOGO_141500
    mn, mv = _motivos(eng, G141500), _motivos(eng481, G141500)
    for k in set(novo) - NOGO_141500 - BASE800_141500:
        assert mn[k] == ["CB ISOL (cumulonimbos)"], (k, mn[k])
    for k in BASE800_141500:
        assert mn[k] == ["BASE 800ft < 1000ft", "CB ISOL (cumulonimbos)",
                         "VIS (LCA) 3000m < 5000m"], (k, mn[k])
    for k in NOGO_141500:
        assert mn[k] == mv[k], k


def test_141500_analise_completa(eng):
    agora = datetime(2026, 11, 14, 16, 0, tzinfo=timezone.utc)
    r = eng.analisar_gamet(G141500, agora=agora)
    assert set(r["por_dec"]) <= {"MARGINAL", "NO-GO"}
    assert not any("Campo não interpretado" in a[1] or "Área não reconhecida" in a[1]
                   for a in r["avisos"])


# ------------------------------------------------------- casos que não mudam

IGUAIS = [
    # Qualificador próprio imediatamente antes do CB
    "SIG CLD:N OF N4000 ISOL TCU/CB 018-030/XXXHFT AGL",
    "SIG CLD:S OF N3800 LCA BKN 004HFT AGL N OF N4000 ISOL TCU/CB 018-030/XXXHFT AGL",
    "SIG CLD:N OF N4000 LCA ISOL TCU/CB 018-030/XXXHFT AGL",
    "SIG CLD:N OF N4000 18/21 ISOL TCU/CB 018-030/XXXHFT AGL",
    "SIG CLD:S OF N3800 LCA BKN 004HFT AGL 18/21 N OF N4000 ISOL TCU/CB 018-030/XXXHFT AGL",
    # 142100 de 14-nov
    "SIG CLD:N OF N4000 AND W OF W00830 LCA BKN 008-010/012HFT AGL N OF N3900 AND E OF "
    "W00830 LCA BKN 002-008/010HFT AGL 21/24 N OF N4000 ISOL TCU/CB 018-030/XXXHFT AGL",
    # 061500 de 6-nov
    "SIG CLD:N OF N3800 LCA BKN 004-008/010HFT AGL BTN N4030 - N3800 MAR AND COT ISOL "
    "TCU/CB 018-035/XXXHFT AGL",
    # 081500 de 8-nov (superfície a meio da linha, 4.7.6)
    "SIG CLD:LCA BKN 006-008/012HFT AGL MAR AND COT ISOL/EMBD TCU/CB 020-035/XXXHFT AGL",
    # 080900 de 8-nov
    "SIG CLD:S OF N4115 LCA BKN 006-008/012HFT AGL S OF N4000 MAR ISOL TCU/CB "
    "020-035/XXXHFT AGL",
    # 060900 de 6-nov
    "SIG CLD:N OF N3830 LCA BKN 004-008/012HFT AGL W OF W00930 ISOL/EMBD CB/TCU "
    "020/XXXHFT AGL",
    # CB a abrir o campo, ou campo sem área (já é toda a FIR)
    "SIG CLD:ISOL TCU/CB 016-025/XXXHFT AGL",
    "SIG CLD:LCA BKN 002-008/012HFT AGL ISOL/EMBD TCU/CB 016-025/XXXHFT AGL",
    "SIG CLD:18/21 LCA BKN 002HFT AGL ISOL TCU/CB 018HFT AGL",
    # Sem CB
    "SIG CLD:N OF N4000 LCA BKN 002-008/010HFT AGL ISOL TCU 018-030/XXXHFT AGL",
    # SIGWX: só SIG CLD muda
    "SIGWX:N OF N4000 FZRA ISOL TS",
    "SIGWX:N OF N4000 SEV SQL ISOL CB",
    # Qualificador próprio numa linha nova (texto colado com quebras)
    "SIG CLD:N OF N4000\nISOL TCU/CB 018-030/XXXHFT AGL",
]


@pytest.mark.parametrize("corpo", IGUAIS)
def test_casos_iguais_a_4_8_1(eng, eng481, corpo):
    t = _g(corpo)
    assert _assin(eng.parse_gamet(t)[0]) == _assin(eng481.parse_gamet(t)[0])
    assert _decisoes(eng, t, _pontos(eng, True)) == _decisoes(eng481, t, _pontos(eng, True))


# ------------------------------------------------------------ casos que mudam

MUDAM = [
    # 121500/122100 de 12-nov
    ("SIG CLD:N OF N3930 LAN LCA BKN 002-004/010HFT AGL ISOL TCU/CB 016-025/XXXHFT AGL",
     "ISOL"),
    # 100300 de 10-nov: só superfície
    ("SIG CLD:LAN AND COT LCA BKN 002-008/012HFT AGL ISOL/EMBD TCU/CB 016-025/XXXHFT AGL",
     "ISOL_EMBD"),
    # 140900 de 14-nov: com janela
    ("SIG CLD:09/11 N OF N3800 LAN LCA BKN 002-006/010HFT AGL ISOL TCU/CB 015-025/XXXHFT AGL",
     "ISOL"),
    # CB/TCU, OCNL, FRQ, EMBD, sem qualificador
    ("SIG CLD:N OF N3830 LCA BKN 004HFT AGL ISOL/EMBD CB/TCU 020/XXXHFT AGL", "ISOL_EMBD"),
    ("SIG CLD:N OF N4000 BKN 010HFT AGL OCNL CB 030/XXXHFT AGL", "OCNL"),
    ("SIG CLD:S OF N3800 BKN 010HFT AGL FRQ TCU/CB 030/XXXHFT AGL", "FRQ"),
    ("SIG CLD:S OF N3800 BKN 010HFT AGL EMBD CB 030/XXXHFT AGL", "EMBD"),
    ("SIG CLD:S OF N3800 BKN 010HFT AGL CB 030/XXXHFT AGL", "GEN"),
    # Janela a meio da linha (4.3): a parte "11/15 ISOL TCU/CB" herda a área
    ("SIG CLD:09/11 N OF N4000 BKN 002HFT AGL 11/15 ISOL TCU/CB 020/XXXHFT AGL", "ISOL"),
    # Superfície a meio da linha (4.7.6), com outra nuvem antes do CB na parte
    ("SIG CLD:N OF N4000 BKN 004HFT AGL MAR AND COT BKN 002HFT AGL ISOL TCU/CB "
     "020/XXXHFT AGL", "ISOL"),
    # D OF LINE (4.8)
    ("SIG CLD:N OF LINE N3800 W01000 - N4000 W00630 LCA BKN 004-008/012HFT AGL ISOL "
     "TCU/CB 018-035/XXXHFT AGL", "ISOL"),
    # Linha de continuação (texto colado com quebras)
    ("SIG CLD:N OF N4000 LCA BKN 002HFT AGL\nISOL TCU/CB 020/XXXHFT AGL", "ISOL"),
    # Depois de outro campo
    ("SFC VIS:N OF N4000 2000M BR SIG CLD:N OF N4000 BKN 004HFT AGL ISOL TCU/CB "
     "020/XXXHFT AGL TURB:N OF N4000 MOD SFC/FL050", "ISOL"),
]


# (6.0.1, decisão h.2 do Duarte a 20-nov-2026) Um CB que abre a sua parte com
# janela própria ("11/15 ISOL TCU/CB") fica em toda a FIR, mas só nessa janela;
# sem janela própria, todo o período (como na 4.9).
JANELA_PROPRIA = {
    "SIG CLD:09/11 N OF N4000 BKN 002HFT AGL 11/15 ISOL TCU/CB 020/XXXHFT AGL": "11–15Z",
}
_JANELA_CB_RE = re.compile(r"\s*(?:LCA\s+)?(\d{2})/(\d{2})\s+(?:LCA\s+)?"
                           r"(?:ISOL|OCNL|FRQ|EMBD|CB|TCU)\b")


def _janela_propria_esperada(parte):
    """Modelo independente: a parte abre com HH/HH e logo a seguir o grupo do CB
    (LCA pode estar antes ou depois da janela) → "HH–HHZ"; senão ""."""
    m = _JANELA_CB_RE.match(parte or "")
    return f"{m.group(1)}–{m.group(2)}Z" if m else ""


@pytest.mark.parametrize("corpo,valor", MUDAM)
def test_casos_que_mudam(eng, eng481, corpo, valor):
    t = _g(corpo)
    blocos = eng.parse_gamet(t)[0]
    velhos = eng481.parse_gamet(t)[0]
    (cb,) = [b for b in blocos if b.phenomenon == "CB"]
    (cbv,) = [b for b in velhos if b.phenomenon == "CB"]
    assert cb.value == cbv.value == valor
    assert not _toda_fir(eng, cbv.polygon)          # na 4.8.1 só na área da subentrada
    jan = JANELA_PROPRIA.get(corpo, "")
    assert _toda_fir(eng, cb.polygon) and cb.window == jan and cb.janela_ambigua == (not jan)
    assert cb.surface == ""
    # Os blocos que não são do grupo do CB ficam iguais
    _resto_igual(blocos, velhos, corpo)
    # Nunca mais permissivo; pior ou igual em todo o lado
    pts = _pontos(eng, True)
    dn, dv = _decisoes(eng, t, pts), _decisoes(eng481, t, pts)
    assert all(GRAV[dn[k]] >= GRAV[dv[k]] for k in dn)
    nivel = "MARGINAL" if valor == "ISOL" else "NO-GO"
    assert all(GRAV[dn[k]] >= GRAV[nivel] for k in dn)
    # Sem avisos novos
    assert eng.campos_nao_interpretados(t) == eng481.campos_nao_interpretados(t)
    assert eng.subentradas_sem_area(t) == eng481.subentradas_sem_area(t)


def test_base_do_cb_acompanha_o_cb(eng, eng481):
    # Base baixa só no grupo do CB: passa a toda a FIR com ele (conservador)
    t = _g("SIG CLD:N OF N4000 BKN 010HFT AGL ISOL TCU/CB 002/XXXHFT AGL")
    (b,) = [x for x in eng.parse_gamet(t)[0] if x.phenomenon == "BASE_AGL" and x.value == 200]
    assert _toda_fir(eng, b.polygon) and b.janela_ambigua and b.window == ""
    d = {_icao(k): v for k, v in _decisoes(eng, t).items()}
    assert d["LPFR"] == "NO-GO"                    # na 4.8.1 GO (a S de N4000)
    assert {_icao(k): v for k, v in _decisoes(eng481, t).items()}["LPFR"] == "GO"
    # A base da nuvem antes do CB não se mexe
    (b10,) = [x for x in eng.parse_gamet(t)[0] if x.phenomenon == "BASE_AGL"
              and x.value == 1000]
    assert not _toda_fir(eng, b10.polygon)


# --------------------------------------------------------- resto do período

def test_resto_do_periodo_conta_o_cb(eng, eng481):
    t = _g("SIG CLD:15/17 N OF N4000 LCA BKN 002HFT AGL ISOL TCU/CB 020/XXXHFT AGL")
    agora = datetime(2026, 11, 14, 18, 30, tzinfo=timezone.utc)
    r = eng.analisar_gamet(t, agora=agora)
    rv = eng481.analisar_gamet(t, agora=agora)
    # 4.8.1: depois das 18Z o resto ignorava o CB e dava GO
    assert eng481.resto_par(rv)[1] == "GO"
    # 4.9: o CB conta sempre → resto MARGINAL, também a N de N4000
    par = eng.resto_par(r)
    assert par is None or par[1] == "MARGINAL"
    bg = eng.AERODROMES[next(k for k in eng.AERODROMES if "LPBG" in k)]
    pp = eng.resto_par(r, ponto=bg)
    assert pp is None or pp[1] in ("MARGINAL", "NO-GO")
    # E o principal: MARGINAL a S, NO-GO a N
    d = {_icao(k): v for k, v in _decisoes(eng, t).items()}
    assert d["LPFR"] == "MARGINAL" and d["LPBG"] == "NO-GO"


def test_resto_141500_cb_nunca_ignorado(eng):
    for b in eng.parse_gamet(G141500)[0]:
        if b.phenomenon == "CB":
            assert b.janela_ambigua


# ------------------------------------------------ Secção II e AIRMET: iguais

def test_seccao_ii_igual(eng, eng481):
    for secn2 in ("N OF N4000 BKN 010HFT AGL ISOL TCU/CB 003/XXXHFT AGL",
                  "N OF N3945 SCT/BKN SC/CU 012-030/040HFT AGL ISOL TCU/CB 004HFT AGL",
                  "LAN BKN 010HFT AGL ISOL CB 002/XXXHFT AGL"):
        t = _g("SIG CLD:NIL", secn2)
        assert eng.nuvens_baixas_secn2(t) == eng481.nuvens_baixas_secn2(t), secn2
    assert eng.nuvens_baixas_secn2(G141500) == eng481.nuvens_baixas_secn2(G141500)


def _a(corpo):
    return f"LPPC AIRMET 3 VALID 141600/141900 LPPT- LPPC LISBOA FIR/MAINLAND AREA {corpo}"


@pytest.mark.parametrize("corpo", [
    _a("BKN CLD OBS N OF N4000 002/010HFT AGL AND ISOL CB STNR NC"),
    _a("ISOL CB OBS N OF N4000 TOP FL300 STNR NC"),
    _a("OCNL CB OBS WI 20NM OF N4100 W00800 TOP FL300 STNR NC"),
    _a("BKN CLD 002/010HFT AGL AND OCNL TCU/CB OBS N OF N3930 STNR NC"),
])
def test_airmet_sintetico_igual(eng, eng481, corpo):
    agora = datetime(2026, 11, 14, 17, 0, tzinfo=timezone.utc)
    ln, lv = eng.ler_airmet(corpo, agora), eng481.ler_airmet(corpo, agora)
    assert _assin(ln["blocos"]) == _assin(lv["blocos"])
    assert (ln["descr"], ln["lido"]) == (lv["descr"], lv["lido"])


# ------------------------------------------------------------ arquivo e 4.8.1

def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return conftest.indice_sem_altos_60(json.loads((DADOS / "indice.json").read_text(encoding="utf-8")))  # 6.0


# GAMETs do arquivo que a 4.9 lê de outra forma (a 15-nov-2026).
# `conftest.cb_49` tira-os das comparações por igualdade com motores antigos; se
# aparecer outro, este teste falha de propósito: confirma a leitura e
# acrescenta-o aqui.
CB_SOLTO = {
    "20261110T0246Z_100300-100900_3278dbfe9c.txt",
    "20261110T0847Z_100900-101500_ede1104c39.txt",
    "20261110T1448Z_101500-102100_0d0b54fa33.txt",
    "20261112T1440Z_121500-122100_80e7317ca2.txt",
    "20261112T2041Z_122100-130300_e79b5ae658.txt",
    "20261113T0242Z_130300-130900_07dfc9a146.txt",
    "20261113T0844Z_130900-131500_65310dc419.txt",
    "20261113T1445Z_131500-132100_86a9e53e04.txt",
    "20261113T2046Z_132100-140300_8989bcdbbd.txt",
    "20261114T0247Z_140300-140900_3941a8fc42.txt",
    "20261114T0848Z_140900-141500_736e7be0bd.txt",
    "20261114T1449Z_141500-142100_0b0ae4c2af.txt",
    # Acrescentado a 16-nov-2026: GAMET real 151500/152100 de 15-nov. `18/21 N OF
    # N4000 AND E OF W00820 LCA BKN 002-008/010HFT AGL 15/18 ISOL TCU/CB
    # 018-030/XXXHFT AGL` — CB colado à parte anterior de uma linha cortada por
    # janela (o caso `09/11 … BKN 002… 11/15 ISOL TCU/CB` da regra da 4.9): passa
    # para toda a FIR e todo o período, com a base de 1800 ft. Verificado pelos
    # testes do arquivo contra a 4.8.1: nunca mais permissivo, blocos dominados.
    "20261115T1454Z_151500-152100_6bcff7cc11.txt",
}


def test_arquivo_gamets_lidos_de_outra_forma(eng, eng481):
    _arquivo()
    mudam = set()
    for p in sorted((DADOS / "gamets").rglob("*.txt")):
        t = p.read_text(encoding="utf-8")
        diferente = _assin(eng.parse_gamet(t)[0]) != _assin(eng481.parse_gamet(t)[0])
        assert diferente == conftest.cb_49(eng, t), p.name
        if diferente:
            mudam.add(p.name)
    assert mudam == CB_SOLTO


def _resto_igual(novos, velhos, ctx):
    """Os blocos da 4.9 que não são do grupo de um CB solto (`cb_solto`) são
    os da 4.8.1; os que sobram da 4.8.1 são um por cada bloco solto, com o
    mesmo fenómeno e valor (o mesmo bloco, antes na área da subentrada)."""
    resto = _assin(velhos)
    for t in _assin([b for b in novos if not b.cb_solto]):
        assert t in resto, (ctx, t)
        resto.remove(t)
    soltos = sorted((b.phenomenon, str(b.value)) for b in novos if b.cb_solto)
    assert sorted(t[:2] for t in resto) == soltos, ctx


def _dominados(eng, novos, velhos, ctx):
    """Cada bloco da 4.8.1 tem um bloco da 4.9 tão severo, com área que o contém."""
    for v in velhos:
        assert any(eng._domina(n, v) for n in novos), (ctx, v.phenomenon, v.value)


def test_arquivo_manual_contra_4_8_1(eng, eng481):
    _arquivo()
    n = severos = 0
    por_gamet = {}
    for f in sorted((DADOS / "gamets").rglob("*.txt")):
        texto = f.read_text(encoding="utf-8")
        pts = _pontos(eng, True)
        dn, dv = _decisoes(eng, texto, pts), _decisoes(eng481, texto, pts)
        mais_sev = [k for k in dn if GRAV[dn[k]] > GRAV[dv[k]]]
        assert not [k for k in dn if GRAV[dn[k]] < GRAV[dv[k]]], f.name
        bn, bv = eng.parse_gamet(texto)[0], eng481.parse_gamet(texto)[0]
        _dominados(eng, bn, bv, f.name)
        assert eng.campos_nao_interpretados(texto) == eng481.campos_nao_interpretados(texto)
        assert eng.subentradas_sem_area(texto) == eng481.subentradas_sem_area(texto)
        assert eng.nuvens_baixas_secn2(texto) == eng481.nuvens_baixas_secn2(texto)
        if f.name not in CB_SOLTO:
            assert _assin(bn) == _assin(bv), f.name
            assert not mais_sev, f.name
            rn = eng.analisar_gamet(texto, "manual")
            rv = eng481.analisar_gamet(texto, "manual")
            assert rn["avisos"] == rv["avisos"], f.name
            assert rn["por_dec"] == rv["por_dec"], f.name
        aero = [k for k in mais_sev if not k.startswith("grelha")]
        if aero:
            por_gamet[f.name] = len(aero)
        severos += len(aero)
        n += 1
    assert n > 100
    # O 141500 é o caso do pedido: 38 pontos GO → MARGINAL com os limiares da
    # 4.9. (5.0) Com os limiares novos nos dois motores, os 5 pontos a N de
    # N4000 (BASE800_141500: base LCA 800 ft < 1000 ft) já são MARGINAL na 4.8.1,
    # por isso só 38 − 5 = 33 mudam por causa do CB.
    assert por_gamet.get(G141500_F.name) == 38 - len(BASE800_141500)
    assert set(por_gamet) <= CB_SOLTO


def test_arquivo_hist_contra_4_8_1(eng, eng481):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        ini = eng._iso_utc(entrada.get("inicio"))
        if not f.exists() or not ini:
            continue
        texto = f.read_text(encoding="utf-8")
        for horas in (0.5, 3, 5.5):
            agora = ini + timedelta(hours=horas)
            rn = eng.analisar_gamet(texto, "arquivo_hist", indice=indice, entrada=entrada,
                                    agora=agora)
            rv = eng481.analisar_gamet(texto, "arquivo_hist", indice=indice,
                                       entrada=entrada, agora=agora)
            for k, (la, lo) in _pontos(eng):
                a = (eng.find_region_for_point(rn["regioes"], la, lo) or {}).get("decision")
                b = (eng481.find_region_for_point(rv["regioes"], la, lo) or {}).get("decision")
                assert GRAV[a] >= GRAV[b], (f.name, horas, k)
                # Resto do período: nunca menos severo do que o da 4.8.1
                ra, rb = eng.resto_par(rn, ponto=(la, lo)), eng481.resto_par(rv, ponto=(la, lo))
                if rb is not None:
                    na = GRAV[ra[1]] if ra is not None else GRAV[a]
                    assert na >= GRAV[rb[1]], (f.name, horas, k)
            if f.name not in CB_SOLTO:
                assert rn["por_dec"] == rv["por_dec"], f.name
        n += 1
    assert n > 100


# ------------------------------------------------------------- linhas geradas

AREAS = ["N OF N4000", "S OF N3830", "E OF W00800", "W OF W00830", "BTN N3800 AND N4000",
         "N OF N3945 AND E OF W00830", "N OF LINE N3800 W01000 - N4000 W00630"]
SUPS = ["", "", "MAR", "LAN", "COT", "MAR AND COT", "LAN AND COT"]
NUVENS = ["LCA BKN 002-008/010HFT AGL", "BKN 004/010HFT AGL", "LCA BKN 008-010/012HFT AGL",
          "OVC 001/005HFT AGL", "LCA BKN 006HFT AGL"]
CBS = ["ISOL TCU/CB 018-030/XXXHFT AGL", "ISOL/EMBD TCU/CB 020-035/XXXHFT AGL",
       "OCNL CB 030/XXXHFT AGL", "EMBD CB/TCU 002/XXXHFT AGL", "FRQ TCU/CB 025/XXXHFT AGL"]


def _sub(rng, com_area=True):
    s = rng.choice(["", "", "18/21 ", "15/17 "])
    if com_area:
        s += rng.choice(AREAS) + " "
    sup = rng.choice(SUPS)
    return (s + (sup + " " if sup else "")).strip()


def _corpo(rng):
    subs = []
    for i in range(rng.choice([1, 2, 2, 3])):
        cab = _sub(rng, com_area=(i > 0 or rng.random() < 0.8))
        r = rng.random()
        if r < 0.45:
            val = f"{rng.choice(NUVENS)} {rng.choice(CBS)}"               # colado
        elif r < 0.6:
            val = f"{rng.choice(NUVENS)} {_sub(rng)} {rng.choice(CBS)}"   # qualificador próprio
        elif r < 0.7:
            val = f"{rng.choice(NUVENS)} 19/21 {rng.choice(CBS)}"         # janela a meio
        elif r < 0.85:
            val = rng.choice(CBS)
        else:
            val = rng.choice(NUVENS)
        subs.append(f"{cab} {val}".strip())
    return "SIG CLD:" + " ".join(subs)


def test_linhas_geradas_contra_4_8_1(eng, eng481):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "49")))
    casos = int(os.environ.get("GAMET_CASOS", "300"))
    pts = _pontos(eng, True)
    mudou = 0
    for _ in range(casos):
        corpo = _corpo(rng)
        t = _g(corpo)
        bn, bv = eng.parse_gamet(t)[0], eng481.parse_gamet(t)[0]
        _dominados(eng, bn, bv, corpo)
        _resto_igual(bn, bv, corpo)
        dn, dv = _decisoes(eng, t, pts), _decisoes(eng481, t, pts)
        assert all(GRAV[dn[k]] >= GRAV[dv[k]] for k in dn), corpo
        assert eng.campos_nao_interpretados(t) == eng481.campos_nao_interpretados(t), corpo
        assert eng.subentradas_sem_area(t) == eng481.subentradas_sem_area(t), corpo
        # Um CB que muda está em toda a FIR; sem janela própria a abrir a sua
        # parte, sem janela e conta sempre; com ela, só nessa janela (6.0.1)
        for b in bn:
            if b.cb_solto:
                jan = _janela_propria_esperada(b.parte)
                assert _toda_fir(eng, b.polygon), corpo
                assert b.window == jan and b.janela_ambigua == (not jan), (corpo, b.parte)
        mudou += any(b.cb_solto for b in bn)
    assert mudou > casos // 5


def test_sem_a_regra_e_a_4_8_1(eng, eng481):
    """`parse_gamet(…, _cb_solto=False)` é a leitura da 4.8.1 (usada pelos
    testes da 4.7.6 que verificam outras regras, e pela Secção II): no arquivo
    e em linhas geradas."""
    textos = [_g(c) for c in IGUAIS] + [_g(c) for c, _v in MUDAM]
    if (DADOS / "gamets").exists():
        textos += [p.read_text(encoding="utf-8") for p in sorted((DADOS / "gamets").rglob("*.txt"))]
    rng = random.Random(4949)
    textos += [_g(_corpo(rng)) for _ in range(150)]
    for t in textos:
        assert _assin(eng.parse_gamet(t, _cb_solto=False)[0]) == \
            _assin(eng481.parse_gamet(t)[0]), t[:200]
        for kw in ({"_modo42": True}, {"_modo475": True}, {"_modo476": True}):
            assert _assin(eng.parse_gamet(t, **kw)[0]) == \
                _assin(eng481.parse_gamet(t, **kw)[0]), (kw, t[:200])



# ---------------------------------------------------------------- 6.0.1 (h.2)
G151500 = (
    'LPPC GAMET VALID 151500/152100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:N OF N3730 LCA 3000-5000M RA 18/21 N OF N4000 AND E OF W00820 LCA 0800-5000 FG/BR SI'
    'G CLD:N OF N3730 LCA BKN 006-010/012HFT AGL 18/21 N OF N4000 AND E OF W00820 LCA BKN 002'
    '-008/010HFT AGL 15/18 ISOL TCU/CB 018-030/XXXHFT AGL SIGMET APPLICABLE: AT TIME OF ISSUE'
    ' NIL SECN II PSYS:18 NIL CLD:SCT/BKN SC/CU 012-030/040HFT AGL FEW/SCT AC/AS 060-090/100-'
    '130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT A'
    'GL 260/023KT PS09 250/016KT PS14 250/014KT PS10 2000FT AGL 270/028KT PS07 260/019KT PS12'
    ' 270/021KT PS09 5000FT AGL 280/040KT PS02 260/024KT PS07 270/030KT PS04 FL100 280/041KT '
    'MS02 270/027KT MS02 270/030KT MS02 FL150 290/041KT MS09 290/037KT MS09 290/036KT MS09 FZ'
    'LVL: 8800FT AMSL 9200FT AMSL 8400FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N37'
    '00 W00800 1000FT AGL 250/012KT PS15 260/012KT PS14 290/007KT PS16 2000FT AGL 250/013KT P'
    'S13 260/015KT PS12 320/005KT PS14 5000FT AGL 250/016KT PS08 280/015KT PS07 260/005KT PS1'
    '0 FL100 270/021KT MS01 280/021KT MS01 280/019KT PS00 FL150 270/025KT MS06 290/024KT MS06'
    ' 290/014KT MS06 FZLVL: 9100FT AMSL 9600FT AMSL 10600FT AMSL MNM QNH:1017HPA='
)


def test_151500_cb_com_janela_propria(eng):
    """(6.0.1, decisão h.2 do Duarte a 20-nov-2026: "como for mais lógico e
    real") GAMET real 151500/152100: `… 18/21 N OF N4000 AND E OF W00820 LCA BKN
    002-008/010HFT AGL 15/18 ISOL TCU/CB 018-030/XXXHFT AGL`. O CB não tem área
    (toda a FIR, 4.9) mas tem janela própria: só das 15 às 18Z. O BKN 002 fica
    a N de N4000 das 18 às 21Z. A decisão principal (pior do período) não muda."""
    from datetime import datetime, timezone
    bl = eng.parse_gamet(G151500)[0]
    (cb,) = [b for b in bl if b.phenomenon == "CB"]
    (b18,) = [b for b in bl if b.phenomenon == "BASE_AGL" and b.value == 1800]
    for b in (cb, b18):
        assert b.cb_solto and _toda_fir(eng, b.polygon)
        assert b.window == "15–18Z" and not b.janela_ambigua
    (b2,) = [b for b in bl if b.phenomenon == "BASE_AGL" and b.value == 200]
    assert b2.window == "18–21Z" and not b2.cb_solto and not _toda_fir(eng, b2.polygon)
    # Principal igual com e sem a janela (pior caso de todo o período)
    sem = eng.analisar_gamet(G151500, "manual", agora=datetime(2026, 11, 15, 16, 0,
                                                                 tzinfo=timezone.utc))
    assert sem["regioes"]
    # Resto do período: às 16:00Z o CB conta; às 19:30Z (18Z + 1 h) já não
    for hora, conta in ((16, True), (19.5, False)):
        h, mi = int(hora), int(round((hora - int(hora)) * 60))
        r = eng.analisar_gamet(G151500, "manual",
                               agora=datetime(2026, 11, 15, h, mi, tzinfo=timezone.utc))
        resto = r["resto"]
        regs = resto["regioes"] if resto else r["regioes"]
        tem_cb = any("CB" in m for x in regs for m in x["reasons"])
        assert tem_cb == conta, (hora, resto and resto["janela"])
