"""
4.6.1 — NiceGUI: o resultado da análise tem de voltar do outro processo.

Encontrado pelo revisor do PR #36 (reproduzido no main 052b42a). Na NiceGUI
(interface principal) `run.cpu_bound(analisar, …)` corre a análise noutro
processo e o resultado volta por pickle. Com AIRMETs lidos em vigor o
resultado traz objectos `MetBlock`, e `nicegui_app/motor.py` criava o módulo
`motor_gamet` com `types.ModuleType` sem o registar em `sys.modules`:

    PicklingError: Can't pickle <class 'motor_gamet.MetBlock'>:
    import of module 'motor_gamet' failed

e o briefing não aparecia (caso real: GAMET 251500/252100 do arquivo, com os
AIRMET 1 e 2 de 25-out). Pior: nos caminhos "colado" e "arquivo" ficava no
ecrã o briefing ANTERIOR, com o texto novo na caixa; ao abrir, ficava o
"A carregar o GAMET…" para sempre.

Os testes do test_nicegui.py não apanhavam isto: chamam `analisar` no mesmo
processo. Aqui corre-se num ProcessPoolExecutor real (fork, spawn e
forkserver, os três métodos que a NiceGUI pode usar) e no próprio
`nicegui.run.cpu_bound`; e, na página simulada, uma excepção na análise tem
de tirar o briefing anterior e mostrar o erro, nos três caminhos.
"""
import asyncio
import json
import multiprocessing as mp
import pickle
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from conftest import build_gamet
from test_v40 import AIR1_25, AIR2_25, COD_AIR2, G251500, _cod

pytest.importorskip("nicegui")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "nicegui_app"))
import main as ng  # noqa: E402

DADOS = RAIZ / "dados"
FMT = "%Y-%m-%dT%H:%MZ"

# Índice sintético (não depende de dados/): o GAMET 251500 e os dois AIRMETs
# reais de 25-out, com as validades do arquivo.
ENTRADA = {"ficheiro": "gamets/2026/10/g251500.txt", "inicio": "2026-10-25T15:00Z",
           "fim": "2026-10-25T21:00Z", "tipo": "GAMET", "recolhido": "2026-10-25T14:42Z"}
INDICE = {"gamets": [ENTRADA], "sigmets": [
    {"texto": AIR1_25, "inicio": "2026-10-25T18:10Z", "fim": "2026-10-25T21:00Z"},
    {"texto": AIR2_25, "inicio": "2026-10-25T18:40Z", "fim": "2026-10-25T21:00Z"},
]}
METODOS = [m for m in ("fork", "spawn", "forkserver") if m in mp.get_all_start_methods()]


def _real():
    """(texto, índice, entrada) do GAMET 251500/252100 no arquivo real."""
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/ (ramo dados)")
    idx = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    ent = [e for e in idx["gamets"] if "_251500-252100_" in e["ficheiro"]]
    if not ent:
        pytest.skip("GAMET 251500/252100 não está no arquivo")
    e = ent[0]
    txt = re.sub(r"\s+", " ", (DADOS / e["ficheiro"]).read_text(encoding="utf-8")).strip()
    return txt, idx, e


def _decisoes(r):
    return {_cod(n): (ng.M.find_region_for_point(r["regioes"], la, lo) or {}).get("decision")
            for n, (la, lo) in ng.M.AERODROMES.items()}


def _resumo(r):
    return (_decisoes(r), [(g["decision"], g["reasons"]) for g in r["regioes"]], r["avisos"],
            r["faixa_sig"], [round(g["polygon"].area, 9) for g in r["regioes"]])


def _tem_metblock(r):
    return any(type(b) is ng.M.MetBlock for a in r["airmet_leituras"] for b in a["blocos"])


def _no_processo(metodo, *args):
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context(metodo)) as ex:
        return ex.submit(ng.analisar, *args).result(timeout=300)


# --- A causa -----------------------------------------------------------------

def test_motor_registado_em_sys_modules():
    assert sys.modules["motor_gamet"] is ng.M
    assert ng.M.MetBlock.__module__ == "motor_gamet"
    b = ng.M.MetBlock("VIS", ng.M.FIR_POLYGON, 200, origem="AIRMET 2", window="18–21Z")
    c = pickle.loads(pickle.dumps(b))
    assert type(c) is ng.M.MetBlock
    assert (c.phenomenon, c.value, c.origem, c.window) == ("VIS", 200, "AIRMET 2", "18–21Z")
    assert c.polygon.equals(b.polygon)


def test_resultado_com_airmets_faz_round_trip_por_pickle():
    r = ng.analisar(G251500, "arquivo_hist", None, None, "", INDICE, ENTRADA)
    assert _tem_metblock(r)          # o caso que rebentava
    r2 = pickle.loads(pickle.dumps(r))
    assert _resumo(r2) == _resumo(r)
    assert {c for c, d in _decisoes(r2).items() if d == "NO-GO"} == COD_AIR2


# --- Num processo a sério (como o cpu_bound) ---------------------------------

@pytest.mark.parametrize("metodo", METODOS)
def test_analisar_noutro_processo_boletins_sinteticos(metodo):
    local = ng.analisar(G251500, "arquivo_hist", None, None, "", INDICE, ENTRADA)
    r = _no_processo(metodo, G251500, "arquivo_hist", None, None, "", INDICE, ENTRADA)
    assert _tem_metblock(r)
    assert _resumo(r) == _resumo(local)
    assert {c for c, d in _decisoes(r).items() if d == "NO-GO"} == COD_AIR2
    assert any("AIRMET 2 — VIS 200m < 1500m" in m for g in r["regioes"] for m in g["reasons"])


@pytest.mark.parametrize("metodo", METODOS)
def test_analisar_noutro_processo_arquivo_real_251500(metodo):
    txt, idx, e = _real()
    local = ng.analisar(txt, "arquivo_hist", None, None, "", idx, e)
    r = _no_processo(metodo, txt, "arquivo_hist", None, None, "", idx, e)
    assert _tem_metblock(r)
    assert _resumo(r) == _resumo(local)
    assert {c for c, d in _decisoes(r).items() if d == "NO-GO"} == COD_AIR2
    assert {d for c, d in _decisoes(r).items() if c not in COD_AIR2} == {"GO"}


def test_pela_propria_nicegui_run_cpu_bound():
    """O caminho da página: nicegui.run.cpu_bound com o pool da NiceGUI."""
    from nicegui import run

    async def corre():
        run.setup()
        try:
            return await run.cpu_bound(ng.analisar, G251500, "arquivo_hist", None, None, "",
                                       INDICE, ENTRADA)
        finally:
            run.tear_down()
    r = asyncio.run(corre())
    assert r is not None and _tem_metblock(r)
    assert {c for c, d in _decisoes(r).items() if d == "NO-GO"} == COD_AIR2


@pytest.mark.parametrize("metodo", METODOS)
def test_pdf_noutro_processo(metodo):
    r = ng.analisar(G251500, "arquivo_hist", None, None, "", INDICE, ENTRADA)
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context(metodo)) as ex:
        dados = ex.submit(ng._gerar_pdf, r["regioes"], r["texto"], r["fz"], r["qnh"],
                          r["validity_label"]).result(timeout=300)
    assert bytes(dados[:5]) == b"%PDF-"


# --- Falhar em voz alta na página -------------------------------------------

G_A = build_gamet("SECN I SFC VIS: N OF N4100 2000M BR", validity="251500/252100")
G_B = build_gamet("SECN I SFC VIS: 0800M FG", validity="251500/252100")


@pytest.fixture
def ng_sim(monkeypatch):
    """Página de nicegui_app/main.py simulada (nicegui.testing.User), com a
    rede simulada e o cpu_bound/io_bound no mesmo processo (a simulação corre
    o main.py com runpy, e as funções dele não se podem enviar a outro
    processo — o regresso por pickle é testado acima)."""
    from nicegui import run
    from nicegui.testing.user_simulation import user_simulation

    async def _inline(f, *a, **k):
        return f(*a, **k)
    monkeypatch.setattr(run, "cpu_bound", _inline)
    monkeypatch.setattr(run, "io_bound", _inline)
    M = ng.M
    monkeypatch.setattr(M, "fetch_gamet_ipma", lambda url="": (True, G_A))
    monkeypatch.setitem(M._IPMA_LAST, "raw", "")
    monkeypatch.setitem(M._IPMA_LAST, "at", None)
    idx = {"gamets": [dict(ENTRADA, ficheiro="gamets/b.txt")], "sigmets": []}
    monkeypatch.setattr(M, "fetch_arquivo_indice", lambda: (True, idx))
    monkeypatch.setattr(M, "fetch_arquivo", lambda f: (True, G_B))
    return user_simulation(main_file=RAIZ / "nicegui_app" / "main.py")


def _rebenta_com(monkeypatch, texto_alvo):
    original = ng.M.analisar_gamet

    def falso(texto, *a, **k):
        if texto == texto_alvo:
            raise ValueError("falha simulada")
        return original(texto, *a, **k)
    monkeypatch.setattr(ng.M, "analisar_gamet", falso)


async def _sem_briefing(user):
    await user.should_see("Não foi possível analisar este GAMET")
    await user.should_see("ValueError: falha simulada")
    await user.should_not_see("BRIEFING POR REGIÕES")
    await user.should_not_see("A carregar o GAMET")
    await user.should_not_see("A analisar o GAMET")


def test_nicegui_erro_no_gamet_actual(ng_sim, monkeypatch):
    _rebenta_com(monkeypatch, G_A)

    async def corpo():
        async with ng_sim as user:
            await user.open("/")
            await _sem_briefing(user)
    asyncio.run(corpo())


def test_nicegui_erro_ao_obter_o_gamet_actual(ng_sim, monkeypatch):
    def rebenta(url=""):
        raise ConnectionError("rede em baixo")
    monkeypatch.setattr(ng.M, "fetch_gamet_ipma", rebenta)

    async def corpo():
        async with ng_sim as user:
            await user.open("/")
            await user.should_see("Não foi possível obter o GAMET")
            await user.should_see("ConnectionError: rede em baixo")
            await user.should_not_see("A carregar o GAMET")
    asyncio.run(corpo())


def test_nicegui_erro_no_texto_colado_tira_o_briefing_anterior(ng_sim, monkeypatch):
    _rebenta_com(monkeypatch, G_B)

    async def corpo():
        from nicegui import ui
        async with ng_sim as user:
            await user.open("/")
            await user.should_see("BRIEFING POR REGIÕES")   # o do GAMET actual (G_A)
            user.find(ui.textarea).elements.pop().value = G_B
            user.find("Analisar este texto").click()
            await _sem_briefing(user)
    asyncio.run(corpo())


def test_nicegui_erro_no_arquivo_tira_o_briefing_anterior(ng_sim, monkeypatch):
    _rebenta_com(monkeypatch, G_B)

    async def corpo():
        async with ng_sim as user:
            await user.open("/")
            await user.should_see("BRIEFING POR REGIÕES")
            user.find("Abrir arquivo").click()
            await user.should_see("Carregar e analisar")
            user.find("Carregar e analisar").click()
            await _sem_briefing(user)
    asyncio.run(corpo())


def test_nicegui_sem_erro_desenha_o_briefing_novo(ng_sim, monkeypatch):
    """Controlo: o mesmo caminho sem excepção desenha o briefing do texto novo."""
    async def corpo():
        from nicegui import ui
        async with ng_sim as user:
            await user.open("/")
            await user.should_see("BRIEFING POR REGIÕES")
            user.find(ui.textarea).elements.pop().value = G_B
            user.find("Analisar este texto").click()
            await user.should_see("VIS 800m")
            await user.should_not_see("Não foi possível analisar")
    asyncio.run(corpo())


def test_mensagem_de_erro_usa_o_tipo_do_subprocesso():
    from nicegui.run import SubprocessException
    x = SubprocessException("PicklingError", "Can't pickle X", "tb")
    msg = ng._msg_erro_analise(x)
    assert msg.startswith("**Não foi possível analisar este GAMET** — PicklingError: Can't pickle X")
    assert "tb" not in msg
