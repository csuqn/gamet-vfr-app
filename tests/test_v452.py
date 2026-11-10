"""
4.5.2 — duas correcções optimistas latentes (pedido do Duarte a 2-nov-2026).

1) BTN degenerado. "BTN N3945 AND N3945" (os dois limites iguais, em latitude
   ou longitude, com AND ou hífen, também com cardinal solto "S BTN N3945 -
   N3945") dava uma faixa de largura zero: área vazia. Num SIGMET/AIRMET o
   boletim aparecia "fora da área do GAMET", sem aviso (também com MOV); no
   GAMET a subentrada era descartada em silêncio (GO), e com cardinal solto
   ficava "S OF N3945". Agora não é área legível, como a linha degenerada do
   "D OF LINE" (4.5): SIGMET → toda a área; AIRMET → toda a FIR + aviso "Área
   do AIRMET não reconhecida"; GAMET → toda a FIR + aviso "Área não
   reconhecida" (regra da 3.4).

2) COT em km. COASTAL_POLYGON era COASTLINE.buffer(10 / 111) em graus: em
   longitude só ~7,7 km a 40°N. Agora o buffer é em km reais (longitude
   escalada pelo cos da latitude de cada troço da costa), unido ao antigo:
   ≥ 10 km em todas as direcções e nunca menor do que até à 4.5.1.

Contra o motor fixo da 4.5.1 (tests/referencia/app_4_5_1.py, cópia de
`git show a76a93b:app.py`; não editar): nunca mais permissivo.
"""
import json
import math
import random
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import Point

import conftest
from conftest import build_gamet

REF451 = Path(__file__).resolve().parent / "referencia" / "app_4_5_1.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
AGORA = datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="011000/011400")


@pytest.fixture(scope="module")
def eng451():
    mod = types.ModuleType("motor_4_5_1")
    mod.__dict__["__file__"] = str(REF451)
    exec(compile(conftest._extract_engine(REF451.read_text(encoding="utf-8")), str(REF451),
                 "exec"), mod.__dict__)
    return mod


def _gamet(sec):
    return build_gamet("SECN I " + sec, validity="011000/011400")


def _sig(q, mov="STNR NC", tipo="SIGMET", sid="T01", fen="EMBD TS"):
    return (f"LPPC {tipo} {sid} VALID 011000/011400 LPPT- LPPC LISBOA FIR {fen} FCST {q} "
            f"TOP FL390 {mov}")


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


_GRELHA = None


def _grelha(eng):
    """Pontos de uma grelha de 0,2° dentro da área do GAMET."""
    global _GRELHA
    if _GRELHA is None:
        x0, y0, x1, y1 = eng.FIR_POLYGON.bounds
        xs, ys = np.meshgrid(np.arange(x0 + 0.05, x1, 0.2), np.arange(y0 + 0.05, y1, 0.2))
        xs, ys = xs.ravel(), ys.ravel()
        dentro = shapely.contains_xy(eng.FIR_POLYGON, xs, ys)
        _GRELHA = list(zip(ys[dentro], xs[dentro]))
    return _GRELHA


def _nunca_mais_permissivo(eng, eng451, rn, rv, caso, grelha=True):
    """Nos 52 aeródromos e na grelha: decisão nova ≥ 4.5.1. Devolve nº de mais severos."""
    pontos = list(eng.AERODROMES.values()) + (_grelha(eng) if grelha else [])
    severos = 0
    for la, lo in pontos:
        dn, dv = _dec(eng, rn, la, lo), _dec(eng451, rv, la, lo)
        assert GRAV[dn] >= GRAV[dv], (caso, la, lo, dn, dv)
        severos += GRAV[dn] > GRAV[dv]
    return severos


def _avisos(r, chave):
    return [m for _, m in r["avisos"] if chave in m]


# =============================================================================
# 1) BTN degenerado
# =============================================================================

BTN_DEGENERADOS = [
    "BTN N3945 AND N3945",
    "BTN N3945 - N3945",
    "BTN N3945-N3945",
    "S BTN N3945 - N3945",
    "N BTN N3945 AND N3945",
    "BTN W00800 AND W00800",
    "BTN W00800 - W0800",            # graus/minutos equivalentes (W008°00')
    "E BTN W00800 - W00800",
    "W BTN W00745 AND W00745",
]


@pytest.mark.parametrize("q", BTN_DEGENERADOS)
def test_btn_degenerado_sigmet_toda_a_area(eng, eng451, q):
    for mov in ("STNR NC", "MOV E 10KT NC"):
        s = _sig(q, mov)
        g, d = eng.area_sigmet(s, AGORA)
        assert g is None, (q, mov, d)
        assert d == "toda a área (área ilegível)"
        r = eng.analisar_gamet(CALMO, "ipma", boletins=[s], boletins_at=AGORA, agora=AGORA)
        assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}, (q, mov)
        assert not _avisos(r, "fora da área"), (q, mov)
        rv = eng451.analisar_gamet(CALMO, "ipma", boletins=[s], boletins_at=AGORA, agora=AGORA)
        _nunca_mais_permissivo(eng, eng451, r, rv, (q, mov))


@pytest.mark.parametrize("q", ["BTN N3945 AND N3945", "BTN N3945 AND N3945 MOV E 10KT",
                               "BTN W00800 - W00800"])
def test_btn_degenerado_sigmet_era_fora_da_area_na_451(eng451, q):
    # O erro: na 4.5.1 a área era vazia — "fora da área do GAMET", sem NO-GO.
    mov = "" if "MOV" in q else "STNR NC"
    g, _ = eng451.area_sigmet(_sig(q, mov), AGORA)
    assert g is not None and g.is_empty


@pytest.mark.parametrize("q", BTN_DEGENERADOS)
def test_btn_degenerado_airmet_toda_a_fir_com_aviso(eng, eng451, q):
    for mov in ("STNR NC", "MOV E 10KT NC"):
        a = _sig(q, mov, tipo="AIRMET", sid="1", fen="BKN CLD 002/010HFT AGL")
        la = eng.ler_airmet(a, AGORA)
        assert la["area_lida"] is False, (q, mov)
        assert not la["fora"]
        assert la["area"].startswith("toda a FIR")
        assert la["blocos"] and all(eng._clean_poly(b.polygon).equals(eng.FIR_POLYGON)
                                    or b.polygon.symmetric_difference(eng.FIR_POLYGON).area < 1e-9
                                    for b in la["blocos"])
        r = eng.analisar_gamet(CALMO, "ipma", boletins=[a], boletins_at=AGORA, agora=AGORA)
        assert _avisos(r, "Área do AIRMET não reconhecida"), (q, mov)
        assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}     # base 200 ft
        rv = eng451.analisar_gamet(CALMO, "ipma", boletins=[a], boletins_at=AGORA, agora=AGORA)
        _nunca_mais_permissivo(eng, eng451, r, rv, (q, mov))


@pytest.mark.parametrize("q", BTN_DEGENERADOS)
@pytest.mark.parametrize("modelo", [
    "SIG CLD: {q} BKN 002/010HFT AGL",
    "SIG CLD: 10/12 {q} BKN 002/010HFT AGL",
    "SFC VIS: N OF N4100 5000M BR {q} 0800M FG",
    "SFC VIS: {q} COT 0800M FG",
])
def test_btn_degenerado_gamet_toda_a_fir_com_aviso(eng, eng451, q, modelo):
    sec = modelo.format(q=q)
    g = _gamet(sec)
    sem_area = []
    blocos, *_ = eng.parse_gamet(g, sem_area)
    fen = "BASE_AGL" if "BKN" in sec else "VIS"
    val = 200 if fen == "BASE_AGL" else 800
    b = [x for x in blocos if x.phenomenon == fen and x.value == val]
    assert b, (sec, blocos)
    sup = eng.surface_polygon("COT") if " COT " in sec else eng.FIR_POLYGON
    assert b[0].polygon.symmetric_difference(sup).area < 1e-6, sec
    assert sem_area, sec
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    assert _avisos(r, "Área não reconhecida"), sec
    rv = eng451.analisar_gamet(g, "manual", agora=AGORA)
    _nunca_mais_permissivo(eng, eng451, r, rv, sec)


def test_btn_degenerado_gamet_era_silencioso_na_451(eng451):
    # O erro no GAMET: a subentrada desaparecia (GO em toda a FIR, sem aviso).
    g = _gamet("SIG CLD: BTN N3945 AND N3945 BKN 002/010HFT AGL")
    sem_area = []
    blocos, *_ = eng451.parse_gamet(g, sem_area)
    assert not blocos and not sem_area
    r = eng451.analisar_gamet(g, "manual", agora=AGORA)
    assert {x["decision"] for x in r["regioes"]} == {"GO"}


def test_btn_degenerado_secn2_toda_a_fir(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="011000/011400")
    g = g.replace("SECN II", "SECN II CLD: BTN N3945 AND N3945 BKN ST 002/010HFT AGL")
    _, nuvens = eng.nuvens_baixas_secn2(g)
    assert nuvens and nuvens[0][0] == 200
    assert nuvens[0][5] is False                         # área não lida → aviso
    assert len(nuvens[0][4]) == len(eng.AERODROMES)      # toda a FIR


BTN_VALIDOS = [
    "BTN N3945 AND N3946", "BTN N3945 - N4000", "BTN N4050-N3840", "S BTN N3720 - N3800",
    "N BTN N3720 AND N3800", "BTN W00800 AND W00801", "BTN W00745 - W00900",
    "E BTN W00800 - W00900", "W BTN W00800 AND W00745",
    "BTN N3840 AND N4100 E OF W00800",
]


@pytest.mark.parametrize("q", BTN_VALIDOS)
def test_btn_nao_degenerado_igual_451(eng, eng451, q):
    for base in (None, eng._caixa_linhas()):
        a, b = eng.extract_polygon(q, base=base), eng451.extract_polygon(q, base=base)
        assert a is not None and a.symmetric_difference(b).area < 1e-12, q
    for mov in ("STNR NC", "MOV E 10KT NC"):
        g, d = eng.area_sigmet(_sig(q, mov), AGORA)
        g1, d1 = eng451.area_sigmet(_sig(q, mov), AGORA)
        assert d == d1 and g.symmetric_difference(g1).area < 1e-12, q
    sec = f"SIG CLD: {q} BKN 002/010HFT AGL"
    b, *_ = eng.parse_gamet(_gamet(sec))
    b1, *_ = eng451.parse_gamet(_gamet(sec))
    assert len(b) == len(b1) and all(x.polygon.symmetric_difference(y.polygon).area < 1e-12
                                     for x, y in zip(b, b1))


def test_btn_degenerado_helper(eng):
    assert eng._btn_degenerado("BKN 002 BTN N3945 AND N3945")
    assert eng._btn_degenerado("S BTN N3945-N3945")
    assert eng._btn_degenerado("BTN W00800 - W0800")
    assert not eng._btn_degenerado("BTN N3945 AND N3946")
    assert not eng._btn_degenerado("BTN W00800 AND E00800")
    assert not eng._btn_degenerado("N OF N3945 AND S OF N3945")


# =============================================================================
# 2) COT em km
# =============================================================================

def _desloca_km(lat, lon, dn_km, de_km):
    # Graus por km (excesso de distância → o ponto fica de certeza a ≥ d km)
    return (lat + dn_km / 110.9, lon + de_km / (111.0 * math.cos(math.radians(lat))))


def _amostra_costa(eng):
    cs = list(eng.COASTLINE.coords)
    pts = []
    for a, b in zip(cs, cs[1:]):
        for t in (0.0, 0.25, 0.5, 0.75):
            pts.append((a[1] + (b[1] - a[1]) * t, a[0] + (b[0] - a[0]) * t))
    pts.append((cs[-1][1], cs[-1][0]))
    return pts


def test_cot_contem_o_antigo(eng, eng451):
    assert eng451.COASTAL_POLYGON.difference(eng.COASTAL_POLYGON).area < 1e-12
    assert eng.COASTAL_POLYGON.area > eng451.COASTAL_POLYGON.area * 1.1
    assert eng.COASTAL_POLYGON.difference(eng.FIR_POLYGON).area < 1e-12


@pytest.mark.parametrize("dn,de", [(0, 1), (0, -1), (1, 0), (-1, 0),
                                   (0.7071, 0.7071), (-0.7071, 0.7071),
                                   (0.7071, -0.7071), (-0.7071, -0.7071)])
def test_cot_10_km_em_todas_as_direccoes(eng, eng451, dn, de):
    cot = eng.COASTAL_POLYGON.buffer(1e-9)
    fora_451 = 0
    n = 0
    for lat, lon in _amostra_costa(eng):
        la, lo = _desloca_km(lat, lon, dn * 9.9, de * 9.9)
        p = Point(lo, la)
        if not eng.FIR_POLYGON.contains(p):
            continue
        n += 1
        assert cot.contains(p), (lat, lon, dn, de)
        fora_451 += not eng451.COASTAL_POLYGON.buffer(1e-9).contains(p)
    assert n > 30
    if de and not dn:
        # O erro da 4.5.1: em longitude a faixa tinha ~7,7 km
        assert fora_451 > 0


def test_cot_largura_medida_em_km(eng):
    # A faixa não cresceu demais: um ponto a mais de ~11 km reais da costa
    # (distância em graus > 11,4/85 → ≥ 11 km em qualquer direcção até 42°N)
    # continua fora do COT.
    cot = eng.COASTAL_POLYGON
    for lat, lon in _amostra_costa(eng)[::7]:
        la, lo = _desloca_km(lat, lon, 0, 11.5)
        p = Point(lo, la)
        if eng.FIR_POLYGON.contains(p) and eng.COASTLINE.distance(p) > 11.4 / 85:
            assert not cot.contains(p), (lat, lon)


def test_cot_aerodromos_inalterados(eng, eng451):
    novo = {n for n, (la, lo) in eng.AERODROMES.items()
            if eng.COASTAL_POLYGON.contains(Point(lo, la))}
    velho = {n for n, (la, lo) in eng451.AERODROMES.items()
             if eng451.COASTAL_POLYGON.contains(Point(lo, la))}
    assert novo == velho
    codigos = {n.split("(")[-1].rstrip(")") for n in novo}
    assert {"LP62", "LP78", "LPPR", "LPFR", "LPCS", "LPPM"} <= codigos
    assert "LPPT" not in codigos


def test_lan_mar_inalterados(eng, eng451):
    for s in ("LAN", "MAR"):
        assert eng.surface_polygon(s).symmetric_difference(eng451.surface_polygon(s)).area < 1e-12
    for s in ("COT", "COT/LAN", "COT/MAR", "COT/LAN/MAR"):
        assert eng451.surface_polygon(s).difference(eng.surface_polygon(s)).area < 1e-12


def test_cot_gamet_ponto_a_8_km_da_costa(eng, eng451):
    # A ~8,5 km a leste da costa (a 40°N): na 4.5.1 fora do COT, agora dentro.
    cs = [c for c in eng.COASTLINE.coords if 39.9 < c[1] < 40.3]
    lon0, lat0 = cs[0]
    la, lo = _desloca_km(lat0, lon0, 0, 8.5)
    p = Point(lo, la)
    assert eng.LAND_POLYGON.contains(p)
    assert not eng451.COASTAL_POLYGON.contains(p)
    assert eng.COASTAL_POLYGON.contains(p)
    g = _gamet("SFC VIS: COT 0800M FG")
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    rv = eng451.analisar_gamet(g, "manual", agora=AGORA)
    assert _dec(eng, r, la, lo) == "NO-GO"
    assert _dec(eng451, rv, la, lo) == "GO"


def test_cot_airmet_recorte_maior(eng, eng451):
    a = _sig("N OF N3930 COT", tipo="AIRMET", sid="1", fen="BKN CLD 002/010HFT AGL")
    la, la1 = eng.ler_airmet(a, AGORA), eng451.ler_airmet(a, AGORA)
    assert la["area_lida"] and la1["area_lida"]
    g, g1 = la["blocos"][0].polygon, la1["blocos"][0].polygon
    assert g1.difference(g).area < 1e-12 and g.area > g1.area


# =============================================================================
# Casos gerados (COT/LAN/MAR e BTN) contra a 4.5.1
# =============================================================================

def _gera_lat(rnd):
    return f"N{rnd.randint(37, 41):02d}{rnd.choice([0, 15, 30, 45]):02d}"


def _gera_lon(rnd):
    return f"W00{rnd.randint(7, 9)}{rnd.choice([0, 15, 30, 45]):02d}"


def _gera_area(rnd):
    k = rnd.choice(["", "", "NOF", "SOF", "EOF", "WOF", "BTNN", "BTNW", "SBTN", "BTNEQ"])
    if k == "":
        return ""
    if k in ("NOF", "SOF"):
        return f"{k[0]} OF {_gera_lat(rnd)}"
    if k in ("EOF", "WOF"):
        return f"{k[0]} OF {_gera_lon(rnd)}"
    sep = rnd.choice([" AND ", " - ", "-"])
    if k == "BTNEQ":                       # degenerado (às vezes)
        v = rnd.choice([_gera_lat, _gera_lon])(rnd)
        return f"{rnd.choice(['', 'S ', 'N '] if v[0] == 'N' else ['', 'E ', 'W '])}BTN {v}{sep}{v}"
    if k == "BTNW":
        return f"BTN {_gera_lon(rnd)}{sep}{_gera_lon(rnd)}"
    car = "S " if k == "SBTN" else ""
    return f"{car}BTN {_gera_lat(rnd)}{sep}{_gera_lat(rnd)}"


def _gera_linha(rnd):
    jan = rnd.choice(["", "", "10/12 ", "12/14 "])
    area = _gera_area(rnd)
    sup = rnd.choice(["", "", "COT ", "LAN ", "MAR ", "COT AND LAN ", "MAR AND COT ",
                      "COT/MAR ", "LAN AND MAR "])
    val = rnd.choice(["0800M FG", "2000M BR", "LCA 1000M BR", "BKN 002/010HFT AGL",
                      "BKN 004/010HFT AGL", "ISOL TS", "OCNL TS", "ISOL CB"])
    campo = ("SIG CLD" if "BKN" in val or "CB" in val else
             "SIGWX" if "TS" in val else "SFC VIS")
    return campo, f"{jan}{area + ' ' if area else ''}{sup}{val}".strip()


def _gera_gamet(rnd):
    campos = {}
    for _ in range(rnd.randint(1, 3)):
        c, l = _gera_linha(rnd)
        campos.setdefault(c, []).append(l)
    sec = " ".join(f"{c}: " + " ".join(ls) for c, ls in campos.items())
    return _gamet(sec)


def test_gerados_gamet_contra_451(eng, eng451):
    rnd = random.Random(452)
    severos = 0
    for i in range(120):
        g = _gera_gamet(rnd)
        r = eng.analisar_gamet(g, "manual", agora=AGORA)
        rv = eng451.analisar_gamet(g, "manual", agora=AGORA)
        severos += _nunca_mais_permissivo(eng, eng451, r, rv, g)
    assert severos > 0          # os casos chegam a apanhar COT/BTN degenerado


def test_gerados_boletins_contra_451(eng, eng451):
    rnd = random.Random(4520)
    for i in range(80):
        area = _gera_area(rnd) or "N OF N3800"
        sup = rnd.choice(["", "COT", "LAN", "MAR", "COT AND LAN"])
        mov = rnd.choice(["STNR NC", "MOV E 10KT NC", "MOV SW 15KT NC"])
        if rnd.random() < 0.5:
            b = _sig(f"{area} {sup}".strip(), mov)
        else:
            b = _sig(f"{area} {sup}".strip(), mov, tipo="AIRMET", sid=str(i % 9 + 1),
                     fen=rnd.choice(["BKN CLD 002/010HFT AGL", "SFC VIS 0800M FG",
                                     "ISOL TS"]))
        r = eng.analisar_gamet(CALMO, "ipma", boletins=[b], boletins_at=AGORA, agora=AGORA)
        rv = eng451.analisar_gamet(CALMO, "ipma", boletins=[b], boletins_at=AGORA, agora=AGORA)
        _nunca_mais_permissivo(eng, eng451, r, rv, b)


# =============================================================================
# Todo o arquivo contra a 4.5.1
# =============================================================================

def test_arquivo_contra_451(eng, eng451):
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    # 4.6: sem os boletins só com graus (verificados contra a 4.5.2 em test_v46.py)
    indice = conftest.indice_sem_graus(
        json.loads((DADOS / "indice.json").read_text(encoding="utf-8")))
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        if conftest.linha_48(texto):
            continue  # 4.8: "D OF LINE" no GAMET, verificado em test_v48.py
        ini = eng._iso_utc(entrada.get("inicio"))
        fim = eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3, minutes=30),
                      fim - timedelta(minutes=15)):
            kw = dict(indice=indice, entrada=entrada, agora=agora)
            rn = eng.analisar_gamet(texto, "arquivo_hist", **kw)
            rv = eng451.analisar_gamet(texto, "arquivo_hist", **kw)
            _nunca_mais_permissivo(eng, eng451, rn, rv, (f.name, agora))
            n += 1
    assert n > 0


def test_versoes(eng, eng451):
    assert eng451.APP_VERSION == "4.5.1"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 5, 2)
