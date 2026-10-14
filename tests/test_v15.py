"""
1.5 — qualificadores geográficos ligados por AND ("N OF N3840 AND W OF
W00815") definem uma única área (intersecção).

Até à 1.4 o parser partia a linha antes do segundo qualificador e este
substituía o primeiro: no GAMET real de 14-out-2026 (21-03Z) o nevoeiro e
as nuvens a 200 ft "N OF N3840 AND W OF W00815" passavam a cobrir todo o
W de W00815 — Portimão e Lagos apareciam NO-GO.
"""
from shapely.geometry import box

GAMET_REAL_20261014 = (
    "LPPC GAMET VALID 142100/150300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
    "SECN I SFC VIS:N OF N3840 AND W OF W00815 LAN AND COT LCA 0200-5000M FG/BR "
    "SIG CLD:N OF N3840 AND W OF W00815 LAN AND COT LCA BKN 002-008/010HFT AGL "
    "TURB:S OF N3700 LCA MOD SFC/FL040 SIGMET APPLICABLE: AT TIME OF ISSUE NIL "
    "SECN II PSYS:00 N4100 W01300 H 1025HPA STNR NC "
    "CLD:N OF N3800 LAN AND COT SCT/BKN SC/CU 012-025/040HFT AGL "
    "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 "
    "1000FT AGL 250/003KT PS20 150/001KT PS21 360/001KT PS22 "
    "FZLVL: 12600FT AMSL 12300FT AMSL 12400FT AMSL MNM QNH:1022HPA="
)

LAT_N3840 = 38 + 40 / 60
LON_W00815 = -(8 + 15 / 60)


def _decisao(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)["decision"]


def test_and_entre_qualificadores_e_interseccao(analyse, eng):
    """REGRESSÃO (1.4): o 'N OF N3840' era descartado."""
    r = analyse(GAMET_REAL_20261014)
    for b in r["blocks"]:
        if b.phenomenon in ("VIS", "BASE_AGL"):
            minx, miny, maxx, maxy = b.polygon.bounds
            assert miny >= LAT_N3840 - 1e-6, f"{b.phenomenon} a sul de N3840"
            assert maxx <= LON_W00815 + 1e-6, f"{b.phenomenon} a leste de W00815"


def test_gamet_real_decisoes(analyse, eng):
    r = analyse(GAMET_REAL_20261014)
    # Dentro da área (N de N3840, W de W00815, terra/costa): base 200 ft
    for ad in ("Porto (LPPR)", "Coimbra (LPCO)", "Lisboa (LPPT)", "Braga (LPBR)"):
        assert _decisao(eng, r["regions"], ad) == "NO-GO", ad
    # Fora da área: Algarve (só TURB MOD, informativo) e interior
    for ad in ("Portimão (LPPM)", "Lagos (LP59)", "Évora (LPEV)"):
        assert _decisao(eng, r["regions"], ad) == "GO", ad


def test_and_igual_a_interseccao_directa(analyse, eng):
    """A área do bloco é a mesma que N OF ∩ W OF ∩ (terra+costa)."""
    r = analyse(GAMET_REAL_20261014)
    vis = next(b for b in r["blocks"] if b.phenomenon == "VIS")
    esperado = (eng.FIR_POLYGON
                .intersection(box(-20, LAT_N3840, 0, 50))
                .intersection(box(-20, 30, LON_W00815, 50))
                .intersection(eng.surface_polygon("COT/LAN")))
    assert vis.polygon.symmetric_difference(esperado).area < 1e-6


def test_and_continua_a_partir_campos_com_conteudo(analyse):
    """A quebra antes de um qualificador que segue conteúdo meteorológico
    mantém-se: duas bolsas com valores diferentes."""
    r = analyse("LPPC GAMET VALID 141500/142100 LPPT- SECN I "
                "SIG CLD:N OF N4030 BKN 002HFT AGL S OF N3845 BKN 008HFT AGL "
                "SIGMET APPLICABLE: NIL=")
    assert r["base"] == [200, 800]


def test_and_contraditorio_nao_faz_desaparecer_o_fenomeno(analyse):
    """'N OF N4000 AND S OF N3800' daria área vazia; a leitura
    conservadora é a união — nunca um fenómeno a desaparecer em silêncio."""
    r = analyse("LPPC GAMET VALID 141500/142100 LPPT- SECN I "
                "SFC VIS:N OF N4000 AND S OF N3800 0800M FG "
                "SIGMET APPLICABLE: NIL=")
    assert r["vis"] == [800]
    assert "NO-GO" in r["decisions"]
