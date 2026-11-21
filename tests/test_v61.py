"""
6.1 — aviso "Campo desconhecido" na Secção I (relatório W45, g.2; pedido do
Duarte a 20-nov-2026).

Até à 4.7.4 `SFC WIND:` não era um nome de campo conhecido: logo depois de
`SECN I` era ignorado em silêncio e, depois de outro campo, ficava colado a
ele como continuação (a área do vento recortava esse campo) — sem "Campo não
interpretado", porque não chegava a ser campo. Desde a 6.1, um `NOME:` da
Secção I que não acaba num nome conhecido dá um aviso. A leitura e as
decisões não mudam.
"""
import sys
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import analisar  # noqa: E402
from test_v49 import G141500  # noqa: E402  (GAMET real 141500/142100)

DADOS = Path(__file__).resolve().parent.parent / "dados"

# O caso da 4.7.4 com um nome que a app não conhece: o vento fica colado à VIS
G_WINDS = build_gamet("SECN I SFC VIS:N OF N4000 LCA 3000M RA SFC WINDS:S OF N3800 35KT "
                      "SIG CLD:N OF N4000 BKN 008/012HFT AGL")


def _avisos(eng, texto):
    return [m for t, m in eng.analisar_gamet(texto, "manual")["avisos"]
            if "Campo desconhecido" in m]


def test_nome_desconhecido_a_meio(eng):
    assert eng.campos_desconhecidos(G_WINDS) == ["SFC WINDS: S OF N3800 35KT"]
    (av,) = _avisos(eng, G_WINDS)
    assert "«`SFC WINDS: S OF N3800 35KT`»" in av
    assert "não o lê como campo" in av
    assert eng.titulo_aviso(av) == "Campo desconhecido"
    assert eng.etiqueta_aviso("aviso", av) == "verificar"


def test_nome_desconhecido_logo_depois_de_secn_i(eng):
    g = build_gamet("SECN I SFC WINDS:N OF N3900 AND W OF W00935 150/30KT SFC VIS:N OF N4000 "
                    "LCA 3000M RA")
    assert eng.campos_desconhecidos(g) == ["SFC WINDS: N OF N3900 AND W OF W00935 150/30KT"]


def test_varios_e_ultimo_antes_do_sigmet(eng):
    g = build_gamet("SECN I MT OBSCN:ENTIRE FIR SIG CLD:N OF N4000 BKN 008/012HFT AGL "
                    "HAZ WX:LCA FG")
    assert eng.campos_desconhecidos(g) == ["MT OBSCN: ENTIRE FIR", "WX: LCA FG"]
    assert len(_avisos(eng, g)) == 2


@pytest.mark.parametrize("nome", ["SFC VIS", "SIG VIS", "VIS", "SIG CLD", "CLD", "SIGWX",
                                  "TURB", "ICE", "MT OBSC", "SFC WSPD", "SFC WIND", "MTW",
                                  "VA"])
def test_nomes_conhecidos_nao_avisam(eng, nome):
    g = build_gamet(f"SECN I {nome}:N OF N4000 LCA 3000M RA")
    assert eng.campos_desconhecidos(g) == []
    # também colado ao valor do campo anterior, sem espaço antes dos dois pontos
    g2 = build_gamet(f"SECN I SFC VIS:N OF N4000 LCA 3000M BR {nome} : NIL")
    assert eng.campos_desconhecidos(g2) == []


def test_fora_da_seccao_i_nao_avisa(eng):
    # SIGMET APPLICABLE fecha a Secção I; a Secção II tem outros campos
    g = (conftest.HDR.format(v="201500/202100") + "SECN I SFC VIS:N OF N4000 LCA 3000M RA "
         "SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:NIL CLDX: NIL WIND/T: NIL "
         "MNM QNH:1013HPA=")
    assert eng.campos_desconhecidos(g) == []
    assert eng.campos_desconhecidos("texto sem secção I: nada") == []


@pytest.mark.parametrize("antes,nome", [
    ("SFC VIS:N OF N4000 LCA 3000M BR", "WINDS"),
    ("SIG CLD:N OF N4000 BKN 008/012HFT AGL", "WSPD"),
    ("TURB:NIL", "ICING"),
])
def test_nome_sem_a_palavra_do_campo_anterior(eng, antes, nome):
    """Revisão do agente parser: o nome não leva a última palavra do campo
    anterior ("BR WINDS:", "AGL WSPD:", "NIL ICING:")."""
    g = build_gamet(f"SECN I {antes} {nome}:N OF N4100 35KT")
    assert eng.campos_desconhecidos(g) == [f"{nome}: N OF N4100 35KT"]


def test_conteudo_cortado(eng):
    g = build_gamet("SECN I SFC WINDS:" + "N OF N3900 35KT " * 20)
    (s,) = eng.campos_desconhecidos(g)
    assert len(s) <= len("SFC WINDS: ") + 120 and s.endswith("…")


def test_decisao_nao_muda(eng):
    """Só aviso: as regiões de analisar_gamet são as do parser sem o aviso."""
    r = eng.analisar_gamet(G_WINDS, "manual")
    blocos, *_ = eng.parse_gamet(G_WINDS)
    regioes = eng.compute_dynamic_regions(blocos)
    for n, (la, lo) in eng.AERODROMES.items():
        assert (eng.find_region_for_point(r["regioes"], la, lo)["decision"]
                == eng.find_region_for_point(regioes, la, lo)["decision"]), n


def test_gamet_real_sem_aviso(eng):
    assert eng.campos_desconhecidos(G141500) == []


@pytest.mark.skipif(not (DADOS / "gamets").exists(), reason="sem dados/")
def test_arquivo_sem_aviso(eng):
    """Nenhum GAMET do arquivo tem um nome de campo desconhecido (a 20-nov-2026,
    150 GAMETs; o SFC WIND de 8-nov já é conhecido desde a 4.7.5)."""
    com = [p.name for p in sorted((DADOS / "gamets").rglob("*.txt"))
           if eng.campos_desconhecidos(p.read_text(encoding="utf-8"))]
    assert com == []


def test_analisar_py_assinala(eng):
    r = analisar.analisar(eng, G_WINDS)
    assert "Campo desconhecido → SFC WINDS: S OF N3800 35KT" in r["alertas"]
    assert not any(a.startswith("Campo desconhecido") for a in analisar.analisar(eng, G141500)["alertas"])


def test_app_streamlit_mostra_o_aviso(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = "outro texto"
    at.session_state["_active_gamet_text"] = G_WINDS
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    avisos = [w.value for w in at.warning if "Campo desconhecido" in w.value]
    assert len(avisos) == 1 and "SFC WINDS" in avisos[0], [w.value for w in at.warning]
    assert any(e.label.startswith("Campo desconhecido") for e in at.expander), \
        [e.label for e in at.expander]
