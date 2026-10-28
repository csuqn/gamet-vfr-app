"""
4.2 — "Resto do período" (pedido do Duarte a 28-out-2026, "opção 2").

A janela HH/HH de um campo NÃO altera a decisão principal: o veredicto, as
cores e as regiões continuam a ser o pior caso de todo o período do GAMET.
Desde a 4.2 há uma SEGUNDA decisão, só informativa, para o resto do período
(de agora até ao fim da validade): sem os blocos do GAMET cuja janela já
terminou. Os sem janela, os activos e os que ainda não começaram contam;
SIGMET/AIRMET contam sempre. Só se mostra quando é diferente (menos severa).

GAMET real 280900/281500 (recolhido a 28-out-2026 08:43Z):
  SFC VIS: 09/11 N OF N3730 LCA 1200-5000M BR
  SIG CLD: 09/11 N OF N3730 LCA BKN 003-006/012HFT AGL
Às 12:30Z o cartão diz MARGINAL com "apenas 09–11Z — já terminou"; o resto
do período (12–15Z) é GO a N de N3730.

Propriedade: em todo o arquivo e várias horas, o veredicto principal, as
regiões e os avisos são idênticos aos do motor da 4.1
(`tests/referencia/app_4_1.py`, cópia fixa do `app.py` do main eb52a15; não
editar), e a decisão do resto nunca é mais severa do que a principal.
"""
import json
import re
import sys
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
RAIZ = Path(__file__).resolve().parent.parent
REF = Path(__file__).resolve().parent / "referencia" / "app_4_1.py"
ARQUIVO = RAIZ / "dados" / "gamets"
INDICE = RAIZ / "dados" / "indice.json"
FICHEIRO = ARQUIVO / "2026" / "10" / "20261028T0843Z_280900-281500_33018dfbf4.txt"

G280900 = (
    "LPPC GAMET VALID 280900/281500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC "
    "VIS:09/11 N OF N3730 LCA 1200-5000M BR SIG CLD:09/11 N OF N3730 LCA BKN 003-006/012HFT AGL "
    "SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:12 NIL CLD:N OF N3800 SCT/BKN SC/CU "
    "012-030/040HFT AGL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 "
    "1000FT AGL 080/009KT PS10 180/006KT PS14 140/005KT PS15 2000FT AGL 110/009KT PS09 "
    "150/006KT PS12 150/005KT PS12 5000FT AGL 230/010KT PS08 180/016KT PS11 220/011KT PS09 "
    "FL100 240/006KT PS05 200/009KT PS06 180/006KT PS06 FL150 290/010KT MS05 260/009KT MS05 "
    "260/006KT MS04 FZLVL: 13300FT AMSL 13100FT AMSL 13200FT AMSL LISBOA EVORA FARO N3845 "
    "W00908 N3830 W00752 N3700 W00800 1000FT AGL 010/007KT PS17 030/006KT PS18 130/001KT PS20 "
    "2000FT AGL 010/006KT PS15 020/009KT PS16 040/006KT PS17 5000FT AGL 290/002KT PS12 "
    "340/006KT PS12 030/010KT PS15 FL100 190/006KT PS06 130/004KT PS06 050/003KT PS07 FL150 "
    "200/002KT MS04 360/004KT MS03 030/008KT MS04 FZLVL: 13000FT AMSL 13400FT AMSL 13000FT "
    "AMSL MNM QNH:1020HPA=")

LINHA = "Resto do período"


def _t(h, m=0, dia=28):
    return datetime(2026, 10, dia, h, m, tzinfo=timezone.utc)


def _nome(eng, icao):
    return next(n for n in eng.AERODROMES if f"({icao})" in n)


def _dec_ponto(eng, r, nome):
    reg = eng.find_region_for_point(r["regioes"], *eng.AERODROMES[nome])
    return reg["decision"] if reg else None


def _a(corpo, n="5", val="281000/281500"):
    return f"LPPC AIRMET {n} VALID {val} LPPT- LPPC LISBOA FIR/MAINLAND AREA {corpo}"


@pytest.fixture(scope="module")
def eng41():
    src = REF.read_text(encoding="utf-8")
    mod = types.ModuleType("motor_4_1")
    mod.__dict__["__file__"] = str(REF)
    exec(compile(conftest._extract_engine(src), str(REF), "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_1(eng41):
    assert eng41.APP_VERSION == "4.1"
    assert not hasattr(eng41, "resto_do_periodo")


def test_versao(eng):
    # 4.2 ou posterior (a 4.3 parte as linhas com janelas a meio)
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 2)


def test_texto_real_igual_ao_arquivo():
    if not FICHEIRO.exists():
        pytest.skip("arquivo (ramo dados) não disponível")
    assert " ".join(FICHEIRO.read_text(encoding="utf-8").split()) == G280900


# --- O GAMET real 280900/281500 ------------------------------------------------

def test_real_10h_janela_activa_sem_segunda_linha(eng):
    r = eng.analisar_gamet(G280900, agora=_t(10))
    assert r["resto"] is None
    assert eng.resto_par(r) is None
    assert LINHA not in eng.html_veredicto(r["por_dec"], r["area"], eng.resto_par(r))
    for i, g in enumerate(r["regioes"]):
        assert LINHA not in eng.html_regiao(g, 50, (), eng.resto_par(r, regiao=i))


def test_real_1230_resto_go_a_norte_principal_marginal(eng):
    r = eng.analisar_gamet(G280900, agora=_t(12, 30))
    # O veredicto principal continua a ser o pior caso de todo o período
    pior = next(d for d in ("NO-GO", "MARGINAL", "GO") if r["por_dec"].get(d))
    assert pior == "MARGINAL"
    resto = r["resto"]
    assert resto is not None and resto["janela"] == "12–15Z"
    assert resto["decisao"] == "GO"
    assert {b.window for b in resto["ignorados"]} == {"09–11Z"}
    assert {b.phenomenon for b in resto["ignorados"]} == {"VIS", "BASE_AGL"}
    # Todos os pontos a N de N3730: principal MARGINAL, resto GO
    norte = [n for n, (la, lo) in eng.AERODROMES.items() if la > 37.55]
    assert len(norte) > 30
    for n in norte:
        assert _dec_ponto(eng, r, n) == "MARGINAL", n
        assert eng.resto_do_ponto(resto, *eng.AERODROMES[n]) == "GO", n
    # Veredicto: linha secundária, sem substituir o principal
    v = eng.html_veredicto(r["por_dec"], r["area"], eng.resto_par(r))
    assert ">MARGINAL<" in v
    assert "Resto do período (12–15Z): <b>GO</b> · pior do período: MARGINAL" in v
    assert v.index('class="gv-big"') < v.index("gv-resto")
    # Cartões: só o MARGINAL leva a linha
    for i, g in enumerate(r["regioes"]):
        h = eng.html_regiao(g, 50, (), eng.resto_par(r, regiao=i))
        assert (LINHA in h) == (g["decision"] == "MARGINAL"), g["label"]
        assert eng.html_chip(g["decision"]) in h
    # Aeródromo seleccionado
    lisboa = _nome(eng, "LPPT")
    h = eng.html_aerodromo(lisboa, eng.find_region_for_point(r["regioes"], *eng.AERODROMES[lisboa]),
                           eng.resto_par(r, ponto=eng.AERODROMES[lisboa]))
    assert f"{lisboa}: MARGINAL" in h
    assert "Resto do período (12–15Z): <b>GO</b> · pior do período: MARGINAL" in h
    faro = _nome(eng, "LPFR")
    h = eng.html_aerodromo(faro, eng.find_region_for_point(r["regioes"], *eng.AERODROMES[faro]),
                           eng.resto_par(r, ponto=eng.AERODROMES[faro]))
    assert f"{faro}: GO" in h and LINHA not in h


def test_real_16h_expirado_sem_segunda_linha(eng):
    r = eng.analisar_gamet(G280900, agora=_t(16))
    assert r["resto"] is None
    assert eng.resto_par(r) is None


def test_real_antes_da_validade_sem_segunda_linha(eng):
    r = eng.analisar_gamet(G280900, agora=_t(8, 30))
    assert r["resto"] is None


def test_real_1230_regioes_iguais_a_41(eng, eng41):
    _iguais(eng.analisar_gamet(G280900, agora=_t(12, 30)),
            eng41.analisar_gamet(G280900, agora=_t(12, 30)))


# --- Que blocos contam ---------------------------------------------------------

def _g(corpo):
    return build_gamet(f"SECN I {corpo}", validity="280900/281500")


def test_sem_janelas_nao_ha_resto(eng):
    r = eng.analisar_gamet(_g("SFC VIS: N OF N3730 LCA 1200-5000M BR"), agora=_t(12, 30))
    assert r["resto"] is None


def test_margem_de_uma_hora_depois_do_fim_da_janela(eng):
    """Decisão do Duarte (28-out-2026): 09/11 só deixa de contar às 12:00."""
    for h, m in ((11, 0), (11, 30), (11, 59)):
        r = eng.analisar_gamet(G280900, agora=_t(h, m))
        assert r["resto"] is None, f"{h}:{m:02d}"
    r = eng.analisar_gamet(G280900, agora=_t(12, 0))
    assert r["resto"] is not None
    assert r["resto"]["decisao"] in ("GO", "MARGINAL")
    assert eng.resto_par(r)[0] == "12–15Z"


def test_margem_no_270900_lisboa_nunca_go_antes_das_12(eng):
    """GAMET real 270900: base 100 ft 09–11Z a W de W00715. Às 11:05 e 11:55 a
    linha secundária não pode dizer GO em Lisboa."""
    g = (Path(__file__).resolve().parents[1] / "dados" / "gamets" / "2026" / "10"
         / "20261027T0853Z_270900-271500_c8fefbd089.txt")
    if not g.exists():
        pytest.skip("arquivo (ramo dados) não disponível")
    texto = g.read_text(encoding="utf-8")
    lisboa = _nome(eng, "LPPT")
    for h, m in ((11, 5), (11, 55)):
        r = eng.analisar_gamet(texto, agora=_t(h, m, dia=27))
        assert r["resto"] is None
        assert _dec_ponto(eng, r, lisboa) == "NO-GO"


def test_bloco_sem_janela_continua_a_contar(eng):
    r = eng.analisar_gamet(_g("SFC VIS:09/11 0800M FG SIG CLD: BKN 004/010HFT AGL"),
                           agora=_t(12, 30))
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["resto"]["decisao"] == "MARGINAL"          # a base 400 ft sem janela conta
    assert eng.resto_par(r) == ("12–15Z", "MARGINAL")


def test_bloco_que_ainda_nao_comecou_conta(eng):
    corpo = "SFC VIS:09/11 N OF N3700 0800M FG 13/15 N OF N3700 2000M BR"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    assert [(b.value, b.window, b.janela_ambigua) for b in blocos] == [
        (800, "09–11Z", False), (2000, "13–15Z", False)]
    lisboa = _nome(eng, "LPPT")
    r = eng.analisar_gamet(_g(corpo), agora=_t(12, 30))
    assert _dec_ponto(eng, r, lisboa) == "NO-GO"
    assert r["resto"]["decisao"] == "MARGINAL"          # 13/15 ainda não começou
    assert eng.resto_do_ponto(r["resto"], *eng.AERODROMES[lisboa]) == "MARGINAL"
    r = eng.analisar_gamet(_g(corpo), agora=_t(13, 30))
    assert r["resto"]["decisao"] == "MARGINAL"          # 13/15 activo
    assert r["resto"]["janela"] == "13–15Z"


def test_duas_janelas_na_mesma_linha_contam_sempre(eng):
    """Até à 4.2 o parser dava a janela 09–11Z aos dois valores de
    "09/11 0800M FG 13/15 2000M BR" e marcava-os janela_ambigua. Desde a 4.3 a
    janela a meio da linha abre uma subentrada (test_v43.py). O que ainda é
    ambíguo — uma janela no fim da linha, ou duas seguidas — continua a contar
    sempre no resto do período."""
    for corpo in ("SFC VIS:09/11 0800M FG 13/15", "SFC VIS:09/11 13/15 0800M FG"):
        blocos, *_ = eng.parse_gamet(_g(corpo))
        assert {(b.window, b.janela_ambigua) for b in blocos} == {("09–11Z", True)}, corpo
        r = eng.analisar_gamet(_g(corpo), agora=_t(12, 30))
        assert r["resto"] is None                       # nenhum bloco ignorado
    # Linha de continuação herda a ambiguidade da linha que abre a subentrada
    corpo = "SFC VIS:09/11 N OF N3700 0800M FG 13/15\nLCA 1000M FG"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    assert blocos and all(b.janela_ambigua for b in blocos)


def test_resto_igual_ao_principal_nao_mostra_linha(eng):
    r = eng.analisar_gamet(_g("SFC VIS:09/11 2000M BR SIG CLD: BKN 002/010HFT AGL"),
                           agora=_t(12, 30))
    assert r["resto"]["decisao"] == "NO-GO"
    assert LINHA not in eng.html_veredicto(r["por_dec"], r["area"], eng.resto_par(r))
    for i, g in enumerate(r["regioes"]):
        assert LINHA not in eng.html_regiao(g, 50, (), eng.resto_par(r, regiao=i))


def test_sigmet_do_gamet_conta_sempre(eng):
    texto = G280900.replace("AT TIME OF ISSUE NIL", "T01 VALID 281000/281400 LPPT")
    r = eng.analisar_gamet(texto, agora=_t(12, 30))
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["resto"]["decisao"] == "NO-GO"
    assert eng.html_resto(eng.resto_par(r), "NO-GO") == ""


def test_sigmet_do_ipma_conta_sempre(eng):
    sig = ("LPPC SIGMET 2 VALID 281100/281500 LPPT- LPPC LISBOA FIR SEV TURB FCST "
           "N OF N4000=")
    r = eng.analisar_gamet(G280900, "ipma", boletins=[sig], boletins_at=_t(12, 30),
                           agora=_t(12, 30))
    porto, lisboa = _nome(eng, "LPPR"), _nome(eng, "LPPT")
    assert eng.resto_do_ponto(r["resto"], *eng.AERODROMES[porto]) == "NO-GO"
    assert eng.resto_do_ponto(r["resto"], *eng.AERODROMES[lisboa]) == "GO"
    assert _dec_ponto(eng, r, lisboa) == "MARGINAL"


def test_airmet_conta_sempre(eng):
    air = _a("BKN CLD 004/010HFT AGL OBS N OF N4000 STNR NC")
    r = eng.analisar_gamet(G280900, "ipma", boletins=[air], boletins_at=_t(12, 30),
                           agora=_t(12, 30))
    porto, lisboa = _nome(eng, "LPPR"), _nome(eng, "LPPT")
    assert _dec_ponto(eng, r, porto) == "MARGINAL"
    assert eng.resto_do_ponto(r["resto"], *eng.AERODROMES[porto]) == "MARGINAL"
    assert eng.resto_do_ponto(r["resto"], *eng.AERODROMES[lisboa]) == "GO"
    assert r["resto"]["decisao"] == "MARGINAL"
    assert all(b.origem == "" for b in r["resto"]["ignorados"])


def test_html_resto_escapado_e_nunca_mais_severo(eng):
    assert eng.html_resto(("<b>12–15Z", "GO"), "MARGINAL").count("&lt;b&gt;12–15Z") == 1
    assert eng.html_resto(("12–15Z", "NO-GO"), "MARGINAL") == ""
    assert eng.html_resto(("12–15Z", "MARGINAL"), "MARGINAL") == ""
    assert eng.html_resto(None, "MARGINAL") == ""
    assert "pior do período: NO-GO" in eng.html_resto(("12–15Z", "MARGINAL"), "NO-GO")


# --- Propriedade: todo o arquivo, várias horas, contra a 4.1 -------------------

def _iguais(novo, antigo):
    assert novo["por_dec"] == antigo["por_dec"]
    assert novo["avisos"] == antigo["avisos"]
    assert novo["faixa_sig"] == antigo["faixa_sig"]
    assert len(novo["regioes"]) == len(antigo["regioes"])
    for a, b in zip(novo["regioes"], antigo["regioes"]):
        assert set(a) == set(b)
        for k in a:
            if k == "polygon":
                assert a[k].symmetric_difference(b[k]).area < 1e-12
            elif k == "notas":
                # Desde a 4.3 a janela "21/24" (até 24, o critério dos cortes)
                # é lida: GAMET real 232100/240300 ganha "TURB: apenas
                # 21–24Z" (TURB MOD, informativo). Mais nada pode mudar.
                assert [n for n in a[k] if not re.search(r"apenas \d{2}–24Z", n)] == b[k], k
            else:
                assert a[k] == b[k], k


def _horas(ini, fim):
    return [ini - timedelta(hours=1), ini + timedelta(minutes=30),
            ini + timedelta(hours=2, minutes=30), ini + timedelta(hours=4, minutes=30),
            fim - timedelta(minutes=15), fim + timedelta(hours=1)]


def _casos_arquivo():
    if not ARQUIVO.exists():
        return []
    return sorted(ARQUIVO.rglob("*.txt"))


def _verifica_resto(eng, r, agora):
    resto = r["resto"]
    if resto is None:
        return 0
    assert r["ini"] <= agora < r["fim"]
    assert resto["ignorados"]
    assert GRAV[resto["decisao"]] <= GRAV[max(r["por_dec"], key=GRAV.get)]
    for g, d in zip(r["regioes"], resto["por_regiao"]):
        assert d is not None and GRAV[d] <= GRAV[g["decision"]], (g["label"], d)
    for nome, (la, lo) in eng.AERODROMES.items():
        principal = _dec_ponto(eng, r, nome)
        d = eng.resto_do_ponto(resto, la, lo)
        if principal is not None:
            assert GRAV[d] <= GRAV[principal], (nome, d, principal)
    return 1


def test_arquivo_principal_igual_a_41_e_resto_nunca_mais_severo(eng, eng41):
    ficheiros = _casos_arquivo()
    if not ficheiros:
        pytest.skip("arquivo (ramo dados) não disponível")
    indice = json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else None
    entradas = {e["ficheiro"]: e for e in (indice or {}).get("gamets", [])}
    com_resto = 0
    for f in ficheiros:
        texto = f.read_text(encoding="utf-8")
        # O dia/mês vem do nome do ficheiro (AAAAMMDDTHHMMZ_…), como na recolha
        m = re.match(r"(\d{8})T", f.name)
        if not m:
            continue
        ref = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
        ini, fim, _ = eng.parse_validity(texto, ref + timedelta(hours=12))
        if ini is None:
            continue
        entrada = entradas.get(str(f.relative_to(RAIZ / "dados")))
        for agora in _horas(ini, fim):
            novo = eng.analisar_gamet(texto, agora=agora)
            _iguais(novo, eng41.analisar_gamet(texto, agora=agora))
            com_resto += _verifica_resto(eng, novo, agora)
            if entrada:
                novo = eng.analisar_gamet(texto, "arquivo_hist", indice=indice,
                                          entrada=entrada, agora=agora)
                _iguais(novo, eng41.analisar_gamet(texto, "arquivo_hist", indice=indice,
                                                   entrada=entrada, agora=agora))
                com_resto += _verifica_resto(eng, novo, agora)
    assert com_resto > 0          # o arquivo tem janelas que terminam


# --- As duas interfaces --------------------------------------------------------

def _gamet_agora():
    """GAMET em vigor agora (relógio real), com uma janela que já terminou.
    O rótulo da janela usa a hora actual: perto da mudança de hora, espera pela
    hora seguinte, para o teste não falhar se a hora mudar a meio (falhou uma
    vez às 14:59:58Z)."""
    import time
    agora = datetime.now(timezone.utc)
    seguinte = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    if (seguinte - agora) < timedelta(minutes=3):
        time.sleep((seguinte - agora).total_seconds() + 2)
        agora = datetime.now(timezone.utc)
    ini = (agora - timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    fim = ini + timedelta(hours=6)
    j2 = ini + timedelta(hours=1)
    texto = build_gamet(f"SECN I SFC VIS:{ini:%H}/{j2:%H} N OF N3730 LCA 1200-5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    return texto, f"{agora:%H}–{fim:%H}Z"


def test_app_streamlit_mostra_a_linha(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    texto, janela = _gamet_agora()
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    # Sem isto a app vai buscar o GAMET do IPMA ao abrir e substitui o texto
    # do teste (dependia da rede e da hora; como em test_v39).
    at.session_state["gamet_loaded"] = "outro texto"
    at.session_state["_active_gamet_text"] = texto
    at.session_state["aerodromo_preferido"] = "Lisboa (LPPT)"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    alvo = f"Resto do período ({janela}): <b>GO</b> · pior do período: MARGINAL"
    md = [m.value for m in at.markdown]
    ver = [m for m in md if 'class="gv-veredicto"' in m]
    assert ver and alvo in ver[0]
    assert re.search(r'class="gv-big"[^>]*>MARGINAL<', ver[0])
    assert conftest.veredicto(at).startswith("MARGINAL")
    assert any('class="gv-ad"' in m and "Lisboa (LPPT): MARGINAL" in m and alvo in m for m in md)
    cartoes = [m for m in md if 'class="gv-regioes"' in m]
    assert cartoes and alvo in cartoes[0]


def test_nicegui_mostra_a_linha():
    pytest.importorskip("nicegui")
    sys.path.insert(0, str(RAIZ / "nicegui_app"))
    import main as ng
    texto, janela = _gamet_agora()
    r = ng.analisar(texto, "manual")
    alvo = f"Resto do período ({janela}): <b>GO</b> · pior do período: MARGINAL"
    v = ng.html_veredicto(r)
    assert alvo in v and re.search(r'class="gv-big"[^>]*>MARGINAL<', v)
    assert alvo in ng.html_cartoes(r)
    h = ng.html_aerodromo(r, "Lisboa (LPPT)")
    assert "Lisboa (LPPT): MARGINAL" in h and alvo in h
    assert alvo not in ng.html_aerodromo(r, "Faro (LPFR)")
