"""
4.0 — A leitura das bases de nuvem nunca pode ser mais permissiva do que a
3.10, verificado CONTRA O MOTOR DA 3.10 (não dentro do motor novo).

O revisor rejeitou o 2188c74: para não ler o topo como base ("002/ABV 030HFT",
"002 / 030HFT"), a regra "número depois de '-' ou '/' não é base" passou a
aceitar espaços — e "ISOL TCU/CB - 002HFT AGL", "OVC - 002/010HFT AGL",
"BKN ST 002 - 004/010HFT AGL"… perdiam a base que o main lia (NO-GO → GO). A
base de 1–2 algarismos antes de barra lia janelas ("06/ 090HFT" → 600). E no
AIRMET o hífen solto de "004 - 008/010HFT" era apagado (base 800).

`tests/referencia/app_3_10.py` é uma cópia fixa do app.py do main 5dfea47
(3.10), só para este teste (o checkout do CI é raso, sem histórico). Não
editar. Gera-se um conjunto determinístico de subentradas de SIG CLD (bases e
topos com hífen colado ou com espaços, "/ABV", " / ", intervalos, janelas
"HH/HH" e "HH/" antes, TCU/CB, LCA, AGL/AMSL/sem referência, áreas) e
verifica-se, nos 52 aeródromos, que a decisão da 4.0 nunca é mais permissiva
do que a da 3.10, e que nenhuma base que a 3.10 lia se perde (cada base da
3.10 tem uma base da 4.0 do mesmo tipo, não mais alta, na mesma área).

Semente: GAMET_SEMENTE (por omissão 40); GAMET_CASOS (por omissão 300).
"""
import os
import random
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet

GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
REF = Path(__file__).resolve().parent / "referencia" / "app_3_10.py"


@pytest.fixture(scope="module")
def eng310():
    mod = types.ModuleType("motor_3_10")
    exec(compile(conftest._extract_engine(REF.read_text(encoding="utf-8")), str(REF), "exec"),
         mod.__dict__)
    assert mod.APP_VERSION == "3.10"
    return mod


def _decisoes(e, texto):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    out = {}
    for nome, (la, lo) in e.AERODROMES.items():
        r = e.find_region_for_point(regioes, la, lo)
        out[nome] = r["decision"] if r else None
    return out


def _bases(e, texto):
    blocos, *_ = e.parse_gamet(texto)
    return [b for b in blocos if b.phenomenon in ("BASE_AGL", "BASE_AMSL")]


def _comparar(eng, eng310, texto):
    novo, antigo = _decisoes(eng, texto), _decisoes(eng310, texto)
    piores = [(n, antigo[n], novo[n]) for n in antigo
              if antigo[n] and (novo[n] is None or GRAV[novo[n]] < GRAV[antigo[n]])]
    assert not piores, (texto[90:200], piores[:5])
    # Nenhuma base perdida: cada base da 3.10 tem uma da 4.0 do mesmo tipo,
    # não mais alta, cuja área contém a da 3.10.
    bn = _bases(eng, texto)
    for b in _bases(eng310, texto):
        ok = any(n.phenomenon == b.phenomenon and n.value <= b.value
                 and n.polygon.buffer(1e-6).contains(b.polygon) for n in bn)
        assert ok, (texto[90:200], "base perdida", b.phenomenon, b.value,
                    [(n.phenomenon, n.value) for n in bn])


# --- Os casos do revisor ---------------------------------------------------

REVISOR = [
    "ISOL TCU/CB - 002HFT AGL",
    "OVC ST 001 - 002/008HFT AGL",
    "N OF N4000 - 002/010HFT AGL",
    "OVC - 002/010HFT AGL",
    "BKN ST 002 - 004/010HFT AGL",
    "LCA BKN 002 - 004/010HFT AGL",
    "06/ 090HFT AGL",
    "06/09 BKN 004/010HFT AGL",
    "06/ BKN 004/010HFT AGL",
    "BKN 40/1000FT",
    # Correcções da 4.0 que têm de continuar (mais severas do que a 3.10)
    "BKN 002/ABV 030HFT AGL",
    "BKN 002/ABV030HFT",
    "BKN 002 / 030HFT AGL",
    # Topo menor do que a base (sem sentido, mas nunca mais alto do que a 3.10)
    "BKN 020/010 - 015HFT AGL",
    "BKN 020 / 002HFT AGL",
    "BKN 020-030 / 002HFT AGL",
    "BKN 020 - 030/002HFT AGL",
    "BKN 060/ABV 010HFT AMSL",
]


@pytest.mark.parametrize("nuvem", REVISOR)
def test_casos_do_revisor_nunca_piores_que_a_3_10(eng, eng310, nuvem):
    _comparar(eng, eng310, build_gamet(f"SECN I SIG CLD: {nuvem}"))


@pytest.mark.parametrize("nuvem, base", [
    ("ISOL TCU/CB - 002HFT AGL", 200),
    ("OVC ST 001 - 002/008HFT AGL", 100),        # intervalo com espaços: a mais baixa
    ("N OF N4000 - 002/010HFT AGL", 200),
    ("OVC - 002/010HFT AGL", 200),
    ("BKN ST 002 - 004/010HFT AGL", 200),
    ("LCA BKN 002 - 004/010HFT AGL", 200),
    ("06/ 090HFT AGL", 9000),                    # a janela nunca é base
    ("BKN 002/ABV 030HFT AGL", 200),
    ("BKN 002 / 030HFT AGL", 200),
])
def test_base_lida(eng, nuvem, base):
    assert min(b.value for b in _bases(eng, build_gamet(f"SECN I SIG CLD: {nuvem}"))) == base


# --- AIRMET: "004 - 008" é intervalo de bases, nunca a mais alta -----------

def test_airmet_intervalo_com_espacos_fica_a_mais_baixa(eng):
    agora = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)
    air = ("LPPC AIRMET 5 VALID 201700/202100 LPPT- LPPC LISBOA FIR/MAINLAND AREA "
           "BKN CLD 004 - 008/010HFT AGL OBS N OF N4000 STNR NC")
    la = eng.ler_airmet(air, agora)
    assert [b.value for b in la["blocos"] if b.phenomenon == "BASE_AGL"] == [400]
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="201500/202100")
    r = eng.analisar_gamet(g, "ipma", boletins=[air], boletins_at=agora, agora=agora)
    reg = eng.find_region_for_point(r["regioes"], 41.3, -7.5)
    assert reg["decision"] == "MARGINAL"


@pytest.mark.parametrize("nuvem, base", [("OVC CLD 0/1000FT", 0), ("OVC CLD 0/300M", 0),
                                         ("BKN CLD 40/100HFT", 4000),
                                         ("BKN CLD 002 - 004/010HFT AGL", 200)])
def test_airmet_bases_curtas_e_intervalos(eng, nuvem, base):
    agora = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)
    air = ("LPPC AIRMET 5 VALID 201700/202100 LPPT- LPPC LISBOA FIR/MAINLAND AREA "
           f"{nuvem} OBS N OF N4000 STNR NC")
    la = eng.ler_airmet(air, agora)
    assert la["lido"], la["descr"]
    assert min(b.value for b in la["blocos"] if b.phenomenon.startswith("BASE")) == base


# --- Gerador ---------------------------------------------------------------

JANELA = ["", "", "06/09 ", "06/ ", "21/03 ", "12/15 "]
AREA = ["", "", "N OF N4000 ", "S OF N3900 ", "E OF W00800 LAN ", "W OF W00830 COT AND MAR ",
        "BTN N3800 AND N4000 ", "N OF N4100 AND W OF W00800 "]
PREFIXO = ["", "LCA ", "ISOL TCU/CB ", "ISOL/EMBD TCU/CB ", "OVC ST ", "BKN ", "OVC ",
           "BKN SC/CU ", "LCA BKN ST ", "SCT/BKN "]
SOLTO = ["", "", "", "- ", "-"]
BASE_H = ["001", "002", "003", "004", "006", "008", "010", "015", "030", "045", "060"]
BASE_F = ["100", "200", "400", "800", "1500", "3000"]
INTERV = ["", "", "-{b}", " - {b}", " -{b}", "- {b}"]
TOPO = ["", "/{t}", "/ {t}", " / {t}", " /{t}", "/ABV {t}", "/ABV{t}", "/XXX",
        "/{t}-{t2}", "/{t} - {t2}"]
UNID = ["HFT", "HFT", "HFT", "HTF", "FT"]
REFS = ["", " AGL", " AGL", " AMSL"]


def _nuvem(rnd):
    unid = rnd.choice(UNID)
    pool = BASE_F if unid == "FT" else BASE_H
    b1 = rnd.choice(pool)
    b2 = rnd.choice(pool)
    t = rnd.choice(["010", "012", "030", "050", "080", "100"]) if unid != "FT" else \
        rnd.choice(["1000", "2000", "4000"])
    t2 = str(int(t) + 20).zfill(len(t))
    return (f"{rnd.choice(SOLTO)}{b1}{rnd.choice(INTERV).format(b=b2)}"
            f"{rnd.choice(TOPO).format(t=t, t2=t2)}{unid}{rnd.choice(REFS)}")


def _casos(n, semente):
    rnd = random.Random(semente)
    casos = []
    while len(casos) < n:
        subs = []
        for _ in range(rnd.choice([1, 1, 2])):
            subs.append(f"{rnd.choice(JANELA)}{rnd.choice(AREA)}{rnd.choice(PREFIXO)}{_nuvem(rnd)}")
        casos.append("SECN I SIG CLD:" + " ".join(subs).replace("  ", " "))
    return casos


SEMENTE = int(os.environ.get("GAMET_SEMENTE", "40"))
CASOS = _casos(int(os.environ.get("GAMET_CASOS", "300")), SEMENTE)


@pytest.mark.parametrize("corpo", CASOS)
def test_nunca_mais_permissivo_que_a_3_10(eng, eng310, corpo):
    _comparar(eng, eng310, build_gamet(corpo))


def test_referencia_e_a_3_10_do_main():
    """A cópia fixa tem de ser a 3.10 tal como está no main 5dfea47."""
    src = REF.read_text(encoding="utf-8")
    assert 'APP_VERSION = "3.10"' in src
    assert "ler_airmet" not in src
