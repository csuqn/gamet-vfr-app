"""
1.6 — Arquivo de GAMETs e recurso ao arquivo.

  * scripts/recolher_gamet.py gera dados/indice.json a partir das pastas;
  * a app escolhe o último GAMET arquivado em vigor quando o IPMA não tem
    GAMET (janela de ~45 min antes de cada emissão);
  * um GAMET do arquivo é analisado com os SIGMETs que estiveram em vigor
    durante a SUA validade — e nunca com os SIGMETs de agora;
  * GAMETs do histórico da sessão ou colados à mão não usam SIGMETs de
    ninguém (só o "SIGMET APPLICABLE" do texto).
"""
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from conftest import build_gamet, veredicto

RAIZ = Path(__file__).resolve().parent.parent
FMT = "%Y-%m-%dT%H:%MZ"


def _sig(num, ini, fim, corpo="SEV TURB FCST N OF N4000 SFC/FL080 STNR NC", tipo="SIGMET"):
    return f"LPPC {tipo} {num} VALID {ini:%d%H%M}/{fim:%d%H%M} LPPT- LPPC LISBOA FIR {corpo}="


def _g(ini, fim, rec, ficheiro="g.txt", tipo="GAMET"):
    return {"ficheiro": ficheiro, "recolhido": rec.strftime(FMT),
            "inicio": ini.strftime(FMT), "fim": fim.strftime(FMT), "tipo": tipo}


def _s(texto, ini, fim, rec):
    return {"ficheiro": "s.txt", "recolhido": rec.strftime(FMT),
            "inicio": ini.strftime(FMT), "fim": fim.strftime(FMT), "texto": texto}


T0 = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------
# Índice (recolha)
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def rec():
    spec = importlib.util.spec_from_file_location("recolher", RAIZ / "scripts" / "recolher_gamet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _escrever(base, rel, texto):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texto, encoding="utf-8")


def test_indice_gerado_das_pastas(rec, tmp_path):
    _escrever(tmp_path, "gamets/2026/10/20261015T0556Z_150300-150900_aaaa.txt",
              build_gamet("SECN I SFC VIS: 5000M BR", validity="150300/150900"))
    _escrever(tmp_path, "gamets/2026/10/20261015T0700Z_150300-150900_bbbb.txt",
              build_gamet("SECN I SFC VIS: 5000M BR", validity="150300/150900")
              .replace("LPPC GAMET VALID", "LPPC GAMET AMD VALID"))
    # Fim do mês: 31/10 21Z → 01/11 03Z
    _escrever(tmp_path, "gamets/2026/10/20261031T2050Z_312100-010300_cccc.txt",
              build_gamet("SECN I SFC VIS: 5000M BR", validity="312100/010300"))
    _escrever(tmp_path, "sigmets/2026/10/20261015T0800Z_SIGMET1_150800-151200_dddd.txt",
              _sig(1, T0 - timedelta(hours=1), T0 + timedelta(hours=3)))
    _escrever(tmp_path, "sigmets/desconhecidos/20261015T0800Z_x.txt", "lixo")
    assert rec.construir_indice(tmp_path) is True
    assert rec.construir_indice(tmp_path) is False, "sem mudanças não reescreve"
    ind = json.loads((tmp_path / "indice.json").read_text(encoding="utf-8"))
    g = {e["ficheiro"].split("_")[-1]: e for e in ind["gamets"]}
    assert g["aaaa.txt"]["inicio"] == "2026-10-15T03:00Z" and g["aaaa.txt"]["fim"] == "2026-10-15T09:00Z"
    assert g["aaaa.txt"]["tipo"] == "GAMET" and g["bbbb.txt"]["tipo"] == "AMD"
    assert g["cccc.txt"]["inicio"] == "2026-10-31T21:00Z" and g["cccc.txt"]["fim"] == "2026-11-01T03:00Z"
    assert len(ind["sigmets"]) == 1, "desconhecidos ficam de fora"
    assert ind["sigmets"][0]["texto"].startswith("LPPC SIGMET 1")
    assert ind["sigmets"][0]["inicio"] == "2026-10-15T08:00Z"


def test_indice_ignora_nomes_estranhos(rec, tmp_path):
    _escrever(tmp_path, "gamets/falhas.txt", "x")
    _escrever(tmp_path, "gamets/2026/10/20261015T0556Z_semvalidade_aaaa.txt", "x")
    rec.construir_indice(tmp_path)
    assert json.loads((tmp_path / "indice.json").read_text())["gamets"] == []


def test_indice_reconstruido_mesmo_se_a_recolha_falhar(rec, tmp_path, monkeypatch):
    """main() constrói o índice no fim, mesmo que a recolha rebente."""
    monkeypatch.setattr(rec, "DESTINO", tmp_path / "gamets")
    (tmp_path / "gamets").mkdir()

    def rebenta():
        raise RuntimeError("falha simulada")
    monkeypatch.setattr(rec, "_recolher", rebenta)
    with pytest.raises(RuntimeError):
        rec.main()
    assert (tmp_path / "indice.json").exists()


# ---------------------------------------------------------------------
# Escolha do GAMET em vigor
# ---------------------------------------------------------------------

def test_ultimo_gamet_valido(eng):
    ind = {"gamets": [
        _g(T0 - timedelta(hours=6), T0, T0 - timedelta(hours=7), "anterior"),
        _g(T0, T0 + timedelta(hours=6), T0 - timedelta(minutes=10), "actual"),
        _g(T0 + timedelta(hours=6), T0 + timedelta(hours=12), T0 + timedelta(hours=5), "seguinte"),
    ]}
    assert eng.ultimo_gamet_valido(ind, T0 + timedelta(hours=1))["ficheiro"] == "actual"
    # fim exclusivo: às 09:00 já vale o novo
    assert eng.ultimo_gamet_valido(ind, T0)["ficheiro"] == "actual"
    assert eng.ultimo_gamet_valido(ind, T0 - timedelta(minutes=1))["ficheiro"] == "anterior"
    assert eng.ultimo_gamet_valido(ind, T0 + timedelta(days=2)) is None
    assert eng.ultimo_gamet_valido({}, T0) is None


def test_emenda_ganha_ao_original(eng):
    ind = {"gamets": [
        _g(T0, T0 + timedelta(hours=6), T0 + timedelta(hours=2), "amd", "AMD"),
        _g(T0, T0 + timedelta(hours=6), T0 - timedelta(minutes=10), "original"),
    ]}
    assert eng.ultimo_gamet_valido(ind, T0 + timedelta(hours=3))["ficheiro"] == "amd"


# ---------------------------------------------------------------------
# SIGMETs de um GAMET antigo
# ---------------------------------------------------------------------

def test_boletins_do_periodo(eng):
    ini, fim = T0, T0 + timedelta(hours=6)
    dentro = _sig(1, T0 + timedelta(hours=1), T0 + timedelta(hours=3))
    antes = _sig(2, T0 - timedelta(hours=5), T0 - timedelta(hours=1))
    toca_inicio = _sig(3, T0 - timedelta(hours=2), T0 + timedelta(minutes=30))
    depois = _sig(4, fim, fim + timedelta(hours=4))
    cnl = _sig(5, T0 + timedelta(hours=2), T0 + timedelta(hours=3), corpo="CNL SIGMET 1 150700/151000")
    airmet = _sig(6, T0 + timedelta(hours=1), T0 + timedelta(hours=2), tipo="AIRMET")
    ind = {"sigmets": [
        _s(dentro, T0 + timedelta(hours=1), T0 + timedelta(hours=3), T0),
        _s(antes, T0 - timedelta(hours=5), T0 - timedelta(hours=1), T0),
        _s(toca_inicio, T0 - timedelta(hours=2), T0 + timedelta(minutes=30), T0),
        _s(depois, fim, fim + timedelta(hours=4), T0),
        _s(cnl, T0 + timedelta(hours=2), T0 + timedelta(hours=3), T0),
        _s(airmet, T0 + timedelta(hours=1), T0 + timedelta(hours=2), T0),
    ]}
    s, a = eng.boletins_do_periodo(ind, ini, fim)
    # O SIGMET 1 foi cancelado a meio, mas esteve em vigor — conta.
    assert s == [dentro, toca_inicio]
    assert a == [airmet]


def test_boletim_com_validade_ilegivel_conta(eng):
    ind = {"sigmets": [{"texto": _sig(1, T0, T0), "inicio": None, "fim": None}]}
    assert len(eng.boletins_do_periodo(ind, T0, T0 + timedelta(hours=6))[0]) == 1


# ---------------------------------------------------------------------
# Recurso ao arquivo
# ---------------------------------------------------------------------

def _gamet_valido_em(agora):
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    return build_gamet("SECN I SFC VIS: N OF N4100 5000M BR",
                       validity=f"{ini:%d%H}00/{fim:%d%H}00"), ini, fim


def test_recurso_devolve_gamet_em_vigor(eng):
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    texto, ini, fim = _gamet_valido_em(agora)
    sig = _sig(9, agora - timedelta(hours=1), agora + timedelta(hours=2))
    ind = {"gamets": [_g(ini, fim, ini, "gamets/x.txt")],
           "sigmets": [_s(sig, agora - timedelta(hours=1), agora + timedelta(hours=2), agora)]}
    lidos = []
    t, e, bol = eng.gamet_de_recurso(lambda: (True, ind),
                                     lambda f: (lidos.append(f), (True, texto + "\n"))[1], agora)
    assert t == texto and e["ficheiro"] == "gamets/x.txt" and lidos == ["gamets/x.txt"]
    assert eng.active_bulletins(bol, agora)[0] == [sig]


def test_recurso_falha_em_voz_alta(eng):
    agora = datetime.now(timezone.utc)
    texto, ini, fim = _gamet_valido_em(agora)
    ind = {"gamets": [_g(ini, fim, ini, "gamets/x.txt")], "sigmets": []}
    t, motivo, _ = eng.gamet_de_recurso(lambda: (False, "HTTP 404"), None, agora)
    assert t is None and "404" in motivo
    t, motivo, _ = eng.gamet_de_recurso(lambda: (True, {"gamets": []}), None, agora)
    assert t is None and "nenhum" in motivo
    t, motivo, _ = eng.gamet_de_recurso(lambda: (True, ind), lambda f: (False, "timeout"), agora)
    assert t is None and "timeout" in motivo


def test_recurso_nao_confia_so_no_nome_do_ficheiro(eng):
    """O índice diz que está em vigor, mas o texto do GAMET diz outra coisa."""
    agora = datetime.now(timezone.utc)
    velho = agora - timedelta(days=1)
    texto = build_gamet("SECN I SFC VIS: 5000M BR",
                        validity=f"{velho:%d%H}00/{velho + timedelta(hours=6):%d%H}00")
    ind = {"gamets": [_g(agora - timedelta(hours=1), agora + timedelta(hours=5), agora, "x")]}
    t, motivo, _ = eng.gamet_de_recurso(lambda: (True, ind), lambda f: (True, texto), agora)
    assert t is None and "já não está em vigor" in motivo


# ---------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------

class RespostaFalsa:
    def __init__(self, status, texto=""):
        self.status_code, self.text = status, texto


def test_fetch_indice(net, monkeypatch):
    monkeypatch.setattr(net.requests, "get", lambda url, **kw: RespostaFalsa(
        200, json.dumps({"gamets": [{"ficheiro": "a"}]})))
    ok, ind = net.fetch_arquivo_indice()
    assert ok and ind["gamets"] == [{"ficheiro": "a"}] and ind["sigmets"] == []
    monkeypatch.setattr(net.requests, "get", lambda url, **kw: RespostaFalsa(200, "<html>"))
    assert net.fetch_arquivo_indice() == (False, "índice ilegível")
    monkeypatch.setattr(net.requests, "get", lambda url, **kw: RespostaFalsa(404))
    assert net.fetch_arquivo_indice() == (False, "HTTP 404")


def test_pagina_sem_gamet_guarda_os_sigmets(net, monkeypatch):
    sig = _sig(3, T0, T0 + timedelta(hours=4))
    monkeypatch.setattr(net.requests, "get", lambda url, **kw: RespostaFalsa(
        200, f"<html><pre>{sig}</pre></html>"))
    ok, _ = net.fetch_gamet_ipma()
    assert not ok
    assert net.extract_bulletins_from_html(net._IPMA_LAST["sem_gamet"]) == [sig]


# ---------------------------------------------------------------------
# App completa
# ---------------------------------------------------------------------

def _app(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()   # o índice do arquivo fica em cache entre testes
    return testing.AppTest.from_file(str(app_path), default_timeout=180)


def test_app_gamet_do_arquivo_usa_sigmets_da_sua_validade(app_path):
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(days=3), agora - timedelta(days=3) + timedelta(hours=6)
    gamet = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    sig_antigo = _sig(4, ini + timedelta(hours=1), ini + timedelta(hours=3))
    sig_de_agora = _sig(8, agora - timedelta(hours=1), agora + timedelta(hours=3))
    at = _app(app_path)
    at.session_state["gamet_loaded"] = gamet
    at.session_state["_active_gamet_text"] = gamet
    at.session_state["gamet_fonte"] = "arquivo_hist"
    at.session_state["arquivo_entrada"] = _g(ini, fim, ini)
    at.session_state["arquivo_indice"] = {"gamets": [], "sigmets": [
        _s(sig_antigo, ini + timedelta(hours=1), ini + timedelta(hours=3), ini)]}
    # SIGMETs de agora na sessão: NÃO se aplicam a um GAMET antigo
    at.session_state["ipma_boletins"] = [sig_de_agora]
    at.session_state["ipma_boletins_at"] = agora
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    avisos = " ".join(w.value for w in at.warning)
    erros = " ".join(e.value for e in at.error)
    assert "GAMET DO ARQUIVO" in avisos
    assert "durante a validade deste GAMET" in erros and "SIGMET 4" in erros
    assert "SIGMET 8" not in erros
    v = veredicto(at)   # 3.0: SIGMET "N OF N4000" → só a sua área
    assert v.startswith("NO-GO em") and "100%" not in v, v


def test_app_gamet_do_arquivo_sem_sigmets(app_path):
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(days=3), agora - timedelta(days=3) + timedelta(hours=6)
    gamet = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    at = _app(app_path)
    at.session_state["gamet_loaded"] = gamet
    at.session_state["_active_gamet_text"] = gamet
    at.session_state["gamet_fonte"] = "arquivo_hist"
    at.session_state["arquivo_entrada"] = _g(ini, fim, ini)
    at.session_state["arquivo_indice"] = {"gamets": [], "sigmets": []}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "NO-GO em 100%" not in veredicto(at) and veredicto(at)
    assert any("Nenhum SIGMET" in c.value for c in at.caption)


def test_app_sem_historico_da_sessao(app_path):
    """2.1: o "Histórico de GAMETs analisados" foi retirado — a app não guarda
    nada entre sessões, e para GAMETs antigos há o arquivo."""
    gamet = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR")
    at = _app(app_path)
    at.session_state["gamet_loaded"] = gamet
    at.session_state["_active_gamet_text"] = gamet
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Briefing" in s.value for s in at.subheader)
    assert not any("Histórico" in e.label for e in at.expander)
    assert "gamet_history" not in at.session_state


def test_app_recurso_ponta_a_ponta(app_path, monkeypatch):
    """IPMA responde sem GAMET (mas com um SIGMET); a app carrega o último
    GAMET arquivado em vigor, avisa e aplica o SIGMET da página."""
    import requests
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    gamet, ini, fim = _gamet_valido_em(agora)
    sig = _sig(5, agora - timedelta(hours=1), agora + timedelta(hours=2))
    indice = {"gamets": [_g(ini, fim, ini, "gamets/2026/10/x.txt")], "sigmets": []}

    def falso_get(url, **kw):
        if "raw.githubusercontent.com" in url:
            if url.endswith("indice.json"):
                return RespostaFalsa(200, json.dumps(indice))
            if url.endswith("gamets/2026/10/x.txt"):
                return RespostaFalsa(200, gamet)
            return RespostaFalsa(404)
        if "pages/actuals/sigmet" in url:
            return RespostaFalsa(200, f"<html><pre>{sig}</pre></html>")
        return RespostaFalsa(404)

    monkeypatch.setattr(requests, "get", falso_get)
    at = _app(app_path)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["gamet_fonte"] == "arquivo_recurso"
    assert at.text_area[0].value.strip() == gamet
    [b for b in at.button if "Analisar" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "ainda não publicou o novo GAMET" in " ".join(w.value for w in at.warning)
    erros = " ".join(e.value for e in at.error)
    v = veredicto(at)   # 3.0: SIGMET "N OF N4000" → só a sua área
    assert "SIGMET 5" in erros and v.startswith("NO-GO em") and "100%" not in v, v


def test_app_sem_ipma_nem_arquivo_falha_em_voz_alta(app_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda url, **kw: RespostaFalsa(503))
    at = _app(app_path)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "gamet_loaded" not in at.session_state
    erros = " ".join(e.value for e in at.error)
    assert "Não foi possível obter o GAMET" in erros and "Arquivo:" in erros


def test_app_abrir_arquivo_e_carregar(app_path, monkeypatch):
    """Caminho completo da secção Arquivo: abrir → escolher → carregar."""
    import requests
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    ini = (agora - timedelta(days=2)).replace(hour=9, minute=0)
    fim = ini + timedelta(hours=6)
    gamet = build_gamet("SECN I SFC VIS: N OF N4100 1000M FG",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    indice = {"gamets": [_g(ini, fim, ini - timedelta(minutes=10), "gamets/a.txt")], "sigmets": []}

    def falso_get(url, **kw):
        if url.endswith("indice.json"):
            return RespostaFalsa(200, json.dumps(indice))
        if url.endswith("gamets/a.txt"):
            return RespostaFalsa(200, gamet)
        return RespostaFalsa(200, "<html>sem nada</html>")

    monkeypatch.setattr(requests, "get", falso_get)
    at = _app(app_path)
    at.session_state["gamet_loaded"] = "x"   # sem auto-fetch
    at.run()
    [b for b in at.button if "Abrir arquivo" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    [b for b in at.button if "Carregar e analisar" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["gamet_fonte"] == "arquivo_hist"
    assert at.session_state["_active_gamet_text"] == gamet
    assert "GAMET DO ARQUIVO" in " ".join(w.value for w in at.warning)
    assert any("Briefing" in s.value for s in at.subheader)


def test_recurso_ignora_sigmets_antigos_do_mesmo_dia(eng):
    """Um SIGMET de há 30 dias com o mesmo dia do mês não pode ser lido como
    estando em vigor hoje (o boletim só traz dia/hora)."""
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    texto, ini, fim = _gamet_valido_em(agora)
    antigo = agora - timedelta(days=30)
    sig = _sig(2, agora - timedelta(hours=1), agora + timedelta(hours=2))
    recente = _sig(3, agora - timedelta(hours=1), agora + timedelta(hours=2))
    ind = {"gamets": [_g(ini, fim, ini, "x")], "sigmets": [
        _s(sig, antigo - timedelta(hours=1), antigo + timedelta(hours=2), antigo),
        _s(recente, agora - timedelta(hours=1), agora + timedelta(hours=2), agora - timedelta(minutes=50))]}
    _, _, bol = eng.gamet_de_recurso(lambda: (True, ind), lambda f: (True, texto), agora)
    assert bol == [recente]


def test_app_arquivo_rotulos_so_com_validade(app_path, monkeypatch):
    """2.1: a lista mostra só a validade (e AMD/COR), não a hora de recolha;
    emendas repetidas para o mesmo período distinguem-se pela ordem."""
    import requests
    ini = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
    fim = ini + timedelta(hours=6)
    indice = {"gamets": [
        _g(ini, fim, ini - timedelta(minutes=10), "gamets/o.txt"),
        _g(ini, fim, ini + timedelta(hours=1), "gamets/a1.txt", "AMD"),
        _g(ini, fim, ini + timedelta(hours=3), "gamets/a2.txt", "AMD"),
    ], "sigmets": []}
    monkeypatch.setattr(requests, "get", lambda url, **kw: RespostaFalsa(
        200, json.dumps(indice)) if url.endswith("indice.json") else RespostaFalsa(404))
    at = _app(app_path)
    at.session_state["gamet_loaded"] = "x"
    at.run()
    [b for b in at.button if "Abrir arquivo" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    sel = [s for s in at.selectbox if s.label == "GAMET"][0]
    rotulos = list(sel.options)   # o AppTest já devolve os rótulos formatados
    assert rotulos == ["09–15Z AMD (2.ª emissão)", "09–15Z AMD (1.ª emissão)", "09–15Z"]
    assert not any("recolhido" in r for r in rotulos)
