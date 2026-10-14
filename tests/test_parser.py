"""
Testes do parser meteorológico — VIS, base de nuvens, trovoadas, TURB/ICE,
MT OBSC e VA.

Cada teste declara a expectativa a partir do SIGNIFICADO do GAMET, não do
que o parser devolve. Se um teste falhar, é o código que está errado (ou a
expectativa foi mal escrita) — nunca se ajusta o teste ao output.
"""
import pytest
from conftest import build_gamet


# ── VISIBILIDADE ─────────────────────────────────────────────────────
@pytest.mark.parametrize("metros,decisao", [
    (100, "NO-GO"), (500, "NO-GO"), (999, "NO-GO"), (1499, "NO-GO"),
    (1500, "MARGINAL"), (2000, "MARGINAL"), (2999, "MARGINAL"),
    (3000, "GO"), (5000, "GO"), (9999, "GO"),
])
def test_vis_limiares(analyse, metros, decisao):
    """Limiares VFR: <1500m NO-GO, <3000m MARGINAL, >=3000m GO."""
    r = analyse(build_gamet(f"SECN I SFC VIS: {metros}M"))
    assert metros in r["vis"]
    assert r["decisions"] == [decisao]


@pytest.mark.parametrize("texto,esperado", [
    ("0.5KM", 500), ("1.5KM", 1500), ("2.5KM", 2500), ("5KM", 5000),
])
def test_vis_em_km(analyse, texto, esperado):
    r = analyse(build_gamet(f"SECN I SFC VIS: {texto}"))
    assert esperado in r["vis"]


@pytest.mark.parametrize("texto,esperado", [
    ("BLW 1000M FG", 999),    # abaixo de X → X-1 (conservador)
    ("BLW 3000M BR", 2999),
    ("ABV 5000M", 5001),      # acima de X → X+1
])
def test_vis_blw_abv(analyse, texto, esperado):
    r = analyse(build_gamet(f"SECN I SFC VIS: {texto}"))
    assert esperado in r["vis"]


@pytest.mark.parametrize("texto,esperado", [
    ("2000-5000M BR", 2000),
    ("5000-2000M", 2000),     # intervalo invertido → mínimo na mesma
])
def test_vis_intervalo_usa_minimo(analyse, texto, esperado):
    r = analyse(build_gamet(f"SECN I SFC VIS: {texto}"))
    assert esperado in r["vis"]


def test_vis_abv_nao_suprime_intervalo(analyse):
    """
    REGRESSÃO (v25): o ramo ABV descartava o intervalo na mesma linha,
    reportando 8001m (bom) e escondendo 2000m (mau) — erro optimista.
    """
    r = analyse(build_gamet("SECN I SFC VIS: LCA 2000-5000M RA ABV 8000M"))
    assert 2000 in r["vis"], "valor conservador foi perdido"
    assert 8001 in r["vis"]
    assert r["decisions"] == ["MARGINAL"]


def test_vis_ignora_fl_e_hpa(analyse):
    """FL050 e 1013HPA não podem ser lidos como metros de visibilidade."""
    r = analyse(build_gamet("SECN I SFC VIS: 5000M TURB: MOD SFC/FL050"))
    assert r["vis"] == [5000]


# ── BASE DE NUVENS ───────────────────────────────────────────────────
@pytest.mark.parametrize("hft,decisao", [
    (1, "NO-GO"), (2, "NO-GO"),        # <300ft
    (3, "MARGINAL"), (4, "MARGINAL"),  # <500ft
    (5, "GO"), (10, "GO"), (30, "GO"),
])
def test_base_limiares(analyse, hft, decisao):
    r = analyse(build_gamet(f"SECN I SIG CLD: BKN {hft:03d}-{hft+10:03d}/XXXHFT AGL"))
    assert hft * 100 in r["base"]
    assert r["decisions"] == [decisao]


def test_base_topo_numerico_nao_e_base(analyse):
    """Em '002-004/010HFT AGL' a base é 200ft; 010 é o topo, não outra base."""
    r = analyse(build_gamet("SECN I SIG CLD: BKN 002-004/010HFT AGL"))
    assert r["base"] == [200]
    assert 1000 not in r["base"]


def test_base_tcu_cb_nao_confunde_barra(analyse):
    """REGRESSÃO: a '/' de TCU/CB era lida como separador de intervalo."""
    r = analyse(build_gamet("SECN I SIG CLD: ISOL TCU/CB 020HFT AGL"))
    assert r["base"] == [2000]


def test_base_amsl_nao_e_agl(analyse):
    r = analyse(build_gamet("SECN I SIG CLD: BKN 050HFT AMSL"))
    assert r["base"] == []


@pytest.mark.parametrize("corpo", [
    "SECN I SIG CLD: NIL",
    "SECN I SIG CLD: BKN AS/AC",
])
def test_base_ausente(analyse, corpo):
    r = analyse(build_gamet(corpo))
    assert r["base"] == []
    assert r["decisions"] == ["GO"]


# ── TROVOADAS ────────────────────────────────────────────────────────
@pytest.mark.parametrize("qualificador,valor,decisao", [
    ("ISOL", "ISOL", "MARGINAL"),
    ("OCNL", "OCNL", "NO-GO"),
    ("FRQ", "FRQ", "NO-GO"),
    ("EMBD", "EMBD", "NO-GO"),
    ("ISOL/EMBD", "ISOL_EMBD", "NO-GO"),
    ("FRQ/EMBD", "FRQ", "NO-GO"),
    ("OCNL/EMBD", "OCNL", "NO-GO"),
    ("GEN", "GEN", "NO-GO"),
])
def test_ts_qualificadores(analyse, qualificador, valor, decisao):
    r = analyse(build_gamet(f"SECN I SIGWX: {qualificador} TS"))
    assert valor in r["ts"]
    assert r["decisions"] == [decisao]


def test_cb_sem_qualificador_e_generico(analyse):
    r = analyse(build_gamet("SECN I SIGWX: CB"))
    assert "GEN" in r["ts"]
    assert r["decisions"] == ["NO-GO"]


def test_ts_nil(analyse):
    r = analyse(build_gamet("SECN I SIGWX: NIL"))
    assert r["ts"] == set()
    assert r["decisions"] == ["GO"]


def test_cb_em_sig_cld_nao_cria_ts(analyse):
    """TCU/CB numa linha de nuvens descreve o tipo, não uma trovoada."""
    r = analyse(build_gamet("SECN I SIG CLD: ISOL TCU/CB 020-030/XXXHFT AGL"))
    assert r["ts"] == set()


# ── TURBULÊNCIA E GELO ───────────────────────────────────────────────
@pytest.mark.parametrize("severidade,valor,decisao", [
    ("MOD", "MOD", "GO"),        # moderado é informativo
    ("SEV", "SEV", "NO-GO"),     # severo é crítico p/ ultraleves
    ("HVY", "SEV", "NO-GO"),     # HVY equivale a SEV
    ("MOD/SEV", "SEV", "NO-GO"),
    ("MOD/HVY", "SEV", "NO-GO"),
])
def test_turb_severidade(analyse, severidade, valor, decisao):
    r = analyse(build_gamet(f"SECN I TURB: {severidade} SFC/FL050"))
    assert valor in r["turb"]
    assert r["decisions"] == [decisao]


@pytest.mark.parametrize("severidade,valor,decisao", [
    ("MOD", "MOD", "GO"),
    ("SEV", "SEV", "NO-GO"),
    ("HVY", "SEV", "NO-GO"),
])
def test_ice_severidade(analyse, severidade, valor, decisao):
    r = analyse(build_gamet(f"SECN I ICE: {severidade} ABV FL070"))
    assert valor in r["ice"]
    assert r["decisions"] == [decisao]


@pytest.mark.parametrize("campo,camada", [
    ("TURB", "SFC/FL050"), ("TURB", "FL050/FL100"),
    ("TURB", "ABV FL050"), ("TURB", "BLW FL100"),
    ("ICE", "ABV FL070"), ("ICE", "BLW FL080"), ("ICE", "FL050/FL100"),
])
def test_camadas_verticais(analyse, campo, camada):
    r = analyse(build_gamet(f"SECN I {campo}: MOD {camada}"))
    assert camada in r["layers"]


# ── MT OBSC E CINZAS VULCÂNICAS ──────────────────────────────────────
def test_mt_obsc_sem_geo_cobre_tudo(analyse):
    r = analyse(build_gamet("SECN I MT OBSC"))
    assert r["mt_obsc"]
    assert r["decisions"] == ["NO-GO"]


def test_va_sem_geo_cobre_tudo(analyse):
    r = analyse(build_gamet("SECN I VA: FIR"))
    assert r["va"]
    assert r["decisions"] == ["NO-GO"]


@pytest.mark.parametrize("geo", ["N OF N3900", "S OF N4030", "BTN N3700 AND N4000"])
def test_mt_obsc_com_geo_e_local(analyse, geo):
    """Com geografia restrita, só a área coberta fica NO-GO."""
    r = analyse(build_gamet(f"SECN I MT OBSC {geo}"))
    assert r["mt_obsc"]
    assert "NO-GO" in r["decisions"]


def test_mt_obsc_nao_duplica(analyse):
    """REGRESSÃO: a linha de geografia seguinte duplicava a entrada."""
    r = analyse(build_gamet("SECN I MT OBSC S OF N3900"))
    n = sum(1 for b in r["blocks"] if b.phenomenon == "MT_OBSC")
    assert n == 1


# ── QUALIFICADORES DE SUPERFÍCIE E TEMPO (v30) ───────────────────────
@pytest.mark.parametrize("qualificador,esperado", [
    ("MAR", "MAR"), ("LAN", "LAN"), ("COT", "COT"),
    ("COT AND MAR", "COT/MAR"), ("MAR AND COT", "COT/MAR"),
])
def test_qualificador_de_superficie(analyse, qualificador, esperado):
    """
    MAR/LAN/COT indicam que o fenómeno só afecta o mar, terra ou a faixa
    costeira. A geometria não é recortada (não temos linha de costa), mas
    a informação tem de chegar ao briefing.
    """
    r = analyse(build_gamet(f"SECN I TURB: S OF N3900 {qualificador} MOD SFC/FL050"))
    turb = [b for b in r["blocks"] if b.phenomenon == "TURB"]
    assert turb and turb[0].surface == esperado


def test_superficie_aparece_nas_notas(analyse):
    r = analyse(build_gamet("SECN I TURB: S OF N3900 MAR MOD SFC/FL050"))
    com_nota = [reg for reg in r["regions"] if reg["notas"]]
    assert com_nota, "nota de superfície não chegou à região"
    assert any("mar" in n.lower() for reg in com_nota for n in reg["notas"])


def test_sem_qualificador_nao_gera_nota(analyse):
    r = analyse(build_gamet("SECN I TURB: S OF N3900 MOD SFC/FL050"))
    for reg in r["regions"]:
        assert not reg["notas"], f"nota inesperada: {reg['notas']}"


@pytest.mark.parametrize("campo,janela", [
    ("TURB:11/15 S OF N3840 MOD SFC/FL020", "11–15Z"),
    ("SIGWX:09/12 N OF N3900 OCNL TS", "09–12Z"),
    ("SIG VIS:15/18 N OF N4030 LCA 2000-5000M BR", "15–18Z"),
])
def test_janela_temporal(analyse, campo, janela):
    """
    Um fenómeno pode aplicar-se só a parte do período do GAMET. A janela
    é declarada no início do campo e vale para as linhas seguintes.
    """
    r = analyse(build_gamet(f"SECN I {campo}"))
    com_janela = [b for b in r["blocks"] if b.window]
    assert com_janela, "janela temporal não capturada"
    assert com_janela[0].window == janela


def test_janela_persiste_apos_quebra_geografica(analyse):
    """
    REGRESSÃO (v30): a injecção de quebra separava 'TURB:11/15' da linha
    com o conteúdo, e a janela perdia-se antes de o bloco ser criado.
    """
    r = analyse(build_gamet("SECN I TURB:11/15 S OF N3840 MAR LCA MOD SFC/FL020"))
    turb = [b for b in r["blocks"] if b.phenomenon == "TURB"]
    assert turb and turb[0].window == "11–15Z"
    assert turb[0].surface == "MAR"


def test_janela_nao_confunde_com_altitudes(analyse):
    """'015-030/XXXHFT' e 'SFC/FL050' não são janelas temporais."""
    r = analyse(build_gamet("SECN I SIG CLD: ISOL TCU/CB 015-030/XXXHFT AGL"))
    for b in r["blocks"]:
        assert not b.window, f"janela falsa: {b.window}"
