"""
3.1 — "BTN N4050 - N3840": o hífen em vez do AND nos qualificadores BTN.

GAMET real 171500/172100 (17-out-2026):

    SIG CLD:N OF N3710 AND E OF W00800 ISOL/EMBD TCU/CB 025-040/XXXHFT AGL
    15/18 BTN N4050 - N3840 MAR AND COT LCA BKN 008/012HFT AGL

Até à 3.0 `extract_polygon()` só aceitava "BTN … AND …". Com o hífen não
reconhecia a área e a subentrada herdava em silêncio a da anterior
("N OF N3710 AND E OF W00800"): a base de 800 ft da costa W entre 38°40' e
40°50'N ficava numa tira junto à foz do Guadiana. Com 800 ft a decisão não
muda, mas com uma base baixa Cascais e Atouguia dariam GO (erro optimista).
"""
import pytest

from conftest import build_gamet

GAMET_171500 = (
    'LPPC GAMET VALID 171500/172100 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:N OF N3710 AND E OF W00800 LCA 3000-5000M RA SIGWX:N OF N3710 AND E OF W00800 '
    'ISOL/EMBD TS SIG CLD:N OF N3710 AND E OF W00800 ISOL/EMBD TCU/CB 025-040/XXXHFT AGL '
    '15/18 BTN N4050 - N3840 MAR AND COT LCA BKN 008/012HFT AGL ICE:18/21 N OF N4100 AND E '
    'OF W00735 LCA MOD ABV FL090 TURB:N OF N3815 MAR AND COT LCA MOD SFC/FL040 SIGMET '
    'APPLICABLE:T02 SECN II PSYS:18 N3910 W00415 L 1014HPA STNR NC CLD:FEW/SCT SC/CU '
    '015-030/045HFT AGL FEW/SCT AC/AS 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU '
    'N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 060/018KT PS12 050/015KT PS21 '
    '060/019KT PS15 2000FT AGL 070/021KT PS10 060/015KT PS18 060/021KT PS13 5000FT AGL '
    '080/015KT PS04 070/010KT PS10 070/008KT PS07 FL100 080/007KT MS01 010/013KT PS00 '
    '020/010KT PS00 FL150 360/007KT MS10 360/020KT MS10 350/018KT MS10 FZLVL: 9900FT AMSL '
    '10700FT AMSL 9600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 '
    '1000FT AGL 350/022KT PS18 310/008KT PS21 340/012KT PS23 2000FT AGL 360/016KT PS18 '
    '310/008KT PS18 310/007KT PS21 5000FT AGL 010/010KT PS12 290/004KT PS11 290/010KT PS14 '
    'FL100 320/017KT PS03 290/010KT PS01 300/008KT PS02 FL150 330/021KT MS08 310/018KT MS08 '
    '330/017KT MS08 FZLVL: 11300FT AMSL 11000FT AMSL 10500FT AMSL MNM QNH:1013HPA='
)

LAT_SUL = 38 + 40 / 60    # N3840
LAT_NORTE = 40 + 50 / 60  # N4050

# Decisões da 3.0 para este GAMET, sem o SIGMET T02 (cujo texto não vem no
# GAMET). A base de 800 ft não altera nenhuma — têm de se manter.
DECISOES_3_0 = {
    'Lisboa (LPPT)': 'GO', 'Porto (LPPR)': 'GO', 'Faro (LPFR)': 'GO',
    'Beja (LPBJ)': 'NO-GO', 'Cascais (LPCS)': 'GO', 'Évora (LPEV)': 'NO-GO',
    'Vila Real (LPVR)': 'NO-GO', 'Ponte de Sor (LPSO)': 'GO',
    'Bragança (LPBG)': 'NO-GO', 'Braga (LPBR)': 'GO',
    'Castelo Branco (LPCB)': 'NO-GO', 'Chaves (LPCH)': 'NO-GO',
    'Coimbra (LPCO)': 'GO', 'Ferreira do Alentejo (LPFA)': 'GO',
    'Figueira dos Cavaleiros (LPFC)': 'GO', 'Espinho (LPIN)': 'GO',
    'Leiria (LPJF)': 'GO', 'Lousã (LPLZ)': 'GO', 'Mirandela (LPMI)': 'NO-GO',
    'Amendoeira - Montemor-o-Novo (LPMN)': 'GO', 'Mogadouro (LPMU)': 'NO-GO',
    'Portimão (LPPM)': 'GO', 'Proença-a-Nova (LPPN)': 'NO-GO',
    'Santa Cruz (LPSC)': 'GO', 'Seia (LPSE)': 'NO-GO', 'Santarém (LPSR)': 'GO',
    'Vilar de Luz/Maia (LPVL)': 'GO', 'Viseu (LPVZ)': 'NO-GO',
    'Alqueidão (LP48)': 'GO', 'Atouguia da Baleia (LP49)': 'GO',
    'Azambuja (LP50)': 'GO', 'Beja UL (LP51)': 'NO-GO', 'Benavente (LP52)': 'GO',
    'Cabeceiras de Basto (LP53)': 'NO-GO', 'Campinho (LP54)': 'NO-GO',
    'Cerval (LP55)': 'GO', 'Herdade da Lameira (LP57)': 'NO-GO',
    'Herdade da Zambujeira (LP58)': 'GO', 'Lagos (LP59)': 'GO', 'Palma (LP61)': 'GO',
    'S. Miguel de Laúndos (LP62)': 'GO', 'Tojeira (LP63)': 'GO',
    'Valdonas (LP64)': 'GO', 'Cabeço da Vaca (LP66)': 'NO-GO',
    'Herdade do Pontal - Pegões (LP68)': 'GO', 'Casalinho Pombal (LP69)': 'GO',
    'Valadas - Ferreira do Zêzere (LP71)': 'GO', 'Lezírias (LP75)': 'GO',
    'Casarão (LP76)': 'GO', 'Alentejo Air Park (LP78)': 'GO', 'Faias (LP79)': 'GO',
    'Pias Longas (LP80)': 'GO',
}


def _dec(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)["decision"]


def _base(r, valor):
    (b,) = [b for b in r["blocks"] if b.phenomenon == "BASE_AGL" and b.value == valor]
    return b


def test_171500_base_800_na_costa_w_entre_3840_e_4050(eng, analyse):
    b = _base(analyse(GAMET_171500), 800)
    minx, miny, maxx, maxy = b.polygon.bounds
    assert abs(miny - LAT_SUL) < 0.01
    assert abs(maxy - LAT_NORTE) < 0.01
    # Costa W e mar — não a tira junto ao Guadiana (E de 8°W)
    assert maxx < -8.0
    assert b.window == "15–18Z"
    from shapely.geometry import Point
    for nome in ("Cascais (LPCS)", "Atouguia da Baleia (LP49)"):
        la, lo = eng.AERODROMES[nome]
        assert b.polygon.contains(Point(lo, la)), nome


def test_171500_subentrada_anterior_mantem_a_sua_area(analyse):
    r = analyse(GAMET_171500)
    b = _base(r, 2500)
    minx, miny, maxx, maxy = b.polygon.bounds
    assert abs(minx - (-8.0)) < 1e-6
    assert abs(miny - (37 + 10 / 60)) < 0.01


def test_171500_decisoes_por_aerodromo_nao_mudam(eng, analyse):
    r = analyse(GAMET_171500.replace("SIGMET APPLICABLE:T02", "SIGMET APPLICABLE: NIL"))
    obtidas = {n: _dec(eng, r["regions"], n) for n in eng.AERODROMES}
    assert obtidas == DECISOES_3_0


def test_171500_com_base_baixa_da_no_go_na_costa_w(eng, analyse):
    texto = GAMET_171500.replace("BKN 008/012HFT", "BKN 002/012HFT").replace(
        "SIGMET APPLICABLE:T02", "SIGMET APPLICABLE: NIL")
    r = analyse(texto)
    for nome in ("Cascais (LPCS)", "Atouguia da Baleia (LP49)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome
    # Fora da faixa ou fora de COT/MAR: a base de 200 ft não chega lá
    for nome in ("Faro (LPFR)", "Portimão (LPPM)", "Porto (LPPR)"):
        assert _dec(eng, r["regions"], nome) == "GO", nome


@pytest.mark.parametrize("btn", ["BTN N4050-N3840", "BTN N4050 - N3840",
                                 "BTN N4050 -N3840", "BTN N4050- N3840"])
def test_btn_latitude_com_hifen_igual_ao_and(analyse, btn):
    com_and = analyse(build_gamet("SECN I SIG CLD:BTN N4050 AND N3840 BKN 002HFT AGL"))
    com_hifen = analyse(build_gamet(f"SECN I SIG CLD:{btn} BKN 002HFT AGL"))
    (a,) = com_and["blocks"]
    (b,) = com_hifen["blocks"]
    assert b.value == 200
    assert a.polygon.symmetric_difference(b.polygon).area < 1e-9


@pytest.mark.parametrize("btn", ["BTN W00800 - W00700", "BTN W00800-W00700"])
def test_btn_longitude_com_hifen(analyse, btn):
    (b,) = analyse(build_gamet(f"SECN I SIG CLD:{btn} BKN 002HFT AGL"))["blocks"]
    minx, _, maxx, _ = b.polygon.bounds
    assert abs(minx - (-8.0)) < 1e-6
    assert abs(maxx - (-7.0)) < 1e-6


def test_btn_com_hifen_seguido_de_e_of_e_uma_so_area(analyse):
    com_and = analyse(build_gamet(
        "SECN I SIG CLD:BTN N3840 AND N4100 E OF W00800 BKN 002HFT AGL"))
    com_hifen = analyse(build_gamet(
        "SECN I SIG CLD:BTN N3840 - N4100 E OF W00800 BKN 002HFT AGL"))
    (a,) = com_and["blocks"]
    (b,) = com_hifen["blocks"]
    assert a.polygon.symmetric_difference(b.polygon).area < 1e-9


def test_btn_com_hifen_nao_estraga_intervalos_de_valores(analyse):
    r = analyse(build_gamet(
        "SECN I SFC VIS:BTN N3840 - N4100 LCA 0400-5000M FG/BR "
        "SIG CLD:BTN N3840-N4100 LCA BKN 002-008/010HFT AGL"))
    assert r["vis"] == [400]
    assert r["base"] == [200]
    for b in r["blocks"]:
        assert abs(b.polygon.bounds[1] - LAT_SUL) < 0.01
        assert abs(b.polygon.bounds[3] - 41.0) < 0.01
