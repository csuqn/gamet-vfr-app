"""
3.7 — "HTF" como gralha de "HFT" nas bases de nuvem.

GAMET real 201500/202100 (recolhido a 20-out-2026 14:47Z): na Secção I
"SIG CLD:19/21 N OF N4100 LCA BKN 008/010HTF AGL" e na Secção II
"012-025/050HTF AGL" e "050-090/100-130HTF AMSL". `_CLD_BASE_RE` só aceitava
HFT|FT, por isso a base desaparecia em silêncio: nenhum bloco, e com
"004/010HTF" a zona saía GO (devia MARGINAL) e com "002/010HTF" GO (devia
NO-GO). `nuvens_baixas_secn2` perdia a nota pelo mesmo motivo. Com o texto
real (800 ft) a decisão é GO e continua GO.

HTF passa a ser lido como HFT (centenas de pés), só na expressão da base de
nuvem.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import build_gamet

AGORA = datetime(2026, 10, 20, 19, 30, tzinfo=timezone.utc)

G201500 = (
    "LPPC GAMET VALID 201500/202100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SIG CLD:19/21 N OF N4100 LCA BKN 008/010HTF AGL SIGMET APPLICABLE: AT TIME OF ISSUE NIL "
    "SECN II PSYS:18 N4100 W01500 - N4200 W01000 COLD FRONT MOV ESE WKN CLD:S OF N4100 "
    "FEW/SCT SC/CU 015-035/050HFT AGL 18/21 N OF N4100 SCT/BKN SC/CU 012-025/050HTF AGL "
    "N OF N4000 AS/AC 050-090/100-130HTF AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 "
    "N4115 W00840 N4045 W00750 1000FT AGL 280/017KT PS10 310/009KT PS13 310/014KT PS10 "
    "2000FT AGL 270/016KT PS08 300/014KT PS10 320/016KT PS08 5000FT AGL 290/017KT PS04 "
    "300/011KT PS05 300/011KT PS05 FL100 270/023KT MS00 280/026KT PS00 280/023KT PS01 "
    "FL150 280/028KT MS09 280/036KT MS09 280/034KT MS09 FZLVL: 9900FT AMSL 9900FT AMSL "
    "10900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL "
    "330/018KT PS13 310/018KT PS15 310/016KT PS16 2000FT AGL 330/020KT PS11 320/017KT PS12 "
    "310/014KT PS13 5000FT AGL 300/006KT PS09 290/010KT PS09 300/008KT PS11 FL100 "
    "290/017KT PS03 290/016KT PS03 290/020KT PS04 FL150 280/024KT MS06 290/024KT MS05 "
    "300/017KT MS05 FZLVL: 12100FT AMSL 12600FT AMSL 12100FT AMSL MNM QNH:1015HPA=")

FICHEIRO = (Path(__file__).resolve().parent.parent / "dados" / "gamets" / "2026" / "10"
            / "20261020T1447Z_201500-202100_9641d0d85f.txt")


def _bases(r):
    return [b for b in r["blocks"] if b.phenomenon in ("BASE_AGL", "BASE_AMSL")]


def _decisoes(eng, regioes):
    return {n: eng.find_region_for_point(regioes, la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _norte(eng):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la > 41.02}


def _sul(eng):
    return {n for n, (la, _lo) in eng.AERODROMES.items() if la < 40.98}


def test_texto_igual_ao_arquivado():
    if not FICHEIRO.exists():
        pytest.skip("arquivo de GAMETs não disponível neste checkout")
    assert " ".join(FICHEIRO.read_text(encoding="utf-8").split()) == G201500


def test_gamet_real_gera_base_800_agl_a_norte_de_n4100(eng, analyse):
    (b,) = _bases(analyse(G201500))
    assert (b.phenomenon, b.value, b.qualifier) == ("BASE_AGL", 800, "LCA")
    assert re.match(r"19\D+21", b.window), b.window
    minx, miny, maxx, maxy = b.polygon.bounds
    assert abs(miny - 41.0) < 1e-6


def test_gamet_real_decisao_go_inalterada(eng, analyse):
    assert set(_decisoes(eng, analyse(G201500)["regions"]).values()) == {"GO"}


def test_htf_igual_a_hft(eng, analyse):
    for base in ("002", "004", "008", "012"):
        htf = analyse(G201500.replace("008/010HTF AGL", f"{base}/010HTF AGL", 1))
        hft = analyse(G201500.replace("008/010HTF AGL", f"{base}/010HFT AGL", 1))
        assert [(b.phenomenon, b.value) for b in _bases(htf)] == \
               [(b.phenomenon, b.value) for b in _bases(hft)] == [("BASE_AGL", int(base) * 100)]
        assert _decisoes(eng, htf["regions"]) == _decisoes(eng, hft["regions"]), base


def test_004_htf_marginal_a_norte_de_n4100(eng, analyse):
    d = _decisoes(eng, analyse(G201500.replace("008/010HTF", "004/010HTF", 1))["regions"])
    norte, sul = _norte(eng), _sul(eng)
    assert norte and sul
    assert {d[n] for n in norte} == {"MARGINAL"}
    assert {d[n] for n in sul} == {"GO"}


def test_002_htf_nogo_a_norte_de_n4100(eng, analyse):
    d = _decisoes(eng, analyse(G201500.replace("008/010HTF", "002/010HTF", 1))["regions"])
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}
    assert {d[n] for n in _sul(eng)} == {"GO"}


@pytest.mark.parametrize("corpo, fen, valor", [
    ("SECN I SIG CLD:N OF N4000 BKN 002HTF AGL", "BASE_AGL", 200),
    ("SECN I SIG CLD:N OF N4000 BKN 002-008/010HTF", "BASE_AGL", 200),
    ("SECN I SIG CLD:N OF N4000 BKN 004/XXXHTF AGL", "BASE_AGL", 400),
    ("SECN I SIG CLD:N OF N4000 OVC SFC/010HTF AGL", "BASE_AGL", 0),
    ("SECN I SIG CLD:N OF N4000 BKN 020/040HTF AMSL", "BASE_AMSL", 2000),
])
def test_formas_da_base_com_htf(analyse, corpo, fen, valor):
    (b,) = _bases(analyse(build_gamet(corpo)))
    assert (b.phenomenon, b.value) == (fen, valor)


def test_nota_secn2_com_htf(eng):
    """Secção II com HTF e base < 500 ft → nota "Nuvens baixas na Secção II"."""
    _, nuvens = eng.nuvens_baixas_secn2(G201500)
    assert nuvens == []   # texto real: 1200 ft, sem nota
    g = G201500.replace("SCT/BKN SC/CU 012-025/050HTF AGL", "SCT/BKN SC/CU 004-025/050HTF AGL")
    _, nuvens = eng.nuvens_baixas_secn2(g)
    assert [(n[0], n[1]) for n in nuvens] == [(400, "AGL")]
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    notas = [x for t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) == 1 and "400 ft AGL" in notas[0]
    # Igual à variante com HFT
    g_hft = g.replace("004-025/050HTF", "004-025/050HFT")
    assert eng.nuvens_baixas_secn2(g_hft)[1] == nuvens


def test_analisar_py_sem_campo_sem_fenomeno(eng):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    r = analisar.analisar(eng, G201500)
    assert r["excepcao"] is None
    assert not [a for a in r["alertas"] if a.startswith("Campo sem fenómeno gerado")], r["alertas"]
    assert not [a for a in r["alertas"] if a.startswith("Palavras desconhecidas")], r["alertas"]


def test_htf_nao_e_lido_fora_da_unidade(analyse):
    """Só a unidade colada ao número muda: "HTF" solto não cria base."""
    assert _bases(analyse(build_gamet("SECN I SIG CLD:N OF N4000 BKN HTF AGL"))) == []
