"""
4.7.2 — topo de nuvem com duas barras ("060-090/100/130HFT AMSL").

GAMET real 060300/060900 (recolhido a 6-nov-2026 02:54Z), Secção II:
"SCT/BKN AS/AC 060-090/100/130HFT AMSL" — o topo em intervalo escrito com
barra em vez de hífen (gralha do IPMA de "100-130"). `_CLD_BASE_RE` não
casava a partir da base e o "130HFT" colado à barra também não (regra da
3.10): a base desaparecia em silêncio. Na Secção II não muda nada (6000 ft
AMSL fica longe do MEF em MAR∪COT a N de N3830), mas o mesmo formato em SIG
CLD era um erro OPTIMISTA: "BKN 002-008/010/015HFT AGL" sozinho dava GO (com
aviso "Campo não interpretado") e, ao lado de um CB ISOL, MARGINAL sem aviso.

Desde a 4.7.2 aceita-se um segundo topo depois de outra barra. A base é o
primeiro número; o topo colado é ignorado; com espaços ou ABV entra no
mínimo (regra da 4.0: nunca mais alta do que uma leitura anterior).
"""
import re
from datetime import datetime, timezone

import pytest

AGORA = datetime(2026, 11, 6, 4, 0, tzinfo=timezone.utc)

G060300 = (
    "LPPC GAMET VALID 060300/060900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS: N OF N3830 MAR AND COT LCA 2000-5000 DZ/RA/BR SIG CLD:N OF N3830 MAR AND COT "
    "LCA BKN 002-008/010HFT AGL TURB:07/09 N OF N3830 COT LCA MOD/SEV SFC/FL050 SECN II "
    "PSYS:WARM FRONT N4500 W01600 - N3700 W01000 MOV NE NC CLD: N OF N3830 MAR AND COT "
    "SCT/BKN SC/CU 012-025/030-050HFT AGL SCT/BKN AS/AC 060-090/100/130HFT AMSL WIND/T: "
    "BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 110/007KT PS07 "
    "170/009KT PS11 160/006KT PS08 2000FT AGL 160/009KT PS05 170/011KT PS09 190/012KT PS07 "
    "5000FT AGL 230/011KT PS02 210/012KT PS06 240/013KT PS05 FL100 260/016KT MS00 "
    "260/018KT PS01 270/018KT PS01 FL150 280/029KT MS09 270/020KT MS09 270/020KT MS09 "
    "FZLVL: 9900FT AMSL 10700FT AMSL 10900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 "
    "W00752 N3700 W00800 1000FT AGL 130/011KT PS12 170/007KT PS12 110/007KT PS15 2000FT AGL "
    "170/010KT PS11 200/007KT PS11 180/003KT PS14 5000FT AGL 240/015KT PS09 270/015KT PS08 "
    "260/011KT PS10 FL100 260/021KT PS00 260/027KT PS01 250/018KT PS01 FL150 250/023KT "
    "MS09 270/023KT MS08 270/024KT MS09 FZLVL: 9800FT AMSL 10300FT AMSL 10500FT AMSL MNM "
    "QNH:1017HPA="
)

# Decisões do GAMET real (Secção I: base 200 ft e TURB SEV em MAR∪COT a N de
# N3830). Iguais na 4.7.1 — a Secção II não entra na decisão.
NO_GO_060300 = {"LPPR", "LP62", "LPCS", "LPSC", "LPIN", "LP63", "LP49"}

NORTE_COSTA = (41.0, -9.2)    # a N de N3830, no mar perto da costa
INTERIOR = (41.8, -6.8)       # Bragança: N de N3830, em terra (fora de MAR∪COT)


def _icao(nome):
    return nome.rsplit("(", 1)[1].rstrip(")")


def _decisoes(eng, regioes):
    return {_icao(n): eng.find_region_for_point(regioes, la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _bases_secn2(eng, gamet):
    norm = eng.normalize(gamet)
    cab, secn2 = re.split(r"SECN\s+II", norm, maxsplit=1)
    conteudo = " ".join(eng._SECN2_CLD_RE.search(secn2).group(1).split())
    blocos, *_ = eng.parse_gamet(f"{cab.split('SECN I', 1)[0]} SECN I SIG CLD:{conteudo} SECN II")
    return sorted((b.phenomenon, b.value) for b in blocos
                  if b.phenomenon in ("BASE_AGL", "BASE_AMSL"))


def _bases(eng, sig_cld):
    blocos, *_ = eng.parse_gamet(_gamet_sig(sig_cld))
    return sorted((b.phenomenon, b.value) for b in blocos
                  if b.phenomenon in ("BASE_AGL", "BASE_AMSL"))


def _gamet_sig(sig_cld):
    return ("LPPC GAMET VALID 060300/060900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
            f"SECN I SIG CLD:{sig_cld} SECN II CLD:NIL MNM QNH:1017HPA=")


# ---------------------------------------------------------------- GAMET real

def test_regex_le_a_base_do_real(eng):
    m = list(eng._CLD_BASE_RE.finditer("SCT/BKN AS/AC 060-090/100/130HFT AMSL"))
    assert [(x.group("base"), x.group("ref")) for x in m] == [("060", "AMSL")]


def test_secn2_real_le_a_base_as_ac_6000_amsl(eng):
    # 012-025/030-050HFT AGL e, novo, 060-090/100/130HFT AMSL
    assert _bases_secn2(eng, G060300) == [("BASE_AGL", 1200), ("BASE_AMSL", 6000)]


def test_secn2_real_sem_nota_nuvens_baixas(eng):
    """6000 ft AMSL em MAR∪COT a N de N3830: nenhum ponto com MEF a menos de
    500 ft — sem nota (igual à 4.7.1, mas agora por ter lido a base)."""
    esperados = [n for n, (la, lo) in eng.AERODROMES.items()
                 if 6000 - eng._terrain_elevation_ft(lo, la) < 500]
    _, nuvens = eng.nuvens_baixas_secn2(G060300)
    assert nuvens == [] or all(set(n[4]) <= set(esperados) for n in nuvens)
    assert nuvens == []
    r = eng.analisar_gamet(G060300, "manual", agora=AGORA)
    assert not [x for _t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert not [x for _t, x in r["avisos"] if "Campo não interpretado" in x]


def test_real_decisoes_dos_52_pontos_inalteradas(eng):
    regioes = eng.compute_dynamic_regions(eng.parse_gamet(G060300)[0])
    dec = _decisoes(eng, regioes)
    assert len(dec) == 52
    assert {c for c, d in dec.items() if d == "NO-GO"} == NO_GO_060300
    assert {c for c, d in dec.items() if d != "NO-GO"} == set(dec) - NO_GO_060300
    assert set(dec.values()) == {"GO", "NO-GO"}
    # A Secção II não pesa: o mesmo GAMET com "CLD: NIL" dá o mesmo
    sem = G060300.replace(
        "CLD: N OF N3830 MAR AND COT SCT/BKN SC/CU 012-025/030-050HFT AGL SCT/BKN AS/AC "
        "060-090/100/130HFT AMSL", "CLD: NIL")
    assert sem != G060300
    assert _decisoes(eng, eng.compute_dynamic_regions(eng.parse_gamet(sem)[0])) == dec


# ------------------------------------------------- o mesmo formato em SIG CLD

def test_sig_cld_duas_barras_sozinho_no_go(eng):
    """Até à 4.7.1: GO + "Campo não interpretado"."""
    g = _gamet_sig("N OF N3830 BKN 002-008/010/015HFT AGL")
    assert _bases(eng, "N OF N3830 BKN 002-008/010/015HFT AGL") == [("BASE_AGL", 200)]
    assert eng.campos_nao_interpretados(g) == []
    regioes = eng.compute_dynamic_regions(eng.parse_gamet(g)[0])
    assert eng.find_region_for_point(regioes, *INTERIOR)["decision"] == "NO-GO"
    assert eng.find_region_for_point(regioes, *NORTE_COSTA)["decision"] == "NO-GO"
    assert eng.find_region_for_point(regioes, 37.1, -8.0)["decision"] == "GO"   # Faro
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    assert not [x for _t, x in r["avisos"] if "Campo não interpretado" in x]


def test_sig_cld_duas_barras_com_cb_no_go_sem_silencio(eng):
    """Até à 4.7.1: MARGINAL (só o CB ISOL) e sem aviso — a base de 200 ft
    perdia-se em silêncio."""
    sig = "N OF N3830 BKN 002-008/010/015HFT AGL ISOL TCU/CB 015/090HFT"
    g = _gamet_sig(sig)
    assert _bases(eng, sig) == [("BASE_AGL", 200), ("BASE_AGL", 1500)]
    regioes = eng.compute_dynamic_regions(eng.parse_gamet(g)[0])
    for p in (INTERIOR, NORTE_COSTA):
        reg = eng.find_region_for_point(regioes, *p)
        assert reg["decision"] == "NO-GO", reg["reasons"]
    assert eng.find_region_for_point(regioes, 37.1, -8.0)["decision"] == "GO"


@pytest.mark.parametrize("texto, base", [
    ("BKN 002/010/015HFT AGL", 200),           # colado: o topo é ignorado
    ("BKN 004-008/010/015HTF AGL", 400),       # HTF (3.7)
    ("BKN SFC/010/015HFT AGL", 0),
    ("BKN 020/030/002HFT AGL", 2000),          # o topo colado nunca é base
    ("BKN 020/030 / 002HFT AGL", 200),         # com espaços entra no mínimo (4.0)
    ("BKN 020/030/ABV 002HFT AGL", 200),       # com ABV entra no mínimo (4.0)
    ("BKN 002/010 / 015HFT AGL", 200),         # até à 4.7.1 dava 1500 (o 015)
])
def test_duas_barras_formas(eng, texto, base):
    assert _bases(eng, f"N OF N3830 {texto}") == [("BASE_AGL", base)]


@pytest.mark.parametrize("texto, esperado", [
    # Formas que não mudam (iguais à 4.7.1)
    ("BKN 002/010HFT AGL", [("BASE_AGL", 200)]),
    ("BKN 002-008/010HFT AGL", [("BASE_AGL", 200)]),
    ("SCT 050-090/100-130HTF AMSL", [("BASE_AMSL", 5000)]),
    ("BKN 002/ABV 030HFT AGL", [("BASE_AGL", 200)]),
    ("BKN 002 / 030HFT AGL", [("BASE_AGL", 200)]),
    ("BKN 004/XXXHFT AGL", [("BASE_AGL", 400)]),
    ("06/ 090HFT", [("BASE_AGL", 9000)]),
    ("ISOL TCU/CB 020/XXXHFT AGL", [("BASE_AGL", 2000)]),
])
def test_formas_antigas_inalteradas(eng, texto, esperado):
    assert _bases(eng, f"N OF N3830 {texto}") == esperado


def test_vento_e_niveis_nao_sao_bases(eng):
    for t in ("260/009/015KT", "SFC/FL050/FL100", "06/09/12"):
        assert not list(eng._CLD_BASE_RE.finditer(t)), t


# --------------------------------------------------------------- AIRMET

def test_airmet_duas_barras_le_a_base(eng):
    """O AIRMET passa pela mesma máquina do SIG CLD."""
    a = ("LPPC AIRMET 5 VALID 060400/060700 LPPT- LPPC LISBOA FIR/MAINLAND AREA "
         "BKN CLD OBS N OF N3830 002/010/015HFT AGL STNR NC")
    lido = eng.ler_airmet(a, AGORA)
    assert lido["lido"], lido["descr"]
    assert [(b.phenomenon, b.value) for b in lido["blocos"]] == [("BASE_AGL", 200)]


# ------------------------------------------- o outro caso do arquivo (21-mar)

# GAMET 211500/212100 (arquivo histórico, texto tal como foi arquivado — já
# cortado a meio do WIND/T). Secção II: "AS/AC 060/090-100/150HFT AMSL". A
# base é o primeiro número, 6000 ft (o menor de todos: nenhuma leitura dá uma
# base mais baixa). Até à 4.7.1 perdia-se em silêncio e não havia nota.
G211500 = (
    "LPPC GAMET VALID 211500/212100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:S OF N4030 LCA 3000-5000M RA SIGWX:S OF N4030 ISOL TS SIG CLD:S OF N4030 ISO"
    "L TCU/CB 015-030/XXXHFT AGL ICE:BTN N3900 AND N4130 LCA MOD ABV FL070 TURB:S OF N370"
    "0 AND E OF W00830 MAR LCA MOD SFC/FL030 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN"
    " II PSYS:18 N3100 W01830 L 995HPA STNR NC CLD:SCT SC/CU 020-040/050HFT AGL N OF N373"
    "0 SCT/BKN AS/AC 060/090-100/150HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4"
    "115 W00840 N4045 W00750 1000FT AGL 170/007KT PS11 320/011KT PS13 110/008KT PS12 2000"
    "FT AGL 160/0"
)


def test_arquivo_211500_le_a_base_e_da_nota_amsl(eng):
    assert _bases_secn2(eng, G211500) == [("BASE_AGL", 2000), ("BASE_AMSL", 6000)]
    esperados = {n for n, (la, lo) in eng.AERODROMES.items()
                 if la > 37.5 + 1e-6 and 6000 - eng._terrain_elevation_ft(lo, la) < 500}
    assert {_icao(n) for n in esperados} == {"LPBG", "LPSE", "LP66"}
    _, nuvens = eng.nuvens_baixas_secn2(G211500)
    assert [(n[0], n[1]) for n in nuvens] == [(6000, "AMSL")]
    assert set(nuvens[0][4]) == esperados
    agora = datetime(2026, 3, 21, 16, 0, tzinfo=timezone.utc)
    r = eng.analisar_gamet(G211500, "manual", agora=agora)
    notas = [x for t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) == 1 and "6000 ft AMSL" in notas[0]
    assert all(t == "info" for t, x in r["avisos"] if "Nuvens baixas" in x)


def test_arquivo_211500_decisoes_inalteradas(eng):
    sem = G211500.replace("SCT/BKN AS/AC 060/090-100/150HFT AMSL", "")
    assert sem != G211500
    com = _decisoes(eng, eng.compute_dynamic_regions(eng.parse_gamet(G211500)[0]))
    assert com == _decisoes(eng, eng.compute_dynamic_regions(eng.parse_gamet(sem)[0]))
