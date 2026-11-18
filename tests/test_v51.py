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
    pior = max([GRAV[c["nivel"]] for c in cs if c["nivel"]] + [-1])
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
    ("BASE 200ft < 500ft", "BASE", "NO-GO", "200 ft"),
    ("BASE 800ft < 1000ft", "BASE", "MARGINAL", "800 ft"),
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
    assert eng.porque_veredicto(r["regions"]) == "Base das nuvens 200 ft — abaixo de 500 ft"


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
    assert eng.porque_veredicto(regs).startswith("Base das nuvens 200 ft — abaixo de 500 ft")
    ordem = eng.zonas_ordem(regs)
    h = _texto(eng.html_zona(1, regs[ordem[0]], 65, regs))
    assert h.startswith("Zona 1") and "Base das nuvens 200 ft — abaixo de 500 ft → NO-GO" in h
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
    assert "Base das nuvens 400 ft — abaixo de 500 ft → NO-GO" in _texto(zona)
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
