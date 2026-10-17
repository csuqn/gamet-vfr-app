"""
2.2 — Redesenho (tema escuro, pensado para telemóvel).

A decisão não muda; muda a apresentação. Estes testes garantem que:
  * os componentes HTML mostram o que o motor calculou (decisão, % da FIR,
    valores) e escapam o texto;
  * a faixa do topo diz a verdade sobre os SIGMETs (ACTIVO / NIL /
    N/VERIF.) — nunca "NIL" quando não foram verificados;
  * o GAMET do IPMA é analisado logo ao abrir, sem carregar num botão.
"""
import re
from datetime import datetime, timezone, timedelta

import pytest

from conftest import build_gamet, veredicto


def _texto(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


# ---------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------

def test_veredicto_pior_decisao_e_percentagens(eng):
    t = _texto(eng.html_veredicto({"NO-GO": 18, "MARGINAL": 22, "GO": 60}, 100))
    assert t.startswith("NO-GO em 18% da FIR")
    assert "MARGINAL 22%" in t and "GO 60%" in t


def test_veredicto_marginal_e_go(eng):
    assert _texto(eng.html_veredicto({"MARGINAL": 30, "GO": 70}, 100)).startswith("MARGINAL em 30% da FIR")
    assert _texto(eng.html_veredicto({"GO": 100}, 100)).startswith("GO — condições favoráveis em toda a FIR")


def test_cartao_regiao_mostra_valores_do_motor(eng, analyse):
    r = analyse(build_gamet("SECN I SFC VIS: 1000M FG SIG CLD: OVC 002/010HFT AGL "
                            "SIGWX: OCNL TS TURB: MOD FL050/100"))
    reg = r["regions"][0]
    t = _texto(eng.html_regiao(reg, 100))
    assert "NO-GO" in t and "100% DA FIR" in t
    assert "1000M" in t and "200FT" in t and "OCNL" in t
    assert "TURB MOD" in t


def test_cartao_sem_valores_mostra_tracos(eng):
    reg = {"label": "Faro", "decision": "GO", "vis": None, "base": None, "ts": [],
           "turb": [], "ice": [], "va": [], "mt_obsc": [], "reasons": []}
    t = _texto(eng.html_regiao(reg, 40))
    assert "VIS —" in t and "BASE AGL —" in t and "CB/TS —" in t


def test_cb_sem_ts_aparece_como_cb(eng):
    reg = {"label": "Bragança", "decision": "NO-GO", "vis": None, "base": None, "ts": [],
           "turb": [], "ice": [], "va": [], "mt_obsc": [], "reasons": ["CB EMBD"]}
    assert "CB/TS CB" in _texto(eng.html_regiao(reg, 10))


def test_texto_e_escapado(eng):
    reg = {"label": "<script>x</script>", "decision": "GO", "vis": None, "base": None,
           "ts": [], "turb": [], "ice": [], "va": [], "mt_obsc": [], "reasons": ["a<b"]}
    h = eng.html_regiao(reg, 1)
    assert "<script>" not in h and "&lt;script&gt;" in h and "a&lt;b" in h


def test_aerodromo_fora_da_area(eng):
    assert "fora da área" in _texto(eng.html_aerodromo("X", None))


# ---------------------------------------------------------------------
# App completa
# ---------------------------------------------------------------------

def _app(app_path):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    return testing.AppTest.from_file(str(app_path), default_timeout=180)


def _faixa(at):
    for m in at.markdown:
        if 'class="gv-faixa"' in m.value:
            return _texto(m.value)
    return ""


class RespostaFalsa:
    def __init__(self, status, texto=""):
        self.status_code, self.text = status, texto


def _gamet_em_vigor(corpo="SECN I SFC VIS: N OF N4100 5000M BR"):
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    return build_gamet(corpo, validity=f"{ini:%d%H}00/{fim:%d%H}00")


def test_app_analisa_logo_o_gamet_do_ipma(app_path, monkeypatch):
    import requests
    gamet = _gamet_em_vigor("SECN I SFC VIS: N OF N4100 2000M BR")   # < 3000 m → MARGINAL
    monkeypatch.setattr(requests, "get", lambda url, **kw: RespostaFalsa(
        200, f"<html><pre>{gamet}</pre></html>") if "pages/actuals/sigmet" in url
        else RespostaFalsa(404))
    at = _app(app_path)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert veredicto(at).startswith("MARGINAL"), veredicto(at)
    f = _faixa(at)
    assert "SIGMET NIL" in f and "VÁLIDO" in f and "EXPIRA" in f


def test_app_faixa_sigmet_activo(app_path, monkeypatch):
    import requests
    agora = datetime.now(timezone.utc)
    gamet = _gamet_em_vigor()
    sig = (f"LPPC SIGMET 3 VALID {agora - timedelta(hours=1):%d%H%M}/"
           f"{agora + timedelta(hours=2):%d%H%M} LPPT- LPPC LISBOA FIR SEV TURB FCST=")
    monkeypatch.setattr(requests, "get", lambda url, **kw: RespostaFalsa(
        200, f"<html><pre>{gamet}</pre><pre>{sig}</pre></html>") if "pages/actuals/sigmet" in url
        else RespostaFalsa(404))
    at = _app(app_path)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "SIGMET ACTIVO" in _faixa(at)
    assert veredicto(at).startswith("NO-GO em 100% da FIR")


def test_app_faixa_gamet_colado_nao_diz_nil(app_path):
    """Colado à mão: os SIGMETs não foram verificados — a faixa não pode
    dizer NIL (seria o erro optimista)."""
    gamet = _gamet_em_vigor()
    at = _app(app_path)
    at.session_state["gamet_loaded"] = "outro texto"
    at.session_state["_active_gamet_text"] = gamet
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    f = _faixa(at)
    assert "N/VERIF." in f and "NIL" not in f
