"""
Protótipo NiceGUI (nicegui_app/): usa o mesmo motor do app.py. Verifica
que a análise do protótipo dá exactamente as mesmas regiões e decisões que
o pipeline da app Streamlit, incluindo o SIGMET e a faixa. Salta se o
NiceGUI não estiver instalado.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from conftest import build_gamet

pytest.importorskip("nicegui")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nicegui_app"))
import main as ng  # noqa: E402

CASOS = [
    "SECN I SFC VIS: N OF N4100 2000M BR",
    "SECN I SFC VIS: 1000M FG SIG CLD: OVC 002/010HFT AGL SIGWX: OCNL TS",
    "SECN I SIG CLD: N OF N4000 BKN 045/080HFT AMSL TURB: COT MOD SFC/FL050",
    "SECN I SIGWX: S OF N3800 ISOL TS MT OBSC: N OF N4100",
]


@pytest.mark.parametrize("corpo", CASOS)
def test_mesmas_decisoes_que_a_app(analyse, corpo):
    g = build_gamet(corpo)
    a = analyse(g)
    r = ng.analisar(g, "manual")
    assert [x["decision"] for x in r["regioes"]] == a["decisions"]
    assert r["faixa_sig"] == ("N/VERIF.", None)


def test_sigmet_do_ipma_forca_no_go(analyse):
    agora = datetime.now(timezone.utc)
    sig = (f"LPPC SIGMET 2 VALID {agora - timedelta(hours=1):%d%H%M}/"
           f"{agora + timedelta(hours=2):%d%H%M} LPPT- LPPC LISBOA FIR SEV TURB FCST=")
    r = ng.analisar(build_gamet(CASOS[0]), "ipma", [sig], agora, "página do IPMA")
    assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert any(t == "erro" and "SIGMET 2" in m for t, m in r["alertas"])
