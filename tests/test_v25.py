"""
2.5 — Visibilidade sem unidade em SFC VIS.

O IPMA escreveu "LCA 5000 RA", sem o "M", em dois GAMETs reais (160900/161500
e 161500/162100). A app só reconhecia valores com "M" e ignorava estes em
silêncio. O `analisar.py` assinalou "Campo sem fenómeno gerado". Com 5000 m não
muda nada, mas no mesmo formato um "LCA 1200 BR" desapareceria e a zona
saía GO (erro optimista).
"""
import pytest

from conftest import build_gamet

GAMET_161500 = (
    'LPPC GAMET VALID 161500/162100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:15/18 N OF N3900 AND E OF W00800 LCA 5000 RA SIGWX:15/18 N OF N3900 AND E OF W00800 '
    'ISOL TS SIG CLD:15/18 N OF N3900 AND E OF W00800 ISOL TCU/CB 030-045/XXXHFT AGL TURB: N '
    'OF N3700 COT AND MAR LCA MOD/SEV SFC/FL030 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN '
    'II PSYS:18 N4400 W00600 H 1026HPA STNR NC CLD:N OF N3800 SCT/BKN SC/CU '
    '012-035/040-050HFT AGL N OF N3700 SCT/BKN AC/AS 060-090/120-150HFT AMSL WIND/T: BRAGANCA'
    ' PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 290/012KT PS19 360/012KT '
    'PS20 310/005KT PS20 2000FT AGL 290/008KT PS17 010/006KT PS19 280/003KT PS18 5000FT AGL '
    '270/003KT PS09 240/003KT PS14 310/004KT PS10 FL100 250/004KT PS03 260/006KT PS04 '
    '240/006KT PS03 FL150 250/008KT MS07 300/009KT MS06 280/006KT MS06 FZLVL: 11200FT AMSL '
    '12300FT AMSL 11600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 '
    '1000FT AGL 350/025KT PS23 340/007KT PS25 260/003KT PS22 2000FT AGL 360/011KT PS22 '
    '340/006KT PS22 310/004KT PS21 5000FT AGL 350/007KT PS14 350/005KT PS13 050/007KT PS14 '
    'FL100 350/002KT PS03 050/005KT PS03 360/004KT PS04 FL150 330/008KT MS05 350/008KT MS06 '
    '330/010KT MS05 FZLVL: 11300FT AMSL 11800FT AMSL 12100FT AMSL MNM QNH:1020HPA='
)


def _vis(r):
    return sorted(b.value for b in r["blocks"] if b.phenomenon == "VIS")


def test_161500_vis_sem_unidade_gera_fenomeno(analyse):
    r = analyse(GAMET_161500)
    (b,) = [b for b in r["blocks"] if b.phenomenon == "VIS"]
    assert b.value == 5000 and b.qualifier == "LCA" and b.window == "15–18Z"


@pytest.mark.parametrize("corpo, esperado, decisao", [
    ("SECN I SFC VIS:N OF N4000 LCA 1200 BR", [1200], "MARGINAL"),
    ("SECN I SFC VIS:N OF N4000 1200 BR", [1200], "NO-GO"),
    ("SECN I SFC VIS:N OF N4000 2500 RA", [2500], "MARGINAL"),
    ("SECN I SFC VIS:N OF N4000 LCA 1200-5000 BR", [1200], "MARGINAL"),
])
def test_vis_sem_unidade_conta_para_a_decisao(analyse, corpo, esperado, decisao):
    r = analyse(build_gamet(corpo))
    assert _vis(r) == esperado
    assert decisao in r["decisions"]


@pytest.mark.parametrize("corpo, esperado", [
    # Coordenadas, janelas e intervalos com unidade não são lidos duas vezes
    ("SECN I SFC VIS:09/11 N OF N3840 AND W OF W00815 LCA 0200-5000M FG/BR", [200]),
    ("SECN I SFC VIS:BTN N3840 AND N4100 E OF W00800 LCA 3000-5000M RA", [3000]),
    ("SECN I SFC VIS:N OF N4000 1500M BR", [1500]),
    ("SECN I SFC VIS:N OF N4000 5KM RA", [5000]),
])
def test_formatos_com_unidade_nao_mudam(analyse, corpo, esperado):
    assert _vis(analyse(build_gamet(corpo))) == esperado
