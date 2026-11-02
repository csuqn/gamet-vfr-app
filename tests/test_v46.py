"""
4.6 — qualificadores dos SIGMET/AIRMET só com graus ("S OF N33" = 33°00').

Caso real (1-nov-2026): SIGMET T02 010850/011250 "EMBD TS FCST S OF N33" e
T03 011250/011650 "EMBD TS FCST S OF N34". O Anexo 3 deixa omitir os minutos
(decisão do Duarte da 3.5 para as coordenadas "Nnn[nn] Wnnn[nn]"), mas os
qualificadores N/S/E/W OF exigiam 4 algarismos: area_sigmet devolvia None →
toda a área → NO-GO nos 52 pontos durante os GAMETs 010900/011500 e
011500/012100, por trovoada a mais de 100 NM do continente. Os T04–T06
("S OF N3430", "N3436") eram lidos e ficavam fora da área, como deve ser.

Só nos boletins: no GAMET (parse_gamet) um "S OF N38" continua sem área (toda
a FIR + aviso "Área não reconhecida"), exactamente como na 4.5.
"""
import json
import re
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from shapely.geometry import box

import conftest
from conftest import build_gamet

DADOS = Path(__file__).resolve().parent.parent / "dados"
REF45 = Path(__file__).resolve().parent / "referencia" / "app_4_5.py"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}

# GAMETs reais (ramo dados, gamets/2026/11/)
G010900 = (
    "LPPC GAMET VALID 010900/011500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:09/11 BTN N3900 AND N4100 MAR AND COT LCA 2000-5000M BR SIG CLD:09/11 BTN "
    "N3900 AND N4100 MAR AND COT LCA BKN 006-008/012HFT AGL SIGMET APPLICABLE: AT TIME OF "
    "ISSUE NIL SECN II PSYS:12 NIL CLD: S OF N3800 FEW/SCT CU/SC 015-030/045HFT AGL "
    "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL "
    "090/006KT PS13 120/015KT PS20 070/008KT PS17 2000FT AGL 070/012KT PS12 140/009KT PS19 "
    "070/009KT PS15 5000FT AGL 040/009KT PS08 090/004KT PS12 030/011KT PS09 FL100 040/010KT "
    "PS05 060/007KT PS04 060/010KT PS04 FL150 090/008KT MS03 080/013KT MS03 090/012KT MS03 "
    "FZLVL: 14000FT AMSL 13100FT AMSL 13100FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 "
    "W00752 N3700 W00800 1000FT AGL 120/008KT PS19 140/003KT PS18 110/013KT PS18 2000FT AGL "
    "120/006KT PS18 120/003KT PS17 110/014KT PS16 5000FT AGL 160/002KT PS11 090/004KT PS10 "
    "080/014KT PS11 FL100 090/010KT PS04 080/008KT PS04 080/005KT PS05 FL150 080/015KT MS04 "
    "090/014KT MS03 070/011KT MS05 FZLVL: 12100FT AMSL 12600FT AMSL 12100FT AMSL MNM "
    "QNH:1019HPA=")
G011500 = (
    "LPPC GAMET VALID 011500/012100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "HAZARDOUS WX NIL SECN II PSYS:18 NIL CLD:NIL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 "
    "N4115 W00840 N4045 W00750 1000FT AGL 090/006KT PS13 120/015KT PS20 070/008KT PS17 "
    "2000FT AGL 070/012KT PS12 140/009KT PS19 070/009KT PS15 5000FT AGL 040/009KT PS08 "
    "090/004KT PS12 030/011KT PS09 FL100 040/010KT PS05 060/007KT PS04 060/010KT PS04 FL150 "
    "090/008KT MS03 080/013KT MS03 090/012KT MS03 FZLVL: 14000FT AMSL 13100FT AMSL 13100FT "
    "AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 120/008KT "
    "PS19 140/003KT PS18 110/013KT PS18 2000FT AGL 120/006KT PS18 120/003KT PS17 110/014KT "
    "PS16 5000FT AGL 160/002KT PS11 090/004KT PS10 080/014KT PS11 FL100 090/010KT PS04 "
    "080/008KT PS04 080/005KT PS05 FL150 080/015KT MS04 090/014KT MS03 070/011KT MS05 "
    "FZLVL: 12100FT AMSL 12600FT AMSL 12100FT AMSL MNM QNH:1019HPA=")
# SIGMETs reais (ramo dados, sigmets/2026/11/)
T02 = ("LPPC SIGMET T02 VALID 010850/011250 LPPT- LPPC LISBOA FIR EMBD TS FCST S OF N33 "
       "TOP FL390 STNR NC")
T03 = ("LPPC SIGMET T03 VALID 011250/011650 LPPT- LPPC LISBOA FIR EMBD TS FCST S OF N34 "
       "TOP FL400 STNR NC")
T04 = ("LPPC SIGMET T04 VALID 011650/011950 LPPT- LPPC LISBOA FIR EMBD TS FCST S OF N3430 "
       "TOP FL400 STNR NC")

# Qualificador de boletim só com graus (o que a 4.6 passa a ler)
GRAUS_RE = conftest.GRAUS_RE


def _t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)


def _s(corpo, sid="7", val="171400/171800", tipo="SIGMET"):
    return f"LPPC {tipo} {sid} VALID {val} LPPT- LPPC LISBOA FIR {corpo}"


AGORA = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100")


def _r(eng, sigs, gamet=CALMO, agora=AGORA, fonte="ipma"):
    return eng.analisar_gamet(gamet, fonte, boletins=sigs, boletins_at=agora, agora=agora)


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


def _decisoes(eng, r):
    return {n: _dec(eng, r, *p) for n, p in eng.AERODROMES.items()}


def _tudo_nogo(r):
    return {g["decision"] for g in r["regioes"]} == {"NO-GO"}


@pytest.fixture(scope="module")
def eng45():
    mod = types.ModuleType("motor_4_5")
    mod.__dict__["__file__"] = str(REF45)
    exec(compile(conftest._extract_engine(REF45.read_text(encoding="utf-8")), str(REF45),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_5(eng, eng45):
    assert eng45.APP_VERSION == "4.5"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 6)


# --- Boletins reais ---------------------------------------------------------

@pytest.mark.parametrize("sig,agora", [(T02, "2026-11-01T09:30"), (T03, "2026-11-01T13:00")])
def test_sigmets_reais_area_lida_fora_da_area(eng, eng45, sig, agora):
    agora = _t(agora)
    assert eng45.area_sigmet(sig, agora)[0] is None          # 4.5: toda a área
    g, d = eng.area_sigmet(sig, agora)
    assert g is not None and g.is_empty, d                  # fora da área do GAMET
    assert d == "área + 10 NM"


def test_sigmets_reais_do_arquivo(eng):
    pasta = DADOS / "sigmets" / "2026" / "11"
    fs = sorted(pasta.glob("20261101T*_SIGMETT0[23]_*.txt")) if pasta.exists() else []
    if len(fs) < 2:
        pytest.skip("sem dados/")
    for f in fs:
        g, _ = eng.area_sigmet(f.read_text(encoding="utf-8"), _t("2026-11-01T12:00"))
        assert g is not None and g.is_empty, f.name


@pytest.mark.parametrize("gamet,sigs,agora", [
    (G010900, [T02], "2026-11-01T09:30"),
    (G010900, [T02], "2026-11-01T12:40"),
    (G010900, [T03], "2026-11-01T13:00"),
    (G010900, [T03], "2026-11-01T14:45"),
    (G011500, [T03], "2026-11-01T15:30"),
    (G011500, [T03], "2026-11-01T16:40"),
])
def test_gamets_reais_ipma_iguais_ao_gamet_sozinho(eng, gamet, sigs, agora):
    agora = _t(agora)
    sem = _r(eng, [], gamet, agora)
    com = _r(eng, sigs, gamet, agora)
    assert not _tudo_nogo(com)
    assert _decisoes(eng, com) == _decisoes(eng, sem)
    assert com["faixa_sig"][0] == "ACTIVO"                   # continua em voz alta
    sid = re.search(r"SIGMET (T0\d)", sigs[0]).group(1)
    txt = " ".join(m for _, m in com["avisos"])
    assert f"SIGMET {sid} (EMBD TS): fora da área do GAMET" in txt


def test_gamets_reais_decisoes_esperadas(eng):
    r = _r(eng, [T02], G010900, _t("2026-11-01T09:30"))
    d = _decisoes(eng, r)
    marg = {"Espinho (LPIN)", "Santa Cruz (LPSC)", "Atouguia da Baleia (LP49)"}
    assert {n for n, v in d.items() if v == "MARGINAL"} == marg
    assert {v for n, v in d.items() if n not in marg} == {"GO"}
    r = _r(eng, [T03], G011500, _t("2026-11-01T15:30"))
    assert set(_decisoes(eng, r).values()) == {"GO"}


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


_sem_graus = conftest.indice_sem_graus


@pytest.mark.parametrize("nome", ["010900-011500", "011500-012100"])
def test_gamets_reais_arquivo_hist_iguais_ao_gamet_sozinho(eng, nome):
    indice = _arquivo()
    entrada = next((e for e in indice["gamets"] if nome in e["ficheiro"]), None)
    if entrada is None:
        pytest.skip("GAMET não está no arquivo")
    texto = (DADOS / entrada["ficheiro"]).read_text(encoding="utf-8")
    ini, fim = eng._iso_utc(entrada["inicio"]), eng._iso_utc(entrada["fim"])
    sig, _ = eng.boletins_do_periodo(indice, ini, fim)
    assert any(GRAUS_RE.search(b) for b in sig)              # o T02 e/ou o T03
    for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3), fim - timedelta(minutes=15)):
        r = eng.analisar_gamet(texto, "arquivo_hist", indice=indice, entrada=entrada, agora=agora)
        s = eng.analisar_gamet(texto, "arquivo_hist", indice=_sem_graus(indice),
                               entrada=entrada, agora=agora)
        assert not _tudo_nogo(r)
        assert _decisoes(eng, r) == _decisoes(eng, s)
        assert r["faixa_sig"][0] == "ACTIVO"


# --- Sintéticos que tocam a área do GAMET ------------------------------------

def test_n_of_n40_so_graus(eng):
    r = _r(eng, [_s("EMBD TS FCST N OF N40 TOP FL300 STNR NC")])
    assert not _tudo_nogo(r)
    assert _dec(eng, r, *eng.AERODROMES["Bragança (LPBG)"]) == "NO-GO"
    assert _dec(eng, r, 40.0 + 3 / 60, -8.0) == "NO-GO"
    assert _dec(eng, r, 40.0 - 6 / 60, -8.0) == "NO-GO"       # dentro dos 10 NM
    assert _dec(eng, r, 40.0 - 20 / 60, -8.0) != "NO-GO"
    assert _dec(eng, r, *eng.AERODROMES["Faro (LPFR)"]) != "NO-GO"


def test_w_of_w008_so_graus(eng):
    r = _r(eng, [_s("SEV TURB FCST W OF W008 SFC/FL080 STNR NC")])
    assert not _tudo_nogo(r)
    assert _dec(eng, r, 39.0, -8.0 - 5 / 60) == "NO-GO"
    k = 0.777                                                 # cos(39°)
    assert _dec(eng, r, 39.0, -8.0 + 6 / 60 / k) == "NO-GO"   # dentro dos 10 NM
    assert _dec(eng, r, 39.0, -8.0 + 20 / 60 / k) != "NO-GO"
    assert _dec(eng, r, *eng.AERODROMES["Bragança (LPBG)"]) != "NO-GO"


def test_btn_so_graus(eng):
    r = _r(eng, [_s("SEV ICE FCST BTN N38 AND N39 FL050/FL120 STNR NC")])
    assert not _tudo_nogo(r)
    assert _dec(eng, r, 38.5, -8.0) == "NO-GO"
    assert _dec(eng, r, 39.0 + 6 / 60, -8.0) == "NO-GO"
    assert _dec(eng, r, 39.0 + 20 / 60, -8.0) != "NO-GO"
    assert _dec(eng, r, 38.0 - 20 / 60, -8.0) != "NO-GO"


def test_airmet_so_graus_sem_margem(eng):
    a = _s("SFC VIS 0800M BR OBS N OF N40 STNR NC", sid="1", tipo="AIRMET")
    r = _r(eng, [a])
    assert _dec(eng, r, 40.0 + 3 / 60, -8.0) == "NO-GO"
    assert _dec(eng, r, 40.0 - 6 / 60, -8.0) == "GO"
    txt = " ".join(m for _, m in r["avisos"])
    assert "Área do AIRMET não reconhecida" not in txt


# Semiplano lido à mão; a área de referência é a do mesmo boletim escrito com
# minutos ("N40" → "N4000"), lida pela 4.5.
@pytest.mark.parametrize("corpo,semi,com_minutos,toda_45", [
    ("EMBD TS FCST N OF N40 TOP FL300 MOV S 10KT NC", (-12, 40, -5, 43),
     "EMBD TS FCST N OF N4000 TOP FL300 MOV S 10KT NC", True),
    ("EMBD TS FCST S OF N38 AND W OF W008 TOP FL300 STNR NC", (-12, 35, -8, 38),
     "EMBD TS FCST S OF N3800 AND W OF W00800 TOP FL300 STNR NC", True),
    ("EMBD TS FCST BTN W009 AND W008 TOP FL300 STNR NC", (-9, 35, -8, 43),
     "EMBD TS FCST BTN W00900 AND W00800 TOP FL300 STNR NC", True),
    ("EMBD TS FCST S BTN N38 - N39 TOP FL300 STNR NC", (-12, 35, -5, 39),
     "EMBD TS FCST S BTN N3800 - N3900 TOP FL300 STNR NC", True),
    # Misto (minutos + só graus): a 4.5 lia só o N OF N3930 e ignorava em
    # silêncio o E OF W008 (área maior); a 4.6 lê os dois e intersecta-os,
    # como os qualificadores do GAMET. Nenhum boletim do arquivo é assim.
    ("EMBD TS FCST N OF N3930 AND E OF W008 TOP FL300 STNR NC", (-8, 39.5, -5, 43),
     "EMBD TS FCST N OF N3930 AND E OF W00800 TOP FL300 STNR NC", False),
])
def test_so_graus_igual_a_forma_com_minutos(eng, eng45, corpo, semi, com_minutos, toda_45):
    """Área nova ⊆ toda a área (4.5), ⊇ semiplano lido, = a forma com minutos."""
    s = _s(corpo)
    assert (eng45.area_sigmet(s, AGORA)[0] is None) == toda_45
    g, d = eng.area_sigmet(s, AGORA)
    assert g is not None and not g.is_empty
    assert g.difference(eng.FIR_POLYGON).area < 1e-9
    alvo = eng.FIR_POLYGON.intersection(box(*semi))
    assert alvo.difference(g).area < 1e-9, corpo
    g5, d5 = eng45.area_sigmet(_s(com_minutos), AGORA)
    assert d == d5
    assert g.symmetric_difference(g5).area < 1e-12, corpo


# --- Formas com minutos inalteradas; o GAMET inalterado -----------------------

@pytest.mark.parametrize("corpo", [
    "EMBD TS FCST S OF N3430 TOP FL400 STNR NC",
    "EMBD TS FCST N OF N4000 TOP FL300 STNR NC",
    "EMBD TS FCST W OF W00800 TOP FL300 STNR NC",
    "EMBD TS FCST E OF W0800 TOP FL300 STNR NC",
    "EMBD TS FCST BTN N3800 AND N4000 TOP FL300 STNR NC",
    "EMBD TS FCST S BTN N3720 - N3800 TOP FL300 STNR NC",
    "EMBD TS FCST BTN W00900 - W00800 TOP FL300 MOV E 10KT NC",
    "EMBD TS FCST S OF N343 TOP FL400 STNR NC",                  # 3 algarismos: ilegível
    "EMBD TS FCST S OF N33X TOP FL400 STNR NC",
    "EMBD TS FCST W OF W08 TOP FL300 STNR NC",                   # 2 algarismos: ilegível
    "EMBD TS FCST W OF W0080 TOP FL300 STNR NC",
    "EMBD TS FCST NW OF N40 TOP FL300 STNR NC",                  # diagonal: toda a área
])
def test_formas_antigas_iguais_a_4_5(eng, eng45, corpo):
    s = _s(corpo)
    g6, d6 = eng.area_sigmet(s, AGORA)
    g5, d5 = eng45.area_sigmet(s, AGORA)
    assert d6 == d5
    assert (g6 is None) == (g5 is None)
    if g6 is not None:
        assert g6.symmetric_difference(g5).area < 1e-12


@pytest.mark.parametrize("corpo", [
    "SIG CLD: S OF N38 BKN 002/010HFT AGL",
    "SIG CLD: N OF N40 BKN 002/010HFT AGL",
    "SFC VIS: W OF W008 0800M FG",
    "SFC VIS: BTN N38 AND N39 0800M FG",
    "SIG CLD: N OF N4000 BKN 002/010HFT AGL",
])
def test_gamet_inalterado(eng, eng45, corpo):
    """No GAMET um qualificador só com graus continua toda a FIR + aviso."""
    if "N4000" not in corpo:
        assert eng.extract_polygon(corpo) is None
    g = build_gamet("SECN I " + corpo, validity="171500/172100")
    r6 = eng.analisar_gamet(g, "manual", agora=AGORA)
    r5 = eng45.analisar_gamet(g, "manual", agora=AGORA)
    assert r6["avisos"] == r5["avisos"]
    assert r6["por_dec"] == r5["por_dec"]
    assert _decisoes(eng, r6) == _decisoes(eng45, r5)
    if "N4000" not in corpo:
        assert _tudo_nogo(r6)
        assert any("Área não reconhecida" in m for _, m in r6["avisos"])


# --- Contra o motor da 4.5: todo o arquivo -----------------------------------
# tests/referencia/app_4_5.py é cópia fixa do app.py do main f40e20f (não
# editar).

def test_boletins_do_arquivo_contra_4_5(eng, eng45):
    indice = _arquivo()
    graus = 0
    for e in indice.get("sigmets", []):
        txt = e.get("texto", "")
        ref = eng._iso_utc(e.get("inicio")) or AGORA
        g6, d6 = eng.area_sigmet(txt, ref)
        g5, d5 = eng45.area_sigmet(txt, ref)
        if GRAUS_RE.search(txt):
            graus += 1
            assert g5 is None, txt                             # 4.5: toda a área
            assert g6 is not None, txt
            assert g6.difference(eng.FIR_POLYGON).area < 1e-9, txt
            m = re.search(r"\b([NS])\s+OF\s+N(\d{2})(?![\dA-Z])", txt)
            if m:
                lat = int(m.group(2))
                semi = box(-30, lat, 10, 60) if m.group(1) == "N" else box(-30, 20, 10, lat)
                assert eng.FIR_POLYGON.intersection(semi).difference(g6).area < 1e-9, txt
                # igual ao mesmo boletim com os minutos escritos (lido pela 4.5)
                g5m, _ = eng45.area_sigmet(txt.replace(m.group(0), m.group(0) + "00"), ref)
                assert g5m is not None and g6.symmetric_difference(g5m).area < 1e-12, txt
            continue
        assert d6 == d5, txt
        assert (g6 is None) == (g5 is None), txt
        if g6 is not None:
            assert g6.symmetric_difference(g5).area < 1e-9, txt
        a6 = eng.ler_airmet(txt, ref) if "AIRMET" in txt[:20] else None
        if a6 is not None:
            a5 = eng45.ler_airmet(txt, ref)
            assert repr(a6) == repr(a5), txt
    assert graus >= 2                                          # o T02 e o T03 reais


def test_arquivo_contra_4_5(eng, eng45):
    indice = _arquivo()
    piso_idx = _sem_graus(indice)
    com_graus = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        ini = eng._iso_utc(entrada.get("inicio"))
        fim = eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        sig, air = eng.boletins_do_periodo(indice, ini, fim)
        tem = any(GRAUS_RE.search(b) for b in sig + air)
        for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3, minutes=30),
                      fim - timedelta(minutes=15)):
            kw = dict(indice=indice, entrada=entrada, agora=agora)
            rn = eng.analisar_gamet(texto, "arquivo_hist", **kw)
            rv = eng45.analisar_gamet(texto, "arquivo_hist", **kw)
            dn, dv = _decisoes(eng, rn), _decisoes(eng45, rv)
            if not tem:
                assert rn["por_dec"] == rv["por_dec"], f.name
                assert rn["avisos"] == rv["avisos"], f.name
                assert rn["faixa_sig"] == rv["faixa_sig"], f.name
                assert dn == dv, f.name
                continue
            com_graus += 1
            piso = eng45.analisar_gamet(texto, "arquivo_hist", indice=piso_idx,
                                        entrada=entrada, agora=agora)
            dp = _decisoes(eng45, piso)
            for n in eng.AERODROMES:
                assert GRAV[dn[n]] <= GRAV[dv[n]], (f.name, n)
                assert GRAV[dn[n]] >= GRAV[dp[n]], (f.name, n)   # nunca abaixo do piso
            assert rn["faixa_sig"] == rv["faixa_sig"], f.name    # continua ACTIVO
    assert com_graus > 0
