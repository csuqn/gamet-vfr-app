"""
5.1 — Novo briefing (pedido do Duarte a 17-nov-2026; maqueta "Briefing VFR —
novo design", 2.ª proposta): mapa em destaque, zonas numeradas de norte para
sul (só o número), painel da zona escolhida, quadro por fenómeno e zona, e
"A ter em conta" com título + etiqueta. O PDF segue a mesma organização.

SÓ APRESENTAÇÃO: as regiões, decisões, motivos e avisos são os do motor. O
quadro e o painel dão a cada motivo um nível (NO-GO/MARGINAL) lido do texto
que decision() escreveu; o teste mais importante deste ficheiro verifica, em
todo o arquivo e em GAMETs gerados, que o pior nível dos motivos de cada
região é EXACTAMENTE a decisão dessa região (nenhum motivo desconhecido) —
assim a cor de uma célula nunca diz menos do que a decisão.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import conftest
from conftest import build_gamet
from test_geometry import GAMETS_VARIADOS

DADOS = Path(__file__).resolve().parent.parent / "dados"
GRAV = {"GO": -1, "MARGINAL": 1, "NO-GO": 2}

# GAMET real 180900/181500 de 18-nov-2026 (recolhido do arquivo)
G180900 = (
    "LPPC GAMET VALID 180900/181500 LPPT- LPPC LISBOA FIR/MAINLAND AREA BLW FL150 SECN I "
    "SFC VIS:LCA 0800-5000M DZ/RA/BR/FG SIG CLD:LCA BKN 002-004/010HFT AGL ICE:N OF N3800 "
    "LCA MOD/SEV ABV FL100 TURB:N OF N3700 LCA MOD/SEV SFC/FL050 SIGMET APPLICABLE:I02 "
    "SECN II PSYS:12 NIL CLD:SCT/BKN SC/CU 012-035/040-050HFT AGL MNM QNH:1008HPA=")


def _texto(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


def _nivel_regiao(eng, reg):
    cs = [eng.classificar_motivo(m) for m in reg["reasons"]]
    desconhecidos = [c["texto"] for c in cs if c["nivel"] is None]
    # (6.0) "INFO" (SIGMET acima do FL195) não decide: fica fora do pior nível.
    pior = max([GRAV[c["nivel"]] for c in cs if c["nivel"] and c["nivel"] != "INFO"] + [-1])
    return pior, desconhecidos


def _verifica_niveis(eng, regioes, origem):
    for reg in regioes:
        pior, desc = _nivel_regiao(eng, reg)
        assert not desc, f"{origem}: motivos desconhecidos {desc}"
        assert pior == GRAV[reg["decision"]], (origem, reg["decision"], reg["reasons"])


# ---------------------------------------------------------------- nível dos motivos

@pytest.mark.parametrize("motivo, linha, nivel, valor", [
    ("VIS 800m < 1500m", "VIS", "NO-GO", "800 m"),
    ("VIS LCA 800m < 1500m (local)", "VIS", "MARGINAL", "800 m (local)"),
    ("VIS 3000m < 5000m", "VIS", "MARGINAL", "3000 m"),
    ("VIS (LCA) 3000m < 5000m", "VIS", "MARGINAL", "3000 m (local)"),
    ("BASE 200ft < 500ft", "BASE", "NO-GO", "200 ft AGL"),
    ("BASE 800ft < 1000ft", "BASE", "MARGINAL", "800 ft AGL"),
    ("TS OCNL (risco alto)", "TS", "NO-GO", "OCNL"),
    ("TS ISOL", "TS", "MARGINAL", "ISOL"),
    ("CB ISOL (cumulonimbos)", "CB", "MARGINAL", "ISOL"),
    ("CB EMBD (cumulonimbos, risco alto)", "CB", "NO-GO", "EMBD"),
    ("TURB SEV SFC/FL060 — risco severo", "TURB", "NO-GO", "SEV SFC/FL060"),
    ("ICE SEV — risco severo", "ICE", "NO-GO", "SEV"),
    ("MTW MOD FL050/FL100 (onda de montanha)", "MTW", "MARGINAL", "MOD FL050/FL100"),
    ("MTW SEV (onda de montanha) — risco severo", "MTW", "NO-GO", "SEV"),
    ("SFC WSPD 35KT ≥ 30KT (vento à superfície)", "WSPD", "NO-GO", "35 kt"),
    ("SIGWX SQL (linha de borrasca), GR (granizo)", "SIGWX", "NO-GO", "SQL, GR"),
    ("SIGMET I01 (GAMET, sem área) — toda a área", "SIGMET", "NO-GO", "I01"),
    ("AIRMET 3 não interpretado (MARGINAL por precaução)", "AIRMET", "MARGINAL", "3"),
    ("VA (cinzas vulcânicas) — NO-GO imediato", "VA", "NO-GO", "sim"),
    ("MT OBSC (montanhas obscurecidas) — NO-GO VFR", "MT_OBSC", "NO-GO", "sim"),
])
def test_classificar_motivo(eng, motivo, linha, nivel, valor):
    c = eng.classificar_motivo(motivo)
    assert (c["linha"], c["nivel"], c["valor"]) == (linha, nivel, valor)
    assert not c["parcial"] and not c["origem"]


def test_classificar_parcial_e_origem(eng):
    c = eng.classificar_motivo("parte da zona: AIRMET 2 — VIS 200m < 1500m")
    assert (c["linha"], c["nivel"], c["valor"]) == ("VIS", "NO-GO", "200 m")
    assert c["parcial"] and c["origem"] == "AIRMET 2"
    assert eng.motivo_legivel(c) == ("Só em parte da zona: Visibilidade 200 m — abaixo de "
                                     "1500 m (AIRMET 2) → NO-GO")
    c = eng.classificar_motivo("isto não é um motivo")
    assert c["linha"] == "OUTRO" and c["nivel"] is None


def test_motivos_coincidem_com_a_decisao_gerados(eng, analyse):
    for corpo in GAMETS_VARIADOS:
        _verifica_niveis(eng, analyse(build_gamet(corpo))["regions"], corpo)


@pytest.mark.skipif(not (DADOS / "gamets").is_dir(), reason="sem o arquivo (dados/)")
def test_motivos_coincidem_com_a_decisao_no_arquivo(eng):
    """Todo o arquivo, sozinho (manual) e com os SIGMET/AIRMET arquivados
    (arquivo_hist): nenhum motivo desconhecido e o pior nível = a decisão."""
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    entradas = {e.get("ficheiro"): e for e in indice.get("gamets", [])}
    n = 0
    for f in sorted((DADOS / "gamets").rglob("*.txt")):
        texto = f.read_text(encoding="utf-8")
        _verifica_niveis(eng, eng.analisar_gamet(texto, "manual")["regioes"], f.name)
        ent = entradas.get(str(f.relative_to(DADOS)))
        if ent:
            r = eng.analisar_gamet(texto, "arquivo_hist", indice=indice, entrada=ent)
            _verifica_niveis(eng, r["regioes"], f.name + " (arquivo_hist)")
        n += 1
    assert n > 100


# ---------------------------------------------------------------- zonas e quadro

def test_zonas_de_norte_para_sul(eng, analyse):
    r = analyse(build_gamet("SECN I SFC VIS: N OF N4100 800M FG "
                            "SIG CLD: S OF N3800 BKN 004/010HFT AGL"))
    regs = r["regions"]
    ordem = eng.zonas_ordem(regs)
    lats = [regs[i]["polygon"].centroid.y for i in ordem]
    assert lats == sorted(lats, reverse=True) and len(ordem) == len(regs) == 3
    assert regs[ordem[0]]["decision"] == "NO-GO"          # VIS 800 a norte
    assert regs[ordem[-1]]["decision"] == "NO-GO"         # base 400 a sul
    assert regs[ordem[1]]["decision"] == "GO"


def test_quadro_so_linhas_com_dados(eng, analyse):
    r = analyse(build_gamet("SECN I SFC VIS: N OF N4000 LCA 1200M BR "
                            "TURB: S OF N3900 MOD SFC/FL050"))
    linhas, ordem = eng.quadro_zonas(r["regions"])
    rot = [x for x, _ in linhas]
    assert rot == ["Visibilidade", "Turbulência"]
    vis = dict(linhas)["Visibilidade"]
    assert any(c and c["valor"] == "1200 m (local)" and c["nivel"] == "MARGINAL" for c in vis)
    turb = [c for c in dict(linhas)["Turbulência"] if c]
    assert turb and all(c["nivel"] == "INFO" and c["valor"].startswith("MOD") for c in turb)
    h = eng.html_quadro(r["regions"])
    assert "Sem trovoada nem CB neste GAMET." in _texto(h)
    assert "ZONA 1" in h and "ZONA 2" in h


def test_quadro_vazio_e_porque(eng, analyse):
    r = analyse(build_gamet("SECN I SFC VIS: NIL"))
    assert "Sem fenómenos significativos" in eng.html_quadro(r["regions"])
    assert eng.porque_veredicto(r["regions"]) == ""
    r = analyse(build_gamet("SECN I SIG CLD: LCA BKN 002-004/010HFT AGL "
                            "TURB: N OF N4000 SEV SFC/FL050"))
    assert eng.porque_veredicto(r["regions"]) == "Base das nuvens 200 ft AGL — abaixo de 500 ft"


def test_quadro_vento_por_estacao(eng):
    r = eng.analisar_gamet(G180900.replace(
        "MNM QNH", "WIND/T: BRAGANCA PORTO VISEU N4145 W00645 N4115 W00840 N4045 W00750 "
        "1000FT AGL 240/033KT PS11 200/026KT PS15 230/024KT PS13 MNM QNH"), "manual")
    linhas, _ = eng.quadro_zonas(r["regioes"], wind=r["wind"])
    vento = [c for c in dict(linhas)["Vento a 1000 ft"] if c]
    assert vento and all(c["nivel"] == "INFO" for c in vento)
    assert "33 kt" in {c["valor"] for c in vento}


def test_gamet_real_180900(eng):
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    _verifica_niveis(eng, regs, "180900")
    assert {g["decision"] for g in regs} == {"NO-GO"}
    assert eng.porque_veredicto(regs).startswith("Base das nuvens 200 ft AGL — abaixo de 500 ft")
    ordem = eng.zonas_ordem(regs)
    h = _texto(eng.html_zona(1, regs[ordem[0]], 65, regs))
    assert h.startswith("Zona 1") and "Base das nuvens 200 ft AGL — abaixo de 500 ft → NO-GO" in h
    assert "Visibilidade 800 m (local) — abaixo de 1500 m → MARGINAL" in h
    assert "aeródromos e pistas" in h
    lisboa = "Lisboa (LPPT)"
    reg = eng.find_region_for_point(regs, *eng.AERODROMES[lisboa])
    z = ordem.index(regs.index(reg)) + 1
    h = eng.html_meu_aerodromo(lisboa, z, reg)
    assert 'class="gv-ad"' in h and f"{lisboa}: NO-GO" in h and f"ZONA {z}" in h


def test_html_e_escapado(eng, analyse):
    r = analyse(build_gamet("SECN I SFC VIS: 800M FG"))
    reg = dict(r["regions"][0])
    reg["reasons"] = ["<script>x</script>"]
    assert "<script>" not in eng.html_zona(1, reg, 100, [reg])
    assert "&lt;script&gt;" in eng.html_zona(1, reg, 100, [reg])


# ---------------------------------------------------------------- avisos

@pytest.mark.parametrize("tipo, md, titulo, etiqueta, visivel", [
    ("aviso", "🕓 **O IPMA ainda não publicou o novo GAMET** (o anterior é retirado…",
     "O IPMA ainda não publicou o novo GAMET", "verificar", False),
    ("aviso", "⚠️ **O GAMET refere o SIGMET I01, que já não está em vigor.** SIGMET I01…",
     "O GAMET refere o SIGMET I01, que já não está em vigor", "verificar", False),
    ("info", "☁️ **Nuvens baixas na Secção II** (informativo — **não altera** a decisão",
     "Nuvens baixas na Secção II", "informativo", False),
    ("aviso", "💨 **Vento forte reportado a 1000ft AGL** (aviso geral — não afecta a decisão",
     "Vento forte reportado a 1000ft AGL", "informativo", False),
    ("aviso", "⚠️ **2 AIRMET em vigor no IPMA** — entra(m) na decisão com as regras",
     "2 AIRMET em vigor no IPMA", "conta para a decisão", False),
    ("info", "ℹ️ SIGMETs do IPMA **não verificados**: o GAMET em análise não foi…",
     "SIGMETs do IPMA não verificados", "informativo", False),
    ("aviso", "⚠️ **Campo não interpretado** — «`XYZ`»: a app não conseguiu ler",
     "Campo não interpretado", "verificar", False),
    ("aviso", "📚 **GAMET DO ARQUIVO — não é o GAMET actual.** Serve para rever",
     "GAMET DO ARQUIVO", "verificar", True),
    ("aviso", "⏱️ Válido: 18/0900Z – 18/1500Z — ⚠️ **FORA DO PERÍODO DE VALIDADE**: os dados",
     "Válido", "verificar", True),
    ("erro", "🚨 **SIGMET APLICÁVEL A ESTE GAMET (I01).** Sem o texto completo",
     "SIGMET APLICÁVEL A ESTE GAMET", "verificar", True),
])
def test_avisos(eng, tipo, md, titulo, etiqueta, visivel):
    assert eng.titulo_aviso(md) == titulo
    assert eng.etiqueta_aviso(tipo, md) == etiqueta
    assert eng.aviso_visivel(tipo, md) is visivel


# ---------------------------------------------------------------- app completa

def _app(app_path, texto, aerodromo=None):
    testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit
    streamlit.cache_data.clear()
    at = testing.AppTest.from_file(str(app_path), default_timeout=180)
    at.session_state["gamet_loaded"] = "outro texto"     # sem auto-fetch
    at.session_state["_active_gamet_text"] = texto
    if aerodromo:
        at.session_state["aerodromo_preferido"] = aerodromo
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _gamet_em_vigor(corpo):
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    return build_gamet(corpo, validity=f"{ini:%d%H}00/{fim:%d%H}00")


def test_app_ordem_e_zona_do_aerodromo(app_path, eng):
    texto = _gamet_em_vigor("SECN I SFC VIS: N OF N4100 800M FG "
                            "SIG CLD: S OF N3800 BKN 004/010HFT AGL")
    at = _app(app_path, texto, "Faro (LPFR)")
    md = [m.value for m in at.markdown]
    ordem = [k for k, m in enumerate(md) for cls in ("gv-faixa", "gv-veredicto", "gv-meu",
                                                      "gv-zona", "gv-quadro") if f'class="{cls}"' in m]
    assert ordem == sorted(ordem) and len(ordem) == 5
    # Faro está a sul: a zona escolhida é a da base de 400 ft (a última)
    meu = next(m for m in md if 'class="gv-meu"' in m)
    zona = next(m for m in md if 'class="gv-zona"' in m)
    n = at.session_state["zona_sel"]
    assert f"ZONA {n}" in meu and f"Zona {n}" in zona and "Faro (LPFR): NO-GO" in meu
    assert "Base das nuvens 400 ft AGL — abaixo de 500 ft → NO-GO" in _texto(zona)
    # Escolher a zona 1 (norte): o painel muda
    at.session_state["zona_sel"] = 1
    at.run()
    zona = next(m.value for m in at.markdown if 'class="gv-zona"' in m.value)
    assert "Zona 1" in zona and "Visibilidade 800 m — abaixo de 1500 m → NO-GO" in _texto(zona)


def test_app_avisos_em_a_ter_em_conta(app_path):
    texto = _gamet_em_vigor("SECN I SFC VIS: N OF N4100 5000M BR SIG CLD: XYZ 123")
    at = _app(app_path, texto)
    rot = [e.label for e in at.expander]
    assert any(r.startswith("Campo não interpretado") and "verificar" in r for r in rot), rot
    assert any(r.startswith("SIGMETs do IPMA não verificados") and "informativo" in r
               for r in rot), rot
    # O texto completo continua lá (dentro do expander), como antes
    assert any("Campo não interpretado" in w.value for w in at.warning)
    assert any("Ter em conta" in s.value or "A ter em conta" in s.value for s in at.subheader)


def test_app_erro_fica_visivel(app_path):
    agora = datetime.now(timezone.utc)
    ini, fim = agora - timedelta(hours=2), agora + timedelta(hours=4)
    texto = build_gamet("SECN I SFC VIS: N OF N4100 5000M BR",
                        validity=f"{ini:%d%H}00/{fim:%d%H}00", sigmet="I01")
    at = _app(app_path, texto)
    assert any("SIGMET APLICÁVEL" in e.value for e in at.error)
    assert not any("SIGMET APLICÁVEL" in e.label for e in at.expander)


# ---------------------------------------------------------------- PDF

@pytest.mark.skipif(not shutil.which("pdftotext"), reason="sem pdftotext")
def test_pdf_segue_o_ecra(eng, tmp_path):
    r = eng.analisar_gamet(G180900, "manual")
    pdf = eng.generate_pdf(r["regioes"], G180900, r["fz"], r["qnh"], r["validity_label"],
                           r["wind"])
    f = tmp_path / "b.pdf"
    f.write_bytes(pdf)
    txt = subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True,
                         text=True).stdout
    for esperado in ("NO-GO em 100% da FIR", "POR FENÓMENO E ZONA", "Zona 1",
                     "Base das nuvens", "Zonas — de norte para sul",
                     "Texto GAMET original"):
        assert esperado in txt, esperado


# ---------------------------------------------------------------- 5.1.1

def test_legenda_do_mapa(eng, app_path):
    assert _texto(eng.html_legenda_mapa()) == "NO-GO MARGINAL GO"
    at = _app(app_path, _gamet_em_vigor("SECN I SFC VIS: N OF N4100 800M FG"))
    md = [m.value for m in at.markdown]
    leg = [k for k, m in enumerate(md) if 'class="gv-legmapa"' in m]
    ver = [k for k, m in enumerate(md) if 'class="gv-veredicto"' in m]
    zona = [k for k, m in enumerate(md) if 'class="gv-zona"' in m]
    assert leg and ver[0] < leg[0] < zona[0]


def test_mapa_ocupa_o_iframe(eng):
    """O mapa é a página completa do Folium (altura 100% do iframe), não o
    _repr_html_ dos notebooks (altura = 60% da largura: no telemóvel sobrava
    um grande espaço vazio por baixo). Zonas numeradas e aeródromo realçado."""
    pytest.importorskip("folium")
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    h = eng.mapa_zonas_html(regs, ordem, 2, "Lisboa (LPPT)")
    assert h.lstrip().lower().startswith("<!doctype html>")
    assert "padding-bottom:60%" not in h and "height: 100.0vh" in h
    for z in range(1, len(ordem) + 1):
        assert f"Zona {z}: NO-GO" in h
    assert "Lisboa (LPPT)" in h and "#7CC4FF" in h


def _linhas_brancas(h):
    """(lista de anéis [[lat, lon], ...], posição no HTML) dos PolyLine brancos."""
    import json
    out = []
    for m in re.finditer(r"L\.polyline\(\s*(\[\[.*?\]\]),\s*(\{.*?\})", h, re.S):
        if '"color": "#FFFFFF"' in m.group(2):
            out.append((json.loads(m.group(1)), m.start()))
    return out


def test_contorno_da_zona_por_cima_de_todas(eng):
    """(5.1.2, captura do Duarte a 18-nov-2026) O contorno branco da zona
    escolhida faz o perímetro inteiro: é desenhado depois de todas as zonas
    (as seguintes tapavam-no nas fronteiras comuns) e segue todos os anéis."""
    pytest.importorskip("folium")
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    assert len(ordem) >= 2
    for sel in range(1, len(ordem) + 1):
        h = eng.mapa_zonas_html(regs, ordem, sel)
        ultimo_poligono = max(m.start() for m in re.finditer(r"L\.polygon\(", h))
        brancas = _linhas_brancas(h)
        assert brancas and all(p > ultimo_poligono for _, p in brancas)
        poly = regs[ordem[sel - 1]]["polygon"]
        geoms = list(getattr(poly, "geoms", [poly]))
        aneis = [a for g in geoms for a in [g.exterior, *g.interiors]]
        assert len(brancas) == len(aneis)
        for (coords, _), anel in zip(brancas, aneis):
            assert coords == [[la, lo] for lo, la in anel.coords]
        # Nenhum polígono de zona é desenhado com contorno branco.
        assert not re.search(r"L\.polygon\([^;]*?\"color\": \"#FFFFFF\"", h, re.S)


def test_zona_com_buraco_nao_pinta_o_buraco(eng):
    """Uma zona com um buraco (outra zona dentro dela) é desenhada com o anel
    interior, e o contorno branco também o segue."""
    pytest.importorskip("folium")
    from shapely.geometry import Polygon
    fora = Polygon([(-9, 38), (-7, 38), (-7, 40), (-9, 40)],
                   [[(-8.5, 38.5), (-7.5, 38.5), (-7.5, 39.5), (-8.5, 39.5)]])
    dentro = Polygon([(-8.5, 38.5), (-7.5, 38.5), (-7.5, 39.5), (-8.5, 39.5)])
    regs = [{"polygon": fora, "decision": "GO"}, {"polygon": dentro, "decision": "NO-GO"}]
    h = eng.mapa_zonas_html(regs, [0, 1], 1)
    assert len(_linhas_brancas(h)) == 2
    assert eng._aneis_folium(fora)[1] == [[la, lo] for lo, la in fora.interiors[0].coords]
    assert eng._aneis_folium(dentro) == [[la, lo] for lo, la in dentro.exterior.coords]


# ---------------------------------------------------------------- 5.1.5

_U01_191500 = ("LPPC SIGMET U01 VALID 191500/191700 LPPT- LPPC LISBOA FIR SEV TURB FCST WI "
               "N3746 W01002 - N3822 W015 - N42 W015 - N3959 W00903 - N3746 W01002 FL220/430 "
               "MOV E 40KT INTSF")


@pytest.mark.parametrize("texto,esperado", [
    (_U01_191500, "turbulência severa prevista, FL220–FL430, desloca-se para E a 40 kt, "
                  "a intensificar"),
    ("LPPC SIGMET U01 VALID 181450/181800 LPPT- LPPC LISBOA FIR SEV TURB FCST N OF N3839 "
     "AND E OF W010 SFC/FL100 MOV ENE 30KT NC",
     "turbulência severa prevista, da superfície ao FL100, desloca-se para ENE a 30 kt, "
     "sem alteração"),
    ("LPPC SIGMET T01 VALID 010450/010850 LPPT- LPPC LISBOA FIR EMBD TSGR OBS AT 0430Z WI "
     "N3700 W01200 - N3600 W01100 TOP FL340 STNR WKN=",
     "trovoada embebida com granizo observada, topo FL340, estacionário, a enfraquecer"),
    ("LPPC SIGMET T02 VALID 010850/011250 LPPT- LPPC LISBOA FIR EMBD TS FCST S OF N33 "
     "TOP ABV FL300 MOV NE 15KT NC=",
     "trovoada embebida prevista, topo acima do FL300, desloca-se para NE a 15 kt, "
     "sem alteração"),
    ("LPPC SIGMET I01 VALID 171745/172145 LPPT- LPPC LISBOA FIR SEV ICE (FZRA) FCST ENTIRE "
     "FIR FL050/120 MOV E 10KT INTSF=",
     "gelo severo (chuva gelada) previsto, FL050–FL120, desloca-se para E a 10 kt, "
     "a intensificar"),
    ("LPPC SIGMET V01 VALID 010000/010600 LPPT- LPPC LISBOA FIR VA CLD OBS AT 2340Z WI "
     "N40 W010 - N41 W010 - N41 W009 - N40 W010 SFC/FL200 MOV E 20KT=",
     "cinzas vulcânicas observadas, da superfície ao FL200, desloca-se para E a 20 kt"),
    ("LPPC SIGMET M01 VALID 010000/010600 LPPT- LPPC LISBOA FIR SEV MTW FCST N OF N4100 "
     "FL080/160 STNR NC=",
     "onda de montanha severa prevista, FL080–FL160, estacionário, sem alteração"),
    ("LPPC SIGMET X01 VALID 010000/010600 LPPT- LPPC LISBOA FIR ALGO NOVO", ""),
    ("", ""),
])
def test_descrever_sigmet(eng, texto, esperado):
    """(5.1.5, pedido do Duarte a 19-nov-2026) O que o SIGMET avisa, por
    extenso (boletins reais do arquivo e formatos do Anexo 3). O que não lê
    fica de fora — nunca inventa."""
    assert eng.descrever_sigmet(texto) == esperado


def test_zona_diz_o_que_o_sigmet_avisa(eng):
    """(5.1.5, captura do Duarte a 19-nov-2026: "SIGMET U01 → NO-GO" sem mais
    nada) O painel da zona, o porquê do veredicto e o quadro dizem o que o
    SIGMET avisa; a decisão não muda. Desde a 6.0 o U01 real (FL220/430) é
    informativo (acima do FL195): verifica-se a descrição com o mesmo SIGMET
    a SFC/FL100, que continua NO-GO, e o U01 real à parte."""
    pytest.importorskip("folium")
    agora = datetime(2026, 11, 19, 15, 30, tzinfo=timezone.utc)
    g = build_gamet("SIGWX: NIL", validity="191500/192100")
    r0 = eng.analisar_gamet(g, "manual", agora=agora)
    baixo = _U01_191500.replace("FL220/430", "SFC/FL100")
    r = eng.analisar_gamet(g, "ipma", boletins=[baixo], boletins_at=agora, agora=agora)
    regs = r["regioes"]
    com = [x for x in regs if any(m.startswith("SIGMET U01") for m in x["reasons"])]
    assert com and all(x["decision"] == "NO-GO" for x in com)
    sem = [x for x in regs if x not in com]
    assert all(x["decision"] == "GO" for x in sem) and r0["regioes"][0]["decision"] == "GO"
    desc = ("turbulência severa prevista, da superfície ao FL100, desloca-se para E a 40 kt, "
            "a intensificar")
    ordem = eng.zonas_ordem(regs)
    z = next(n for n, i in enumerate(ordem, 1) if regs[i] in com)
    h = eng.html_zona(z, regs[ordem[z - 1]], 30.0, regs, (), None, r["blocos"])
    assert f"SIGMET U01 — {desc}" in eng.html.unescape(h)
    assert desc in eng.porque_veredicto(regs, r["blocos"])
    q = eng.html.unescape(eng.html_quadro(regs, ordem, z, None, r["blocos"]))
    assert "U01 SEV TURB" in q
    # 6.0: o U01 real, FL220/430 — GO em toda a FIR, motivo informativo descrito
    r = eng.analisar_gamet(g, "ipma", boletins=[_U01_191500], boletins_at=agora, agora=agora)
    regs = r["regioes"]
    assert all(x["decision"] == "GO" for x in regs)
    com = [x for x in regs if any(m.startswith("SIGMET U01") for m in x["reasons"])]
    assert com
    ordem = eng.zonas_ordem(regs)
    z = next(n for n, i in enumerate(ordem, 1) if regs[i] in com)
    h = eng.html.unescape(eng.html_zona(z, regs[ordem[z - 1]], 30.0, regs, (), None, r["blocos"]))
    assert ("SIGMET U01 — turbulência severa prevista, FL220–FL430, desloca-se para E a 40 kt, "
            "a intensificar — acima dos níveis VFR") in h


def test_sigmet_so_referido_no_gamet(eng):
    """Sem o texto do SIGMET (só "SIGMET APPLICABLE" no GAMET colado à mão), o
    motivo diz isso em vez de ficar só o identificador."""
    g = build_gamet("SIGWX: NIL", sigmet="U01")
    r = eng.analisar_gamet(g, "manual")
    regs = r["regioes"]
    cs = [eng._com_info_sigmet(eng.classificar_motivo(m), r["blocos"])
          for x in regs for m in x["reasons"]]
    sig = [c for c in cs if c["linha"] == "SIGMET"]
    assert sig and all(c["nivel"] == "NO-GO" for c in sig)
    assert all("referido no GAMET, sem o texto completo" in eng.motivo_legivel(c) for c in sig)


@pytest.mark.skipif(not (DADOS / "gamets").is_dir(), reason="sem o arquivo (dados/)")
def test_sigmets_do_arquivo_descritos(eng):
    """Todos os SIGMETs arquivados que entram numa zona (arquivo_hist) ficam
    descritos — o fenómeno é sempre lido — e o nível continua NO-GO."""
    indice = json.loads((DADOS / "indice.json").read_text(encoding="utf-8"))
    entradas = {e.get("ficheiro"): e for e in indice.get("gamets", [])}
    vistos = 0
    for f in sorted((DADOS / "gamets").rglob("*.txt")):
        ent = entradas.get(str(f.relative_to(DADOS)))
        if not ent:
            continue
        r = eng.analisar_gamet(f.read_text(encoding="utf-8"), "arquivo_hist",
                               indice=indice, entrada=ent)
        for x in r["regioes"]:
            for m in x["reasons"]:
                c = eng._com_info_sigmet(eng.classificar_motivo(m), r["blocos"])
                if c["linha"] != "SIGMET" or "GAMET, sem área" in m:
                    continue
                vistos += 1
                # 6.0: acima do FL195 (TURB/ICE/MTW SEV) é informativo
                assert c["nivel"] == ("INFO" if m.endswith("(acima dos níveis VFR)") else "NO-GO")
                assert c.get("longo", "").startswith(c["valor"].split()[0] + " — "), (f.name, m)
                assert eng._fen_sigmet_pt(c["longo"])[0] is None  # já em português
    assert vistos > 0


# ---------------------------------------------------------------- 5.1.3

@pytest.mark.parametrize("tooltip,n,esperado", [
    ("Zona 3: GO", 3, 3), ("Zona 1: NO-GO", 3, 1), ("Zona 2: MARGINAL", 2, 2),
    ("Zona 4: GO", 3, None), ("Zona 0: GO", 3, None),
    ("Lisboa (LPPT)", 3, None), ("Alqueidão", 3, None), (None, 3, None), ("", 3, None),
    (12, 3, None), ("Zona 12: GO", 12, 12),
])
def test_zona_do_clique(eng, tooltip, n, esperado):
    """(5.1.3) O tooltip do objecto tocado no mapa dá a zona; os aeródromos e
    toques fora de uma zona não mudam nada."""
    assert eng.zona_do_clique(tooltip, n) == esperado


def test_tocar_em_cada_zona_do_mapa_da_essa_zona(eng):
    """(5.1.3, pedido do Duarte a 19-nov-2026) Cada polígono e cada número do
    mapa têm um tooltip que `zona_do_clique` lê como a sua zona; o contorno
    branco não recebe toques (passam para a zona por baixo) e não há rectângulo
    de foco à volta da zona tocada."""
    folium = pytest.importorskip("folium")
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    n = len(ordem)
    fmap = eng.mapa_zonas(regs, ordem, 2, "Lisboa (LPPT)")
    por_zona = {}
    brancas = 0

    def _todos(el):
        for c in el._children.values():
            yield c
            if isinstance(c, folium.FeatureGroup):
                yield from _todos(c)

    for filho in _todos(fmap):
        tip = next((c for c in filho._children.values()
                    if isinstance(c, folium.Tooltip)), None)
        if isinstance(filho, (folium.Polygon, folium.Marker)) and tip is not None \
                and tip.text.startswith("Zona"):
            z = eng.zona_do_clique(tip.text, n)
            assert z is not None
            por_zona.setdefault(z, set()).add(type(filho).__name__)
        if isinstance(filho, folium.PolyLine) and not isinstance(filho, folium.Polygon):
            assert filho.options.get("interactive") is False
            brancas += 1
    assert set(por_zona) == set(range(1, n + 1))
    assert all(v == {"Polygon", "Marker"} for v in por_zona.values())
    assert brancas >= 1
    h = fmap.get_root().render()
    assert ".leaflet-interactive:focus{outline:none}" in h
    # Os aeródromos não são zonas
    for nome in ("Lisboa (LPPT)",):
        assert eng.zona_do_clique(nome, n) is None


def test_camada_da_zona_escolhida(eng):
    """(5.1.4) A camada da zona escolhida tem o contorno de todos os anéis da
    zona e o número com aro branco, e nada nela recebe toques. O mapa base
    (sem zona escolhida) não depende da zona: no Streamlit fica igual entre
    toques e o componente não o monta de novo."""
    folium = pytest.importorskip("folium")
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    for sel in range(1, len(ordem) + 1):
        fg = eng.camada_zona(regs, ordem, sel)
        assert isinstance(fg, folium.FeatureGroup)
        linhas = [c for c in fg._children.values() if isinstance(c, folium.PolyLine)]
        marcas = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        poly = regs[ordem[sel - 1]]["polygon"]
        aneis = [a for g in getattr(poly, "geoms", [poly]) for a in [g.exterior, *g.interiors]]
        assert len(linhas) == len(aneis) and len(marcas) == 1
        assert all(c.options.get("interactive") is False for c in linhas + marcas)
        assert f">{sel}</div>" in marcas[0].icon.options["html"]
        assert "#FFFFFF" in marcas[0].icon.options["html"]
    # Fora de 1..n ou sem zona: camada vazia
    assert not eng.camada_zona(regs, ordem, 0)._children
    assert not eng.camada_zona(regs, ordem, len(ordem) + 1)._children
    # O mapa base não leva camada nem contorno branco
    base = eng.mapa_zonas(regs, ordem, None)
    assert not any(isinstance(c, folium.FeatureGroup) for c in base._children.values())
    assert '"color": "#FFFFFF"' not in base.get_root().render()


def test_mapa_base_igual_entre_zonas_para_o_st_folium(eng):
    """(5.1.4) A chave interna do st_folium é um hash do JavaScript do mapa base
    sem os identificadores aleatórios: dois mapas base gerados em voltas
    diferentes (com outra zona escolhida) dão o mesmo hash, por isso o mapa não
    é montado de novo ao trocar de zona."""
    pytest.importorskip("folium")
    sf = pytest.importorskip("streamlit_folium")
    r = eng.analisar_gamet(G180900, "manual")
    regs = r["regioes"]
    ordem = eng.zonas_ordem(regs)
    hashes = set()
    for _ in range(3):
        m = eng.mapa_zonas(regs, ordem, None, "Lisboa (LPPT)")
        m.render()
        hashes.add(sf.generate_js_hash(sf._get_map_string(m), "mapa_x"))
    assert len(hashes) == 1


# ---------------------------------------------------------------- 5.1.2

def _motivos_base(eng, r):
    out = []
    for g in r["regioes"]:
        ib = eng.info_base(g, r["blocos"])
        for m in g["reasons"]:
            c = eng._com_info_base(eng.classificar_motivo(m), ib)
            if c["linha"] == "BASE":
                out.append((g["base"], c["valor"], eng.motivo_legivel(c)))
    return out


def test_base_local_gamet_real_180900(eng):
    """`LCA BKN 002-004/010HFT AGL` (GAMET real 180900/181500): a base é local."""
    r = eng.analisar_gamet(G180900, "manual")
    mb = _motivos_base(eng, r)
    assert mb and all(v == "200 ft AGL (local)" for _, v, _ in mb)
    assert all(t == "Base das nuvens 200 ft AGL (local) — abaixo de 500 ft → NO-GO"
               for _, _, t in mb)
    assert eng.porque_veredicto(r["regioes"], r["blocos"]).startswith(
        "Base das nuvens 200 ft AGL (local) — abaixo de 500 ft")


def test_base_amsl_diz_a_origem(eng):
    r = eng.analisar_gamet(build_gamet("SECN I SIG CLD: BKN 060/090HFT AMSL"), "manual")
    mb = _motivos_base(eng, r)
    assert mb
    for base, v, t in mb:
        assert v == f"{base} ft AGL (de AMSL)"
        assert f"{base} ft AGL (6000 ft AMSL no GAMET, junto ao relevo)" in t


def test_base_sem_referencia_diz_a_origem(eng):
    r = eng.analisar_gamet(build_gamet("SECN I SIG CLD: N OF N4000 BKN 004/010HFT"), "manual")
    (base, v, t), = _motivos_base(eng, r)
    assert (base, v) == (400, "400 ft AGL (sem ref.)")
    assert "(sem referência no GAMET, lida como AGL)" in t


def test_base_local_so_se_todas_locais(eng):
    """Uma base geral com o mesmo valor que uma LCA não fica "local"; a mais
    baixa é a que decide e é a que se descreve."""
    r = eng.analisar_gamet(build_gamet(
        "SECN I SIG CLD: LCA BKN 004/010HFT AGL N OF N4000 BKN 003/010HFT AGL"), "manual")
    for base, v, _ in _motivos_base(eng, r):
        assert "local" not in v or base == 400
    r = eng.analisar_gamet(build_gamet(
        "SECN I SIG CLD: LCA BKN 004/010HFT AGL N OF N4000 BKN 004/010HFT AGL"), "manual")
    norte = [v for base, v, _ in _motivos_base(eng, r)]
    assert "400 ft AGL" in norte          # a N de N4000 há uma base geral de 400


def test_origem_da_base_nao_muda_decisoes(eng):
    """Os blocos devolvidos são exactamente os que entraram nas regiões:
    recalcular as regiões com eles dá as mesmas decisões."""
    for corpo in GAMETS_VARIADOS[:15]:
        r = eng.analisar_gamet(build_gamet(corpo), "manual")
        regs = eng.compute_dynamic_regions(r["blocos"])
        assert sorted((g["decision"], round(g["polygon"].area, 6)) for g in regs) == \
            sorted((g["decision"], round(g["polygon"].area, 6)) for g in r["regioes"])
