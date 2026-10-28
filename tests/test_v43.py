"""
4.3 — Uma janela "HH/HH" a meio da linha abre sempre uma subentrada nova
(pedido do Duarte a 28-out-2026).

Até à 4.2 só "HH/HH MAR|LAN|COT" seguido de valores partia a linha (4.1).
Ficavam dois defeitos, iguais aos da 4.0, sem nenhum caso no arquivo:

1. "HH/HH MAR|LAN|COT" no fim da linha, ou seguido de outro qualificador:
       SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 MAR
   A 1.ª subentrada ficava recortada pela superfície da seguinte (MAR): a
   base de 200 ft deixava de contar em terra (OPTIMISTA: GO em Bragança).
2. Valores com janelas diferentes na mesma linha e sem área:
       SFC VIS:09/11 0800M FG 13/15 2000M BR
   O 2000M ficava com a janela 09–11Z (a 4.2 protegia-se com
   MetBlock.janela_ambigua no resto do período).

Desde a 4.3 a parte que começa pela janela fica com a sua janela e com a área
do que vem a seguir: superfície → a superfície em toda a FIR (leitura A, como
na 4.1); qualificador → essa área; só valores → a área da subentrada que a
linha já tinha (com a superfície da parte anterior). A 1.ª parte nunca é
recortada pela superfície de uma parte seguinte. Cada parte é unida com a área
que a 4.2 dava à(s) parte(s) da linha de onde vêm os valores, e um bloco da 4.2
sem bloco novo tão severo que o contenha entra tal como a 4.2 o lia — nunca
mais permissivo. Verificado contra o motor da 4.2
(`tests/referencia/app_4_2.py`, cópia fixa do app.py do main 597a70d; não
editar), no arquivo e em subentradas geradas. Semente: GAMET_SEMENTE (por
omissão 43); GAMET_CASOS (por omissão 300).
"""
import json
import os
import random
import re
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from shapely.geometry import Point

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
RAIZ = Path(__file__).resolve().parent.parent
REF = Path(__file__).resolve().parent / "referencia" / "app_4_2.py"
ARQUIVO = RAIZ / "dados" / "gamets"
SIGMETS = RAIZ / "dados" / "sigmets"
INDICE = RAIZ / "dados" / "indice.json"
VAL = "280900/281500"

CASO1 = "SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 MAR"
CASO1B = ("SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 MAR W OF W00800 "
          "BKN 004/008HFT AGL")
CASO2 = "SFC VIS:09/11 0800M FG 13/15 2000M BR"


@pytest.fixture(scope="module")
def eng42():
    src = REF.read_text(encoding="utf-8")
    mod = types.ModuleType("motor_4_2")
    mod.__dict__["__file__"] = str(REF)
    exec(compile(conftest._extract_engine(src), str(REF), "exec"), mod.__dict__)
    return mod


def _t(h, m=0, dia=28):
    return datetime(2026, 10, dia, h, m, tzinfo=timezone.utc)


def _g(corpo):
    return build_gamet(f"SECN I {corpo}", validity=VAL)


def _nome(eng, icao):
    return next(n for n in eng.AERODROMES if f"({icao})" in n)


def _blocos(eng, corpo):
    return eng.parse_gamet(_g(corpo))[0]


def _so(blocos, fen, val):
    r = [b for b in blocos if b.phenomenon == fen and b.value == val]
    assert len(r) == 1, (fen, val, [(b.phenomenon, b.value) for b in blocos])
    return r[0]


# Grelha de 0,3° sobre a FIR (além dos 52 aeródromos)
GRELHA = [(36.95 + 0.3 * i, -9.55 + 0.3 * j) for i in range(18) for j in range(12)]


def _decisoes(e, texto, pontos):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    out = {}
    for k, (la, lo) in pontos:
        r = e.find_region_for_point(regioes, la, lo)
        out[k] = r["decision"] if r else None
    return out


def _pontos(eng, grelha=False):
    p = list(eng.AERODROMES.items())
    if grelha:
        p += [(f"grelha {la:.2f} {lo:.2f}", (la, lo)) for la, lo in GRELHA
              if eng.FIR_POLYGON.contains(Point(lo, la))]
    return p


def _blocos_cobertos(eng, bn, bv, ctx):
    """Cada bloco da 4.2 tem um da 4.3 com o mesmo fenómeno, valor igual ou
    pior e área que contém a da 4.2 (WX componente a componente)."""
    for b in bv:
        comps = ([(c, "WX") for c in b.value.split("/")] if b.phenomenon == "WX"
                 else [(b.value, b.phenomenon)])
        for val, fen in comps:
            def serve(n):
                if n.phenomenon != fen or not n.polygon.buffer(1e-6).contains(b.polygon):
                    return False
                if fen == "VIS" and n.qualifier == "LCA" and b.qualifier != "LCA":
                    return False
                if fen == "WX":
                    return val in n.value.split("/")
                if fen in ("TS", "CB"):
                    d = 1 if fen == "TS" else 2
                    return eng.TS_RISK.get(n.value, d) >= eng.TS_RISK.get(val, d)
                if fen in ("VIS", "BASE_AGL", "BASE_AMSL"):
                    return n.value <= val
                if fen == "WSPD":
                    return n.value >= val
                if fen in ("TURB", "ICE", "MTW"):
                    return n.value in (val, "SEV")
                return n.value == val
            assert any(serve(n) for n in bn), (ctx, "bloco da 4.2 perdido", fen, val)


def _comparar(eng, eng42, texto, grelha=False):
    """Nunca mais permissivo do que a 4.2 (aeródromos e, se pedido, grelha),
    nenhum bloco da 4.2 com menos área, nenhum aviso "Campo não interpretado"
    novo. Devolve (novo, antigo)."""
    pts = _pontos(eng, grelha)
    novo, antigo = _decisoes(eng, texto, pts), _decisoes(eng42, texto, pts)
    piores = [(n, antigo[n], novo[n]) for n in antigo
              if antigo[n] and (novo[n] is None or GRAV[novo[n]] < GRAV[antigo[n]])]
    assert not piores, (texto[90:300], piores[:5])
    bn, *_ = eng.parse_gamet(texto)
    bv, *_ = eng42.parse_gamet(texto)
    _blocos_cobertos(eng, bn, bv, texto[90:300])
    if not eng42.campos_nao_interpretados(texto):
        assert eng.campos_nao_interpretados(texto) == [], texto[90:300]
    return novo, antigo


def _dec_ponto(eng, r, nome):
    reg = eng.find_region_for_point(r["regioes"], *eng.AERODROMES[nome])
    return reg["decision"] if reg else None


def _verifica_resto(eng, r):
    """O resto do período nunca é mais severo do que a decisão principal."""
    resto = r["resto"]
    if resto is None:
        return 0
    assert GRAV[resto["decisao"]] <= GRAV[max(r["por_dec"], key=GRAV.get)]
    for g, d in zip(r["regioes"], resto["por_regiao"]):
        assert d is not None and GRAV[d] <= GRAV[g["decision"]], (g["label"], d)
    for nome, (la, lo) in eng.AERODROMES.items():
        principal = _dec_ponto(eng, r, nome)
        if principal is not None:
            assert GRAV[eng.resto_do_ponto(resto, la, lo)] <= GRAV[principal], nome
    return 1


# --- Referência e versão ---------------------------------------------------------

def test_referencia_e_a_4_2(eng42):
    assert eng42.APP_VERSION == "4.2"
    assert not hasattr(eng42, "_cortes_janela")


def test_versao(eng):
    assert eng.APP_VERSION == "4.3"


# --- Defeito 1: "HH/HH MAR" no fim da linha (optimista na 4.2) -------------------

def test_caso1_primeira_parte_sem_recorte(eng, eng42):
    b = _so(_blocos(eng, CASO1), "BASE_AGL", 200)
    n4000 = eng.extract_polygon("N OF N4000")
    assert b.polygon.symmetric_difference(n4000).area < 1e-6
    assert b.surface == "" and b.window == "09–11Z" and not b.janela_ambigua
    # Na 4.2 só no mar
    v = _so(_blocos(eng42, CASO1), "BASE_AGL", 200)
    assert v.surface == "MAR"
    assert not v.polygon.contains(Point(eng.AERODROMES[_nome(eng, "LPBG")][::-1]))


@pytest.mark.parametrize("icao", ["LPBG", "LPVR", "LPCH", "LPVZ", "LPMU", "LPPR"])
def test_caso1_terra_a_n_de_n4000_no_go(eng, eng42, icao):
    novo, antigo = _comparar(eng, eng42, _g(CASO1))
    assert novo[_nome(eng, icao)] == "NO-GO"
    assert antigo[_nome(eng, icao)] in ("GO", "NO-GO")      # 4.2: GO em terra


def test_caso1_4_2_dava_go_em_terra(eng, eng42):
    _novo, antigo = _comparar(eng, eng42, _g(CASO1))
    assert antigo[_nome(eng, "LPBG")] == "GO"
    assert antigo[_nome(eng, "LPPT")] == "GO"


def test_caso1_a_sul_continua_go(eng, eng42):
    novo, _ = _comparar(eng, eng42, _g(CASO1))
    for icao in ("LPPT", "LPFR", "LPEV", "LPBJ"):
        assert novo[_nome(eng, icao)] == "GO"


def test_caso1_sem_avisos(eng):
    t = _g(CASO1)
    assert eng.campos_nao_interpretados(t) == []
    assert eng.subentradas_sem_area(t) == []


@pytest.mark.parametrize("sup", ["MAR", "COT", "LAN", "MAR AND COT", "COT AND LAN", "LAN MAR"])
def test_caso1_superficies(eng, eng42, sup):
    corpo = f"SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 {sup}"
    _comparar(eng, eng42, _g(corpo))
    b = _so(_blocos(eng, corpo), "BASE_AGL", 200)
    assert b.polygon.symmetric_difference(eng.extract_polygon("N OF N4000")).area < 1e-6
    assert eng.campos_nao_interpretados(_g(corpo)) == []


def test_caso1_com_and_antes_da_janela(eng, eng42):
    corpo = "SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL AND 11/15 COT AND LAN"
    _comparar(eng, eng42, _g(corpo))
    b = _so(_blocos(eng, corpo), "BASE_AGL", 200)
    assert b.surface == "" and b.window == "09–11Z"


def test_caso1b_superficie_e_qualificador(eng, eng42):
    """"… 11/15 MAR W OF W00800 BKN 004/008HFT AGL": a quebra antes de W OF
    deixava "11/15 MAR" no fim da 1.ª linha; passa para o início da seguinte."""
    _comparar(eng, eng42, _g(CASO1B))
    bl = _blocos(eng, CASO1B)
    b200, b400 = _so(bl, "BASE_AGL", 200), _so(bl, "BASE_AGL", 400)
    assert b200.polygon.symmetric_difference(eng.extract_polygon("N OF N4000")).area < 1e-6
    assert b200.window == "09–11Z"
    assert b400.window == "11–15Z" and not b400.janela_ambigua
    # Nunca menos do que a 4.2 dava (W OF W00800, todas as superfícies)
    assert b400.polygon.buffer(1e-6).contains(eng.extract_polygon("W OF W00800"))
    assert eng.campos_nao_interpretados(_g(CASO1B)) == []
    assert eng.subentradas_sem_area(_g(CASO1B)) == []


def test_caso1_superficie_e_coordenadas(eng, eng42):
    corpo = ("SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 MAR WI N4000 W00900 - "
             "N4000 W00800 - N3900 W00800 - N3900 W00900 - N4000 W00900 BKN 004/008HFT AGL")
    _comparar(eng, eng42, _g(corpo))
    bl = _blocos(eng, corpo)
    assert _so(bl, "BASE_AGL", 200).surface == ""
    assert _so(bl, "BASE_AGL", 400).window == "11–15Z"


# --- Defeito 2: valores com janelas diferentes na mesma linha ---------------------

def test_caso2_cada_valor_com_a_sua_janela(eng, eng42):
    _comparar(eng, eng42, _g(CASO2))
    bl = _blocos(eng, CASO2)
    assert [(b.value, b.window, b.janela_ambigua) for b in bl] == [
        (800, "09–11Z", False), (2000, "13–15Z", False)]
    # A 4.2 dava 09–11Z aos dois (protegida por janela_ambigua)
    assert {(b.window, b.janela_ambigua) for b in _blocos(eng42, CASO2)} == {("09–11Z", True)}
    assert eng.campos_nao_interpretados(_g(CASO2)) == []


def test_caso2_decisao_principal_igual(eng, eng42):
    novo, antigo = _comparar(eng, eng42, _g(CASO2), grelha=True)
    assert novo == antigo
    assert set(novo.values()) == {"NO-GO"}


def test_caso2_resto_do_periodo_as_1230(eng):
    """Às 12:30 o 0800M (09–11Z, terminou há mais de 1 h) sai; o 2000M (13–15Z,
    ainda não começou) conta: resto MARGINAL, principal NO-GO."""
    r = eng.analisar_gamet(_g(CASO2), agora=_t(12, 30))
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert [b.value for b in r["resto"]["ignorados"]] == [800]
    assert r["resto"]["decisao"] == "MARGINAL"
    assert eng.resto_par(r) == ("12–15Z", "MARGINAL")
    assert _verifica_resto(eng, r)
    # Às 11:30 (dentro da margem de 1 h) ainda nada sai
    assert eng.analisar_gamet(_g(CASO2), agora=_t(11, 30))["resto"] is None
    # Às 16:00 o GAMET já expirou
    assert eng.analisar_gamet(_g(CASO2), agora=_t(16, 0))["resto"] is None


def test_caso2_resto_na_4_2_nao_ignorava_nada(eng42):
    assert eng42.analisar_gamet(_g(CASO2), agora=_t(12, 30))["resto"] is None


def test_caso2_com_qualificador_herda_area_e_superficie(eng, eng42):
    corpo = "SFC VIS:09/11 N OF N4000 MAR 0800M FG 13/15 2000M BR"
    _comparar(eng, eng42, _g(corpo))
    bl = _blocos(eng, corpo)
    b800, b2000 = _so(bl, "VIS", 800), _so(bl, "VIS", 2000)
    assert b2000.window == "13–15Z" and b2000.surface == "MAR"
    assert b2000.polygon.symmetric_difference(b800.polygon).area < 1e-9
    v = _so(_blocos(eng42, corpo), "VIS", 2000)
    assert b2000.polygon.buffer(1e-6).contains(v.polygon)


def test_caso2_tres_janelas_e_lca(eng, eng42):
    corpo = "SFC VIS:09/11 W OF W00800 0800M FG 11/13 LCA 1200M BR 13/15 3000M RA"
    _comparar(eng, eng42, _g(corpo))
    bl = _blocos(eng, corpo)
    assert {b.value: (b.window, b.qualifier) for b in bl} == {
        800: ("09–11Z", ""), 1200: ("11–13Z", "LCA"), 3000: ("13–15Z", "")}
    w = eng.extract_polygon("W OF W00800")
    assert all(b.polygon.symmetric_difference(w).area < 1e-6 for b in bl)


def test_caso2_janela_ate_as_24(eng, eng42):
    t = build_gamet("SECN I SFC VIS:18/21 0800M FG 21/24 2000M BR", validity="281800/290000")
    _comparar(eng, eng42, t)
    bl, *_ = eng.parse_gamet(t)
    assert [(b.value, b.window) for b in bl] == [(800, "18–21Z"), (2000, "21–24Z")]


def test_caso2_linha_de_continuacao(eng, eng42):
    corpo = "SFC VIS:09/11 N OF N3700 0800M FG 13/15 2000M BR\nLCA 1000M FG"
    _comparar(eng, eng42, _g(corpo))
    bl = _blocos(eng, corpo)
    assert {b.value: b.window for b in bl} == {800: "09–11Z", 2000: "13–15Z", 1000: "13–15Z"}
    assert not any(b.janela_ambigua for b in bl)


@pytest.mark.parametrize("corpo", [
    "SIG CLD:09/11 BKN 004/010HFT AGL 13/15 BKN 008/012HFT AGL",
    "SIGWX:09/11 ISOL TS 13/15 OCNL TSRA",
    "TURB:09/11 MOD SFC/FL050 13/15 SEV SFC/FL080",
    "ICE:09/11 MOD FL050/FL100 13/15 SEV FL060/FL120",
    "SFC WSPD:09/11 25KT 13/15 32KT",
    "MTW:09/11 MOD FL050/100 13/15 SEV FL050/100",
])
def test_outros_campos_partidos(eng, eng42, corpo):
    _comparar(eng, eng42, _g(corpo))
    bl = _blocos(eng, corpo)
    assert sorted({b.window for b in bl}) == ["09–11Z", "13–15Z"], corpo
    assert not any(b.janela_ambigua for b in bl)
    assert eng.campos_nao_interpretados(_g(corpo)) == []


def test_resto_com_janelas_partidas_nunca_mais_severo(eng):
    for corpo in (CASO2, CASO1, CASO1B, "SIG CLD:09/11 BKN 002/006HFT AGL 13/15 BKN 004/008HFT AGL",
                  "SIGWX:09/11 OCNL TS 11/13 ISOL TS"):
        for agora in (_t(9, 30), _t(12, 0), _t(12, 30), _t(13, 30), _t(14, 50)):
            _verifica_resto(eng, eng.analisar_gamet(_g(corpo), agora=agora))


# --- Garantia: um bloco que a partição tornaria menos severo ----------------------

def test_qualificador_que_ficava_na_outra_parte(eng, eng42):
    """"ISOL TCU/CB … 13/15 EMBD …": na 4.2 o EMBD da linha inteira tornava o
    CB ISOL_EMBD (NO-GO); partida, a 1.ª parte só tem ISOL. O bloco da 4.2
    entra tal como era (e conta sempre no resto do período)."""
    corpo = "SIG CLD:09/11 ISOL TCU/CB 030/XXXHFT AGL 13/15 EMBD BKN 020HFT AGL"
    novo, antigo = _comparar(eng, eng42, _g(corpo))
    assert novo == antigo and set(novo.values()) == {"NO-GO"}
    cb = [b for b in _blocos(eng, corpo) if b.phenomenon == "CB"]
    assert any(b.value == "ISOL_EMBD" and b.janela_ambigua for b in cb)


def test_ts_sem_ts_na_segunda_parte(eng, eng42):
    corpo = "SIGWX:09/11 ISOL TS 13/15 OCNL"
    novo, antigo = _comparar(eng, eng42, _g(corpo))
    assert novo == antigo and set(novo.values()) == {"NO-GO"}


# --- Casos que ficam iguais à 4.2 -------------------------------------------------

IGUAIS = [
    # sem janela a meio
    "SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL",
    "SFC VIS:W OF W00715 0800M BR MAR AND COT",
    # janela a abrir o campo, com ou sem superfície
    "SIG CLD:11/15 MAR AND COT BKN 002/006HFT AGL",
    "SIG CLD 11/15 MAR BKN 002/006HFT AGL",
    # janela no fim da linha (sem nada a seguir)
    "SFC VIS:09/11 0800M FG 13/15",
    # janela depois de um qualificador ou de LCA (é a da própria subentrada)
    "SIG CLD:N OF N4000 11/15 BKN 002/006HFT AGL",
    "SFC VIS:LCA 09/11 0800M FG",
    # duas janelas seguidas
    "SFC VIS:09/11 13/15 0800M FG",
    # qualificador depois do valor (quebra injectada, como sempre)
    "SIG CLD:09/11 N OF N4000 BKN 002/006HFT AGL 11/15 S OF N4000 BKN 004/008HFT AGL",
    "SFC VIS:09/11 W OF W00800 0800M FG 11/15 BTN N3840 AND N4000 2000M BR",
    # GAMET real 270900 (4.1): igual à 4.2
    "SFC VIS:09/11 W OF W00715 LCA 0200-5000M FG/BR 11/15 MAR AND COT LCA 0400-5000M FG/BR",
    # MT OBSC: só áreas e superfícies — não parte
    "MT OBSC:09/11 N OF N4100 LAN 13/15 MAR",
    "MT OBSC:N OF N4100 LAN S OF N3800 LAN",
]


@pytest.mark.parametrize("corpo", IGUAIS)
def test_inalterados(eng, eng42, corpo):
    t = _g(corpo)
    novo, antigo = _comparar(eng, eng42, t, grelha=True)
    assert novo == antigo
    sig = lambda bl: [(b.phenomenon, b.value, b.qualifier, b.window, b.surface,  # noqa: E731
                       b.janela_ambigua, round(b.polygon.area, 9)) for b in bl]
    assert sig(eng.parse_gamet(t)[0]) == sig(eng42.parse_gamet(t)[0])
    assert eng.campos_nao_interpretados(t) == eng42.campos_nao_interpretados(t)
    assert eng.subentradas_sem_area(t) == eng42.subentradas_sem_area(t)


def test_janela_depois_de_area_comprida(eng, eng42):
    """A janela depois de uma área com mais de 24 caracteres é a da subentrada
    e não parte a linha. A 4.2 lia-a porque a 4.1 cortava em "11/15 MAR", mas
    deixava a área sozinha como subentrada e avisava "Campo não interpretado"
    (aviso falso, que desaparece)."""
    corpo = "SIG CLD:N OF N4000 AND W OF W00800 11/15 MAR BKN 004/010HFT AGL"
    t = _g(corpo)
    novo, antigo = _comparar(eng, eng42, t, grelha=True)
    assert novo == antigo
    (b,) = _blocos(eng, corpo)
    (v,) = _blocos(eng42, corpo)
    assert (b.value, b.window, b.surface, b.janela_ambigua) == (400, "11–15Z", "MAR", False)
    assert b.polygon.symmetric_difference(v.polygon).area < 1e-9
    assert eng42.campos_nao_interpretados(t) == ["SIG CLD: N OF N4000 AND W OF W00800"]
    assert eng.campos_nao_interpretados(t) == []


# --- Falsos positivos: números que parecem janela ---------------------------------

FALSOS = [
    "SIG CLD:N OF N4000 BKN 002/006HFT AGL OVC 010/015HFT AGL",
    "SIG CLD:N OF N4000 ISOL TCU/CB 06/ 090HFT AGL",
    "SIG CLD:N OF N4000 BKN 002-004/010-015HFT AGL",
    "SIG CLD:N OF N4000 BKN 10/15 HFT AGL",
    "SFC WSPD:N OF N4000 20/24 KT",
    "SFC WSPD:N OF N4000 30/35KT",
    "TURB:N OF N4000 MOD SFC/FL050 SEV ABV FL070",
    "ICE:N OF N4000 MOD FL050/FL100",
    "SFC VIS:N OF N4000 0800M BR 25/30 FG",
    "SFC VIS:N OF N4000 0800M BR 12/30 FG",
    "SIG CLD:N OF N4000 BKN 002/ABV 030HFT AGL",
    "MTW:N OF N4000 SEV FL050/100 10/20 M",
]


@pytest.mark.parametrize("corpo", FALSOS)
def test_falsos_positivos_de_janela(eng, eng42, corpo):
    t = _g(corpo)
    linha = eng.normalize(corpo).split(":", 1)[1]
    assert eng._cortes_janela(linha) == []
    novo, antigo = _comparar(eng, eng42, t)
    assert novo == antigo
    sig = lambda bl: [(b.phenomenon, b.value, b.window, b.janela_ambigua,  # noqa: E731
                       round(b.polygon.area, 9)) for b in bl]
    assert sig(eng.parse_gamet(t)[0]) == sig(eng42.parse_gamet(t)[0])


def test_cortes_janela(eng):
    c = eng._cortes_janela
    assert c("SFC VIS:09/11 0800M FG 13/15 2000M BR") == [(23, 13, 15)]
    assert c("09/11 N OF N4000 BKN 002/006HFT AGL 11/15 MAR") == [(36, 11, 15)]
    assert c("SFC VIS:09/11 0800M FG 21/24 2000M") == [(23, 21, 24)]
    assert c("SFC VIS:09/11 0800M FG 21/25 2000M") == []
    assert c("SFC VIS:09/11 0800M FG 13/15") == []
    assert c("SFC VIS: LCA 09/11 0800M FG") == []
    assert c("N OF N4000 AND W OF W00800 11/15 BKN 004HFT") == []


# --- Secção II, AIRMET, MT OBSC/VA --------------------------------------------------

def test_secn2_janela_no_fim(eng, eng42):
    t = ("LPPC GAMET VALID 280900/281500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
         "SECN I SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II CLD:09/11 N OF N4000 "
         "SCT ST 002/006HFT AGL 11/15 MAR MNM QNH:1020HPA=")
    _c, nuvens = eng.nuvens_baixas_secn2(t)
    (n,) = nuvens
    assert n[0] == 200 and n[2] == "09–11Z" and n[3] == ""
    assert _nome(eng, "LPBG") in n[4]
    _c, antigas = eng42.nuvens_baixas_secn2(t)
    assert antigas[0][3] == "MAR" and _nome(eng, "LPBG") not in antigas[0][4]
    assert set(antigas[0][4]) <= set(n[4])


def test_secn2_duas_janelas(eng):
    t = ("LPPC GAMET VALID 280900/281500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
         "SECN I SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II CLD:09/11 SCT ST "
         "002/006HFT AGL 13/15 SCT ST 004/008HFT AGL MNM QNH:1020HPA=")
    _c, nuvens = eng.nuvens_baixas_secn2(t)
    assert {n[0]: n[2] for n in nuvens} == {200: "09–11Z", 400: "13–15Z"}


def _airmets():
    from test_v40 import AIR1_25, AIR2_25, AIR1_17
    txt = [AIR1_25, AIR2_25, AIR1_17,
           "LPPC AIRMET 5 VALID 281000/281300 LPPT- LPPC LISBOA FIR/MAINLAND AREA SFC VIS "
           "0800M FG OBS N OF N4000 STNR NC=",
           "LPPC AIRMET 6 VALID 281000/281300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BKN CLD "
           "002/010HFT AGL FCST N OF N4000 AND W OF W00800 STNR NC="]
    if SIGMETS.exists():
        txt += [p.read_text(encoding="utf-8") for p in sorted(SIGMETS.rglob("*AIRMET*.txt"))]
    return txt


def test_airmet_sintetico_igual_a_4_2(eng, eng42):
    sig = lambda bl: [(b.phenomenon, b.value, b.qualifier, b.window, b.surface,  # noqa: E731
                       b.origem, round(b.polygon.area, 9)) for b in bl]
    for a in _airmets():
        for ref in (_t(10, 30), datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc),
                    datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)):
            assert sig(eng.blocos_airmet([a], ref)[0]) == sig(eng42.blocos_airmet([a], ref)[0]), a[:60]


def test_va_e_mt_obsc_partidos_nunca_menos(eng, eng42):
    for corpo in ("VA:09/11 VA CLD FL050/100 13/15 MAR VA CLD FL100/150",
                  "MT OBSC:09/11 N OF N4100 BY CLD 13/15 S OF N3800 LAN",
                  "MT OBSC:09/11 N OF N4100 BY CLD 13/15 MAR"):
        _comparar(eng, eng42, _g(corpo), grelha=True)


# --- Contra o motor da 4.2: arquivo -------------------------------------------------

def _arquivo():
    return sorted(ARQUIVO.rglob("*.txt")) if ARQUIVO.exists() else []


def test_arquivo_igual_a_4_2(eng, eng42):
    """Nenhum GAMET do arquivo tem janelas a meio da linha que mudem: os
    blocos, as decisões e os avisos são iguais aos da 4.2."""
    fich = _arquivo()
    if not fich:
        pytest.skip("arquivo (ramo dados) não disponível")
    sig = lambda bl: [(b.phenomenon, b.value, b.qualifier, b.window, b.surface,  # noqa: E731
                       b.janela_ambigua, round(b.polygon.area, 9)) for b in bl]
    for p in fich:
        t = p.read_text(encoding="utf-8").strip()
        novo, antigo = _comparar(eng, eng42, t)
        assert novo == antigo, p.name
        assert sig(eng.parse_gamet(t)[0]) == sig(eng42.parse_gamet(t)[0]), p.name
        assert eng.campos_nao_interpretados(t) == eng42.campos_nao_interpretados(t)
        assert eng.subentradas_sem_area(t) == eng42.subentradas_sem_area(t)
        assert eng.nuvens_baixas_secn2(t) == eng42.nuvens_baixas_secn2(t)


def test_arquivo_analise_completa_e_resto(eng, eng42):
    fich = _arquivo()
    if not fich:
        pytest.skip("arquivo (ramo dados) não disponível")
    indice = json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else None
    entradas = {e["ficheiro"]: e for e in (indice or {}).get("gamets", [])}
    for f in fich:
        texto = f.read_text(encoding="utf-8")
        m = re.match(r"(\d{8})T", f.name)
        if not m:
            continue
        ref = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
        ini, fim, _ = eng.parse_validity(texto, ref + timedelta(hours=12))
        if ini is None:
            continue
        entrada = entradas.get(str(f.relative_to(RAIZ / "dados")))
        for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3, minutes=30),
                      fim - timedelta(minutes=15)):
            for args, kw in ((("manual",), {}),
                             (("arquivo_hist",), {"indice": indice, "entrada": entrada})):
                if args[0] == "arquivo_hist" and not entrada:
                    continue
                novo = eng.analisar_gamet(texto, *args, agora=agora, **kw)
                antigo = eng42.analisar_gamet(texto, *args, agora=agora, **kw)
                assert novo["por_dec"] == antigo["por_dec"], f.name
                assert novo["avisos"] == antigo["avisos"], f.name
                assert [g["decision"] for g in novo["regioes"]] == \
                       [g["decision"] for g in antigo["regioes"]]
                assert (novo["resto"] is None) == (antigo["resto"] is None)
                if novo["resto"]:
                    assert novo["resto"]["decisao"] == antigo["resto"]["decisao"]
                _verifica_resto(eng, novo)


# --- Contra o motor da 4.2: subentradas geradas -------------------------------------

QUALS = ["", "", "W OF W00715 ", "N OF N4000 ", "S OF N3900 AND W OF W00800 ",
         "BTN N3840 AND N4000 ", "E OF W00800 ", "N OF N4100 AND E OF W00800 "]
SUPS = ["MAR", "LAN", "COT", "MAR AND COT", "COT AND LAN", "LAN AND MAR", "COT MAR"]
VALORES = {
    "SFC VIS": ["LCA 0200-5000M FG/BR", "0800M BR", "3000M RA", "LCA 1,5KM BR", "1200M BR",
                "2000M BR", "LCA 5000 RA"],
    "SIG CLD": ["LCA BKN 001-004/008HFT AGL", "BKN 004/010HFT AGL", "OVC 002/006HFT",
                "ISOL TCU/CB 020/XXXHFT AGL", "BKN 008/015HFT AMSL", "OCNL CB 030/XXXHFT AGL",
                "BKN 002/ABV 030HFT AGL", "SCT 010-020/030-040HFT AGL"],
    "SIGWX": ["ISOL TS", "OCNL TSRA", "SQL", "FZDZ", "FRQ CB", "ISOL EMBD TS"],
    "TURB": ["SEV SFC/FL080", "MOD SFC/FL050", "MOD ABV FL070", "SEV FL050/100 MOV E 10KT"],
    "ICE": ["SEV FL060/FL120", "MOD FL050/FL100"],
    "SFC WSPD": ["30KT", "25-35KT", "32KT", "20KT"],
    "MTW": ["SEV FL050/100", "MOD SFC/FL080"],
    "MT OBSC": ["", "BY CLD"],
}


def _jan(rng, h):
    return f"{h:02d}/{min(h + 2, 24):02d}"


def _subentrada(rng):
    campo = rng.choice(list(VALORES))
    val = lambda: rng.choice(VALORES[campo])  # noqa: E731
    h = rng.choice([9, 10, 11])
    jan0 = rng.choice(["", f"{_jan(rng, h)} "])
    sup0 = rng.choice(["", "", f"{rng.choice(SUPS)} "])
    lca0 = rng.choice(["", "", "", "LCA "])
    partes = [f"{jan0}{lca0}{rng.choice(QUALS)}{sup0}{val()}"]
    for _ in range(rng.choice([1, 1, 2])):
        h = min(h + rng.choice([1, 2]), 22)
        sep = rng.choice(["", "", "AND "])
        tipo = rng.choice(["sup", "valores", "valores", "sup_fim", "qual", "sup_qual", "lca"])
        if tipo == "sup":
            resto = f"{rng.choice(SUPS)} {val()}"
        elif tipo == "valores":
            resto = val()
        elif tipo == "sup_fim":
            resto = rng.choice(SUPS)
        elif tipo == "qual":
            resto = f"{rng.choice(QUALS[2:])}{val()}"
        elif tipo == "sup_qual":
            resto = f"{rng.choice(SUPS)} {rng.choice(QUALS[2:])}{val()}"
        else:
            resto = f"LCA {val()}"
        partes.append(f"{sep}{_jan(rng, h)} {resto}".rstrip())
    if rng.random() < 0.15:
        partes.append(f"{rng.choice(QUALS[2:])}{val()}")
    texto = " ".join(p for p in partes if p.strip())
    if rng.random() < 0.1:
        texto += f"\n{val()}"
    return f"{campo}{rng.choice([':', ': ', ' '])}{texto}"


def test_geradas_contra_4_2(eng, eng42):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "43")))
    n = int(os.environ.get("GAMET_CASOS", "300"))
    mudaram = partidos = com_resto = 0
    for k in range(n):
        corpo = " ".join(_subentrada(rng) for _ in range(rng.choice([1, 1, 2])))
        t = _g(corpo)
        novo, antigo = _comparar(eng, eng42, t, grelha=(k % 3 == 0))
        mudaram += novo != antigo
        partidos += any(eng._cortes_janela(l) for l in eng.normalize(corpo).splitlines())
        if k % 2 == 0:
            com_resto += _verifica_resto(eng, eng.analisar_gamet(t, agora=_t(12, 30)))
    # O gerador exercita de facto a mudança
    assert partidos > n // 2
    assert mudaram > 0
    assert com_resto > 0
