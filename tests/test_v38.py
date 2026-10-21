"""
3.8 — topo de nuvem em intervalo ("050-090/100-130HTF AMSL").

GAMET real 201500/202100 (recolhido a 20-out-2026 14:47Z), Secção II:
"N OF N4000 AS/AC 050-090/100-130HTF AMSL". `_CLD_BASE_RE` só aceitava um
número no topo, por isso não casava a partir da base; o único casamento era o
"130HTF AMSL" depois do '-', que o filtro de topo/fim de intervalo descarta.
A base desaparecia em silêncio. Em SIG CLD, "LCA BKN 002-004/010-015HFT AGL"
dava 0 blocos e a zona saía GO em vez de NO-GO; na Secção II perdia-se a nota
"Nuvens baixas na Secção II".

Desde a 3.8 o topo pode ser um intervalo; a base continua a ser o primeiro
número (o menor do intervalo de bases) e o topo é ignorado.
"""
import re
from datetime import datetime, timezone

import pytest

from conftest import build_gamet
from test_v37 import G201500, _bases, _decisoes, _norte, _sul

AGORA = datetime(2026, 10, 20, 19, 30, tzinfo=timezone.utc)

SIG_REAL = "LCA BKN 008/010HTF AGL"


def _sig(texto_nuvem):
    """O GAMET real com outra nuvem no SIG CLD (19/21 N OF N4100)."""
    assert SIG_REAL in G201500
    return G201500.replace(SIG_REAL, texto_nuvem, 1)


def _bases_secn2(eng, gamet):
    """Bases do CLD da Secção II, lidas com a máquina do SIG CLD (como
    nuvens_baixas_secn2), sem o filtro de < 500 ft."""
    norm = eng.normalize(gamet)
    cab, secn2 = re.split(r"SECN\s+II", norm, maxsplit=1)
    conteudo = " ".join(eng._SECN2_CLD_RE.search(secn2).group(1).split())
    blocos, *_ = eng.parse_gamet(f"{cab.split('SECN I', 1)[0]} SECN I SIG CLD:{conteudo} SECN II")
    return [(b.phenomenon, b.value) for b in blocos
            if b.phenomenon in ("BASE_AGL", "BASE_AMSL")]


def test_secn2_real_le_base_as_ac_5000_amsl(eng):
    bases = _bases_secn2(eng, G201500)
    # 015-035/050HFT AGL, 012-025/050HTF AGL e, novo, 050-090/100-130HTF AMSL
    assert sorted(bases) == sorted([("BASE_AGL", 1500), ("BASE_AGL", 1200),
                                    ("BASE_AMSL", 5000)])


def test_secn2_real_as_ac_contra_mef(eng):
    """Regra da 3.6: base AMSL contra o MEF. 5000 ft AMSL a N de N4000 fica
    < 500 ft acima do MEF nos aeródromos com MEF > 4500 ft → nota (só
    informativa). Até à 3.7 a base perdia-se e não havia nota."""
    esperados = {n for n, (la, lo) in eng.AERODROMES.items()
                 if la > 40.0 + 1e-6 and 5000 - eng._terrain_elevation_ft(lo, la) < 500}
    assert esperados   # Estrela, Trás-os-Montes, Minho
    _, nuvens = eng.nuvens_baixas_secn2(G201500)
    assert [(n[0], n[1]) for n in nuvens] == [(5000, "AMSL")]
    assert set(nuvens[0][4]) == esperados
    r = eng.analisar_gamet(G201500, "manual", agora=AGORA)
    notas = [x for _t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) == 1 and "5000 ft AMSL" in notas[0]


def test_secn2_real_decisao_inalterada(eng, analyse):
    """A Secção II nunca entra na decisão: continua tudo GO."""
    assert set(_decisoes(eng, analyse(G201500)["regions"]).values()) == {"GO"}


def test_secn2_topo_em_intervalo_base_baixa_da_nota(eng):
    g = G201500.replace("SCT/BKN SC/CU 012-025/050HTF AGL",
                        "SCT/BKN SC/CU 004-025/040-050HFT AGL")
    assert g != G201500
    _, nuvens = eng.nuvens_baixas_secn2(g)
    assert sorted((n[0], n[1]) for n in nuvens) == [(400, "AGL"), (5000, "AMSL")]
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    notas = [x for _t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) == 1 and "400 ft AGL" in notas[0]


@pytest.mark.parametrize("nuvem, valor", [
    ("LCA BKN 002-004/010-015HFT AGL", 200),
    ("LCA BKN 002/010-015HFT AGL", 200),
    ("LCA BKN 002/010-015HTF AGL", 200),
    ("LCA BKN 004/010-015HFT", 400),
])
def test_sig_cld_topo_em_intervalo_le_a_base(eng, analyse, nuvem, valor):
    (b,) = _bases(analyse(_sig(nuvem)))
    assert (b.phenomenon, b.value, b.qualifier) == ("BASE_AGL", valor, "LCA")
    assert re.match(r"19\D+21", b.window), b.window
    assert abs(b.polygon.bounds[1] - 41.0) < 1e-6


def test_002_topo_em_intervalo_nogo_a_norte_de_n4100(eng, analyse):
    d = _decisoes(eng, analyse(_sig("LCA BKN 002-004/010-015HFT AGL"))["regions"])
    assert {d[n] for n in _norte(eng)} == {"NO-GO"}
    assert {d[n] for n in _sul(eng)} == {"GO"}


def test_004_topo_em_intervalo_marginal_a_norte_de_n4100(eng, analyse):
    d = _decisoes(eng, analyse(_sig("LCA BKN 004/010-015HFT"))["regions"])
    assert {d[n] for n in _norte(eng)} == {"MARGINAL"}
    assert {d[n] for n in _sul(eng)} == {"GO"}


@pytest.mark.parametrize("intervalo, simples", [
    ("LCA BKN 002-004/010-015HFT AGL", "LCA BKN 002-004/010HFT AGL"),
    ("LCA BKN 002/010-015HTF AGL", "LCA BKN 002/010HTF AGL"),
    ("LCA BKN 004/010-015HFT", "LCA BKN 004/010HFT"),
    ("BKN 020-030/040-060HFT AMSL", "BKN 020-030/040HFT AMSL"),
])
def test_topo_em_intervalo_igual_a_topo_simples(eng, analyse, intervalo, simples):
    a, b = analyse(_sig(intervalo)), analyse(_sig(simples))
    assert [(x.phenomenon, x.value) for x in _bases(a)] == \
           [(x.phenomenon, x.value) for x in _bases(b)]
    assert len(_bases(a)) == 1
    assert _decisoes(eng, a["regions"]) == _decisoes(eng, b["regions"])


def test_amsl_com_topo_em_intervalo(analyse):
    (b,) = _bases(analyse(_sig("BKN 020-030/040-060HFT AMSL")))
    assert (b.phenomenon, b.value) == ("BASE_AMSL", 2000)


@pytest.mark.parametrize("corpo, esperado", [
    # O topo (em intervalo ou não) nunca é lido como base
    ("SECN I SIG CLD:N OF N4000 BKN 020/002-004HFT AGL", [("BASE_AGL", 2000)]),
    ("SECN I SIG CLD:N OF N4000 BKN 020-030/002-004HFT AGL", [("BASE_AGL", 2000)]),
    ("SECN I SIG CLD:N OF N4000 BKN 020/002HFT AGL", [("BASE_AGL", 2000)]),
    ("SECN I SIG CLD:N OF N4000 OVC SFC/010-015HFT AGL", [("BASE_AGL", 0)]),
])
def test_topo_nunca_e_base(analyse, corpo, esperado):
    assert [(b.phenomenon, b.value) for b in _bases(analyse(build_gamet(corpo)))] == esperado
