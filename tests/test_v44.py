"""
4.4 — Redacção da nota "Nuvens baixas na Secção II" para bases AMSL.

GAMET real 301500/302100 (recolhido a 30-out-2026 14:42Z), Secção II:
"N OF N4000 LAN FEW/SCT AS/AC 060-090/100-130HFT AMSL". A base de 6000 ft AMSL
é comparada com o MEF da quadrícula (relevo mais alto + obstáculos), não com a
elevação do aeródromo, e fica < 500 ft acima do MEF em LPBG, LPSE e LP66. Até à
4.3 a nota dizia "aeródromos abrangidos: LPBG, LPSE, LP66", o que dava a ideia
de nuvem baixa na própria pista (observação do comparador no relatório de
31-out-2026; pedido do Duarte). Desde a 4.4 a linha AMSL diz que a base fica
perto do relevo mais alto da quadrícula. As bases AGL continuam iguais.
Só muda o texto: os pontos, a decisão e as regiões ficam iguais.
"""
from datetime import datetime, timezone

G301500 = """LPPC GAMET VALID 301500/302100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC VIS:18/21 N OF N3900 MAR AND COT LCA 1200-5000M BR SIG CLD:18/21 N OF N3900 MAR AND COT LCA BKN 003-008/012HFT AGL SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:18 NIL CLD:MAR AND COT FEW SC/CU 012-015/035HFT AGL N OF N4000 LAN FEW/SCT AS/AC 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 250/002KT PS15 360/006KT PS19 330/004KT PS17 2000FT AGL 350/002KT PS13 030/005KT PS18 050/003KT PS15 5000FT AGL 010/005KT PS08 350/006KT PS13 010/007KT PS10 FL100 010/008KT PS04 320/005KT PS05 360/006KT PS06 FL150 350/015KT MS05 360/006KT MS05 350/010KT MS05 FZLVL: 12500FT AMSL 13100FT AMSL 13100FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 030/013KT PS21 020/011KT PS21 070/001KT PS20 2000FT AGL 040/011KT PS19 050/008KT PS18 070/004KT PS20 5000FT AGL 350/006KT PS13 340/003KT PS12 020/003KT PS13 FL100 140/005KT PS05 130/003KT PS06 140/002KT PS06 FL150 110/008KT MS05 020/003KT MS04 090/007KT MS05 FZLVL: 13000FT AMSL 13400FT AMSL 12900FT AMSL MNM QNH:1017HPA="""

G300900 = """LPPC GAMET VALID 300900/301500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I HAZARDOUS WX NIL SECN II PSYS:12 NIL CLD:LAN FEW SC/CU 012-030/040HFT AGL BTN N3900 AND N4130 MAR AND COT SCT ST 004-008/012HFT AGL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 230/001KT PS14 060/003KT PS18 280/002KT PS17 2000FT AGL 310/005KT PS12 040/002KT PS17 350/004KT PS15 5000FT AGL 010/003KT PS09 320/006KT PS13 040/003KT PS09 FL100 320/007KT PS04 310/003KT PS05 350/004KT PS06 FL150 340/014KT MS05 310/010KT MS05 340/010KT MS05 FZLVL: 12500FT AMSL 13100FT AMSL 12400FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 060/007KT PS22 080/003KT PS20 100/006KT PS21 2000FT AGL 050/006KT PS19 050/006KT PS18 090/008KT PS19 5000FT AGL 040/002KT PS12 120/002KT PS11 140/006KT PS13 FL100 120/005KT PS06 070/005KT PS06 140/008KT PS05 FL150 110/003KT MS05 030/005KT MS04 100/009KT MS05 FZLVL: 13000FT AMSL 13400FT AMSL 13000FT AMSL MNM QNH:1017HPA="""


def _nota(eng, gamet, agora):
    r = eng.analisar_gamet(gamet, "manual", agora=agora)
    notas = [x for _t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) == 1
    return r, notas[0]


def test_versao(eng):
    assert tuple(int(x) for x in eng.APP_VERSION.split(".")) >= (4, 4)


def test_amsl_diz_relevo_e_nao_aerodromos_abrangidos(eng):
    _, nota = _nota(eng, G301500, datetime(2026, 10, 30, 15, 30, tzinfo=timezone.utc))
    linha = next(l for l in nota.splitlines() if "6000 ft AMSL" in l)
    assert "relevo mais alto" in linha and "MEF" in linha
    assert "não necessariamente na pista" in linha
    assert "aeródromos abrangidos" not in linha
    for cod in ("LPBG", "LPSE", "LP66"):
        assert cod in linha


def test_amsl_mesmos_pontos(eng):
    _, nuvens = eng.nuvens_baixas_secn2(G301500)
    assert [(n[0], n[1]) for n in nuvens] == [(6000, "AMSL")]
    cods = {p.split("(")[-1].rstrip(")") for p in nuvens[0][4]}
    assert cods == {"LPBG", "LPSE", "LP66"}


def test_agl_inalterada(eng):
    _, nota = _nota(eng, G300900, datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc))
    linha = next(l for l in nota.splitlines() if "400 ft AGL" in l)
    assert "aeródromos abrangidos: LPPR, LPIN, LPSC, LP49, LP62" in linha
    assert "relevo mais alto" not in linha


def test_decisao_inalterada(eng, analyse):
    regioes = analyse(G301500)["regions"]
    for nome, (la, lo) in eng.AERODROMES.items():
        reg = eng.find_region_for_point(regioes, la, lo)
        esperado = "MARGINAL" if any(c in nome for c in
                                     ("LPPR", "LPIN", "LPSC", "LP49", "LP62")) else "GO"
        assert reg["decision"] == esperado, nome
