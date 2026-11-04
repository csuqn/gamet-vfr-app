"""
4.7.1 — o motivo de TURB/ICE/MTW mostra só a camada do fenómeno que decide.

Caso real: GAMET 030900/031500 (3-nov-2026). Na célula onde a TURB SEV das
09–11Z (SFC/FL070) e a TURB MOD das 11–15Z (SFC/FL060) se sobrepõem, o motivo
era "TURB SEV SFC/FL070/SFC/FL060 — risco severo": parecia que a SEV ia até
FL060. Só muda o texto; as decisões e `turb_layers` ficam iguais.
"""

GAMET_030900 = (
    "LPPC GAMET VALID 030900/031500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW "
    "FL150 SECN I TURB:09/11 N OF N3900 LCA MOD/SEV SFC/FL070 11/15 BTN N4130 "
    "- N4000 AND W OF W00745 LAN LCA MOD SFC/FL060 SIGMET APPLICABLE: AT TIME "
    "OF ISSUE NIL SECN II PSYS:12 NIL CLD:NIL MNM QNH:1012HPA="
)

NO_GO_030900 = {
    "LPPR", "LPVR", "LPSO", "LPBG", "LPBR", "LPCB", "LPCH", "LPCO", "LPIN",
    "LPJF", "LPLZ", "LPMI", "LPMU", "LPPN", "LPSC", "LPSE", "LPSR", "LPVL",
    "LPVZ", "LP48", "LP49", "LP50", "LP53", "LP55", "LP57", "LP62", "LP64",
    "LP66", "LP69", "LP71", "LP76", "LP80",
}


def _icao(nome):
    return nome.rsplit("(", 1)[1].rstrip(")")


def test_gamet_real_030900_motivo_so_com_camada_sev(eng):
    blocos, *_ = eng.parse_gamet(GAMET_030900)
    regioes = eng.compute_dynamic_regions(blocos)
    motivos = [m for r in regioes for m in r["reasons"]]
    assert "TURB SEV SFC/FL070 — risco severo" in motivos
    assert not any("FL060" in m for m in motivos)
    # Decisões iguais às da 4.7 (as do piloto e do relatório de 4-nov)
    nogo = set()
    for nome, (la, lo) in eng.AERODROMES.items():
        reg = eng.find_region_for_point(regioes, la, lo)
        if reg["decision"] == "NO-GO":
            nogo.add(_icao(nome))
        else:
            assert reg["decision"] == "GO", nome
    assert nogo == NO_GO_030900
    # A região continua a guardar as duas camadas (briefing/PDF)
    camadas = set().union(*(r["turb_layers"] for r in regioes))
    assert {"SFC/FL070", "SFC/FL060"} <= camadas


def _ev(t, v, layer, q=""):
    return (t, v, q, layer)


def test_turb_sev_com_mod_noutra_camada(eng):
    d = eng.decision([_ev("TURB", "SEV", "SFC/FL070"),
                         _ev("TURB", "MOD", "SFC/FL060")])
    assert d[0] == "NO-GO"
    assert "TURB SEV SFC/FL070 — risco severo" in d[-1]
    assert d[5] == ["SFC/FL070", "SFC/FL060"]  # turb_layers inalterado


def test_duas_turb_sev_camadas_distintas_e_repetidas(eng):
    d = eng.decision([_ev("TURB", "SEV", "SFC/FL070"),
                         _ev("TURB", "SEV", "FL050/FL100"),
                         _ev("TURB", "SEV", "SFC/FL070")])
    assert "TURB SEV SFC/FL070/FL050/FL100 — risco severo" in d[-1]


def test_turb_sev_sem_camada_com_mod_com_camada(eng):
    d = eng.decision([_ev("TURB", "SEV", ""), _ev("TURB", "MOD", "SFC/FL060")])
    assert d[0] == "NO-GO"
    assert "TURB SEV — risco severo" in d[-1]


def test_ice_sev_com_mod(eng):
    d = eng.decision([_ev("ICE", "SEV", "FL050/FL100"),
                         _ev("ICE", "MOD", "FL030/FL050")])
    assert d[0] == "NO-GO"
    assert "ICE SEV FL050/FL100 — risco severo" in d[-1]
    assert d[7] == ["FL050/FL100", "FL030/FL050"]  # ice_layers inalterado


def test_mtw_sev_e_mod(eng):
    d = eng.decision([_ev("MTW", "SEV", "FL080"), _ev("MTW", "MOD", "FL050")])
    assert d[0] == "NO-GO"
    assert "MTW SEV FL080 (onda de montanha) — risco severo" in d[-1]
    d = eng.decision([_ev("MTW", "MOD", "FL050"), _ev("MTW", "MOD", "FL050")])
    assert d[0] == "MARGINAL"
    assert "MTW MOD FL050 (onda de montanha)" in d[-1]


def test_so_mod_continua_go(eng):
    d = eng.decision([_ev("TURB", "MOD", "SFC/FL060"),
                         _ev("ICE", "MOD", "FL030/FL050")])
    assert d[0] == "GO"
