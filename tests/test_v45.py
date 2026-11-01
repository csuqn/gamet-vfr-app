"""
4.5 — "D OF LINE …" nos SIGMET/AIRMET (pedido do Duarte a 1-nov-2026).

Caso real: SIGMET T01 311035/311330 ("SW OF LINE N3508 W01641 - N35 W01628 AND
W OF LINE N35 W01628 - N3149 W01734") e T01 010450/010850 ("S OF LINE N3430
W01728 - N3430 W01728 AND SW OF LINE N3430 W01728 - N3156 W01459"), EMBD TS
na parte oceânica da FIR, a mais de 100 NM da área do GAMET. Até à 4.4
qualquer LINE dava toda a área: NO-GO em todo o continente durante 7 h.
Agora cada qualificador é o semiplano do lado D da linha prolongada; vários
são intersectados; na dúvida, toda a área (ou o qualificador não restringe).
"""
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import build_gamet

AGORA = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100")

DADOS = Path(__file__).resolve().parent.parent / "dados"

G310900 = (
    "LPPC GAMET VALID 310900/311500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:09/10 BTN N3840 AND N4100 MAR AND COT LCA 0500-5000M FG/BR SIG CLD:09/10 BTN "
    "N3840 AND N4100 MAR AND COT LCA BKN 002-006/012HFT AGL SIGMET APPLICABLE: AT TIME OF "
    "ISSUE NIL SECN II PSYS:12 NIL CLD:N OF N3830 FEW/SCT SC/CU 015-025/035HFT AGL MNM "
    "QNH:1018HPA=")
G010300 = (
    "LPPC GAMET VALID 010300/010900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:BTN N3900 AND N4100 MAR AND COT LCA 0200-5000M BR/FG SIG CLD:BTN N3900 AND N4100 "
    "MAR AND COT LCA BKN 002-005/012HFT AGL SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II "
    "PSYS:06 NIL CLD: BTN N3900 AND N4100 MAR AND COT FEW/SCT SC/CU 012-025/035HFT AGL MNM "
    "QNH:1019HPA=")
T01_31 = ("LPPC SIGMET T01 VALID 311035/311330 LPPT- LPPC LISBOA FIR EMBD TS FCST SW OF LINE "
          "N3508 W01641 - N35 W01628 AND W OF LINE N35 W01628 - N3149 W01734 FL420 MOV ENE "
          "15KT NC")
T01_01 = ("LPPC SIGMET T01 VALID 010450/010850 LPPT- LPPC LISBOA FIR EMBD TS FCST S OF LINE "
          "N3430 W01728 - N3430 W01728 AND SW OF LINE N3430 W01728 - N3156 W01459 TOP FL420 "
          "STNR NC")


def _t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)


def _s(corpo, sid="7", val="171400/171800", tipo="SIGMET"):
    return f"LPPC {tipo} {sid} VALID {val} LPPT- LPPC LISBOA FIR {corpo}"


def _r(eng, sigs, gamet=CALMO, agora=AGORA, fonte="ipma"):
    return eng.analisar_gamet(gamet, fonte, boletins=sigs, boletins_at=agora, agora=agora)


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


def _ad(eng, r, nome):
    return _dec(eng, r, *eng.AERODROMES[nome])


def _decisoes(eng, r):
    return {n: _ad(eng, r, n) for n in eng.AERODROMES}


def _tudo_nogo(r):
    return {g["decision"] for g in r["regioes"]} == {"NO-GO"}


# --- Casos reais -----------------------------------------------------------

@pytest.mark.parametrize("gamet,sig,agora", [
    (G310900, T01_31, "2026-10-31T11:00"),
    (G310900, T01_31, "2026-10-31T13:20"),
    (G010300, T01_01, "2026-11-01T05:00"),
    (G010300, T01_01, "2026-11-01T08:30"),
])
def test_t01_reais_fora_da_area_decisao_igual_ao_gamet(eng, gamet, sig, agora):
    agora = _t(agora)
    sem = _r(eng, [], gamet, agora)
    com = _r(eng, [sig], gamet, agora)
    assert not _tudo_nogo(com)
    assert _decisoes(eng, com) == _decisoes(eng, sem)
    # Continua em voz alta: a faixa diz ACTIVO e o alerta diz onde está
    assert com["faixa_sig"][0] == "ACTIVO"
    txt = " ".join(m for _, m in com["avisos"])
    assert "SIGMET T01 (EMBD TS): fora da área do GAMET" in txt


def test_t01_reais_area_lida(eng):
    g, d = eng.area_sigmet(T01_31, _t("2026-10-31T11:00"))
    assert g is not None and g.is_empty
    assert "2 semiplanos" in d and "deslocação ENE 15 kt" in d
    g, d = eng.area_sigmet(T01_01, _t("2026-11-01T05:00"))
    assert g is not None and g.is_empty
    # A linha degenerada (o mesmo ponto duas vezes) não restringe nada
    assert "semiplano" in d and "1 linha ilegível ignorada" in d


def test_t01_real_semiplano_cobre_a_area_da_trovoada(eng):
    """Sem recorte à FIR: a área lida contém a zona a SW da linha."""
    t, corpo = eng._corpo_boletim(T01_31)
    geom, _ = eng._area_boletim(t, corpo, _t("2026-10-31T11:00"))
    from shapely.geometry import Point
    for lon, lat in [(-17.5, 33.0), (-18.5, 34.5), (-18.5, 31.0)]:
        assert geom.contains(Point(lon, lat)), (lon, lat)
    for lon, lat in [(-9.0, 39.0), (-12.0, 37.0), (-15.0, 36.0)]:
        assert not geom.contains(Point(lon, lat)), (lon, lat)


def test_t01_real_do_arquivo(eng):
    """O ficheiro arquivado (ramo dados), se existir, dá o mesmo."""
    f = list((DADOS / "sigmets" / "2026" / "10").glob("20261031T1046Z_SIGMETT01_*.txt")) \
        if DADOS.exists() else []
    if not f:
        pytest.skip("sem dados/")
    g, _ = eng.area_sigmet(f[0].read_text(), _t("2026-10-31T11:00"))
    assert g is not None and g.is_empty


# --- Semiplanos perto do continente ----------------------------------------

def test_n_of_line_horizontal(eng):
    r = _r(eng, [_s("EMBD TS FCST N OF LINE N3900 W01100 - N3900 W00600 TOP FL300 STNR NC")])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Porto (LPPR)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"
    assert _ad(eng, r, "Évora (LPEV)") != "NO-GO"
    assert _dec(eng, r, 39.0 - 6 / 60, -8.0) == "NO-GO"       # dentro dos 10 NM
    assert _dec(eng, r, 39.0 - 20 / 60, -8.0) != "NO-GO"


def test_e_of_line_vertical(eng):
    r = _r(eng, [_s("SEV TURB FCST E OF LINE N4300 W00800 - N3600 W00800 SFC/FL080 STNR NC")])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Évora (LPEV)") == "NO-GO"
    assert _ad(eng, r, "Porto (LPPR)") != "NO-GO"
    assert _ad(eng, r, "Lisboa (LPPT)") != "NO-GO"


def test_diagonal_sw_of_line(eng):
    # Linha de NW para SE: (-10, 42) → (-6, 37). LPPT a SW, LPBG a NE.
    r = _r(eng, [_s("EMBD TS FCST SW OF LINE N4200 W01000 - N3700 W00600 TOP FL300 STNR NC")])
    assert _ad(eng, r, "Lisboa (LPPT)") == "NO-GO"
    assert _ad(eng, r, "Bragança (LPBG)") != "NO-GO"


def test_linha_curta_e_prolongada(eng):
    """A linha vai até à fronteira da FIR: os troços das pontas prolongam-se."""
    r = _r(eng, [_s("EMBD TS FCST N OF LINE N3900 W01000 - N3900 W00930 TOP FL300 STNR NC")])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"


def test_dois_semiplanos_intersectados(eng):
    corpo = ("EMBD TS FCST N OF LINE N3800 W01100 - N3800 W00600 AND S OF LINE N4000 W01100 "
             "- N4000 W00600 TOP FL300 STNR NC")
    r = _r(eng, [_s(corpo)])
    assert _ad(eng, r, "Évora (LPEV)") == "NO-GO"
    assert _ad(eng, r, "Bragança (LPBG)") != "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"
    # Sem AND, o mesmo (como os qualificadores do GAMET)
    r2 = _r(eng, [_s(corpo.replace(" AND ", " "))])
    assert _decisoes(eng, r2) == _decisoes(eng, r)


def test_linha_com_tres_pontos(eng):
    # Quebrada: (−11, 38) → (−8, 39) → (−6, 39). N dela: LPBG sim, LPFR não.
    r = _r(eng, [_s("EMBD TS FCST N OF LINE N3800 W01100 - N3900 W00800 - N3900 W00600 "
                    "TOP FL300 STNR NC")])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"


def test_mov_estende_o_semiplano(eng):
    corpo = "EMBD TS FCST W OF LINE N4400 W01200 - N3500 W01200 TOP FL300 {} NC"
    parado = _r(eng, [_s(corpo.format("STNR"))])
    movel = _r(eng, [_s(corpo.format("MOV E 30KT"))])    # 4 h × 30 kt = 120 NM para leste
    assert _dec(eng, parado, 39.0, -10.0) != "NO-GO"
    assert _dec(eng, movel, 39.0, -10.0) == "NO-GO"


# --- Na dúvida, toda a área -------------------------------------------------

@pytest.mark.parametrize("corpo", [
    "EMBD TS FCST S OF LINE N3430 W01728 - N3430 W01728 TOP FL420 STNR NC",    # só degenerada
    "EMBD TS FCST N OF LINE N3800 W01000 - N4200 W00950 TOP FL300 STNR NC",    # quase paralela
    "EMBD TS FCST N OF LINE N3800 W01000 TOP FL300 STNR NC",                   # um só ponto
    "EMBD TS FCST ALONG LINE N3800 W01000 - N4000 W00700 TOP FL300 STNR NC",   # sem "D OF"
    "EMBD TS FCST N OF LINE N3800 W01000 - N3800 W00600 AND N OF N3900 TOP FL300 STNR NC",
    "EMBD TS FCST WI N3900 W00930 - N3900 W00915 - N3915 W00915 N OF LINE N3800 W01000 - "
    "N3800 W00600 TOP FL300 STNR NC",
    "EMBD TS FCST N OF LINE N3800 W01000 - N3800 W00600 AND S OF LINE N3700 W01000 - N3700 "
    "W00600 TOP FL300 STNR NC",                                                 # sem área comum
    "EMBD TS FCST N OF LINE N3800 W01000 - N3800 W00600 TOP FL300 MOV N 150KT NC",  # 600 NM
    "EMBD TS FCST N OF LINE N3800 W01000 - N3800 W00600 TOP FL300 MOV N NC",   # MOV ilegível
    "EMBD TS FCST N OF LINE N3800 W01000 - N3800 W00600 ENTIRE FIR TOP FL300 STNR NC",
])
def test_duvida_toda_a_area(eng, corpo):
    r = _r(eng, [_s(corpo)])
    assert _tudo_nogo(r), corpo


def test_linha_degenerada_com_outra_nao_restringe(eng):
    """A degenerada é ignorada, a outra conta (área maior do que a intersecção)."""
    com = _r(eng, [_s("EMBD TS FCST S OF LINE N3800 W00800 - N3800 W00800 AND N OF LINE N3900 "
                      "W01100 - N3900 W00600 TOP FL300 STNR NC")])
    so = _r(eng, [_s("EMBD TS FCST N OF LINE N3900 W01100 - N3900 W00600 TOP FL300 STNR NC")])
    assert _decisoes(eng, com) == _decisoes(eng, so)


# --- AIRMET -----------------------------------------------------------------

def test_airmet_com_linha(eng):
    a = _s("SFC VIS 0800M BR OBS N OF LINE N3800 W01000 - N4000 W00700 STNR NC",
           sid="1", tipo="AIRMET")
    r = _r(eng, [a])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") == "GO"
    txt = " ".join(m for _, m in r["avisos"])
    assert "Área do AIRMET não reconhecida" not in txt
    assert "AIRMET não interpretado" not in txt


def test_airmet_sem_margem(eng):
    a = _s("SFC VIS 0800M BR OBS N OF LINE N3900 W01100 - N3900 W00600 STNR NC",
           sid="1", tipo="AIRMET")
    r = _r(eng, [a])
    assert _dec(eng, r, 39.0 + 3 / 60, -8.0) == "NO-GO"
    assert _dec(eng, r, 39.0 - 6 / 60, -8.0) == "GO"       # sem os 10 NM do SIGMET


# --- Nunca optimista: verificação independente -----------------------------

def _lado(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


_DIRS = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
         "NE": (1, 1), "NW": (-1, 1), "SE": (1, -1), "SW": (-1, -1)}


def _fmt(lon, lat):
    la, lo = abs(lat), abs(lon)
    return (f"{'N' if lat >= 0 else 'S'}{int(la):02d}{round((la % 1) * 60) % 60:02d} "
            f"{'W' if lon < 0 else 'E'}{int(lo):03d}{round((lo % 1) * 60) % 60:02d}")


@pytest.mark.parametrize("semente", range(4))
def test_aleatorio_nenhum_ponto_do_lado_d_fica_sem_nogo(eng, semente):
    """
    Linhas de um troço (prolongadas são rectas), 1 ou 2 qualificadores: todo
    o ponto da grelha que um teste de lado independente põe na área (a mais
    de 1 NM da linha, para a resolução das coordenadas) tem de ser NO-GO; se a
    app caiu para toda a área, é NO-GO por definição.
    """
    rnd = random.Random(semente)
    grelha = [(lat / 10, lon / 10) for lat in range(370, 421, 5) for lon in range(-95, -62, 5)]
    grelha = [p for p in grelha if eng.FIR_POLYGON.contains(
        __import__("shapely.geometry", fromlist=["Point"]).Point(p[1], p[0]))]
    verificados = lidos = 0
    for _ in range(12):
        quals, rect = [], []
        for _q in range(rnd.choice((1, 2))):
            a = (rnd.randint(-120, -50) / 10, rnd.randint(355, 430) / 10)
            b = (rnd.randint(-120, -50) / 10, rnd.randint(355, 430) / 10)
            # Coordenadas ao minuto, como no texto
            a = (round(a[0] * 60) / 60, round(a[1] * 60) / 60)
            b = (round(b[0] * 60) / 60, round(b[1] * 60) / 60)
            if a == b:
                continue
            d = rnd.choice(list(_DIRS))
            quals.append(f"{d} OF LINE {_fmt(*a)} - {_fmt(*b)}")
            rect.append((a, b, _DIRS[d]))
        if not quals:
            continue
        corpo = "EMBD TS FCST " + " AND ".join(quals) + " TOP FL300 STNR NC"
        r = _r(eng, [_s(corpo)])
        lidos += not _tudo_nogo(r)
        for lat, lon in grelha:
            p = (lon, lat)
            dentro = True
            for a, b, (dx, dy) in rect:
                s_d = _lado(a, b, (a[0] + dx, a[1] + dy))
                s_p = _lado(a, b, p)
                comp = math.hypot(b[0] - a[0], b[1] - a[1])
                if s_d == 0 or s_p * s_d <= 0 or abs(s_p) / comp < 1 / 60:
                    dentro = False
                    break
            if dentro:
                verificados += 1
                assert _dec(eng, r, lat, lon) == "NO-GO", (corpo, lat, lon)
    # O teste tem de verificar alguma coisa: áreas lidas e pontos do lado D
    assert lidos >= 4 and verificados >= 20, (lidos, verificados)


# --- Contra o motor da 4.4: todo o arquivo ----------------------------------
# tests/referencia/app_4_4.py é cópia fixa do app.py do main 7e7fd12 (não
# editar). Só mudam os períodos com um boletim "OF LINE" em vigor; nesses, a
# decisão nunca fica abaixo da que a 4.4 dava sem esse boletim.

import json  # noqa: E402
import re  # noqa: E402
import types  # noqa: E402
from datetime import timedelta  # noqa: E402

import conftest  # noqa: E402
from conftest import indice_sem_linhas  # noqa: E402

REF44 = Path(__file__).resolve().parent / "referencia" / "app_4_4.py"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}


@pytest.fixture(scope="module")
def eng44():
    mod = types.ModuleType("motor_4_4")
    mod.__dict__["__file__"] = str(REF44)
    exec(compile(conftest._extract_engine(REF44.read_text(encoding="utf-8")), str(REF44),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_4_4_le_line_como_toda_a_area(eng44):
    t, corpo = eng44._corpo_boletim(T01_31)
    assert eng44._area_boletim(t, corpo, _t("2026-10-31T11:00"))[0] is None


def test_boletins_do_arquivo_area_igual_a_4_4_sem_line(eng, eng44):
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    linhas = 0
    for e in indice.get("sigmets", []):
        txt = e.get("texto", "")
        ref = eng._iso_utc(e.get("inicio")) or AGORA
        g5, _ = eng.area_sigmet(txt, ref)
        g4, _ = eng44.area_sigmet(txt, ref)
        if re.search(r"\bOF\s+LINE\b", txt):
            linhas += 1
            assert g4 is None                                  # 4.4: toda a área
            continue
        assert (g5 is None) == (g4 is None), txt
        if g5 is not None:
            assert g5.symmetric_difference(g4).area < 1e-9, txt
    assert linhas >= 2                                         # os dois T01 reais


def test_arquivo_contra_4_4(eng, eng44):
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    sem = indice_sem_linhas(indice)
    com_linha = 0
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
        tem_linha = any(re.search(r"\bOF\s+LINE\b", b) for b in sig + air)
        for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3, minutes=30),
                      fim - timedelta(minutes=15)):
            kw = dict(indice=indice, entrada=entrada, agora=agora)
            rn = eng.analisar_gamet(texto, "arquivo_hist", **kw)
            rv = eng44.analisar_gamet(texto, "arquivo_hist", **kw)
            dn = {n: _dec(eng, rn, *p) for n, p in eng.AERODROMES.items()}
            dv = {n: _dec(eng44, rv, *p) for n, p in eng.AERODROMES.items()}
            if not tem_linha:
                assert rn["por_dec"] == rv["por_dec"], f.name
                assert rn["avisos"] == rv["avisos"], f.name
                assert rn["faixa_sig"] == rv["faixa_sig"], f.name
                assert dn == dv, f.name
                continue
            com_linha += 1
            piso = eng44.analisar_gamet(texto, "arquivo_hist", indice=sem, entrada=entrada,
                                        agora=agora)
            dp = {n: _dec(eng44, piso, *p) for n, p in eng.AERODROMES.items()}
            for n in eng.AERODROMES:
                assert GRAV[dn[n]] <= GRAV[dv[n]], (f.name, n)
                assert GRAV[dn[n]] >= GRAV[dp[n]], (f.name, n)   # nunca abaixo do piso
            assert rn["faixa_sig"] == rv["faixa_sig"], f.name    # continua ACTIVO
    assert com_linha > 0
