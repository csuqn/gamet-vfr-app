"""
Vocabulário do scripts/analisar.py: falsos alarmes "Palavras desconhecidas"
em GAMETs reais (relatórios de 20, 21 e 23-out-2026).

- `SECN I HAZARDOUS WX NIL` (GAMET real 220900/221500) é a forma de NIL.
- Tempo presente com três partes `RA/DZ/BR` (GAMET real 230300/230900).
Uma palavra realmente desconhecida continua a ser assinalada, sozinha ou
combinada com barras.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import analisar  # noqa: E402

G220900 = (
    "LPPC GAMET VALID 220900/221500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
    "SECN I HAZARDOUS WX NIL SECN II PSYS:12 NIL CLD:N OF N3715 MAR AND COT "
    "SCT/BKN SC/CU 012-025/040HFT AGL 12/15 N OF N4030 AND W OF W00800 LAN "
    "SCT/BKN SC/CU 012-035/040HFT AGL MNM QNH:1021HPA="
)
G230300 = (
    "LPPC GAMET VALID 230300/230900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
    "SECN I SFC VIS:N OF N3800 LCA 2000-5000M RA/DZ/BR SIG CLD:N OF N3800 LCA "
    "BKN 004-008/012HFT AGL TURB: LCA MOD SFC/FL030 SIGMET APPLICABLE: AT TIME "
    "OF ISSUE NIL SECN II CLD:S OF N4000 SCT/BKN AC/AS 060-090/100-130HFT AMSL "
    "N OF N3800 SCT/BKN SC/CU 012-035/050HFT AGL MNM QNH:1025HPA="
)


def _desconhecidas(r):
    return [a for a in r["alertas"] if a.startswith("Palavras desconhecidas")]


@pytest.mark.parametrize("g", [G220900, G230300], ids=["220900", "230300"])
def test_gamets_reais_sem_falso_alarme(eng, g):
    r = analisar.analisar(eng, g)
    assert r["excepcao"] is None
    assert _desconhecidas(r) == [], r["alertas"]


def test_decisao_inalterada(eng):
    r = analisar.analisar(eng, G230300)
    assert r["resumo"]["MARGINAL"] > 0 and r["resumo"]["NO-GO"] == 0


@pytest.mark.parametrize("tok", ["HTX", "RA/DZ/HTX", "XYZQ/RA/BR"])
def test_palavra_desconhecida_continua_assinalada(tok):
    assert tok in analisar.palavras_desconhecidas(f"SFC VIS:LCA 2000M {tok}")


def test_combinacoes_conhecidas():
    assert analisar.palavras_desconhecidas("HAZARDOUS WX NIL") == []
    assert analisar.palavras_desconhecidas("LCA 2000M RA/DZ/BR SHRA/BR/FG") == []
