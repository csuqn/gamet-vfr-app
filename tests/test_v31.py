"""
3.3 — Base de nuvem em SIG CLD sem referência (AGL/AMSL).

Dois GAMETs reais (172100/180300 e 180300/180900) trazem
"LCA BKN 002-008/010HFT" sem AGL nem AMSL a seguir ao HFT. `_CLD_BASE_RE`
exigia a referência, por isso a base de 200 ft desaparecia em silêncio e a
zona saía MARGINAL (só o nevoeiro LCA) em vez de NO-GO (base < 300 ft, sem
excepção LCA). O `analisar.py` assinalava "Campo sem fenómeno gerado".

Sem referência a base é lida como AGL (decisão do Duarte, 18-out-2026):
em SIG CLD o IPMA dá as bases em AGL e a falta da referência é quase
certamente uma gralha. Só "AMSL" explícito é convertido contra o relevo.
"""
import re
import sys
from pathlib import Path

import pytest

from conftest import build_gamet

GAMET_172100 = (
    'LPPC GAMET VALID 172100/180300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VI'
    'S:S OF N4000 AND W OF W00800 LCA 0200-5000M FG/BR SIG CLD:S OF N4000 AND W OF W00800 LCA B'
    'KN 002-008/010HFT ICE:N OF N4000 AND E OF W00830 LCA MOD ABV FL090 TURB:N OF N3930 LCA MOD'
    '/SEV SFC/FL060 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:00 N3650 W00715 L 1012'
    'HPA STNR NC CLD:LCA SCT/BKN SC/CU 015-030/045HFT AGL N OF N3800 LAN FEW/SCT AC/AS 060-090/'
    '100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT'
    ' AGL 060/022KT PS08 090/026KT PS16 060/032KT PS11 2000FT AGL 060/029KT PS05 090/033KT PS14'
    ' 070/040KT PS10 5000FT AGL 080/016KT PS03 050/015KT PS10 070/014KT PS06 FL100 050/014KT MS'
    '01 040/015KT MS00 020/011KT MS01 FL150 070/008KT MS10 030/007KT MS11 010/010KT MS11 FZLVL:'
    ' 9400FT AMSL 9900FT AMSL 8900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00'
    '800 1000FT AGL 030/016KT PS18 050/007KT PS18 070/005KT PS18 2000FT AGL 050/015KT PS17 060/'
    '003KT PS16 080/005KT PS17 5000FT AGL 050/009KT PS10 250/001KT PS10 250/004KT PS13 FL100 01'
    '0/010KT PS02 310/003KT PS01 280/007KT PS00 FL150 350/013KT MS10 320/011KT MS08 320/012KT M'
    'S09 FZLVL: 10500FT AMSL 10300FT AMSL 10500FT AMSL MNM QNH:1011HPA='
)

GAMET_180300 = (
    'LPPC GAMET VALID 180300/180900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VI'
    'S:S OF N3800 LCA 0200-5000M FG/BR SIG CLD:S OF N3800 LCA BKN 002-008/010HFT TURB:N OF N380'
    '0 LCA MOD/SEV SFC/FL060 SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:06 N3640 W007'
    '00 L 1011HPA STNR NC CLD:SCT/BKN SC/CU 015-030/045HFT AGL N OF N3800 LAN FEW/SCT AC/AS 060'
    '-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1'
    '000FT AGL 050/026KT PS06 070/024KT PS13 060/035KT PS08 2000FT AGL 060/034KT PS04 080/030KT'
    ' PS12 070/044KT PS07 5000FT AGL 070/019KT PS04 030/019KT PS08 070/024KT PS07 FL100 060/021'
    'KT PS01 060/025KT PS01 060/018KT PS01 FL150 050/029KT MS09 050/034KT MS10 040/026KT MS12 F'
    'ZLVL: 10500FT AMSL 10700FT AMSL 10200FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N'
    '3700 W00800 1000FT AGL 060/018KT PS15 070/019KT PS14 080/006KT PS18 2000FT AGL 070/015KT P'
    'S15 070/012KT PS15 080/005KT PS15 5000FT AGL 040/019KT PS10 040/008KT PS09 340/003KT PS11 '
    'FL100 030/010KT MS00 010/004KT MS00 180/003KT MS00 FL150 030/016KT MS10 020/006KT MS09 280'
    '/006KT MS10 FZLVL: 9800FT AMSL 9600FT AMSL 9800FT AMSL MNM QNH:1011HPA='
)

# Decisões por aeródromo (código ICAO/UL). Os NO-GO novos são os pontos
# dentro da área da base de 200 ft; os restantes ficam como estavam.
NOVOS_NOGO_172100 = set("LPPT LPCS LPSO LPFA LPFC LPMN LPPM LPSC LPSR LP48 LP49 LP50 "
                        "LP52 LP58 LP59 LP61 LP63 LP68 LP75 LP78 LP79".split())
GO_172100 = set("LP51 LP54 LP57 LPBJ LPEV LPFR".split())

NOVOS_NOGO_180300 = set("LPFR LPPM LP58 LP59 LP78".split())


def _por_codigo(eng, regioes):
    out = {}
    for nome, (la, lo) in eng.AERODROMES.items():
        cod = re.search(r"\((\w+)\)", nome).group(1)
        out[cod] = eng.find_region_for_point(regioes, la, lo)["decision"]
    return out


def _bases(r):
    return [b for b in r["blocks"] if b.phenomenon in ("BASE_AGL", "BASE_AMSL")]


@pytest.mark.parametrize("gamet", [GAMET_172100, GAMET_180300], ids=["172100", "180300"])
def test_base_sem_referencia_gera_fenomeno(analyse, gamet):
    r = analyse(gamet)
    # Uma só base: o 008 (fim do intervalo) e o 010 (topo) não são bases
    (b,) = _bases(r)
    assert b.value == 200 and b.qualifier == "LCA"


def test_172100_decisoes_por_aerodromo(eng, analyse):
    dec = _por_codigo(eng, analyse(GAMET_172100)["regions"])
    assert len(dec) == 52
    for cod in NOVOS_NOGO_172100:
        assert dec[cod] == "NO-GO", cod
    for cod in GO_172100:
        assert dec[cod] == "GO", cod
    # Todos os restantes já eram NO-GO (TURB SEV a norte de N3930)
    for cod in set(dec) - NOVOS_NOGO_172100 - GO_172100:
        assert dec[cod] == "NO-GO", cod


def test_180300_decisoes_por_aerodromo(eng, analyse):
    dec = _por_codigo(eng, analyse(GAMET_180300)["regions"])
    assert len(dec) == 52
    # A sul de N3800: base 200 ft → NO-GO (antes MARGINAL, só VIS LCA);
    # a norte, TURB SEV → NO-GO como antes. Toda a FIR fica NO-GO.
    assert set(dec.values()) == {"NO-GO"}
    for cod in NOVOS_NOGO_180300:
        assert dec[cod] == "NO-GO", cod


@pytest.mark.parametrize("gamet", [GAMET_172100, GAMET_180300], ids=["172100", "180300"])
def test_com_agl_continua_igual(eng, analyse, gamet):
    """O mesmo GAMET com "HFT AGL" lê a base como AGL, como antes, e dá as
    mesmas decisões por aeródromo do que a versão sem referência."""
    com_agl = gamet.replace("BKN 002-008/010HFT ", "BKN 002-008/010HFT AGL ", 1)
    assert com_agl != gamet
    r_agl = analyse(com_agl)
    (b,) = _bases(r_agl)
    assert b.phenomenon == "BASE_AGL" and b.value == 200
    assert _por_codigo(eng, r_agl["regions"]) == _por_codigo(eng, analyse(gamet)["regions"])


@pytest.mark.parametrize("corpo, fen, valor", [
    ("SECN I SIG CLD:N OF N4000 BKN 002-008/010HFT AGL", "BASE_AGL", 200),
    ("SECN I SIG CLD:N OF N4000 BKN 020/040HFT AMSL", "BASE_AMSL", 2000),
    ("SECN I SIG CLD:N OF N4000 BKN 002-008/010HFT", "BASE_AGL", 200),
    ("SECN I SIG CLD:N OF N4000 BKN 004/XXXHFT", "BASE_AGL", 400),
    ("SECN I SIG CLD:N OF N4000 OVC SFC/010HFT", "BASE_AGL", 0),
    ("SECN I SIG CLD:N OF N4000 BKN 800/1100FT", "BASE_AGL", 800),
])
def test_formas_da_base(analyse, corpo, fen, valor):
    (b,) = _bases(analyse(build_gamet(corpo)))
    assert (b.phenomenon, b.value) == (fen, valor)


def test_sem_referencia_igual_a_agl(eng, analyse):
    """Sem referência a base vale exactamente como AGL, e o "AMSL" explícito
    continua a ser convertido contra o relevo (dá base AGL menor)."""
    for base in ("002", "004", "010", "020", "040"):
        sem = analyse(build_gamet(f"SECN I SIG CLD:BKN {base}/060HFT"))
        agl = analyse(build_gamet(f"SECN I SIG CLD:BKN {base}/060HFT AGL"))
        assert _por_codigo(eng, sem["regions"]) == _por_codigo(eng, agl["regions"]), base
    amsl = analyse(build_gamet("SECN I SIG CLD:BKN 020/060HFT AMSL"))
    (b,) = _bases(amsl)
    assert b.phenomenon == "BASE_AMSL"
    # 2000 ft AMSL fica abaixo de 300 ft AGL no relevo mais alto → NO-GO algures
    assert "NO-GO" in set(_por_codigo(eng, amsl["regions"]).values())


def test_motivo_base_200_ft(analyse):
    r = analyse(GAMET_180300)
    motivos = {m for reg in r["regions"] for m in reg["reasons"]}
    assert any(re.search(r"BASE 200\s*ft\s*<\s*300\s*ft", m, re.I) for m in motivos), motivos


def test_analisar_ja_nao_assinala_campo_sem_fenomeno(eng):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    for gamet in (GAMET_172100, GAMET_180300):
        r = analisar.analisar(eng, gamet)
        assert r["excepcao"] is None
        assert not [a for a in r["alertas"] if a.startswith("Campo sem fenómeno")], r["alertas"]
