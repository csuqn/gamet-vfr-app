"""
2.7 — SIGMET/AIRMET sem "=" final.

Os primeiros boletins reais apanhados na página do IPMA (17-out-2026, 10:14Z)
vinham SEM o "=" final. Até à 2.6 o "=" era obrigatório: a app não os via
(dizia "sem SIGMET em vigor", faixa NIL — erro optimista) e a recolha
guardava-os em sigmets/desconhecidos/.
"""
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

from conftest import build_gamet

SIG_T01 = ("LPPC SIGMET T01 VALID 171010/171410 LPPT- LPPC LISBOA FIR EMBD TS FCST WI "
           "N4137 W00616 - N4157 W00634 - N4156 W00713 - N4152 W00746 - N4008 W00810 - "
           "N3947 W00658 - N4137 W00616 TOP FL360 STNR NC")
AIR_1 = ("LPPC AIRMET 1 VALID 171000/171300 LPPT- LPPC LISBOA FIR/MAINLAND AREA MOD TURB OBS "
         "WI 10NM OF N3845 W00930 FL015 STNR WKN")
DURANTE = datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)
G = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="170900/171500")


def test_extrai_boletins_reais_sem_igual_em_blocos_pre(net):
    html = f"<html><pre>{SIG_T01}</pre><pre>{AIR_1}</pre></html>"
    assert net.extract_bulletins_from_html(html) == [SIG_T01, AIR_1]


def test_extrai_sem_blocos_pre_e_nao_engole_o_seguinte(net):
    texto = f"<div>{SIG_T01}<br>{AIR_1}<br>LPPC GAMET VALID 171500/172100 LPPT- ...=</div>"
    assert net.extract_bulletins_from_html(texto) == [SIG_T01, AIR_1]


def test_com_igual_continua_a_funcionar(net):
    assert net.extract_bulletins_from_html(f"<pre>{SIG_T01}=</pre>") == [SIG_T01 + "="]


def test_designador_alfanumerico_activo_e_cancelado(eng):
    s, a = eng.active_bulletins([SIG_T01, AIR_1], DURANTE)
    assert s == [SIG_T01] and a == [AIR_1]
    cnl = "LPPC SIGMET T02 VALID 171200/171410 LPPT- LPPC LISBOA FIR CNL SIGMET T01 171010/171410"
    s, _ = eng.active_bulletins([SIG_T01, cnl], datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc))
    assert s == []


def test_sigmet_real_forca_no_go_e_faixa_activo(eng, net):
    boletins = net.extract_bulletins_from_html(f"<pre>{SIG_T01}</pre><pre>{AIR_1}</pre>")
    r = eng.analisar_gamet(G, "ipma", boletins=boletins, boletins_at=DURANTE, agora=DURANTE)
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    texto = " ".join(m for _, m in r["avisos"])
    assert "SIGMET T01" in texto and "AIRMET 1" in texto


def test_recolha_classifica_os_boletins_reais():
    raiz = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("rec", raiz / "scripts" / "recolher_gamet.py")
    rec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rec)
    for b in (SIG_T01, AIR_1):
        m = rec._SIGMET_RE.search(b)
        assert m and m.group(1).strip() == b
