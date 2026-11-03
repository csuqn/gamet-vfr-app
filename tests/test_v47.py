"""
4.7 — Calendário no painel "Arquivo de GAMETs" (pedido do Duarte a
2-nov-2026): escolher o dia num calendário e depois o GAMET desse dia.

  * arquivo_por_dia / arquivo_dias_extremos / arquivo_dia_mais_proximo
    (funções puras, secção de rede do app.py — fixture `net`): índice real
    (dados/indice.json; salta sem dados/) e índices sintéticos;
  * app Streamlit completa (rede simulada): date_input com min/max do
    arquivo, dia com GAMETs → lista certa → carregar → fonte arquivo_hist;
    dia sem GAMETs → mensagem com o dia mais próximo;
  * NiceGUI (salta sem NiceGUI): ui.date só com os dias do arquivo
    seleccionáveis e marcados, abre no mais recente; escolher dia + GAMET
    carrega e analisa com a fonte arquivo_hist.

Nada do motor de decisão muda.
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import build_gamet, veredicto

RAIZ = Path(__file__).resolve().parent.parent
INDICE_REAL = RAIZ / "dados" / "indice.json"
FMT = "%Y-%m-%dT%H:%MZ"


def _g(ini, fim, rec, ficheiro, tipo="GAMET"):
    return {"ficheiro": ficheiro, "recolhido": rec.strftime(FMT),
            "inicio": ini.strftime(FMT) if ini else None,
            "fim": fim.strftime(FMT) if fim else None, "tipo": tipo}


def _t(d, h, m=0):
    return datetime(2026, 10, d, h, m, tzinfo=timezone.utc)


def _rotulos(por_dia, dia):
    return [x["rotulo"] for x in por_dia[dia]]


def _fich(por_dia, dia):
    return [x["entrada"]["ficheiro"] for x in por_dia[dia]]


# ---------------------------------------------------------------------
# Função pura — índices sintéticos
# ---------------------------------------------------------------------

def test_indice_vazio(net):
    for ind in ({"gamets": [], "sigmets": []}, {}, None):
        pd = net.arquivo_por_dia(ind)
        assert pd == {}
        assert net.arquivo_dias_extremos(pd) == (None, None)
        assert net.arquivo_dia_mais_proximo(pd, "2026-10-15") is None


def test_um_dia_ordem_cronologica(net):
    ind = {"gamets": [
        _g(_t(15, 15), _t(15, 21), _t(15, 14, 20), "c.txt"),
        _g(_t(15, 3), _t(15, 9), _t(15, 2, 20), "a.txt"),
        _g(_t(15, 9), _t(15, 15), _t(15, 8, 20), "b.txt"),
    ]}
    pd = net.arquivo_por_dia(ind)
    assert list(pd) == ["2026-10-15"]
    assert _fich(pd, "2026-10-15") == ["a.txt", "b.txt", "c.txt"]
    assert _rotulos(pd, "2026-10-15") == ["03–09Z", "09–15Z", "15–21Z"]
    assert net.arquivo_dias_extremos(pd) == ("2026-10-15", "2026-10-15")
    # a entrada é a do índice (a mesma que analisar_gamet recebe)
    assert pd["2026-10-15"][0]["entrada"] is ind["gamets"][1]


def test_amd_cor_e_emissoes_repetidas(net):
    """Os rótulos são os que o Streamlit já dava até à 4.6 (test_v16)."""
    ini, fim = _t(15, 9), _t(15, 15)
    ind = {"gamets": [
        _g(ini, fim, ini - timedelta(minutes=10), "o.txt"),
        _g(ini, fim, ini + timedelta(hours=3), "a2.txt", "AMD"),
        _g(ini, fim, ini + timedelta(hours=1), "a1.txt", "AMD"),
        _g(ini, fim, ini + timedelta(hours=2), "c.txt", "COR"),
    ]}
    pd = net.arquivo_por_dia(ind)
    assert _fich(pd, "2026-10-15") == ["o.txt", "a1.txt", "c.txt", "a2.txt"]
    assert _rotulos(pd, "2026-10-15") == [
        "09–15Z", "09–15Z AMD (1.ª emissão)", "09–15Z COR", "09–15Z AMD (2.ª emissão)"]
    assert not any("recolhido" in r for r in _rotulos(pd, "2026-10-15"))


def test_duas_emissoes_do_mesmo_periodo(net):
    ini, fim = _t(16, 15), _t(16, 21)
    ind = {"gamets": [_g(ini, fim, ini + timedelta(minutes=40), "b.txt"),
                      _g(ini, fim, ini - timedelta(minutes=20), "a.txt")]}
    pd = net.arquivo_por_dia(ind)
    assert _fich(pd, "2026-10-16") == ["a.txt", "b.txt"]
    assert _rotulos(pd, "2026-10-16") == ["15–21Z (1.ª emissão)", "15–21Z (2.ª emissão)"]


def test_travessia_da_meia_noite_fica_no_dia_do_inicio(net):
    ind = {"gamets": [_g(_t(17, 21), _t(18, 3), _t(17, 20, 20), "n.txt"),
                      _g(_t(18, 3), _t(18, 9), _t(18, 2, 20), "m.txt")]}
    pd = net.arquivo_por_dia(ind)
    assert _fich(pd, "2026-10-17") == ["n.txt"]
    assert _rotulos(pd, "2026-10-17") == ["21–03Z"]
    assert _fich(pd, "2026-10-18") == ["m.txt"]


def test_recolhido_antes_da_meia_noite_conta_o_inicio(net):
    """O GAMET 0300/0900 recolhido às 23:50 da véspera fica no dia do início."""
    ind = {"gamets": [_g(_t(20, 3), _t(20, 9), _t(19, 23, 50), "x.txt")]}
    assert list(net.arquivo_por_dia(ind)) == ["2026-10-20"]


def test_entradas_sem_inicio(net):
    """Sem início: dia da recolha, rótulo que o diz. Sem data nenhuma ou com
    data impossível: fora (não há dia onde a pôr). Sem ficheiro: fora."""
    ind = {"gamets": [
        {"ficheiro": "s.txt", "recolhido": "2026-10-21T10:25Z", "tipo": "GAMET"},
        {"ficheiro": "s2.txt", "recolhido": "2026-10-21T16:05Z", "inicio": None, "fim": None, "tipo": "AMD"},
        _g(_t(21, 9), _t(21, 15), _t(21, 8, 20), "n.txt"),
        {"ficheiro": "z.txt"},
        {"ficheiro": "z2.txt", "recolhido": "2026-13-45T10:00Z"},
        {"recolhido": "2026-10-21T10:00Z", "inicio": "2026-10-21T09:00Z"},
        "lixo",
    ]}
    pd = net.arquivo_por_dia(ind)
    assert list(pd) == ["2026-10-21"]
    assert _fich(pd, "2026-10-21") == ["n.txt", "s.txt", "s2.txt"]
    assert _rotulos(pd, "2026-10-21") == [
        "09–15Z", "validade ilegível (recolhido às 10:25Z)", "validade ilegível (recolhido às 16:05Z) AMD"]


def test_meses_e_anos_diferentes(net):
    ind = {"gamets": [
        _g(datetime(2027, 1, 2, 9, tzinfo=timezone.utc), datetime(2027, 1, 2, 15, tzinfo=timezone.utc),
           datetime(2027, 1, 2, 8, tzinfo=timezone.utc), "c.txt"),
        _g(datetime(2026, 12, 31, 21, tzinfo=timezone.utc), datetime(2027, 1, 1, 3, tzinfo=timezone.utc),
           datetime(2026, 12, 31, 20, tzinfo=timezone.utc), "b.txt"),
        _g(datetime(2026, 3, 21, 15, tzinfo=timezone.utc), datetime(2026, 3, 21, 21, tzinfo=timezone.utc),
           datetime(2026, 3, 21, 15, tzinfo=timezone.utc), "a.txt"),
    ]}
    pd = net.arquivo_por_dia(ind)
    assert list(pd) == ["2026-03-21", "2026-12-31", "2027-01-02"]
    assert net.arquivo_dias_extremos(pd) == ("2026-03-21", "2027-01-02")
    assert _rotulos(pd, "2026-12-31") == ["21–03Z"]


def test_dia_mais_proximo(net):
    pd = {"2026-10-10": [], "2026-10-14": [], "2026-10-20": []}
    assert net.arquivo_dia_mais_proximo(pd, "2026-10-14") == "2026-10-14"
    assert net.arquivo_dia_mais_proximo(pd, "2026-10-13") == "2026-10-14"
    assert net.arquivo_dia_mais_proximo(pd, date(2026, 10, 11)) == "2026-10-10"
    assert net.arquivo_dia_mais_proximo(pd, "2026-10-17") == "2026-10-20"   # empate → o mais recente
    assert net.arquivo_dia_mais_proximo(pd, "2026-10-12") == "2026-10-14"   # empate → o mais recente
    assert net.arquivo_dia_mais_proximo(pd, "2025-01-01") == "2026-10-10"
    assert net.arquivo_dia_mais_proximo(pd, "2027-01-01") == "2026-10-20"


# ---------------------------------------------------------------------
# Função pura — índice real
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def indice_real():
    if not INDICE_REAL.exists():
        pytest.skip("sem dados/ (ramo dados)")
    return json.loads(INDICE_REAL.read_text(encoding="utf-8"))


def test_indice_real_todos_os_gamets_num_dia(net, indice_real):
    pd = net.arquivo_por_dia(indice_real)
    fichs = [x["entrada"]["ficheiro"] for v in pd.values() for x in v]
    # nenhum GAMET perdido nem repetido
    assert sorted(fichs) == sorted(e["ficheiro"] for e in indice_real["gamets"])
    for dia, lista in pd.items():
        date.fromisoformat(dia)
        chaves = [(x["entrada"].get("inicio") or x["entrada"]["recolhido"], x["entrada"]["recolhido"])
                  for x in lista]
        assert chaves == sorted(chaves), dia
        for x in lista:
            e = x["entrada"]
            assert (e.get("inicio") or e["recolhido"])[:10] == dia
            if e.get("inicio"):
                assert x["rotulo"].startswith(f"{e['inicio'][11:13]}–{e['fim'][11:13]}Z")
        assert len({x["rotulo"] for x in lista}) == len(lista), dia   # rótulos distintos no dia
    d0, d1 = net.arquivo_dias_extremos(pd)
    assert d0 == min(pd) and d1 == max(pd)
    assert net.arquivo_dia_mais_proximo(pd, d1) == d1


def test_indice_real_dias_conhecidos(net, indice_real):
    """Os dois GAMETs históricos isolados (21/03 e 06/09) e a recolha
    contínua desde 14/10; o 141500/142100 recolhido às 18:25 fica a 14/10."""
    pd = net.arquivo_por_dia(indice_real)
    assert net.arquivo_dias_extremos(pd)[0] == "2026-03-21"
    assert _rotulos(pd, "2026-03-21") == ["15–21Z"]
    assert "15–21Z" in _rotulos(pd, "2026-10-14")
    assert net.arquivo_dia_mais_proximo(pd, "2026-06-01") == "2026-03-21"
    assert net.arquivo_dia_mais_proximo(pd, "2026-08-01") == "2026-09-06"
    assert net.arquivo_dia_mais_proximo(pd, "2026-10-01") == "2026-10-14"


# ---------------------------------------------------------------------
# App Streamlit completa (rede simulada)
# ---------------------------------------------------------------------

class RespostaFalsa:
    def __init__(self, status, texto=""):
        self.status_code, self.text = status, texto


def _app(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    return testing.AppTest.from_file(str(app_path), default_timeout=180)


def _arquivo_simulado(monkeypatch):
    """Três dias com GAMETs (12, 14 e 15 do mês passado de há 20 dias) e o
    texto de cada um; devolve (índice, {ficheiro: texto})."""
    import requests
    base = (datetime.now(timezone.utc) - timedelta(days=20)).replace(hour=0, minute=0, second=0,
                                                                     microsecond=0)
    d12, d14, d15 = base, base + timedelta(days=2), base + timedelta(days=3)
    gamets, textos = [], {}
    for nome, ini, corpo, tipo in [
        ("a.txt", d12.replace(hour=9), "SECN I SFC VIS: N OF N4100 5000M BR", "GAMET"),
        ("b.txt", d14.replace(hour=3), "SECN I SFC VIS: 1000M FG", "GAMET"),
        ("c.txt", d14.replace(hour=9), "SECN I SFC VIS: N OF N4100 2000M BR", "GAMET"),
        ("d.txt", d14.replace(hour=9), "SECN I SFC VIS: 0800M FG", "AMD"),
        ("e.txt", d15.replace(hour=21), "SECN I SFC VIS: N OF N4100 4000M BR", "GAMET"),
    ]:
        fim = ini + timedelta(hours=6)
        rec = ini - timedelta(minutes=20) if tipo == "GAMET" else ini + timedelta(hours=1)
        gamets.append(_g(ini, fim, rec, "gamets/" + nome, tipo))
        validade = f"{ini:%d%H}00/{fim:%d%H}00"
        textos["gamets/" + nome] = build_gamet(corpo, validity=validade).replace(
            "LPPC GAMET VALID", "LPPC GAMET AMD VALID" if tipo == "AMD" else "LPPC GAMET VALID")
    indice = {"gamets": gamets, "sigmets": []}

    def falso_get(url, **kw):
        if "raw.githubusercontent.com" in url:
            if url.endswith("indice.json"):
                return RespostaFalsa(200, json.dumps(indice))
            for f, t in textos.items():
                if url.endswith(f):
                    return RespostaFalsa(200, t)
            return RespostaFalsa(404)
        return RespostaFalsa(200, "<html>sem nada</html>")

    monkeypatch.setattr(requests, "get", falso_get)
    return indice, textos, (d12.date(), d14.date(), d15.date())


def _abrir(app_path):
    at = _app(app_path)
    at.session_state["gamet_loaded"] = "x"   # sem auto-fetch
    at.run()
    [b for b in at.button if "Abrir arquivo" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_app_calendario_abre_no_dia_mais_recente(app_path, monkeypatch):
    _, _, (d12, d14, d15) = _arquivo_simulado(monkeypatch)
    at = _abrir(app_path)
    cal = at.date_input[0]
    assert cal.value == d15
    assert cal.min == d12 and cal.max == d15
    assert not any(s.label.startswith("Dia") for s in at.selectbox)   # o selectbox de dias saiu
    sel = [s for s in at.selectbox if s.label == "GAMET"][0]
    assert list(sel.options) == ["21–03Z"]
    assert "5 GAMETs em 3 dias" in " ".join(c.value for c in at.caption)


def test_app_escolher_dia_lista_e_carregar(app_path, monkeypatch):
    indice, textos, (d12, d14, d15) = _arquivo_simulado(monkeypatch)
    at = _abrir(app_path)
    at.date_input[0].set_value(d14)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    sel = [s for s in at.selectbox if s.label == "GAMET"][0]
    # mais recente primeiro, como até à 4.6
    assert list(sel.options) == ["09–15Z AMD", "09–15Z", "03–09Z"]
    sel.set_value(2)   # o 03–09Z
    at.run()
    [b for b in at.button if "Carregar e analisar" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["gamet_fonte"] == "arquivo_hist"
    assert at.session_state["_active_gamet_text"] == textos["gamets/b.txt"]
    assert at.session_state["arquivo_entrada"]["ficheiro"] == "gamets/b.txt"
    assert at.session_state["arquivo_indice"] == indice
    assert at.session_state["gamet_loaded_at"] == "arquivo (03–09Z)"
    assert "GAMET DO ARQUIVO" in " ".join(w.value for w in at.warning)
    assert veredicto(at).startswith("NO-GO"), veredicto(at)   # 1000M FG em toda a FIR
    assert at.date_input[0].value == d14   # o dia fica escolhido


def test_app_dia_sem_gamets(app_path, monkeypatch):
    _, _, (d12, d14, d15) = _arquivo_simulado(monkeypatch)
    at = _abrir(app_path)
    d13 = d12 + timedelta(days=1)   # 13: equidistante de 12 e 14 → o mais recente
    at.date_input[0].set_value(d13)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    info = " ".join(i.value for i in at.info)
    assert f"Não há GAMETs arquivados a {d13:%d/%m/%Y}" in info
    assert f"mais próximo é {d14:%d/%m/%Y} (3 GAMET(s))" in info
    assert not [s for s in at.selectbox if s.label == "GAMET"]
    assert not [b for b in at.button if "Carregar e analisar" in b.label]
    # O botão leva ao dia mais próximo (estado em session_state, não no clique)
    [b for b in at.button if b.label == f"Ver {d14:%d/%m/%Y}"][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.date_input[0].value == d14
    sel = [s for s in at.selectbox if s.label == "GAMET"][0]
    assert list(sel.options) == ["09–15Z AMD", "09–15Z", "03–09Z"]
    at.run()   # a lista mantém-se noutros ciclos
    assert [s for s in at.selectbox if s.label == "GAMET"]


def test_app_arquivo_vazio_e_sem_datas(app_path, monkeypatch):
    import requests
    for ind, msg in [({"gamets": [], "sigmets": []}, "O arquivo ainda está vazio."),
                     ({"gamets": [{"ficheiro": "z.txt"}], "sigmets": []},
                      "O arquivo não tem GAMETs com data legível.")]:
        monkeypatch.setattr(requests, "get", lambda url, ind=ind, **kw: RespostaFalsa(
            200, json.dumps(ind)) if url.endswith("indice.json") else RespostaFalsa(404))
        at = _abrir(app_path)
        assert msg in " ".join(i.value for i in at.info)
        assert not at.date_input


# ---------------------------------------------------------------------
# NiceGUI (interface principal)
# ---------------------------------------------------------------------

@pytest.fixture
def ng_sim(monkeypatch):
    """Simulação NiceGUI (nicegui.testing.User) da página de nicegui_app/main.py,
    com a rede simulada e o cpu_bound/io_bound na mesma thread. Os testes são
    síncronos e correm o corpo com asyncio.run — sem plugin de pytest
    assíncrono (o CI não instala a NiceGUI e estes testes saltam)."""
    pytest.importorskip("nicegui")
    from nicegui import run
    from nicegui.testing.user_simulation import user_simulation
    sys.path.insert(0, str(RAIZ / "nicegui_app"))

    async def _inline(f, *a, **k):
        return f(*a, **k)
    monkeypatch.setattr(run, "cpu_bound", _inline)
    monkeypatch.setattr(run, "io_bound", _inline)
    return user_simulation(main_file=RAIZ / "nicegui_app" / "main.py")


async def _abrir_ng(user):
    from nicegui import ui
    await user.open("/")
    await user.should_see("Recarregar GAMET")
    user.find("Abrir arquivo").click()
    await user.should_see("Dias UTC")
    return user.find(ui.date).elements.pop()


def test_nicegui_calendario_opcoes_e_eventos(ng_sim, monkeypatch):
    asyncio.run(_test_nicegui_calendario_opcoes_e_eventos(ng_sim, monkeypatch))


async def _test_nicegui_calendario_opcoes_e_eventos(ng_sim, monkeypatch):
    _, _, (d12, d14, d15) = _arquivo_simulado(monkeypatch)
    async with ng_sim as user:
        cal = await _abrir_ng(user)
        qdias = [d.strftime("%Y/%m/%d") for d in (d12, d14, d15)]
        assert cal.props["options"] == qdias
        assert cal.props["events"] == qdias
        assert cal.value == d15.isoformat()           # abre no mais recente
        assert cal.props["navigation-min-year-month"] == d12.strftime("%Y/%m")
        assert cal.props["navigation-max-year-month"] == d15.strftime("%Y/%m")
        await user.should_see("5 GAMETs em 3 dias")
        from nicegui import ui
        sel = user.find(ui.select).elements
        sel = [s for s in sel if s.props.get("label") == "GAMET"][0]
        assert list(sel.options.values()) == ["21–03Z"]


def test_nicegui_escolher_dia_e_carregar(ng_sim, monkeypatch):
    asyncio.run(_test_nicegui_escolher_dia_e_carregar(ng_sim, monkeypatch))


async def _test_nicegui_escolher_dia_e_carregar(ng_sim, monkeypatch):
    indice, textos, (d12, d14, d15) = _arquivo_simulado(monkeypatch)
    import main as ng   # o mesmo módulo que a simulação usa (motor M partilhado)
    chamadas = []
    original = ng.M.analisar_gamet

    def espiao(texto, fonte, *a, **k):
        chamadas.append((texto, fonte, a, k))
        return original(texto, fonte, *a, **k)
    monkeypatch.setattr(ng.M, "analisar_gamet", espiao)

    async with ng_sim as user:
        from nicegui import ui
        cal = await _abrir_ng(user)
        cal.value = d14.isoformat()
        await user.should_see("3 GAMET(s)")
        sel = [s for s in user.find(ui.select).elements if s.props.get("label") == "GAMET"][0]
        assert list(sel.options.values()) == ["03–09Z", "09–15Z", "09–15Z AMD"]
        assert sel.value == 2                         # o mais recente do dia
        sel.value = 0                                 # o 03–09Z
        chamadas.clear()
        user.find("Carregar e analisar").click()
        for _ in range(100):
            if chamadas:
                break
            await asyncio.sleep(0.05)
        await user.should_see("BRIEFING POR REGIÕES")
        assert len(chamadas) == 1
        texto, fonte, a, _ = chamadas[0]
        assert texto == textos["gamets/b.txt"] and fonte == "arquivo_hist"
        assert a[3] == indice and a[4]["ficheiro"] == "gamets/b.txt"
        assert user.find(ui.textarea).elements.pop().value == textos["gamets/b.txt"]

        # Dia sem GAMETs (o QDate não deixa, mas o valor pode vir do cliente)
        cal.value = (d12 + timedelta(days=1)).isoformat()
        await user.should_see("Escolhe um dia com GAMETs")
        assert not [s for s in user.find(ui.select).elements if s.props.get("label") == "GAMET"]


def test_nicegui_erro_ao_ler_gamet_notifica(ng_sim, monkeypatch):
    asyncio.run(_test_nicegui_erro_ao_ler_gamet_notifica(ng_sim, monkeypatch))


async def _test_nicegui_erro_ao_ler_gamet_notifica(ng_sim, monkeypatch):
    import requests
    indice, _, _ = _arquivo_simulado(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda url, **kw: RespostaFalsa(
        200, json.dumps(indice)) if url.endswith("indice.json") else RespostaFalsa(404))
    async with ng_sim as user:
        await _abrir_ng(user)
        user.find("Carregar e analisar").click()
        await user.should_see("Não foi possível ler o GAMET: HTTP 404")
