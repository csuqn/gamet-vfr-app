"""
3.5 — Duas mudanças de regra aprovadas pelo Duarte (19-out-2026).

1. Cardinal solto antes de BTN. GAMET real 182100/190300:

       SFC VIS:23/03 S BTN N3720 - N3800 LAN LCA 0200-5000M FG/BR
       SIG CLD:23/03 S BTN N3720 - N3800 LAN LCA BKN 002-008/010HFT

   Até à 3.4 o "S" era ignorado em silêncio (a quebra injectada antes de
   "BTN N…" separava-o, e com ele a janela 23/03): a área era só a faixa
   BTN ∩ LAN e o NO-GO ficava em LP58 e LP78. Opção (b) do Duarte: um
   cardinal simples solto imediatamente antes de BTN dá a UNIÃO da faixa com
   o semiplano nessa direcção, a partir do limite mais extremo nessa direcção
   ("S BTN N3720 - N3800" → "S OF N3800"), com aviso. Cardinal e BTN de eixos
   diferentes ("E BTN N3720 - N3800") → toda a FIR + aviso, como a 3.4.
   A área nova contém sempre a antiga.

2. Coordenadas de SIGMET só com graus (Anexo 3: Nnn[nn] Wnnn[nn]). SIGMET
   real U02 de 18-out-2026 traz "N3347 W018": até à 3.4 a área era
   "ilegível" e o SIGMET (turbulência a ~700 km da costa) punha NO-GO em
   toda a FIR das 23:30 às 02:00Z.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import build_gamet

# ---------------------------------------------------------------------
# Boletins reais, integrais
# ---------------------------------------------------------------------

GAMET_182100 = (
    "LPPC GAMET VALID 182100/190300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:23/03 S BTN N3720 - N3800 LAN LCA 0200-5000M FG/BR SIG CLD:23/03 S BTN N3720 - "
    "N3800 LAN LCA BKN 002-008/010HFT TURB:N OF N4000 LCA MOD SFC/FL050 SIGMET APPLICABLE: AT "
    "TIME OF ISSUE NIL SECN II PSYS:00 N3400 W00830 L 1011HPA STNR NC CLD:FEW/SCT SC/CU "
    "012-025/040HFT AGL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 "
    "1000FT AGL 060/022KT PS05 080/022KT PS15 070/033KT PS09 2000FT AGL 070/030KT PS04 "
    "090/029KT PS12 090/028KT PS10 5000FT AGL 080/007KT PS04 050/012KT PS10 070/007KT PS07 "
    "FL100 340/007KT PS00 020/011KT PS02 020/013KT PS01 FL150 360/016KT MS09 010/024KT MS08 "
    "020/017KT MS09 FZLVL: 10500FT AMSL 10700FT AMSL 10200FT AMSL LISBOA EVORA FARO N3845 "
    "W00908 N3830 W00752 N3700 W00800 1000FT AGL 060/020KT PS17 080/019KT PS16 070/010KT PS17 "
    "2000FT AGL 080/022KT PS15 080/011KT PS15 100/010KT PS15 5000FT AGL 070/012KT PS10 "
    "040/004KT PS09 110/013KT PS10 FL100 060/012KT PS01 090/005KT PS00 090/008KT PS01 FL150 "
    "050/028KT MS09 060/015KT MS08 060/011KT MS10 FZLVL: 10500FT AMSL 10300FT AMSL 10500FT "
    "AMSL MNM QNH:1011HPA=")

SIGMET_U02 = (
    "LPPC SIGMET U02 VALID 182330/190200 LPPT- LPPC LISBOA FIR SEV TURB FCST WI N3140 W01527 "
    "- N3347 W018 - N3458 W01644 - N3237 W01425 - N3140 W01527 FL230/440 MOV SSE 25KT WKN")

SIGMET_U01 = (
    "LPPC SIGMET U01 VALID 182030/182330 LPPT- LPPC LISBOA FIR SEV TURB FCST WI N3324 W01656 "
    "- N3405 W01752 - N3414 W01746 - N3540 W01602 - N3507 W01510 - N3324 W01656 FL330/430 "
    "MOV SSE 25KT INTSF")

# SIGMETs reais de 17 e 18-out-2026 (todas as coordenadas com minutos)
SIGMETS_T = [
    "LPPC SIGMET T01 VALID 171010/171410 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4137 W00616 - "
    "N4157 W00634 - N4156 W00713 - N4152 W00746 - N4008 W00810 - N3947 W00658 - N4137 W00616 "
    "TOP FL360 STNR NC",
    "LPPC SIGMET T02 VALID 171400/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4150 W00745 - "
    "N3940 W00753 - N3940 W00653 - N4143 W00609 - N4150 W00745 TOP FL340 STNR WKN",
    "LPPC SIGMET T01 VALID 181325/181525 LPPT- LPPC LISBOA FIR EMBD TSGR OBS WI N3808 W00657 - "
    "N3826 W00719 - N3823 W00858 - N3658 W00908 - N3657 W00728 - N3808 W00657 TOP FL420 STNR NC",
    "LPPC SIGMET T02 VALID 181530/181730 LPPT- LPPC LISBOA FIR EMBD TSGR OBS WI N3656 W00728 - "
    "N3808 W00657 - N3828 W00719 - N3818 W00935 - N3655 W00929 - N3656 W00728 TOP FL400 STNR NC",
]

MEIA_NOITE = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)   # 23:30–02:00 do U02
ANTES_U02 = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)

ALGARVE = ("Faro (LPFR)", "Portimão (LPPM)", "Lagos (LP59)",
           "Herdade da Zambujeira (LP58)", "Alentejo Air Park (LP78)")


def _ad(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)["decision"]


def _base(blocks, valor):
    (b,) = [b for b in blocks if b.phenomenon == "BASE_AGL" and b.value == valor]
    return b


def _igual(a, b):
    return a.symmetric_difference(b).area < 1e-6


def _semiplano(eng, x0=None, y0=None, x1=None, y1=None):
    return eng._clean_poly(eng.FIR_POLYGON.intersection(eng.box(
        eng.FIR_MINX if x0 is None else x0, eng.FIR_MINY if y0 is None else y0,
        eng.FIR_MAXX if x1 is None else x1, eng.FIR_MAXY if y1 is None else y1)))


# ---------------------------------------------------------------------
# 1. GAMET real 182100: "S BTN N3720 - N3800"
# ---------------------------------------------------------------------

def test_182100_algarve_no_go(eng):
    r = eng.analisar_gamet(GAMET_182100, "ipma", boletins=[], boletins_at=MEIA_NOITE,
                           agora=MEIA_NOITE)
    for nome in ALGARVE:
        assert _ad(eng, r["regioes"], nome) == "NO-GO", nome
    # A N de N3800 o nevoeiro não se aplica
    for nome in ("Lisboa (LPPT)", "Évora (LPEV)", "Porto (LPPR)"):
        assert _ad(eng, r["regioes"], nome) != "NO-GO", nome


def test_182100_area_e_s_of_n3800_em_terra_com_janela(eng):
    blocks = eng.parse_gamet(GAMET_182100)[0]
    esperado = eng._clean_poly(_semiplano(eng, y1=38.0).intersection(eng.surface_polygon("LAN")))
    b = _base(blocks, 200)
    assert _igual(b.polygon, esperado)
    assert b.window == "23–03Z"
    (v,) = [x for x in blocks if x.phenomenon == "VIS"]
    assert _igual(v.polygon, esperado)
    assert v.window == "23–03Z"


def test_182100_aviso_visivel(eng):
    r = eng.analisar_gamet(GAMET_182100, "ipma", boletins=[], boletins_at=MEIA_NOITE,
                           agora=MEIA_NOITE)
    avisos = [t for tipo, t in r["avisos"] if tipo == "aviso" and "cardinal solto" in t]
    assert len(avisos) == 2, r["avisos"]
    assert all("S OF N3800" in a and "S BTN N3720 - N3800" in a for a in avisos)
    assert not [t for _, t in r["avisos"] if "Área não reconhecida" in t]


def test_182100_subentradas_alargadas(eng):
    s = eng.subentradas_alargadas(GAMET_182100)
    assert [x[1] for x in s] == ["S OF N3800", "S OF N3800"]
    assert s[0][0].startswith("SFC VIS") and "S BTN N3720 - N3800" in s[0][0]
    assert s[1][0].startswith("SIG CLD")
    assert eng.subentradas_sem_area(GAMET_182100) == []


def test_analisar_py_assinala_e_hifen_no_vocabulario(eng):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analisar
    r = analisar.analisar(eng, GAMET_182100)
    alargadas = [a for a in r["alertas"] if a.startswith("Cardinal solto antes de BTN")]
    assert len(alargadas) == 2, r["alertas"]
    assert all("S OF N3800" in a for a in alargadas)
    assert not [a for a in r["alertas"] if a.startswith("Palavras desconhecidas")], r["alertas"]


# ---------------------------------------------------------------------
# Outras direcções e eixos
# ---------------------------------------------------------------------

@pytest.mark.parametrize("area, leitura, limites", [
    ("S BTN N3720 - N3800", "S OF N3800", dict(y1=38.0)),
    ("S BTN N3800 AND N3720", "S OF N3800", dict(y1=38.0)),
    ("N BTN N3720 - N3800", "N OF N3720", dict(y0=37 + 20 / 60)),
    ("N BTN N4000 AND N3840", "N OF N3840", dict(y0=38 + 40 / 60)),
    ("E BTN W00800 - W00700", "E OF W00800", dict(x0=-8.0)),
    ("W BTN W00800 - W00700", "W OF W00700", dict(x1=-7.0)),
    ("W BTN W00700 AND W00830", "W OF W00700", dict(x1=-7.0)),
])
def test_cardinal_solto_direccoes(eng, analyse, area, leitura, limites):
    texto = build_gamet(f"SECN I SIG CLD:{area} LCA BKN 002HFT AGL")
    b = _base(analyse(texto)["blocks"], 200)
    assert _igual(b.polygon, _semiplano(eng, **limites)), area
    assert [x[1] for x in eng.subentradas_alargadas(texto)] == [leitura]
    assert eng.subentradas_sem_area(texto) == []


@pytest.mark.parametrize("area", [
    "E BTN N3720 - N3800", "W BTN N3720 - N3800",
    "N BTN W00800 - W00700", "S BTN W00800 AND W00700",
])
def test_eixo_trocado_toda_a_fir_com_aviso(eng, analyse, area):
    # Só se injecta quebra antes de "BTN N…" (não se injectam quebras novas);
    # para o BTN em longitudes usa-se a quebra do próprio texto.
    sep = " " if " BTN N" in area else "\n"
    texto = build_gamet(f"SECN I SIG CLD:S OF N4100 LCA BKN 010HFT AGL{sep}{area} LCA BKN 002HFT AGL")
    r = analyse(texto)
    assert _igual(_base(r["blocks"], 200).polygon, eng.FIR_POLYGON), area
    # A subentrada anterior não é afectada
    assert _base(r["blocks"], 1000).polygon.bounds[3] <= 41 + 1e-6
    (s,) = eng.subentradas_sem_area(texto)
    assert area in s
    assert eng.subentradas_alargadas(texto) == []
    for nome in ("Porto (LPPR)", "Lisboa (LPPT)", "Bragança (LPBG)", "Faro (LPFR)"):
        assert _ad(eng, r["regions"], nome) == "NO-GO", (area, nome)
    av = [t for _, t in eng.analisar_gamet(texto, "manual")["avisos"]
          if "Área não reconhecida" in t]
    assert len(av) == 1


def test_eixo_trocado_no_inicio_do_campo(eng, analyse):
    texto = build_gamet("SECN I SIG CLD:E BTN N3720 - N3800 LAN LCA BKN 002HFT AGL")
    b = _base(analyse(texto)["blocks"], 200)
    esperado = eng._clean_poly(eng.FIR_POLYGON.intersection(eng.surface_polygon("LAN")))
    assert _igual(b.polygon, esperado)
    assert len(eng.subentradas_sem_area(texto)) == 1


def test_cardinal_solto_com_outro_qualificador_na_linha(eng, analyse):
    """Intersecção com os outros qualificadores da linha mantém-se."""
    texto = build_gamet("SECN I SIG CLD:S BTN N3720 - N3800 AND W OF W00800 LCA BKN 002HFT AGL")
    b = _base(analyse(texto)["blocks"], 200)
    assert _igual(b.polygon, _semiplano(eng, x1=-8.0, y1=38.0))


def test_sem_cardinal_e_cardinal_com_of_nao_mudam(eng, analyse):
    for corpo, limites in [
        ("SIG CLD:BTN N3720 - N3800 LCA BKN 002HFT AGL", dict(y0=37 + 20 / 60, y1=38.0)),
        ("SIG CLD:S OF N3800 LCA BKN 002HFT AGL", dict(y1=38.0)),
    ]:
        texto = build_gamet("SECN I " + corpo)
        assert _igual(_base(analyse(texto)["blocks"], 200).polygon, _semiplano(eng, **limites))
        assert eng.subentradas_alargadas(texto) == []


def test_diagonal_continua_toda_a_fir(eng, analyse):
    texto = build_gamet("SECN I SIG CLD:SW OF W00800 LCA BKN 002HFT AGL")
    assert _igual(_base(analyse(texto)["blocks"], 200).polygon, eng.FIR_POLYGON)
    assert len(eng.subentradas_sem_area(texto)) == 1


def test_qualificador_antes_do_cardinal_nao_se_junta(eng, analyse):
    """
    Revisão do d043ce1: "SW OF W00800 S BTN …" (e "E OF W00800 [AND] S BTN …")
    não se juntam numa só área — a 3.4 partia a linha antes do BTN e o
    fenómeno ficava em toda a faixa. A quebra vai para antes do cardinal: o
    fenómeno fica em S OF N3800 (contém a faixa), com aviso; a diagonal,
    sozinha na sua linha, continua a dar o aviso de área não reconhecida.
    """
    texto = build_gamet("SECN I SIG CLD:SW OF W00800 S BTN N3720 - N3800 LCA BKN 002HFT AGL")
    assert _igual(_base(analyse(texto)["blocks"], 200).polygon, _semiplano(eng, y1=38.0))
    assert len(eng.subentradas_sem_area(texto)) == 1
    assert [x[1] for x in eng.subentradas_alargadas(texto)] == ["S OF N3800"]
    for pre in ("E OF W00800 ", "E OF W00800 AND ", "W OF W00800 ", "BTN W00800 - W00700 "):
        texto = build_gamet(f"SECN I SIGWX:{pre}S BTN N3720 - N3800 OCNL TS")
        (b,) = analyse(texto)["blocks"]
        assert _igual(b.polygon, _semiplano(eng, y1=38.0)), pre


def test_mesma_linha_nunca_menor_que_a_leitura_antiga(eng, analyse):
    """
    BTN em longitudes não leva quebra: "E OF W00750 E BTN W00900 - W00800"
    fica numa linha. Na 3.4: E OF W00750 ∩ faixa = vazio → união (inclui a
    faixa). A leitura nova sozinha (E OF W00750 ∩ E OF W00900) perdia a
    faixa; a 3.5 une-a com a leitura da 3.4.
    """
    texto = build_gamet("SECN I SIGWX:E OF W00750 E BTN W00900 - W00800 OCNL TS")
    (b,) = analyse(texto)["blocks"]
    faixa = _semiplano(eng, x0=-9.0, x1=-8.0)
    assert faixa.difference(b.polygon).area < 1e-9


_CASOS_CONTEM = [f"{c} BTN {a} {sep} {b}"
                 for c in "NSEW"
                 for a, b in (("N3720", "N3800"), ("N4100", "N3840"),
                              ("W00800", "W00700"), ("W00630", "W00900"))
                 for sep in ("-", "AND")]


@pytest.mark.parametrize("area", _CASOS_CONTEM)
@pytest.mark.parametrize("sufixo", ["", " LAN", " MAR AND COT"])
def test_area_nova_contem_sempre_a_antiga(eng, analyse, area, sufixo):
    """
    Nunca mais permissivo do que a 3.4: a 3.4 separava o cardinal e ficava
    só com a faixa BTN (o mesmo texto sem o cardinal).
    """
    novo = analyse(build_gamet(f"SECN I SIG CLD:{area}{sufixo} LCA BKN 002HFT AGL"))
    antigo = analyse(build_gamet(f"SECN I SIG CLD:{area[2:]}{sufixo} LCA BKN 002HFT AGL"))
    pn = _base(novo["blocks"], 200).polygon
    pa = _base(antigo["blocks"], 200).polygon
    assert pa.difference(pn).area < 1e-9, area
    if not sufixo:
        assert pn.area > pa.area, area


def test_gamets_variados_inclui_o_182100():
    from test_geometry import GAMETS_VARIADOS
    assert any("S BTN N3720 - N3800" in g for g in GAMETS_VARIADOS)


# ---------------------------------------------------------------------
# 2. Coordenadas de SIGMET só com graus
# ---------------------------------------------------------------------

def test_coord_re_aceita_graus_sem_minutos(eng):
    assert eng._coord(eng._COORD_RE.search("N3347 W018").groups()) == (-18.0, 33 + 47 / 60)
    assert eng._coord(eng._COORD_RE.search("N39 W007").groups()) == (-7.0, 39.0)
    assert eng._coord(eng._COORD_RE.search("N39 W00730").groups()) == (-7.5, 39.0)
    assert eng._coord(eng._COORD_RE.search("S12 E015").groups()) == (15.0, -12.0)


@pytest.mark.parametrize("mal", ["N39 W07", "N390 W00700", "N3900 W0070", "N3900 W0070000",
                                 "N3 W007", "N39W", "N39 X007", "N39 W007X"])
def test_coordenadas_mal_formadas_continuam_toda_a_area(eng, mal):
    s = (f"LPPC SIGMET 7 VALID 171400/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N3900 W00800 "
         f"- {mal} - N4000 W00700 - N4000 W00800 TOP FL300 STNR NC")
    geom, _ = eng.area_sigmet(s)
    assert geom is None, mal


def test_u02_real_area_legivel_fora_da_area_do_gamet(eng):
    geom, desc = eng.area_sigmet(SIGMET_U02, ref=MEIA_NOITE)
    assert geom is not None, desc
    assert geom.is_empty
    assert "toda a área" not in desc


def test_u02_real_vertice_so_com_graus(eng):
    (seg,) = re.findall(r"WI (.*?) FL230", SIGMET_U02)
    pol = eng._area_wi(seg)
    assert pol is not None
    xs = {round(x, 6) for x, _ in pol.exterior.coords}
    assert -18.0 in xs


def test_u02_real_nao_muda_a_decisao_do_gamet(eng):
    sem = eng.analisar_gamet(GAMET_182100, "ipma", boletins=[], boletins_at=MEIA_NOITE,
                             agora=MEIA_NOITE)
    com = eng.analisar_gamet(GAMET_182100, "ipma", boletins=[SIGMET_U02],
                             boletins_at=MEIA_NOITE, agora=MEIA_NOITE)
    for nome in eng.AERODROMES:
        assert _ad(eng, com["regioes"], nome) == _ad(eng, sem["regioes"], nome), nome
    assert _ad(eng, com["regioes"], "Lisboa (LPPT)") != "NO-GO"


def test_u01_real_inalterado(eng):
    geom, desc = eng.area_sigmet(SIGMET_U01, ref=ANTES_U02)
    assert geom is not None and geom.is_empty
    (seg,) = re.findall(r"WI (.*?) FL330", SIGMET_U01)
    pts = [(-(16 + 56 / 60), 33 + 24 / 60), (-(17 + 52 / 60), 34 + 5 / 60),
           (-(17 + 46 / 60), 34 + 14 / 60), (-(16 + 2 / 60), 35 + 40 / 60),
           (-(15 + 10 / 60), 35 + 7 / 60)]
    assert _igual(eng._area_wi(seg), eng.Polygon(pts))


_COORD_ANTIGO = re.compile(r"([NS])(\d{2})(\d{2})\s*([EW])(\d{3})(\d{2})")


@pytest.mark.parametrize("sig", SIGMETS_T + [SIGMET_U01])
def test_sigmets_com_minutos_lidos_como_antes(eng, sig):
    def antigo(c):
        lat = int(c[1]) + int(c[2]) / 60
        lon = int(c[4]) + int(c[5]) / 60
        return (-lon if c[3] == "W" else lon, -lat if c[0] == "S" else lat)
    assert ([eng._coord(c) for c in eng._COORD_RE.findall(sig)]
            == [antigo(c) for c in _COORD_ANTIGO.findall(sig)])


def test_circulo_so_com_graus(eng):
    s = ("LPPC SIGMET 7 VALID 171400/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST WI 20NM OF "
         "N39 W009 TOP FL300 STNR NC")
    geom, desc = eng.area_sigmet(s)
    assert geom is not None, desc
    assert geom.contains(eng.Point(-9.0, 39.0)) or eng.Point(-9.0, 39.0).distance(geom) < 1e-6
    assert not geom.contains(eng.Point(-8.0, 39.0))
