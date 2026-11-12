"""
Carrega o motor meteorológico a partir do ficheiro da app Streamlit.

A app é um único ficheiro que executa código de UI ao ser importado, pelo
que não pode ser importada directamente pelo pytest. Este conftest extrai
apenas as secções de lógica pura (parser, decisão, geometria, PDF) e
executa-as num módulo isolado.

Se reorganizares o ficheiro da app, só é preciso ajustar os marcadores em
_SECTIONS — não é preciso mexer nos testes.
"""
import re
import sys
import types
from pathlib import Path

import pytest

APP_FILE = "app.py"

# (nome, marcador_inicio, marcador_fim) — por ordem de dependência
_SECTIONS = [
    ("normalize",  "def normalize(text):",
                   "\n# -------------------------------------------------\n# GEO"),
    ("zones",      "# GEOGRAFIA — área do GAMET",
                   "AERODROMES = {"),
    ("core",       "AERODROMES = {",
                   "\n# -------------------------------------------------\n# DECISION"),
    ("wind",       "def parse_wind(secn2: str) -> list:",
                   "\n# -------------------------------------------------\n# PARSER — v"),
    ("parser",     "def parse_gamet(text",
                   "\n# -------------------------------------------------\n# PDF EXPORT"),
    ("pdf",        "def _pdf_briefing_page",
                   "\n\n# -------------------------------------------------\n# EXECU"),
]

# Módulos da app que o motor não usa (UI e rede).
_SKIP_IMPORTS = ("streamlit", "requests", "folium", "pandas")


def _app_imports(src: str) -> str:
    """
    Usa os imports DA PRÓPRIA APP (linhas de topo), em vez de uma lista
    fixa. Até à 1.0 a lista era fixa e incluía `defaultdict`, que a app
    deixou de importar — os testes passavam e a app rebentava ao analisar.
    """
    linhas = ["import matplotlib", "matplotlib.use('Agg')"]
    for linha in src.splitlines():
        if re.match(r"^(import|from)\s", linha):
            mod = linha.split()[1].split(".")[0]
            if mod not in _SKIP_IMPORTS:
                linhas.append(linha)
    return "\n".join(linhas) + "\n"



def _find_app() -> Path:
    """Localiza o ficheiro da app (nome fixo desde a 1.0)."""
    root = Path(__file__).resolve().parent.parent
    app = root / APP_FILE
    if not app.exists():
        pytest.fail(f"{APP_FILE} não encontrado em {root}")
    return app


def _extract_engine(src: str) -> str:
    """Junta as secções de lógica pura numa fonte executável."""
    parts = [_app_imports(src)]

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    parts.append(f'APP_VERSION = "{m.group(1) if m else "0.0"}"\n')

    for name, start, end in _SECTIONS:
        if start not in src:
            pytest.fail(f"Marcador de início da secção '{name}' não encontrado: {start!r}")
        i = src.index(start)
        if end not in src[i:]:
            pytest.fail(f"Marcador de fim da secção '{name}' não encontrado: {end!r}")
        j = src.index(end, i)
        parts.append(src[i:j])

    return "\n\n".join(parts)


_MAIN_ORIGINAL = sys.modules.get("__main__")


@pytest.fixture(autouse=True)
def _repor_main():
    """A `nicegui.testing.user_simulation` corre o main.py com runpy como
    `__main__` e, ao sair, `nicegui_reset_globals` tira de sys.modules o módulo
    das páginas — o próprio `__main__`. Os testes seguintes que lançam
    processos com spawn/forkserver (test_v461.py) rebentavam com
    KeyError: '__main__' (4.7: o test_v47.py corre antes). Repõe-se o original."""
    yield
    if _MAIN_ORIGINAL is not None and sys.modules.get("__main__") is None:
        sys.modules["__main__"] = _MAIN_ORIGINAL


@pytest.fixture(scope="session")
def app_path() -> Path:
    return _find_app()


@pytest.fixture(scope="session")
def eng(app_path):
    """Motor meteorológico carregado da app, sem executar a UI."""
    source = _extract_engine(app_path.read_text(encoding="utf-8"))
    module = types.ModuleType("gamet_engine")
    module.__dict__["__file__"] = str(app_path)
    try:
        exec(compile(source, str(app_path), "exec"), module.__dict__)
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"Falha ao carregar o motor de {app_path.name}: {exc}")
    sys.modules["gamet_engine"] = module
    return module


@pytest.fixture(scope="session")
def net(app_path):
    """
    Secção de rede (fetch do IPMA) isolada, para testes com respostas
    simuladas. Fica separada do motor por depender de `requests`.
    """
    src = app_path.read_text(encoding="utf-8")
    start = "_IPMA_BASE ="
    end = "\n# -------------------------------------------------\n# UI — carregamento"
    if start not in src or end not in src:
        pytest.skip("Secção de rede não encontrada na app")
    block = src[src.index(start):src.index(end)]

    import time
    import requests
    from datetime import datetime, timezone, timedelta

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    module = types.ModuleType("gamet_net")
    module.__dict__.update({
        "re": re, "time": time, "requests": requests,
        "datetime": datetime, "timezone": timezone, "timedelta": timedelta,
        "APP_VERSION": m.group(1) if m else "0.0",
    })
    exec(compile(block, str(app_path), "exec"), module.__dict__)
    return module


# ---------------------------------------------------------------------
# Auxiliares partilhados
# ---------------------------------------------------------------------

HDR = "LPPC GAMET VALID {v} LPPT-LPPC LISBOA FIR/MAINLAND AREA BLW FL150 "
NIL_TAIL = " SIGMET APPLICABLE: AT TIME OF ISSUE NIL SECN II MNM QNH:{q}HPA="
SIG_TAIL = " SIGMET APPLICABLE: {s} SECN II MNM QNH:{q}HPA="


def build_gamet(body, validity="201500/202100", qnh="1013", sigmet=None):
    """Monta um GAMET completo a partir do corpo da Secção I."""
    tail = (SIG_TAIL.format(s=sigmet, q=qnh) if sigmet
            else NIL_TAIL.format(q=qnh))
    return HDR.format(v=validity) + body + tail


@pytest.fixture
def analyse(eng):
    """
    Corre o pipeline completo tal como a app faz e devolve um resumo
    fácil de usar nas asserções.
    """
    def _run(text):
        has_sig, sig_text = eng.extract_sigmet_applicable(text)
        blocks, fzlvl, qnh, wind = eng.parse_gamet(text)
        regions = eng.compute_dynamic_regions(blocks)
        if has_sig:
            regions = eng.apply_sigmet_override(regions, sig_text)
        return {
            "has_sigmet": has_sig,
            "sigmet_text": sig_text,
            "blocks": blocks,
            "regions": regions,
            "fzlvl": fzlvl,
            "qnh": qnh,
            "wind": wind,
            "decisions": [r["decision"] for r in regions],
            "vis":   sorted({b.value for b in blocks if b.phenomenon == "VIS"}),
            "base":  sorted({b.value for b in blocks if b.phenomenon == "BASE_AGL"}),
            "ts":    {b.value for b in blocks if b.phenomenon == "TS"},
            "turb":  {b.value for b in blocks if b.phenomenon == "TURB"},
            "ice":   {b.value for b in blocks if b.phenomenon == "ICE"},
            "mt_obsc": any(b.phenomenon == "MT_OBSC" for b in blocks),
            "va":      any(b.phenomenon == "VA" for b in blocks),
            "layers":  " ".join(b.layer for b in blocks if b.layer),
        }
    return _run


def veredicto(at):
    """
    Texto visível do veredicto global numa execução do AppTest. Desde a 2.2
    o veredicto é um cartão HTML (st.markdown) e não um st.error/st.warning;
    devolve o texto sem marcação, como o utilizador o lê.
    """
    for m in at.markdown:
        if 'class="gv-veredicto"' in m.value:
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.value)).strip()
    return ""


# 4.4 — só muda a redacção da nota "Nuvens baixas na Secção II" nas bases AMSL.
# Os testes que comparam os avisos com os motores de referência (4.1, 4.2)
# repõem a redacção antiga antes de comparar: o resto do aviso tem de ser igual.
_RED44_CAB = ("Base abaixo de 500 ft acima do solo (bases AMSL: acima do relevo "
              "mais alto da quadrícula):")
_RED44_AMSL = re.compile(
    r"fica a menos de 500 ft do \*\*relevo mais alto\*\* \(MEF\) da quadrícula de: "
    r"(.*?) — junto às serras, não necessariamente na pista")


def avisos_redaccao_43(avisos):
    """Avisos da 4.4+ com a redacção da nota de nuvens baixas da 4.3."""
    out = []
    for tipo, md in avisos:
        if "Nuvens baixas na Secção II" in md:
            md = md.replace(_RED44_CAB, "Base abaixo de 500 ft:")
            md = _RED44_AMSL.sub(r"aeródromos abrangidos: \1", md)
        out.append((tipo, md))
    return out


# 4.5: "D OF LINE …" nos SIGMET/AIRMET passou a ser lido como semiplano (até à
# 4.4: toda a área). Os testes que comparam todo o arquivo com motores fixos
# anteriores (4.1, 4.2) verificam OUTRAS mudanças; tiram-se do índice só os
# boletins com "OF LINE", cuja leitura mudou de propósito e é verificada
# contra a 4.4 em test_v45.py (test_arquivo_contra_4_4).
def indice_sem_linhas(indice):
    if not indice:
        return indice
    return {**indice, "sigmets": [e for e in indice.get("sigmets", [])
                                  if not re.search(r"\bOF\s+LINE\b", e.get("texto", ""))]}


# 4.6: qualificadores dos SIGMET/AIRMET só com graus ("S OF N33", "W OF W008",
# "BTN N38 AND N39") passaram a ser lidos (até à 4.5.2: toda a área). Os testes
# que comparam todo o arquivo com motores fixos anteriores (4.1, 4.2, 4.4,
# 4.5, 4.5.1) verificam OUTRAS mudanças; tiram-se do índice só esses boletins,
# cuja leitura mudou de propósito e é verificada contra a 4.5.2 em test_v46.py
# (test_arquivo_contra_4_5_2).
GRAUS_RE = re.compile(r"\b[NSEW]\s+(?:OF|BTN)\s+(?:N\d{2}|[WE]\d{3})(?![\dA-Z])"
                      r"|\bBTN\s+\S+\s*(?:AND|-)\s*(?:N\d{2}|[WE]\d{3})(?![\dA-Z])")


def indice_sem_graus(indice):
    if not indice:
        return indice
    return {**indice, "sigmets": [e for e in indice.get("sigmets", [])
                                  if not GRAUS_RE.search(e.get("texto", ""))]}


# 4.6 (relatório de 12-nov-2026): o SIGMET real U08 111400/111700 (`S OF N3940
# AND E OF W010`) é o primeiro boletim MISTO do arquivo — um qualificador com
# minutos e outro só com graus. A 4.5.2 lia o primeiro e ignorava em silêncio o
# segundo; a 4.6 intersecta os dois, e a área é a do mesmo boletim com os
# minutos escritos (`W010` → `W01000`), lida pela 4.5.2. `com_minutos` escreve
# os minutos `00` nas coordenadas só com graus dos qualificadores (as que
# GRAUS_RE encontra), e só nessas: os polígonos WI já liam graus desde a 3.5.
_GRAUS_QUAL_RE = (
    re.compile(r"(\b[NSEW]\s+(?:OF|BTN)\s+)(N\d{2}|[WE]\d{3})(?![\dA-Z])"),
    re.compile(r"(\bBTN\s+)(N\d{2}|[WE]\d{3})(?![\dA-Z])"),
    re.compile(r"(\bBTN\s+\S+\s*(?:AND|-)\s*)(N\d{2}|[WE]\d{3})(?![\dA-Z])"),
)


def com_minutos(texto):
    """O mesmo boletim com os minutos `00` escritos nos qualificadores só com graus."""
    anterior = None
    while anterior != texto:
        anterior = texto
        for r in _GRAUS_QUAL_RE:
            texto = r.sub(lambda m: m.group(1) + m.group(2) + "00", texto)
    return texto


def indice_com_minutos(indice):
    """O índice com os boletins só com graus (e mistos) reescritos por `com_minutos`."""
    if not indice:
        return indice
    return {**indice, "sigmets": [
        {**e, "texto": com_minutos(e.get("texto", ""))} if GRAUS_RE.search(e.get("texto", ""))
        else e for e in indice.get("sigmets", [])]}


# 4.5.1 (relatório de 11-nov-2026): com qualificadores do GAMET num SIGMET, a
# margem e o MOV contam a partir do semiplano não recortado, e a área pode
# crescer de propósito (verificado contra a 4.5 em test_v46_margem.py:
# test_boletins_do_arquivo_contem_4_5 e test_arquivo_contra_4_5). O SIGMET real
# U01 110100/110500 (`S OF N3459 … MOV NE 30KT`) foi o primeiro do arquivo em
# que isso se vê: na 4.5.1+ chega à área do GAMET 102100/110300 ("NO-GO na sua
# área"), nos motores 4.1/4.2/4.4 fica "fora da área do GAMET". Os testes que
# comparam todo o arquivo com esses motores por igualdade verificam OUTRAS
# mudanças; tiram-se do índice só os boletins cuja área a 4.5.1+ lê de forma
# diferente da 4.5 (`tests/referencia/app_4_5.py`, cópia fixa; não editar).
_REF45 = Path(__file__).resolve().parent / "referencia" / "app_4_5.py"
_MOTOR45 = []


def _motor_45():
    if not _MOTOR45:
        mod = types.ModuleType("motor_4_5_conftest")
        mod.__dict__["__file__"] = str(_REF45)
        exec(compile(_extract_engine(_REF45.read_text(encoding="utf-8")), str(_REF45),
                     "exec"), mod.__dict__)
        _MOTOR45.append(mod)
    return _MOTOR45[0]


def margem_451(eng, texto, ref):
    """True se a área do boletim na 4.5.1+ (`eng`) não é a da 4.5."""
    e45 = cot_452(_motor_45(), eng)   # a faixa COT da 4.5.2 (como nos motores comparados)
    if re.match(r"\s*LPPC\s+AIRMET", texto):
        # AIRMET: sem margem; o que entra na decisão são os blocos de ler_airmet
        b, b45 = eng.ler_airmet(texto, ref)["blocos"], e45.ler_airmet(texto, ref)["blocos"]
        if len(b) != len(b45):
            return True
        return any(x.phenomenon != y.phenomenon
                   or x.polygon.symmetric_difference(y.polygon).area > 1e-9
                   for x, y in zip(b, b45))
    g, d = eng.area_sigmet(texto, ref)
    g45, d45 = e45.area_sigmet(texto, ref)
    if (g is None) != (g45 is None):
        return True
    if g is None:
        return False
    return g.symmetric_difference(g45).area > 1e-9


def indice_sem_margem_451(indice, eng):
    if not indice:
        return indice
    fica = []
    for e in indice.get("sigmets", []):
        ref = eng._iso_utc(e.get("inicio"))
        if ref is None or not margem_451(eng, e.get("texto", ""), ref):
            fica.append(e)
    return {**indice, "sigmets": fica}


# 4.5.2: a faixa costeira (COT) passou a ter 10 km reais em todas as direcções
# (até à 4.5.1, ~7,7 km em longitude). Os testes que comparam com motores fixos
# anteriores (4.1, 4.2, 4.4) por igualdade verificam OUTRAS mudanças: dá-se ao
# motor antigo a faixa da 4.5.2, que muda de propósito e é verificada contra a
# 4.5.1 em test_v452.py. Os motores antigos só lêem a faixa em
# SURFACE_POLYGONS["COT"] (surface_polygon), a partir de COASTAL_POLYGON.
def cot_452(mod, eng):
    """Põe no motor `mod` (fixo, anterior à 4.5.2) a faixa costeira de `eng`."""
    mod.COASTAL_POLYGON = eng.COASTAL_POLYGON
    mod.SURFACE_POLYGONS["COT"] = eng.COASTAL_POLYGON
    return mod


# 4.7.2: _CLD_BASE_RE passou a aceitar um segundo topo depois de outra barra
# ("060-090/100/130HFT AMSL"); até à 4.7.1 a base desaparecia em silêncio. No
# arquivo só muda a nota informativa "Nuvens baixas na Secção II" do GAMET
# 211500/212100 de 21-mar ("AS/AC 060/090-100/150HFT AMSL": 6000 ft AMSL junto
# ao relevo) — nenhuma decisão. Os testes que comparam avisos por igualdade com
# motores fixos anteriores (4.1, 4.2, 4.4, 4.5.2) verificam OUTRAS mudanças:
# dá-se ao motor antigo a expressão da 4.7.2, que muda de propósito e é
# verificada em test_v472.py (e contra a 3.10 em test_v40_contra_310.py, que
# não a recebe). O ciclo do estado "CLD" dos motores antigos só lê os grupos
# da 4.0; o 2.º topo colado é ignorado em ambos.
def cld_base_472(mod, eng):
    """Põe no motor `mod` (fixo, anterior à 4.7.2) a _CLD_BASE_RE de `eng`."""
    mod._CLD_BASE_RE = eng._CLD_BASE_RE
    return mod


# 4.7.1: o motivo "TURB SEV …" / "ICE SEV …" / "MTW SEV|MOD …" passou a mostrar
# só as camadas dos eventos com esse nível (até à 4.7, todas as do tipo:
# "TURB SEV SFC/FL070/SFC/FL060"). Os testes que comparam motivos por igualdade
# com motores fixos anteriores verificam OUTRAS mudanças: comparam-se os
# motivos sem a nota de camada dessas três linhas. A camada nova é verificada
# em test_v471.py; a decisão continua a ser comparada à parte.
_CAMADA_471_RE = re.compile(r"^((?:TURB|ICE) SEV|MTW (?:SEV|MOD)) [^—(]*?(?= —| \(onda|$)")


def motivos_sem_camada_471(motivos):
    return [_CAMADA_471_RE.sub(r"\1", m) for m in motivos]


# 4.7.3: numa região fundida, o motivo que só vale numa das partes passou a
# "parte da zona: <motivo>" (até à 4.7.2 aparecia sem prefixo, como se valesse
# em toda a região), e os parciais vão no fim da lista. Os testes que comparam
# motivos por igualdade com motores fixos anteriores verificam OUTRAS mudanças:
# comparam-se os motivos da versão nova sem o prefixo, por ordem. O prefixo é
# verificado em test_v473.py (contra a 4.7.2: os mesmos motivos sem o prefixo).
MOTIVO_PARCIAL_473 = "parte da zona: "


def motivos_sem_parcial_473(motivos):
    return sorted(m[len(MOTIVO_PARCIAL_473):] if m.startswith(MOTIVO_PARCIAL_473) else m
                  for m in motivos)


# 4.7.4: o mesmo para as NOTAS de alcance de uma região fundida ("parte da
# zona: BASE: apenas sobre a costa e o mar…"); até à 4.7.3 eram a união, sem
# prefixo, por ordem alfabética. O prefixo é verificado em test_v474.py.
def notas_sem_parcial_474(notas):
    return motivos_sem_parcial_473(notas)


# 4.7.5: "SFC WIND:" na Secção I passou a ser o mesmo campo que "SFC WSPD:"
# (até à 4.7.4 era ignorado em silêncio; GAMETs reais 081500 e 082100 de
# 8-nov-2026). Os testes que comparam o arquivo por igualdade com motores fixos
# anteriores verificam OUTRAS mudanças: dão aos dois motores o texto com o nome
# antigo, que todos lêem desde a 1.4. Que a 4.7.5 lê os dois nomes da mesma
# forma (também no arquivo) e nunca fica mais permissiva do que a 4.7.4 é
# verificado em test_v475.py.
_SFC_WIND_475_RE = re.compile(r"\bSFC(\s+)WIND\b(?!/)", re.IGNORECASE)


def sfc_wind_475(texto):
    partes = re.split(r"(SECN\s+II)", texto, maxsplit=1, flags=re.IGNORECASE)
    partes[0] = _SFC_WIND_475_RE.sub(r"SFC\1WSPD", partes[0])
    return "".join(partes)


# 4.7.6: uma superfície (MAR/LAN/COT) a meio da linha, depois de conteúdo do
# campo e seguida de mais conteúdo, abre uma parte nova (GAMET real 081500/
# 082100 de 8-nov-2026: "LCA BKN 006-008/012HFT AGL MAR AND COT ISOL/EMBD
# TCU/CB …" — o LCA BKN 006 deixa de ficar só no mar e na costa). Os testes que
# comparam o arquivo por igualdade com motores fixos anteriores verificam
# OUTRAS mudanças: saltam os GAMETs que a 4.7.6 lê de outra forma (no arquivo a
# 9-nov-2026, só o 081500). Esses são verificados contra a 4.7.5 em
# test_v476.py (nunca mais permissivo, nenhum bloco com menos área).
def superficie_476(eng, texto):
    """True se a 4.7.6 (`eng`) lê o GAMET de outra forma que a 4.7.5 — algum
    bloco da Secção I ou da nota da Secção II muda com os cortes por superfície.
    No arquivo a 9-nov-2026 são 2: o 081500 de 8-nov (SIG CLD) e o 151500 de
    15-out (Secção II); o conjunto é fixo em
    `test_v476.test_arquivo_gamets_lidos_de_outra_forma`."""
    if not hasattr(eng, "_cortes_superficie"):
        return False

    def assin(t, **kw):
        return sorted((b.phenomenon, str(b.value), b.qualifier, b.surface, b.window,
                       b.janela_ambigua, round(b.polygon.area, 9))
                      for b in eng.parse_gamet(t, **kw)[0])
    if assin(texto) != assin(texto, _modo475=True):
        return True
    conteudo, _ = eng.nuvens_baixas_secn2(texto)
    if conteudo:
        t2 = f"SECN I SIG CLD:{conteudo} SECN II"
        return assin(t2) != assin(t2, _modo475=True)
    return False


# 4.8: "D OF LINE …" no GAMET (Secção I e nota da Secção II) passou a ser lido
# como semiplano (até à 4.7.6: área não reconhecida → toda a FIR + aviso, ou,
# sem quebra antes de "N OF LINE", a área da subentrada anterior). Os testes
# que comparam o arquivo por igualdade com motores fixos anteriores verificam
# OUTRAS mudanças: saltam os GAMETs com "LINE" (no arquivo a 10-nov-2026 são 6;
# conjunto fixo em `test_v48.test_arquivo_gamets_com_linha`). Esses são
# verificados contra a 4.7.6 em test_v48.py (sem LINE, tudo igual; mais
# permissivo só fora do semiplano de uma linha).
_LINE_48_RE = re.compile(r"\bLINE\b")


def linha_48(texto):
    """True se o GAMET tem "LINE" (a 4.8 pode lê-lo de outra forma)."""
    return bool(_LINE_48_RE.search(texto.upper()))
