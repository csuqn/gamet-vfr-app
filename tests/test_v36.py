"""
3.6 — Nota informativa para nuvens baixas da Secção II (pedido do Duarte,
20-out-2026). O CLD da Secção II não entra na decisão (não é SIG CLD), mas uma
base < 500 ft AGL passa a gerar um aviso "info" com os aeródromos abrangidos.

Caso real: GAMET 192100/200300 — "SECN I HAZARDOUS WX NIL ... SECN II ...
CLD:00/03 N OF N4000 LAN SCT ST 004-008/012HFT LAN FEW/SCT SC/CU ...".
"""
from datetime import datetime, timezone

AGORA = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)

G192100 = (
    "LPPC GAMET VALID 192100/200300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "HAZARDOUS WX NIL SECN II PSYS:00 N3700 W00700 L 1012HPA STNR NC CLD:00/03 N OF N4000 "
    "LAN SCT ST 004-008/012HFT LAN FEW/SCT SC/CU 015-030/045HFT AGL W OF W00800 FEW/SCT "
    "AC/AS 060-090/100-130HFT AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 "
    "N4045 W00750 1000FT AGL 170/003KT PS08 040/004KT PS15 170/002KT PS12 2000FT AGL "
    "230/006KT PS06 340/004KT PS14 180/001KT PS10 5000FT AGL 260/009KT PS01 280/004KT PS07 "
    "280/006KT PS05 FL100 290/016KT MS02 300/020KT MS01 300/014KT MS01 FL150 270/025KT MS11 "
    "310/031KT MS09 290/024KT MS11 FZLVL: 8300FT AMSL 9200FT AMSL 9500FT AMSL LISBOA EVORA "
    "FARO N3845 W00908 N3830 W00752 N3700 W00800 1000FT AGL 340/014KT PS15 330/006KT PS17 "
    "280/010KT PS16 2000FT AGL 320/011KT PS14 270/007KT PS14 260/011KT PS15 5000FT AGL "
    "260/011KT PS09 230/012KT PS07 230/012KT PS10 FL100 310/013KT PS02 280/013KT PS02 "
    "290/012KT PS03 FL150 300/030KT MS08 300/028KT MS08 310/026KT MS07 FZLVL: 11300FT AMSL "
    "11000FT AMSL 11300FT AMSL MNM QNH:1010HPA=")

# Os 18 pontos em terra a norte de N4000 (leitura do piloto no relatório de 20-out)
NORTE_4000 = {"LPPR", "LPVR", "LPBG", "LPBR", "LPCH", "LPCO", "LPIN", "LPLZ", "LPMI",
              "LPMU", "LPSE", "LPVL", "LPVZ", "LP53", "LP55", "LP62", "LP66", "LP76"}


def _cod(nome):
    return nome.rsplit("(", 1)[1].rstrip(")")


def _nota(r):
    notas = [(t, x) for t, x in r["avisos"] if "Nuvens baixas na Secção II" in x]
    assert len(notas) <= 1
    return notas[0] if notas else None


def _decisoes(eng, r):
    return {n: eng.find_region_for_point(r["regioes"], la, lo)["decision"]
            for n, (la, lo) in eng.AERODROMES.items()}


def test_gamet_real_192100_da_nota_com_os_aerodromos_certos(eng):
    conteudo, nuvens = eng.nuvens_baixas_secn2(G192100)
    assert conteudo.startswith("00/03 N OF N4000 LAN SCT ST 004")
    assert len(nuvens) == 1
    base, ref, janela, sup, pontos, lida, lca = nuvens[0]
    assert (base, ref, sup, lida, lca) == (400, "AGL", "LAN", True, False)
    assert janela.startswith("00")
    assert {_cod(p) for p in pontos} == NORTE_4000


def test_gamet_real_192100_decisao_nao_muda(eng):
    """A nota é só informativa: tudo GO, como na 3.5."""
    r = eng.analisar_gamet(G192100, "manual", agora=AGORA)
    assert set(_decisoes(eng, r).values()) == {"GO"}
    tipo, txt = _nota(r)
    assert tipo == "info"
    assert "não altera" in txt and "400 ft AGL" in txt
    assert "LPPR" in txt and "LPPT" not in txt


def test_sem_nota_quando_a_secn2_nao_tem_base_baixa(eng):
    g = G192100.replace("SCT ST 004-008/012HFT", "SCT ST 006-008/012HFT")
    assert eng.nuvens_baixas_secn2(g)[1] == []
    assert _nota(eng.analisar_gamet(g, "manual", agora=AGORA)) is None


def test_sem_secn2_ou_cld_nil(eng):
    assert eng.nuvens_baixas_secn2("LPPC GAMET VALID 192100/200300 SECN I HAZARDOUS WX NIL=") \
        == ("", [])
    g = G192100.split("CLD:")[0] + "CLD: NIL WIND/T:" + G192100.split("WIND/T:", 1)[1]
    assert eng.nuvens_baixas_secn2(g) == ("", [])


def test_regioes_iguais_com_e_sem_a_cld_da_secn2(eng):
    """O CLD da Secção II nunca entra em compute_dynamic_regions."""
    sem = G192100.split("CLD:")[0] + "WIND/T:" + G192100.split("WIND/T:", 1)[1]
    a = eng.analisar_gamet(G192100, "manual", agora=AGORA)
    b = eng.analisar_gamet(sem, "manual", agora=AGORA)
    assert _decisoes(eng, a) == _decisoes(eng, b)
    assert a["por_dec"] == b["por_dec"]


def test_secn1_continua_a_mandar(eng):
    """Com SIG CLD na Secção I a decisão vem dela; a nota da II acrescenta-se."""
    g = G192100.replace("HAZARDOUS WX NIL",
                        "SIG CLD:S OF N3900 LAN BKN ST 002/008HFT AGL")
    r = eng.analisar_gamet(g, "manual", agora=AGORA)
    d = _decisoes(eng, r)
    assert d["Faro (LPFR)"] == "NO-GO"
    assert d["Porto (LPPR)"] == "GO"
    assert _nota(r) is not None


def test_base_amsl_conta_contra_o_relevo(eng):
    """Base AMSL baixa: só os pontos onde fica < 500 ft acima do MEF."""
    g = G192100.replace("SCT ST 004-008/012HFT", "SCT ST 004-008/012HFT AMSL")
    _, nuvens = eng.nuvens_baixas_secn2(g)
    for base, ref, *_resto in nuvens:
        assert ref == "AMSL"
    pontos = {p for n in nuvens for p in n[4]}
    for p in pontos:
        la, lo = eng.AERODROMES[p]
        assert 400 - eng._terrain_elevation_ft(lo, la) < 500


def test_area_ilegivel_na_secn2_marca_toda_a_fir(eng):
    g = G192100.replace("00/03 N OF N4000 LAN SCT ST", "00/03 NW OF N4000 LAN SCT ST")
    _, nuvens = eng.nuvens_baixas_secn2(g)
    assert nuvens and nuvens[0][5] is False
    assert len(nuvens[0][4]) == len(eng.AERODROMES)
    assert "área não reconhecida" in _nota(eng.analisar_gamet(g, "manual", agora=AGORA))[1]


def test_lca_aparece_na_nota(eng):
    g = G192100.replace("LAN SCT ST 004", "LAN LCA SCT ST 004")
    _, nuvens = eng.nuvens_baixas_secn2(g)
    assert nuvens and nuvens[0][6] is True
    assert "LCA" in _nota(eng.analisar_gamet(g, "manual", agora=AGORA))[1]
