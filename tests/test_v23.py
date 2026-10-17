"""
2.3 — Qualificadores seguidos sem AND e janela horária de subentradas.

GAMETs reais (recolhidos a 16 e 17-out-2026) que expuseram os dois erros:

1. "BTN N3840 AND N4100 E OF W00800" (162100/170300) e
   "BTN N3840 AND N4100 W OF W00800" (170300/170900): sem AND entre o BTN e o
   E/W OF, a injecção de quebras partia a linha e o BTN perdia-se. O
   nevoeiro e as nuvens a 100–200 ft passavam a cobrir todo o E (ou W) de
   8°W, do Algarve a Trás-os-Montes: Faro, Beja, Bragança, Portimão… NO-GO
   sem razão (erro pessimista).
2. "SIG CLD:09/11 … BKN 003 … 12/15 N OF N4000 … ISOL TCU/CB" (160900/161500):
   a janela "12/15" ficava no fim da linha anterior e o CB era mostrado
   como "apenas 09–11Z" (e "já terminou" à hora em que estava previsto).
"""
from conftest import build_gamet

GAMET_160900 = (
    'LPPC GAMET VALID 160900/161500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:09/11 N OF N3920 AND W OF W00815 LCA 1500-5000M BR 13/15 N OF N4000 AND E OF W00740 '
    'LCA 5000 RA SIGWX:13/15 N OF N4000 AND E OF W00740 ISOL TS SIG CLD:09/11 N OF N3920 AND '
    'W OF W00815 LCA BKN 003-008/010HFT AGL 12/15 N OF N4000 AND E OF W00740 ISOL TCU/CB '
    '030-045/XXXHFT AGL TURB: N OF N3800 COT AND MAR LCA MOD/SEV SFC/FL025 SIGMET APPLICABLE:'
    ' AT TIME OF ISSUE NIL SECN II PSYS:12 N4030 W01545 H 1027HPA STNR NC CLD:N OF N3800 '
    'FEW/SCT SC/CU 012-035/040-050HFT AGL 11/15 LAN FEW/SCT AC/AS 060-090/120-150HFT AMSL '
    'WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 250/007KT'
    ' PS20 360/008KT PS19 230/005KT PS21 2000FT AGL 250/007KT PS17 360/011KT PS20 240/004KT '
    'PS18 5000FT AGL 260/009KT PS09 240/005KT PS14 250/007KT PS10 FL100 260/009KT PS03 '
    '230/012KT PS03 250/005KT PS03 FL150 240/010KT MS06 280/009KT MS06 270/003KT MS06 FZLVL: '
    '11200FT AMSL 11500FT AMSL 10900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700'
    ' W00800 1000FT AGL 020/008KT PS23 250/001KT PS24 110/009KT PS23 2000FT AGL 020/007KT '
    'PS21 290/001KT PS21 100/010KT PS20 5000FT AGL 030/009KT PS14 010/002KT PS13 050/009KT '
    'PS15 FL100 020/008KT PS03 060/008KT PS03 070/005KT PS04 FL150 350/004KT MS06 350/004KT '
    'MS05 300/006KT MS05 FZLVL: 11300FT AMSL 11800FT AMSL 12100FT AMSL MNM QNH:1020HPA='
)

GAMET_162100 = (
    'LPPC GAMET VALID 162100/170300 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:BTN N3840 AND N4100 E OF W00800 COT AND LAN LCA 0300-5000M FG/BR SIG CLD:BTN N3840 '
    'AND N4100 E OF W00800 COT AND LAN LCA BKN 002-008/010HFT AGL SIGMET APPLICABLE: AT TIME '
    'OF ISSUE NIL SECN II PSYS:00 N5000 W01400 H 1037HPA STNR NC CLD:SCT/BKN SC/CU '
    '012-030/045HFT AGL N OF N3900 SCT/BKN AC/AS 060-090/100-130HFT AMSL WIND/T: BRAGANCA '
    'PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL 060/017KT PS14 060/005KT '
    'PS19 320/003KT PS18 2000FT AGL 090/013KT PS13 030/007KT PS19 270/002KT PS17 5000FT AGL '
    '170/001KT PS08 040/006KT PS14 170/003KT PS10 FL100 240/009KT PS02 320/010KT PS02 '
    '220/008KT PS03 FL150 280/006KT MS07 280/010KT MS08 300/010KT MS09 FZLVL: 11200FT AMSL '
    '11500FT AMSL 11600FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 W00752 N3700 W00800 '
    '1000FT AGL 360/021KT PS22 360/013KT PS23 040/011KT PS25 2000FT AGL 020/011KT PS21 '
    '010/008KT PS21 050/007KT PS23 5000FT AGL 320/004KT PS14 060/003KT PS13 040/008KT PS15 '
    'FL100 290/005KT PS03 350/004KT PS03 010/002KT PS03 FL150 350/012KT MS06 350/006KT MS06 '
    '330/009KT MS05 FZLVL: 12100FT AMSL 11000FT AMSL 12100FT AMSL MNM QNH:1018HPA='
)

GAMET_170300 = (
    'LPPC GAMET VALID 170300/170900 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I SFC '
    'VIS:N OF N3840 AND W OF W00800 COT AND LAN LCA 0200-5000M FG/BR SIG CLD:BTN N3840 AND '
    'N4100 W OF W00800 COT AND LAN LCA BKN 001-008/010HFT AGL N OF N4100 AND E OF W00800 '
    'ISOL/EMBD TCU/CB 025-035/XXXHFT AGL TURB:N OF N4100 LAN LCA MOD SFC/FL070 SIGMET '
    'APPLICABLE: AT TIME OF ISSUE NIL SECN II PSYS:06 NIL CLD:N OF LINE N3600 W01000 - N4000 '
    'W00700 SCT/BKN SC/CU 012-030/045HFT AGL LAN N OF N3900 SCT/BKN AC/AS 060-090/100-130HFT '
    'AMSL WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 1000FT AGL '
    '060/018KT PS11 090/007KT PS18 050/017KT PS17 2000FT AGL 070/021KT PS10 100/009KT PS18 '
    '100/009KT PS16 5000FT AGL 150/001KT PS06 080/003KT PS13 180/003KT PS09 FL100 240/007KT '
    'PS01 310/009KT PS01 310/005KT PS02 FL150 250/010KT MS08 340/016KT MS08 300/011KT MS10 '
    'FZLVL: 10500FT AMSL 10700FT AMSL 10900FT AMSL LISBOA EVORA FARO N3845 W00908 N3830 '
    'W00752 N3700 W00800 1000FT AGL 350/023KT PS19 360/008KT PS22 170/002KT PS23 2000FT AGL '
    '360/013KT PS20 350/002KT PS20 030/001KT PS21 5000FT AGL 280/008KT PS14 280/005KT PS12 '
    '350/007KT PS14 FL100 350/009KT PS03 340/006KT PS02 020/008KT PS02 FL150 330/018KT MS07 '
    '330/012KT MS07 330/012KT MS06 FZLVL: 11300FT AMSL 11000FT AMSL 11300FT AMSL MNM '
    'QNH:1018HPA='
)


def _dec(eng, regioes, nome):
    la, lo = eng.AERODROMES[nome]
    return eng.find_region_for_point(regioes, la, lo)["decision"]


def _blocos(r, fen):
    return [b for b in r["blocks"] if b.phenomenon == fen]


# ── 1. BTN seguido de E/W OF sem AND ─────────────────────────────────
def test_162100_btn_e_of_e_uma_so_area(eng, analyse):
    r = analyse(GAMET_162100)
    for fen in ("VIS", "BASE_AGL"):
        (b,) = _blocos(r, fen)
        minx, miny, maxx, maxy = b.polygon.bounds
        assert abs(miny - (38 + 40 / 60)) < 0.01, fen
        assert abs(maxy - 41.0) < 0.01, fen
        assert minx >= -8.0 - 1e-6, fen


def test_162100_decisoes_por_aerodromo(eng, analyse):
    r = analyse(GAMET_162100)
    # Dentro da faixa 38°40'–41°N a leste de 8°W: base 200 ft → NO-GO
    for nome in ("Castelo Branco (LPCB)", "Proença-a-Nova (LPPN)",
                 "Viseu (LPVZ)", "Seia (LPSE)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome
    # Fora da faixa (a sul de 38°40'N ou a norte de 41°N): nada previsto
    for nome in ("Faro (LPFR)", "Beja (LPBJ)", "Évora (LPEV)",
                 "Bragança (LPBG)", "Chaves (LPCH)", "Vila Real (LPVR)"):
        assert _dec(eng, r["regions"], nome) == "GO", nome


def test_170300_decisoes_por_aerodromo(eng, analyse):
    r = analyse(GAMET_170300)
    (base,) = [b for b in _blocos(r, "BASE_AGL") if b.value == 100]
    assert abs(base.polygon.bounds[1] - (38 + 40 / 60)) < 0.01
    assert abs(base.polygon.bounds[3] - 41.0) < 0.01
    # Faixa 38°40'–41°N a oeste de 8°W: base 100 ft → NO-GO
    for nome in ("Lisboa (LPPT)", "Coimbra (LPCO)", "Leiria (LPJF)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome
    # A norte de 41°N, a W de 8°W: só o nevoeiro LCA → MARGINAL
    for nome in ("Porto (LPPR)", "Braga (LPBR)"):
        assert _dec(eng, r["regions"], nome) == "MARGINAL", nome
    # CB ISOL/EMBD a norte de 41°N e a E de 8°W → NO-GO
    for nome in ("Bragança (LPBG)", "Chaves (LPCH)", "Vila Real (LPVR)"):
        assert _dec(eng, r["regions"], nome) == "NO-GO", nome
    # Alentejo e Algarve, a sul de 38°40'N: GO
    for nome in ("Faro (LPFR)", "Portimão (LPPM)", "Ferreira do Alentejo (LPFA)",
                 "Beja (LPBJ)", "Évora (LPEV)"):
        assert _dec(eng, r["regions"], nome) == "GO", nome


def test_qualificadores_seguidos_sem_and_sao_interseccao(analyse):
    com_and = analyse(build_gamet(
        "SECN I SIG CLD:N OF N4000 AND E OF W00800 BKN 002HFT AGL"))
    sem_and = analyse(build_gamet(
        "SECN I SIG CLD:N OF N4000 E OF W00800 BKN 002HFT AGL"))
    (a,) = com_and["blocks"]
    (b,) = sem_and["blocks"]
    assert a.polygon.symmetric_difference(b.polygon).area < 1e-9


# ── 2. Janela horária de cada subentrada ─────────────────────────────
def test_160900_janela_do_cb_e_12_15(analyse):
    r = analyse(GAMET_160900)
    (cb,) = _blocos(r, "CB")
    assert cb.window == "12–15Z"
    bases = {b.value: b.window for b in _blocos(r, "BASE_AGL")}
    assert bases == {300: "09–11Z", 3000: "12–15Z"}
    (ts,) = _blocos(r, "TS")
    assert ts.window == "13–15Z"


def test_janela_no_inicio_do_campo_continua_a_funcionar(analyse):
    r = analyse(build_gamet(
        "SECN I SIGWX:13/15 N OF N4000 ISOL TS "
        "SIG CLD:09/11 N OF N3920 LCA BKN 003HFT AGL 12/15 S OF N3800 ISOL TCU/CB "
        "030/XXXHFT AGL TURB: MOD SFC/FL050"))
    (ts,) = _blocos(r, "TS")
    assert ts.window == "13–15Z"
    janelas = {b.value: b.window for b in _blocos(r, "BASE_AGL")}
    assert janelas == {300: "09–11Z", 3000: "12–15Z"}
    (turb,) = _blocos(r, "TURB")
    assert turb.window == ""


def test_subentrada_sem_janela_nao_herda_a_anterior(analyse):
    r = analyse(build_gamet(
        "SECN I SIG CLD:09/11 N OF N3920 LCA BKN 003HFT AGL "
        "12/15 N OF N4000 ISOL TCU/CB 030/XXXHFT AGL S OF N3800 OVC 002/010HFT AGL"))
    janelas = {b.value: b.window for b in _blocos(r, "BASE_AGL")}
    assert janelas == {300: "09–11Z", 3000: "12–15Z", 200: ""}


def test_janela_logo_a_seguir_aos_dois_pontos(analyse):
    for corpo in ("SECN I SFC VIS:13/15 N OF N4000 LCA 1200M BR",
                  "SECN I SFC VIS: 13/15 N OF N4000 LCA 1200M BR",
                  "SECN I SFC VIS:13/15 LCA 1200M BR"):
        (b,) = _blocos(analyse(build_gamet(corpo)), "VIS")
        assert b.window == "13–15Z", corpo
