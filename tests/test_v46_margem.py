"""
4.5.1 — margem de 10 NM dos SIGMET medida a partir do semiplano NÃO recortado.

Erro (revisor do PR #33, confirmado): nos SIGMET com os qualificadores do
GAMET ("S OF N3800", "W OF W01000", "BTN …"), _area_boletim → extract_polygon
recortava o semiplano à área do GAMET e só depois area_sigmet juntava os 10
NM. O fenómeno ocupa o semiplano em toda a FIR LPPC (também fora da área do
GAMET), por isso um ponto da área do GAMET a menos de 10 NM do semiplano, mas
a mais de 10 NM da parte recortada (degrau do sector inferior a N3800, costa
oeste a W01000, concavidades da fronteira), ficava fora do NO-GO — optimista.
O mesmo com o MOV: deslocava-se a área recortada.

Agora o semiplano é lido numa caixa à volta da área do GAMET, deslocado pelo
MOV, e a margem é medida a partir dele; o resultado é sempre unido à leitura
da 4.5 (nunca menos área).
"""
import json
import math
import random
import re
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import Point

import conftest
from conftest import build_gamet

REF45 = Path(__file__).resolve().parent / "referencia" / "app_4_5.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}

AGORA = datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="011000/011400")


def _sig(q, mov="STNR NC", tipo="SIGMET", sid="T01", fen="EMBD TS"):
    return (f"LPPC {tipo} {sid} VALID 011000/011400 LPPT- LPPC LISBOA FIR {fen} FCST {q} "
            f"TOP FL390 {mov}")


@pytest.fixture(scope="module")
def eng45():
    mod = types.ModuleType("motor_4_5")
    mod.__dict__["__file__"] = str(REF45)
    exec(compile(conftest._extract_engine(REF45.read_text(encoding="utf-8")), str(REF45),
                 "exec"), mod.__dict__)
    return mod


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


def _contem(maior, menor):
    return menor.difference(maior).area < 1e-9


# --- Os exemplos do revisor --------------------------------------------------

@pytest.mark.parametrize("q,lat,lon", [
    ("S OF N3800", 38.0067, -9.9833),     # degrau do sector inferior a N3800, 0,4 NM
    ("W OF W01000", 37.2567, -9.8333),    # ~8 NM a leste de W01000
])
def test_exemplos_do_revisor(eng, eng45, q, lat, lon):
    s = _sig(q)
    p = Point(lon, lat)
    assert eng.FIR_POLYGON.contains(p)
    g45, _ = eng45.area_sigmet(s, AGORA)
    assert not g45.contains(p)                       # o erro da 4.5
    g, d = eng.area_sigmet(s, AGORA)
    assert g.contains(p), d
    assert d == "área + 10 NM"
    r = eng.analisar_gamet(CALMO, "ipma", boletins=[s], boletins_at=AGORA, agora=AGORA)
    assert _dec(eng, r, lat, lon) == "NO-GO"
    r45 = eng45.analisar_gamet(CALMO, "ipma", boletins=[s], boletins_at=AGORA, agora=AGORA)
    assert _dec(eng45, r45, lat, lon) == "GO"


# --- Distância "à mão" ao semiplano não recortado ----------------------------
# Cada qualificador é um intervalo em latitude ou longitude (graus). A
# distância de um ponto à intersecção dos intervalos, em NM, é estimada por
# excesso (cos da latitude do próprio ponto ou do ponto mais próximo, o
# maior), para só se verificarem pontos que estão de certeza a <= 10 NM.

_GRELHA = None


def _grelha(eng):
    global _GRELHA
    if _GRELHA is None:
        x0, y0, x1, y1 = eng.FIR_POLYGON.bounds
        xs, ys = np.meshgrid(np.arange(x0, x1, 0.03), np.arange(y0, y1, 0.03))
        xs, ys = xs.ravel(), ys.ravel()
        dentro = shapely.contains_xy(eng.FIR_POLYGON, xs, ys)
        _GRELHA = (xs[dentro], ys[dentro])
    return _GRELHA


def _lat(v):
    return int(v[1:3]) + int(v[3:5]) / 60


def _lon(v):
    s = -1 if v[0] == "W" else 1
    return s * (int(v[1:4]) + int(v[4:6]) / 60)


def _gera_lat(rnd):
    return f"N{rnd.randint(36, 42):02d}{rnd.choice([0, 10, 15, 20, 30, 40, 45, 50]):02d}"


def _gera_lon(rnd):
    return f"W{rnd.randint(6, 10):03d}{rnd.choice([0, 10, 15, 20, 30, 40, 45, 50]):02d}"


def _gera_qual(rnd):
    """(texto, intervalo de latitude, intervalo de longitude)."""
    inf = math.inf
    k = rnd.choice(["N", "S", "E", "W", "BTNN", "BTNW", "SBTN", "NBTN", "EBTN", "WBTN"])
    if k in ("N", "S"):
        v = _gera_lat(rnd)
        iv = (_lat(v), inf) if k == "N" else (-inf, _lat(v))
        return f"{k} OF {v}", iv, (-inf, inf)
    if k in ("E", "W"):
        v = _gera_lon(rnd)
        iv = (_lon(v), inf) if k == "E" else (-inf, _lon(v))
        return f"{k} OF {v}", (-inf, inf), iv
    sep = rnd.choice([" AND ", " - ", "-"])
    if k in ("BTNN", "SBTN", "NBTN"):
        a, b = _gera_lat(rnd), _gera_lat(rnd)
        while a == b:                       # faixa degenerada: fora deste teste
            b = _gera_lat(rnd)
        lo, hi = sorted((_lat(a), _lat(b)))
        car = {"BTNN": "", "SBTN": "S ", "NBTN": "N "}[k]
        if car == "S ":
            lo = -inf
        elif car == "N ":
            hi = inf
        return f"{car}BTN {a}{sep}{b}", (lo, hi), (-inf, inf)
    a, b = _gera_lon(rnd), _gera_lon(rnd)
    while a == b:
        b = _gera_lon(rnd)
    lo, hi = sorted((_lon(a), _lon(b)))
    car = {"BTNW": "", "EBTN": "E ", "WBTN": "W "}[k]
    if car == "E ":
        hi = inf
    elif car == "W ":
        lo = -inf
    return f"{car}BTN {a}{sep}{b}", (-inf, inf), (lo, hi)


def _gera_caso(rnd, com_mov):
    n = 1 if com_mov else rnd.choice([1, 1, 2, 2, 3])
    textos, lat_iv, lon_iv = [], (-math.inf, math.inf), (-math.inf, math.inf)
    for _ in range(n):
        t, la, lo = _gera_qual(rnd)
        textos.append(t)
        lat_iv = (max(lat_iv[0], la[0]), min(lat_iv[1], la[1]))
        lon_iv = (max(lon_iv[0], lo[0]), min(lon_iv[1], lo[1]))
    q = rnd.choice([" AND ", " "]).join(textos)
    mov, dn, de = "STNR NC", 0.0, 0.0
    if com_mov:
        rumo = rnd.choice(["N", "S", "E", "W", "NE", "SW", "NW", "SE", "ENE", "SSW"])
        kt = rnd.randint(5, 30)
        mov = f"MOV {rumo} {kt}KT NC"
        ang = math.radians(_RUMOS[rumo])
        dist = kt * 4                                   # VALID 011000/011400
        dn, de = dist * math.cos(ang), dist * math.sin(ang)
    return q, mov, lat_iv, lon_iv, dn, de


_RUMOS = {"N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90, "ESE": 112.5, "SE": 135,
          "SSE": 157.5, "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5, "W": 270,
          "WNW": 292.5, "NW": 315, "NNW": 337.5}


def _verifica_margem(eng, g, lat_iv, lon_iv, dn, de, caso):
    """Todo o ponto da grelha a <= 9,8 NM da área varrida está em g."""
    xs, ys = _grelha(eng)
    (a, b), (c, d) = lat_iv, lon_iv
    # Área varrida pelo MOV (um só qualificador: só conta a componente normal)
    a2, b2 = a + min(0, dn) / 60, b + max(0, dn) / 60
    cosl = np.cos(np.radians(ys))
    c2 = c + np.minimum(0, de) / (60 * cosl)
    d2 = d + np.maximum(0, de) / (60 * cosl)
    dlat = np.maximum(0, np.maximum(a2 - ys, ys - b2))
    lat_n = np.clip(ys, a2, b2)
    cosm = np.cos(np.radians(np.minimum(np.abs(ys), np.abs(lat_n))))
    dlon = np.maximum(0, np.maximum(c2 - xs, xs - d2))
    dist = np.hypot(dlat * 60, dlon * 60 * cosm)
    perto = dist <= 9.8
    if not perto.any():
        return 0
    ok = shapely.contains_xy(g, xs[perto], ys[perto])
    falta = [(round(y, 4), round(x, 4)) for x, y in zip(xs[perto][~ok], ys[perto][~ok])]
    assert not falta, (caso, falta[:5])
    return int(perto.sum())


@pytest.mark.parametrize("com_mov", [False, True])
def test_margem_contra_semiplano_e_contem_45(eng, eng45, com_mov):
    rnd = random.Random(4651 + com_mov)
    verificados = novos = 0
    for _ in range(150):
        q, mov, lat_iv, lon_iv, dn, de = _gera_caso(rnd, com_mov)
        s = _sig(q, mov)
        g, d = eng.area_sigmet(s, AGORA)
        g45, _ = eng45.area_sigmet(s, AGORA)
        if g45 is None:
            assert g is None, s
            continue
        if g is None:
            continue                                   # toda a área: mais severo
        assert _contem(g, g45), s
        if g.difference(g45).area > 1e-6:
            novos += 1
        if lat_iv[0] <= lat_iv[1] and lon_iv[0] <= lon_iv[1]:
            verificados += _verifica_margem(eng, g, lat_iv, lon_iv, dn, de, s)
        # AIRMET: sem margem; sem MOV, igual à 4.5 dentro da FIR
        a = _sig(q, mov, tipo="AIRMET", sid="3", fen="BKN CLD 002/010HFT AGL")
        la, la45 = eng.ler_airmet(a, AGORA), eng45.ler_airmet(a, AGORA)
        ga = eng.unary_union([b.polygon for b in la["blocos"]]) if la["blocos"] else None
        ga45 = eng.unary_union([b.polygon for b in la45["blocos"]]) if la45["blocos"] else None
        if ga45 is not None:
            assert ga is not None and _contem(ga, ga45), a
            if not com_mov:
                assert ga.symmetric_difference(ga45).area < 1e-9, a
    assert verificados > 1000
    assert novos > 10


def test_mov_parte_do_semiplano_nao_recortado(eng, eng45):
    # S OF N3700 a mover para N 20 KT durante 4 h: 80 NM → até N3820 + 10 NM.
    s = _sig("S OF N3700", "MOV N 20KT NC")
    g, _ = eng.area_sigmet(s, AGORA)
    g45, _ = eng45.area_sigmet(s, AGORA)
    assert _contem(g, g45)
    n = _verifica_margem(eng, g, (-math.inf, 37.0), (-math.inf, math.inf), 80, 0, s)
    assert n > 100


def test_deslocacao_grande_toda_a_area(eng):
    # Semiplano lido numa caixa de 10°: deslocação que não cabe → toda a área.
    g, d = eng.area_sigmet(_sig("S OF N3000", "MOV N 99KT NC"), AGORA)
    assert g is None and "deslocação" in d


def test_wi_e_line_inalterados(eng, eng45):
    for q in ["WI N3800 W00900 - N3900 W00900 - N3900 W00800 - N3800 W00800 - N3800 W00900",
              "WI 30NM OF N3830 W00900",
              "W OF LINE N4300 W01000 - N3600 W01000",
              "SW OF LINE N3508 W01641 - N35 W01628 AND W OF LINE N35 W01628 - N3149 W01734"]:
        for mov in ("STNR NC", "MOV E 15KT NC"):
            s = _sig(q, mov)
            g, _ = eng.area_sigmet(s, AGORA)
            g45, _ = eng45.area_sigmet(s, AGORA)
            assert (g is None) == (g45 is None), s
            if g is not None:
                assert g.symmetric_difference(g45).area < 1e-9, s


def test_superficie_no_sigmet_nao_recorta(eng):
    # A 4.5 não recorta o SIGMET por COT/LAN/MAR (fica a área toda + margem):
    # continua assim, e a margem parte do semiplano.
    g, _ = eng.area_sigmet(_sig("S OF N3800 MAR"), AGORA)
    assert g.contains(Point(-9.9833, 38.0067))
    assert g.contains(Point(-8.0, 37.5))                       # terra a sul de N3800


def test_extract_polygon_do_gamet_inalterado(eng, eng45):
    rnd = random.Random(46)
    for _ in range(300):
        q, *_ = _gera_caso(rnd, False)
        a, b = eng.extract_polygon(q), eng45.extract_polygon(q)
        assert (a is None) == (b is None), q
        if a is not None:
            assert a.symmetric_difference(b).area < 1e-12, q


# --- Contra o motor da 4.5: todo o arquivo -----------------------------------
# tests/referencia/app_4_5.py é cópia fixa do app.py do main f40e20f (não
# editar).

def test_boletins_do_arquivo_contem_4_5(eng, eng45):
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    n = 0
    for e in indice.get("sigmets", []):
        txt = e.get("texto", "")
        ref = eng._iso_utc(e.get("inicio")) or AGORA
        if conftest.GRAUS_RE.search(txt):          # 4.6: só com graus, em test_v46.py
            continue
        if re.match(r"\s*LPPC\s+AIRMET", txt):
            la, la45 = eng.ler_airmet(txt, ref), eng45.ler_airmet(txt, ref)
            for b45 in la45["blocos"]:
                assert any(b.phenomenon == b45.phenomenon and _contem(b.polygon, b45.polygon)
                           for b in la["blocos"]), txt
            continue
        g, _ = eng.area_sigmet(txt, ref)
        g45, _ = eng45.area_sigmet(txt, ref)
        if g45 is None:
            assert g is None, txt
        elif g is not None:
            assert _contem(g, g45), txt
        n += 1
    assert n > 0


def test_arquivo_contra_4_5(eng, eng45):
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
        ini = eng._iso_utc(entrada.get("inicio"))
        fim = eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        for agora in (ini + timedelta(minutes=30), ini + timedelta(hours=3, minutes=30),
                      fim - timedelta(minutes=15)):
            kw = dict(indice=indice, entrada=entrada, agora=agora)
            rn = eng.analisar_gamet(texto, "arquivo_hist", **kw)
            rv = eng45.analisar_gamet(texto, "arquivo_hist", **kw)
            for nome, p in eng.AERODROMES.items():
                assert GRAV[_dec(eng, rn, *p)] >= GRAV[_dec(eng45, rv, *p)], (f.name, nome)
            n += 1
    assert n > 0


def test_versoes(eng, eng45):
    assert eng45.APP_VERSION == "4.5"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 5, 1)
