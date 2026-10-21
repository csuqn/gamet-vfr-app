"""
3.10 — Duas leituras optimistas que já existiam (confirmadas pelo revisor do
PR #22; pedido do Duarte a 21-out-2026). Nenhuma apareceu ainda num GAMET
real: os testes usam o GAMET real 201500/202100 (arquivo,
`20261020T1447Z_201500-202100_9641d0d85f.txt`) com a Secção I trocada.

1. MT OBSC e VA: até à 3.9 só a linha que abre o campo gerava bloco. Em
   "MT OBSC:N OF N4100 LAN S OF N3800 LAN" a parte a S de N3800 ficava fora
   da decisão (desde a 3.9 com o aviso "Campo não interpretado"). Agora cada
   subentrada com área gera o seu bloco, com a sua janela HH/HH.

2. "SFC VIS: LCA 1,5KM BR" era lido como 5000 m (a expressão dos KM apanhava
   o "5KM"). A vírgula decimal (`\\d,\\d+KM`) vale agora como ponto.
"""
import pytest

from conftest import build_gamet
from test_v37 import G201500, AGORA

SECN1 = "SIG CLD:19/21 N OF N4100 LCA BKN 008/010HTF AGL"
assert SECN1 in G201500


def _g(corpo):
    """GAMET real 201500 com a Secção I trocada."""
    return G201500.replace(SECN1, corpo, 1)


def _blocos(eng, texto, fen):
    blocos, *_ = eng.parse_gamet(texto)
    return [b for b in blocos if b.phenomenon == fen]


def _decisoes(eng, regioes):
    return {n: eng.find_region_for_point(regioes, la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _norte(eng, lat=41.02):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la > lat}


def _sul(eng, lat=37.98):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la < lat}


def _entre(eng, a, b):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if a + 0.02 < la < b - 0.02}


def _a_sul(b, lat):
    return b.polygon.bounds[3] <= lat + 1e-6


def _a_norte(b, lat):
    return b.polygon.bounds[1] >= lat - 1e-6


# ---------------------------------------------------------------------
# 1. MT OBSC e VA com várias subentradas
# ---------------------------------------------------------------------

def test_mt_obsc_duas_subentradas_lan(eng, analyse):
    g = _g("MT OBSC:N OF N4100 LAN S OF N3800 LAN")
    mt = _blocos(eng, g, "MT_OBSC")
    assert len(mt) == 2, mt
    assert any(_a_norte(b, 41.0) for b in mt)
    assert any(_a_sul(b, 38.0) for b in mt), "a 2.ª subentrada tem de gerar bloco"
    lan = eng.surface_polygon("LAN")
    for b in mt:
        assert b.surface == "LAN"
        assert b.polygon.difference(lan).area < 1e-6
    d = _decisoes(eng, analyse(g)["regions"])
    assert {d[n] for n in _norte(eng) | _sul(eng)} == {"NO-GO"}
    assert {d[n] for n in _entre(eng, 38.0, 41.0)} == {"GO"}
    assert eng.campos_nao_interpretados(g) == []


def test_mt_obsc_duas_subentradas_sem_janela_nem_superficie(eng, analyse):
    g = _g("MT OBSC:N OF N4100 LCA S OF N3800 LCA")
    mt = _blocos(eng, g, "MT_OBSC")
    assert len(mt) == 2
    assert all(b.window == "" for b in mt)
    d = _decisoes(eng, analyse(g)["regions"])
    assert {d[n] for n in _sul(eng)} == {"NO-GO"}
    assert eng.campos_nao_interpretados(g) == []


def test_mt_obsc_tres_subentradas_com_janela(eng, analyse):
    g = _g("MT OBSC:N OF N4100 LAN 17/19 BTN N3900 AND N4000 LAN 19/21 S OF N3800 MAR")
    mt = _blocos(eng, g, "MT_OBSC")
    norte = [b for b in mt if _a_norte(b, 41.0)]
    meio = [b for b in mt if _a_norte(b, 39.0) and _a_sul(b, 40.0)]
    sul = [b for b in mt if _a_sul(b, 38.0)]
    assert len(norte) == 1 and len(meio) == 1 and len(sul) == 1, mt
    assert norte[0].window == ""
    assert meio[0].window == "17–19Z"
    assert sul[0].window == "19–21Z"
    assert sul[0].surface == "MAR"
    assert sul[0].polygon.intersection(eng.surface_polygon("LAN")).area < 1e-6
    # Antes das 17Z a faixa do meio está GO; nas 17–19Z está NO-GO
    d = _decisoes(eng, analyse(g)["regions"])
    assert {d[n] for n in _entre(eng, 39.0, 40.0)} == {"NO-GO"}
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}
    assert eng.campos_nao_interpretados(g) == []


def test_mt_obsc_janela_antes_da_primeira_subentrada(eng):
    """"MT OBSC:17/19 N OF N4100 LAN 19/21 S OF N3800 LAN": a 2.ª subentrada
    gera bloco com a sua janela. (A linha que abre o campo, vazia, dava MT
    OBSC em toda a FIR até à 3.10; desde a 3.11 já não — test_v311.)"""
    g = _g("MT OBSC:17/19 N OF N4100 LAN 19/21 S OF N3800 LAN")
    mt = _blocos(eng, g, "MT_OBSC")
    norte = [b for b in mt if _a_norte(b, 41.0)]
    sul = [b for b in mt if _a_sul(b, 38.0)]
    assert [b.window for b in norte] == ["17–19Z"]
    assert [b.window for b in sul] == ["19–21Z"]
    assert not any(b.polygon.equals(eng.FIR_POLYGON) for b in mt)   # 3.11
    assert eng.campos_nao_interpretados(g) == []


def test_va_duas_subentradas(eng, analyse):
    g = _g("VA: N OF N4100 LCA S OF N3800 LCA")
    va = _blocos(eng, g, "VA")
    assert len(va) == 2
    assert any(_a_norte(b, 41.0) for b in va)
    assert any(_a_sul(b, 38.0) for b in va)
    d = _decisoes(eng, analyse(g)["regions"])
    assert {d[n] for n in _norte(eng) | _sul(eng)} == {"NO-GO"}
    assert {d[n] for n in _entre(eng, 38.0, 41.0)} == {"GO"}
    assert eng.campos_nao_interpretados(g) == []


def test_va_em_sigwx_continua_conservador(eng, analyse):
    """VA dentro de SIGWX abre o campo VA (quebra injectada antes de "VA"):
    é lido em toda a FIR, como até à 3.9."""
    for corpo in ("SIGWX: S OF N3800 VA", "SIGWX: N OF N4100 ISOL TS VA S OF N3800 VA"):
        g = _g(corpo)
        assert any(b.polygon.equals(eng.FIR_POLYGON) for b in _blocos(eng, g, "VA"))
        assert set(_decisoes(eng, analyse(g)["regions"]).values()) == {"NO-GO"}


@pytest.mark.parametrize("corpo, fen", [
    ("MT OBSC: N OF N4100", "MT_OBSC"),
    ("MT OBSC: N OF N4100 LAN", "MT_OBSC"),
    ("VA: N OF N4000", "VA"),
    ("MT OBSC: ENTIRE FIR", "MT_OBSC"),
])
def test_uma_subentrada_inalterada(eng, corpo, fen):
    blocos = _blocos(eng, _g(corpo), fen)
    assert len(blocos) == 1


def test_mt_obsc_qualificador_fora_da_fir_descarta(eng):
    g = _g("MT OBSC:N OF N4100 LAN N OF N4300 LAN")   # FIR acaba em N42°09'
    mt = _blocos(eng, g, "MT_OBSC")
    assert len(mt) == 1 and _a_norte(mt[0], 41.0)
    assert eng.campos_nao_interpretados(g) == []


def test_mt_obsc_entire_fir_na_segunda_subentrada(eng):
    """ENTIRE FIR no início de linha (quebra do próprio texto) é toda a FIR,
    sem aviso de área."""
    g = _g("MT OBSC:N OF N4100 LAN\nENTIRE FIR LAN")
    mt = _blocos(eng, g, "MT_OBSC")
    terra = eng.surface_polygon("LAN").intersection(eng.FIR_POLYGON)
    assert len(mt) == 2
    assert any(b.polygon.symmetric_difference(terra).area < 1e-6 for b in mt)
    assert eng.subentradas_sem_area(g) == []
    assert eng.campos_nao_interpretados(g) == []


@pytest.mark.parametrize("corpo", [
    "MT OBSC:N OF N4100 LAN NW OF W00800 LAN",
    "MT OBSC:N OF N4100 LAN BTN N3900 ~ N3800 LAN",
])
def test_mt_obsc_area_ilegivel_toda_a_fir_com_aviso(eng, analyse, corpo):
    g = _g(corpo)
    assert eng.subentradas_sem_area(g)
    d = _decisoes(eng, analyse(g)["regions"])
    assert set(d.values()) == {"NO-GO"}


def test_gamet_real_inalterado(eng, analyse):
    assert _decisoes(eng, analyse(G201500)["regions"]) == \
        {n: "GO" for n in eng.AERODROMES}


# ---------------------------------------------------------------------
# 2. Vírgula decimal nos KM
# ---------------------------------------------------------------------

def _vis(eng, corpo):
    return sorted(b.value for b in _blocos(eng, _g(corpo), "VIS"))


@pytest.mark.parametrize("corpo, esperado", [
    ("SFC VIS: LCA 1,5KM BR", [1500]),
    ("SFC VIS: LCA 0,8KM FG", [800]),
    ("SFC VIS: N OF N4100 LCA 1,5 KM BR", [1500]),
    ("SFC VIS: 2,5KM RA", [2500]),
    ("SIG VIS: LCA 1,5KM BR", [1500]),
    ("SFC VIS: LCA 1.5KM BR", [1500]),            # ponto: inalterado
    ("SFC VIS: LCA 5KM RA", [5000]),              # inteiro: inalterado
    ("SFC VIS: LCA 1500-5000M BR", [1500]),       # inalterado
])
def test_km_com_virgula_decimal(eng, corpo, esperado):
    assert _vis(eng, corpo) == esperado


@pytest.mark.parametrize("corpo, esperado", [
    # Vírgula seguida de espaço: separa valores
    ("SFC VIS: LCA 0800M BR, 5KM RA", [800, 5000]),
    # Vírgula entre unidade e número: separa valores
    ("SFC VIS: LCA 1200M,5KM RA", [1200, 5000]),
    # Parte inteira de 4 algarismos não é um decimal de KM
    ("SFC VIS: LCA 2500,5KM RA", [2500, 5000]),
])
def test_virgula_que_nao_e_decimal(eng, corpo, esperado):
    assert _vis(eng, corpo) == esperado


@pytest.mark.parametrize("corpo, decisao", [
    ("SFC VIS: LCA 1,5KM BR", "MARGINAL"),
    ("SFC VIS: LCA 0,8KM FG", "MARGINAL"),        # LCA < 1500 → MARGINAL
    ("SFC VIS: 0,8KM FG", "NO-GO"),
    ("SFC VIS: 2,5KM RA", "MARGINAL"),
])
def test_km_com_virgula_decisao(eng, analyse, corpo, decisao):
    d = _decisoes(eng, analyse(_g(corpo))["regions"])
    assert set(d.values()) == {decisao}


def test_km_com_virgula_no_briefing(eng):
    r = eng.analisar_gamet(_g("SFC VIS: LCA 1,5KM BR"), "manual", agora=AGORA)
    assert set(_decisoes(eng, r["regioes"]).values()) == {"MARGINAL"}


def test_build_gamet_sintetico(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4000 LCA 1,5KM BR")
    vis = [b.value for b in _blocos(eng, g, "VIS")]
    assert vis == [1500]
