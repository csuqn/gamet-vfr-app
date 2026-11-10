"""
4.7.4 — as NOTAS de alcance de uma região fundida só afirmam o que vale em
toda ela (seguimento da 4.7.3, que tratou os motivos).

GAMET real 061500/062100 (dados/gamets/2026/11/20261106T1442Z_061500-062100_
9541f75dd8.txt), SIG CLD "N OF N3800 LCA BKN 004-008/010HFT AGL BTN N4030 -
N3800 MAR AND COT ISOL TCU/CB …". A fatia costeira de 1,2% com o CB é absorvida
por `_merge_slivers` na região MARGINAL do interior norte (LPBG, LPCH, LPPR…) e
`_absorb_values` unia as notas: a linha "Alcance" dessa região dizia "BASE:
apenas sobre a costa e o mar (área já recortada); CB: apenas sobre a costa e o
mar" — como se a base de 400 ft não contasse no interior (leitura optimista).

Desde a 4.7.4 a fusão fica igual (regiões, polígonos, decisões, valores,
motivos) e uma nota que só vale numa das partes passa a "parte da zona: <nota>"
(`_notas_fundidas`, mesma regra de `_motivos_fundidos`). Nenhuma nota desaparece.
"""
import json
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import conftest
from test_v473 import G061500, INTERIOR_NORTE, _icao

REF473 = Path(__file__).resolve().parent / "referencia" / "app_4_7_3.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
PARCIAL = "parte da zona: "
NOTA_BASE = "BASE: apenas sobre a costa e o mar (área já recortada)"
NOTA_CB = "CB: apenas sobre a costa e o mar (área já recortada)"


@pytest.fixture(scope="module")
def eng473(eng):
    mod = types.ModuleType("motor_4_7_3")
    mod.__dict__["__file__"] = str(REF473)
    exec(compile(conftest._extract_engine(REF473.read_text(encoding="utf-8")), str(REF473),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_7_3(eng, eng473):
    assert eng473.APP_VERSION == "4.7.3"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 7, 4)


def _pontos(eng, texto):
    blocos, *_ = eng.parse_gamet(texto)
    regioes = eng.compute_dynamic_regions(blocos)
    return regioes, {_icao(n): eng.find_region_for_point(regioes, la, lo)
                     for n, (la, lo) in eng.AERODROMES.items()}


# ---------------------------------------------------------------- GAMET real

def test_gamet_real_061500_interior_norte_sem_nota_costeira_plena(eng):
    _, pontos = _pontos(eng, G061500)
    for icao in INTERIOR_NORTE:
        notas = pontos[icao]["notas"]
        assert NOTA_BASE not in notas and NOTA_CB not in notas, (icao, notas)
        # Nenhuma nota desaparece: ficam como "parte da zona"
        assert PARCIAL + NOTA_BASE in notas and PARCIAL + NOTA_CB in notas, (icao, notas)
    # A região de Cascais/Tojeira é toda costa/mar com o CB: notas plenas
    for icao in ("LPCS",):
        assert NOTA_BASE in pontos[icao]["notas"] and NOTA_CB in pontos[icao]["notas"]
        assert not any(n.startswith(PARCIAL) for n in pontos[icao]["notas"])
    # Decisões iguais às da 4.7.3: MARGINAL a N de N3800, GO a sul
    for nome, (la, lo) in eng.AERODROMES.items():
        assert pontos[_icao(nome)]["decision"] == ("MARGINAL" if la > 38.0 else "GO"), nome


def test_gamet_real_061500_na_4_7_3_a_nota_era_plena(eng473):
    """O erro que a 4.7.4 corrige (o teste acima falha com este motor)."""
    _, pontos = _pontos(eng473, G061500)
    assert NOTA_BASE in pontos["LPBG"]["notas"] and NOTA_CB in pontos["LPBG"]["notas"]


def test_gamet_real_061500_igual_a_4_7_3_excepto_prefixo(eng, eng473):
    _comparar(eng, eng473, G061500, "061500")


def test_ui_e_pdf_com_notas_parciais(eng):
    r = eng.analisar_gamet(G061500, "manual")
    reg = eng.find_region_for_point(r["regioes"], 41.8, -6.73)    # perto de Bragança
    notas = eng.annotate_window_notes(reg["notas"], r["ini"])
    assert PARCIAL + NOTA_BASE in notas
    html = eng.html_regiao(reg, 38.8, notas)
    assert "Alcance restrito" in html and "parte da zona: BASE: apenas sobre a costa" in html
    pdf = eng.generate_pdf(r["regioes"], G061500, r["fz"], r["qnh"], "")
    assert pdf[:4] == b"%PDF"


def test_annotate_window_notes_com_prefixo(eng):
    ini = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
    agora = datetime(2026, 11, 6, 12, 30, tzinfo=timezone.utc)
    n = eng.annotate_window_notes([PARCIAL + "VIS: apenas 09–11Z"], ini, agora)
    assert n == [PARCIAL + "VIS: apenas 09–11Z — já terminou"]


# ---------------------------------------------------------------- _notas_fundidas

def _reg(notas, reasons=()):
    return dict(vis=None, base=None, ts=[], turb=[], turb_layers=[], ice=[],
                ice_layers=[], mt_obsc=[], va=[], reasons=list(reasons), notas=list(notas))


def test_absorb_nota_comum_fica_plena(eng):
    a = _reg([NOTA_BASE, "ICE: apenas sobre terra (área já recortada)"])
    b = _reg([NOTA_BASE])
    eng._absorb_values(a, b)
    assert a["notas"] == [NOTA_BASE, PARCIAL + "ICE: apenas sobre terra (área já recortada)"]


def test_absorb_nota_so_de_uma_parte_fica_parcial_nos_dois_sentidos(eng):
    a = _reg(["ICE: apenas sobre terra (área já recortada)"])
    b = _reg([NOTA_BASE, NOTA_CB, "ICE: apenas sobre terra (área já recortada)"])
    eng._absorb_values(a, b)
    assert a["notas"] == ["ICE: apenas sobre terra (área já recortada)",
                          PARCIAL + NOTA_BASE, PARCIAL + NOTA_CB]
    a = _reg([NOTA_BASE])
    b = _reg([])
    eng._absorb_values(a, b)
    assert a["notas"] == [PARCIAL + NOTA_BASE]


def test_absorb_nota_parcial_continua_parcial_sem_duplicar(eng):
    a = _reg([PARCIAL + NOTA_BASE])
    b = _reg([NOTA_BASE])
    eng._absorb_values(a, b)
    assert a["notas"] == [PARCIAL + NOTA_BASE]
    assert eng._notas_fundidas([], []) == []
    assert eng._notas_fundidas(["X: apenas 09–11Z"], ["X: apenas 09–11Z"]) == ["X: apenas 09–11Z"]


# ---------------------------------------------------------------- contra a 4.7.3
# tests/referencia/app_4_7_3.py é cópia fixa do app.py do main 65374dd
# (`git show 65374dd:app.py`; não editar).

GRELHA = [(la / 10, lo / 10) for la in range(368, 422, 3) for lo in range(-96, -61, 3)]


def _comparar(eng, eng473, texto, nome, fonte="manual", **kw):
    rn = eng.analisar_gamet(texto, fonte, **kw)
    rv = eng473.analisar_gamet(texto, fonte, **kw)
    _comparar_regioes(eng, eng473, rn["regioes"], rv["regioes"], nome)
    for campo in ("por_dec", "avisos", "faixa_sig"):
        assert rn.get(campo) == rv.get(campo), (nome, campo)
    rr_n, rr_v = rn.get("resto"), rv.get("resto")
    assert (rr_n is None) == (rr_v is None), nome
    if rr_n:
        assert rr_n["decisao"] == rr_v["decisao"], nome
        assert rr_n.get("janela") == rr_v.get("janela"), nome
        _comparar_regioes(eng, eng473, rr_n["regioes"], rr_v["regioes"], nome + " resto")
    return rn


def _comparar_regioes(eng, eng473, regs_n, regs_v, nome):
    assert len(regs_n) == len(regs_v), nome
    for a, b in zip(regs_n, regs_v):
        assert set(a) == set(b), nome
        assert a["polygon"].symmetric_difference(b["polygon"]).area < 1e-12, nome
        for k in b:
            if k == "polygon":
                continue
            if k == "notas":
                # Nenhuma nota desaparece nem aparece: só passa a "parte da zona"
                assert conftest.notas_sem_parcial_474(a[k]) == sorted(b[k]), (nome, a[k], b[k])
                continue
            assert a[k] == b[k], (nome, k)
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        rn = eng.find_region_for_point(regs_n, la, lo)
        rv = eng473.find_region_for_point(regs_v, la, lo)
        assert (rn is None) == (rv is None), (nome, la, lo)
        if rn is not None:
            assert rn["decision"] == rv["decision"], (nome, la, lo)


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


def test_arquivo_manual_contra_4_7_3(eng, eng473):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        if conftest.superficie_476(eng, f.read_text(encoding="utf-8")):
            continue  # 4.7.6: verificado em test_v476.py
        if conftest.linha_48(f.read_text(encoding="utf-8")):
            continue  # 4.8: "D OF LINE" no GAMET, verificado em test_v48.py
        ini = eng._iso_utc(entrada.get("inicio"))
        kw = {"agora": ini + timedelta(hours=3, minutes=30)} if ini else {}
        _comparar(eng, eng473, conftest.sfc_wind_475(f.read_text(encoding="utf-8")),  # 4.7.5
                  f.name, **kw)
        n += 1
    assert n > 50


def test_arquivo_hist_contra_4_7_3(eng, eng473):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        ini, fim = eng._iso_utc(entrada.get("inicio")), eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        if conftest.superficie_476(eng, f.read_text(encoding="utf-8")):
            continue  # 4.7.6: verificado em test_v476.py
        if conftest.linha_48(f.read_text(encoding="utf-8")):
            continue  # 4.8: "D OF LINE" no GAMET, verificado em test_v48.py
        for agora in (ini + timedelta(minutes=30), fim - timedelta(minutes=15)):
            _comparar(eng, eng473, conftest.sfc_wind_475(f.read_text(encoding="utf-8")),  # 4.7.5
                      f.name, "arquivo_hist",
                      indice=indice, entrada=entrada, agora=agora)
            n += 1
    assert n > 100


# ---------------------------------------------------------------- oráculo
# Cada nota PLENA de alcance (superfície/janela) de uma região tem de valer em
# cada ponto dela: calculada directamente sobre os blocos que contêm o ponto,
# como em compute_dynamic_regions. As notas "(informativo…)" de AIRMETs ficam
# de fora (dependem dos motivos).

def _notas_ponto(eng, blocos, lon, lat):
    p = eng.Point(lon, lat)
    notas = set()
    for b in blocos:
        if b.polygon is None or b.polygon.is_empty:
            continue
        if not b.polygon.buffer(0.01).contains(p):
            continue
        if not b.polygon.buffer(-0.01).contains(p):
            return None          # em cima de uma fronteira — não julgar
        rotulo = eng._PHENOM_LABEL.get(b.phenomenon, b.phenomenon)
        if getattr(b, "origem", ""):
            rotulo = f"{b.origem} {rotulo}"
        if getattr(b, "surface", ""):
            notas.add(f"{rotulo}: apenas sobre {eng._SURFACE_LABEL.get(b.surface, b.surface)} "
                      f"(área já recortada)")
        if getattr(b, "window", ""):
            notas.add(f"{rotulo}: apenas {b.window}")
    return notas


def _verificar_oraculo(eng, texto, nome):
    blocos, *_ = eng.parse_gamet(texto)
    regioes = eng.compute_dynamic_regions(blocos)
    n = 0
    for la, lo in list(eng.AERODROMES.values()) + GRELHA:
        if not eng.FIR_POLYGON.buffer(-0.02).contains(eng.Point(lo, la)):
            continue
        esperado = _notas_ponto(eng, blocos, lo, la)
        reg = eng.find_region_for_point(regioes, la, lo)
        if esperado is None or reg is None:
            continue
        for nota in reg["notas"]:
            if nota.startswith(PARCIAL) or "(informativo" in nota:
                continue
            assert nota in esperado, (nome, la, lo, nota)
        n += 1
    return n


def test_notas_plenas_valem_em_cada_ponto_gamet_real(eng):
    assert _verificar_oraculo(eng, G061500, "061500") > 50


def test_notas_plenas_valem_em_cada_ponto_arquivo(eng):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if f.exists():
            n += _verificar_oraculo(eng, f.read_text(encoding="utf-8"), f.name)
    assert n > 1000
