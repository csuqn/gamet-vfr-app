"""
2.0 — Cumulonimbos em SIG CLD passam a contar para a decisão; bolsas
residuais do mesmo grupo juntam-se mesmo que não sejam contíguas.

GAMET real que expôs os dois problemas (recolhido a 2026-10-16T02:52Z):
"N OF N4000 AND E OF W00800 ISOL/EMBD TCU/CB 030-040/XXXHFT AGL" em SIG CLD,
sem TS em SIGWX. Até à 1.6, Bragança, Vila Real, Chaves, Viseu… saíam GO
sem menção ao CB, e aparecia um cartão GO de 45 km² junto ao Minho.

Regra aprovada pelo Duarte (opção b): CB isolado → MARGINAL; embebido,
ocasional ou frequente → NO-GO. TCU sozinho não altera a decisão.
"""
import pytest

from conftest import build_gamet

GAMET_160300 = (
    "LPPC GAMET VALID 160300/160900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
    "SECN I SFC VIS:N OF N3840 AND W OF W00810 LCA 0200-5000M FG/BR "
    "SIG CLD:N OF N3840 AND W OF W00810 LCA BKN 002-008/010HFT AGL "
    "N OF N4000 AND E OF W00800 ISOL/EMBD TCU/CB 030-040/XXXHFT AGL "
    "TURB:N OF N3800 COT AND MAR LCA MOD SFC/FL020 "
    "SIGMET APPLICABLE: AT TIME OF ISSUE NIL "
    "SECN II PSYS:06 N3940 W01500 H 1025HPA STNR NC "
    "CLD:N OF N3800 FEW/SCT SC/CU 012-030/040HFT AGL E OF W00730 FEW/SCT AC/AS "
    "060-090/100-130HFT AMSL "
    "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 "
    "1000FT AGL 270/005KT PS19 010/009KT PS19 270/002KT PS20 "
    "2000FT AGL 250/008KT PS17 350/010KT PS20 250/004KT PS19 "
    "5000FT AGL 250/009KT PS09 230/010KT PS15 210/004KT PS11 "
    "FL100 250/010KT PS03 230/013KT PS03 260/005KT PS03 "
    "FL150 250/012KT MS07 290/007KT MS06 300/007KT MS07 "
    "FZLVL: 11200FT AMSL 11500FT AMSL 10900FT AMSL "
    "LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 "
    "1000FT AGL 040/012KT PS22 080/002KT PS22 110/008KT PS22 "
    "2000FT AGL 050/007KT PS22 290/002KT PS21 110/015KT PS21 "
    "5000FT AGL 020/007KT PS14 040/002KT PS13 060/012KT PS14 "
    "FL100 010/010KT PS04 030/008KT PS03 040/009KT PS05 "
    "FL150 350/010KT MS05 330/004KT MS05 220/001KT MS04 "
    "FZLVL: 11300FT AMSL 11800FT AMSL 13000FT AMSL MNM QNH:1021HPA="
)

PONTOS_CB = ["Bragança (LPBG)", "Chaves (LPCH)", "Vila Real (LPVR)",
             "Mirandela (LPMI)", "Mogadouro (LPMU)", "Viseu (LPVZ)",
             "Seia (LPSE)", "Cabeceiras de Basto (LP53)", "Cabeço da Vaca (LP66)"]


def _regiao(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)


# ── GAMET real ───────────────────────────────────────────────────────
def test_gamet_real_cb_embebido_da_nogo(eng, analyse):
    r = analyse(GAMET_160300)
    cb = [b for b in r["blocks"] if b.phenomenon == "CB"]
    assert [b.value for b in cb] == ["ISOL_EMBD"]
    for nome in PONTOS_CB:
        reg = _regiao(eng, r["regions"], nome)
        assert reg["decision"] == "NO-GO", nome
        assert any(m.startswith("CB ISOL/EMBD") for m in reg["reasons"]), nome


def test_gamet_real_resto_inalterado(eng, analyse):
    """O CB não mexe no que já estava certo: costa NO-GO, Sul GO."""
    r = analyse(GAMET_160300)
    for nome in ("Porto (LPPR)", "Lisboa (LPPT)", "Coimbra (LPCO)", "Lousã (LPLZ)"):
        assert _regiao(eng, r["regions"], nome)["decision"] == "NO-GO", nome
    for nome in ("Évora (LPEV)", "Faro (LPFR)", "Ponte de Sor (LPSO)"):
        assert _regiao(eng, r["regions"], nome)["decision"] == "GO", nome


def test_gamet_real_sem_cartao_residual(eng, analyse):
    """A bolsa GO de 45 km² junto ao Minho junta-se à região GO principal."""
    r = analyse(GAMET_160300)
    limite = 0.015 * eng.FIR_POLYGON.area
    pequenas = [x for x in r["regions"] if x["polygon"].area < limite]
    assert not pequenas, [(x["label"], x["decision"]) for x in pequenas]
    total = sum(x["polygon"].area for x in r["regions"])
    assert abs(total / eng.FIR_POLYGON.area - 1) < 0.005


# ── Regra do CB em SIG CLD ───────────────────────────────────────────
@pytest.mark.parametrize("linha,decisao", [
    ("ISOL TCU/CB 030/XXXHFT AGL",       "MARGINAL"),
    ("ISOL CB 030/XXXHFT AGL",           "MARGINAL"),
    ("ISOL/EMBD TCU/CB 030/XXXHFT AGL",  "NO-GO"),
    ("EMBD CB 030/XXXHFT AGL",           "NO-GO"),
    ("OCNL CB 030/XXXHFT AGL",           "NO-GO"),
    ("FRQ TCU/CB 030/XXXHFT AGL",        "NO-GO"),
    ("CB 030/XXXHFT AGL",                "NO-GO"),   # sem qualificador → conservador
    ("ISOL TCU 030/XXXHFT AGL",          "GO"),      # TCU sozinho não conta
    ("OCNL TCU 030/XXXHFT AGL",          "GO"),
])
def test_cb_em_sig_cld(analyse, linha, decisao):
    r = analyse(build_gamet(f"SECN I SIG CLD: {linha}"))
    assert r["decisions"] == [decisao]
    assert r["ts"] == set()      # continua a não ser lido como trovoada


def test_cb_limitado_a_sua_area(eng, analyse):
    r = analyse(build_gamet("SECN I SIG CLD: N OF N4100 OCNL TCU/CB 025/XXXHFT AGL"))
    assert _regiao(eng, r["regions"], "Bragança (LPBG)")["decision"] == "NO-GO"
    assert _regiao(eng, r["regions"], "Faro (LPFR)")["decision"] == "GO"


def test_cb_com_ts_em_sigwx_continua_nogo(analyse):
    """Forma habitual do IPMA (TS em SIGWX + CB em SIG CLD): nada piora."""
    r = analyse(build_gamet("SECN I SIGWX: OCNL TS SIG CLD: OCNL TCU/CB 020/XXXHFT AGL"))
    assert r["decisions"] == ["NO-GO"]


def test_cb_respeita_janela_e_superficie(analyse):
    r = analyse(build_gamet("SECN I SIG CLD: 12/15 MAR ISOL/EMBD CB 030/XXXHFT AGL"))
    cb = [b for b in r["blocks"] if b.phenomenon == "CB"]
    assert cb and cb[0].window and cb[0].surface == "MAR"
    nogo = [x for x in r["regions"] if x["decision"] == "NO-GO"]
    assert nogo and any("CB" in n for x in nogo for n in x["notas"])


# ── Bolsas residuais ─────────────────────────────────────────────────
def test_bolsa_residual_de_outro_grupo_nao_se_mistura(eng):
    """Uma bolsa com causas diferentes não contígua continua à parte."""
    from shapely.geometry import box
    fir = eng.FIR_POLYGON
    a = fir.intersection(box(-10, 35, -7.5, 43))
    b = fir.intersection(box(-7.0, 41.8, -6.9, 41.85))   # pequena, isolada
    regs = [
        dict(polygon=a, label="A", decision="GO", notas=[], _grupo=0, vis=None,
             base=None, ts=[], turb=[], turb_layers=[], turb_parcial=False, ice=[],
             ice_layers=[], ice_parcial=False, mt_obsc=[], va=[], reasons=[]),
        dict(polygon=b, label="B", decision="GO", notas=["TURB: apenas 12–15Z"], _grupo=1,
             vis=None, base=None, ts=[], turb=["MOD"], turb_layers=[], turb_parcial=False,
             ice=[], ice_layers=[], ice_parcial=False, mt_obsc=[], va=[], reasons=[]),
    ]
    out = eng._merge_slivers(regs)
    assert len(out) == 2
