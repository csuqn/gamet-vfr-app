"""
3.4 — Subentrada com área ilegível passa a valer para toda a FIR, com aviso.

Pedido do Duarte (18-out-2026). Até à 3.3, quando `extract_polygon()` não
conseguia ler a área de uma subentrada a meio de um campo, a subentrada
herdava EM SILÊNCIO a área da anterior. Foi assim que o GAMET real
171500/172100, antes da 3.1 (hífen do BTN por ler), pôs a base da costa W
numa tira junto ao Guadiana:

    SIG CLD:N OF N3710 AND E OF W00800 ISOL/EMBD TCU/CB 025-040/XXXHFT AGL
    15/18 BTN N4050 - N3840 MAR AND COT LCA BKN 008/012HFT AGL

Agora, uma subentrada que começa (depois da janela HH/HH) por algo com ar de
qualificador geográfico e da qual não se tira área vale para toda a FIR
(leitura conservadora) e `analisar_gamet()` mostra um aviso com o texto.
Os testes usam o GAMET real com o hífen trocado por um separador que a app
não conhece ("~").
"""
import sys
from pathlib import Path

import pytest
from shapely.geometry import Point

from conftest import build_gamet
from test_v32 import GAMET_171500, DECISOES_3_0

ILEGIVEL = GAMET_171500.replace("BTN N4050 - N3840", "BTN N4050 ~ N3840").replace(
    "SIGMET APPLICABLE:T02", "SIGMET APPLICABLE: NIL")
BAIXA = ILEGIVEL.replace("BKN 008/012HFT", "BKN 002/012HFT")


def _dec(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)["decision"]


def _base(r, valor):
    (b,) = [b for b in r["blocks"] if b.phenomenon == "BASE_AGL" and b.value == valor]
    return b


# ---------------------------------------------------------------------
# GAMET real 171500 com o separador do BTN ilegível
# ---------------------------------------------------------------------

def test_subentrada_ilegivel_vale_para_toda_a_fir(eng, analyse):
    b = _base(analyse(ILEGIVEL), 800)
    # Toda a FIR, recortada só pelo MAR AND COT da própria subentrada — não
    # a área "N OF N3710 AND E OF W00800" da subentrada anterior
    esperado = eng._clean_poly(eng.FIR_POLYGON.intersection(eng.surface_polygon("COT/MAR")))
    assert b.polygon.symmetric_difference(esperado).area < 1e-6
    assert b.window == "15–18Z"


def test_subentrada_anterior_mantem_a_sua_area(analyse):
    b = _base(analyse(ILEGIVEL), 2500)
    minx, miny, _, _ = b.polygon.bounds
    assert abs(minx - (-8.0)) < 1e-6
    assert abs(miny - (37 + 10 / 60)) < 0.01


def test_subentradas_sem_area_devolve_o_texto(eng):
    (s,) = eng.subentradas_sem_area(ILEGIVEL)
    assert "BTN N4050 ~ N3840" in s
    assert "BKN 008/012HFT AGL" in s
    assert s.startswith("SIG CLD")


def test_analisar_gamet_avisa(eng):
    r = eng.analisar_gamet(ILEGIVEL, "manual")
    avisos = [t for tipo, t in r["avisos"] if tipo == "aviso" and "Área não reconhecida" in t]
    assert len(avisos) == 1, r["avisos"]
    assert "BTN N4050 ~ N3840" in avisos[0]
    assert "toda a FIR" in avisos[0]


def test_aviso_escapado_na_nicegui(eng):
    """O texto do GAMET vai para o aviso; na NiceGUI passa por html.escape."""
    texto = ILEGIVEL.replace("BTN N4050 ~ N3840", "BTN N4050 <b>x</b> N3840")
    r = eng.analisar_gamet(texto, "manual")
    (aviso,) = [t for _, t in r["avisos"] if "Área não reconhecida" in t]
    assert "<B>X</B>" in aviso.upper()            # o motor guarda o texto tal como é
    assert "<b>" not in eng._e(aviso)             # e a interface escapa-o


def test_base_baixa_real_com_mar_e_cot_chega_a_toda_a_costa(eng, analyse):
    r = analyse(BAIXA)
    # Fora da faixa BTN N3840/N4050 e fora da área herdada: só ficam NO-GO
    # porque a subentrada passou a valer para toda a FIR (costa e mar)
    for nome in ("Faro (LPFR)", "Porto (LPPR)", "Cascais (LPCS)", "Portimão (LPPM)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome


def test_base_baixa_sem_superficie_da_no_go_em_lisboa_e_faro(eng, analyse):
    r = analyse(BAIXA.replace("MAR AND COT LCA BKN 002", "LCA BKN 002"))
    for nome in ("Lisboa (LPPT)", "Faro (LPFR)", "Porto (LPPR)", "Bragança (LPBG)",
                 "Évora (LPEV)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome


def test_analisar_py_assinala(eng):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    r = analisar.analisar(eng, ILEGIVEL)
    assert any(a.startswith("Área não reconhecida") and "BTN N4050 ~ N3840" in a
               for a in r["alertas"]), r["alertas"]
    r = analisar.analisar(eng, GAMET_171500)
    assert not [a for a in r["alertas"] if a.startswith("Área não reconhecida")]


# ---------------------------------------------------------------------
# Outras formas de área ilegível a meio de um campo
# ---------------------------------------------------------------------

# A meio de um campo, uma subentrada só começa linha nova se a quebra já
# for injectada (BTN N…, N OF N…) ou se o texto trouxer a quebra. Aqui usa-se
# a quebra do próprio texto. A injecção de quebras antes dos qualificadores
# não lidos fica de fora (ver o teste do "SW OF" mais abaixo).
@pytest.mark.parametrize("area", [
    "NW OF N4000", "BTN N4000 / N3800", "N OF N40", "WI N4000 W00800 - N3900 W00700",
    "ALONG COAST", "N PART", "S PART",
])
def test_formas_ilegiveis_a_meio_do_campo(eng, analyse, area):
    texto = build_gamet(f"SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL\n{area} LCA BKN 002HFT AGL")
    r = analyse(texto)
    b = _base(r, 200)
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6, area
    # A subentrada anterior não é afectada
    assert _base(r, 1000).polygon.bounds[3] <= 38.0 + 1e-6
    (s,) = eng.subentradas_sem_area(texto)
    assert area in s
    for nome in ("Porto (LPPR)", "Lisboa (LPPT)", "Bragança (LPBG)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", (area, nome)


def test_btn_ilegivel_sem_quebra_no_texto(eng, analyse):
    """BTN N…: a quebra já era injectada; a subentrada vale para toda a FIR."""
    texto = build_gamet("SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL "
                        "BTN N4000 / N3800 LCA BKN 002HFT AGL")
    b = _base(analyse(texto), 200)
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert len(eng.subentradas_sem_area(texto)) == 1


def test_entire_fir_a_meio_do_campo_toda_a_fir_sem_aviso(eng, analyse):
    texto = build_gamet("SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL\nENTIRE FIR LCA BKN 002HFT AGL")
    b = _base(analyse(texto), 200)
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert eng.subentradas_sem_area(texto) == []
    assert not [t for _, t in eng.analisar_gamet(texto, "manual")["avisos"]
                if "Área não reconhecida" in t]


def test_ilegivel_no_inicio_do_campo_avisa_e_ja_era_toda_a_fir(eng, analyse):
    texto = build_gamet("SECN I SIG CLD:NW OF N4000 LCA BKN 002HFT AGL")
    b = _base(analyse(texto), 200)
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert len(eng.subentradas_sem_area(texto)) == 1


def test_janela_da_subentrada_ilegivel_e_a_dela(analyse):
    r = analyse(build_gamet(
        "SECN I SIG CLD:09/12 S OF N3800 LCA BKN 010HFT AGL\n12/15 NW OF N4000 LCA BKN 002HFT AGL"))
    assert _base(r, 1000).window == "09–12Z"
    assert _base(r, 200).window == "12–15Z"


def test_sw_of_colado_na_mesma_linha_toda_a_fir_com_aviso(eng, analyse):
    """
    "E OF W00700 ISOL TS SW OF W00830 OCNL TS" fica numa só linha (não se
    injectam quebras antes de diagonais). Até à 3.3 "SW OF" era lido como
    "W OF": E OF W00700 ∩ W OF W00830 = vazio → união, e a faixa entre 8°30'W
    e 7°W ficava sem TS. Com a diagonal a linha não tem área legível: ISOL e
    OCNL TS em toda a FIR, com aviso. O NE continua NO-GO; a faixa do meio
    passa a NO-GO (mais severo, nunca mais permissivo).
    """
    texto = build_gamet("SECN I SIGWX:E OF W00700 ISOL TS SW OF W00830 OCNL TS")
    r = analyse(texto)
    # Uma linha de SIGWX dá um só bloco de TS, com o pior qualificador (como
    # no main): o ISOL fica absorvido pelo OCNL.
    assert r["ts"] == {"OCNL"}
    for b in r["blocks"]:
        assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    for nome in ("Bragança (LPBG)", "Mogadouro (LPMU)", "Cabeço da Vaca (LP66)",
                 "Lisboa (LPPT)", "Évora (LPEV)", "Viseu (LPVZ)", "Faro (LPFR)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome
    (s,) = eng.subentradas_sem_area(texto)
    assert "SW OF W00830" in s


# ---------------------------------------------------------------------
# Qualificadores diagonais (NE/NW/SE/SW OF): nunca lidos como cardinais
# ---------------------------------------------------------------------

_DIAGONAIS = [f"{d} OF {c}" for d in ("NE", "NW", "SE", "SW") for c in ("W00800", "N3840")]


@pytest.mark.parametrize("qual", _DIAGONAIS)
def test_diagonal_nao_da_area(eng, qual):
    assert eng.extract_polygon(f"{qual} LCA BKN 002HFT AGL") is None


@pytest.mark.parametrize("qual", _DIAGONAIS)
def test_diagonal_no_inicio_da_linha_toda_a_fir_com_aviso(eng, analyse, qual):
    texto = build_gamet(f"SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL\n{qual} LCA BKN 002HFT AGL")
    r = analyse(texto)
    assert _base(r, 200).polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6, qual
    assert _base(r, 1000).polygon.bounds[3] <= 38.0 + 1e-6
    (s,) = eng.subentradas_sem_area(texto)
    assert qual in s
    avisos = [t for _, t in eng.analisar_gamet(texto, "manual")["avisos"]
              if "Área não reconhecida" in t]
    assert len(avisos) == 1 and qual in avisos[0]
    for nome in ("Porto (LPPR)", "Lisboa (LPPT)", "Bragança (LPBG)", "Faro (LPFR)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", (qual, nome)


@pytest.mark.parametrize("qual", _DIAGONAIS)
def test_diagonal_no_inicio_do_campo(eng, analyse, qual):
    texto = build_gamet(f"SECN I SIG CLD:{qual} LCA BKN 002HFT AGL")
    assert _base(analyse(texto), 200).polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert len(eng.subentradas_sem_area(texto)) == 1


def test_diagonal_juntada_por_and_ao_cardinal_toda_a_fir(eng, analyse):
    """
    "SE OF N3840 AND N OF N4000" é uma só área: a junção por AND aceita as
    diagonais, por isso não há quebra antes de "N OF N4000" e a linha inteira
    (com a diagonal) fica sem área legível → toda a FIR + aviso, para as duas
    bases. Em 9c86865 a quebra ficava e a base de 200 ft ficava só a N de
    N4000; com outros arranjos (ver o teste seguinte) isso era mais
    permissivo do que o main. Toda a FIR é a leitura conservadora.
    """
    texto = build_gamet("SECN I SIG CLD:N OF N3800 LCA BKN 010HFT AGL SE OF N3840 AND "
                        "N OF N4000 LCA BKN 002HFT AGL")
    r = analyse(texto)
    assert _base(r, 200).polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    assert _base(r, 1000).polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    (s,) = eng.subentradas_sem_area(texto)
    assert "SE OF N3840 AND N OF N4000" in s


def test_btn_diagonal_and_cardinal_nunca_mais_permissivo(eng, analyse):
    """
    Fuzz do revisor: no main, "SW OF" era lido como "W OF", a intersecção com
    N OF N3840 dava vazio e a união punha o ISOL TS em toda a faixa (Faro, Beja
    e Évora MARGINAL). Em 9c86865 a quebra antes de "N OF N3840" deixava o TS
    só a N de N3840 (GO no Sul). Agora a linha fica junta → toda a FIR + aviso.
    """
    texto = build_gamet("SECN I SIGWX: BTN N3700 - N3840 SW OF W00800 AND N OF N3840 ISOL TS")
    r = analyse(texto)
    (b,) = [b for b in r["blocks"] if b.phenomenon == "TS"]
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6
    for nome in ("Faro (LPFR)", "Beja (LPBJ)", "Évora (LPEV)"):
        assert _dec(eng, r["regions"], nome) in ("MARGINAL", "NO-GO"), nome
    (s,) = eng.subentradas_sem_area(texto)
    assert "SW OF W00800" in s


@pytest.mark.parametrize("corpo", [
    "SIGWX:SW OF W00800 BTN N3700 AND N3840 ISOL TS",       # diagonal + BTN
    "SIGWX:SW OF W00800 BTN N3700 - N3840 ISOL TS",
    "SIGWX:SW OF W00800 N OF N3840 ISOL TS",                # cardinal sem AND
    "SIGWX:NE OF W00800 S OF N3900 ISOL TS",
    "SIGWX:E OF W00800 - NE OF W00800 AND W OF W00830 ISOL TS",
    "SIGWX:N OF N3840 SW OF W00800 AND E OF W00800 ISOL TS",
])
def test_diagonal_nunca_e_partida_do_cardinal_seguinte(eng, analyse, corpo):
    """A quebra antes de N/S/E/W OF ou BTN não separa a diagonal do resto."""
    texto = build_gamet("SECN I " + corpo)
    r = analyse(texto)
    (b,) = [b for b in r["blocks"] if b.phenomenon == "TS"]
    assert b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-6, corpo
    assert len(eng.subentradas_sem_area(texto)) == 1


@pytest.mark.parametrize("corpo,limites", [
    ("SIG CLD:N OF N3840 AND W OF W00850 LCA BKN 002HFT AGL",
     dict(miny=38 + 40 / 60, maxx=-(8 + 50 / 60))),
    ("SIGWX:E OF W00800 LAN ISOL/EMBD TS", dict(minx=-8.0)),
])
def test_cardinais_continuam_iguais(eng, analyse, corpo, limites):
    texto = build_gamet("SECN I " + corpo)
    (b,) = analyse(texto)["blocks"]
    minx, miny, maxx, maxy = b.polygon.bounds
    for k, v in limites.items():
        assert abs(locals()[k] - v) < 1e-6, (k, locals()[k], v)
    assert eng.subentradas_sem_area(texto) == []


def test_sigmet_com_diagonal_e_toda_a_area(eng):
    sig = ("LPPC SIGMET T05 VALID 181400/181800 LPPT- LPPC LISBOA FIR "
           "SEV TURB FCST SW OF W00800 SFC/FL080 STNR NC=")
    geom, desc = eng.area_sigmet(sig)
    assert geom is None
    assert "toda a área" in desc
    # O mesmo SIGMET com cardinal continua a ter área própria
    geom, _ = eng.area_sigmet(sig.replace("SW OF", "W OF"))
    assert geom is not None and not geom.is_empty
    assert geom.bounds[2] < -7.5


# ---------------------------------------------------------------------
# Casos legítimos que NÃO mudam
# ---------------------------------------------------------------------

def test_a_linha_de_continuacao_sem_qualificador_usa_a_area_da_subentrada(eng, analyse):
    texto = build_gamet("SECN I SIG CLD:N OF N4000 LCA BKN 010HFT AGL\nLCA BKN 002HFT AGL")
    r = analyse(texto)
    assert _base(r, 200).polygon.bounds[1] >= 40.0 - 1e-6
    assert eng.subentradas_sem_area(texto) == []
    assert _dec(eng, r["regions"], "Lisboa (LPPT)") == "GO"


def test_a_continuacao_com_fenomeno_proprio(eng, analyse):
    texto = build_gamet("SECN I SIGWX:N OF N4000 ISOL TS\nOCNL TS")
    r = analyse(texto)
    for b in r["blocks"]:
        assert b.polygon.bounds[1] >= 40.0 - 1e-6
    assert eng.subentradas_sem_area(texto) == []


def test_b_qualificador_fora_da_fir_continua_descartado(eng, analyse):
    # A FIR termina em 42°09'N: "N OF N4300" não tem área dentro dela
    texto = build_gamet("SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL N OF N4300 LCA BKN 002HFT AGL")
    r = analyse(texto)
    assert 200 not in r["base"]
    assert eng.subentradas_sem_area(texto) == []
    assert _dec(eng, r["regions"], "Porto (LPPR)") == "GO"


@pytest.mark.parametrize("sup", ["MAR", "COT", "LAN", "MAR AND COT"])
def test_c_mar_lan_cot_sozinhos_nao_sao_area(eng, analyse, sup):
    texto = build_gamet(f"SECN I SIG CLD:S OF N3800 LCA BKN 010HFT AGL\n{sup} LCA BKN 002HFT AGL")
    r = analyse(texto)
    assert _base(r, 200).polygon.bounds[3] <= 38.0 + 1e-6
    assert eng.subentradas_sem_area(texto) == []


def test_qualificadores_legiveis_nao_avisam(eng):
    for corpo in ("SIG CLD:N OF N3840 AND W OF W00815 LCA BKN 002HFT AGL",
                  "SIG CLD:BTN N3840 AND N4100 E OF W00800 LCA BKN 002HFT AGL",
                  "SIG CLD:BTN N4050 - N3840 MAR AND COT LCA BKN 002HFT AGL",
                  "SIG CLD:09/11 N OF N3920 AND W OF W00815 LCA BKN 003HFT AGL "
                  "12/15 N OF N4000 AND E OF W00740 ISOL TCU/CB 030-045/XXXHFT AGL"):
        assert eng.subentradas_sem_area(build_gamet("SECN I " + corpo)) == [], corpo


def test_171500_real_decisoes_nao_mudam(eng, analyse):
    r = analyse(GAMET_171500.replace("SIGMET APPLICABLE:T02", "SIGMET APPLICABLE: NIL"))
    assert {n: _dec(eng, r["regions"], n) for n in eng.AERODROMES} == DECISOES_3_0
    assert eng.subentradas_sem_area(GAMET_171500) == []
