"""
3.9 — Aviso "Campo não interpretado" (pedido do Duarte a 21-out-2026).

O IPMA engana-se muitas vezes a digitar. No GAMET real 201500/202100
("SIG CLD:19/21 N OF N4100 LCA BKN 008/010HTF AGL"), até à 3.6 a base
desaparecia em silêncio e a app dava GO sem dizer nada — só o
`scripts/analisar.py` dava por isso no relatório do dia seguinte. Desde a
3.9, `campos_nao_interpretados()` devolve as subentradas da Secção I com
conteúdo (não NIL) que não geraram nenhum fenómeno, e `analisar_gamet()`
junta um aviso que as duas interfaces mostram. Só aviso: a decisão não muda.

Os testes usam o GAMET real 201500 com a gralha "HTF" (já lida desde a 3.7)
trocada por uma gralha nova, "HTX".
"""
import sys
from pathlib import Path

import pytest

from conftest import build_gamet
from test_v15 import GAMET_REAL_20261014
from test_v20 import GAMET_160300
from test_v23 import GAMET_160900, GAMET_162100, GAMET_170300
from test_v25 import GAMET_161500
from test_v31 import GAMET_172100, GAMET_180300
from test_v32 import GAMET_171500
from test_v35 import GAMET_182100
from test_v36 import G192100
from test_v37 import G201500, AGORA

HTX = G201500.replace("008/010HTF AGL", "008/010HTX AGL", 1)
SUB_HTX = "SIG CLD: 19/21 N OF N4100 LCA BKN 008/010HTX AGL"
ARQUIVO = Path(__file__).resolve().parent.parent / "dados" / "gamets"


def _avisos(eng, texto):
    r = eng.analisar_gamet(texto, "manual", agora=AGORA)
    return [(t, x) for t, x in r["avisos"] if "Campo não interpretado" in x]


def _decisoes(eng, regioes):
    return {n: eng.find_region_for_point(regioes, la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


# ---------------------------------------------------------------------
# GAMET real 201500 com gralha nova
# ---------------------------------------------------------------------

def test_gamet_real_com_gralha_nova_avisa(eng):
    assert eng.campos_nao_interpretados(HTX) == [SUB_HTX]
    ((tipo, aviso),) = _avisos(eng, HTX)
    assert tipo == "aviso"
    assert "19/21 N OF N4100 LCA BKN 008/010HTX AGL" in aviso
    assert "NÃO entra na" in aviso and "GAMET original" in aviso


def test_gamet_real_tal_como_veio_nao_avisa(eng):
    assert eng.campos_nao_interpretados(G201500) == []
    assert _avisos(eng, G201500) == []


def test_aviso_nao_muda_a_decisao(eng, analyse):
    r = eng.analisar_gamet(HTX, "manual", agora=AGORA)
    assert _decisoes(eng, r["regioes"]) == _decisoes(eng, analyse(HTX)["regions"])
    # A base perdida dava GO (800 ft também dava): o aviso é a única diferença
    assert set(_decisoes(eng, r["regioes"]).values()) == {"GO"}


def test_parse_gamet_igual_com_e_sem_recolha(eng):
    for g in (HTX, G201500, GAMET_171500, GAMET_160900):
        a, *_ = eng.parse_gamet(g)
        b, *_ = eng.parse_gamet(g, [], [], [])
        assert [(x.phenomenon, x.value, x.window, x.polygon.wkt) for x in a] == \
               [(x.phenomenon, x.value, x.window, x.polygon.wkt) for x in b]


def test_aviso_sem_backticks_partidos_e_escapado(eng):
    g = HTX.replace("008/010HTX AGL", "008/010HTX `<b>x</b>` AGL")
    ((_, aviso),) = _avisos(eng, g)
    assert aviso.count("`") == 2                  # só o par do código
    assert "<B>X</B>" in aviso                    # o motor guarda o texto tal como é
    assert "<B>" not in eng._e(aviso)             # e a interface escapa-o


# ---------------------------------------------------------------------
# Campo totalmente ilegível e subentrada ilegível ao lado de uma legível
# ---------------------------------------------------------------------

@pytest.mark.parametrize("corpo, esperado", [
    ("SECN I TURB: N OF N4000 LCA XYZ SFC/FL040", "TURB: N OF N4000 LCA XYZ SFC/FL040"),
    ("SECN I SIGWX: N OF N4000 ISOL ZZ", "SIGWX: N OF N4000 ISOL ZZ"),
    ("SECN I SIG CLD: BKN 004/010XYZ AGL", "SIG CLD: BKN 004/010XYZ AGL"),
    ("SECN I SFC VIS: N OF N4000 LCA 1200 BR".replace("1200", "12OO"),
     "SFC VIS: N OF N4000 LCA 12OO BR"),
    ("SECN I ICE: LCA ABV FL090", "ICE: LCA ABV FL090"),
    ("SECN I SFC WSPD: N OF N4000 35 KNOTS", "SFC WSPD: N OF N4000 35 KNOTS"),
    ("SECN I MTW: N OF N4000 FL080", "MTW: N OF N4000 FL080"),
])
def test_campo_totalmente_ilegivel(eng, corpo, esperado):
    g = build_gamet(corpo)
    assert eng.campos_nao_interpretados(g) == [esperado]
    assert len(_avisos(eng, g)) == 1


@pytest.mark.parametrize("corpo, esperado", [
    ("SECN I SIG CLD:N OF N4100 LCA BKN 004/010HFT AGL S OF N4000 LCA BKN 003/010XYZ AGL",
     "SIG CLD: S OF N4000 LCA BKN 003/010XYZ AGL"),
    ("SECN I SIG CLD:S OF N4000 LCA BKN 003/010XYZ AGL N OF N4100 LCA BKN 004/010HFT AGL",
     "SIG CLD: S OF N4000 LCA BKN 003/010XYZ AGL"),
    ("SECN I SFC VIS:09/11 N OF N4000 LCA 1500-5000M BR 13/15 S OF N3900 LCA 15OO BR",
     "SFC VIS: 13/15 S OF N3900 LCA 15OO BR"),
])
def test_subentrada_ilegivel_ao_lado_de_uma_legivel(eng, analyse, corpo, esperado):
    g = build_gamet(corpo)
    assert eng.campos_nao_interpretados(g) == [esperado]
    assert analyse(g)["blocks"], "a subentrada legível continua a gerar o seu bloco"
    (( _, aviso),) = _avisos(eng, g)
    assert esperado.split(": ", 1)[1] in aviso


def test_subentrada_ilegivel_no_campo_legivel_escapava_a_verificacao_por_campo(eng):
    """A verificação antiga do analisar.py era por campo: com outra subentrada
    legível no mesmo campo, não dizia nada."""
    g = build_gamet("SECN I SIG CLD:N OF N4100 LCA BKN 004/010HFT AGL "
                    "S OF N4000 LCA BKN 003/010XYZ AGL")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    r = analisar.analisar(eng, g)
    assert [a for a in r["alertas"] if a.startswith("Campo sem fenómeno gerado")] == \
           ["Campo sem fenómeno gerado → SIG CLD: S OF N4000 LCA BKN 003/010XYZ AGL"]


def test_analisar_py_usa_o_motor(eng):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    assert not hasattr(analisar, "campos_sem_fenomeno")
    r = analisar.analisar(eng, HTX)
    assert f"Campo sem fenómeno gerado → {SUB_HTX}" in r["alertas"], r["alertas"]


# ---------------------------------------------------------------------
# O que NÃO pode avisar
# ---------------------------------------------------------------------

REAIS = [GAMET_REAL_20261014, GAMET_160300, GAMET_160900, GAMET_161500, GAMET_162100,
         GAMET_170300, GAMET_171500, GAMET_172100, GAMET_180300, GAMET_182100,
         G192100, G201500]


@pytest.mark.parametrize("g", REAIS)
def test_gamets_reais_nao_avisam(eng, g):
    assert eng.campos_nao_interpretados(g) == []


def test_arquivo_inteiro_nao_avisa(eng):
    fich = sorted(ARQUIVO.rglob("*.txt")) if ARQUIVO.exists() else []
    if not fich:
        pytest.skip("arquivo de GAMETs não disponível neste checkout")
    falsos = {p.name: eng.campos_nao_interpretados(p.read_text(encoding="utf-8"))
              for p in fich}
    assert {k: v for k, v in falsos.items() if v} == {}


@pytest.mark.parametrize("corpo", [
    "SECN I SFC VIS: NIL SIG CLD: NIL SIGWX: NIL TURB: NIL ICE: NIL",
    "SECN I MT OBSC: NIL VA: NIL SFC WSPD: NIL MTW: NIL",
    "SECN I SIGWX: NIL=",
    "HAZARDOUS WX NIL",
    # Campo com dois pontos repetidos (GAMET real 170900: "SIG CLD::09/11 …")
    "SECN I SIG CLD::09/11 N OF N3840 LCA BKN 004-008/010HFT AGL",
    # Qualificador numa linha e fenómeno na seguinte (quebra do próprio texto)
    "SECN I SIG CLD: N OF N4000\nLCA BKN 004/010HFT AGL",
    # Área lida, mas fora da FIR ou da superfície: descartada de propósito
    "SECN I SIG CLD: N OF N4200 LCA BKN 002/010HFT AGL",
    "SECN I TURB: N OF N4200 MOD SFC/FL040",
    # Fenómenos que geram bloco informativo / sem efeito na decisão
    "SECN I TURB: N OF N3800 COT AND MAR LCA MOD SFC/FL020",
    "SECN I ICE: N OF N4000 LCA MOD ABV FL090",
    "SECN I MTW: N OF N4000 MOD FL080",
    "SECN I SIG CLD: E OF W00740 ISOL TCU 025-040/XXXHFT AGL",
    "SECN I SIG CLD: N OF N4000 AS/AC 050-090/100-130HFT AMSL",
    "SECN I SIGWX: S OF N3800 ISOL/EMBD TS",
    "SECN I SFC VIS: N OF N4100 LCA 5000 RA",
    "SECN I SFC WSPD: N OF N4000 35KT",
    "SECN I MT OBSC: N OF N4100",
    "SECN I VA: N OF N4000",
    "SECN I SIG CLD: ENTIRE FIR BKN 004/010HFT AGL",
])
def test_nao_avisa(eng, corpo):
    assert eng.campos_nao_interpretados(build_gamet(corpo)) == []


def test_area_nao_reconhecida_nao_e_campo_nao_interpretado(eng):
    """Área ilegível mas fenómeno lido (toda a FIR): é o aviso de área (3.4),
    não este."""
    g = build_gamet("SECN I SIG CLD: N OF N4100 LCA BKN 004/010HFT AGL\n"
                    "BTN N4050 ~ N3840 LCA BKN 008/012HFT AGL")
    assert eng.subentradas_sem_area(g)
    assert eng.campos_nao_interpretados(g) == []


# ---------------------------------------------------------------------
# As duas interfaces
# ---------------------------------------------------------------------

def test_app_streamlit_mostra_o_aviso(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = "outro texto"
    at.session_state["_active_gamet_text"] = HTX
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    avisos = [w.value for w in at.warning if "Campo não interpretado" in w.value]
    assert len(avisos) == 1 and "008/010HTX AGL" in avisos[0], [w.value for w in at.warning]


def test_nicegui_mostra_o_aviso():
    pytest.importorskip("nicegui")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nicegui_app"))
    import main as ng
    r = ng.analisar(HTX.replace("008/010HTX", "008/010HTX<b>"), "manual")
    (aviso,) = [x for t, x in r["avisos"] if t == "aviso" and "Campo não interpretado" in x]
    html = ng._md(aviso)
    assert "<code>" in html and "&lt;B&gt;" in html and "<B>" not in html


@pytest.mark.parametrize("corpo", [
    "SECN I MT OBSC: N OF N4100 LAN S OF N3800 LAN",
    "SECN I VA: N OF N4100 LCA S OF N3800 LCA",
])
def test_segunda_subentrada_de_mt_obsc_ou_va_nunca_em_silencio(eng, corpo):
    """Até à 3.9 a máquina de estados só criava MT_OBSC/VA na linha que abre o
    campo e a 2.ª subentrada (S OF N3800) só avisava. Desde a 3.10 gera o seu
    bloco — e deixa de avisar. Nunca em silêncio: gera bloco ou avisa."""
    g = build_gamet(corpo)
    blocos, *_ = eng.parse_gamet(g)
    sul = [b for b in blocos if b.polygon.bounds[3] <= 38 + 1e-6]
    avisos = eng.campos_nao_interpretados(g)
    assert sul or any("S OF N3800" in a for a in avisos), (blocos, avisos)
    # 3.10: gera bloco, com o fenómeno do campo, e já não avisa
    fen = "MT_OBSC" if corpo.startswith("SECN I MT OBSC") else "VA"
    assert [b.phenomenon for b in sul] == [fen], blocos
    assert avisos == [], avisos
