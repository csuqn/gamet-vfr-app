"""
3.2 — (1) SIGMET referido no GAMET que já se sabe terminado (expirou ou foi
cancelado) deixa de pôr NO-GO, com aviso; estado desconhecido continua a dar
NO-GO em toda a área (decisão do Duarte, 17-out-2026). (2) Uma fatia pequena
só se funde numa vizinha cujos motivos já incluam os dela — os motivos de uma
zona não passam para outra.

Caso real: GAMET 171500/172100 ("SIGMET APPLICABLE: T02"), T02 válido
14:00–18:00Z. Às 18:13Z a app punha NO-GO em toda a FIR e Alqueidão
mostrava "CB/TS ISOL/EMBD" de uma zona a leste de W008.
"""
from datetime import datetime, timezone

from conftest import build_gamet

G1521 = """LPPC GAMET VALID 171500/172100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VIS:N OF N3710 AND E OF W00800 LCA 3000-5000M RA SIGWX:N OF N3710 AND E OF W00800 ISOL/EMBD TS SIG CLD:N OF N3710 AND E OF W00800 ISOL/EMBD TCU/CB 025-040/XXXHFT AGL 15/18 BTN N4050 - N3840 MAR AND COT LCA BKN 008/012HFT AGL ICE:18/21 N OF N4100 AND E OF W00735 LCA MOD ABV FL090 TURB:N OF N3815 MAR AND COT LCA MOD SFC/FL040 SIGMET APPLICABLE:T02 SECN II PSYS:18 N3910 W00415 L 1014HPA STNR NC CLD:FEW/SCT SC/CU 015-030/045HFT AGL FEW/SCT AC/AS 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 060/018KT PS12 050/015KT PS21 060/019KT PS15 2000FT AGL 070/021KT PS10 060/015KT PS18 060/021KT PS13 5000FT AGL 080/015KT PS04 070/010KT PS10 070/008KT PS07 FL100 080/007KT MS01 010/013KT PS00 020/010KT PS00 FL150 360/007KT MS10 360/020KT MS10 350/018KT MS10 FZLVL: 9900FT AMSL 10700FT AMSL 9600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 350/022KT PS18 310/008KT PS21 340/012KT PS23 2000FT AGL 360/016KT PS18 310/008KT PS18 310/007KT PS21 5000FT AGL 010/010KT PS12 290/004KT PS11 290/010KT PS14 FL100 320/017KT PS03 290/010KT PS01 300/008KT PS02 FL150 330/021KT MS08 310/018KT MS08 330/017KT MS08 FZLVL: 11300FT AMSL 11000FT AMSL 10500FT AMSL MNM QNH:1013HPA="""
T01 = ("LPPC SIGMET T01 VALID 171010/171410 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4137 W00616 - "
       "N4157 W00634 - N4156 W00713 - N4152 W00746 - N4008 W00810 - N3947 W00658 - N4137 W00616 "
       "TOP FL360 STNR NC")
T02 = ("LPPC SIGMET T02 VALID 171400/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4150 W00745 - "
       "N3940 W00753 - N3940 W00653 - N4143 W00609 - N4150 W00745 TOP FL340 STNR WKN")
DEPOIS = datetime(2026, 10, 17, 18, 13, tzinfo=timezone.utc)
DURANTE = datetime(2026, 10, 17, 17, 0, tzinfo=timezone.utc)


def _ad(eng, r, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(r["regioes"], la, lo)


def test_sigmet_referido_ja_expirado_deixa_de_contar(eng):
    r = eng.analisar_gamet(G1521, "ipma", boletins=[], boletins_at=DEPOIS, agora=DEPOIS,
                           boletins_arquivo=[T01, T02])
    lp48 = _ad(eng, r, "Alqueidão (LP48)")
    assert lp48["decision"] == "GO" and not any("SIGMET" in m for m in lp48["reasons"])
    # A trovoada do próprio GAMET (a leste de W008) continua NO-GO
    assert _ad(eng, r, "Bragança (LPBG)")["decision"] == "NO-GO"
    avisos = " ".join(m for _, m in r["avisos"])
    assert "já não está em vigor" in avisos and "expirou às 1800Z" in avisos
    assert r["faixa_sig"] == ("NIL", "GO")


def test_estado_desconhecido_continua_toda_a_area(eng):
    # Sem arquivo e sem o T02 na página: não se sabe se expirou → conservador
    r = eng.analisar_gamet(G1521, "ipma", boletins=[], boletins_at=DEPOIS, agora=DEPOIS)
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    # Colado à mão: idem
    r = eng.analisar_gamet(G1521, "manual", agora=DEPOIS)
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}


def test_sigmet_cancelado_deixa_de_contar(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100", sigmet="T05")
    t05 = T02.replace("T02", "T05")
    cnl = "LPPC SIGMET T06 VALID 171600/171800 LPPT- LPPC LISBOA FIR CNL SIGMET T05 171400/171800"
    r = eng.analisar_gamet(g, "ipma", boletins=[t05, cnl], boletins_at=DURANTE, agora=DURANTE)
    assert "NO-GO" not in {x["decision"] for x in r["regioes"]}
    assert any("cancelado" in m for _, m in r["avisos"])


def test_sigmet_referido_em_vigor_continua_a_contar_na_area(eng):
    r = eng.analisar_gamet(G1521, "ipma", boletins=[T02], boletins_at=DURANTE, agora=DURANTE,
                           boletins_arquivo=[T01, T02])
    assert _ad(eng, r, "Bragança (LPBG)")["decision"] == "NO-GO"
    assert any("SIGMET T02 (EMBD TS)" in m for m in _ad(eng, r, "Mirandela (LPMI)")["reasons"])
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_um_expirado_e_outro_desconhecido_continua_toda_a_area(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="171500/172100",
                    sigmet="T02 AND T09")
    r = eng.analisar_gamet(g, "ipma", boletins=[], boletins_at=DEPOIS, agora=DEPOIS,
                           boletins_arquivo=[T02])
    assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}


def test_motivos_de_uma_fatia_nao_passam_para_a_vizinha(eng):
    # SIGMET sem área (toda a FIR) + uma faixa pequena de TS no extremo sul
    g = build_gamet("SECN I SIGWX: BTN N3700 AND N3715 E OF W00745 ISOL/EMBD TS",
                    validity="171500/172100", sigmet="T02")
    r = eng.analisar_gamet(g, "manual", agora=DURANTE)
    lp48 = _ad(eng, r, "Alqueidão (LP48)")
    assert lp48["decision"] == "NO-GO"
    assert not any(m.startswith("TS") for m in lp48["reasons"]), lp48["reasons"]
    # A faixa de TS continua no briefing, com o seu motivo
    assert any(any(m.startswith("TS") for m in x["reasons"]) for x in r["regioes"])
    area = sum(x["polygon"].area for x in r["regioes"])
    assert abs(area / eng.FIR_POLYGON.area - 1) < 0.01


# ---------------------------------------------------------------------
# Casos do revisor (18-out-2026): a numeração dos SIGMET recomeça todos os
# dias — um T02 (ou um CNL do T02) de ontem não diz nada sobre o T02 de hoje.
# ---------------------------------------------------------------------
T02_ONTEM = T02.replace("171400/171800", "161400/161800")
T02_HOJE_TARDE = T02.replace("171400/171800", "171700/172100")
NOITE = datetime(2026, 10, 17, 19, 0, tzinfo=timezone.utc)


def test_a1_t02_de_ontem_expirado_nao_prova_nada(eng):
    r = eng.analisar_gamet(G1521, "ipma", boletins=[], boletins_at=NOITE, agora=NOITE,
                           boletins_arquivo=[T02_ONTEM])
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_a2_t02_de_hoje_em_vigor_no_arquivo_continua_a_contar(eng):
    r = eng.analisar_gamet(G1521, "ipma", boletins=[], boletins_at=NOITE, agora=NOITE,
                           boletins_arquivo=[T02_ONTEM, T02_HOJE_TARDE])
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert _ad(eng, r, "Bragança (LPBG)")["decision"] == "NO-GO"
    assert not any("já não está em vigor" in m for _, m in r["avisos"])


def test_b1_cnl_de_ontem_nao_cancela_o_t02_de_hoje(eng):
    cnl_ontem = "LPPC SIGMET T03 VALID 161600/161800 LPPT- LPPC LISBOA FIR CNL SIGMET T02 161400/161800"
    s, _ = eng.active_bulletins([T02_HOJE_TARDE, cnl_ontem], NOITE)
    assert s == [T02_HOJE_TARDE]
    r = eng.analisar_gamet(G1521, "arquivo_recurso", boletins=[T02_HOJE_TARDE, cnl_ontem],
                           boletins_at=NOITE, agora=NOITE)
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert _ad(eng, r, "Bragança (LPBG)")["decision"] == "NO-GO"


def test_f_t02_de_hoje_ainda_por_comecar_continua_a_contar(eng):
    cedo = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
    r = eng.analisar_gamet(G1521, "ipma", boletins=[T02_HOJE_TARDE], boletins_at=cedo, agora=cedo,
                           boletins_arquivo=[T02_ONTEM])
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_cnl_sem_validade_cancela_so_o_boletim_em_vigor(eng):
    cnl = "LPPC SIGMET T03 VALID 171600/171800 LPPT- LPPC LISBOA FIR CNL SIGMET T02"
    agora = datetime(2026, 10, 17, 16, 30, tzinfo=timezone.utc)
    s, _ = eng.active_bulletins([T02, T02_ONTEM, cnl], agora)
    assert s == []                                     # T02 de hoje cancelado
    s, _ = eng.active_bulletins([T02_HOJE_TARDE, cnl], datetime(2026, 10, 17, 19, 0, tzinfo=timezone.utc))
    assert s == [T02_HOJE_TARDE]                       # começou depois do CNL — não é o mesmo


def test_g6_boletim_com_o_mesmo_id_ilegivel_nao_prova_nada(eng):
    ilegivel = "LPPC SIGMET T02 VALID 17XX00/171800 LPPT- LPPC LISBOA FIR EMBD TS FCST"
    r = eng.analisar_gamet(G1521, "ipma", boletins=[], boletins_at=NOITE, agora=NOITE,
                           boletins_arquivo=[T02, ilegivel])
    assert {g["decision"] for g in r["regioes"]} == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_h_gamet_depois_da_meia_noite_nao_usa_o_t02_da_vespera(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="180030/180300", sigmet="T02")
    t02_17 = T02.replace("171400/171800", "172045/180045")
    agora = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)
    r = eng.analisar_gamet(g, "ipma", boletins=[], boletins_at=agora, agora=agora,
                           boletins_arquivo=[t02_17])
    assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}
    # Mas um GAMET que começou no dia 17 e refere o T02 do dia 17 já expirado: deixa de contar
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="172100/180300", sigmet="T02")
    r = eng.analisar_gamet(g, "ipma", boletins=[], boletins_at=agora, agora=agora,
                           boletins_arquivo=[t02_17])
    assert "NO-GO" not in {x["decision"] for x in r["regioes"]}
