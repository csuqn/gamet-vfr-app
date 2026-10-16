"""
1.4 — campos do modelo OACI que a app ignorava (SFC WSPD, MTW, SIGWX além
da trovoada) e SIGMETs lidos directamente da página do IPMA.
"""
from datetime import datetime, timezone, timedelta

import pytest
from conftest import build_gamet, veredicto


# ---------------------------------------------------------------------
# Campos novos
# ---------------------------------------------------------------------

@pytest.mark.parametrize("corpo, fen, valor, decisao", [
    ("MTW:N OF N4000 SEV ABV FL050",  "MTW",  "SEV", "NO-GO"),
    ("MTW:N OF N4000 MOD ABV FL050",  "MTW",  "MOD", "MARGINAL"),
    ("SFC WSPD:N OF N4000 35KT",      "WSPD", 35,    "NO-GO"),
    ("SFC WSPD:LCA 40-50KT",          "WSPD", 50,    "NO-GO"),
    ("SFC WSPD:18MPS",                "WSPD", 35,    "NO-GO"),
    ("SIGWX:SEV SQL",                 "WX",   "SQL", "NO-GO"),
    ("SIGWX:OCNL FZRA",               "WX",   "FZRA", "NO-GO"),
    ("SIGWX:LCA FZDZ",                "WX",   "FZDZ", "NO-GO"),
    ("SIGWX:HVY DS",                  "WX",   "DS",  "NO-GO"),
    ("SIGWX:HVY SS",                  "WX",   "SS",  "NO-GO"),
    ("SIGWX:ISOL GR",                 "WX",   "GR",  "NO-GO"),
])
def test_campos_oaci(analyse, corpo, fen, valor, decisao):
    """REGRESSÃO (1.3): estes campos eram ignorados e davam GO."""
    r = analyse(build_gamet(f"SECN I {corpo}"))
    assert [(b.phenomenon, b.value) for b in r["blocks"]] == [(fen, valor)]
    assert decisao in r["decisions"]


def test_tsgr_continua_a_ser_trovoada(analyse):
    r = analyse(build_gamet("SECN I SIGWX:FRQ TSGR"))
    assert [(b.phenomenon, b.value) for b in r["blocks"]] == [("TS", "FRQ")]


def test_mtw_dentro_de_turb_nao_abre_campo(analyse):
    r = analyse(build_gamet("SECN I TURB:N OF N4000 SEV MTW SFC/FL100"))
    assert [(b.phenomenon, b.value) for b in r["blocks"]] == [("TURB", "SEV")]


def test_campos_novos_nao_passam_em_silencio_num_gamet_completo(analyse):
    """O caso perigoso: um campo novo no meio de campos conhecidos."""
    r = analyse(build_gamet(
        "SECN I SFC VIS:5000M BR SFC WSPD:35KT MTW:N OF N4100 MOD FL050/FL100 "
        "TURB:MOD SFC/FL050"))
    assert {b.phenomenon for b in r["blocks"]} == {"VIS", "WSPD", "MTW", "TURB"}
    # Duas zonas NO-GO (com e sem a onda de montanha), nenhuma GO
    assert set(r["decisions"]) == {"NO-GO"}
    assert any("SFC WSPD" in m for reg in r["regions"] for m in reg["reasons"])


def test_vento_abaixo_de_30kt_nao_altera_decisao(analyse):
    r = analyse(build_gamet("SECN I SFC WSPD:25KT"))
    assert r["decisions"] == ["GO"]


# ---------------------------------------------------------------------
# SIGMETs do IPMA
# ---------------------------------------------------------------------

def _sig(num, ini, fim, corpo="SEV TURB FCST N OF N4000 SFC/FL080 STNR NC", tipo="SIGMET"):
    v = f"{ini:%d%H%M}/{fim:%d%H%M}"
    return f"LPPC {tipo} {num} VALID {v} LPPT- LPPC LISBOA FIR {corpo}="


def _agora():
    return datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)


def test_sigmet_activo(eng):
    n = _agora()
    s, a = eng.active_bulletins([_sig(1, n - timedelta(hours=1), n + timedelta(hours=3))], n)
    assert len(s) == 1 and a == []


@pytest.mark.parametrize("ini_h, fim_h", [(-5, -1), (1, 4)])
def test_sigmet_fora_de_validade(eng, ini_h, fim_h):
    n = _agora()
    s, _ = eng.active_bulletins([_sig(1, n + timedelta(hours=ini_h), n + timedelta(hours=fim_h))], n)
    assert s == []


def test_sigmet_cancelado(eng):
    n = _agora()
    original = _sig(2, n - timedelta(hours=1), n + timedelta(hours=3))
    cnl = _sig(3, n - timedelta(minutes=30), n + timedelta(hours=3),
               corpo=f"CNL SIGMET 2 {n - timedelta(hours=1):%d%H%M}/{n + timedelta(hours=3):%d%H%M}")
    s, _ = eng.active_bulletins([original, cnl], n)
    assert s == [], "nem o cancelado nem o boletim de cancelamento contam"


def test_airmet_separado(eng):
    n = _agora()
    s, a = eng.active_bulletins(
        [_sig(1, n - timedelta(hours=1), n + timedelta(hours=2), tipo="AIRMET")], n)
    assert s == [] and len(a) == 1


def test_sigmet_que_cruza_a_meia_noite(eng):
    n = datetime(2026, 10, 14, 23, 30, tzinfo=timezone.utc)
    s, _ = eng.active_bulletins([_sig(4, n - timedelta(hours=1), n + timedelta(hours=3))], n)
    assert len(s) == 1


def test_extrair_boletins_da_pagina(net):
    """Estrutura real da página do IPMA (um boletim por bloco <pre>)."""
    pagina = (
        '<div class="left sigmet-container"><hr><b>LPPC (LISBOA FIR)</b>'
        "<pre>LPPC GAMET VALID 141500/142100 LPPT-\nLPPC LISBOA FIR/MAINLAND AREA BLW FL150\n"
        "SECN I\nSIGMET APPLICABLE: AT TIME OF ISSUE NIL\nSECN II\nMNM QNH:1022HPA=</pre>"
        "<pre>LPPC SIGMET 2 VALID 141600/142000 LPPT-\nLPPC LISBOA FIR SEV TURB FCST\n"
        "N OF N4000 SFC/FL080 STNR NC=</pre></div>")
    out = net.extract_bulletins_from_html(pagina)
    assert out == ["LPPC SIGMET 2 VALID 141600/142000 LPPT- LPPC LISBOA FIR SEV TURB FCST "
                   "N OF N4000 SFC/FL080 STNR NC="]


def test_app_aplica_sigmet_nao_referido_no_gamet(app_path):
    """
    O caso que justificou a 1.4: SIGMET em vigor no IPMA, mas o GAMET em
    vigor ainda diz NIL. A app tem de pôr NO-GO em toda a área e avisar.
    """
    testing = pytest.importorskip("streamlit.testing.v1")
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=6), agora + timedelta(hours=6)
    gamet = build_gamet("SECN I SFC VIS:N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00")
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = gamet
    at.session_state["_active_gamet_text"] = gamet
    at.session_state["ipma_boletins"] = [_sig(7, agora - timedelta(hours=1), agora + timedelta(hours=3))]
    at.session_state["ipma_boletins_at"] = agora
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    erros = " ".join(e.value for e in at.error)
    assert "SIGMET em vigor no IPMA" in erros and "não referido no GAMET" in erros
    assert "NO-GO em 100% da FIR" in veredicto(at)
