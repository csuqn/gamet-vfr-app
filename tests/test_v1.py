"""
Regressões e invariantes introduzidos na 1.0.

Cada teste corresponde a um erro real encontrado na revisão da v31 — os
GAMETs usados são os que o expuseram.
"""
import random
from datetime import datetime, timezone

import pytest
from conftest import build_gamet


# ---------------------------------------------------------------------
# Parser — formatos de base de nuvem
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cld, fen, valor", [
    ("BKN 002HFT AGL",          "BASE_AGL", 200),
    ("BKN 002/010HFT AGL",      "BASE_AGL", 200),   # base/topo — ignorado até à v31
    ("OVC 004/XXXHFT AGL",      "BASE_AGL", 400),   # topo desconhecido — idem
    ("BKN 002-004/010HFT AGL",  "BASE_AGL", 200),
    ("BKN 003-008/XXXHFT AGL",  "BASE_AGL", 300),
    ("OVC SFC/010HFT AGL",      "BASE_AGL", 0),
    ("OVC 800/1100FT AGL",      "BASE_AGL", 800),   # pés, forma-modelo OACI
    ("ISOL TCU/CB 020HFT AGL",  "BASE_AGL", 2000),
    ("BKN 050HFT AMSL",         "BASE_AMSL", 5000),
    ("BKN 030/060HFT AMSL",     "BASE_AMSL", 3000),
    ("BKN 030-040/060HFT AMSL", "BASE_AMSL", 3000),
])
def test_formatos_de_base(eng, cld, fen, valor):
    blocks, *_ = eng.parse_gamet(build_gamet(f"SECN I SIG CLD: {cld}"))
    assert [(b.phenomenon, b.value) for b in blocks] == [(fen, valor)]


def test_base_topo_nunca_le_o_topo(eng):
    """O topo (segundo número) nunca pode ser lido como uma segunda base."""
    blocks, *_ = eng.parse_gamet(build_gamet(
        "SECN I SIG CLD: BKN 002-005/XXXHFT AGL SCT 010/020HFT AGL"))
    assert sorted(b.value for b in blocks) == [200, 1000]


def test_base_topo_baixa_da_nogo(analyse):
    r = analyse(build_gamet("SECN I SIG CLD: BKN 002/010HFT AGL"))
    assert r["decisions"] == ["NO-GO"]


# ---------------------------------------------------------------------
# Pertença das células por área (regressão do ponto representativo)
# ---------------------------------------------------------------------

def test_regressao_ponto_representativo(analyse):
    """
    REGRESSÃO (v31): representative_point() devolveu o vértice (-9, 38),
    fora de todos os fenómenos, e 12% da FIR saíram GO com TS EMBD e ICE
    SEV a cobrir a FIR inteira.
    """
    r = analyse(build_gamet(
        "SECN I SIGWX: EMBD TS ICE: N OF N3840 SEV FL050/FL120 "
        "ICE: SEV FL050/FL120 SIG CLD: S OF N3800 SCT 030HFT AGL"))
    assert set(r["decisions"]) == {"NO-GO"}


@pytest.mark.parametrize("extra", [
    "", "SIG CLD: S OF N3800 SCT 030HFT AGL", "ICE: N OF N3840 SEV FL050/FL120",
    "SFC VIS: BTN N3800 AND N3840 MAR 2000M BR", "TURB: E OF W00800 LAN MOD SFC/FL080",
    "SIG CLD: BKN 040HFT AMSL",
])
def test_fenomeno_global_nogo_em_todas_as_regioes(analyse, extra):
    """Um NO-GO que cobre a FIR inteira tem de chegar a todas as regiões."""
    r = analyse(build_gamet(f"SECN I SIGWX: EMBD TS {extra}"))
    assert set(r["decisions"]) == {"NO-GO"}


def _oraculo(eng, blocks, lon, lat):
    """Decisão calculada directamente sobre os fenómenos que contêm o ponto."""
    p = eng.Point(lon, lat)
    ev = []
    for b in blocks:
        if not b.polygon.buffer(0.01).contains(p):
            continue
        if not b.polygon.buffer(-0.01).contains(p):
            return None          # em cima de uma fronteira — não julgar
        if b.phenomenon == "BASE_AMSL":
            ev.append(("BASE", max(0, round(b.value - eng._terrain_elevation_ft(lon, lat))),
                       b.qualifier, b.layer))
        elif b.phenomenon == "BASE_AGL":
            ev.append(("BASE", b.value, b.qualifier, b.layer))
        else:
            ev.append((b.phenomenon, b.value, b.qualifier, b.layer))
    return eng.decision(ev)[0]


def _gamet_aleatorio(rng):
    lats = ["N3730", "N3800", "N3840", "N3900", "N3930", "N4000", "N4030", "N4100", "N4130"]
    lons = ["W00730", "W00800", "W00830", "W00900"]

    def geo():
        c = rng.random()
        if c < .35: return ""
        if c < .55: return f"N OF {rng.choice(lats)} "
        if c < .75: return f"S OF {rng.choice(lats)} "
        if c < .85: return f"E OF {rng.choice(lons)} "
        if c < .92: return f"W OF {rng.choice(lons)} "
        a, b = sorted(rng.sample(lats, 2))
        return f"BTN {a} AND {b} "

    def sup():
        return rng.choice(["", "", "", "MAR ", "LAN ", "COT ", "COT AND MAR "])

    campos = [
        lambda: f"SFC VIS: {geo()}{sup()}{rng.choice(['', 'LCA '])}{rng.choice([800, 1200, 2500, 6000])}M BR",
        lambda: f"SIG CLD: {geo()}{sup()}BKN {rng.choice(['002HFT AGL', '004/010HFT AGL', '030HFT AMSL', '045/070HFT AMSL'])}",
        lambda: f"SIGWX: {geo()}{sup()}{rng.choice(['ISOL', 'OCNL', 'EMBD'])} TS",
        lambda: f"TURB: {geo()}{sup()}{rng.choice(['MOD', 'SEV'])} SFC/FL080",
        lambda: f"ICE: {geo()}{rng.choice(['MOD', 'SEV'])} FL050/FL120",
    ]
    return build_gamet("SECN I " + " ".join(rng.choice(campos)() for _ in range(rng.randint(1, 5))))


def test_regioes_concordam_com_oraculo(eng, analyse):
    """
    Em 150 GAMETs aleatórios, a decisão da região que contém cada um dos
    52 aeródromos tem de ser igual à decisão calculada directamente sobre
    os fenómenos que contêm esse ponto. Foi este teste (em versão de 5000
    GAMETs) que expôs o erro do ponto representativo.
    """
    rng = random.Random(2026)
    erros = []
    for _ in range(150):
        t = _gamet_aleatorio(rng)
        r = analyse(t)
        for nome, (la, lo) in eng.AERODROMES.items():
            esperado = _oraculo(eng, r["blocks"], lo, la)
            if esperado is None:
                continue
            reg = eng.find_region_for_point(r["regions"], la, lo)
            if reg["decision"] != esperado:
                erros.append((nome, esperado, reg["decision"], t))
    assert not erros, erros[:3]


def test_refine_parte_celulas_parciais(eng):
    celula = eng.box(0, 0, 2, 1)
    partes = eng._refine_cells([celula], [eng.box(1, -1, 3, 2)])
    assert len(partes) == 2
    assert abs(sum(p.area for p in partes) - 2) < 1e-9


# ---------------------------------------------------------------------
# FIR com fronteira terrestre real
# ---------------------------------------------------------------------

def test_fir_poligono_unico_sem_buracos(eng):
    assert eng.FIR_POLYGON.geom_type == "Polygon"
    assert len(eng.FIR_POLYGON.interiors) == 0
    assert eng.FIR_POLYGON.is_valid


def test_todos_os_aerodromos_dentro_da_fir(eng):
    fora = [n for n, (la, lo) in eng.AERODROMES.items()
            if not eng.FIR_POLYGON.contains(eng.Point(lo, la))]
    assert not fora, f"fora da FIR: {fora}"


@pytest.mark.parametrize("nome, lat, lon, dentro", [
    ("Melgaço",          42.11, -8.26, True),    # fora até à v31 (26 km)
    ("Barrancos",        38.13, -6.98, True),    # fora até à v31 (25 km)
    ("Mogadouro (vila)", 41.34, -6.71, True),
    ("Ayamonte (ES)",    37.21, -7.40, False),   # dentro até à v31
    ("Badajoz (ES)",     38.88, -6.97, False),
    ("Tui (ES)",         42.05, -8.64, False),
])
def test_fronteira_terrestre(eng, nome, lat, lon, dentro):
    assert eng.FIR_POLYGON.contains(eng.Point(lon, lat)) == dentro, nome


def test_regiao_a_norte_de_42_e_coberta(analyse, eng):
    """N OF N4200 tem agora área real (Alto Minho, Montesinho)."""
    r = analyse(build_gamet("SECN I SFC VIS: N OF N4200 800M FG"))
    assert "NO-GO" in r["decisions"]


# ---------------------------------------------------------------------
# Relevo — conversão AMSL→AGL conservadora
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cume, lat, lon, ft", [
    ("Torre (Estrela)", 40.322, -7.613, 6539),
    ("Fóia (Monchique)", 37.315, -8.595, 2960),
    ("Larouco",          41.890, -7.715, 5036),
    ("Marão",            41.248, -7.885, 4642),
    ("Montejunto",       39.170, -9.050, 2185),
])
def test_grelha_nao_subestima_cumes(eng, cume, lat, lon, ft):
    assert eng._terrain_elevation_ft(lon, lat) >= ft, cume


def test_amsl_sobre_serra_e_conservador(analyse, eng):
    """
    REGRESSÃO (v31): BKN 050HFT AMSL dava GO em toda a FIR, incluindo a
    Serra da Estrela (~6500 ft), por usar a elevação de um único ponto
    baixo por zona.
    """
    r = analyse(build_gamet("SECN I SIG CLD: BKN 050HFT AMSL"))
    seia = eng.find_region_for_point(r["regions"], *eng.AERODROMES["Seia (LPSE)"])
    faro = eng.find_region_for_point(r["regions"], *eng.AERODROMES["Faro (LPFR)"])
    assert seia["decision"] == "NO-GO"
    # ...mas a Estrela não pode contaminar o Algarve
    assert faro["decision"] == "GO"


def test_amsl_nao_fragmenta_o_briefing(analyse):
    """Pior caso encontrado na revisão: 33 regiões antes da consolidação."""
    r = analyse(build_gamet(
        "SECN I SIG CLD: W OF W00730 OVC 022HFT AMSL SIGWX: W OF W00830 LAN ISOL TS "
        "ICE: 17/21 N OF N4030 COT AND MAR MOD FL050/FL120 TURB: S OF N3900 LAN MOD SFC/FL080"))
    assert len(r["regions"]) <= 12


def test_sem_amsl_grelha_nao_entra(analyse):
    """Sem bases AMSL, a grelha de relevo não pode partir as regiões."""
    r = analyse(build_gamet("SECN I SFC VIS: 800M FG"))
    assert len(r["regions"]) == 1


# ---------------------------------------------------------------------
# Janela horária
# ---------------------------------------------------------------------

def _dt(d, h, m=0):
    return datetime(2026, 10, d, h, m, tzinfo=timezone.utc)


@pytest.mark.parametrize("janela, inicio, agora, estado", [
    ("16–18Z", _dt(9, 15), _dt(9, 15, 30), "ainda não começou"),
    ("16–18Z", _dt(9, 15), _dt(9, 17),     "activo agora"),
    ("16–18Z", _dt(9, 15), _dt(9, 18),     "já terminou"),
    ("23–02Z", _dt(9, 21), _dt(10, 1),     "activo agora"),   # cruza meia-noite
    ("00–03Z", _dt(9, 21), _dt(9, 22),     "ainda não começou"),
    ("00–03Z", _dt(9, 21), _dt(10, 2),     "activo agora"),
    ("21–24Z", _dt(9, 21), _dt(9, 23, 59), "activo agora"),
    ("10–12Z", _dt(9, 12), _dt(9, 13, 39), "já terminou"),    # caso apanhado na UI
    ("16–18Z", None,       _dt(9, 17),     ""),
])
def test_estado_da_janela(eng, janela, inicio, agora, estado):
    assert eng.window_status(janela, inicio, agora) == estado


def test_janela_so_anota_nao_muda_decisao(analyse):
    r = analyse(build_gamet("SECN I SIGWX: 09/12 EMBD TS"))
    assert r["decisions"] == ["NO-GO"]


# ---------------------------------------------------------------------
# App completa (UI) — só corre se o Streamlit estiver instalado
# ---------------------------------------------------------------------

def test_app_completa_sem_excepcoes(app_path):
    """
    Corre a app de ponta a ponta, tal como o Streamlit. Foi assim que se
    apanhou um import em falta que os testes do motor não viam.
    """
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.run()
    at.text_area[0].set_value(build_gamet(
        "SECN I SFC VIS: 10/12 N OF N4030 LCA 1200M BR "
        "SIG CLD: BKN 045/080HFT AMSL N OF N4000 BKN 002/010HFT AGL "
        "SIGWX: S OF N3800 ISOL TS TURB: COT MOD SFC/FL050"))
    [b for b in at.button if "Analisar" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Briefing" in s.value for s in at.subheader)


def test_vertice_sul_coincide_com_enr21(eng):
    """eAIP ENR 2.1: '... along Portuguese/Spanish border - 3558N 00723W'."""
    pt = eng.Point(-(7 + 23 / 60), 35 + 58 / 60)
    assert eng.FIR_POLYGON.exterior.distance(pt) < 1e-4


# ---------------------------------------------------------------------
# Área do GAMET = sectores inferiores do ENR 2.1.3 (1.1)
# ---------------------------------------------------------------------

_VERTICES_OFICIAIS = [
    "415308N0085015W", "402358N0064906W", "392300N0080100W", "385400N0100000W",
    "392055N0094705W", "401159N0092633W", "402256N0092205W", "403856N0091505W",
    "404940N0091111W", "375957N0071223W", "380000N0090000W", "380000N0092800W",
    "380000N0100000W", "370730N0072318W", "364016N0072311W", "355800N0072300W",
    "355800N0104400W",
]


@pytest.mark.parametrize("ponto", _VERTICES_OFICIAIS)
def test_vertices_oficiais_na_fronteira_da_area(eng, ponto):
    """Todos os vértices dos sectores inferiores estão nos limites da área
    ou na divisória entre sectores."""
    p = eng.Point(*eng._dms(ponto))
    limites = [eng.FIR_POLYGON.exterior] + [s.exterior for s in eng.ZONES.values()]
    assert min(l.distance(p) for l in limites) < 1e-6, ponto


def test_vertices_dos_sectores_superiores_nao_sao_usados(eng):
    """REGRESSÃO (1.0): 415203N 0085037W e 403856N 0091500W são dos
    sectores superiores (FL245+), não da área do GAMET."""
    coords = set((round(x, 5), round(y, 5)) for x, y in eng.FIR_POLYGON.exterior.coords)
    for ponto in ("415203N0085037W", "403856N0091500W"):
        x, y = eng._dms(ponto)
        assert (round(x, 5), round(y, 5)) not in coords


def test_triangulo_sudoeste_incluido(eng):
    """REGRESSÃO (1.0): o limite 355800N 0104400W → 380000N 0092800W era
    simplificado e deixava de fora ~4500 km² de mar ao largo de Sines."""
    assert eng.FIR_POLYGON.contains(eng.Point(-9.98, 36.98))


@pytest.mark.parametrize("ancora", [
    "414909N0080902W", "414849N0080335W", "415145N0072708W", "412853N0061708W",
    "402358N0064906W", "390700N0070100W", "384917N0070505W", "381812N0071047W",
    "375957N0071223W", "375928N0071409W", "371016N0072340W", "372503N0072636W",
    "415308N0085015W", "370730N0072318W",
])
def test_fronteira_passa_pelas_ancoras_oficiais(eng, ancora):
    """Pontos onde o ENR 2.1 diz 'along Portuguese/Spanish border'."""
    assert eng.BORDER_LINE.distance(eng.Point(*eng._dms(ancora))) < 1e-9


def test_sectores_encaixam_sem_sobreposicao(eng):
    secs = list(eng.ZONES.values())
    soma = sum(s.area for s in secs)
    assert abs(soma - eng.FIR_POLYGON.area) < 1e-6
    for i in range(len(secs)):
        for j in range(i + 1, len(secs)):
            assert secs[i].intersection(secs[j]).area < 1e-9


# ---------------------------------------------------------------------
# Relevo — MEF do SkyDemon (1.2)
# ---------------------------------------------------------------------

@pytest.mark.parametrize("lat, lon, mef", [
    (40.32, -7.61, 6900),   # Estrela
    (41.89, -7.72, 5400),   # Larouco
    (41.25, -7.89, 5000),   # Marão
    (37.32, -8.60, 3300),   # Fóia
    (39.17, -9.05, 2500),   # Montejunto
    (38.79, -9.39, 2100),   # Sintra
    (40.07, -8.20, 4400),   # Lousã / Trevim
])
def test_mef_lidos(eng, lat, lon, mef):
    """Valores lidos das capturas do SkyDemon fornecidas pelo utilizador."""
    assert eng._terrain_elevation_ft(lon, lat) == mef


def test_quadriculas_de_1_grau_por_30_minutos(eng):
    assert (eng._TILE_LON, eng._TILE_LAT) == (1.0, 0.5)
    b = eng._tile_box(eng._tile_key(-7.61, 40.32))
    assert b.bounds == (-8.0, 40.0, -7.0, 40.5)


def test_todas_as_quadriculas_da_area_tem_mef(eng):
    em_falta = [k for k in eng._tiles_touching(eng.FIR_POLYGON)
                if k not in eng._TERRAIN_MAX_FT]
    assert not em_falta


def test_mef_celula_nao_herda_quadricula_vizinha(analyse, eng):
    """
    REGRESSÃO (1.2): com SCT 028HFT AMSL, Évora (MEF 2500 → base 300 ft,
    MARGINAL) saía NO-GO porque a sua célula tocava numa quadrícula vizinha
    com área ínfima, que o corte ignorava mas o cálculo do MEF contava.
    """
    r = analyse(build_gamet(
        "SECN I SIG CLD: SCT 028HFT AMSL SIGWX: BTN N3900 AND N4130 FRQ TS"))
    reg = eng.find_region_for_point(r["regions"], *eng.AERODROMES["Évora (LPEV)"])
    assert reg["decision"] == "MARGINAL"


def test_bolsas_separadas_mostram_os_seus_valores(analyse):
    """
    REGRESSÃO (1.0–1.2): bolsas separadas com as mesmas causas mostravam
    todas a base mais baixa do grupo — o norte aparecia com 100 ft quando o
    GAMET dizia 200 ft. Na v31 estava correcto.
    """
    r = analyse(build_gamet(
        "SECN I SIG CLD: N OF N4100 BKN 002HFT AGL SIG CLD: S OF N3800 BKN 001HFT AGL"))
    nogo = {round(reg["polygon"].representative_point().y): reg["base"]
            for reg in r["regions"] if reg["decision"] == "NO-GO"}
    norte = [b for lat, b in nogo.items() if lat >= 41]
    sul = [b for lat, b in nogo.items() if lat <= 38]
    assert norte == [200] and sul == [100]


def test_absorcao_fica_com_o_valor_mais_conservador(eng):
    alvo = {"vis": 1200, "base": 200, "ts": [], "turb": ["MOD"], "turb_layers": [],
            "ice": [], "ice_layers": [], "mt_obsc": [], "va": [],
            "reasons": ["BASE 200ft < 300ft"], "notas": []}
    peq = {"vis": None, "base": 100, "ts": [], "turb": [], "turb_layers": [],
           "ice": [], "ice_layers": [], "mt_obsc": [], "va": [],
           "reasons": ["BASE 100ft < 300ft"], "notas": []}
    eng._absorb_values(alvo, peq)
    assert alvo["base"] == 100 and alvo["vis"] == 1200
    assert alvo["reasons"] == ["BASE 100ft < 300ft"]
    assert alvo["turb_parcial"] is True
