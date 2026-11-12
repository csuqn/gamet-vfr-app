"""
4.8.1 — `sigmets_terminados`: um boletim com o mesmo id de OUTRO dia UTC é
ignorado (como os do mesmo dia que não se sobrepõem à validade do GAMET), em
vez de bloquear a prova. Até à 4.8 contava como "não se prova nada" e um T01
de ontem impedia de dar como terminado o T01 de hoje já expirado → NO-GO em
toda a área (erro pessimista).

Caso real: GAMET 110300/110900 de 11-nov-2026 (`SIGMET APPLICABLE:T01`;
dados/gamets/2026/11/20261111T0251Z_110300-110900_007a6780e6.txt). Às 08:30Z,
com fonte "ipma" (página com U03 e T04) e os boletins arquivados das últimas
24 h (o T01 de 10-nov e o T01 de 11-nov, que expirou às 04:45Z), a 4.8 dizia
"SIGMET referido no GAMET sem o texto completo disponível: NO-GO em toda a
área" em vez de "T01 já não está em vigor (expirou às 0445Z)".
"""
from datetime import datetime, timezone

from conftest import build_gamet

# GAMET real, tal como foi recolhido (cópia, para correr sem `dados/`)
G110300 = """LPPC GAMET VALID 110300/110900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VIS:LCA 1100-5000M RA/DZ/BR SIGWX:S OF N4000 ISOL/EMBD TS SIG CLD:LCA BKN 002-008/012HFT AGL ISOL/EMBD TCU/CB 016-025/XXXHFT AGL ICE:LCA MOD ABV FL090 TURB:LCA MOD/SEV SFC/FL080 SIGMET APPLICABLE:T01 SECN II PSYS:06 N4430 W01815 L 983HPA STNR NC 06 N3430 W01630 L 989HPA MOV NE NC CLD:SCT/BKN SC/CU 012-030/040HFT AGL SCT/BKN AS/AC 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 210/017KT PS10 180/028KT PS14 180/023KT PS11 2000FT AGL 220/022KT PS09 200/032KT PS13 190/027KT PS10 5000FT AGL 230/037KT PS02 220/029KT PS08 220/033KT PS06 FL100 230/040KT MS00 240/029KT PS00 230/031KT MS00 FL150 240/046KT MS09 240/036KT MS08 220/034KT MS08 FZLVL: 9300FT AMSL 9900FT AMSL 9500FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 200/022KT PS15 180/022KT PS15 190/027KT PS17 2000FT AGL 210/028KT PS14 200/026KT PS14 190/027KT PS15 5000FT AGL 210/032KT PS09 210/031KT PS09 200/027KT PS10 FL100 210/033KT PS01 230/038KT PS00 220/043KT PS01 FL150 210/033KT MS06 240/036KT MS06 240/036KT MS05 FZLVL: 10500FT AMSL 9500FT AMSL 10500FT AMSL MNM QNH:998HPA="""

# Boletins reais arquivados (dados/sigmets/2026/11/), últimas 24 h antes das 08:30Z de 11-nov
T01_10 = "LPPC SIGMET T01 VALID 100900/101200 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4150 W00854 - N4252 W01301 - N4212 W01437 - N4211 W01439 - N4006 W01241 - N4150 W00854 TOP FL300 MOV ESE 30KT NC"
T02_10 = "LPPC SIGMET T02 VALID 101200/101500 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4055 W01125 - N4234 W01153 - N4213 W01038 - N4201 W01004 - N4104 W01033 - N4055 W01125 TOP FL300 MOV NNE 30KT NC"
T01_11 = "LPPC SIGMET T01 VALID 110045/110445 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N3958 W00704 - N3959 W00959 - N3652 W01008 - N3647 W00853 - N3958 W00704 TOP FL300 STNR NC"
U03_11 = "LPPC SIGMET U03 VALID 110500/110900 LPPT- LPPC LISBOA FIR SEV TURB FCST S OF N3459 SFC/FL080 MOV NE 30KT NC"
T04_11 = "LPPC SIGMET T04 VALID 110745/111145 LPPT- LPPC LISBOA FIR EMBD TS FCST E OF LINE N3148 W01509 - N3348 W01552 AND S OF LINE N3348 W01552 - N3415 W01314 TOP FL430 MOV ENE 40KT NC"

AS_0830 = datetime(2026, 11, 11, 8, 30, tzinfo=timezone.utc)
AS_0330 = datetime(2026, 11, 11, 3, 30, tzinfo=timezone.utc)
PERIODO = (datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc),
           datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc))
CNL_T01_11 = "LPPC SIGMET T02 VALID 110300/110445 LPPT- LPPC LISBOA FIR CNL SIGMET T01 110045/110445"


def _decisoes(eng, r):
    return {n: eng.find_region_for_point(r["regioes"], la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _avisos(r):
    return " ".join(m for _, m in r["avisos"])


# ---------------------------------------------------------------------
# Caso real
# ---------------------------------------------------------------------
def test_real_t01_de_ontem_nao_impede_t01_de_hoje_expirado(eng):
    todos = [T01_10, T02_10, T01_11, U03_11, T04_11]
    t = eng.sigmets_terminados(todos, AS_0830, PERIODO)
    assert t.get("T01") == "expirou às 0445Z"
    # Igual ao que dava só com os boletins do dia 11
    assert t == eng.sigmets_terminados([T01_11, U03_11, T04_11], AS_0830, PERIODO)


def test_real_analisar_gamet_0830(eng):
    r = eng.analisar_gamet(G110300, "ipma", boletins=[U03_11, T04_11], boletins_at=AS_0830,
                           agora=AS_0830, boletins_arquivo=[T01_10, T02_10, T01_11, U03_11, T04_11])
    av = _avisos(r)
    assert "já não está em vigor" in av and "expirou às 0445Z" in av
    assert "NO-GO em toda a área" not in av
    for reg in r["regioes"]:
        assert not any("toda a área" in m and "SIGMET" in m for m in reg["reasons"]), reg["reasons"]
    # O mesmo que sem o T01 de ontem no arquivo
    r11 = eng.analisar_gamet(G110300, "ipma", boletins=[U03_11, T04_11], boletins_at=AS_0830,
                             agora=AS_0830, boletins_arquivo=[T01_11, U03_11, T04_11])
    assert _decisoes(eng, r) == _decisoes(eng, r11)


def test_real_gamet_calmo_deixa_de_ser_nogo_em_toda_a_fir(eng):
    # O mesmo cenário num dia calmo: a 4.8 dava NO-GO em toda a FIR
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="110300/110900", sigmet="T01")
    r = eng.analisar_gamet(g, "ipma", boletins=[U03_11, T04_11], boletins_at=AS_0830,
                           agora=AS_0830, boletins_arquivo=[T01_10, T02_10, T01_11, U03_11, T04_11])
    # Só fica o U03 (SEV TURB a S de N3459, MOV NE) na sua área, no sul
    assert "expirou às 0445Z" in _avisos(r)
    for reg in r["regioes"]:
        assert not any("toda a área" in m for m in reg["reasons"]), reg["reasons"]
    d = _decisoes(eng, r)
    assert d["Bragança (LPBG)"] == "GO" and d["Lisboa (LPPT)"] == "GO"
    assert {v for v in d.values()} != {"NO-GO"}


# ---------------------------------------------------------------------
# Casos que continuam conservadores
# ---------------------------------------------------------------------
def test_so_o_t01_de_ontem_continua_toda_a_area(eng):
    assert "T01" not in eng.sigmets_terminados([T01_10], AS_0830, PERIODO)
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="110300/110900", sigmet="T01")
    r = eng.analisar_gamet(g, "ipma", boletins=[], boletins_at=AS_0830, agora=AS_0830,
                           boletins_arquivo=[T01_10])
    assert {x["decision"] for x in r["regioes"]} == {"NO-GO"}
    assert "já não está em vigor" not in _avisos(r)
    assert "NO-GO em toda a área" in _avisos(r)


def test_t01_de_hoje_activo_continua_a_contar(eng):
    assert "T01" not in eng.sigmets_terminados([T01_10, T01_11], AS_0330, PERIODO)
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="110300/110900", sigmet="T01")
    r = eng.analisar_gamet(g, "ipma", boletins=[T01_11], boletins_at=AS_0330, agora=AS_0330,
                           boletins_arquivo=[T01_10, T01_11])
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert "já não está em vigor" not in _avisos(r)
    la, lo = eng.AERODROMES["Évora (LPEV)"]
    assert eng.find_region_for_point(r["regioes"], la, lo)["decision"] == "NO-GO"


def test_t01_de_hoje_cancelado_com_o_de_ontem_presente(eng):
    t = eng.sigmets_terminados([T01_10, T01_11, CNL_T01_11], AS_0330, PERIODO)
    assert t.get("T01") == "cancelado"


def test_gamet_2100_0300_boletim_do_dia_seguinte_nao_prova_nada(eng):
    periodo = (datetime(2026, 11, 10, 21, 0, tzinfo=timezone.utc),
               datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc))
    agora = datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc)
    t01_11_cedo = T01_11.replace("110045/110445", "110000/110100")   # do dia 11, já expirado
    assert "T01" not in eng.sigmets_terminados([t01_11_cedo], agora, periodo)
    # O T01 do dia 10 que se sobrepõe e expirou prova; o do dia 11 não o impede
    t01_10_noite = T01_10.replace("100900/101200", "102100/110000")
    t = eng.sigmets_terminados([t01_10_noite, t01_11_cedo], agora, periodo)
    assert t.get("T01") == "expirou às 0000Z"
    # Com o T01 do dia 10 ainda activo, continua a contar
    t01_10_activo = T01_10.replace("100900/101200", "102300/110300")
    assert "T01" not in eng.sigmets_terminados([t01_10_activo, t01_11_cedo], agora, periodo)


# ---------------------------------------------------------------------
# Revisor do #46: um boletim de outro dia ainda activo e sobreposto ao GAMET
# continua a bloquear a prova (o GAMET pode estar a referi-lo)
# ---------------------------------------------------------------------
# Dia 10: T01 emitido tarde, válido até às 03:00 do dia 11 (padrão real:
# T07 082300/090300, U01 102100/110100 → U01 110100/110500)
X_10 = "LPPC SIGMET T01 VALID 102300/110300 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N3958 W00704 - N3959 W00959 - N3652 W01008 - N3647 W00853 - N3958 W00704 TOP FL300 STNR NC"
# Dia 11: T01 emitido às 00:10 e cancelado às 00:40
Y_11 = "LPPC SIGMET T01 VALID 110010/110410 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N4130 W00700 - N4130 W00800 - N4100 W00800 - N4100 W00700 - N4130 W00700 TOP FL300 STNR NC"
CNL_Y = "LPPC SIGMET T02 VALID 110040/110410 LPPT- LPPC LISBOA FIR CNL SIGMET T01 110010/110410"
AS_0050 = datetime(2026, 11, 11, 0, 50, tzinfo=timezone.utc)
AMD_0045 = (datetime(2026, 11, 11, 0, 45, tzinfo=timezone.utc),
            datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc))


def test_revisor_t01_de_ontem_activo_bloqueia_a_prova(eng):
    assert "T01" not in eng.sigmets_terminados([X_10, Y_11, CNL_Y], AS_0050, AMD_0045)


def test_revisor_pagina_sem_o_t01_de_ontem_continua_nogo_em_toda_a_area(eng):
    g = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR", validity="110045/110300", sigmet="T01")
    r = eng.analisar_gamet(g, "ipma", boletins=[], boletins_at=AS_0050, agora=AS_0050,
                           boletins_arquivo=[X_10, Y_11, CNL_Y])
    d = _decisoes(eng, r)
    assert all(v == "NO-GO" for v in d.values()), d


def test_revisor_t01_de_ontem_ja_terminado_nao_bloqueia(eng):
    # Às 03:30 o X_10 já expirou: não bloqueia; o Y_11 cancelado prova
    depois = datetime(2026, 11, 11, 3, 30, tzinfo=timezone.utc)
    per = (datetime(2026, 11, 11, 0, 45, tzinfo=timezone.utc),
           datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc))
    assert eng.sigmets_terminados([X_10, Y_11, CNL_Y], depois, per).get("T01") == "cancelado"
