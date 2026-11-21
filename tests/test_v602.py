"""6.0.2 (pedido do Duarte a 21-nov-2026): um SIGMET de outro dia UTC que
estava em vigor no início da validade do GAMET serve de prova de que o id
referido terminou.

Caso real: GAMET 210300/210900 de 21-nov-2026 com "SIGMET APPLICABLE:U02"; o
único U02 é o 202355/210355 de 20-nov (SEV TURB SFC/FL070 no N e centro). Até
à 6.0.1, depois das 03:55Z, a app ao vivo (fonte `ipma`) forçava NO-GO em toda
a área até às 09Z; os 10 pontos do sul ficam fora de todos os SIGMETs.
"""
from datetime import datetime, timezone
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "dados"

G210300 = """LPPC GAMET VALID 210300/210900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VIS:N OF N3845 LCA 1200-5000M RA/DZ/BR SIG CLD:N OF N3845 LCA BKN 002-008/010HFT AGL N OF N3830 ISOL/EMBD TCU/CB 020-030/XXXHFT AGL ICE:06/09 N OF N3900 LCA MOD ABV FL110 TURB:N OF N4000 LCA MOD/SEV SFC/FL070 SIGMET APPLICABLE:U02 SECN II PSYS:06 N3700 W01600 - N4200 W01100 COLD FRONT MOV E NC CLD:SCT/BKN SC/CU 012-035/040HFT AGL N OF N3800 SCT/BKN AS/AC 060-090/100-130HFT AMSL MNM QNH:1009HPA="""
U02_20 = "LPPC SIGMET U02 VALID 202355/210355 LPPT- LPPC LISBOA FIR SEV TURB FCST WI N3944 W00704 - N4151 W00635 - N4210 W01031 - N3935 W00908 - N3944 W00704 SFC/FL070 STNR NC"
U01_21 = "LPPC SIGMET U01 VALID 210355/210755 LPPT- LPPC LISBOA FIR SEV TURB FCST WI N4026 W00844 - N4019 W00654 - N4158 W00637 - N4158 W00909 - N4026 W00844 SFC/FL070 STNR WKN"
T01_21 = "LPPC SIGMET T01 VALID 210525/210825 LPPT- LPPC LISBOA FIR EMBD TS FCST WI N3801 W01451 - N3901 W01454 - N4209 W01043 - N4116 W00811 - N3801 W01451 TOP FL320 MOV NE 25KT INTSF"

SUL = ["Faro (LPFR)", "Beja (LPBJ)", "Ferreira do Alentejo (LPFA)",
       "Figueira dos Cavaleiros (LPFC)", "Portimão (LPPM)"]
PER = (datetime(2026, 11, 21, 3, 0, tzinfo=timezone.utc),
       datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))


def _t(h, m=0):
    return datetime(2026, 11, 21, h, m, tzinfo=timezone.utc)


def _dec(eng, r):
    return {n: eng.find_region_for_point(r["regioes"], la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def _avisos(r):
    return " ".join(m for _, m in r["avisos"])


def test_sigmets_terminados_u02_de_ontem_expirado(eng):
    assert eng.sigmets_terminados([U02_20, U01_21], _t(4, 30), PER) == {"U02": "expirou às 0355Z"}


def test_u02_de_ontem_activo_continua_a_contar(eng):
    assert "U02" not in eng.sigmets_terminados([U02_20], _t(3, 30), PER)


def test_real_ipma_depois_de_expirar(eng):
    for agora, activos in ((_t(4, 30), [U01_21]), (_t(6, 30), [U01_21, T01_21])):
        r = eng.analisar_gamet(G210300, "ipma", boletins=activos, boletins_at=agora,
                               agora=agora, boletins_arquivo=[U02_20, U01_21, T01_21])
        d = _dec(eng, r)
        assert all(d[n] == "GO" for n in SUL), d
        assert d["Porto (LPPR)"] == "NO-GO"           # GAMET (base 200 ft, CB EMBD)
        assert r["faixa_sig"] == ("ACTIVO", "NO-GO")    # U01 (e T01) em vigor
        assert "U02" in _avisos(r) and "já não está em vigor" in _avisos(r)
        assert "forçada a NO-GO em toda a área" not in _avisos(r)
        # Igual ao GAMET sem a referência + os SIGMETs em vigor
        g0 = G210300.replace("SIGMET APPLICABLE:U02", "SIGMET APPLICABLE: NIL")
        r0 = eng.analisar_gamet(g0, "ipma", boletins=activos, boletins_at=agora, agora=agora,
                                boletins_arquivo=[U02_20, U01_21, T01_21])
        assert _dec(eng, r0) == d


def test_real_ipma_antes_de_expirar_conta_na_area(eng):
    agora = _t(3, 30)
    r = eng.analisar_gamet(G210300, "ipma", boletins=[U02_20], boletins_at=agora,
                           agora=agora, boletins_arquivo=[U02_20])
    d = _dec(eng, r)
    assert d["Coimbra (LPCO)"] == "NO-GO"
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_boletim_de_ontem_que_nao_estava_em_vigor_no_inicio_nao_prova(eng):
    # Expirou antes do início do GAMET (02:58): não é o referido → por provar
    u02_cedo = U02_20.replace("202355/210355", "202355/210258")
    assert "U02" not in eng.sigmets_terminados([u02_cedo], _t(4, 30), PER)
    # De ontem, começou depois do início do GAMET 2100/0300 e está activo → por provar
    per = (datetime(2026, 11, 20, 21, 0, tzinfo=timezone.utc), _t(3))
    assert "U02" not in eng.sigmets_terminados([U02_20], _t(1), per)


def test_com_um_u02_do_proprio_dia_activo_continua_a_contar(eng):
    u02_21 = U01_21.replace("U01", "U02").replace("210355/210755", "210400/210800")
    assert "U02" not in eng.sigmets_terminados([U02_20, u02_21], _t(4, 30), PER)


def test_ficheiros_reais_iguais_aos_do_teste():
    if not (DADOS / "sigmets").is_dir():
        import pytest
        pytest.skip("sem o arquivo (dados/)")
    txt = (DADOS / "gamets/2026/11/20261121T0251Z_210300-210900_08674606f5.txt").read_text()
    assert txt.startswith(G210300.split(" SECN II")[0])
    s = (DADOS / "sigmets/2026/11/20261121T0005Z_SIGMETU02_202355-210355_e12119c06d.txt").read_text()
    assert U02_20 in s
