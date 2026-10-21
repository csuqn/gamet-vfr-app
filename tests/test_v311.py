"""
3.11 — Duas leituras que já existiam (confirmadas pelo revisor do PR #23;
pedido do Duarte a 21-out-2026). Nenhuma apareceu ainda num GAMET real: os
testes usam o GAMET real 201500/202100 (arquivo,
`20261020T1447Z_201500-202100_9641d0d85f.txt`) com a Secção I trocada.

1. `ENTIRE FIR` a meio de uma linha era ignorado (erro OPTIMISTA): em
   "MT OBSC: N OF N4100 LAN ENTIRE FIR" a área ficava só a N de N4100 (41
   aeródromos GO). Por decisão do Duarte injecta-se agora uma quebra antes de
   `ENTIRE FIR` (com a janela HH/HH que o precede), em todos os campos da
   Secção I. Uma subentrada `ENTIRE FIR` sem janela vale para todo o período.
   `… AND ENTIRE FIR` não é junção: toda a FIR (leitura conservadora).

2. A linha que abre o campo MT OBSC (ou `VA:`) vazia — só a janela, ou nada,
   porque a janela/qualificador passou para a linha seguinte — dava sempre um
   bloco de toda a FIR em todo o período ("MT OBSC:17/19 N OF N4100 LAN" →
   toda a FIR). Esse bloco só sai quando a linha de abertura é vazia/só
   janela/só pontuação, é a única linha da sua subentrada e uma subentrada
   seguinte do mesmo campo gera o seu bloco. Tudo o resto fica igual.
   `MT OBSC: NIL` / `VA: NIL` não mudam (questão à espera do Duarte); "VA"
   sem dois pontos (VA dentro de SIGWX) não muda.
"""
import pytest

from test_v37 import G201500, AGORA

SECN1 = "SIG CLD:19/21 N OF N4100 LCA BKN 008/010HTF AGL"
assert SECN1 in G201500


def _g(corpo):
    """GAMET real 201500 com a Secção I trocada."""
    return G201500.replace(SECN1, corpo, 1)


def _blocos(eng, texto, fen=None):
    blocos, *_ = eng.parse_gamet(texto)
    return [b for b in blocos if fen is None or b.phenomenon == fen]


def _decisoes(eng, texto):
    regioes = eng.compute_dynamic_regions(_blocos(eng, texto))
    return {n: eng.find_region_for_point(regioes, la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _toda(eng, b):
    return b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6


def _a_sul(b, lat):
    return b.polygon.bounds[3] <= lat + 1e-6


def _a_norte(b, lat):
    return b.polygon.bounds[1] >= lat - 1e-6


def _norte(eng, lat=41.02):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la > lat}


def _sul(eng, lat=37.98):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la < lat}


# ---------------------------------------------------------------------
# 1. ENTIRE FIR a meio da linha
# ---------------------------------------------------------------------

def test_mt_obsc_entire_fir_a_meio_da_linha(eng):
    """O caso do revisor: 41 GO / 11 NO-GO até à 3.10; deve dar 52 NO-GO."""
    g = _g("MT OBSC: N OF N4100 LAN ENTIRE FIR")
    mt = _blocos(eng, g, "MT_OBSC")
    assert any(_toda(eng, b) and b.window == "" for b in mt), mt
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.subentradas_sem_area(g) == []
    assert eng.campos_nao_interpretados(g) == []


def test_mt_obsc_entire_fir_com_janela(eng):
    """A subentrada "19/21 ENTIRE FIR" já não se perde, e a janela não passa
    para a subentrada anterior (S OF N3800 LAN vale todo o período)."""
    g = _g("MT OBSC: S OF N3800 LAN 19/21 ENTIRE FIR")
    mt = _blocos(eng, g, "MT_OBSC")
    sul = [b for b in mt if _a_sul(b, 38.0)]
    toda = [b for b in mt if _toda(eng, b)]
    assert [b.window for b in sul] == [""]
    assert [b.surface for b in sul] == ["LAN"]
    assert [b.window for b in toda] == ["19–21Z"]
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


def test_entire_fir_sem_janela_nao_herda_a_anterior(eng):
    """Uma subentrada sem janela vale para todo o período."""
    g = _g("MT OBSC:17/19 N OF N4100 LAN ENTIRE FIR")
    toda = [b for b in _blocos(eng, g, "MT_OBSC") if _toda(eng, b)]
    assert [b.window for b in toda] == [""]


@pytest.mark.parametrize("corpo, fen, valor", [
    ("SIG CLD: N OF N4100 BKN 010HFT AGL ENTIRE FIR BKN 002HFT AGL", "BASE_AGL", 200),
    ("SFC VIS: N OF N4100 5000M RA ENTIRE FIR 1000M BR", "VIS", 1000),
    ("SIGWX: N OF N4100 ISOL TS ENTIRE FIR OCNL TS", "TS", "OCNL"),
    ("TURB: N OF N4100 MOD FL050/FL100 ENTIRE FIR SEV SFC/FL080", "TURB", "SEV"),
    ("ICE: N OF N4100 MOD FL080/FL120 ENTIRE FIR SEV FL050/FL100", "ICE", "SEV"),
    ("MTW: N OF N4100 MOD FL080 ENTIRE FIR SEV SFC/FL100", "MTW", "SEV"),
    ("SFC WSPD: N OF N4100 25KT ENTIRE FIR 35KT", "WSPD", 35),
    ("VA: N OF N4100 LAN ENTIRE FIR", "VA", "VA"),
    ("MT OBSC: N OF N4100 MAR ENTIRE FIR", "MT_OBSC", "MT OBSC"),
])
def test_entire_fir_a_meio_em_todos_os_campos(eng, corpo, fen, valor):
    g = _g(corpo)
    blocos = [b for b in _blocos(eng, g, fen) if b.value == valor]
    assert any(_toda(eng, b) and b.window == "" for b in blocos), blocos
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.subentradas_sem_area(g) == []
    assert eng.campos_nao_interpretados(g) == []


def test_entire_fir_a_meio_com_janela_noutro_campo(eng):
    g = _g("SIG CLD: N OF N4100 BKN 010HFT AGL 19/21 ENTIRE FIR BKN 002HFT AGL")
    bases = {b.value: b for b in _blocos(eng, g, "BASE_AGL")}
    assert set(bases) == {1000, 200}
    assert _toda(eng, bases[200]) and bases[200].window == "19–21Z"
    assert _a_norte(bases[1000], 41.0) and bases[1000].window == ""


def test_entire_fir_lan_a_seguir(eng):
    """"ENTIRE FIR LAN": toda a terra da FIR (a superfície da subentrada)."""
    g = _g("MT OBSC: N OF N4100 MAR ENTIRE FIR LAN")
    terra = eng.surface_polygon("LAN").intersection(eng.FIR_POLYGON)
    mt = _blocos(eng, g, "MT_OBSC")
    assert any(b.surface == "LAN" and b.polygon.symmetric_difference(terra).area < 1e-6
               for b in mt), mt
    assert any(b.surface == "MAR" and _a_norte(b, 41.0) for b in mt)
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}   # aeródromos em terra


def test_entire_fir_mar_a_seguir(eng):
    g = _g("SIG CLD: N OF N4100 LAN BKN 010HFT AGL ENTIRE FIR MAR BKN 002HFT AGL")
    b200 = [b for b in _blocos(eng, g, "BASE_AGL") if b.value == 200]
    mar = eng.surface_polygon("MAR").intersection(eng.FIR_POLYGON)
    assert len(b200) == 1 and b200[0].surface == "MAR"
    assert b200[0].polygon.symmetric_difference(mar).area < 1e-6


def test_entire_fir_depois_de_and_toda_a_fir(eng):
    """"N OF N4100 AND ENTIRE FIR": não é junção de qualificadores — leitura
    conservadora, toda a FIR."""
    g = _g("MT OBSC: N OF N4100 AND ENTIRE FIR")
    assert any(_toda(eng, b) for b in _blocos(eng, g, "MT_OBSC"))
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}

    g = _g("SIG CLD: N OF N4100 AND ENTIRE FIR BKN 002HFT AGL")
    b200 = [b for b in _blocos(eng, g, "BASE_AGL") if b.value == 200]
    assert len(b200) == 1 and _toda(eng, b200[0])
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    # O resto da linha ("N OF N4100 AND") fica sem fenómeno e avisa.
    assert eng.campos_nao_interpretados(g) == ["SIG CLD: N OF N4100 AND"]


@pytest.mark.parametrize("corpo, fen, janela", [
    ("MT OBSC: ENTIRE FIR", "MT_OBSC", ""),
    ("MT OBSC:ENTIRE FIR", "MT_OBSC", ""),
    ("MT OBSC ENTIRE FIR", "MT_OBSC", ""),
    ("MT OBSC:19/21 ENTIRE FIR", "MT_OBSC", "19–21Z"),
    ("MT OBSC 19/21 ENTIRE FIR", "MT_OBSC", "19–21Z"),
    ("VA: ENTIRE FIR", "VA", ""),
    ("SIG CLD: ENTIRE FIR BKN 002HFT AGL", "BASE_AGL", ""),
    ("SIG CLD ENTIRE FIR BKN 002HFT AGL", "BASE_AGL", ""),
    ("SIG CLD:19/21 ENTIRE FIR BKN 002HFT AGL", "BASE_AGL", "19–21Z"),
    ("SFC VIS: ENTIRE FIR 1000M BR", "VIS", ""),
])
def test_entire_fir_no_inicio_do_campo_inalterado(eng, corpo, fen, janela):
    g = _g(corpo)
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1, blocos
    assert _toda(eng, blocos[0]) and blocos[0].window == janela
    assert eng.subentradas_sem_area(g) == []
    assert eng.campos_nao_interpretados(g) == []


def test_entire_fir_em_inicio_de_linha_inalterado(eng):
    """A quebra do próprio texto antes de ENTIRE FIR já funcionava (3.4)."""
    g = _g("SIG CLD:S OF N3800 LCA BKN 010HFT AGL\nENTIRE FIR LCA BKN 002HFT AGL")
    bases = {b.value: b for b in _blocos(eng, g, "BASE_AGL")}
    assert _toda(eng, bases[200]) and _a_sul(bases[1000], 38.0)
    assert eng.subentradas_sem_area(g) == []


def test_sigmet_com_entire_fir_a_meio_ja_e_toda_a_area(eng):
    """A área do SIGMET é outra função e não tinha o problema."""
    texto = ("LPPC SIGMET 7 VALID 201500/201900 LPPT- LPPC LISBOA FIR "
             "SEV TURB FCST N OF N4000 ENTIRE FIR SFC/FL080 STNR NC")
    assert eng.area_sigmet(texto)[0] is None


def test_gamet_real_inalterado(eng):
    assert _decisoes(eng, G201500) == {n: "GO" for n in eng.AERODROMES}


# ---------------------------------------------------------------------
# 2. Linha de abertura vazia em MT OBSC / VA
# ---------------------------------------------------------------------

@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_so_com_janela(eng, campo, fen):
    """"MT OBSC:17/19 N OF N4100 LAN": só a N de N4100, terra, 17–19Z."""
    g = _g(f"{campo}17/19 N OF N4100 LAN")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1, blocos
    assert _a_norte(blocos[0], 41.0)
    assert blocos[0].window == "17–19Z" and blocos[0].surface == "LAN"
    d = _decisoes(eng, g)
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}
    assert {d[n] for n in _sul(eng, 40.9)} == {"GO"}
    assert eng.campos_nao_interpretados(g) == []


def test_abertura_mt_obsc_sem_dois_pontos(eng):
    """"MT OBSC S OF N3900": só a S de N3900."""
    g = _g("MT OBSC S OF N3900")
    mt = _blocos(eng, g, "MT_OBSC")
    assert len(mt) == 1 and _a_sul(mt[0], 39.0)
    d = _decisoes(eng, g)
    assert {d[n] for n in _norte(eng, 39.02)} == {"GO"}
    assert {d[n] for n in _sul(eng, 38.98)} == {"NO-GO"}


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_vazia_duas_subentradas(eng, campo, fen):
    g = _g(f"{campo}17/19 N OF N4100 LAN 19/21 S OF N3800 LAN")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 2 and not any(_toda(eng, b) for b in blocos)
    assert sorted(b.window for b in blocos) == ["17–19Z", "19–21Z"]
    d = _decisoes(eng, g)
    meio = {n for n, (la, _lo) in eng.AERODROMES.items() if 38.02 < la < 40.98}
    assert {d[n] for n in meio} == {"GO"}


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_vazia_com_subentrada_de_area_ilegivel(eng, campo, fen):
    """A subentrada seguinte sem área legível já dá toda a FIR, com aviso."""
    g = _g(f"{campo}17/19 N OF N4100 LAN NW OF W00800")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and blocos[0].window == "17–19Z"
    terra = eng.surface_polygon("LAN").intersection(eng.FIR_POLYGON)
    assert blocos[0].polygon.symmetric_difference(terra).area < 1e-6
    assert eng.subentradas_sem_area(g)
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_vazia_com_entire_fir_a_seguir(eng, campo, fen):
    g = _g(f"{campo}19/21 ENTIRE FIR")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and _toda(eng, blocos[0]) and blocos[0].window == "19–21Z"


# ---- Casos que não mudam ----

@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_com_conteudo_inalterada(eng, campo, fen):
    """"MT OBSC: LAN": toda a terra da FIR."""
    g = _g(f"{campo} LAN")
    blocos = _blocos(eng, g, fen)
    terra = eng.surface_polygon("LAN").intersection(eng.FIR_POLYGON)
    assert len(blocos) == 1
    assert blocos[0].polygon.symmetric_difference(terra).area < 1e-6
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_seguida_de_outro_campo_inalterada(eng, campo, fen):
    """"MT OBSC:" seguido directamente de outro campo: toda a FIR."""
    g = _g(f"{campo} SFC VIS: N OF N4100 5000M RA")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and _toda(eng, blocos[0])
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_so_com_janela_e_nada_mais_inalterada(eng, campo, fen):
    g = _g(f"{campo}17/19")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and _toda(eng, blocos[0]) and blocos[0].window == "17–19Z"


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_uma_subentrada_na_abertura_inalterada(eng, campo, fen):
    g = _g(f"{campo} N OF N4100 LAN")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and _a_norte(blocos[0], 41.0)


@pytest.mark.parametrize("campo, fen", [("MT OBSC:", "MT_OBSC"), ("VA:", "VA")])
def test_abertura_vazia_e_subentrada_fora_da_fir_inalterada(eng, campo, fen):
    """A única subentrada cai fora da FIR (descartada): fica o bloco de toda a
    FIR da linha de abertura, como até à 3.10 (conservador)."""
    g = _g(f"{campo}17/19 N OF N4300")
    blocos = _blocos(eng, g, fen)
    assert len(blocos) == 1 and _toda(eng, blocos[0])


def test_abertura_vazia_com_continuacao_inalterada(eng):
    """Linha sem qualificador a seguir à abertura ("LAN") pertence à
    subentrada de abertura: fica o bloco de toda a FIR."""
    g = _g("MT OBSC:\nLAN\nN OF N4100")
    mt = _blocos(eng, g, "MT_OBSC")
    assert any(_toda(eng, b) for b in mt)
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


@pytest.mark.parametrize("corpo", [
    "SIGWX: VA S OF N3800 ISOL TS",
    "SIGWX: S OF N3800 VA",
    "VA S OF N3900",
])
def test_va_sem_dois_pontos_inalterado(eng, corpo):
    """"VA" sem dois pontos é o VA dentro de SIGWX: continua em toda a FIR."""
    g = _g(corpo)
    assert any(_toda(eng, b) for b in _blocos(eng, g, "VA"))
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


@pytest.mark.parametrize("corpo, fen", [
    ("MT OBSC: NIL", "MT_OBSC"),
    ("VA: NIL", "VA"),
    ("MT OBSC: NIL N OF N4100", "MT_OBSC"),
])
def test_nil_nao_mexe(eng, corpo, fen):
    """NIL fica como na 3.10 (questão à espera do Duarte): toda a FIR."""
    assert any(_toda(eng, b) for b in _blocos(eng, _g(corpo), fen))
