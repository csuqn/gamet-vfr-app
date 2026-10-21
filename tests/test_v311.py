"""
3.11 — Uma leitura optimista que já existia (confirmada pelo revisor do PR
#23; pedido do Duarte a 21-out-2026) e duas que ficam como estavam. Nenhuma
apareceu ainda num GAMET real: os
testes usam o GAMET real 201500/202100 (arquivo,
`20261020T1447Z_201500-202100_9641d0d85f.txt`) com a Secção I trocada.

1. `ENTIRE FIR` a meio de uma linha era ignorado (erro OPTIMISTA): em
   "MT OBSC: N OF N4100 LAN ENTIRE FIR" a área ficava só a N de N4100 (41
   aeródromos GO). A linha continua a ser lida inteira como na 3.10 e cada
   parte "[HH/HH] ENTIRE FIR …" é lida a mais, como subentrada de toda a FIR
   (com a sua janela e superfície); uma parte sem fenómeno próprio alarga a
   linha a toda a FIR. Nunca mais permissivo do que a 3.10 (casos do revisor
   do PR #24 abaixo; prova geral em test_v311_contra_310.py).

2. `MT OBSC: NIL` / `VA: NIL` e a linha de abertura vazia de MT OBSC/VA
   continuam a dar toda a FIR, como na 3.10 (decisão do Duarte a 21-out-2026:
   mais vale conservador do que permissivo).
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
    # A linha real fica como na 3.10 (janela lida nos primeiros 24
    # caracteres, aqui a da parte); a parte virtual dá toda a FIR 19–21Z.
    assert [b.window for b in sul] == ["19–21Z"]
    assert [b.surface for b in sul] == ["LAN"]
    assert [b.window for b in toda] == ["19–21Z"]
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}


def test_entire_fir_sem_janela_nao_herda_a_anterior(eng):
    """Uma subentrada sem janela vale para todo o período."""
    g = _g("MT OBSC: S OF N3800 LAN 17/19 N OF N4100 LAN ENTIRE FIR")
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
    """"ENTIRE FIR LAN": a parte virtual dá toda a terra da FIR; a linha
    inteira continua lida como na 3.10 (N de N4100, superfície LAN/MAR)."""
    g = _g("MT OBSC: N OF N4100 MAR ENTIRE FIR LAN")
    terra = eng.surface_polygon("LAN").intersection(eng.FIR_POLYGON)
    mt = _blocos(eng, g, "MT_OBSC")
    assert any(b.surface == "LAN" and b.polygon.symmetric_difference(terra).area < 1e-6
               for b in mt), mt
    assert any(b.surface == "LAN/MAR" and _a_norte(b, 41.0) for b in mt)
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}   # aeródromos em terra


def test_entire_fir_mar_a_seguir(eng):
    g = _g("SIG CLD: N OF N4100 LAN BKN 010HFT AGL ENTIRE FIR MAR BKN 002HFT AGL")
    b200 = [b for b in _blocos(eng, g, "BASE_AGL") if b.value == 200]
    mar = eng.surface_polygon("MAR").intersection(eng.FIR_POLYGON)
    virtual = [b for b in b200 if b.surface == "MAR"]
    assert len(virtual) == 1
    assert virtual[0].polygon.symmetric_difference(mar).area < 1e-6
    # A linha inteira, como na 3.10: 200 ft a N de N4100 (terra e mar)
    assert any(b.surface == "LAN/MAR" and _a_norte(b, 41.0) for b in b200)
    d = _decisoes(eng, g)
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}


def test_entire_fir_depois_de_and_toda_a_fir(eng):
    """"N OF N4100 AND ENTIRE FIR": não é junção de qualificadores — leitura
    conservadora, toda a FIR."""
    g = _g("MT OBSC: N OF N4100 AND ENTIRE FIR")
    assert any(_toda(eng, b) for b in _blocos(eng, g, "MT_OBSC"))
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}

    g = _g("SIG CLD: N OF N4100 AND ENTIRE FIR BKN 002HFT AGL")
    b200 = [b for b in _blocos(eng, g, "BASE_AGL") if b.value == 200]
    assert any(_toda(eng, b) for b in b200)
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.campos_nao_interpretados(g) == []


# ---- Casos do revisor do PR #24: nunca mais permissivo do que a 3.10 ----

def test_revisor_diagonal_depois_de_entire_fir(eng):
    """Na 3.10 a diagonal deixa a linha sem área → OCNL TS em toda a FIR, com
    aviso. Tem de continuar assim (no 979aeeb o OCNL TS ficava só a N de
    N4100 e o aviso desaparecia)."""
    corpo = "SIGWX: N OF N4100 OCNL TS ENTIRE FIR SW OF W00800 ISOL TS"
    g = _g(corpo)
    ts = _blocos(eng, g, "TS")
    assert any(b.value == "OCNL" and _toda(eng, b) for b in ts), ts
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.subentradas_sem_area(g) == [corpo]


@pytest.mark.parametrize("corpo", [
    "SIGWX: S OF N3800 LAN OCNL TS ENTIRE FIR MAR ISOL TS",
    "SIG CLD: S OF N3800 LAN BKN 002HFT AGL ENTIRE FIR MAR BKN 040HFT AGL",
    "SFC VIS: S OF N3800 LAN 1000M FG ENTIRE FIR MAR 4000M RA",
])
def test_revisor_superficies_diferentes(eng, corpo):
    """A linha inteira (superfície LAN/MAR, como na 3.10) mantém o NO-GO a S
    de N3800; a parte ENTIRE FIR MAR é lida a mais."""
    g = _g(corpo)
    d = _decisoes(eng, g)
    assert {d[n] for n in _sul(eng)} == {"NO-GO"}
    assert any(_a_sul(b, 38.0) and b.surface == "LAN/MAR" for b in _blocos(eng, g))


def test_revisor_entire_fir_no_fim_da_linha(eng):
    """"TURB: SEV SFC/FL050 ENTIRE FIR": a linha inteira é lida outra vez em
    toda a FIR, sem "Campo não interpretado"."""
    g = _g("TURB: N OF N4100 SEV SFC/FL050 ENTIRE FIR")
    turb = _blocos(eng, g, "TURB")
    assert len(turb) == 2 and any(_toda(eng, b) for b in turb)
    assert any(_a_norte(b, 41.0) for b in turb)          # a leitura da 3.10
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.campos_nao_interpretados(g) == []
    assert eng.subentradas_sem_area(g) == []


def test_revisor_janela_em_inicio_de_linha(eng):
    """"SIG CLD:\n19/21 ENTIRE FIR …" não perde a janela."""
    g = _g("SIG CLD:\n19/21 ENTIRE FIR BKN 002HFT AGL")
    b = _blocos(eng, g, "BASE_AGL")
    assert len(b) == 1 and _toda(eng, b[0]) and b[0].window == "19–21Z"


@pytest.mark.parametrize("corpo, fen, valor", [
    ("SIGWX: N OF N4100 LAN ISOL TS 19/21 ENTIRE FIR ISOL TS\nSEV SQL", "WX", "SQL"),
    ("SIG CLD: N OF N4100 BKN 010HFT AGL 17/18 ENTIRE FIR BKN 030HFT AGL\nOVC 002HFT AGL",
     "BASE_AGL", 200),
])
def test_revisor_linha_seguinte_herda_como_na_3_10(eng, corpo, fen, valor):
    """2.ª revisão do PR #24: a parte virtual "HH/HH ENTIRE FIR" não muda a
    janela nem a área que a linha seguinte (sem qualificador) herda. Como na
    3.10: a N de N4100, em todo o período (no 7789689 ficava em toda a FIR, só
    na janela da parte — "ainda não começou" no LPPR às 16Z)."""
    g = _g(corpo)
    b = [x for x in _blocos(eng, g, fen) if x.value == valor]
    assert len(b) == 1, b
    assert b[0].window == ""
    assert _a_norte(b[0], 41.0)
    d = _decisoes(eng, g)
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}


def test_linha_descartada_na_3_10_continua_descartada(eng):
    """Na 3.10 "17/19 … E OF W00800 … COT" ficava sem área (descartada antes
    de ler a janela) e as linhas seguintes herdavam N OF N4000 ∩ E OF W00800
    em todo o período. A linha real fica igual; a cópia virtual "toda" (por
    causa do "ENTIRE FIR AND" sem fenómeno) dá o SEV na faixa costeira."""
    g = _g("MTW: 17/19 N OF N4000 AND E OF W00800 SEV SFC/FL100 ENTIRE FIR AND "
           "ENTIRE FIR COT SEV SFC/FL100\nMOD FL080\nSEV SFC/FL100")
    mtw = _blocos(eng, g, "MTW")
    seguintes = [b for b in mtw if b.surface == ""]
    assert sorted(b.value for b in seguintes) == ["MOD", "SEV"]
    assert all(b.window == "" and _a_norte(b, 40.0) for b in seguintes)
    costa = [b for b in mtw if b.surface == "COT"]
    assert costa and all(b.value == "SEV" for b in costa)


@pytest.mark.parametrize("corpo, fen, valor, janela", [
    # 3.ª revisão do PR #24: a janela colada à parte ENTIRE FIR numa linha de
    # continuação é, como na 3.10, a janela da linha inteira.
    ("SIG CLD: 15/17 N OF N4100 BKN 030HFT AGL\nOVC 002HFT 19/21 ENTIRE FIR BKN 040HFT AGL",
     "BASE_AGL", 200, "19–21Z"),
    ("SIGWX: 15/17 N OF N4100 ISOL TS\nSEV SQL 19/21 ENTIRE FIR ISOL TS", "WX", "SQL", "19–21Z"),
    ("SIGWX: 15/17 N OF N4100 ISOL TS\nFRQ TS ENTIRE FIR 19/21 ISOL TS", "TS", "FRQ", "19–21Z"),
    ("SFC VIS: 15/17 N OF N4100 5000M RA\n1000M FG 18/20 ENTIRE FIR 4000M BR", "VIS", 1000,
     "18–20Z"),
    ("MTW: 16/20 E OF W00800 MOD FL080\nSEV SFC/FL100 19/21 ENTIRE FIR MOD FL080", "MTW", "SEV",
     "19–21Z"),
])
def test_revisor_janela_da_linha_de_continuacao_como_na_3_10(eng, corpo, fen, valor, janela):
    g = _g(corpo)
    b = [x for x in _blocos(eng, g, fen) if x.value == valor and not _toda(eng, x)]
    assert [x.window for x in b] == [janela], b


def test_area_alargada_mantem_aviso(eng):
    """O aviso "Área alargada" (3.5) da linha inteira mantém-se."""
    g = _g("SIG CLD: S BTN N3720 - N3800 BKN 002HFT AGL ENTIRE FIR BKN 040HFT AGL")
    assert [l for _, l in eng.subentradas_alargadas(g)] == ["S OF N3800"]
    assert any(_toda(eng, b) and b.value == 4000 for b in _blocos(eng, g, "BASE_AGL"))


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
# 2. MT OBSC / VA: NIL e abertura vazia continuam a dar toda a FIR
# ---------------------------------------------------------------------
# Decisão do Duarte (21-out-2026): mais vale conservador do que permissivo.
# Estas leituras ficam como na 3.10 (as correcções propostas no PR #24 foram
# retiradas por tornarem decisões mais permissivas).

@pytest.mark.parametrize("corpo, fen", [
    ("MT OBSC: NIL", "MT_OBSC"),
    ("MT OBSC:NIL", "MT_OBSC"),
    ("MT OBSC: 17/19 NIL", "MT_OBSC"),
    ("VA: NIL", "VA"),
    ("VA: 19/21 NIL", "VA"),
])
def test_nil_continua_toda_a_fir(eng, corpo, fen):
    g = _g(corpo)
    assert any(_toda(eng, b) for b in _blocos(eng, g, fen))
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
    assert eng.campos_nao_interpretados(g) == []


@pytest.mark.parametrize("corpo, fen", [
    ("MT OBSC:17/19 N OF N4100 LAN", "MT_OBSC"),
    ("MT OBSC S OF N3900", "MT_OBSC"),
    ("MT OBSC:17/19 N OF N4100 LAN 19/21 S OF N3800 LAN", "MT_OBSC"),
    ("VA:17/19 N OF N4100 LAN", "VA"),
    ("VA S OF N3900", "VA"),
])
def test_abertura_vazia_continua_toda_a_fir(eng, corpo, fen):
    """A linha que abre o campo, vazia (ou só com a janela, que passa para a
    linha seguinte), dá toda a FIR em todo o período, além das subentradas."""
    g = _g(corpo)
    blocos = _blocos(eng, g, fen)
    assert any(_toda(eng, b) and b.window == "" for b in blocos), blocos
    assert len(blocos) >= 2
    assert set(_decisoes(eng, g).values()) == {"NO-GO"}
