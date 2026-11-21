"""
7.0 — GO condicional (decisão do Duarte a 21-nov-2026: "não faz sentido nenhum
dar NO-GO quando o piloto vai voar muito abaixo dessa altitude").

TURB/ICE/MTW severos com o limite inferior ESCRITO a partir do FL100 — no
GAMET (`ICE: LCA MOD/SEV ABV FL120`) ou num SIGMET só de TURB/ICE/MTW SEV (a
lista branca da 6.0, `SEV ICE … FL120/210`) — dão GO COND. (entre GO e
MARGINAL) com o tecto 1000 ft abaixo do limite ("GO abaixo do FL110"). Abaixo
do FL100, sem limite inferior, mais de um nível na mesma linha, ou outro
fenómeno → como até à 6.1. A decisão "forçada" (regra desligada:
`_COND_MIN_FL` inatingível) é a da 6.1 e serve de referência: a 7.0 só pode
ser menos severa onde há um motivo condicional, e nunca abaixo de GO COND.
"""
import json
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet
from test_v60 import _decisoes, _gamet, _ipma, _u02_com, U02

DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "GO COND.": 0.5, "MARGINAL": 1, "NO-GO": 2}

# SIGMET real I01 de 17-nov-2026 (gelo severo FL120/210 no Minho)
I01 = ("LPPC SIGMET I01 VALID 171745/172145 LPPT- LPPC LISBOA FIR SEV ICE FCST WI "
       "N4138 W00958 - N42 W00950 - N4153 W00850 - N4211 W00808 - N4150 W00801 - "
       "N4119 W00822 - N4138 W00958 FL120/210 STNR NC")


def _desligada(eng, mp):
    """A regra da 7.0 desligada: o comportamento da 6.1."""
    mp.setattr(eng, "_COND_MIN_FL", 10 ** 6)


def _dec(eng, ev):
    return eng.decision(ev)


# ---------------------------------------------------------------- camadas

@pytest.mark.parametrize("camada, inferior", [
    ("ABV FL100", 100), ("ABV FL120", 120), ("FL120/FL150", 120), ("FL150/FL120", 120),
    ("ABV FL100 INTSF", 100), ("ABV FL090", 90),
    ("SFC/FL070", None), ("", None), ("BLW FL100", None), ("SFC/3000FT", None),
    ("ABV FL100 SFC/FL050", None), ("FL100/150", None), ("ABV FL100 MOV E 10KT", None),
])
def test_inferior_camada(eng, camada, inferior):
    assert eng.inferior_camada(camada) == inferior


# ---------------------------------------------------------------- decision()

@pytest.mark.parametrize("tipo", ["ICE", "TURB"])
def test_sev_a_partir_do_fl100_da_go_cond(eng, tipo):
    d, *_, motivos = _dec(eng, [(tipo, "SEV", "LCA", "ABV FL100")])
    assert d == "GO COND."
    assert motivos == [f"{tipo} SEV ABV FL100 — risco severo — GO abaixo do FL090"]


@pytest.mark.parametrize("camada", ["ABV FL090", "ABV FL095", "SFC/FL070", "", "ABV FL100 SFC/FL050",
                                    "BLW FL120"])
def test_sev_abaixo_do_fl100_ou_por_ler_continua_no_go(eng, camada):
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", camada)])
    assert d == "NO-GO"
    assert not any("GO abaixo" in m for m in motivos)


def test_tecto_e_o_mais_baixo(eng):
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", "ABV FL120"), ("ICE", "SEV", "", "FL100/FL150")])
    assert d == "GO COND."
    assert motivos[-1].endswith("GO abaixo do FL090")


def test_uma_sev_baixa_basta_para_no_go(eng):
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", "ABV FL120"), ("ICE", "SEV", "", "SFC/FL050")])
    assert d == "NO-GO"


def test_outro_motivo_mais_grave_prevalece_e_o_tecto_fica(eng):
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", "ABV FL120"), ("VIS", 3000, "", "")])
    assert d == "MARGINAL"
    assert any(m.endswith("GO abaixo do FL110") for m in motivos)
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", "ABV FL120"), ("TURB", "SEV", "", "SFC/FL060")])
    assert d == "NO-GO"
    d, *_, motivos = _dec(eng, [("ICE", "SEV", "", "ABV FL120"), ("TURB", "MOD", "", "SFC/FL050")])
    assert d == "GO COND."


def test_mtw(eng):
    assert _dec(eng, [("MTW", "SEV", "", "ABV FL100")])[0] == "GO COND."
    d = _dec(eng, [("MTW", "SEV", "", "ABV FL100"), ("MTW", "MOD", "", "SFC/FL050")])
    assert d[0] == "MARGINAL" and any(m.endswith("GO abaixo do FL090") for m in d[-1])
    assert _dec(eng, [("MTW", "SEV", "", "SFC/FL080")])[0] == "NO-GO"


def test_sem_nada_continua_go(eng):
    assert _dec(eng, [])[0] == "GO"


# ---------------------------------------------------------------- GAMET

def _pontos_dec(eng, texto, mp=None):
    r = eng.analisar_gamet(texto, "manual")
    return _decisoes(eng, r["regioes"]), r


def test_gamet_gelo_abv_fl120_em_toda_a_fir(eng):
    d, r = _pontos_dec(eng, build_gamet("SECN I ICE: LCA MOD/SEV ABV FL120"))
    assert set(d.values()) == {"GO COND."}
    assert all(any(m.endswith("GO abaixo do FL110") for m in g["reasons"]) for g in r["regioes"])


def test_gamet_gelo_so_a_norte(eng):
    d, _ = _pontos_dec(eng, build_gamet("SECN I ICE: N OF N3900 LCA MOD/SEV ABV FL100"))
    lat = dict((n, la) for n, (la, lo) in eng.AERODROMES.items())
    for n, dec in d.items():
        assert dec == ("GO COND." if lat[n] > 39.05 else "GO") or abs(lat[n] - 39) < 0.05, (n, dec)


@pytest.mark.parametrize("campo", [
    "ICE: LCA MOD/SEV ABV FL090",                 # 14 GAMETs reais: abaixo do FL100
    "ICE: LCA SEV ABV FL120 SFC/FL050",           # dois níveis na mesma linha
    "ICE: LCA SEV ABV FL120 MOD SFC/FL040",
    "TURB: LCA MOD/SEV SCF/FL060",                # gralha real (162100 de 16-nov): por ler
    "TURB: LCA MOD/SEV SFC/FL070",
    "ICE: LCA SEV FL100/150",                     # 2.º nível sem FL: não é camada
])
def test_gamet_continua_no_go(eng, campo, monkeypatch):
    g = build_gamet("SECN I " + campo)
    d, _ = _pontos_dec(eng, g)
    with monkeypatch.context() as mp:
        _desligada(eng, mp)
        df, _ = _pontos_dec(eng, g)
    assert set(d.values()) == {"NO-GO"} and d == df


def test_gamet_real_170900(eng, monkeypatch):
    """GAMET real 170900/171500 de 17-nov: `ICE: N OF N3900 LCA MOD/SEV ABV
    FL120` com BASE 400 ft e VIS 800 m LCA em toda a FIR — continua NO-GO,
    mas o motivo do gelo passa a dizer o tecto."""
    f = DADOS / "gamets/2026/11/20261117T0848Z_170900-171500_8a41d3e169.txt"
    if not f.exists():
        pytest.skip("sem dados/")
    t = f.read_text(encoding="utf-8")
    d, r = _pontos_dec(eng, t)
    assert set(d.values()) == {"NO-GO"}
    assert any("ICE SEV ABV FL120 — risco severo — GO abaixo do FL110" in g["reasons"]
               for g in r["regioes"])


# ---------------------------------------------------------------- SIGMET

def test_sigmet_i01_real(eng, monkeypatch):
    """SIGMET real I01 de 17-nov (SEV ICE FL120/210): GO COND. na área (+10 NM),
    GO fora; faixa e aviso dizem o tecto. Com a regra desligada era NO-GO."""
    from datetime import datetime, timezone
    agora = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
    g = build_gamet("SECN I SIGWX: NIL", validity="171500/172100")
    r = eng.analisar_gamet(g, "ipma", boletins=[I01], boletins_at=agora, agora=agora)
    d = _decisoes(eng, r["regioes"])
    with monkeypatch.context() as mp:
        _desligada(eng, mp)
        rf = eng.analisar_gamet(g, "ipma", boletins=[I01], boletins_at=agora, agora=agora)
    df = _decisoes(eng, rf["regioes"])
    mudam = {n for n in d if d[n] != df[n]}
    assert mudam and all(df[n] == "NO-GO" and d[n] == "GO COND." for n in mudam)
    assert set(d.values()) == {"GO", "GO COND."}
    assert {n for n in d if d[n] == "GO COND."} == {n for n in df if df[n] == "NO-GO"}
    assert r["faixa_sig"] == ("≥ FL120", "GO COND.")
    av = [txt for t, txt in r["avisos"] if "SIGMET" in txt and "GO" in txt]
    assert any("GO condicional abaixo do FL110" in a for a in av)
    motivos = {m for x in r["regioes"] for m in x["reasons"]}
    assert any(m.startswith("SIGMET I01 (SEV ICE)") and m.endswith("GO abaixo do FL110")
               for m in motivos)


@pytest.mark.parametrize("niveis, esperado, tecto", [
    ("FL100/190", "GO COND.", "FL090"),
    ("FL150/250", "GO COND.", "FL140"),
    ("FL195/300", "GO COND.", "FL185"),
    ("FL196/300", "GO", None),           # acima do FL195: informativo (6.0)
    ("FL090/250", "NO-GO", None),
    ("SFC/FL100", "NO-GO", None),
    ("FL150/250 AND FL050/120", "NO-GO", None),
])
def test_sigmet_niveis(eng, niveis, esperado, tecto):
    r = _ipma(eng, _gamet(), [_u02_com(niveis)])
    vals = set(_decisoes(eng, r["regioes"]).values())
    assert esperado in vals and vals <= {"GO", esperado}
    if tecto:
        assert any(m.endswith(f"GO abaixo do {tecto}") for x in r["regioes"] for m in x["reasons"])


@pytest.mark.parametrize("fen", ["SEV ICE", "SEV MTW"])
def test_sigmet_outros_fenomenos_da_lista(eng, fen):
    r = _ipma(eng, _gamet(), [_u02_com("FL120/250", fen)])
    assert "GO COND." in _decisoes(eng, r["regioes"]).values()


@pytest.mark.parametrize("fen", ["EMBD TS", "VA CLD", "SEV TURB OCNL TSRA"])
def test_sigmet_fora_da_lista_continua_no_go(eng, fen):
    r = _ipma(eng, _gamet(), [_u02_com("FL120/250", fen)])
    assert "NO-GO" in _decisoes(eng, r["regioes"]).values()
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_sigmet_cond_com_outro_no_go(eng):
    r = _ipma(eng, _gamet(), [_u02_com("FL150/250"), _u02_com("SFC/FL100", sid="U03")])
    assert "NO-GO" in _decisoes(eng, r["regioes"]).values()
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")


def test_sigmet_cond_e_alto(eng):
    r = _ipma(eng, _gamet(), [_u02_com("FL150/250"), U02.replace("U02", "U03")])
    assert r["faixa_sig"] == ("≥ FL150", "GO COND.")


def test_sigmet_applicable_com_texto(eng):
    g = _gamet(sigmet="U02")
    r = _ipma(eng, g, [_u02_com("FL150/250")])
    assert any(t == "aviso" and "O GAMET refere o SIGMET" in txt and "FL140" in txt
               for t, txt in r["avisos"])


def test_sigmet_applicable_sem_texto_continua_no_go_em_toda_a_area(eng):
    r = eng.analisar_gamet(_gamet(sigmet="U02"), "manual")
    assert set(_decisoes(eng, r["regioes"]).values()) == {"NO-GO"}


# ---------------------------------------------------------------- briefing

def test_classificar_motivo(eng):
    for m, linha in [("ICE SEV ABV FL120 — risco severo — GO abaixo do FL110", "ICE"),
                     ("TURB SEV FL100/FL150 — risco severo — GO abaixo do FL090", "TURB"),
                     ("MTW SEV ABV FL100 (onda de montanha) — risco severo — GO abaixo do FL090", "MTW"),
                     ("SIGMET I01 (SEV ICE) — WI … + 10 NM — GO abaixo do FL110", "SIGMET")]:
        c = eng.classificar_motivo(m)
        assert (c["linha"], c["nivel"]) == (linha, "GO COND."), m
        assert eng.motivo_legivel(c).endswith("→ GO COND.")
        assert "abaixo de FL" in eng.motivo_legivel(c)


def test_cor_azul_no_mapa_e_legenda(eng):
    assert eng._DEC_BARRA["GO COND."].upper() == "#3B82F6"
    r = eng.analisar_gamet(build_gamet("SECN I ICE: N OF N3900 LCA MOD/SEV ABV FL100"), "manual")
    ordem = eng.zonas_ordem(r["regioes"])
    html = eng.mapa_zonas(r["regioes"], ordem, None, None).get_root().render()
    assert "#3B82F6" in html and "GO COND." in html
    assert "GO COND." in eng.html_legenda_mapa()


def test_quadro_e_painel(eng):
    r = eng.analisar_gamet(build_gamet("SECN I ICE: LCA MOD/SEV ABV FL120"), "manual")
    linhas, _ = eng.quadro_zonas(r["regioes"])
    gelo = [c for rot, cels in linhas if rot == "Gelo" for c in cels if c]
    assert gelo and all(c["nivel"] == "GO COND." for c in gelo)
    assert "abaixo de FL110" in eng.html_zona(1, r["regioes"][0], 100, r["regioes"])


def test_comparar_piloto_le_go_cond():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import comparar_piloto as cp
    for x in ("GO COND.", "GO condicional", "**GO COND**", "GO-COND"):
        assert cp.ler_decisao(x) == "GO COND."
    assert cp.ler_decisao("GO COND. / GO") is None
    assert cp.GRAVIDADE["GO"] < cp.GRAVIDADE["GO COND."] < cp.GRAVIDADE["MARGINAL"]


# ---------------------------------------------------------------- arquivo

def _arquivo():
    if not (DADOS / "gamets").exists():
        pytest.skip("sem dados/")
    return sorted((DADOS / "gamets").rglob("*.txt"))


# GAMETs do arquivo com TURB/ICE/MTW SEV a partir do FL100 (a 21-nov-2026).
# Se aparecer outro, confirma a leitura e junta-o aqui.
COND_70 = {
    "20261108T0850Z_080900-081500_189d1079bf.txt",
    "20261108T1451Z_081500-082100_73bc1f4fc4.txt",
    "20261116T0843Z_160900-161500_b4a5e06183.txt",
    "20261116T1444Z_161500-162100_40795fde32.txt",
    "20261116T2045Z_162100-170300_89141ca089.txt",
    "20261117T0246Z_170300-170900_9f8fa36615.txt",
    "20261117T0848Z_170900-171500_8a41d3e169.txt",
    "20261117T2050Z_172100-180300_d3ce7a76be.txt",
    "20261118T0252Z_180300-180900_a89825f2bc.txt",
    "20261118T0853Z_180900-181500_c605aecd70.txt",
}


def test_arquivo_conjunto_fixo(eng):
    com = {f.name for f in _arquivo() if conftest.cond_70(eng, f.read_text(encoding="utf-8"))}
    assert com == COND_70


def _comparar(eng, monkeypatch, fonte, indice=None):
    entradas = {e.get("ficheiro"): e for e in (indice or {}).get("gamets", [])}
    menos, n = [], 0
    for f in _arquivo():
        t = f.read_text(encoding="utf-8")
        kw = {}
        if fonte == "arquivo_hist":
            ent = entradas.get(str(f.relative_to(DADOS)))
            if not ent:
                continue
            kw = dict(indice=indice, entrada=ent)
        r = eng.analisar_gamet(t, fonte, **kw)
        with monkeypatch.context() as mp:
            _desligada(eng, mp)
            rf = eng.analisar_gamet(t, fonte, **kw)
        d, df = _decisoes(eng, r["regioes"]), _decisoes(eng, rf["regioes"])
        for p in d:
            if d[p] == df[p]:
                continue
            n += 1
            # Só menos severo, nunca abaixo de GO COND., e com um motivo condicional
            assert GRAV[d[p]] < GRAV[df[p]] and d[p] != "GO", (f.name, p, df[p], d[p])
            la, lo = eng.AERODROMES[p]
            reg = eng.find_region_for_point(r["regioes"], la, lo)
            assert any(" — GO abaixo do FL" in m for m in reg["reasons"]), (f.name, p)
            menos.append((f.name, p))
    return menos


def test_arquivo_manual_so_menos_severo_onde_ha_tecto(eng, monkeypatch):
    menos = _comparar(eng, monkeypatch, "manual")
    assert {g for g, _ in menos} <= COND_70


def test_arquivo_hist_so_menos_severo_onde_ha_tecto(eng, monkeypatch):
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8")) \
        if (DADOS / "indice.json").exists() else pytest.skip("sem dados/")
    menos = _comparar(eng, monkeypatch, "arquivo_hist", indice)
    assert menos      # há SIGMETs FL100–FL195 no arquivo (I01 17-nov, U02 21-nov…)


# ---------------------------------------------------------------- revisão do agente parser
# Caminhos optimistas encontrados na 1.ª versão: todos têm de ficar iguais à
# regra desligada (a 6.1), nos 52 pontos.
_OPTIMISTAS = [
    "ICE: SEV ABV FL120 10/12 SFC/FL050",          # garantia (_domina)
    "ICE: SEV ABV FL120 LAN FL030/FL060",          # corte por superfície
    "ICE: SEV ABV FL120 MAR SFC/FL050 LCA",
] + [f"ICE: SEV ABV FL120 {x}" for x in (
    "SFC/050", "SFC/F050", "SFC-050", "030/060", "FL 030/060", "ABV FL 030", "F030/F060",
    "A030", "BLW A050", "SFC/A050", "SFC/1500M", "1500M", "SFC", "FRM SFC", "FZLVL SFC",
    "FZRA", "LLWS")] + [
    "TURB: SEV ABV FL100 BLW 300M",
    "ICE: SEV ABV FL120\n SFC/FL050",              # linha de continuação sem intensidade
    "ICE: N OF N4000 SEV ABV FL120 S OF N4000 SFC/FL050",
    "ICE: SEV ABV FL120 SFC WINDS: 35KT",          # campo desconhecido colado
]


@pytest.mark.parametrize("campo", _OPTIMISTAS)
def test_revisao_parser_igual_a_regra_desligada(eng, monkeypatch, campo):
    g = build_gamet("SECN I " + campo)
    d, r = _pontos_dec(eng, g)
    with monkeypatch.context() as mp:
        _desligada(eng, mp)
        df, _ = _pontos_dec(eng, g)
    assert d == df, {p: (df[p], d[p]) for p in d if d[p] != df[p]}
    assert "GO COND." not in d.values()


def test_revisao_parser_airmet_sintetico(eng, monkeypatch):
    from datetime import datetime, timezone
    agora = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
    air = ("LPPC AIRMET 1 VALID 171800/172200 LPPT- LPPC LISBOA FIR SEV ICE FCST N OF N4000 "
           "ABV FL120 SFC/050 STNR NC=")
    g = build_gamet("SECN I SIGWX: NIL", validity="171500/172100")
    def dec():
        r = eng.analisar_gamet(g, "ipma", boletins=[air], boletins_at=agora, agora=agora)
        return _decisoes(eng, r["regioes"])
    d = dec()
    with monkeypatch.context() as mp:
        _desligada(eng, mp)
        df = dec()
    assert d == df and "GO COND." not in d.values()


def test_campos_cond_ok(eng):
    assert eng.campos_cond_ok(build_gamet("SECN I ICE: N OF N3900 LCA MOD/SEV ABV FL120")) == {"ICE": True}
    assert eng.campos_cond_ok(build_gamet("SECN I ICE: LCA MOD/SEV ABV FL120 TURB: LCA MOD SFC/FL050")) \
        == {"ICE": True, "TURB": True}
    assert eng.campos_cond_ok(build_gamet("SECN I ICE: SEV ABV FL120 SFC/050")) == {"ICE": False}
    assert eng.campos_cond_ok(build_gamet("SECN I SIGWX: NIL")) == {}


def test_mtw_mod_com_a_sua_camada(eng):
    d, *_, motivos = _dec(eng, [("MTW", "SEV", "", "ABV FL100"), ("MTW", "MOD", "", "SFC/FL050")])
    assert d == "MARGINAL"
    assert "MTW MOD SFC/FL050 (onda de montanha)" in motivos


# ---------------------------------------------------------------- revisor do PR #66
def test_porque_mostra_o_tecto_mais_baixo(eng):
    """Duas zonas GO COND. com tectos diferentes: o porquê do veredicto diz o
    mais baixo (FL090), não o motivo comum (FL110)."""
    g = build_gamet("SECN I TURB: N OF N3900 SEV ABV FL120 ICE: N OF N4000 SEV ABV FL100")
    r = eng.analisar_gamet(g, "manual")
    tectos = {eng.tecto_regiao(x) for x in r["regioes"] if x["decision"] == "GO COND."}
    assert tectos == {90, 110}
    p = eng.porque_veredicto(r["regioes"], r["blocos"])
    assert p.startswith("GO abaixo do FL090 — ") and "FL110" not in p


def test_meu_aerodromo_e_zona_mostram_o_tecto(eng):
    r = eng.analisar_gamet(build_gamet("SECN I ICE: LCA MOD/SEV ABV FL120"), "manual")
    reg = r["regioes"][0]
    assert "GO COND. · abaixo do FL110" in eng.html_meu_aerodromo("Lisboa (LPPT)", 1, reg)
    assert "ABAIXO DO FL110" in eng.html_zona(1, reg, 100, r["regioes"])
    assert "abaixo do FL110" in eng.html_aerodromo("Lisboa (LPPT)", reg)


def test_chip_azul(eng):
    h = eng.html_chip("GO COND.")
    assert 'class="gv-chip gv-GO-COND"' in h
    assert ".gv-GO-COND" in eng._CSS if hasattr(eng, "_CSS") else True


def test_chip_azul_no_css(app_path):
    src = app_path.read_text(encoding="utf-8")
    assert ".gv-GO-COND  { background:#10223F; color:#8DB6FF;" in src


@pytest.mark.parametrize("fen", ["SEV ICE", "SEV TURB", "SEV MTW"])
def test_airmet_com_sev_continua_no_go(eng, monkeypatch, fen):
    """A regra é só para o GAMET e os SIGMETs (decisão do Duarte)."""
    from datetime import datetime, timezone
    agora = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
    air = (f"LPPC AIRMET 1 VALID 171800/172200 LPPT- LPPC LISBOA FIR {fen} FCST N OF N4000 "
           "ABV FL120 STNR NC=")
    g = build_gamet("SECN I SIGWX: NIL", validity="171500/172100")
    def dec():
        r = eng.analisar_gamet(g, "ipma", boletins=[air], boletins_at=agora, agora=agora)
        return _decisoes(eng, r["regioes"])
    d = dec()
    with monkeypatch.context() as mp:
        _desligada(eng, mp)
        df = dec()
    assert d == df and "GO COND." not in d.values() and "NO-GO" in d.values()
