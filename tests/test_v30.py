"""
3.0 — O SIGMET vale na sua área, não na FIR toda (decisão do Duarte,
17-out-2026): NO-GO dentro da área do SIGMET + 10 NM de margem, estendida na
direcção do movimento (MOV) durante a validade. Na dúvida — área ilegível,
ENTIRE FIR, só o identificador no GAMET — continua NO-GO em toda a área.
"""
from datetime import datetime, timezone

from conftest import build_gamet

AGORA = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
CALMO = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100")
T02 = ("LPPC SIGMET T02 VALID 171400/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4150 W00745 "
       "- N3940 W00753 - N3940 W00653 - N4143 W00609 - N4150 W00745 TOP FL340 STNR WKN")


def _s(corpo, sid="7", val="171400/171800"):
    return f"LPPC SIGMET {sid} VALID {val} LPPT- LPPC LISBOA FIR {corpo}"


def _r(eng, sigs, gamet=CALMO, fonte="ipma"):
    return eng.analisar_gamet(gamet, fonte, boletins=sigs, boletins_at=AGORA, agora=AGORA)


def _dec(eng, r, lat, lon):
    reg = eng.find_region_for_point(r["regioes"], lat, lon)
    return reg["decision"] if reg else None


def _ad(eng, r, nome):
    return _dec(eng, r, *eng.AERODROMES[nome])


def test_t02_real_so_no_interior_norte_e_centro(eng):
    r = _r(eng, [T02])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Mirandela (LPMI)") == "NO-GO"
    for fora in ("Lisboa (LPPT)", "Faro (LPFR)", "Porto (LPPR)", "Évora (LPEV)"):
        assert _ad(eng, r, fora) != "NO-GO", fora
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert any("SIGMET T02 (EMBD TS)" in "; ".join(g["reasons"]) for g in r["regioes"])


def test_margem_de_10_nm(eng):
    r = _r(eng, [T02])
    # Bordo oeste do T02 ~W00749 a 41°N. 6 NM para oeste → dentro da margem;
    # 20 NM para oeste → fora.
    import math
    k = math.cos(math.radians(41.0))
    lon_bordo = -(7 + 49 / 60)
    assert _dec(eng, r, 41.0, lon_bordo - 6 / 60 / k) == "NO-GO"
    assert _dec(eng, r, 41.0, lon_bordo - 20 / 60 / k) != "NO-GO"


def test_area_ilegivel_vale_toda_a_area(eng):
    r = _r(eng, [_s("SEV TURB FCST SFC/FL080 STNR NC")])
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}


def test_entire_fir_e_line_valem_toda_a_area(eng):
    for corpo in ("SEV TURB FCST ENTIRE FIR SFC/FL080 STNR NC",
                  "EMBD TS FCST N OF LINE N3800 W01000 - N4000 W00700 TOP FL300 STNR NC"):
        r = _r(eng, [_s(corpo)])
        assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}, corpo


def test_qualificador_como_no_gamet(eng):
    r = _r(eng, [_s("SEV TURB FCST N OF N4000 SFC/FL080 STNR NC")])
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"


def test_movimento_estende_a_area(eng):
    pequeno = "EMBD TS FCST WI N3900 W00930 - N3900 W00915 - N3915 W00915 - N3915 W00930 TOP FL300"
    parado = _r(eng, [_s(pequeno + " STNR NC")])
    movel = _r(eng, [_s(pequeno + " MOV E 20KT NC")])   # 4 h × 20 kt = 80 NM para leste
    ponto = (39.12, -8.2)                                # ~45 NM a leste do polígono
    assert _dec(eng, parado, *ponto) != "NO-GO"
    assert _dec(eng, movel, *ponto) == "NO-GO"


def test_movimento_ilegivel_vale_toda_a_area(eng):
    r = _r(eng, [_s("EMBD TS FCST WI N3900 W00930 - N3900 W00915 - N3915 W00915 TOP FL300 MOV FAST NC")])
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}


def test_circulo(eng):
    r = _r(eng, [_s("SEV TURB OBS WI 10NM OF N3845 W00930 FL015 STNR NC")])
    assert _ad(eng, r, "Cascais (LPCS)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"


def test_sigmet_fora_da_area_nao_muda_decisao(eng):
    espanha = "EMBD TS FCST WI N4100 W00400 - N4100 W00300 - N4200 W00300 - N4200 W00400 TOP FL300 STNR NC"
    r = _r(eng, [_s(espanha)])
    assert "NO-GO" not in {g["decision"] for g in r["regioes"]}
    assert any("fora da área" in m for _, m in r["avisos"])


def test_gamet_refere_t02_e_o_t02_esta_disponivel(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100", sigmet="T02")
    r = _r(eng, [T02], gamet=g)
    assert _ad(eng, r, "Bragança (LPBG)") == "NO-GO"
    assert _ad(eng, r, "Faro (LPFR)") != "NO-GO"


def test_gamet_refere_sigmet_sem_texto_completo_vale_toda_a_area(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100", sigmet="T05")
    assert {x["decision"] for x in _r(eng, [T02], gamet=g)["regioes"]} == {"NO-GO"}
    assert {x["decision"] for x in eng.analisar_gamet(g, "manual", agora=AGORA)["regioes"]} == {"NO-GO"}


# ---------------------------------------------------------------------
# Casos apontados pelo revisor (17-out-2026): nunca uma área menor do que a
# do SIGMET sem cair para toda a área.
# ---------------------------------------------------------------------
QUADRADO = "N3900 W00800 - N3900 W00700 - N4000 W00700 - N4000 W00800"


def test_fcst_at_inclui_a_posicao_prevista(eng):
    corpo = ("EMBD TS OBS WI N3840 W00930 - N3840 W00900 - N3900 W00900 - N3900 W00930 "
             "TOP FL300 FCST AT 1800Z WI N4005 W00720 - N4005 W00710 - N4015 W00710 - "
             "N4015 W00720")
    r = _r(eng, [_s(corpo)])
    assert _dec(eng, r, 38.83, -9.25) == "NO-GO"      # posição observada
    assert _dec(eng, r, 40.17, -7.25) == "NO-GO"      # posição prevista
    assert _dec(eng, r, 39.5, -8.2) == "NO-GO"        # caminho entre as duas


def test_poligono_que_se_cruza_usa_a_envolvente(eng):
    bem, _ = eng.area_sigmet(_s(f"EMBD TS FCST WI {QUADRADO} TOP FL300 STNR NC"))
    laco, _ = eng.area_sigmet(_s("EMBD TS FCST WI N3900 W00800 - N4000 W00700 - "
                                 "N3900 W00700 - N4000 W00800 TOP FL300 STNR NC"))
    assert laco.area >= bem.area * 0.999


def test_coordenada_sem_minutos_cai_para_toda_a_area(eng):
    geom, _ = eng.area_sigmet(_s("EMBD TS FCST WI N3900 W00800 - N39 W007 - N4000 W00700 - "
                                 "N4000 W00800 TOP FL300 STNR NC"))
    assert geom is None


def test_identificador_desconhecido_no_gamet_vale_toda_a_area(eng):
    for campo in ("T02 AND AB3X", "T02 AND T003", "T02, 103", "T02 E MAIS"):
        g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100",
                        sigmet=campo)
        dec = {x["decision"] for x in _r(eng, [T02], gamet=g)["regioes"]}
        assert dec == {"NO-GO"}, campo


def test_margem_nunca_abaixo_de_10_nm(eng):
    import math
    from shapely.geometry import Point
    geom, _ = eng.area_sigmet(T02)
    pol = eng.Polygon([(-7.75, 41.8333), (-7.8833, 39.6667), (-6.8833, 39.6667),
                       (-6.15, 41.7167)])
    # Pontos a 9,9 NM do bordo (haversine), em várias direcções, têm de estar
    # dentro da área (onde ela estiver dentro da FIR).
    for ang in range(0, 360, 15):
        for vx, vy in list(pol.exterior.coords)[:-1]:
            a = math.radians(ang)
            dlat = 9.9 / 60 * math.cos(a)
            dlon = 9.9 / 60 * math.sin(a) / math.cos(math.radians(vy))
            p = Point(vx + dlon, vy + dlat)
            if eng.FIR_POLYGON.contains(p):
                assert geom.buffer(1e-9).contains(p), (vx, vy, ang)
