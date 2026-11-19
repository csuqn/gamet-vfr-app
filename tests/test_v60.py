"""
6.0 — SIGMET acima dos níveis VFR (decisão do Duarte a 19-nov-2026).

O VFR não se faz acima do FL195 (SERA.5005(d)(2)). Um SIGMET de SEV TURB,
SEV ICE ou SEV MTW cujo limite inferior ESCRITO está acima do FL195 não toca
num voo VFR: entra como bloco "SIGMET_ALTO", com o motivo "SIGMET <rot>
(acima dos níveis VFR)", classificado "INFO", sem mudar a decisão.

Continua NO-GO (leitura conservadora): limite inferior na superfície ou até ao
FL195, só o topo, níveis ilegíveis ou ausentes, TS, VA, duas camadas com uma
baixa, e o SIGMET só referido no GAMET sem o texto completo.

Caso real: SIGMET U02 de 19-nov-2026 (SEV TURB FCST … FL220/430 MOV E 40KT).
As expectativas vêm do significado do SIGMET (fenómeno e níveis escritos),
nunca do que o motor devolve.
"""
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import build_gamet

DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": 0, "MARGINAL": 1, "NO-GO": 2}
AGORA = datetime(2026, 11, 19, 17, 30, tzinfo=timezone.utc)
VALIDADE = "191500/192100"

_AREA_U02 = ("WI N3746 W01002 - N3822 W015 - N42 W015 - N3959 W00903 - N3746 W01002")
# SIGMET real U02 de 19-nov-2026
U02 = ("LPPC SIGMET U02 VALID 191700/192100 LPPT- LPPC LISBOA FIR SEV TURB FCST "
       f"{_AREA_U02} FL220/430 MOV E 40KT NC=")
# SIGMET real U01 de 19-nov-2026 (o anterior, já expirado às 17:30Z)
U01 = ("LPPC SIGMET U01 VALID 191500/191700 LPPT- LPPC LISBOA FIR SEV TURB FCST "
       f"{_AREA_U02} FL220/430 MOV E 40KT INTSF")


def _u02_com(niveis, fen="SEV TURB", sid="U02"):
    """O U02 real com outros níveis/fenómeno (mesma área e movimento)."""
    nv = f" {niveis}" if niveis else ""
    return (f"LPPC SIGMET {sid} VALID 191700/192100 LPPT- LPPC LISBOA FIR {fen} FCST "
            f"{_AREA_U02}{nv} MOV E 40KT NC=")


def _gamet(corpo="SIGWX: NIL", sigmet=None):
    return build_gamet("SECN I " + corpo, validity=VALIDADE, sigmet=sigmet)


def _ipma(eng, g, boletins):
    return eng.analisar_gamet(g, "ipma", boletins=boletins, boletins_at=AGORA, agora=AGORA)


def _pontos(eng):
    return dict(eng.AERODROMES)          # 52: aeródromos ICAO + pistas UL


def _decisoes(eng, regioes):
    out = {}
    for nome, (lat, lon) in _pontos(eng).items():
        g = eng.find_region_for_point(regioes, lat, lon)
        assert g is not None, f"{nome} fora de todas as regiões"
        out[nome] = g["decision"]
    return out


def _forcado(eng, monkeypatch):
    """Comportamento anterior à 6.0: todo o SIGMET completo é NO-GO."""
    monkeypatch.setattr(eng, "sigmet_acima_vfr", lambda texto: None)


# ---------------------------------------------------------------------
# Níveis
# ---------------------------------------------------------------------

@pytest.mark.parametrize("niveis, inferior", [
    ("FL220/430", 220),                 # U02 real
    ("FL220/FL430", 220),
    ("FL200/430", 200),
    ("FL196/300", 196),
    ("FL195/300", 195),                 # toca no FL195: VFR ainda lá voa
    ("FL150/250", 150),
    ("FL100/190", 100),
    ("FL050/120", 50),
    ("ABV FL250", 250),
    ("SFC/FL100", 0),
    ("SFC/FL050", 0),
    ("BLW FL250", 0),                   # sem limite inferior → superfície
    ("TOP FL340", 0),                   # só o topo → pode chegar ao solo
    ("TOP ABV FL300", 0),
    ("TOP BLW FL300", 0),
    ("SFC/3000FT", 0),
    ("3000/8000FT", 0),                 # pés: abaixo do FL195
    ("FL220/430 AND FL050/120", 50),    # duas camadas: a mais baixa
    ("FL220/430 TOP FL340", 0),
    ("", None),                         # sem níveis → por ler
    ("FL220", None),                    # nível sem limite inferior legível
])
def test_nivel_inferior_sigmet(eng, niveis, inferior):
    assert eng.nivel_inferior_sigmet(_u02_com(niveis)) == inferior


@pytest.mark.parametrize("fen, niveis, alto", [
    ("SEV TURB", "FL220/430", 220),
    ("SEV TURB", "FL200/430", 200),
    ("SEV TURB", "FL196/300", 196),
    ("SEV ICE", "FL220/300", 220),
    ("SEV MTW", "FL220/300", 220),
    ("SEV TURB", "ABV FL250", 250),
    # Continuam a contar (None)
    ("SEV TURB", "FL195/300", None),
    ("SEV TURB", "FL150/250", None),
    ("SEV TURB", "SFC/FL100", None),
    ("SEV TURB", "TOP FL340", None),
    ("SEV TURB", "TOP ABV FL300", None),
    ("SEV TURB", "BLW FL250", None),
    ("SEV TURB", "", None),
    ("SEV TURB", "FL220", None),
    ("SEV TURB", "FL220/430 AND FL050/120", None),
    ("SEV ICE (FZRA)", "FL050/120", None),
    ("EMBD TS", "FL220/430", None),
    ("OBSC TS", "FL220/430", None),
    ("FRQ TS", "FL220/430", None),
    ("SQL TS", "FL220/430", None),
    ("VA CLD", "FL220/430", None),
    ("HVY DS", "FL220/430", None),
    ("TC", "FL220/430", None),
    ("RDOACT CLD", "FL220/430", None),
])
def test_sigmet_acima_vfr(eng, fen, niveis, alto):
    assert eng.sigmet_acima_vfr(_u02_com(niveis, fen)) == alto


def test_sigmets_reais_de_19_nov(eng):
    assert eng.sigmet_acima_vfr(U02) == 220
    assert eng.sigmet_acima_vfr(U01) == 220


# ---------------------------------------------------------------------
# U02 real sozinho
# ---------------------------------------------------------------------

def test_u02_sozinho_toda_a_fir_go(eng):
    r = _ipma(eng, _gamet(), [U02])
    assert {g["decision"] for g in r["regioes"]} == {"GO"}
    assert set(_decisoes(eng, r["regioes"]).values()) == {"GO"}
    assert any(b.phenomenon == "SIGMET_ALTO" for b in r["blocos"])
    assert not any(b.phenomenon == "SIGMET" for b in r["blocos"])


def test_u02_motivo_info_onde_o_sigmet_poria_no_go(eng, monkeypatch):
    """Cada ponto que o U02 poria em NO-GO (comportamento anterior) fica GO na
    6.0, com o motivo do SIGMET presente e classificado INFO."""
    r = _ipma(eng, _gamet(), [U02])
    with monkeypatch.context() as mp:
        _forcado(eng, mp)
        rf = _ipma(eng, _gamet(), [U02])
    dec_f = _decisoes(eng, rf["regioes"])
    afectados = [n for n, d in dec_f.items() if d == "NO-GO"]
    assert afectados, "o U02 (MOV E 40KT + 10 NM) devia cobrir aeródromos"
    for nome in afectados:
        lat, lon = _pontos(eng)[nome]
        g = eng.find_region_for_point(r["regioes"], lat, lon)
        assert g["decision"] == "GO", nome
        cs = [eng.classificar_motivo(m) for m in g["reasons"]]
        sig = [c for c in cs if c["linha"] == "SIGMET"]
        assert sig and all(c["valor"] == "U02" and c["nivel"] == "INFO" for c in sig), \
            (nome, g["reasons"])


def test_u02_faixa_e_avisos(eng):
    r = _ipma(eng, _gamet(), [U02])
    assert r["faixa_sig"] == ("ACIMA FL195", None)
    tipos = [t for t, _ in r["avisos"]]
    sig = [(t, txt) for t, txt in r["avisos"] if "SIGMET" in txt]
    assert sig and all(t == "info" for t, _ in sig), sig
    assert any("acima dos níveis VFR" in txt for _, txt in sig)
    assert "erro" not in tipos, r["avisos"]


def test_u02_porque_veredicto_sem_o_sigmet(eng):
    r = _ipma(eng, _gamet(), [U02])
    assert eng.porque_veredicto(r["regioes"], r["blocos"]) == ""
    # Com um fenómeno que decide (VIS 3000 m → MARGINAL), o porquê é ele e
    # não o SIGMET alto.
    r = _ipma(eng, _gamet("SFC VIS: 3000M BR"), [U02])
    assert {g["decision"] for g in r["regioes"]} == {"MARGINAL"}
    p = eng.porque_veredicto(r["regioes"], r["blocos"])
    assert p and "U02" not in p and "SIGMET" not in p and "turbulência" not in p, p


def test_u02_painel_da_zona(eng):
    pytest.importorskip("folium")
    r = _ipma(eng, _gamet(), [U02])
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    zonas = [(z, regs[i]) for z, i in enumerate(ordem, 1)
             if any(eng.classificar_motivo(m)["linha"] == "SIGMET" for m in regs[i]["reasons"])]
    assert zonas
    for z, reg in zonas:
        h = eng.html.unescape(eng.html_zona(z, reg, 30.0, regs, (), None, r["blocos"]))
        assert "acima dos níveis VFR" in h
        assert "GO" in h and "NO-GO" not in h
    cs = [eng._com_info_sigmet(eng.classificar_motivo(m), r["blocos"])
          for _, reg in zonas for m in reg["reasons"]]
    sig = [c for c in cs if c["linha"] == "SIGMET"]
    assert all(c["nivel"] == "INFO" for c in sig)
    assert all("turbulência severa" in c.get("longo", "") for c in sig)


def test_u01_expirado_e_u02_em_vigor(eng):
    """Página do IPMA com os dois: o U01 já expirou às 17Z; o U02 é alto."""
    r = _ipma(eng, _gamet(), [U01, U02])
    assert set(_decisoes(eng, r["regioes"]).values()) == {"GO"}
    assert r["faixa_sig"] == ("ACIMA FL195", None)


# ---------------------------------------------------------------------
# O mesmo SIGMET com outros níveis/fenómeno: NO-GO na área, como antes
# ---------------------------------------------------------------------

@pytest.mark.parametrize("fen, niveis", [
    ("SEV TURB", "FL150/250"),
    ("SEV TURB", "FL195/300"),
    ("SEV TURB", "SFC/FL100"),
    ("SEV TURB", "TOP FL340"),
    ("SEV TURB", "TOP ABV FL300"),
    ("SEV TURB", ""),
    ("SEV TURB", "FL220/430 AND FL050/120"),
    ("SEV ICE", "FL100/190"),
    ("SEV MTW", "FL080/160"),
    ("EMBD TS", "FL220/430"),
    ("VA CLD", "FL220/430"),
])
def test_continua_no_go_como_antes(eng, monkeypatch, fen, niveis):
    s = _u02_com(niveis, fen)
    r = _ipma(eng, _gamet(), [s])
    with monkeypatch.context() as mp:
        _forcado(eng, mp)
        rf = _ipma(eng, _gamet(), [s])
    d, df = _decisoes(eng, r["regioes"]), _decisoes(eng, rf["regioes"])
    assert d == df
    assert "NO-GO" in d.values()
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert not any(b.phenomenon == "SIGMET_ALTO" for b in r["blocos"])
    assert any(t == "erro" and "SIGMET" in txt for t, txt in r["avisos"])


def test_u02_mais_sigmet_baixo(eng):
    """U02 (alto) + um SIGMET baixo noutra área: faixa ACTIVO, NO-GO só onde
    o baixo chega; o U02 continua informativo."""
    baixo = ("LPPC SIGMET U03 VALID 191700/192100 LPPT- LPPC LISBOA FIR SEV TURB FCST "
             "WI N4130 W00730 - N4200 W00730 - N4200 W00630 - N4130 W00630 - N4130 W00730 "
             "SFC/FL100 STNR NC=")
    r = _ipma(eng, _gamet(), [U02, baixo])
    rb = _ipma(eng, _gamet(), [baixo])
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    d, db = _decisoes(eng, r["regioes"]), _decisoes(eng, rb["regioes"])
    assert d == db
    assert "NO-GO" in d.values() and "GO" in d.values()
    # Os NO-GO vêm todos do baixo, nunca do U02
    for g in r["regioes"]:
        if g["decision"] == "NO-GO":
            cs = [eng.classificar_motivo(m) for m in g["reasons"]]
            assert any(c["valor"] == "U03" and c["nivel"] == "NO-GO" for c in cs)
        for m in g["reasons"]:
            c = eng.classificar_motivo(m)
            if c["valor"] == "U02":
                assert c["nivel"] == "INFO"


# ---------------------------------------------------------------------
# GAMET que refere o SIGMET
# ---------------------------------------------------------------------

def test_gamet_refere_u02_com_texto_disponivel(eng):
    r = _ipma(eng, _gamet(sigmet="U02"), [U02])
    assert set(_decisoes(eng, r["regioes"]).values()) == {"GO"}
    assert not any(b.phenomenon == "SIGMET" for b in r["blocos"])
    assert r["faixa_sig"] == ("ACIMA FL195", None)
    ref = [txt for t, txt in r["avisos"] if t == "aviso" and "refere o SIGMET" in txt]
    assert ref and "acima dos níveis VFR" in ref[0]
    assert not any(t == "erro" for t, _ in r["avisos"]), r["avisos"]


def test_gamet_colado_refere_u02_sem_texto(eng):
    """Colado à mão: só o identificador — não se sabe os níveis → toda a área."""
    r = eng.analisar_gamet(_gamet(sigmet="U02"), "manual", agora=AGORA)
    assert set(_decisoes(eng, r["regioes"]).values()) == {"NO-GO"}
    assert r["faixa_sig"] == ("ACTIVO", "NO-GO")
    assert any(t == "erro" and "SIGMET APLICÁVEL" in txt for t, txt in r["avisos"])


def test_gamet_refere_u02_ipma_sem_o_texto(eng):
    """Fonte IPMA mas o U02 não está na página: continua NO-GO em toda a área."""
    r = _ipma(eng, _gamet(sigmet="U02"), [])
    assert set(_decisoes(eng, r["regioes"]).values()) == {"NO-GO"}


# ---------------------------------------------------------------------
# Resto do período
# ---------------------------------------------------------------------

def test_resto_do_periodo_nao_conta_o_sigmet_alto(eng, monkeypatch):
    # VIS 800 m das 15 às 16Z: às 17:30Z já terminou há mais de 1 h
    g = _gamet("SFC VIS: 15/16 0800M FG")
    r = _ipma(eng, g, [U02])
    assert r["resto"] is not None
    assert r["resto"]["decisao"] == "GO"
    with monkeypatch.context() as mp:
        _forcado(eng, mp)
        rf = _ipma(eng, g, [U02])
    assert rf["resto"]["decisao"] == "NO-GO"        # o mesmo SIGMET a contar


# ---------------------------------------------------------------------
# Propriedade: 200 SIGMETs gerados
# ---------------------------------------------------------------------

# SEV ICE (FZRA) continua a contar (revisão do agente `parser`: a chuva gelada
# é NO-GO no SIGWX; na dúvida, conta) — fica com os outros fenómenos.
_FEN_ALTOS = ["SEV TURB", "SEV ICE", "SEV MTW"]
_FEN_OUTROS = ["EMBD TS", "FRQ TS", "OBSC TS", "SQL TS", "VA CLD", "HVY DS", "TC",
               "SEV ICE (FZRA)"]
# (texto dos níveis, limite inferior escrito ou None se não legível)
_NIVEIS = [
    ("FL{a}/{b}", "fl"), ("FL{a}/FL{b}", "fl"), ("ABV FL{a}", "fl"),
    ("SFC/FL{b}", 0), ("BLW FL{b}", 0), ("TOP FL{b}", 0), ("TOP ABV FL{b}", 0),
    ("SFC/3000FT", 0), ("2000/8000FT", 0), ("", None),
    ("FL{a}/{b} AND FL050/120", 50),
]


def _area_aleatoria(rnd):
    tipo = rnd.randrange(4)
    if tipo == 0:
        la, lo = rnd.uniform(36.5, 41.5), rnd.uniform(-10.5, -6.8)
        dla, dlo = rnd.uniform(0.3, 2.0), rnd.uniform(0.3, 2.0)
        pts = [(la, lo), (la + dla, lo), (la + dla, lo + dlo), (la, lo + dlo), (la, lo)]

        def c(p):
            a, o = p
            return f"N{int(a):02d}{round((a % 1) * 60) % 60:02d} W{int(-o):03d}{round((-o % 1) * 60) % 60:02d}"
        return "WI " + " - ".join(c(p) for p in pts)
    if tipo == 1:
        return rnd.choice(["N OF N4000", "S OF N3830", "E OF W00800", "W OF W00900"])
    if tipo == 2:
        return f"WI {rnd.choice([20, 40, 60])}NM OF N{rnd.randint(37, 41)}00 W00{rnd.randint(7, 9)}00"
    return "ENTIRE FIR"


def _gerar(rnd, i):
    fen = rnd.choice(_FEN_ALTOS * 3 + _FEN_OUTROS)
    # metade com limite inferior em FL, para haver casos dos dois lados do FL195
    modelo, inf = rnd.choice(_NIVEIS[:3] if rnd.random() < 0.5 else _NIVEIS)
    a = rnd.choice([100, 150, 180, 190, 195, 196, 200, 220, 250, 300])
    b = max(a + 50, rnd.choice([250, 340, 400, 430]))
    niveis = modelo.format(a=f"{a:03d}", b=f"{b:03d}")
    inferior = a if inf == "fl" else inf
    mov = rnd.choice(["STNR", "MOV E 20KT", "MOV NE 40KT", "MOV S 10KT"])
    texto = (f"LPPC SIGMET U{i % 9 + 1:02d} VALID 191700/192100 LPPT- LPPC LISBOA FIR "
             f"{fen} {rnd.choice(['FCST', 'OBS'])} {_area_aleatoria(rnd)} "
             f"{niveis} {mov} {rnd.choice(['NC', 'WKN', 'INTSF'])}=").replace("  ", " ")
    alto = (fen in _FEN_ALTOS and inferior is not None and inferior > 195)
    return texto, alto


def test_propriedade_sigmets_gerados(eng, monkeypatch):
    """Para 200 SIGMETs gerados, nos 52 pontos: a 6.0 só é menos severa do que
    o mesmo SIGMET forçado a NO-GO quando ele é TURB/ICE/MTW SEV com o limite
    inferior escrito acima do FL195 (calculado à parte, pelo gerador) — e
    nesse caso é exactamente o GAMET sem o SIGMET."""
    rnd = random.Random(60)
    g = _gamet("SFC VIS: N OF N4000 3000M BR SIG CLD: S OF N3800 BKN 004/010HFT AGL")
    sem = _decisoes(eng, _ipma(eng, g, [])["regioes"])
    casos = [_gerar(rnd, i) for i in range(200)]
    assert sum(a for _, a in casos) >= 30 and sum(not a for _, a in casos) >= 30
    novos = {}
    for s, _ in casos:
        novos[s] = _decisoes(eng, _ipma(eng, g, [s])["regioes"])
    with monkeypatch.context() as mp:
        _forcado(eng, mp)
        forc = {s: _decisoes(eng, _ipma(eng, g, [s])["regioes"]) for s, _ in casos}
    for s, alto in casos:
        ni = eng.sigmet_acima_vfr(s)
        assert (ni is not None) == alto, s
        for nome in sem:
            d, df = novos[s][nome], forc[s][nome]
            assert GRAV[d] <= GRAV[df], (s, nome)
            if GRAV[d] < GRAV[df]:
                assert ni is not None and ni > 195, (s, nome)
            if alto:
                assert d == sem[nome], (s, nome)
            else:
                assert d == df, (s, nome)


# ---------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------

@pytest.mark.skipif(not (DADOS / "indice.json").is_file(), reason="sem o arquivo (dados/)")
def test_arquivo_sigmet_alto_nunca_no_go_por_si(eng):
    """Em arquivo_hist, nenhum SIGMET arquivado acima do FL195 gera NO-GO por
    si: os motivos dele são sempre INFO e, sem ele no índice, as decisões nos
    52 pontos são as mesmas."""
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    altos = [e for e in indice.get("sigmets", [])
             if eng.sigmet_acima_vfr(e.get("texto", "")) is not None]
    if not altos:
        pytest.skip("nenhum SIGMET alto no arquivo")
    ids_altos = {id(e) for e in altos}
    indice_sem = dict(indice, sigmets=[e for e in indice["sigmets"] if id(e) not in ids_altos])
    textos_altos = {e["texto"] for e in altos}
    vistos = 0
    for ent in indice.get("gamets", []):
        f = DADOS / ent["ficheiro"]
        if not f.is_file():
            continue
        txt = f.read_text(encoding="utf-8")
        r = eng.analisar_gamet(txt, "arquivo_hist", indice=indice, entrada=ent)
        if not (set(r["sigmets"]) & textos_altos):
            continue
        vistos += 1
        for b in r["blocos"]:
            if b.phenomenon == "SIGMET" and getattr(b, "texto", None):
                assert b.texto not in textos_altos, b.value
        for gr in r["regioes"]:
            for m in gr["reasons"]:
                c = eng.classificar_motivo(m)
                if c["linha"] == "SIGMET" and c["nivel"] == "NO-GO":
                    blk = [b for b in r["blocos"] if b.phenomenon == "SIGMET"
                           and m.endswith(b.value)]
                    assert not any(getattr(b, "texto", None) in textos_altos for b in blk), (ent["ficheiro"], m)
        r0 = eng.analisar_gamet(txt, "arquivo_hist", indice=indice_sem, entrada=ent)
        assert _decisoes(eng, r["regioes"]) == _decisoes(eng, r0["regioes"]), ent["ficheiro"]
    assert vistos


# ---------------------------------------------------------------------
# Revisão do agente `parser` (19-nov-2026): leituras optimistas da 1.ª versão
# ---------------------------------------------------------------------
_CAB = "LPPC SIGMET U09 VALID 191700/192100 LPPT- LPPC LISBOA FIR "


@pytest.mark.parametrize("corpo", [
    "SEV TURB FCST WI N3746 W01002 - N4200 W01500 FL250/350 AND WI N3800 W00900 FL150",
    "SEV TURB FCST FL250/350 AND WI N3800 W00900 - N3900 W00800 3000M/FL250",
    "SEV TURB FCST FL250/350 AND WI N3800 W00900 0900/3000M",
    "SEV TURB FCST FL250/350 AND WI N3800 W00900 FL100-200",
    "SEV TURB FCST FL250/350 AND FL100 / 200",
    "SEV TURB FCST FL250/350 AND FL 100/200",
    "SEV TURB FCST FL250/350 AND SFC-FL100",
    "SEV TURB FCST FL250/350 AND GND/FL100",
    "SEV TURB FCST FL250/350 AND BLW FL 100",
    "SEV TURB FCST FL250/350 AND 8000 FT",
    "SEV TURB OBS AT 1500Z WI N3800 W00900 - N3900 W00800 FL220/430 "
    "FCST AT 1900Z WI N3900 W00900 - N4000 W00800 FL180",
    "EMBD TS SEV TURB FCST FL250/350",
    "SEV TURB FCST FL250/350 VA CLD",
    "TC SEV TURB FCST FL250/350",
    "RDOACT CLD SEV TURB FCST FL250/350",
    "HVY DS SEV TURB FCST FL250/350",
    "SEV ICE (FZRA) FCST FL220/300",
    "SEV TURB FCST FL200/150",
    "SEV TURB FCST FL220 / 430",
    "SEV TURB FCST FL220-430",
])
def test_parser_casos_optimistas_continuam_a_contar(eng, corpo):
    """Um nível baixo noutro formato, outro fenómeno no mesmo texto, números
    trocados ou níveis que não se lêem bem: o SIGMET continua a contar."""
    assert eng.sigmet_acima_vfr(_CAB + corpo) is None


@pytest.mark.parametrize("corpo, nivel", [
    ("SEV TURB FCST WI N3746 W01002 - N3822 W01500 - N4200 W01500 FL220/430 MOV E 40KT NC=", 220),
    ("SEV TURB FCST ABV FL250 MOV E 20KT", 250),
    ("SEV MTW FCST N OF N4100 FL220/300 STNR NC=", 220),
    ("SEV ICE FCST WI N3800 W01000 - N4000 W00900 - N3900 W00800 FL200/FL260 NC=", 200),
])
def test_parser_formas_legitimas_lidas(eng, corpo, nivel):
    assert eng.sigmet_acima_vfr(_CAB + corpo) == nivel
