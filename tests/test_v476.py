"""
4.7.6 — Uma superfície (MAR/LAN/COT) a meio da linha, depois de conteúdo do
campo e seguida de mais conteúdo, abre uma parte nova da subentrada.

GAMET real 081500/082100 de 8-nov-2026
(dados/gamets/2026/11/20261108T1451Z_081500-082100_73bc1f4fc4.txt):

    SIG CLD:LCA BKN 006-008/012HFT AGL MAR AND COT ISOL/EMBD TCU/CB
            020-035/XXXHFT AGL

Até à 4.7.5 o motor só abria subentrada a meio da linha com uma janela
`HH/HH` (4.1/4.3); a superfície `MAR AND COT` recortava a linha inteira, e o
`LCA BKN 006` ficava só no mar e na costa (0,45 da FIR). Neste GAMET não muda
nenhuma decisão (600 ft ≥ 500), mas com uma base < 500 ft o interior ficava GO
(leitura optimista). Desde a 4.7.6 o que vem antes da superfície fica com a
área da subentrada (aqui toda a FIR) e o que vem depois com a superfície. Cada
parte é unida com a área que a 4.7.5 lhe dava e um bloco da 4.7.5 sem bloco
novo tão severo que o contenha entra tal como a 4.7.5 o lia — nunca mais
permissivo. Verificado contra o motor da 4.7.5
(`tests/referencia/app_4_7_5.py`, cópia fixa do app.py do main 607150c; não
editar), no arquivo e em linhas geradas. Semente: GAMET_SEMENTE (por omissão
476); GAMET_CASOS (por omissão 300).
"""
import json
import os
import random
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from shapely.geometry import Point

import conftest
from conftest import build_gamet
from test_v475 import G081500

REF475 = Path(__file__).resolve().parent / "referencia" / "app_4_7_5.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2, None: -1}
VAL = "081500/082100"
LINHA_REAL = ("SIG CLD:LCA BKN 006-008/012HFT AGL MAR AND COT ISOL/EMBD TCU/CB "
              "020-035/XXXHFT AGL")
# Grelha de 0,3° sobre a FIR (além dos 52 aeródromos)
GRELHA = [(36.95 + 0.3 * i, -9.55 + 0.3 * j) for i in range(18) for j in range(12)]


@pytest.fixture(scope="module")
def eng475(eng):
    mod = types.ModuleType("motor_4_7_5")
    mod.__dict__["__file__"] = str(REF475)
    exec(compile(conftest._extract_engine(REF475.read_text(encoding="utf-8")), str(REF475),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_7_5(eng, eng475):
    assert eng475.APP_VERSION == "4.7.5"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 7, 6)


def _g(corpo):
    return build_gamet(f"SECN I {corpo}", validity=VAL)


def _t(h, m=0):
    return datetime(2026, 11, 8, h, m, tzinfo=timezone.utc)


def _icao(nome):
    return nome.split("(")[-1].rstrip(")")


def _so(blocos, fen, val):
    r = [b for b in blocos if b.phenomenon == fen and b.value == val]
    assert len(r) == 1, (fen, val, [(b.phenomenon, b.value) for b in blocos])
    return r[0]


def _pontos(eng, grelha=False):
    p = list(eng.AERODROMES.items())
    if grelha:
        p += [(f"grelha {la:.2f} {lo:.2f}", (la, lo)) for la, lo in GRELHA
              if eng.FIR_POLYGON.contains(Point(lo, la))]
    return p


def _decisoes(e, texto, pontos):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    return {k: (e.find_region_for_point(regioes, la, lo) or {}).get("decision")
            for k, (la, lo) in pontos}


def _mar_cot(eng):
    return eng.SURFACE_POLYGONS["MAR"].union(eng.SURFACE_POLYGONS["COT"])


# ---------------------------------------------------------------- GAMET real

def test_gamet_real_081500_base_em_toda_a_fir_e_cb_no_mar_e_costa(eng):
    blocos, *_ = eng.parse_gamet(G081500)
    base = _so(blocos, "BASE_AGL", 600)
    assert base.qualifier == "LCA" and base.surface == ""
    assert base.polygon.buffer(1e-6).contains(eng.FIR_POLYGON)
    cb = _so(blocos, "CB", "ISOL_EMBD")
    assert cb.surface == "COT/MAR"
    assert _mar_cot(eng).buffer(1e-6).contains(cb.polygon)
    assert not cb.polygon.contains(Point(-6.7, 41.8))         # interior (Bragança)
    # A base do CB (2000 ft) fica com o CB
    b20 = _so(blocos, "BASE_AGL", 2000)
    assert b20.surface == "COT/MAR"
    assert not eng.campos_nao_interpretados(G081500)


def test_gamet_real_081500_na_4_7_5_a_base_ficava_so_no_mar_e_costa(eng475):
    """O erro que a 4.7.6 corrige (o teste acima falha com este motor)."""
    blocos, *_ = eng475.parse_gamet(G081500)
    base = _so(blocos, "BASE_AGL", 600)
    assert base.surface == "COT/MAR"
    assert base.polygon.area < 0.5 * eng475.FIR_POLYGON.area


def test_gamet_real_081500_decisoes_iguais_a_4_7_5(eng, eng475):
    for fonte_kw in ({}, {"agora": _t(15, 30)}, {"agora": _t(19, 30)}):
        rn = eng.analisar_gamet(G081500, "manual", **fonte_kw)
        rv = eng475.analisar_gamet(G081500, "manual", **fonte_kw)
        assert rn["por_dec"] == rv["por_dec"]
        assert rn["avisos"] == rv["avisos"]
        for nome, (la, lo) in eng.AERODROMES.items():
            a = eng.find_region_for_point(rn["regioes"], la, lo)
            b = eng475.find_region_for_point(rv["regioes"], la, lo)
            assert a["decision"] == b["decision"], nome


def test_gamet_real_081500_base_no_interior_sem_nota_de_mar(eng):
    blocos, *_ = eng.parse_gamet(_g(LINHA_REAL))
    regioes = eng.compute_dynamic_regions(blocos)
    reg = eng.find_region_for_point(regioes, 41.8, -6.73)        # perto de Bragança
    assert reg["base"] == 600                                      # 4.7.5: sem base
    assert not any(n.startswith("BASE: apenas sobre") for n in reg["notas"]), reg["notas"]
    assert not any("CB" in n for n in reg["reasons"]), reg["reasons"]


# ---------------------------------------------------------------- variante < 500 ft

LINHA_002 = LINHA_REAL.replace("006-008", "002-008")


def test_variante_bkn_002_interior_nogo(eng, eng475):
    t = _g(LINHA_002)
    mc = _mar_cot(eng)
    novo = _decisoes(eng, t, _pontos(eng))
    antigo = _decisoes(eng475, t, _pontos(eng475))
    interior = [n for n, (la, lo) in eng.AERODROMES.items()
                if not mc.buffer(0.02).contains(Point(lo, la))]
    assert len(interior) > 15
    for nome in interior:
        assert novo[nome] == "NO-GO", nome
        assert antigo[nome] == "GO", nome            # a 4.7.5: optimista
    for nome in eng.AERODROMES:
        assert GRAV[novo[nome]] >= GRAV[antigo[nome]], nome
    for icao in ("LPBG", "LPEV", "LPVR", "LPCH"):
        nome = next(n for n in eng.AERODROMES if _icao(n) == icao)
        assert novo[nome] == "NO-GO"


def test_variante_vis_lca_antes_da_superficie(eng):
    blocos, *_ = eng.parse_gamet(_g("SFC VIS:LCA 1200M BR MAR 0800M FG"))
    v12 = _so(blocos, "VIS", 1200)
    assert v12.surface == "" and v12.qualifier == "LCA"
    assert v12.polygon.buffer(1e-6).contains(eng.FIR_POLYGON)
    v8 = _so(blocos, "VIS", 800)
    assert v8.surface == "MAR" and v8.qualifier == ""


def test_variante_com_area_da_subentrada(eng):
    """O que vem antes fica com a área da subentrada (não toda a FIR)."""
    blocos, *_ = eng.parse_gamet(_g("SIG CLD:N OF N4000 BKN 002/008HFT AGL LAN OCNL CB "
                                    "030/XXXHFT AGL"))
    b2 = _so(blocos, "BASE_AGL", 200)
    assert b2.surface == ""
    assert b2.polygon.contains(Point(-8.68, 41.24))            # Porto (costa)
    assert not b2.polygon.contains(Point(-8.0, 39.0))          # a sul de N4000
    cb = _so(blocos, "CB", "OCNL")
    assert cb.surface == "LAN"
    assert not cb.polygon.contains(Point(-9.5, 41.0))          # mar


# ---------------------------------------------------------------- casos iguais à 4.7.5

IGUAIS = [
    "SIG CLD:MAR AND COT BKN 002/008HFT AGL",                  # superfície no início
    "SIG CLD:LCA MAR BKN 002/008HFT AGL ISOL TCU/CB 020/XXXHFT AGL",
    "SIG CLD:BKN 002/008HFT AGL MAR",                          # no fim
    "SIG CLD:BKN 002/008HFT AGL MAR AND COT",
    "SIG CLD:N OF N4000 MAR BKN 002/008HFT AGL",               # depois da área
    "SIG CLD:09/11 COT BKN 002/008HFT AGL",                    # depois da janela
    "SIG CLD:BKN 002/008HFT AGL 11/15 MAR ISOL TCU/CB 020/XXXHFT AGL",  # janela (4.3)
    "SIG CLD:BKN 002/008HFT AGL MAR 11/15 ISOL TCU/CB 020/XXXHFT AGL",
    "SIG CLD:BKN 002/008HFT AGL MAR N OF N4000 BKN 004/008HFT AGL",
    "SFC VIS:LAN LCA 0800M FG",
    "SFC VIS:0800M FG LAN",
    "SIGWX:17/21 MAR AND COT ISOL/EMBD TS",
    "ICE:LAN LCA MOD/SEV ABV FL100",
    "TURB:LCA MOD/SEV SFC/FL150",
    "MT OBSC:N OF N4100 LAN S OF N3800 LAN",
    # Área ilegível antes da superfície (test_v34): "~" não é conteúdo
    "SIG CLD:15/18 BTN N4050 ~ N3840 MAR AND COT LCA BKN 008/012HFT AGL",
    # Algo com ar de área depois da superfície: fica como na 4.7.5
    "SIG CLD:15/17 BKN 004/008HFT AGL 17/19 EMBD MAR ISOL CB WI N4000 W00800 - "
    "N3900 W00800 - N3900 W00700 - N4000 W00800",
    "SIG CLD:BKN 002/008HFT AGL MAR ISOL CB NW OF W00800",
    "SIG CLD:BKN 002/008HFT AGL MAR ISOL CB WI 30NM OF N3900 W00800",
]


def _assin(blocos):
    return sorted((b.phenomenon, str(b.value), b.qualifier, b.surface, b.window,
                   b.janela_ambigua, round(b.polygon.area, 9)) for b in blocos)


@pytest.mark.parametrize("corpo", IGUAIS)
def test_casos_iguais_a_4_7_5(eng, eng475, corpo):
    t = _g(corpo)
    bn, *_ = eng.parse_gamet(t)
    bv, *_ = eng475.parse_gamet(t)
    assert _assin(bn) == _assin(bv), corpo
    assert eng.campos_nao_interpretados(t) == eng475.campos_nao_interpretados(t)
    assert eng.subentradas_sem_area(t) == eng475.subentradas_sem_area(t)
    assert _cortes(eng, corpo) == []


def test_area_ilegivel_com_lixo_antes_da_superficie(eng, eng475):
    """Uma palavra que não é área ("X") parte a linha; o aviso "Área não
    reconhecida" fica com o texto da 4.7.5 e a base continua em MAR∪COT de
    toda a FIR, como na 4.7.5."""
    t = _g("SIG CLD:N OF N3710 ISOL TCU/CB 025-040/XXXHFT AGL "
           "15/18 BTN N4050 X N3840 MAR AND COT LCA BKN 002/012HFT AGL")
    assert eng.subentradas_sem_area(t) == eng475.subentradas_sem_area(t)
    (s,) = eng.subentradas_sem_area(t)
    assert "BKN 002/012HFT AGL" in s
    bn, *_ = eng.parse_gamet(t)
    bv, *_ = eng475.parse_gamet(t)
    _blocos_cobertos(eng, bn, bv, t)
    assert eng.campos_nao_interpretados(t) == eng475.campos_nao_interpretados(t)


def _cortes(eng, corpo):
    return [c for l in eng.normalize(corpo).splitlines()
            for c in eng._cortes_superficie(l, [x[0] for x in eng._cortes_janela(l)])]


def test_cortes_superficie(eng):
    assert _cortes(eng, LINHA_REAL)
    l = eng.normalize(LINHA_REAL)
    (p,) = eng._cortes_superficie(l, [])
    assert l[p:].startswith("MAR AND COT ISOL")


# ---------------------------------------------------------------- janela e resto

def test_janela_da_linha_vale_nas_duas_partes(eng):
    blocos, *_ = eng.parse_gamet(_g("SIG CLD:17/19 BKN 002/008HFT AGL MAR OCNL CB "
                                    "030/XXXHFT AGL"))
    assert {b.window for b in blocos} == {"17–19Z"}
    assert not any(b.janela_ambigua for b in blocos)


def test_janela_no_fim_da_linha_continua_ambigua(eng):
    """Outra janela no fim da linha: na 4.7.5 todos os blocos ficavam
    janela_ambigua; o que vem antes da superfície também fica."""
    blocos, *_ = eng.parse_gamet(_g("SIG CLD:15/17 BKN 002/008HFT AGL MAR OCNL CB "
                                    "030/XXXHFT AGL 19/21"))
    assert blocos and all(b.janela_ambigua for b in blocos)


# ---------------------------------------------------------------- Secção II

def test_seccao_ii_nuvem_baixa_antes_da_superficie(eng, eng475):
    t = (f"LPPC GAMET VALID {VAL} LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
         "SFC VIS:NIL SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II "
         "CLD:SCT ST 004/008HFT AGL MAR SCT/BKN SC 015-030/040HFT AGL MNM QNH:1003HPA=")
    _c, novo = eng.nuvens_baixas_secn2(t)
    _c, antigo = eng475.nuvens_baixas_secn2(t)
    (n,) = novo
    (a,) = antigo
    assert n[0] == a[0] == 400
    assert n[3] == "" and a[3] == "MAR"
    assert set(a[4]) <= set(n[4])
    assert any("LPBG" in p for p in n[4]) and not any("LPBG" in p for p in a[4])


def test_seccao_ii_gamet_real_igual(eng, eng475):
    assert eng.nuvens_baixas_secn2(G081500) == eng475.nuvens_baixas_secn2(G081500)


# ---------------------------------------------------------------- AIRMET sintético

AIRMETS = [
    "LPPC AIRMET 1 VALID 251810/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BKN CLD OBS "
    "N OF N3930 COT 002HFT AGL STNR NC",
    "LPPC AIRMET 2 VALID 251840/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA SFC VIS "
    "0200-5000M FG/BR OBS N OF N3930 COT AND LAN STNR NC",
    "LPPC AIRMET 3 VALID 251840/252100 LPPT- LPPC LISBOA FIR/MAINLAND AREA SFC VIS "
    "4000M BR AND BKN CLD 002/010HFT AGL MAR AND COT ISOL TCU OBS N OF N3930 STNR NC",
]


@pytest.mark.parametrize("texto", AIRMETS)
def test_airmet_igual_a_4_7_5(eng, eng475, texto):
    n = eng.ler_airmet(texto)
    v = eng475.ler_airmet(texto)
    assert _assin(n["blocos"]) == _assin(v["blocos"])
    assert n["descr"] == v["descr"] and n["lido"] == v["lido"]


# ---------------------------------------------------------------- contra a 4.7.5

def _blocos_cobertos(eng, bn, bv, ctx):
    """Cada bloco da 4.7.5 tem um da 4.7.6 tão severo, com área que o contém."""
    for b in bv:
        assert any(eng._domina(n, b) for n in bn), (ctx, b.phenomenon, b.value, b.surface)


def _comparar(eng, eng475, texto, ctx, grelha=False):
    pts = _pontos(eng, grelha)
    novo = _decisoes(eng, texto, pts)
    antigo = _decisoes(eng475, texto, pts)
    for k in novo:
        assert GRAV[novo[k]] >= GRAV[antigo[k]], (ctx, k, novo[k], antigo[k])
    bn, *_ = eng.parse_gamet(texto)
    bv, *_ = eng475.parse_gamet(texto)
    _blocos_cobertos(eng, bn, bv, ctx)
    # Nenhum aviso "Campo não interpretado" novo
    assert set(eng.campos_nao_interpretados(texto)) <= \
        set(eng475.campos_nao_interpretados(texto)), ctx
    assert eng.subentradas_sem_area(texto) == eng475.subentradas_sem_area(texto), ctx
    return novo != antigo


def _resto_nao_menos_severo(eng, eng475, texto, agora, ctx, **kw):
    rn = eng.analisar_gamet(texto, agora=agora, **kw)
    rv = eng475.analisar_gamet(texto, agora=agora, **kw)
    # Decisão principal nunca menos severa, em toda a área
    for d in ("NO-GO", "MARGINAL"):
        an = sum(a for dd, a in rn["por_dec"].items() if GRAV[dd] >= GRAV[d])
        av = sum(a for dd, a in rv["por_dec"].items() if GRAV[dd] >= GRAV[d])
        assert an >= av - 1e-6, (ctx, agora, d)
    # Resto do período (sem resto: o principal), ponto a ponto: nunca menos severo
    for nome, (la, lo) in eng.AERODROMES.items():
        def _dec(e, r):
            if r.get("resto"):
                return e.resto_do_ponto(r["resto"], la, lo)
            return (e.find_region_for_point(r["regioes"], la, lo) or {}).get("decision")
        assert GRAV[_dec(eng, rn)] >= GRAV[_dec(eng475, rv)], (ctx, agora, nome)
    return rn, rv


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


def test_arquivo_manual_contra_4_7_5(eng, eng475):
    indice = _arquivo()
    n = mudaram = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        if conftest.linha_48(texto):
            continue  # 4.8: "D OF LINE" no GAMET, verificado em test_v48.py
        mudaram += _comparar(eng, eng475, texto, f.name, grelha=True)
        ini = eng._iso_utc(entrada.get("inicio"))
        if ini:
            for h in (1, 3.5, 5.5):
                _resto_nao_menos_severo(eng, eng475, texto, ini + timedelta(hours=h), f.name)
        n += 1
    assert n > 50


# GAMETs do arquivo que a 4.7.6 lê de outra forma que a 4.7.5 (e que, por isso,
# `conftest.superficie_476` tira das comparações por igualdade com motores
# antigos). Conjunto fixo (revisor do #44): um erro largo em
# `_cortes_superficie` faria saltar GAMETs em silêncio. Se aparecer um GAMET
# novo com uma superfície a meio da linha, este teste falha de propósito:
# confirma a leitura e acrescenta-o aqui.
LIDOS_DE_OUTRA_FORMA = {
    "20261015T1450Z_151500-152100_68a0284195.txt",   # Secção II: `… AGL LAN FEW/SCT AC/AS …`
    "20261108T1451Z_081500-082100_73bc1f4fc4.txt",   # SIG CLD: `… AGL MAR AND COT ISOL/EMBD TCU/CB …`
}


def test_arquivo_gamets_lidos_de_outra_forma(eng):
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    lidos = {p.name for p in sorted((DADOS / "gamets").rglob("*.txt"))
             if conftest.superficie_476(eng, p.read_text(encoding="utf-8"))}
    assert lidos == LIDOS_DE_OUTRA_FORMA, (
        f"novos: {sorted(lidos - LIDOS_DE_OUTRA_FORMA)}; "
        f"em falta: {sorted(LIDOS_DE_OUTRA_FORMA - lidos)}")


def test_arquivo_hist_contra_4_7_5(eng, eng475):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        if not f.exists():
            continue
        ini, fim = eng._iso_utc(entrada.get("inicio")), eng._iso_utc(entrada.get("fim"))
        if not ini or not fim:
            continue
        texto = f.read_text(encoding="utf-8")
        if conftest.linha_48(texto):
            continue  # 4.8: "D OF LINE" no GAMET, verificado em test_v48.py
        for agora in (ini + timedelta(minutes=30), fim - timedelta(minutes=15)):
            rn, rv = _resto_nao_menos_severo(eng, eng475, texto, agora, f.name,
                                             fonte="arquivo_hist", indice=indice,
                                             entrada=entrada)
            for nome, (la, lo) in eng.AERODROMES.items():
                a = eng.find_region_for_point(rn["regioes"], la, lo)
                b = eng475.find_region_for_point(rv["regioes"], la, lo)
                assert GRAV[(a or {}).get("decision")] >= GRAV[(b or {}).get("decision")], \
                    (f.name, nome)
            n += 1
    assert n > 100


def test_modo475_e_a_leitura_da_4_7_5(eng, eng475):
    """Justifica `conftest.superficie_476` e o `_modo475` usado em test_v475.py:
    a leitura interna `_modo475=True` dá os mesmos blocos que o motor da 4.7.5,
    em todo o arquivo e nas linhas geradas."""
    textos = []
    if (DADOS / "indice.json").exists():
        textos = [p.read_text(encoding="utf-8") for p in sorted((DADOS / "gamets").rglob("*.txt"))]
        # 4.8: "D OF LINE" no GAMET (também na leitura interna), em test_v48.py
        textos = [t for t in textos if not conftest.linha_48(t)]
    rng = random.Random(4760)
    textos += [_g(_linha(rng)) for _ in range(150)]
    for t in textos:
        a = eng.parse_gamet(t, _modo475=True)[0]
        b = eng475.parse_gamet(t)[0]
        assert _assin(a) == _assin(b), t[:200]
        assert [x.polygon.symmetric_difference(y.polygon).area < 1e-12
                for x, y in zip(a, b)] == [True] * len(b)


# ---------------------------------------------------------------- linhas geradas

SUPS = ["MAR", "LAN", "COT", "MAR AND COT", "COT AND LAN", "LAN AND MAR", "COT MAR"]
QUALS = ["", "", "", "W OF W00715 ", "N OF N4000 ", "S OF N3900 AND W OF W00800 ",
         "BTN N3840 AND N4000 ", "E OF W00800 "]
VALORES = {
    "SFC VIS": ["LCA 0200-5000M FG/BR", "0800M BR", "3000M RA", "LCA 1,5KM BR", "1200M BR",
                "2000M BR", "LCA 5000 RA", "FG", "BR"],
    "SIG CLD": ["LCA BKN 001-004/008HFT AGL", "BKN 004/010HFT AGL", "OVC 002/006HFT",
                "ISOL TCU/CB 020/XXXHFT AGL", "BKN 008/015HFT AMSL", "OCNL CB 030/XXXHFT AGL",
                "ISOL/EMBD TCU/CB 020-035/XXXHFT AGL", "LCA BKN 006-008/012HFT AGL",
                "BKN ST", "ISOL TCU", "EMBD"],
    "SIGWX": ["ISOL TS", "OCNL TSRA", "SQL", "FZDZ", "FRQ CB", "ISOL/EMBD TS", "EMBD", "TS"],
    "TURB": ["SEV SFC/FL080", "MOD SFC/FL050", "LCA MOD/SEV SFC/FL150", "MOD", "FL050/100"],
    "ICE": ["SEV FL060/FL120", "MOD FL050/FL100", "LCA MOD/SEV ABV FL100"],
    "SFC WSPD": ["30KT", "25-35KT", "20KT"],
    "MTW": ["SEV FL050/100", "MOD SFC/FL080"],
    "MT OBSC": ["", "BY CLD"],
}


def _linha(rng):
    campo = rng.choice(list(VALORES))
    val = lambda: rng.choice(VALORES[campo])  # noqa: E731
    h = rng.choice([15, 16, 17])
    partes = [rng.choice(["", "", f"{h:02d}/{h + 2:02d} "]) + rng.choice(["", "", "LCA "])
              + rng.choice(QUALS) + rng.choice(["", "", "", f"{rng.choice(SUPS)} "]) + val()]
    for _ in range(rng.choice([1, 1, 2, 3])):
        tipo = rng.choice(["sup", "sup", "sup", "valores", "janela", "sup_fim", "janela_sup"])
        if tipo == "sup":
            p = f"{rng.choice(['', '', 'AND '])}{rng.choice(SUPS)} {val()}"
        elif tipo == "valores":
            p = val()
        elif tipo == "janela":
            h = min(h + 1, 20)
            p = f"{h:02d}/{h + 2:02d} {val()}"
        elif tipo == "janela_sup":
            h = min(h + 1, 20)
            p = f"{h:02d}/{h + 2:02d} {rng.choice(SUPS)} {val()}"
        else:
            p = rng.choice(SUPS)
        partes.append(p)
    if rng.random() < 0.15:
        partes.append(f"{rng.choice(QUALS[3:])}{val()}")
    texto = " ".join(p.strip() for p in partes if p.strip())
    return f"{campo}{rng.choice([':', ': ', ' '])}{texto}"


def test_geradas_contra_4_7_5(eng, eng475):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "476")))
    n = int(os.environ.get("GAMET_CASOS", "300"))
    mudaram = cortados = 0
    for k in range(n):
        corpo = " ".join(_linha(rng) for _ in range(rng.choice([1, 1, 2])))
        t = _g(corpo)
        mudaram += _comparar(eng, eng475, t, corpo, grelha=(k % 3 == 0))
        cortados += bool(_cortes(eng, corpo))
        if k % 3 == 0:
            for agora in (_t(16, 0), _t(18, 30), _t(20, 30)):
                _resto_nao_menos_severo(eng, eng475, t, agora, corpo)
    # O gerador exercita de facto a mudança
    assert cortados > n // 3
    assert mudaram > 0
