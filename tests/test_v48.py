"""
4.8 — "D OF LINE p1 - p2 [- …]" na Secção I (e na Secção II) do GAMET.

GAMET real 091500/092100 de 9-nov-2026
(dados/gamets/2026/11/20261109T1444Z_091500-092100_540ca00855.txt):

    SFC VIS:N OF LINE N3800 W01000 - N4000 W00630 LCA 1200-5000M RA/DZ/BR
    SIG CLD:N OF LINE N3800 W01000 - N4000 W00630 LCA BKN 004-008/012HFT AGL
            N OF N3845 ISOL/EMBD TCU/CB 018-035/XXXHFT AGL

Até à 4.7.6 a subentrada ficava sem área → toda a FIR + aviso "Área não
reconhecida" (regra da 3.4): a VIS LCA 1200 m e a base de 400 ft iam para o
Algarve e o Baixo Alentejo (LPFR, LPBJ, LPFA, LPFC, LPPM, LP51, LP54, LP58,
LP59, LP78 em MARGINAL). Desde a 4.8 a área é o semiplano do lado D da linha,
prolongada pelos troços das pontas — a mesma geometria dos SIGMET/AIRMET desde
a 4.5 (`_semiplano_linha`) —, recortado à FIR e intersectado com os outros
qualificadores e a superfície da linha, sem margem. Na dúvida, fica como na
4.7.6 (toda a FIR + aviso). Verificado contra o motor da 4.7.6
(`tests/referencia/app_4_7_6.py`, cópia fixa do app.py do main c3712a5; não
editar). Semente: GAMET_SEMENTE (por omissão 48); GAMET_CASOS (por omissão 300).
"""
import os
import random
import types
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point

import conftest
from conftest import build_gamet

REF476 = Path(__file__).resolve().parent / "referencia" / "app_4_7_6.py"
DADOS = Path(__file__).resolve().parent.parent / "dados"
G091500_F = DADOS / "gamets/2026/11/20261109T1444Z_091500-092100_540ca00855.txt"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2, None: -1}
VAL = "091500/092100"
LINHA = "N3800 W01000 - N4000 W00630"

# O GAMET real, tal como foi recolhido (cópia, para correr sem `dados/`)
G091500 = (
    "LPPC GAMET VALID 091500/092100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
    "SECN I SFC VIS:N OF LINE N3800 W01000 - N4000 W00630 LCA 1200-5000M RA/DZ/BR "
    "SIGWX:N OF N3845 COT ISOL/EMBD TS SIG CLD:N OF LINE N3800 W01000 - N4000 W00630 "
    "LCA BKN 004-008/012HFT AGL N OF N3845 ISOL/EMBD TCU/CB 018-035/XXXHFT AGL "
    "TURB:N OF N3830 LCA MOD/SEV SFC/FL040 SIGMET APPLICABLE: AT TIME OF ISSUE NIL "
    "SECN II PSYS:18 N4545 W01900 L 972HPA STNR NC CLD:N OF LINE N3800 W01000 - "
    "N4000 W00630 SCT/BKN SC/CU 012-030/040HFT AGL S OF LINE N3800 W01000 - N4000 "
    "W00630 FEW/SCT SC/CU 012-030/040HFT AGL SCT/BKN AS/AC 060-090/100-130HFT AMSL "
    "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL "
    "200/021KT PS11 190/034KT PS15 190/028KT PS12 2000FT AGL 210/029KT PS09 190/043KT "
    "PS13 200/035KT PS11 5000FT AGL 220/036KT PS04 210/043KT PS09 210/041KT PS06 FL100 "
    "220/036KT MS00 210/041KT PS01 210/041KT MS00 FL150 220/038KT MS10 210/042KT MS09 "
    "220/041KT MS09 FZLVL: 9900FT AMSL 9900FT AMSL 9500FT AMSL LISBOA EVORA FARO N3845 "
    "W00908 N3830 W00752 N3700 W00800 1000FT AGL 210/030KT PS17 210/025KT PS16 "
    "230/021KT PS18 2000FT AGL 210/038KT PS15 220/031KT PS14 230/027KT PS16 5000FT AGL "
    "220/041KT PS09 220/036KT PS08 230/029KT PS10 FL100 230/042KT PS02 230/033KT PS00 "
    "240/031KT MS00 FL150 240/046KT MS08 240/044KT MS07 240/048KT MS06 FZLVL: 10500FT "
    "AMSL 10300FT AMSL 10500FT AMSL MNM QNH:1002HPA=")

SUL = {"LPFR", "LPBJ", "LPFA", "LPFC", "LPPM", "LP51", "LP54", "LP58", "LP59", "LP78"}


@pytest.fixture(scope="module")
def eng476(eng):
    mod = types.ModuleType("motor_4_7_6")
    mod.__dict__["__file__"] = str(REF476)
    exec(compile(conftest._extract_engine(REF476.read_text(encoding="utf-8")), str(REF476),
                 "exec"), mod.__dict__)
    return mod


def test_referencia_e_a_4_7_6(eng, eng476):
    assert eng476.APP_VERSION == "4.7.6"
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 8)


def test_copia_do_gamet_real_igual_ao_arquivo():
    if not G091500_F.exists():
        pytest.skip("sem dados/")
    assert " ".join(G091500_F.read_text(encoding="utf-8").split()) == G091500


def _g(corpo, secn2=""):
    t = build_gamet(f"SECN I {corpo}", validity=VAL)
    if secn2:
        t = t.replace(" SECN II ", f" SECN II CLD:{secn2} ")
    return t


def _icao(nome):
    return nome.split("(")[-1].rstrip(")")


def _decisoes(e, texto, pontos=None):
    blocos, *_ = e.parse_gamet(texto)
    regioes = e.compute_dynamic_regions(blocos)
    tem, sig = e.extract_sigmet_applicable(texto)
    if tem:
        regioes = e.apply_sigmet_override(regioes, sig)
    pontos = pontos if pontos is not None else list(e.AERODROMES.items())
    return {k: (e.find_region_for_point(regioes, la, lo) or {}).get("decision")
            for k, (la, lo) in pontos}


# ------------------------------------------------- lado D, calculado à parte

def _prolongada(pts, comp=60.0):
    """A linha (lon, lat) prolongada pelos troços das pontas."""
    pts = [q for i, q in enumerate(pts) if i == 0 or q != pts[i - 1]]
    def ext(p, q):
        vx, vy = p[0] - q[0], p[1] - q[1]
        n = (vx * vx + vy * vy) ** 0.5
        return (p[0] + vx / n * comp, p[1] + vy / n * comp)
    return LineString([ext(pts[0], pts[1])] + list(pts) + [ext(pts[-1], pts[-2])])


_DIR = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def lado(direc, pts, lon, lat):
    """True se (lon, lat) está do lado `direc` da linha: o raio que sai do ponto
    no sentido contrário de `direc` cruza a linha prolongada."""
    dx, dy = _DIR[direc]
    raio = LineString([(lon, lat), (lon - dx * 80, lat - dy * 80)])
    return raio.intersects(_prolongada(pts))


# ------------------------------------------------------------- GAMET real

def test_gamet_real_091500_areas(eng):
    blocos, *_ = eng.parse_gamet(G091500)
    pts = [(-10.0, 38.0), (-6.5, 40.0)]
    vis = [b for b in blocos if b.phenomenon == "VIS"]
    assert [b.value for b in vis] == [1200]
    base = [b for b in blocos if b.phenomenon == "BASE_AGL" and b.value == 400]
    assert len(base) == 1
    for b in (vis[0], base[0]):
        assert b.qualifier == "LCA"
        assert b.polygon.area < 0.8 * eng.FIR_POLYGON.area
        for nome, (la, lo) in eng.AERODROMES.items():
            dentro = b.polygon.buffer(1e-9).contains(Point(lo, la))
            assert dentro == lado("N", pts, lo, la), nome
    # O CB continua a ser uma subentrada com área própria (N OF N3845)
    cb = [b for b in blocos if b.phenomenon == "CB"]
    assert len(cb) == 1 and cb[0].value == "ISOL_EMBD"
    assert cb[0].parte.startswith("N OF N3845")
    assert not cb[0].polygon.contains(Point(-8.0, 38.5))


def test_gamet_real_091500_sem_avisos_de_area(eng):
    assert eng.subentradas_sem_area(G091500) == []
    assert eng.campos_nao_interpretados(G091500) == []
    r = eng.analisar_gamet(G091500, "manual")
    assert not any("Área não reconhecida" in md for _, md in r["avisos"])


def test_gamet_real_091500_52_pontos(eng, eng476):
    novo = _decisoes(eng, G091500)
    antigo = _decisoes(eng476, G091500)
    assert sum(v == "MARGINAL" for v in antigo.values()) == 10
    for nome in eng.AERODROMES:
        if _icao(nome) in SUL:
            assert antigo[nome] == "MARGINAL", nome
            assert novo[nome] == "GO", nome
        else:
            assert antigo[nome] == "NO-GO", nome
            assert novo[nome] == "NO-GO", nome
    assert {_icao(n) for n, (la, lo) in eng.AERODROMES.items()
            if novo[n] == "GO"} == SUL
    r = eng.analisar_gamet(G091500, "manual")
    for nome, (la, lo) in eng.AERODROMES.items():
        assert eng.find_region_for_point(r["regioes"], la, lo)["decision"] == novo[nome]


def test_gamet_real_091500_na_4_7_6_toda_a_fir_com_aviso(eng476):
    """O que a 4.8 muda (o teste das áreas falha com este motor)."""
    assert len(eng476.subentradas_sem_area(G091500)) == 2
    blocos, *_ = eng476.parse_gamet(G091500)
    vis = [b for b in blocos if b.phenomenon == "VIS"][0]
    assert vis.polygon.buffer(1e-6).contains(eng476.FIR_POLYGON)


def test_analisar_py_sem_alertas_de_area_nem_line(eng):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    r = analisar.analisar(eng, G091500)
    assert r["excepcao"] is None
    assert not any(a.startswith(("Palavras desconhecidas", "Área não reconhecida"))
                   for a in r["alertas"]), r["alertas"]
    # Uma linha ilegível continua a ser assinalada (agora como área)
    r = analisar.analisar(eng, _g("SFC VIS:N OF LINE N3800 W01000 0800M FG"))
    assert any(a.startswith("Área não reconhecida") for a in r["alertas"]), r["alertas"]


# ------------------------------------------------------------- variantes

def _so(blocos, fen, val):
    r = [b for b in blocos if b.phenomenon == fen and b.value == val]
    assert len(r) == 1, (fen, val, [(b.phenomenon, b.value) for b in blocos])
    return r[0]


def _verifica_lado(eng, poly, direc, pts, extra=None, passo=0.1):
    """Em toda a FIR (grelha de `passo`°): dentro de `poly` ⇔ do lado `direc`
    da linha (e de `extra`, se dado), longe da fronteira."""
    linha = _prolongada(pts)
    x0, y0, x1, y1 = eng.FIR_POLYGON.bounds
    n = 0
    la = y0
    while la < y1:
        lo = x0
        while lo < x1:
            p = Point(lo, la)
            if eng.FIR_POLYGON.buffer(-1e-3).contains(p) and linha.distance(p) > 1e-3:
                esperado = lado(direc, pts, lo, la) and (extra is None or extra(lo, la))
                assert poly.buffer(1e-9).contains(p) == esperado, (direc, pts, lo, la)
                n += 1
            lo += passo
        la += passo
    assert n > 100


@pytest.mark.parametrize("direc", ["N", "S"])
def test_n_e_s_da_linha_real(eng, direc):
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:{direc} OF LINE {LINHA} 0800M FG"))
    v = _so(blocos, "VIS", 800)
    _verifica_lado(eng, v.polygon, direc, [(-10.0, 38.0), (-6.5, 40.0)])
    assert not eng.subentradas_sem_area(_g(f"SFC VIS:{direc} OF LINE {LINHA} 0800M FG"))


@pytest.mark.parametrize("direc", ["E", "W"])
def test_e_e_w_de_linha_norte_sul(eng, direc):
    corpo = f"SIG CLD:{direc} OF LINE N3700 W00830 - N4200 W00745 BKN 002/008HFT AGL"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    b = _so(blocos, "BASE_AGL", 200)
    _verifica_lado(eng, b.polygon, direc, [(-8.5, 37.0), (-7.75, 42.0)])
    assert not eng.subentradas_sem_area(_g(corpo))


def test_linha_com_tres_pontos(eng):
    pts = [(-10.0, 37.0), (-8.0, 39.0), (-6.5, 39.5)]
    corpo = "SFC VIS:N OF LINE N3700 W01000 - N3900 W00800 - N3930 W00630 0800M FG"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    _verifica_lado(eng, _so(blocos, "VIS", 800).polygon, "N", pts)
    # Linha em V (mais área do que a recta entre as pontas): S de um V
    pts = [(-10.0, 41.0), (-8.0, 38.5), (-6.5, 41.0)]
    corpo = "SFC VIS:S OF LINE N4100 W01000 - N3830 W00800 - N4100 W00630 0800M FG"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    _verifica_lado(eng, _so(blocos, "VIS", 800).polygon, "S", pts)


@pytest.mark.parametrize("sup", ["MAR", "LAN", "COT", "MAR AND COT", "COT AND LAN"])
def test_com_superficie(eng, sup):
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:N OF LINE {LINHA} {sup} 0800M FG"))
    v = _so(blocos, "VIS", 800)
    chave = "/".join(s for s in ("COT", "LAN", "MAR") if s in sup)
    assert v.surface == chave
    sp = eng.surface_polygon(chave)
    semi = eng._clean_poly(eng.FIR_POLYGON.intersection(
        eng._semiplano_linha("N", [(-10.0, 38.0), (-6.5, 40.0)])))
    esperado = eng._clean_poly(semi.intersection(sp))
    assert v.polygon.symmetric_difference(esperado).area < 1e-9


@pytest.mark.parametrize("corpo", [
    f"SFC VIS:N OF LINE {LINHA} AND W OF W00800 0800M FG",
    f"SFC VIS:N OF LINE {LINHA} W OF W00800 0800M FG",
    f"SFC VIS:W OF W00800 AND N OF LINE {LINHA} 0800M FG",
    f"SFC VIS:W OF W00800 N OF LINE {LINHA} 0800M FG",
])
def test_com_outro_qualificador(eng, corpo):
    blocos, *_ = eng.parse_gamet(_g(corpo))
    assert len(blocos) == 1
    _verifica_lado(eng, blocos[0].polygon, "N", [(-10.0, 38.0), (-6.5, 40.0)],
                   extra=lambda lo, la: lo < -8.0)
    assert not eng.subentradas_sem_area(_g(corpo))


def test_abre_subentrada_depois_de_valores(eng):
    corpo = f"SIG CLD:BKN 002/008HFT AGL S OF LINE {LINHA} OCNL CB 020/XXXHFT AGL"
    blocos, *_ = eng.parse_gamet(_g(corpo))
    b2 = _so(blocos, "BASE_AGL", 200)
    assert b2.polygon.buffer(1e-6).contains(eng.FIR_POLYGON)        # 1.ª subentrada
    cb = _so(blocos, "CB", "OCNL")
    assert cb.parte.startswith("S OF LINE")
    _verifica_lado(eng, cb.polygon, "S", [(-10.0, 38.0), (-6.5, 40.0)])
    assert not eng.subentradas_sem_area(_g(corpo))
    assert not eng.campos_nao_interpretados(_g(corpo))


def test_janelas(eng):
    # Janela antes da linha, na própria subentrada
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:17/19 N OF LINE {LINHA} 0800M FG"))
    assert _so(blocos, "VIS", 800).window == "17–19Z"
    # Janela no fim da linha anterior: passa para a subentrada da linha
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:0800M FG 17/19 N OF LINE {LINHA} 2000M BR"))
    v8, v20 = _so(blocos, "VIS", 800), _so(blocos, "VIS", 2000)
    assert v8.window == "" and v8.polygon.buffer(1e-6).contains(eng.FIR_POLYGON)
    assert v20.window == "17–19Z"
    _verifica_lado(eng, v20.polygon, "N", [(-10.0, 38.0), (-6.5, 40.0)])
    # Janela depois da linha (só área antes): é a da subentrada
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:N OF LINE {LINHA} 17/19 0800M FG"))
    assert _so(blocos, "VIS", 800).window == "17–19Z"
    # Janela a meio dos valores (4.3): parte nova com a área da subentrada
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:N OF LINE {LINHA} 0800M FG 19/21 2000M BR"))
    v8, v20 = _so(blocos, "VIS", 800), _so(blocos, "VIS", 2000)
    assert v20.window == "19–21Z"
    assert v8.polygon.symmetric_difference(v20.polygon).area < 1e-9
    assert v8.polygon.area < 0.8 * eng.FIR_POLYGON.area


def test_superficie_a_meio_depois_da_linha(eng):
    """4.7.6: a superfície a meio parte; a parte antes fica com o semiplano."""
    blocos, *_ = eng.parse_gamet(_g(f"SFC VIS:N OF LINE {LINHA} LCA 1200M BR MAR 0800M FG"))
    v12, v8 = _so(blocos, "VIS", 1200), _so(blocos, "VIS", 800)
    assert v12.surface == "" and v8.surface == "MAR"
    assert v8.polygon.buffer(1e-6).within(v12.polygon.buffer(1e-6)) or v8.polygon.area < v12.polygon.area
    _verifica_lado(eng, v12.polygon, "N", [(-10.0, 38.0), (-6.5, 40.0)])


def test_s_de_linha_a_norte_da_fir_e_toda_a_fir_sem_aviso(eng):
    t = _g("SFC VIS:S OF LINE N4300 W01000 - N4330 W00600 0800M FG")
    blocos, *_ = eng.parse_gamet(t)
    assert blocos[0].polygon.buffer(1e-6).contains(eng.FIR_POLYGON)
    assert not eng.subentradas_sem_area(t)


# ------------------------------------------------------------- na dúvida

DUVIDA = [
    "SFC VIS:N OF LINE N3800 W01000 0800M FG",                          # um só ponto
    "SFC VIS:N OF LINE N3800 W01000 - N3800 W01000 0800M FG",           # degenerada
    "SFC VIS:N OF LINE N3700 W00800 - N4100 W00810 0800M FG",           # quase paralela
    "SFC VIS:E OF LINE N3800 W01000 - N3810 W00600 0800M FG",           # quase paralela
    "SFC VIS:N OF LINE N38 W010 - N40 W00630 0800M FG",                 # só graus
    "SFC VIS:N OF LINE N3800 W01000 - N4000 W0630 0800M FG",            # coordenada ilegível
    f"SFC VIS:NW OF LINE {LINHA} 0800M FG",                             # diagonal
    f"SFC VIS:N OF LINE {LINHA} - N41 W006 0800M FG",                   # ponto por ler
    f"SFC VIS:N OF LINE {LINHA} N4100 W00600 0800M FG",                 # ponto sem hífen
    f"SFC VIS:ALONG LINE {LINHA} 0800M FG",                             # LINE sem D OF
    f"SFC VIS:LINE {LINHA} 0800M FG",
    f"SFC VIS:N OF N3700 AND LINE {LINHA} 0800M FG",
    "SFC VIS:N OF LINE N4100 W01000 - N4130 W00600 AND S OF N3800 0800M FG",  # vazia
    "SFC VIS:N OF LINE N4300 W01000 - N4330 W00600 0800M FG",           # fora da FIR
    f"SFC VIS:N OF LINE {LINHA} AND S OF LINE {LINHA} 0800M FG",        # vazia
    f"SFC VIS:N OF LINE {LINHA} AND NW OF W00800 0800M FG",             # com diagonal
    "SFC VIS:E OF LINE N4130 W00700 - N3930 W00715 AND N OF N3900 MAR 0800M FG",  # sem mar
]


@pytest.mark.parametrize("corpo", DUVIDA)
def test_na_duvida_toda_a_fir_com_aviso(eng, eng476, corpo):
    t = _g(corpo)
    blocos, *_ = eng.parse_gamet(t)
    v = _so(blocos, "VIS", 800)
    toda = eng.FIR_POLYGON if not v.surface else eng.surface_polygon(v.surface)
    assert v.polygon.buffer(1e-6).contains(toda), corpo
    assert len(eng.subentradas_sem_area(t)) == 1, corpo
    # Nunca mais permissivo do que a 4.7.6
    pts = list(eng.AERODROMES.items())
    novo, antigo = _decisoes(eng, t, pts), _decisoes(eng476, t, pts)
    assert all(GRAV[novo[k]] >= GRAV[antigo[k]] for k in novo), corpo


def test_linha_ilegivel_depois_de_valores_nao_herda_area(eng):
    """Um "LINE" ilegível numa subentrada de continuação também é toda a FIR
    com aviso (como as diagonais), nunca a área da subentrada anterior."""
    t = _g("SFC VIS:N OF N4100 3000M BR S OF LINE N3800 W01000 0800M FG")
    blocos, *_ = eng.parse_gamet(t)
    assert _so(blocos, "VIS", 800).polygon.buffer(1e-6).contains(eng.FIR_POLYGON)
    assert _so(blocos, "VIS", 3000).polygon.area < 0.5 * eng.FIR_POLYGON.area
    assert len(eng.subentradas_sem_area(t)) == 1


# ------------------------------------------------------------- Secção II

def test_seccao_ii_gamet_real_091500(eng, eng476):
    """A leitura da Secção II separa N e S da linha; a nota tem a garantia da
    4.7.6 (revisor do PR #45): o AS/AC 6000 ft AMSL que vem depois de "S OF
    LINE … FEW/SCT SC/CU" pode valer para toda a FIR — a nota mantém
    LPBG/LPSE/LP66, agora sem a linha "área não reconhecida"."""
    conteudo, nuvens = eng.nuvens_baixas_secn2(G091500)
    assert conteudo.startswith("N OF LINE")
    assert nuvens == [(6000, "AMSL", "", "", ["Bragança (LPBG)", "Seia (LPSE)",
                                               "Cabeço da Vaca (LP66)"], True, False)]
    assert [n[:5] for n in nuvens] == [n[:5] for n in eng476.nuvens_baixas_secn2(G091500)[1]]
    aviso = eng._aviso_nuvens_baixas(G091500)[1]
    assert "LPBG, LPSE, LP66" in aviso and "área não reconhecida" not in aviso
    # A leitura (sem a garantia) continua a separar os lados da linha
    blocos, *_ = eng.parse_gamet(f"SECN I SIG CLD:{conteudo} SECN II")
    pts = [(-10.0, 38.0), (-6.5, 40.0)]
    b_n = [b for b in blocos if b.parte.startswith("SIG CLD:N OF")]
    b_s = [b for b in blocos if b.parte.startswith("S OF")]
    assert len(b_n) == 1 and len(b_s) == 2
    assert all(b.linha for b in blocos)
    _verifica_lado(eng, b_n[0].polygon, "N", pts, passo=0.2)
    for b in b_s:
        _verifica_lado(eng, b.polygon, "S", pts, passo=0.2)
    assert not eng.subentradas_sem_area(f"SECN I SIG CLD:{conteudo} SECN II")


def test_seccao_ii_nuvem_baixa_com_garantia(eng, eng476):
    t = _g("SFC VIS:2000M BR", secn2=f"N OF LINE {LINHA} BKN ST 003-008/010HFT AGL")
    _, nuvens = eng.nuvens_baixas_secn2(t)
    assert len(nuvens) == 1
    base, ref, _, _, pontos, lida, _ = nuvens[0]
    assert (base, ref, lida) == (300, "AGL", True)
    pts = [(-10.0, 38.0), (-6.5, 40.0)]
    lado_n = {n for n, (la, lo) in eng.AERODROMES.items() if lado("N", pts, lo, la)}
    # A 4.7.6 dava toda a FIR: a nota nunca tem menos pontos
    assert set(pontos) >= lado_n
    assert set(pontos) == set(eng476.nuvens_baixas_secn2(t)[1][0][4])
    # Decisão inalterada (a Secção II não entra na decisão)
    assert set(_decisoes(eng, t).values()) == {"MARGINAL"}
    assert "área não reconhecida" not in eng._aviso_nuvens_baixas(t)[1]


def test_seccao_ii_270900_garantia_repoe_lpse(eng, eng476):
    """GAMET real 270900/271500: "N OF LINE N3900 W01200 - N4200 W00800 SCT/BKN
    AS/AC 060-090/…HFT AMSL". A 4.7.6 não partia a linha (o AS/AC ficava com o
    W OF W00715 da subentrada anterior e a nota dava LPSE). A 4.8 lê-o a N da
    linha, que não chega a LPSE, mas a nota une a área da 4.7.6: LPSE fica."""
    t = _g("SFC VIS:3000M BR", secn2="W OF W00715 SCT/BKN SC 012-030/040HFT AGL N OF LINE "
           "N3900 W01200 - N4200 W00800 SCT/BKN AS/AC 060-090/100-130HFT AMSL")
    assert [n[4] for n in eng476.nuvens_baixas_secn2(t)[1]] == [["Seia (LPSE)"]]
    assert [n[4] for n in eng.nuvens_baixas_secn2(t)[1]] == [["Seia (LPSE)"]]
    blocos, *_ = eng.parse_gamet(f"SECN I SIG CLD:{eng.nuvens_baixas_secn2(t)[0]} SECN II")
    asac = _so(blocos, "BASE_AMSL", 6000)
    assert asac.linha
    _verifica_lado(eng, asac.polygon, "N", [(-12.0, 39.0), (-8.0, 42.0)], passo=0.2)


def test_seccao_ii_sem_linha_sem_garantia(eng):
    """Sem LINE nada muda: nenhuma base vem de uma linha."""
    t = _g("SFC VIS:3000M BR", secn2="W OF W00715 SCT ST 003/008HFT AGL")
    blocos, *_ = eng.parse_gamet(f"SECN I SIG CLD:{eng.nuvens_baixas_secn2(t)[0]} SECN II")
    assert not any(b.linha for b in blocos)


# ------------------------------------------------------------- contra a 4.7.6

import json  # noqa: E402
import re  # noqa: E402
from datetime import timedelta  # noqa: E402

# Grelha de 0,3° sobre a FIR (além dos 52 aeródromos)
GRELHA = [(36.95 + 0.3 * i, -9.55 + 0.3 * j) for i in range(18) for j in range(12)]
# Leitura própria do teste (independente do motor) de "D OF LINE …"
_LINHA_T = re.compile(r"\b([NSEW]) OF LINE ((?:N\d{4} [WE]\d{5} - )+N\d{4} [WE]\d{5})(?![\dA-Z])")


def _pts(txt):
    out = []
    for la, h, lo in re.findall(r"N(\d{4}) ([WE])(\d{5})", txt):
        lat = int(la[:2]) + int(la[2:]) / 60
        lon = int(lo[:3]) + int(lo[3:]) / 60
        out.append((-lon if h == "W" else lon, lat))
    return out


def _linhas_da_parte(parte):
    return [(m.group(1), _pts(m.group(2))) for m in _LINHA_T.finditer(" ".join(parte.split()))]


def _pontos(eng, grelha=False):
    p = list(eng.AERODROMES.items())
    if grelha:
        p += [(f"grelha {la:.2f} {lo:.2f}", (la, lo)) for la, lo in GRELHA
              if eng.FIR_POLYGON.contains(Point(lo, la))]
    return p


def _secn1(texto):
    return re.split(r"SECN\s+II", texto, maxsplit=1)[0]


def _assin(blocos):
    return [(b.phenomenon, str(b.value), b.qualifier, b.surface, b.window, b.janela_ambigua,
             round(b.polygon.area, 9)) for b in blocos]


def _testemunha(eng, eng476, texto, la, lo):
    """Prova de que o ponto ficou mais permissivo por estar fora de um
    semiplano: um bloco da 4.7.6 que o cobre não tem, na 4.8, nenhum bloco
    igual (fenómeno, valor) que o cubra, e um bloco igual da 4.8 vem de uma
    parte com uma linha legível de cujo lado D o ponto não está (calculado à
    parte, com a linha lida pelo teste) — ou que o ponto está fora dos outros
    qualificadores ou da superfície dessa parte."""
    p = Point(lo, la)
    # Em cima de uma linha (< 0,001°) é fronteira: nenhum dos lados é errado
    if any(len(set(pts)) >= 2 and _prolongada(pts).distance(p) < 1e-3
           for _, pts in _linhas_da_parte(_secn1(texto))):
        return True
    bn = eng.parse_gamet(texto)[0]
    for b in eng476.parse_gamet(texto)[0]:
        if not b.polygon.buffer(1e-9).contains(p):
            continue
        iguais = [n for n in bn if (n.phenomenon, n.value) == (b.phenomenon, b.value)]
        if any(n.polygon.buffer(1e-9).contains(p) for n in iguais):
            continue
        for n in iguais:
            linhas = _linhas_da_parte(n.parte or "")
            if not linhas:
                continue
            for direc, pts in linhas:
                if len(set(pts)) >= 2 and not lado(direc, pts, lo, la):
                    return True
            # Ou fora dos outros qualificadores / da superfície da mesma parte,
            # lidos pelo motor da 4.7.6 (que os punha noutra subentrada e dava
            # ao "D OF LINE … AND" toda a FIR)
            resto = _LINHA_T.sub(" ", " ".join(n.parte.split()))
            q = eng476.extract_polygon(resto)
            if q is not None and not q.buffer(1e-9).contains(p):
                return True
            sup = "/".join(x for x in ("COT", "LAN", "MAR") if re.search(rf"\b{x}\b", resto))
            sp = eng476.surface_polygon(sup) if sup else None
            if sp is not None and not sp.buffer(1e-9).contains(p):
                return True
    return False


def _comparar(eng, eng476, texto, ctx, grelha=False, decisoes=None):
    """Sem LINE na Secção I: blocos e decisões iguais. Com LINE: só pode ficar
    mais permissivo um ponto fora do semiplano de uma linha. Devolve o nº de
    pontos mais permissivos."""
    pts = _pontos(eng, grelha)
    if decisoes is None:
        novo, antigo = _decisoes(eng, texto, pts), _decisoes(eng476, texto, pts)
    else:
        novo, antigo = decisoes
    bn, *_ = eng.parse_gamet(texto)
    bv, *_ = eng476.parse_gamet(texto)
    if not re.search(r"\bLINE\b", _secn1(texto)):
        assert _assin(bn) == _assin(bv), ctx
        assert novo == antigo, ctx
        assert eng.subentradas_sem_area(texto) == eng476.subentradas_sem_area(texto), ctx
        return 0
    n = 0
    for k, (la, lo) in pts:
        if GRAV[novo[k]] < GRAV[antigo[k]]:
            assert _testemunha(eng, eng476, texto, la, lo), (ctx, k, antigo[k], novo[k])
            n += 1
    # Nenhum aviso "Campo não interpretado" novo
    assert set(eng.campos_nao_interpretados(texto)) <= \
        set(eng476.campos_nao_interpretados(texto)), ctx
    return n


def _nota_nunca_perde(eng, eng476, texto, ctx):
    """Garantia da nota da Secção II (revisor do PR #45): cada base da nota da
    4.7.6 está na da 4.8, com os mesmos pontos ou mais (a janela pode passar a
    ser todo o período e o LCA cair: uma subentrada nova não herda a janela
    nem o LCA da linha da 4.7.6 — mais conservador)."""
    novo = eng.nuvens_baixas_secn2(texto)[1]
    for base, ref, jan, _sup, pontos, _lida, lca in eng476.nuvens_baixas_secn2(texto)[1]:
        assert any((n[0], n[1]) == (base, ref) and n[2] in ("", jan) and n[6] <= lca
                   and set(n[4]) >= set(pontos) for n in novo), (ctx, base, ref, jan, pontos)


def _arquivo():
    if not (DADOS / "indice.json").exists():
        pytest.skip("sem dados/")
    return json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))


def _sem_nota_secn2(avisos):
    return [a for a in avisos if "Nuvens baixas na Secção II" not in a[1]]


# GAMETs do arquivo com "LINE" (a 10-nov-2026). `conftest.linha_48` tira-os das
# comparações por igualdade com motores antigos; se aparecer outro, este teste
# falha de propósito: confirma a leitura e acrescenta-o aqui.
COM_LINHA = {
    "20261017T0242Z_170300-170900_8f7b0c865c.txt": "II",
    "20261020T2049Z_202100-210300_07eb03c12c.txt": "II",
    "20261024T0851Z_240900-241500_6ba62ed9c0.txt": "II",
    "20261027T0853Z_270900-271500_c8fefbd089.txt": "II",
    "20261106T0841Z_060900-061500_f32bab6a2c.txt": "II",
    "20261109T1444Z_091500-092100_540ca00855.txt": "I",
}


def test_arquivo_gamets_com_linha():
    if not (DADOS / "gamets").exists():
        pytest.skip("sem dados/")
    com = {}
    for p in sorted((DADOS / "gamets").rglob("*.txt")):
        t = p.read_text(encoding="utf-8")
        if conftest.linha_48(t):
            com[p.name] = "I" if re.search(r"\bLINE\b", _secn1(t)) else "II"
    assert com == COM_LINHA


def test_arquivo_manual_contra_4_7_6(eng, eng476):
    _arquivo()
    n = perm = 0
    for f in sorted((DADOS / "gamets").rglob("*.txt")):
        texto = f.read_text(encoding="utf-8")
        perm += _comparar(eng, eng476, texto, f.name, grelha=True)
        rn = eng.analisar_gamet(texto, "manual")
        rv = eng476.analisar_gamet(texto, "manual")
        if not conftest.linha_48(texto):
            assert rn["avisos"] == rv["avisos"], f.name
            assert rn["por_dec"] == rv["por_dec"], f.name
            assert eng.nuvens_baixas_secn2(texto) == eng476.nuvens_baixas_secn2(texto)
        elif COM_LINHA.get(f.name) == "II":
            # Só a nota informativa da Secção II pode mudar
            assert _sem_nota_secn2(rn["avisos"]) == _sem_nota_secn2(rv["avisos"]), f.name
            assert rn["por_dec"] == rv["por_dec"], f.name
        _nota_nunca_perde(eng, eng476, texto, f.name)
        n += 1
    assert n > 100
    # Só o 091500 (o único com LINE na Secção I): os 10 pontos do sul
    assert perm == 10 + sum(
        1 for la, lo in GRELHA if eng.FIR_POLYGON.contains(Point(lo, la))
        and GRAV[_decisoes(eng, G091500, [("g", (la, lo))])["g"]]
        < GRAV[_decisoes(eng476, G091500, [("g", (la, lo))])["g"]])


def test_arquivo_hist_contra_4_7_6(eng, eng476):
    indice = _arquivo()
    n = 0
    for entrada in indice.get("gamets", []):
        f = DADOS / entrada["ficheiro"]
        ini = eng._iso_utc(entrada.get("inicio"))
        if not f.exists() or not ini:
            continue
        texto = f.read_text(encoding="utf-8")
        agora = ini + timedelta(minutes=30)
        rn = eng.analisar_gamet(texto, "arquivo_hist", indice=indice, entrada=entrada,
                                agora=agora)
        rv = eng476.analisar_gamet(texto, "arquivo_hist", indice=indice, entrada=entrada,
                                   agora=agora)
        pts = _pontos(eng)
        dn = {k: (eng.find_region_for_point(rn["regioes"], la, lo) or {}).get("decision")
              for k, (la, lo) in pts}
        dv = {k: (eng476.find_region_for_point(rv["regioes"], la, lo) or {}).get("decision")
              for k, (la, lo) in pts}
        if not re.search(r"\bLINE\b", _secn1(texto)):
            assert dn == dv, f.name
            assert rn["por_dec"] == rv["por_dec"], f.name
        else:
            for k, (la, lo) in pts:
                if GRAV[dn[k]] < GRAV[dv[k]]:
                    assert _testemunha(eng, eng476, texto, la, lo), (f.name, k)
        n += 1
    assert n > 100


# ------------------------------------------------------------- linhas geradas

VALORES = {
    "SFC VIS": ["LCA 1200-5000M RA/DZ/BR", "0800M FG", "2000M BR", "LCA 0400M FG"],
    "SIG CLD": ["LCA BKN 004-008/012HFT AGL", "BKN 002/006HFT AGL", "OCNL CB 030/XXXHFT AGL",
                "ISOL/EMBD TCU/CB 018-035/XXXHFT AGL", "BKN 008/015HFT AMSL"],
    "SIGWX": ["ISOL TS", "OCNL TSRA", "ISOL/EMBD TS"],
    "TURB": ["SEV SFC/FL080", "LCA MOD/SEV SFC/FL040"],
    "MT OBSC": ["BY CLD"],
}
QUALS = ["W OF W00800", "N OF N3830", "E OF W00800", "BTN N3800 AND N4000", "S OF N4100"]
SUPS = ["MAR", "LAN", "COT", "MAR AND COT"]


def _coord_txt(lon, lat):
    la, lo = round(abs(lat) * 60), round(abs(lon) * 60)
    return f"N{la // 60:02d}{la % 60:02d} W{lo // 60:03d}{lo % 60:02d}"


def _linha_gerada(rng):
    n = rng.choice([2, 2, 2, 3])
    q = lambda a, b: rng.randint(int(a * 4), int(b * 4)) / 4  # noqa: E731
    pts = [(q(-11, -6), q(36.5, 42.5)) for _ in range(n)]
    if rng.random() < 0.05:
        pts[1] = pts[0]                                      # degenerada
    direc = rng.choice("NSEW")
    txt = f"{direc} OF LINE " + " - ".join(_coord_txt(*p) for p in pts)
    if rng.random() < 0.05:
        txt = txt.replace("0 W", " W", 1)                    # coordenada ilegível
    return txt


def _corpo_gerado(rng, com_linha=True):
    campos = []
    for _ in range(rng.choice([1, 1, 2])):
        campo = rng.choice(list(VALORES))
        val = lambda: rng.choice(VALORES[campo])  # noqa: E731
        area = _linha_gerada(rng) if com_linha else rng.choice(QUALS)
        r = rng.random()
        if r < 0.2:
            area = f"{area} AND {rng.choice(QUALS)}"
        elif r < 0.3:
            area = f"{rng.choice(QUALS)} {rng.choice(['AND ', ''])}{area}"
        sub = rng.choice(["", "", "16/18 "]) + area + rng.choice(["", "", f" {rng.choice(SUPS)}"])
        sub += " " + val()
        partes = [sub]
        r = rng.random()
        if r < 0.25:
            partes.insert(0, val())                          # valores antes: quebra
        elif r < 0.4:
            partes.append(f"{rng.choice(QUALS)} {val()}")    # outra subentrada depois
        elif r < 0.5:
            partes.append(f"19/21 {val()}")                  # janela a meio
        elif r < 0.6:
            partes.insert(0, f"{val()} 17/19")               # janela antes da linha
        campos.append(f"{campo}:{' '.join(partes)}")
    return " ".join(campos)


def test_geradas_contra_4_7_6(eng, eng476):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "48")))
    n = int(os.environ.get("GAMET_CASOS", "300"))
    perm = lidas = 0
    for k in range(n):
        com = k % 4 != 0
        corpo = _corpo_gerado(rng, com_linha=com)
        t = _g(corpo)
        perm += _comparar(eng, eng476, t, corpo, grelha=(k % 3 == 0))
        lidas += com and not eng.subentradas_sem_area(t)
    # O gerador exercita de facto a mudança
    assert perm > 0 and lidas > n // 4


def test_propriedade_lado_d_sempre_dentro(eng):
    """Linhas aleatórias (2–3 pontos, N/S/E/W): todo o ponto da FIR do lado D
    (calculado à parte) está na área do bloco, e nenhum do outro lado — ou,
    na dúvida, a área é toda a FIR com aviso."""
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "48")) + 1)
    lidas = 0
    for _ in range(60):
        txt = _linha_gerada(rng)
        t = _g(f"SFC VIS:{txt} 0800M FG")
        v = _so(eng.parse_gamet(t)[0], "VIS", 800)
        if eng.subentradas_sem_area(t):
            assert v.polygon.buffer(1e-6).contains(eng.FIR_POLYGON), txt
            continue
        (direc, pts), = _linhas_da_parte(txt)
        _verifica_lado(eng, v.polygon, direc, pts, passo=0.25)
        lidas += 1
    assert lidas > 20


# ------------------------------------------------------------- EXC / OR

EXC_OR = [
    f"SFC VIS:ENTIRE FIR EXC N OF LINE {LINHA} 0800M FG",
    f"SFC VIS:N OF LINE {LINHA} EXC MAR 0800M FG",
    f"SFC VIS:0800M FG EXC N OF LINE {LINHA}",
    f"SFC VIS:N OF N4000 OR N OF LINE {LINHA} 0800M FG",
    f"SFC VIS:N OF LINE {LINHA} OR S OF N3800 0800M FG",
    f"SFC VIS:N OF LINE {LINHA} OR E OF W00800 0800M FG",
    f"SFC VIS:2000M BR OR N OF LINE {LINHA} 0800M FG",
    f"SIG CLD:BKN 008/015HFT AGL EXC S OF LINE {LINHA} BKN 002/006HFT AGL",
    f"SIG CLD:S OF LINE {LINHA} OR W OF W00800 BKN 002/006HFT AGL",
    f"SIG CLD:ENTIRE FIR EXC S OF LINE {LINHA} AND W OF W00800 BKN 002/006HFT AGL",
]


@pytest.mark.parametrize("corpo", EXC_OR)
def test_exc_or_com_linha_como_na_4_7_6(eng, eng476, corpo):
    """Revisor do PR #45: "ENTIRE FIR EXC N OF LINE …" não pode ler-se "a N da
    linha". Com EXC ou OR a linha com LINE fica como na 4.7.6 (sem área
    legível: toda a FIR), com aviso; nunca mais permissivo do que a 4.7.6."""
    t = _g(corpo)
    pts = _pontos(eng, grelha=True)
    novo, antigo = _decisoes(eng, t, pts), _decisoes(eng476, t, pts)
    for k in novo:
        assert GRAV[novo[k]] >= GRAV[antigo[k]], (corpo, k)
    bn, bv = eng.parse_gamet(t)[0], eng476.parse_gamet(t)[0]
    for v in bv:
        assert any(eng._domina(n, v) for n in bn), (corpo, v.phenomenon, v.value)
    assert not any(b.linha for b in bn)
    # A linha com LINE e EXC/OR tem o aviso "Área não reconhecida"
    sem = eng.subentradas_sem_area(t)
    assert any("LINE" in x and re.search(r"\b(?:EXC|OR)\b", x) for x in sem), sem
    assert set(eng476.subentradas_sem_area(t)) <= set(sem)


def test_exc_or_sem_linha_inalterados(eng, eng476):
    for corpo in ("SFC VIS:ENTIRE FIR EXC N OF N4000 0800M FG",
                  "SFC VIS:N OF N4000 OR S OF N3800 0800M FG",
                  "SIG CLD:BKN 002/006HFT AGL EXC MAR"):
        t = _g(corpo)
        assert _assin(eng.parse_gamet(t)[0]) == _assin(eng476.parse_gamet(t)[0]), corpo
        assert eng.subentradas_sem_area(t) == eng476.subentradas_sem_area(t), corpo


# ------------------------------------------------------------- leitura da 4.7.6

def test_modo476_e_a_leitura_da_4_7_6(eng, eng476):
    """A leitura interna `_modo476=True` (garantia da nota da Secção II) dá os
    mesmos blocos que o motor da 4.7.6: arquivo (Secção I e o CLD da Secção II),
    linhas geradas e os casos EXC/OR."""
    textos = []
    if (DADOS / "gamets").exists():
        for p in sorted((DADOS / "gamets").rglob("*.txt")):
            t = p.read_text(encoding="utf-8")
            textos.append(t)
            conteudo, _ = eng.nuvens_baixas_secn2(t)
            if conteudo:
                textos.append(f"SECN I SIG CLD:{conteudo} SECN II")
    rng = random.Random(4761)
    textos += [_g(_corpo_gerado(rng)) for _ in range(150)]
    textos += [_g(c) for c in EXC_OR + DUVIDA]
    for t in textos:
        a = eng.parse_gamet(t, _modo476=True)[0]
        b = eng476.parse_gamet(t)[0]
        assert _assin(a) == _assin(b), t[:200]
        assert all(x.polygon.symmetric_difference(y.polygon).area < 1e-12
                   for x, y in zip(a, b)), t[:200]
        sa, sb = [], []
        eng.parse_gamet(t, sa, _modo476=True)
        eng476.parse_gamet(t, sb)
        assert sa == sb, t[:200]


# ------------------------------------------------------------- nota: geradas

def test_seccao_ii_geradas_nota_nunca_perde(eng, eng476):
    rng = random.Random(int(os.environ.get("GAMET_SEMENTE", "48")) + 2)
    bases = ["SCT ST 003-008/010HFT AGL", "BKN SC 004/012HFT AGL", "SCT/BKN AS/AC 060-090/100HFT AMSL",
             "FEW/SCT SC/CU 012-030/040HFT AGL", "BKN ST 002/006HFT AGL"]
    com_nota = 0
    for _ in range(int(os.environ.get("GAMET_CASOS", "300")) // 3):
        subs = []
        for _ in range(rng.choice([1, 2, 3])):
            area = rng.choice([_linha_gerada(rng), _linha_gerada(rng), rng.choice(QUALS), ""])
            sup = rng.choice(["", "", f" {rng.choice(SUPS)}"])
            vals = " ".join(rng.choice(bases) for _ in range(rng.choice([1, 2])))
            subs.append(f"{rng.choice(['', '', '16/18 '])}{area}{sup} {vals}".strip())
        t = _g("SFC VIS:3000M BR", secn2=" ".join(subs))
        _nota_nunca_perde(eng, eng476, t, subs)
        com_nota += bool(eng.nuvens_baixas_secn2(t)[1])
    assert com_nota > 10
