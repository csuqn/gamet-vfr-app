import streamlit as st
import math
import re
import io
import time
import requests
try:
    import folium
    _FOLIUM_OK = True
except ImportError:
    _FOLIUM_OK = False
import matplotlib.pyplot as plt
try:
    import pandas as pd
    _PANDAS_OK = True
except ImportError:
    _PANDAS_OK = False
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from shapely.geometry import box, Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union, polygonize
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

APP_VERSION = "1.6"

st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title(f"✈️ LPPC GAMET – Motor Cartográfico v{APP_VERSION}")

# -------------------------------------------------
# IPMA SELF-BRIEFING — fetch automático
# -------------------------------------------------

_IPMA_BASE = "https://brief-ng.ipma.pt"

# Candidatos de endpoint, por ordem de tentativa. O IPMA já mudou o caminho
# pelo menos uma vez (showsigmet.php deixou de existir → 404), pelo que a
# app tenta vários em vez de depender de um só. Podes acrescentar aqui o
# endpoint correcto se descobrires um novo.
_GAMET_ENDPOINTS = [
    # O IPMA migrou o Self-Briefing para uma single-page app
    # (brief-ng.ipma.pt/#showSIGMET). Os antigos .php na raiz deixaram de
    # existir; o conteúdo passou a ser servido a partir de /pages/actuals/.
    "/pages/actuals/sigmet.php",
    "/pages/actuals/gamet.php",
    "/api/sigmet",
    "/api/gamet",
    "/api/bulletins/sigmet",
    # Legado — mantidos por segurança caso o IPMA reverta
    "/showsigmet.php",
    "/showgamet.php",
]

# Parâmetros extra que a SPA envia. Não parecem ser obrigatórios, mas
# imitar o pedido real reduz o risco de o servidor recusar.
_GAMET_PARAMS = {
    "hash_link":  "#showSIGMET",
    "_page_hash": "showSIGMET",
}

# Horas UTC de emissão do GAMET (0300, 0900, 1500, 2100Z)
_GAMET_HOURS = [3, 9, 15, 21]

def next_gamet_time() -> datetime:
    """Calcula o próximo momento de emissão do GAMET em UTC."""
    now = datetime.now(timezone.utc)
    for h in _GAMET_HOURS:
        candidate = now.replace(hour=h, minute=5, second=0, microsecond=0)
        if candidate > now:
            return candidate
    # Nenhum hoje — próximo é amanhã às 03Z
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=3, minute=5, second=0, microsecond=0)

def format_countdown(dt: datetime) -> str:
    """Formata tempo restante até dt em hh:mm:ss."""
    delta = dt - datetime.now(timezone.utc)
    total = max(0, int(delta.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def extract_gamet_from_html(raw: str) -> str:
    """
    Isola o bloco 'LPPC GAMET ... =' de uma resposta do IPMA.

    Funciona com HTML (páginas antigas) e com JSON (API da nova
    single-page app), porque em ambos os casos o texto do GAMET aparece
    literalmente na resposta — basta remover marcação, escapes e ruído
    antes de o procurar.

    Devolve o texto do GAMET, ou "" se não encontrar.
    """
    text = raw
    # Escapes típicos de JSON
    text = text.replace("\\n", " ").replace("\\r", " ").replace('\\"', '"')
    text = text.replace("\\/", "/")
    # Marcação HTML e entidades
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"(LPPC\s+GAMET\s+(?:AMD\s+|COR\s+)?VALID\s+.+?=)", text, re.DOTALL)
    return m.group(1).strip() if m else ""

# Última página recebida com GAMET ("raw") e, quando a página respondeu mas
# ainda sem o GAMET novo, essa página ("sem_gamet") — traz os SIGMETs.
_IPMA_LAST = {"raw": "", "at": None, "sem_gamet": ""}

# Arquivo dos GAMETs/SIGMETs recolhidos de 15 em 15 min pelo GitHub Actions
# (ramo "dados"). Lido por raw.githubusercontent.com — sem passar pela API
# do GitHub, que tem limite de pedidos.
_ARQUIVO_BASE = "https://raw.githubusercontent.com/csuqn/gamet-vfr-app/dados/"


def fetch_arquivo(caminho: str) -> tuple:
    """(ok, texto|erro) de um ficheiro do arquivo."""
    try:
        resp = requests.get(_ARQUIVO_BASE + caminho, timeout=8,
                            headers={"User-Agent": f"GAMET-Decoder/{APP_VERSION}"})
    except requests.RequestException as e:
        return False, f"erro de ligação ({type(e).__name__})"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    return True, resp.text


def fetch_arquivo_indice() -> tuple:
    """(ok, índice|erro) — o índice é um JSON com listas 'gamets' e 'sigmets'."""
    import json
    ok, txt = fetch_arquivo("indice.json")
    if not ok:
        return False, txt
    try:
        dados = json.loads(txt)
    except ValueError:
        return False, "índice ilegível"
    if not isinstance(dados, dict) or not isinstance(dados.get("gamets"), list):
        return False, "índice com formato inesperado"
    dados.setdefault("sigmets", [])
    return True, dados

_BULLETIN_RE = re.compile(
    r"(LPPC\s+(?:SIGMET|AIRMET)\s+\S+\s+VALID\s+\d{6}/\d{6}.+?=)", re.DOTALL)


def extract_bulletins_from_html(raw: str) -> list:
    """
    SIGMET/AIRMET LPPC presentes na página do IPMA (um por bloco <pre>;
    se a página não tiver blocos, procura no texto todo).
    """
    def _limpar(t):
        t = t.replace("\\n", " ").replace("\\r", " ").replace('\\"', '"').replace("\\/", "/")
        t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ").replace("&amp;", "&")
        return re.sub(r"\s+", " ", t).strip()
    blocos = re.findall(r"<pre[^>]*>(.*?)</pre>", raw or "", re.DOTALL | re.IGNORECASE) or [raw or ""]
    out = []
    for bl in blocos:
        for m in _BULLETIN_RE.finditer(_limpar(bl)):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


def fetch_gamet_ipma(custom_url: str = "") -> tuple:
    """
    Carrega o GAMET do LPPC do Self-Briefing IPMA (endpoint público).

    Tenta vários endpoints conhecidos, porque o IPMA já alterou o caminho no
    passado. Se `custom_url` for indicado, é usado em exclusivo.

    Devolve (sucesso: bool, texto_ou_erro: str).
    """
    urls = [custom_url] if custom_url else [_IPMA_BASE + p for p in _GAMET_ENDPOINTS]

    attempts = []       # diagnóstico por URL
    reached_ok = False  # algum endpoint respondeu 200?
    _IPMA_LAST["sem_gamet"] = ""

    for url in urls:
        # Se o URL já traz query string própria (ex.: colado do browser),
        # não impomos os nossos parâmetros — só acrescentamos o
        # cache-buster, que é inofensivo.
        if "?" in url:
            params = {"_": int(time.time() * 1000)}
        else:
            params = dict(_GAMET_PARAMS, _=int(time.time() * 1000))
        try:
            resp = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": f"Mozilla/5.0 (compatible; GAMET-Decoder/{APP_VERSION})",
                    # A SPA envia estes — alguns servidores recusam pedidos
                    # que não pareçam vir da própria página
                    "Referer": f"{_IPMA_BASE}/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "text/html, */*; q=0.01",
                },
                timeout=10,
            )
        except requests.RequestException as e:
            attempts.append(f"{url} → erro de ligação ({type(e).__name__})")
            continue

        if resp.status_code != 200:
            attempts.append(f"{url} → HTTP {resp.status_code}")
            continue

        reached_ok = True
        gamet = extract_gamet_from_html(resp.text)
        if gamet:
            # A mesma página traz os SIGMET/AIRMET em vigor — guardada para
            # extract_bulletins_from_html, sem um segundo pedido ao IPMA
            _IPMA_LAST["raw"] = resp.text
            _IPMA_LAST["at"] = datetime.now(timezone.utc)
            return True, gamet
        # Página certa sem GAMET (janela antes da emissão): guarda-se a
        # primeira que traga boletins LPPC, para não perder os SIGMETs
        if not _IPMA_LAST["sem_gamet"] and extract_bulletins_from_html(resp.text):
            _IPMA_LAST["sem_gamet"] = resp.text
        attempts.append(f"{url} → respondeu, mas sem GAMET do LPPC no conteúdo")

    detail = "\n".join(f"• {a}" for a in attempts)
    if reached_ok:
        return False, (
            "O IPMA respondeu, mas não foi encontrado nenhum GAMET do LPPC no "
            "conteúdo. O GAMET pode ainda não estar emitido, ou o formato da "
            "página mudou.\n\n" + detail
        )
    return False, (
        "Não foi possível obter o GAMET de nenhum endpoint conhecido do IPMA. "
        "O endereço do serviço pode ter mudado — usa o campo de texto abaixo "
        "para colar o GAMET manualmente, ou indica o novo URL nas opções "
        "avançadas.\n\n" + detail
    )


# -------------------------------------------------
# UI — carregamento automático
# -------------------------------------------------

def _carregar_do_ipma():
    """Fetch do IPMA e actualização da sessão. Devolve (ok, texto|erro)."""
    ok, result = fetch_gamet_ipma(st.session_state.get("ipma_custom_url", ""))
    agora_txt = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%MZ")
    if ok:
        st.session_state["gamet_loaded"]    = result
        st.session_state["gamet_loaded_at"] = agora_txt
        st.session_state["gamet_fonte"]     = "ipma"
        st.session_state["ipma_boletins_fonte"] = "página do IPMA"
        st.session_state["ipma_boletins"]    = extract_bulletins_from_html(_IPMA_LAST["raw"])
        st.session_state["ipma_boletins_at"] = _IPMA_LAST["at"]
        st.session_state.pop("gamet_fetch_error", None)
        st.session_state.pop("_tentar_recurso", None)
    else:
        # Guardar o erro para o mostrar no expander — antes falhava em
        # silêncio e o utilizador só via a caixa de texto vazia
        st.session_state["gamet_fetch_error"] = result
        # Recurso ao arquivo (último GAMET ainda em vigor). Só pode correr
        # depois de o motor estar definido — ver o início de # EXECUÇÃO.
        st.session_state["_tentar_recurso"] = True
        # SIGMETs da página, se respondeu sem GAMET (janela antes da emissão)
        st.session_state["_pagina_sem_gamet"] = extract_bulletins_from_html(_IPMA_LAST["sem_gamet"])
        st.session_state["_pagina_sem_gamet_at"] = (
            datetime.now(timezone.utc) if _IPMA_LAST["sem_gamet"] else None)
    return ok, result


# Auto-fetch ao arrancar se não há GAMET em sessão
if "gamet_loaded" not in st.session_state and "gamet_fetch_error" not in st.session_state:
    with st.spinner("A carregar GAMET do Self-Briefing IPMA..."):
        _carregar_do_ipma()

with st.expander("📡 GAMET do IPMA", expanded=bool(st.session_state.get("gamet_fetch_error"))
                 and st.session_state.get("gamet_fonte") != "arquivo_recurso"):
    col_btn, col_next = st.columns([1, 2])
    with col_btn:
        if st.button("🔄 Recarregar GAMET"):
            with st.spinner("A carregar..."):
                ok, result = _carregar_do_ipma()
            if ok:
                st.success("✅ GAMET actualizado!")
    with col_next:
        nxt = next_gamet_time()
        st.info(f"⏭️ Próximo GAMET esperado: **{nxt.strftime('%H:%MZ')}** "
                f"(em {format_countdown(nxt)})")

    if st.session_state.get("gamet_fetch_error"):
        if st.session_state.get("gamet_fonte") == "arquivo_recurso":
            st.info("O IPMA não tem GAMET publicado neste momento — está "
                    "carregado o último GAMET do arquivo ainda em vigor.\n\n"
                    + st.session_state["gamet_fetch_error"])
        else:
            st.error(st.session_state["gamet_fetch_error"])

    if "gamet_loaded_at" in st.session_state:
        st.caption(f"⏱️ Carregado às {st.session_state['gamet_loaded_at']}")

    # Permite apontar para um endpoint novo sem editar o código — útil
    # quando o IPMA muda o caminho do serviço
    custom = st.text_input(
        "🔧 URL alternativo do IPMA (opcional)",
        value=st.session_state.get("ipma_custom_url", ""),
        placeholder=f"{_IPMA_BASE}/novo_endpoint.php",
        help="Se o IPMA mudar o endereço do serviço, cola aqui o URL correcto. "
             "Deixa vazio para tentar os endpoints conhecidos.",
    )
    if custom != st.session_state.get("ipma_custom_url", ""):
        st.session_state["ipma_custom_url"] = custom

    st.caption(
        "Se o carregamento automático falhar, podes sempre colar o texto do "
        "GAMET manualmente na caixa abaixo — a app funciona na mesma."
    )

# ---- Arquivo de GAMETs ----
# Os GAMETs e SIGMETs recolhidos de 15 em 15 min pelo GitHub Actions. Para
# rever situações passadas — NÃO para planear um voo com um GAMET antigo.
@st.cache_data(ttl=300, show_spinner=False)
def _indice_arquivo():
    return fetch_arquivo_indice()


with st.expander("📚 Arquivo de GAMETs"):
    st.caption("GAMETs recolhidos automaticamente do IPMA desde 14/10/2026 "
               "(com os SIGMETs emitidos). Serve para consultar e analisar "
               "situações passadas — **não** para planear um voo.")
    if st.button("📂 Abrir arquivo") or st.session_state.get("_arquivo_aberto"):
        st.session_state["_arquivo_aberto"] = True
        _ok_idx, _idx = _indice_arquivo()
        if not _ok_idx:
            st.error(f"Não foi possível ler o arquivo: {_idx}")
        elif not _idx["gamets"]:
            st.info("O arquivo ainda está vazio.")
        else:
            _por_dia = defaultdict(list)
            for _e in _idx["gamets"]:
                _por_dia[(_e.get("inicio") or _e["recolhido"])[:10]].append(_e)
            _dias = sorted(_por_dia, reverse=True)
            _dia = st.selectbox(
                "Dia (início da validade)", _dias,
                format_func=lambda d: f"{d[8:10]}/{d[5:7]}/{d[:4]} · {len(_por_dia[d])} GAMET(s)")
            _lista = sorted(_por_dia[_dia], key=lambda e: (e.get("inicio") or "", e["recolhido"]),
                            reverse=True)

            def _rotulo(e):
                ini, fim = e.get("inicio") or "", e.get("fim") or ""
                tipo = "" if e.get("tipo", "GAMET") == "GAMET" else f" {e['tipo']}"
                return (f"{ini[11:13]}–{fim[11:13]}Z{tipo} · recolhido "
                        f"{e['recolhido'][8:10]}/{e['recolhido'][5:7]} {e['recolhido'][11:16]}Z")
            _esc = st.selectbox("GAMET", range(len(_lista)), format_func=lambda i: _rotulo(_lista[i]))
            if st.button("Carregar e analisar este GAMET"):
                _ok_t, _txt = fetch_arquivo(_lista[_esc]["ficheiro"])
                if not _ok_t:
                    st.error(f"Não foi possível ler o GAMET: {_txt}")
                else:
                    _txt = re.sub(r"\s+", " ", _txt).strip()
                    st.session_state["gamet_loaded"] = _txt
                    st.session_state["gamet_loaded_at"] = f"arquivo ({_rotulo(_lista[_esc])})"
                    st.session_state["gamet_fonte"] = "arquivo_hist"
                    st.session_state["arquivo_entrada"] = _lista[_esc]
                    st.session_state["arquivo_indice"] = _idx
                    st.session_state["_active_gamet_text"] = _txt
                    st.rerun()

# Preencher text_area com GAMET carregado (ou vazio para input manual)
_default = st.session_state.get("gamet_loaded", "")

gamet_text = st.text_area(
    "Texto do GAMET (LPPC) — carregado automaticamente ou cole aqui",
    value=_default,
    height=200,
)

# -------------------------------------------------
# GEOGRAFIA — área do GAMET, costa e fronteira
# -------------------------------------------------
# Fonte dos limites: eAIP Portugal, ENR 2.1 (27-NOV-2025). O GAMET LPPC
# cobre a área continental abaixo do FL150, que corresponde aos sectores
# INFERIORES da FIR (ENR 2.1.3, SFC–FL245): NORTH LOWER (3.1), CENTRE
# LOWER (6.1) e SOUTH LOWER (8.1). Os sectores superiores incluem espaço
# aéreo delegado sobre Espanha e não servem para isto — até à 1.0 a app
# usava, por engano, dois vértices deles (415203N 0085037W e 403856N
# 0091500W) e um limite sudoeste simplificado.

def _dms(token):
    """'415308N0085015W' (ou com espaço) → (lon, lat) em graus decimais."""
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})N\s*(\d{3})(\d{2})(\d{2})W", token.strip())
    if not m:
        raise ValueError(f"coordenada inválida: {token!r}")
    g = [int(v) for v in m.groups()]
    return (-(g[3] + g[4] / 60 + g[5] / 3600), g[0] + g[1] / 60 + g[2] / 3600)

def _dms_list(raw):
    return [_dms(t) for t in raw.split()]

# -------------------------------------------------
# LINHA DE COSTA
# -------------------------------------------------
# Costa continental portuguesa, do Guadiana (Vila Real de Santo António)
# ao Minho (Caminha), com 67 pontos e espaçamento médio de ~12 km.
# Fonte: NAV Portugal (dados fornecidos pelo utilizador).
_COASTLINE_RAW = (
    "370943N0072400W 371035N0072708W 370932N0073135W 370741N0073559W "
    "370431N0074045W 365750N0075207W 365741N0075334W 365804N0075516W "
    "370133N0080149W 370404N0080623W 370524N0081101W 370421N0081804W "
    "370550N0082148W 370508N0082555W 370629N0083142W 370712N0083707W "
    "370448N0084006W 370343N0084728W 370231N0085157W 365943N0085652W "
    "370119N0085944W 371148N0085508W 371906N0085238W 372654N0084813W "
    "373600N0084914W 374451N0084849W 375319N0084813W 375704N0085311W "
    "380925N0084724W 382111N0084736W 382924N0085433W 382439N0091156W "
    "382451N0091317W 383305N0091139W 383940N0091535W 384026N0091934W "
    "384128N0092449W 384138N0092752W 384239N0092921W 384630N0093003W "
    "385344N0092641W 390433N0092526W 391030N0092151W 391622N0092018W "
    "392109N0092344W 392134N0092440W 392215N0092403W 392313N0092038W "
    "392415N0091633W 393053N0090911W 393451N0090636W 394552N0090203W "
    "400044N0085452W 400834N0085233W 401054N0085432W 402639N0084838W "
    "403837N0084546W 405721N0083932W 410756N0084020W 411433N0084349W "
    "412217N0084613W 412453N0084734W 413019N0084730W 414033N0085040W "
    "414508N0085303W 415021N0085241W 415220N0085233W"
)

_COAST_POINTS = _dms_list(_COASTLINE_RAW)
COASTLINE = LineString(_COAST_POINTS)

# -------------------------------------------------
# FRONTEIRA TERRESTRE PORTUGAL–ESPANHA
# -------------------------------------------------
# O ENR 2.1 define o troço terrestre só como "along Portuguese/Spanish
# border", sem coordenadas intermédias. Construção:
#
# 1. Traçado base: Natural Earth 1:10m, "admin_0_boundary_lines_land"
#    (domínio público), simplificado a 0,002°. Vai de junto à foz do
#    Guadiana até V. N. de Cerveira — não inclui os estuários.
# 2. Âncoras oficiais: os pontos do ENR 2.1 onde um espaço aéreo começa
#    ou acaba "along Portuguese/Spanish border" estão, por definição, na
#    fronteira. A linha é forçada a passar exactamente por eles. Antes do
#    ajuste a Natural Earth desviava-se deles 0,04–3,3 km.
# 3. Extremos: foz do Minho (415308N 0085015W) e foz do Guadiana
#    (370730N 0072318W), também do ENR 2.1.
_BORDER_RAW = (
    "-7.4144,37.1928 -7.4342,37.2593 -7.4276,37.2745 -7.4374,37.3073 "
    "-7.4450,37.3868 -7.4623,37.4179 -7.4600,37.4291 -7.4689,37.4756 "
    "-7.4759,37.4943 -7.5063,37.5181 -7.5154,37.5293 -7.5237,37.5557 "
    "-7.5291,37.5567 -7.5297,37.5672 -7.5158,37.5809 -7.5125,37.5904 "
    "-7.5143,37.6014 -7.5049,37.6064 -7.4716,37.6369 -7.4576,37.7001 "
    "-7.4440,37.7302 -7.4263,37.7506 -7.3344,37.8119 -7.3069,37.8508 "
    "-7.2958,37.8849 -7.2739,37.9315 -7.2686,37.9492 -7.2727,37.9770 "
    "-7.2658,37.9830 -7.2340,37.9881 -7.2233,37.9938 -7.1853,37.9887 "
    "-7.1597,37.9968 -7.1419,38.0116 -7.1320,38.0324 -7.1233,38.0400 "
    "-7.1059,38.0387 -7.0494,38.0202 -7.0240,38.0226 -7.0158,38.0468 "
    "-7.0064,38.0593 -6.9976,38.0896 -6.9790,38.1199 -6.9475,38.1966 "
    "-6.9642,38.2061 -6.9921,38.2043 -7.0181,38.1980 -7.0264,38.1996 "
    "-7.0387,38.1862 -7.0631,38.1775 -7.1035,38.1736 -7.1269,38.1909 "
    "-7.1672,38.2721 -7.1963,38.2922 -7.2114,38.3175 -7.3171,38.4246 "
    "-7.3592,38.4464 -7.3352,38.4694 -7.3341,38.4810 -7.3456,38.4941 "
    "-7.3358,38.5059 -7.3177,38.5563 -7.2759,38.6038 -7.2704,38.6177 "
    "-7.2735,38.6254 -7.2860,38.6319 -7.2909,38.6382 -7.2930,38.6563 "
    "-7.2841,38.7132 -7.2704,38.7375 -7.2115,38.7754 -7.1964,38.7800 "
    "-7.1797,38.7909 -7.1662,38.8034 -7.1606,38.8129 -7.1510,38.8193 "
    "-7.1049,38.8272 -7.0887,38.8334 -7.0561,38.8551 -7.0573,38.8694 "
    "-7.0522,38.8850 -7.0660,38.9046 -7.0445,38.9186 -7.0221,38.9429 "
    "-6.9733,39.0140 -6.9749,39.0230 -6.9863,39.0301 -6.9794,39.0472 "
    "-6.9857,39.0668 -6.9997,39.0847 -7.0158,39.0968 -7.0388,39.1091 "
    "-7.0649,39.1148 -7.0913,39.1124 -7.1273,39.0975 -7.1572,39.1054 "
    "-7.1675,39.1135 -7.1689,39.1219 -7.1579,39.1414 -7.1558,39.1515 "
    "-7.1681,39.1706 -7.2193,39.1848 -7.2441,39.1956 -7.2581,39.2113 "
    "-7.2658,39.2314 -7.2643,39.2523 -7.2508,39.2706 -7.3005,39.3179 "
    "-7.3193,39.3295 -7.3267,39.3413 -7.3314,39.3626 -7.3319,39.3847 "
    "-7.3189,39.4133 -7.3136,39.4361 -7.3135,39.4574 -7.3209,39.4674 "
    "-7.3629,39.4761 -7.3842,39.4840 -7.3994,39.4937 -7.4089,39.5156 "
    "-7.4176,39.5242 -7.4513,39.5378 -7.4681,39.5502 -7.4979,39.5810 "
    "-7.5158,39.5938 -7.5573,39.6798 -7.3414,39.6718 -7.2928,39.6833 "
    "-7.2529,39.6823 -7.2358,39.6865 -7.2141,39.6762 -7.1829,39.6751 "
    "-7.0358,39.6893 -7.0211,39.6940 -7.0096,39.7155 -7.0133,39.7389 "
    "-6.9930,39.7742 -7.0003,39.8025 -6.9930,39.8161 -6.9852,39.8211 "
    "-6.9528,39.8329 -6.9277,39.8619 -6.9218,39.8972 -6.9252,39.9179 "
    "-6.9095,39.9320 -6.8998,39.9656 -6.9016,39.9765 -6.8969,39.9871 "
    "-6.8797,40.0092 -6.9199,40.0649 -6.9557,40.1029 -6.9772,40.1134 "
    "-7.0158,40.1191 -7.0277,40.1326 -7.0348,40.1667 -7.0431,40.1814 "
    "-7.0346,40.1931 -7.0248,40.2162 -7.0158,40.2255 -6.9547,40.2534 "
    "-6.8964,40.2555 -6.8781,40.2652 -6.8702,40.2955 -6.8120,40.3323 "
    "-6.7944,40.3564 -6.8281,40.3806 -6.8513,40.4095 -6.8571,40.4421 "
    "-6.8387,40.4772 -6.8153,40.5025 -6.8125,40.5146 -6.8181,40.5319 "
    "-6.8484,40.5648 -6.8505,40.5822 -6.8445,40.5978 -6.8213,40.6302 "
    "-6.8143,40.6472 -6.8162,40.6772 -6.8391,40.7575 -6.8391,40.7769 "
    "-6.8335,40.7978 -6.8381,40.8149 -6.8367,40.8402 -6.8203,40.8442 "
    "-6.8162,40.8568 -6.8212,40.8701 -6.8321,40.8759 -6.8470,40.8789 "
    "-6.8553,40.8872 -6.8852,40.9489 -6.8992,40.9668 -6.9404,41.0034 "
    "-6.9425,41.0160 -6.9318,41.0291 -6.9279,41.0479 -6.9068,41.0561 "
    "-6.8453,41.0519 -6.8180,41.0541 -6.8044,41.0644 -6.7648,41.1089 "
    "-6.7565,41.1271 -6.7590,41.1518 -6.7552,41.1588 -6.7422,41.1714 "
    "-6.7069,41.1943 -6.6938,41.2174 -6.6466,41.2676 -6.5635,41.2707 "
    "-6.4959,41.2949 -6.4631,41.3141 -6.4310,41.3390 -6.3996,41.3775 "
    "-6.3792,41.3775 -6.3755,41.3908 -6.3762,41.3969 -6.3792,41.3973 "
    "-6.3523,41.4093 -6.3211,41.4110 -6.3210,41.4196 -6.2829,41.4656 "
    "-6.2859,41.4869 -6.2795,41.4970 -6.2536,41.5175 -6.2059,41.5703 "
    "-6.2301,41.5949 -6.2722,41.6282 -6.3171,41.6501 -6.3659,41.6636 "
    "-6.4608,41.6766 -6.4744,41.6659 -6.5030,41.6531 -6.5134,41.6509 "
    "-6.5415,41.6589 -6.5553,41.6749 -6.5631,41.7130 -6.5774,41.7397 "
    "-6.5601,41.7669 -6.5357,41.8486 -6.5242,41.8674 -6.5679,41.8759 "
    "-6.5758,41.8829 -6.5676,41.9261 -6.5717,41.9426 -6.5851,41.9547 "
    "-6.6095,41.9623 -6.6228,41.9410 -6.6568,41.9331 -6.7280,41.9309 "
    "-6.7579,41.9376 -6.7944,41.9797 -6.8249,41.9838 -6.8312,41.9540 "
    "-6.8550,41.9429 -6.9171,41.9391 -6.9451,41.9434 -6.9695,41.9577 "
    "-6.9924,41.9664 -7.0158,41.9537 -7.0513,41.9420 -7.0827,41.9528 "
    "-7.1132,41.9724 -7.1454,41.9875 -7.1597,41.9857 -7.1773,41.9784 "
    "-7.1999,41.9637 -7.2021,41.9497 -7.1957,41.9174 -7.1979,41.9015 "
    "-7.2187,41.8790 -7.2515,41.8637 -7.3225,41.8454 -7.3919,41.8420 "
    "-7.4054,41.8352 -7.4427,41.8060 -7.4470,41.8218 -7.4566,41.8392 "
    "-7.4694,41.8525 -7.5158,41.8650 -7.5233,41.8602 -7.5263,41.8474 "
    "-7.5316,41.8402 -7.5467,41.8320 -7.5884,41.8242 -7.6061,41.8255 "
    "-7.6222,41.8323 -7.6228,41.8417 -7.6074,41.8732 -7.6612,41.8749 "
    "-7.7064,41.8963 -7.7220,41.8993 -7.7501,41.8884 -7.8122,41.8771 "
    "-7.8392,41.8784 -7.8497,41.8758 -7.8648,41.8579 -7.8966,41.8579 "
    "-7.9061,41.9139 -7.9258,41.9082 -7.9354,41.8800 -7.9448,41.8670 "
    "-7.9794,41.8686 -7.9936,41.8637 -8.0157,41.8419 -8.0486,41.8164 "
    "-8.0935,41.8067 -8.1796,41.8107 -8.1754,41.8366 -8.1770,41.8499 "
    "-8.1846,41.8577 -8.2204,41.8682 -8.2317,41.8860 -8.2302,41.9047 "
    "-8.2207,41.9227 -8.1821,41.9654 -8.1530,41.9868 -8.1080,42.0109 "
    "-8.0974,42.0235 -8.0951,42.0409 -8.1032,42.0558 -8.1184,42.0669 "
    "-8.1376,42.0729 -8.1584,42.0714 -8.1913,42.0621 -8.2040,42.0696 "
    "-8.2074,42.0858 -8.2043,42.1288 -8.2224,42.1536 -8.2523,42.1376 "
    "-8.2707,42.1320 -8.2954,42.1301 -8.3300,42.1084 -8.3467,42.1017 "
    "-8.5012,42.0831 -8.5200,42.0777 -8.5544,42.0601 -8.5728,42.0544 "
    "-8.6269,42.0510 -8.6439,42.0415 -8.6526,42.0314 -8.6708,41.9998 "
    "-8.6913,41.9896 -8.7170,41.9838 -8.7508,41.9690 "
)


_FOZ_MINHO    = _dms("415308N0085015W")   # NORTH LOWER 3.1
_FOZ_GUADIANA = _dms("370730N0072318W")   # SOUTH LOWER 8.1
_LIM_NORTE_CENTRO = _dms("402358N0064906W")   # sectores 3.1 / 6.1
_LIM_CENTRO_SUL   = _dms("375957N0071223W")   # sectores 6.1 / 8.1

# Outros pontos do ENR 2.1 que iniciam/terminam "along border"
_BORDER_ANCHORS = _dms_list(
    "414909N0080902W 414849N0080335W "    # NORTH UPPER
    "415145N0072708W "                    # PORTO TMA
    "412853N0061708W "                    # NORTH UPPER (Douro)
    "390700N0070100W 384917N0070505W "    # CENTRE UPPER
    "381812N0071047W "                    # CENTRE UPPER
    "375928N0071409W 371016N0072340W "    # SOUTH UPPER
    "372503N0072636W"                     # FARO TMA
) + [_LIM_NORTE_CENTRO, _LIM_CENTRO_SUL]

def _build_border():
    """Fronteira Minho → Guadiana, a passar exactamente pelas âncoras."""
    from shapely.ops import substring
    ne = [tuple(float(v) for v in par.split(",")) for par in _BORDER_RAW.split()]
    base = LineString([_FOZ_MINHO] + ne[::-1] + [_FOZ_GUADIANA])
    marcos = sorted([(0.0, _FOZ_MINHO), (base.length, _FOZ_GUADIANA)]
                    + [(base.project(Point(p)), p) for p in _BORDER_ANCHORS])
    coords = [_FOZ_MINHO]
    for (d0, _p0), (d1, p1) in zip(marcos, marcos[1:]):
        troco = list(substring(base, d0, d1).coords)
        coords.extend(troco[1:-1])     # interior do troço da Natural Earth
        coords.append(p1)              # e a âncora oficial, exacta
    linha = LineString(coords)
    # Falhar em voz alta: uma âncora mal ordenada criaria um zigue-zague
    assert linha.is_simple, "fronteira com auto-intersecção"
    return linha

BORDER_LINE = _build_border()

def _border_between(a, b):
    """Troço da fronteira entre dois pontos dela, de a para b."""
    from shapely.ops import substring
    d0, d1 = BORDER_LINE.project(Point(a)), BORDER_LINE.project(Point(b))
    pts = list(substring(BORDER_LINE, d0, d1).coords)
    return [a] + pts[1:-1] + [b]

# -------------------------------------------------
# SECTORES INFERIORES (ENR 2.1.3, SFC–FL245)
# -------------------------------------------------
SECTOR_NORTE = Polygon(   # NORTH LOWER SECTOR 3.1
    _border_between(_FOZ_MINHO, _LIM_NORTE_CENTRO)
    + _dms_list("392300N0080100W 385400N0100000W 392055N0094705W "
                "401159N0092633W 402256N0092205W 403856N0091505W "
                "404940N0091111W")
)
SECTOR_CENTRO = Polygon(  # CENTRE LOWER SECTOR 6.1
    _border_between(_LIM_NORTE_CENTRO, _LIM_CENTRO_SUL)
    + _dms_list("380000N0090000W 380000N0091200W 380000N0092800W "
                "380000N0100000W 385400N0100000W 392300N0080100W")
)
SECTOR_SUL = Polygon(     # SOUTH LOWER SECTOR 8.1
    _border_between(_LIM_CENTRO_SUL, _FOZ_GUADIANA)
    + _dms_list("364016N0072311W 355800N0072300W 355800N0104400W "
                "380000N0092800W 380000N0091200W 380000N0090000W")
)

ZONES = {
    "SECTOR NORTE": SECTOR_NORTE,
    "SECTOR CENTRO": SECTOR_CENTRO,
    "SECTOR SUL": SECTOR_SUL,
}
for _nome, _sec in ZONES.items():
    assert _sec.is_valid, f"{_nome} inválido"

_fir = unary_union(list(ZONES.values()))
# Garantia: a área é um polígono único e sem buracos.
assert _fir.geom_type == "Polygon" and not _fir.interiors, _fir.geom_type
FIR_POLYGON = _fir

# Terra = anel fechado pela costa (Guadiana → Minho) e pela fronteira
# (Minho → Guadiana). Os estuários do Minho e do Tejo contam como terra.
LAND_POLYGON = Polygon(_COAST_POINTS + list(BORDER_LINE.coords)).buffer(0).intersection(FIR_POLYGON)
SEA_POLYGON = FIR_POLYGON.difference(LAND_POLYGON)

# Faixa costeira (COT): banda de ~10 km para cada lado da linha, que é a
# convenção que adoptámos — a definição OACI não fixa uma largura.
_COT_KM = 10.0
COASTAL_POLYGON = COASTLINE.buffer(_COT_KM / 111.0).intersection(FIR_POLYGON)

SURFACE_POLYGONS = {
    "MAR": SEA_POLYGON,
    "LAN": LAND_POLYGON,
    "COT": COASTAL_POLYGON,
}

def surface_polygon(surface):
    """
    Devolve o polígono correspondente a um qualificador de superfície
    (MAR / LAN / COT, ou combinações como COT/MAR), ou None se não
    houver qualificador.
    """
    if not surface:
        return None
    partes = [SURFACE_POLYGONS[s] for s in surface.split("/") if s in SURFACE_POLYGONS]
    if not partes:
        return None
    return unary_union(partes) if len(partes) > 1 else partes[0]

FIR_MINX, FIR_MINY, FIR_MAXX, FIR_MAXY = FIR_POLYGON.bounds

# -------------------------------------------------
# RELEVO — MEF (Maximum Elevation Figure) por quadrícula de 1° × 30'
# -------------------------------------------------
# Usada na conversão AMSL→AGL das bases de nuvem: a base AGL é calculada
# contra a elevação MÁXIMA da quadrícula, ou seja, a pior que um piloto
# encontra nessa zona. (Até à v31 era uma interpolação de 11 pontos que
# subestimava a Estrela em ~3000 ft; na 1.0/1.1 uma grelha aproximada.)
#
# Fonte: MEF do SkyDemon (software de navegação que usa dados aeronáuticos
# oficiais), lidos em capturas de ecrã fornecidas pelo utilizador (out-2026).
# Incluem obstáculos e margem — mais adequados a isto do que a altitude pura
# do terreno.
# Conferência com cumes conhecidos: Torre 6539 ft → 6900; Larouco 5036 →
# 5400; Marão 4642 → 5000; Fóia 2959 → 3300; Montejunto 2185 → 2500.
#
# Quadrículas de 1° de longitude × 30' de latitude, como as do SkyDemon.
# Chave: (latitude sul, longitude oeste). Valores em pés.
_TILE_LAT = 0.5
_TILE_LON = 1.0
_MEF_MAR_NAO_LIDO = 600   # quadrículas só de mar sem MEF legível: o
                          # maior valor visto em quadrículas de mar
_TERRAIN_MAX_FT = {
    #            10–9°W            9–8°W             8–7°W             7–6°W
    (42.0, -10): 600,  (42.0, -9): 4700, (42.0, -8): 6200, (42.0, -7): 7500,
    (41.5, -10): 300,  (41.5, -9): 5400, (41.5, -8): 5400, (41.5, -7): 5800,
    (41.0, -10): 300,  (41.0, -9): 4400, (41.0, -8): 5000, (41.0, -7): 4200,
    (40.5, -10): 300,  (40.5, -9): 4700, (40.5, -8): 4900, (40.5, -7): 6000,
    (40.0, -10): 300,  (40.0, -9): 4400, (40.0, -8): 6900, (40.0, -7): 5700,
    (39.5, -10): 1000, (39.5, -9): 3400, (39.5, -8): 3900, (39.5, -7): 3000,
    (39.0, -10): 2500, (39.0, -9): 2100, (39.0, -8): 3700, (39.0, -7): 3600,
    (38.5, -10): 2100, (38.5, -9): 1800, (38.5, -8): 2500, (38.5, -7): 3300,
    (38.0, -10): 2000, (38.0, -9): 2000, (38.0, -8): 2400, (38.0, -7): 3900,
    (37.5, -10): 300,  (37.5, -9): 1600, (37.5, -8): 2400, (37.5, -7): 3400,
    (37.0, -10): 400,  (37.0, -9): 3300, (37.0, -8): 2300, (37.0, -7): 1200,
    (36.5, -10): 300,  (36.5, -9): 500,  (36.5, -8): 400,  (36.5, -7): 900,
    # Só mar, sem MEF legível nas capturas (sul e sudoeste da área)
    (37.5, -11): _MEF_MAR_NAO_LIDO, (37.0, -11): _MEF_MAR_NAO_LIDO,
    (36.5, -11): _MEF_MAR_NAO_LIDO,
    (36.0, -11): _MEF_MAR_NAO_LIDO, (36.0, -10): _MEF_MAR_NAO_LIDO,
    (36.0, -9): _MEF_MAR_NAO_LIDO,  (36.0, -8): _MEF_MAR_NAO_LIDO,
    (35.5, -11): _MEF_MAR_NAO_LIDO, (35.5, -10): _MEF_MAR_NAO_LIDO,
    (35.5, -9): _MEF_MAR_NAO_LIDO,  (35.5, -8): _MEF_MAR_NAO_LIDO,
}

def _tile_key(lon, lat):
    return (math.floor(lat / _TILE_LAT) * _TILE_LAT, math.floor(lon / _TILE_LON) * _TILE_LON)

def _tile_box(key):
    lat_s, lon_w = key
    return box(lon_w, lat_s, lon_w + _TILE_LON, lat_s + _TILE_LAT)

def _tiles_touching(geom):
    """Chaves das quadrículas cuja área intersecta `geom`."""
    x0, y0, x1, y1 = geom.bounds
    for la in range(math.floor(y0 / _TILE_LAT), math.ceil(y1 / _TILE_LAT)):
        for lo in range(math.floor(x0 / _TILE_LON), math.ceil(x1 / _TILE_LON)):
            k = (la * _TILE_LAT, lo * _TILE_LON)
            if _tile_box(k).intersection(geom).area > 1e-9:
                yield k

# Falhar em voz alta: TODAS as quadrículas que tocam a área têm de ter
# valor. Uma em falta daria 0 ft de terreno — base AMSL lida como AGL, o
# erro optimista que isto veio evitar.
_em_falta = [k for k in _tiles_touching(FIR_POLYGON) if k not in _TERRAIN_MAX_FT]
if _em_falta:
    raise RuntimeError(f"Quadrículas de relevo em falta: {_em_falta}")

def _terrain_max_ft(geom):
    """Elevação máxima (ft) das quadrículas que `geom` toca com área."""
    return max((_TERRAIN_MAX_FT[k] for k in _tiles_touching(geom)
                if k in _TERRAIN_MAX_FT), default=0)

def _terrain_elevation_ft(lon, lat):
    """MEF da quadrícula que contém o ponto (lon, lat)."""
    return _TERRAIN_MAX_FT.get(_tile_key(lon, lat), 0)

# Quadrículas que tocam a área — usadas para partir as zonas quando há
# bases AMSL, para a conversão ser feita quadrícula a quadrícula e não com
# o máximo de uma zona enorme (a Estrela não pode pôr o Algarve em NO-GO).
TERRAIN_TILES = [_tile_box(k) for k in _tiles_touching(FIR_POLYGON)]

# -------------------------------------------------
# CIDADES
# -------------------------------------------------

AERODROMES = {
    # Aeródromos civis nacionais de Portugal Continental (código ICAO) —
    # coordenadas oficiais do Manual VFR / eVFR (NAV Portugal), ponto de
    # referência do aeródromo (ARP), AD 2.2. Fonte fornecida directamente
    # pelo utilizador a partir da publicação em vigor.
    "Lisboa (LPPT)":                       (38.7742, -9.1342),
    "Porto (LPPR)":                        (41.2356, -8.6781),
    "Faro (LPFR)":                         (37.0144, -7.9658),
    "Beja (LPBJ)":                         (38.0789, -7.9325),
    "Cascais (LPCS)":                      (38.7256, -9.3553),
    "Évora (LPEV)":                        (38.5297, -7.8919),
    "Vila Real (LPVR)":                    (41.2756, -7.7200),
    "Ponte de Sor (LPSO)":                 (39.2117, -8.0578),
    "Bragança (LPBG)":                     (41.8567, -6.7075),
    "Braga (LPBR)":                        (41.5869, -8.4450),
    "Castelo Branco (LPCB)":               (39.8483, -7.4417),
    "Chaves (LPCH)":                       (41.7219, -7.4628),
    "Coimbra (LPCO)":                      (40.1561, -8.4692),
    "Ferreira do Alentejo (LPFA)":         (38.0392, -8.1042),
    "Figueira dos Cavaleiros (LPFC)":      (38.0775, -8.2358),
    "Espinho (LPIN)":                      (40.9725, -8.6450),
    "Leiria (LPJF)":                       (39.7822, -8.8197),
    "Lousã (LPLZ)":                        (40.1422, -8.2400),
    "Mirandela (LPMI)":                    (41.4703, -7.2278),
    "Amendoeira - Montemor-o-Novo (LPMN)": (38.7092, -8.2753),
    "Mogadouro (LPMU)":                    (41.3944, -6.6844),
    "Portimão (LPPM)":                     (37.1494, -8.5839),
    "Proença-a-Nova (LPPN)":               (39.7311, -7.8747),
    "Santa Cruz (LPSC)":                   (39.1236, -9.3800),
    "Seia (LPSE)":                         (40.4533, -7.6917),
    "Santarém (LPSR)":                     (39.2086, -8.6886),
    "Vilar de Luz/Maia (LPVL)":            (41.2792, -8.5172),
    "Viseu (LPVZ)":                        (40.7256, -7.8892),
}

# Pistas de ultraleves (código LPxx, Manual VFR / eVFR — NAV Portugal, AD 4).
# Coordenadas: ponto de referência (AD 4.2, item 1), convertidas de
# DDMMSSH/DDDMMSSH para decimal. Fonte: eVFR fornecido directamente pelo
# utilizador a partir da publicação oficial em vigor.
ULTRALIGHT_STRIPS = {
    "Alqueidão (LP48)":                   (39.0675, -8.8061),
    "Atouguia da Baleia (LP49)":          (39.3481, -9.3200),
    "Azambuja (LP50)":                    (39.0592, -8.8264),
    "Beja UL (LP51)":                     (38.0603, -7.8775),
    "Benavente (LP52)":                   (38.9133, -8.7858),
    "Cabeceiras de Basto (LP53)":         (41.5553, -7.9878),
    "Campinho (LP54)":                    (38.3592, -7.4658),
    "Cerval (LP55)":                      (41.9750, -8.6733),
    "Herdade da Lameira (LP57)":          (39.2778, -7.7725),
    "Herdade da Zambujeira (LP58)":       (37.6708, -8.1239),
    "Lagos (LP59)":                       (37.1219, -8.6789),
    "Palma (LP61)":                       (38.5147, -8.5761),
    "S. Miguel de Laúndos (LP62)":        (41.4486, -8.7086),
    "Tojeira (LP63)":                     (38.8833, -9.4275),
    "Valdonas (LP64)":                    (39.5908, -8.3714),
    "Cabeço da Vaca (LP66)":              (40.3444, -6.9800),
    "Herdade do Pontal - Pegões (LP68)":  (38.7114, -8.6100),
    "Casalinho Pombal (LP69)":            (39.8864, -8.6489),
    "Valadas - Ferreira do Zêzere (LP71)": (39.6819, -8.2531),
    "Lezírias (LP75)":                    (38.9025, -8.9369),
    "Casarão (LP76)":                     (40.5492, -8.4061),
    "Alentejo Air Park (LP78)":           (37.4656, -8.7372),
    "Faias (LP79)":                       (38.6878, -8.7450),
    "Pias Longas (LP80)":                 (39.5978, -8.5672),
}

# Todos os pontos de referência disponíveis para consulta rápida e mapa —
# aeródromos civis + pistas de ultraleves
AERODROMES = {**AERODROMES, **ULTRALIGHT_STRIPS}
# Compatibilidade — usado por label_region() e marcadores do mapa
CITIES = AERODROMES

# -------------------------------------------------
# DATA MODEL
# -------------------------------------------------

@dataclass
class MetBlock:
    phenomenon: str
    polygon: object
    value: object
    qualifier: str = ""   # LCA, EMBD, etc.
    layer: str = ""       # SFC/FL050, ABV FL070, etc.
    surface: str = ""     # MAR, LAN, COT — superfície afectada
    window: str = ""      # 11–15Z — janela temporal dentro do GAMET

# -------------------------------------------------
# NORMALIZE
# -------------------------------------------------

def normalize(text):
    text = text.upper()
    text = text.replace("–", "-").replace("\r\n", "\n").replace("\r", "\n")
    return text

def looks_unparseable(text):
    """
    Detecta texto que provavelmente não é um GAMET válido/completo — para
    distinguir "GAMET genuinamente calmo" (todos os campos NIL, mas
    presentes) de "texto incompleto ou mal colado" (parser não encontra
    nenhum campo reconhecível, e por omissão mostraria GO em toda a FIR,
    dando uma falsa sensação de segurança).

    Devolve True se nenhum marcador de secção nem nenhum campo meteorológico
    conhecido foi encontrado no texto.
    """
    t = normalize(text)
    has_section = bool(re.search(r"SECN\s+I\b", t))
    # NOTA: SIGMET APPLICABLE não conta como campo meteorológico. Um texto
    # com apenas "SECN I SIGMET APPLICABLE: NIL" não tem nenhum fenómeno
    # legível — se contasse, passaria como parseável e a app mostraria GO
    # em toda a FIR, que é exactamente o falso conforto que esta função
    # existe para evitar.
    field_pattern = re.compile(
        r"\bSFC\s+VIS\b|\bSIG\s+VIS\b|\bVIS\s*:|\bSIGWX\b|\bSIG\s+CLD\b|"
        r"\bCLD\s*:|\bTURB\b|\bICE\b|\bMT\s+OBSC\b|\bVA\s*:"
    )
    has_field = bool(field_pattern.search(t))
    return not (has_section and has_field)

# -------------------------------------------------
# VALIDADE
# -------------------------------------------------

def _build_utc_date(day, hour, minute, ref):
    """
    Constrói um datetime UTC para o dia/hora indicados, procurando o mês
    correcto à volta da data de referência.

    O GAMET só indica o DIA (não o mês), pelo que um GAMET emitido a 31 de
    Março e lido a 1 de Abril tem de ser resolvido para Março — usar
    ref.replace(day=31) levantaria ValueError, porque Abril não tem dia 31.

    Devolve o candidato mais próximo de `ref`, ou None se o dia não existir
    em nenhum dos meses considerados.
    """
    candidates = []
    for month_offset in (-1, 0, 1):
        month = ref.month + month_offset
        year  = ref.year
        if month < 1:
            month += 12
            year  -= 1
        elif month > 12:
            month -= 12
            year  += 1
        try:
            candidates.append(datetime(year, month, day, hour, minute,
                                        tzinfo=timezone.utc))
        except ValueError:
            continue  # dia não existe nesse mês (ex.: 31 de Abril)
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - ref).total_seconds()))


def parse_validity(text):
    """Extrai período de validade e verifica se está ativo."""
    text = normalize(text)
    m = re.search(r"VALID\s+(\d{2})(\d{2})(\d{2})/(\d{2})(\d{2})(\d{2})", text)
    if not m:
        return None, None, False
    day_s, hh_s, mm_s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day_e, hh_e, mm_e = int(m.group(4)), int(m.group(5)), int(m.group(6))
    now = datetime.now(timezone.utc)

    start = _build_utc_date(day_s, hh_s, mm_s, now)
    if start is None:
        return None, None, False

    # O fim é sempre depois do início e o GAMET dura poucas horas — procurar
    # o candidato para o dia final que fique logo a seguir ao início
    end = _build_utc_date(day_e, hh_e, mm_e, start)
    if end is None:
        return None, None, False
    if end <= start:
        # Cruza fronteira de mês/ano — avançar um mês e reconstruir
        month = start.month + 1
        year  = start.year
        if month > 12:
            month = 1
            year += 1
        try:
            end = datetime(year, month, day_e, hh_e, mm_e, tzinfo=timezone.utc)
        except ValueError:
            return None, None, False

    active = start <= now <= end
    return start, end, active

def extract_sigmet_applicable(text):
    """
    Extrai o conteúdo do campo SIGMET APPLICABLE, em vez de o descartar
    silenciosamente. Este campo indica se existe um SIGMET activo que se
    sobrepõe à área/período do GAMET — SIGMETs são emitidos para fenómenos
    que justificam alerta acima do que um GAMET rotineiro cobre (turbulência
    severa, gelo severo, cinzas vulcânicas, ondas de montanha severas, etc.),
    pelo que nunca devem ser ignorados silenciosamente.

    Isola primeiro a linha do SIGMET, e só depois corta conteúdo de campos
    que apareçam a seguir — preserva o texto completo do SIGMET (que pode
    legitimamente conter palavras como TURB ou ICE) sem capturar campos
    subsequentes.

    Devolve (has_active_sigmet: bool, raw_text: str).
    """
    t = normalize(text)
    t = re.sub(r"(SIGMET\s+APPLICABLE)", r"\n\1", t)
    for raw_line in t.splitlines():
        line = raw_line.strip()
        if not line.startswith("SIGMET"):
            continue
        content = re.sub(r"^SIGMET\s+APPLICABLE\s*:?\s*", "", line).strip()
        # Cortar em qualquer campo do GAMET que venha depois (o SIGMET é
        # sempre o último campo da Secção I — o que vier a seguir é outro
        # campo, não parte do texto do SIGMET)
        cut = re.split(
            r"\bSECN\s+II\b|\bSFC\s+VIS\b|\bSIG\s+VIS\b|\bSIG\s+CLD\b|"
            r"\bSIGWX\b|\bMT\s+OBSC\b|\bVIS\s*:|\bCLD\s*:",
            content, maxsplit=1
        )[0]
        content = cut.strip().rstrip("=").strip()
        cleaned = re.sub(r"\bAT\s+TIME\s+OF\s+ISSUE\b", "", content).strip()
        if cleaned in ("", "NIL"):
            return False, content
        return True, content
    return False, ""

# -------------------------------------------------
# GEO
# -------------------------------------------------

def _lon(deg, minn, hemi):
    """Converte graus+minutos numa longitude com sinal (W negativo, E positivo)."""
    val = int(deg) + int(minn) / 60
    return -val if hemi == "W" else val

def _clean_poly(geom):
    """
    Garante que o resultado de uma intersecção geométrica é sempre um
    Polygon ou MultiPolygon limpo — nunca uma GeometryCollection.

    Intersecções entre polígonos cujas fronteiras quase coincidem podem
    produzir GeometryCollection com componentes degenerados (LineString,
    Point) além do Polygon esperado. Sem esta limpeza, geom.boundary
    devolve None para essas GeometryCollections, o que faz com que a
    fronteira desapareça silenciosamente do cálculo de zonas dinâmicas
    (compute_dynamic_regions) — um fenómeno inteiro pode ficar "invisível".
    """
    if geom.is_empty:
        return geom
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
        if not polys:
            return Polygon()  # polígono vazio — nenhuma área válida
        if len(polys) == 1:
            return polys[0]
        return unary_union(polys)
    # Outro tipo (LineString, Point, etc.) — sem área válida
    return Polygon()

def extract_polygon(line):
    poly = FIR_POLYGON
    geo_found = False
    partes = []  # cada qualificador isolado, recortado à FIR

    # BTN N\d\d\d\d AND N\d\d\d\d  (latitude)
    for m in re.findall(r"BTN\s+N(\d{2})(\d{2})\s+AND\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat1 = int(m[0]) + int(m[1]) / 60
        lat2 = int(m[2]) + int(m[3]) / 60
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(FIR_MINX, min(lat1, lat2), FIR_MAXX, max(lat1, lat2)))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    # BTN W/E\d\d\d\d AND W/E\d\d\d\d  (longitude)
    for m in re.findall(r"BTN\s+([WE])(\d{2,3})(\d{2})\s+AND\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon1 = _lon(m[1], m[2], m[0])
        lon2 = _lon(m[4], m[5], m[3])
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(min(lon1, lon2), FIR_MINY, max(lon1, lon2), FIR_MAXY))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    # N OF N\d\d\d\d
    for m in re.findall(r"N\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(FIR_MINX, lat, FIR_MAXX, FIR_MAXY))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    # S OF N\d\d\d\d
    for m in re.findall(r"S\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(FIR_MINX, FIR_MINY, FIR_MAXX, lat))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    # E OF W/E\d\d\d\d
    for m in re.findall(r"E\s+OF\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon = _lon(m[1], m[2], m[0])
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(lon, FIR_MINY, FIR_MAXX, FIR_MAXY))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    # W OF W/E\d\d\d\d
    for m in re.findall(r"W\s+OF\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon = _lon(m[1], m[2], m[0])
        partes.append(_clean_poly(FIR_POLYGON.intersection(box(FIR_MINX, FIR_MINY, lon, FIR_MAXY))))
        poly = _clean_poly(poly.intersection(partes[-1]))

    if geo_found and poly.is_empty and len(partes) > 1:
        # Qualificadores incompatíveis na mesma linha (ex.: "N OF N4000 AND
        # S OF N3800") dão intersecção vazia, o que faria o fenómeno
        # desaparecer. Na dúvida, a leitura conservadora é a união.
        poly = _clean_poly(unary_union([p for p in partes if not p.is_empty]))

    return poly if geo_found else None

# -------------------------------------------------
# WIND PARSER — v25
# -------------------------------------------------

# Níveis do GAMET na ordem de emissão
_WIND_LEVELS = ["1000FT AGL", "2000FT AGL", "5000FT AGL", "FL100", "FL150"]

def parse_wind(secn2: str) -> list:
    """
    Extrai tabela de vento/temperatura da Secção II.
    Devolve lista de dicts:
      [{"station": str, "lat": float, "lon": float,
        "levels": {"1000FT AGL": {"dir":..,"spd":..,"temp":..}, ...}}, ...]
    """
    if not secn2:
        return []

    # Injectar quebras de linha antes de tokens-chave
    # (necessário quando o texto vem numa única linha do fetch IPMA)
    secn2 = re.sub(r"(?<!\n)(WIND/T\s*:)", r"\n\1", secn2)
    secn2 = re.sub(r"(?<!\n)(FZLVL\s*:)", r"\n\1", secn2)
    secn2 = re.sub(r"(?<!\n)(MNM\s+QNH)", r"\n\1", secn2)
    # Injectar quebra antes de cada nível de vento
    secn2 = re.sub(r"(?<!\n)(\d{4}FT\s+AGL)", r"\n\1", secn2)
    secn2 = re.sub(r"(?<!\n)(FL\d{3})\s+(\d{3}/\d{3}KT)", r"\n\1 \2", secn2)
    # Injectar quebra onde nome de estação segue imediatamente valor AMSL do FZLVL
    # ex: "7800FT AMSL LISBOA EVORA FARO" → "7800FT AMSL\nLISBOA EVORA FARO"
    secn2 = re.sub(r"(AMSL)\s*([A-Z]{4,})", r"\1\n\2", secn2)
    # Injectar quebra onde nome de estação (com ou sem espaço) precede coordenada
    # ex: "VISEUN4145 W" → "VISEU\nN4145 W"  (sem espaço)
    # ex: "VISEU N4145 W" → "VISEU\nN4145 W"  (com espaço)
    secn2 = re.sub(r"([A-Z])\s*(N[34]\d{3}\s+W)", r"\1\n\2", secn2)

    # Isolar bloco WIND/T — vai até MNM QNH (captura ambos os grupos de estações)
    wm = re.search(r"WIND/T\s*:(.*?)(?:MNM\s+QNH|$)", secn2, re.DOTALL)
    if not wm:
        return []
    wind_block = wm.group(1)

    # Tokenizar linha a linha — cada grupo: nomes / coords / 5 linhas de vento
    stations = []
    lines = [l.strip() for l in wind_block.splitlines() if l.strip()]

    def _parse_coord_line(line):
        """Extrai pares (lat, lon) de uma linha de coordenadas."""
        coords = []
        for m in re.finditer(r"N(\d{2})(\d{2})\s+W(\d{2,3})(\d{2})", line):
            lat = int(m.group(1)) + int(m.group(2)) / 60
            lon = -(int(m.group(3)) + int(m.group(4)) / 60)
            coords.append((lat, lon))
        return coords

    def _parse_wind_entry(token):
        """Extrai dir/spd/temp de um token tipo '170/007KT PS11'."""
        m = re.match(r"(\d{3})/(\d{3})KT\s+(PS|MS)(\d+)", token)
        if m:
            sign = 1 if m.group(3) == "PS" else -1
            return {
                "dir":  int(m.group(1)),
                "spd":  int(m.group(2)),
                "temp": sign * int(m.group(4)),
            }
        return None

    def _is_station_name_line(line):
        """
        True se a linha contém só nomes de estações (sem dígitos).
        Aceita acentos e pontos (ex.: BRAGANÇA, S. MIGUEL) — o critério
        real é "não tem dígitos e é maioritariamente maiúsculas".
        """
        if re.search(r"\d", line):
            return False
        letters = [c for c in line if c.isalpha()]
        if not letters:
            return False
        return all(c.isupper() for c in letters)

    def _is_coord_line(line):
        return bool(re.search(r"N\d{4}\s+W\d{4,5}", line))

    def _is_level_line(line):
        return bool(re.match(r"(\d{4}FT\s+AGL|FL\d{3})", line))

    def _split_names(names_line, n_expected):
        """
        Divide a linha de nomes em exactamente n_expected estações.

        O número de estações é dado pelas COORDENADAS (inequívocas), não
        pela contagem de palavras — nomes como "VILA REAL" ou "S. MIGUEL
        DE LAUNDOS" têm espaços e partiriam o alinhamento se se usasse
        simplesmente .split(). Quando há mais palavras do que estações,
        as palavras excedentes são agrupadas da esquerda para a direita.
        """
        words = names_line.split()
        if n_expected <= 0:
            return []
        if len(words) == n_expected:
            return words
        if len(words) < n_expected:
            # Menos palavras do que coordenadas — devolver o que há
            return words
        # Mais palavras do que estações: agrupar o excedente no início,
        # mantendo as últimas estações com uma palavra cada
        extra = len(words) - n_expected
        grouped = [" ".join(words[:extra + 1])]
        grouped.extend(words[extra + 1:])
        return grouped

    def flush_group(names_line, coords, lvl_lines):
        """Cria entradas de estação a partir de um grupo recolhido."""
        names = _split_names(names_line, len(coords))
        n = min(len(names), len(coords))
        entries = []
        for k in range(n):
            entry = {
                "station": names[k],
                "lat": coords[k][0],
                "lon": coords[k][1],
                "levels": {},
            }
            for lvl_line in lvl_lines:
                # Extrair nível e os n tokens de vento
                lm = re.match(r"(\d{4}FT\s+AGL|FL\d{3})\s+(.*)", lvl_line)
                if not lm:
                    continue
                level_key = lm.group(1)
                rest = lm.group(2)
                # Cada estação tem: DDD/DDDKT PSxx ou MSxx
                tokens = re.findall(r"\d{3}/\d{3}KT\s+(?:PS|MS)\d+", rest)
                if k < len(tokens):
                    parsed = _parse_wind_entry(tokens[k])
                    if parsed:
                        entry["levels"][level_key] = parsed
            entries.append(entry)
        return entries

    # Parse linha a linha
    cur_names  = ""
    cur_coords = []
    cur_levels = []

    for line in lines:
        if _is_station_name_line(line):
            # Novo grupo — flush anterior se existir
            if cur_names and cur_coords and cur_levels:
                stations.extend(flush_group(cur_names, cur_coords, cur_levels))
            cur_names  = line
            cur_coords = []
            cur_levels = []
        elif _is_coord_line(line):
            cur_coords.extend(_parse_coord_line(line))
        elif _is_level_line(line):
            cur_levels.append(line)

    # Flush último grupo
    if cur_names and cur_coords and cur_levels:
        stations.extend(flush_group(cur_names, cur_coords, cur_levels))

    return stations



# -------------------------------------------------
# PARSER — v25
# -------------------------------------------------

# Palavras-chave que NÃO devem ser confundidas com visibilidade ou altitude
_FL_PATTERN = re.compile(r"FL\d{2,3}")          # FL050, FL100, FL150 …
_HPA_PATTERN = re.compile(r"\d+\s*HPA")         # 986HPA, 1005HPA …

_TS_DISPLAY = {
    "ISOL_EMBD": "ISOL/EMBD",
}

def _ts_label(val):
    return _TS_DISPLAY.get(val, val)

def _trend_icon(layer_str):
    """
    Devolve um ícone de tendência para uma string de camada que pode
    conter INTSF (intensificação) ou WKN (enfraquecimento) — ajuda a
    destacar visualmente fenómenos que estão a piorar, mesmo quando o
    valor de severidade reportado (MOD/SEV) ainda não reflecte isso.
    """
    if not layer_str:
        return ""
    if "INTSF" in layer_str:
        return " 📈"
    if "WKN" in layer_str:
        return " 📉"
    return ""

def _trend_text(layer_str):
    """Variante em texto simples de _trend_icon, para uso no PDF (matplotlib
    não renderiza emoji de forma fiável sem fontes específicas)."""
    if not layer_str:
        return ""
    if "INTSF" in layer_str:
        return " [A INTENSIFICAR]"
    if "WKN" in layer_str:
        return " [A ENFRAQUECER]"
    return ""


# -------------------------------------------------
# JANELA HORÁRIA — estado face à hora actual
# -------------------------------------------------
# A janela "HH/HH" de um campo NÃO altera a decisão (continua a valer para
# todo o período, por ser o conservador: a previsão pode atrasar-se ou
# antecipar-se). Mas o piloto deve saber se, à hora a que consulta, o
# fenómeno já passou ou ainda não começou.
_WINDOW_RE = re.compile(r"(\d{2})–(\d{2})Z")

def window_status(window, start_dt, now=None):
    """
    Devolve "activo agora", "já terminou", "ainda não começou" ou "" (sem
    dados). `start_dt` é o início da validade do GAMET, que fixa o dia a
    que as horas da janela se referem.
    """
    m = _WINDOW_RE.search(window or "")
    if not m or start_dt is None:
        return ""
    now = now or datetime.now(timezone.utc)
    h1, h2 = int(m.group(1)), int(m.group(2))
    if h1 > 24 or h2 > 24:
        return ""
    # O GAMET só dá horas: o dia é o do candidato (véspera, mesmo dia,
    # dia seguinte) mais próximo do início da validade. Ex.: válido desde
    # as 21Z, "00/03" é na madrugada seguinte; válido desde as 12Z, "10/12"
    # é na manhã do próprio dia (e já terminou).
    meia_noite = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    candidatos = [meia_noite + timedelta(days=k, hours=h1) for k in (-1, 0, 1)]
    ini = min(candidatos, key=lambda c: abs((c - start_dt).total_seconds()))
    fim = ini.replace(hour=0) + timedelta(hours=h2) if h2 != 24 else \
          ini.replace(hour=0) + timedelta(days=1)
    if fim <= ini:                          # cruza a meia-noite
        fim += timedelta(days=1)
    if now < ini:
        return "ainda não começou"
    if now >= fim:
        return "já terminou"
    return "activo agora"

def annotate_window_notes(notas, start_dt, now=None):
    """Acrescenta o estado actual às notas de janela horária."""
    saida = []
    for n in notas or []:
        estado = window_status(n, start_dt, now) if "apenas" in n and _WINDOW_RE.search(n) else ""
        saida.append(f"{n} — {estado}" if estado else n)
    return saida

# Fenómenos de SIGWX (além da trovoada) que forçam NO-GO, com a descrição
# usada nos motivos. GR isolado = granizo sem trovoada (TSGR conta como TS).
_SIGWX_SEVEROS = {
    "SQL":  "linha de borrasca",
    "FZRA": "chuva que gela",
    "FZDZ": "chuvisco que gela",
    "DS":   "tempestade de poeira",
    "SS":   "tempestade de areia",
    "FC":   "nuvem funil",
    "TC":   "ciclone tropical",
    "GR":   "granizo",
}

# Base de nuvem em SIG CLD — ver comentário no estado "CLD" de parse_gamet.
_CLD_BASE_RE = re.compile(
    r"(?<![\dA-Z])(?P<base>SFC|\d{3,5})"
    r"(?:-\d{3,5})?"                      # fim do intervalo de bases
    r"(?:/(?:\d{3,5}|XXX))?"              # topo
    r"\s*(?P<unit>HFT|FT)\s+(?P<ref>AGL|AMSL)\b"
)

def parse_gamet(text):

    text = normalize(text)

    # ---- Separar Secções I e II ----
    secn_split = re.split(r"SECN\s+II", text, maxsplit=1)
    secn1 = secn_split[0]
    # Secção II guardada para extração futura (vento, FZLVL, QNH)
    secn2 = secn_split[1] if len(secn_split) > 1 else ""

    # ---- Injetar quebras antes de campos conhecidos ----
    secn1 = re.sub(r"(SECN\s+I\b)", r"\n\1\n", secn1)
    secn1 = re.sub(r"(\bSFC\s+VIS\b|\bSIG\s+VIS\b|\bVIS\s*:)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bSIG\s+CLD\b|\bCLD\s*:)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bSIGWX\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bTURB\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bICE\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bMT\s+OBSC\b)", r"\n\1", secn1)
    # Campos do modelo OACI (Anexo 3) que até à 1.3 eram ignorados:
    # vento generalizado à superfície e onda de montanha. "MTW" só abre
    # campo com dois pontos — "SEV MTW" dentro de TURB não é um campo.
    secn1 = re.sub(r"(\bSFC\s+WSPD\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bMTW\s*:)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bVA\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(SIGMET\s+APPLICABLE)", r"\n\1", secn1)

    # Injetar quebras antes de qualificadores geográficos secundários na mesma linha
    # ex: "...010HFT AGL S OF N3845 ISOL..." → "...010HFT AGL\nS OF N3845 ISOL..."
    # Aplica-se a N OF, S OF, E OF, W OF, BTN quando precedidos de conteúdo meteorológico
    # Qualificadores ligados por AND ("N OF N3840 AND W OF W00815") definem
    # UMA área e não podem ser partidos em linhas diferentes — senão o
    # segundo substitui o primeiro (GAMET real de 14-out-2026: o nevoeiro
    # do N de N3840 passava a cobrir todo o W de W00815, Algarve incluído).
    # O AND fica temporariamente como "&&" para as regras abaixo não o
    # verem como conteúdo meteorológico.
    secn1 = re.sub(
        r"((?:[NSEW]\s+OF\s+[NWE]\d{4,5}|BTN\s+[NWE]\d{4,5}\s+AND\s+[NWE]\d{4,5}))"
        r"\s+AND\s+(?=(?:[NSEW]\s+OF\s+[NWE]\d{4,5}|BTN\s+[NWE]\d{4,5}))",
        r"\1 && ", secn1)
    secn1 = re.sub(r"(\w)\s+(N\s+OF\s+N\d{4})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(S\s+OF\s+N\d{4})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(E\s+OF\s+[WE]\d{4,5})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(W\s+OF\s+[WE]\d{4,5})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(BTN\s+N\d{4})", r"\1\n\2", secn1)
    secn1 = secn1.replace(" && ", " AND ")

    lines = [l.strip() for l in secn1.splitlines() if l.strip()]

    state = "IDLE"
    blocks = []
    current_polygon = FIR_POLYGON
    current_window  = ""

    for raw_line in lines:

        line = raw_line.strip()
        if not line:
            continue

        # Ignorar linha SIGMET APPLICABLE
        if line.startswith("SIGMET"):
            # SIGMET APPLICABLE é sempre o último campo da Secção I
            # Tudo o que vier depois é inválido — parar o parsing aqui
            break

        # ---- Detetar mudança de estado ----
        new_state = None
        if re.match(r"SFC\s+VIS|SIG\s+VIS|VIS\s*:", line):
            new_state = "VIS"
        elif re.match(r"SIG\s+CLD|CLD\s*:", line):
            new_state = "CLD"
        elif re.match(r"SIGWX", line):
            new_state = "SIGWX"
        elif re.match(r"TURB", line):
            new_state = "TURB"
        elif re.match(r"ICE", line):
            new_state = "ICE"
        elif re.match(r"MT\s+OBSC", line):
            new_state = "MT_OBSC"
        elif re.match(r"SFC\s+WSPD", line):
            new_state = "WSPD"
        elif re.match(r"MTW\s*:", line):
            new_state = "MTW"
        elif re.match(r"VA\b", line):
            new_state = "VA"
        elif re.match(r"SECN\s+I\b", line):
            state = "IDLE"
            current_polygon = FIR_POLYGON
            continue

        if new_state:
            state = new_state
            current_polygon = FIR_POLYGON  # reset geo ao mudar de campo
            current_window = ""            # reset janela temporal
            # Remover a keyword da linha para processar só o conteúdo
            content = re.sub(
                r"^(SFC\s+VIS\s*:?|SIG\s+VIS\s*:?|VIS\s*:|SIG\s+CLD\s*:?|CLD\s*:|SIGWX\s*:?|TURB\s*:?|ICE\s*:?|MT\s+OBSC\s*:?|SFC\s+WSPD\s*:?|MTW\s*:|VA\s*:?)\s*",
                "", line
            ).strip()
        else:
            content = line

        if state == "IDLE":
            continue

        # ---- Contexto geográfico ----
        # Um qualificador geográfico que caia fora dos limites da FIR
        # (ex.: "N OF N4200", quando a FIR termina em N41°54') produz um
        # polígono vazio. Nesse caso o fenómeno não se aplica a lado
        # nenhum — mas manter o polígono anterior faria com que passasse
        # a cobrir a FIR inteira, transformando área nula em cobertura
        # total. Marca-se a área como vazia e o bloco é descartado.
        new_poly = extract_polygon(line)
        if new_poly is not None:
            current_polygon = new_poly

        poly = current_polygon
        if poly is not None and poly.is_empty:
            continue  # fenómeno sem área aplicável dentro da FIR

        # ---- Qualificador local ----
        qualifier = ""
        if re.search(r"\bLCA\b", content):
            qualifier = "LCA"

        # ---- Qualificador de superfície (MAR / LAN / COT) ----
        # Indicam que o fenómeno só afecta o mar, só terra, ou a faixa
        # costeira. Com a linha de costa definida (COASTLINE), a área é
        # recortada de facto — a anotação serve para o piloto perceber
        # porque é que a zona tem a forma que tem.
        # Ordem canónica (COT, LAN, MAR) para que "COT AND MAR" e
        # "MAR AND COT" dêem a mesma chave de tradução
        superficies = [s for s in ("COT", "LAN", "MAR")
                       if re.search(rf"\b{s}\b", content)]
        surface = "/".join(superficies)

        # Recortar a área pelo qualificador de superfície. Antes isto era
        # apenas anotado no briefing, por falta de linha de costa; com a
        # costa definida, a geometria passa a ser exacta — um "TURB MAR"
        # deixa de pintar o interior do país.
        if surface:
            sp = surface_polygon(surface)
            if sp is not None:
                recortado = _clean_poly(poly.intersection(sp))
                if recortado.is_empty:
                    # O fenómeno não tem área aplicável dentro da FIR
                    continue
                poly = recortado

        # ---- Janela temporal (HH/HH) ----
        # Um fenómeno pode aplicar-se só a parte do período do GAMET
        # (ex.: "TURB:11/15 ..." num GAMET válido 0900/1500).
        wm = re.search(r"(?:^|\s)(\d{2})/(\d{2})(?=\s|$)", content[:24])
        if wm:
            h1, h2 = int(wm.group(1)), int(wm.group(2))
            if h1 <= 23 and h2 <= 23:
                current_window = f"{h1:02d}–{h2:02d}Z"
        window = current_window

        # ---- PARSE por estado ----

        if state == "VIS":
            vis_content = _FL_PATTERN.sub("", content)
            vis_content = _HPA_PATTERN.sub("", vis_content)

            # Recolher TODOS os valores presentes na linha. Antes usava-se
            # if/elif entre BLW/ABV e os restantes padrões, o que fazia com
            # que "LCA 2000-5000M RA ABV 8000M" reportasse só 8001m e
            # descartasse os 2000m — um erro no sentido optimista (perigoso).
            # A decisão usa depois o mínimo, que é a leitura conservadora.
            consumed_spans = []

            # BLW X → X-1 (conservador)
            for m in re.finditer(r"\bBLW\s+(\d{3,4})M\b", vis_content):
                val = int(m.group(1)) - 1
                consumed_spans.append(m.span())
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier, surface=surface, window=window))

            # ABV X → X+1
            for m in re.finditer(r"\bABV\s+(\d{3,4})M\b", vis_content):
                val = int(m.group(1)) + 1
                consumed_spans.append(m.span())
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier, surface=surface, window=window))

            def _already_consumed(pos):
                return any(s <= pos < e for s, e in consumed_spans)

            # Captura KM
            for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*KM\b", vis_content):
                if _already_consumed(m.start()):
                    continue
                val = int(float(m.group(1)) * 1000)
                blocks.append(MetBlock("VIS", poly, val, qualifier, surface=surface, window=window))

            # Intervalo: 2000-5000M → mínimo
            for m in re.finditer(r"\b(\d{3,4})-(\d{3,4})M\b", vis_content):
                if _already_consumed(m.start()):
                    continue
                val = min(int(m.group(1)), int(m.group(2)))
                consumed_spans.append(m.span())
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier, surface=surface, window=window))

            # Valor simples
            for m in re.finditer(r"(?<!\d)(\d{3,4})M\b", vis_content):
                pos = m.start()
                if _already_consumed(pos):
                    continue
                if vis_content[max(0, pos - 5):pos].rstrip().endswith("-"):
                    continue
                val = int(m.group(1))
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier, surface=surface, window=window))

        elif state == "CLD":
            # Uma única expressão para todas as formas de base de nuvem:
            #   "002HFT AGL"          base única
            #   "002/010HFT AGL"      base/topo (forma-modelo OACI)
            #   "002-004/010HFT AGL"  intervalo de bases/topo
            #   "004/XXXHFT AGL"      topo desconhecido
            #   "SFC/010HFT AGL"      base à superfície → 0 ft
            #   "800/1100FT AGL"      valores em pés (sem o H de centenas)
            # e o mesmo com AMSL. A base é sempre o PRIMEIRO número — o
            # menor do intervalo, por ser o conservador. Antes da v32 a
            # forma base/topo sem intervalo não era reconhecida e nuvens a
            # 200 ft passavam como GO.
            for m in _CLD_BASE_RE.finditer(content):
                # Um número precedido de '-' ou '/' é topo ou fim de intervalo,
                # não base ("TCU/CB 020HFT" mantém-se: o '/' é do TCU/CB e
                # está separado do número por um espaço).
                if m.start() > 0 and content[m.start() - 1] in "-/":
                    continue
                base_txt, unidade, ref = m.group("base"), m.group("unit"), m.group("ref")
                if base_txt == "SFC":
                    base_ft = 0
                elif unidade == "HFT":
                    base_ft = int(base_txt) * 100
                else:
                    base_ft = int(base_txt)
                fen = "BASE_AGL" if ref == "AGL" else "BASE_AMSL"
                blocks.append(MetBlock(fen, poly, base_ft, qualifier, surface=surface, window=window))

        elif state == "SIGWX":
            # FIX: EMBD tratado separadamente e eleva risco
            embd = bool(re.search(r"\bEMBD\b", content))
            ts_qualifier = ""

            if "FRQ" in content:
                ts_qualifier = "FRQ"
            elif "OCNL" in content:
                ts_qualifier = "OCNL"
            elif "ISOL" in content:
                ts_qualifier = "ISOL"

            if "TS" in content or "CB" in content:
                # EMBD eleva: ISOL/EMBD → tratado como OCNL para decisão
                if embd and ts_qualifier == "ISOL":
                    ts_qualifier = "ISOL_EMBD"
                elif embd and not ts_qualifier:
                    ts_qualifier = "EMBD"
                elif not ts_qualifier:
                    ts_qualifier = "GEN"
                blocks.append(MetBlock("TS", poly, ts_qualifier, qualifier, surface=surface, window=window))

            # Outros fenómenos de SIGWX, todos NO-GO para VFR. Até à 1.3 só
            # a trovoada era lida e "SIGWX: SEV SQL" passava como GO.
            severos = [c for c in _SIGWX_SEVEROS if re.search(rf"\b{c}\b", content)]
            if severos:
                blocks.append(MetBlock("WX", poly, "/".join(severos), qualifier,
                                       surface=surface, window=window))

        elif state == "WSPD":
            # Vento médio generalizado à superfície (o GAMET só o inclui
            # acima de 30 kt). Fica o valor mais alto, por ser o conservador.
            kts = []
            for m in re.finditer(r"(\d{2,3})(?:-(\d{2,3}))?\s*(KT|MPS)\b", content):
                vals = [int(v) for v in m.groups()[:2] if v]
                fator = 1.944 if m.group(3) == "MPS" else 1.0
                kts.append(round(max(vals) * fator))
            if kts:
                blocks.append(MetBlock("WSPD", poly, max(kts), qualifier,
                                       surface=surface, window=window))

        elif state == "MTW":
            layer_m = re.search(r"(SFC/FL\d+|FL\d+/FL\d+|ABV\s+FL\d+|BLW\s+FL\d+)", content)
            if "HVY" in content or "SEV" in content:
                severity = "SEV"
            elif "MOD" in content:
                severity = "MOD"
            else:
                severity = None
            if severity:
                blocks.append(MetBlock("MTW", poly, severity, qualifier,
                                       layer_m.group(1) if layer_m else "",
                                       surface=surface, window=window))

        elif state == "TURB":
            layer = ""
            layer_m = re.search(r"(SFC/FL\d+|FL\d+/FL\d+|SFC/\d+FT|ABV\s+FL\d+|BLW\s+FL\d+)", content)
            if layer_m:
                layer = layer_m.group(1)
            # HVY eleva para SEV
            if "HVY" in content or "SEV" in content:
                severity = "SEV"
            elif "MOD" in content:
                severity = "MOD"
            else:
                severity = None
            # Movimento
            mov = ""
            if "STNR" in content:
                mov = "STNR"
            elif re.search(r"MOV\s+[A-Z]{1,3}\s+\d+KT", content):
                mov_m = re.search(r"MOV\s+([A-Z]{1,3}\s+\d+KT)", content)
                if mov_m:
                    mov = f"MOV {mov_m.group(1)}"
            # Tendência
            trend = ""
            if "INTSF" in content:
                trend = "INTSF"
            elif "WKN" in content:
                trend = "WKN"
            if severity:
                extra = " ".join(filter(None, [mov, trend]))
                blocks.append(MetBlock("TURB", poly, severity, qualifier,
                                       layer + (f" {extra}" if extra else ""), surface=surface, window=window))

        elif state == "ICE":
            layer = ""
            layer_m = re.search(r"(ABV\s+FL\d+|FL\d+/FL\d+|SFC/FL\d+|BLW\s+FL\d+)", content)
            if layer_m:
                layer = layer_m.group(1)
            # HVY eleva SEV
            if "HVY" in content or "SEV" in content:
                severity = "SEV"
            elif "MOD" in content:
                severity = "MOD"
            else:
                severity = None
            # Tendência
            trend = ""
            if "INTSF" in content:
                trend = "INTSF"
            elif "WKN" in content:
                trend = "WKN"
            if severity:
                blocks.append(MetBlock("ICE", poly, severity, qualifier, layer + (f" {trend}" if trend else ""), surface=surface, window=window))

        elif state == "MT_OBSC":
            # Montanhas obscurecidas — sempre NO-GO para VFR
            # Só appenda quando a linha activa o estado (new_state presente)
            if new_state == "MT_OBSC":
                blocks.append(MetBlock("MT_OBSC", poly, "MT OBSC", qualifier, surface=surface, window=window))

        elif state == "VA":
            # Cinzas vulcânicas — sempre NO-GO
            if new_state == "VA":
                blocks.append(MetBlock("VA", poly, "VA", qualifier, surface=surface, window=window))

    # ---- Extração Secção II: FZLVL, QNH e vento ----
    fzlvl_values = [int(m) for m in re.findall(r"(\d{4,5})FT\s+AMSL", secn2)]
    fzlvl_min = min(fzlvl_values) if fzlvl_values else None

    qnh_m = re.search(r"MNM\s+QNH\s*:?\s*(\d{3,4})\s*HPA", secn2)
    qnh_min = int(qnh_m.group(1)) if qnh_m else None

    wind_data = parse_wind(secn2)

    return blocks, fzlvl_min, qnh_min, wind_data

# -------------------------------------------------
# ZONAS DINÂMICAS
# -------------------------------------------------
# A app evoluiu de "3 sectores fixos" para geometria dinâmica pura: a
# decisão é calculada directamente sobre a forma real de cada fenómeno do
# GAMET, não sobre regiões pré-definidas. ZONES / SECTOR_* mantêm-se apenas
# como definição da fronteira geográfica da FIR (FIR_POLYGON).

_SURFACE_LABEL = {
    "MAR": "o mar",
    "LAN": "terra",
    "COT": "a faixa costeira",
    "COT/MAR": "a costa e o mar",
    "LAN/MAR": "terra e mar",
    "COT/LAN": "a costa e terra",
    "COT/LAN/MAR": "costa, terra e mar",
}

_PHENOM_LABEL = {
    "VIS": "VIS", "BASE_AGL": "BASE", "BASE_AMSL": "BASE",
    "TS": "TS", "TURB": "TURB", "ICE": "ICE",
    "MT_OBSC": "MT OBSC", "VA": "VA",
    "WSPD": "SFC WSPD", "MTW": "MTW", "WX": "SIGWX",
}


def label_region(poly, max_names=3):
    """
    Devolve um rótulo legível para uma região dinâmica, baseado nos
    aeródromos e pistas que caem dentro dela.

    Escolhe os pontos mais próximos do centro da região — e não os
    primeiros por ordem alfabética — para que o rótulo descreva de facto
    onde a região fica. Numa região que cobre o norte do país, "Braga,
    Porto, Vila Real" é informativo; "Alqueidão, Atouguia, Azambuja"
    (alfabético) não diz nada sobre a localização.

    Se nenhum ponto cair dentro, usa uma descrição geográfica aproximada.
    """
    contidos = []
    for name, (lat, lon) in CITIES.items():
        try:
            if poly.contains(Point(lon, lat)):
                contidos.append((name, lat, lon))
        except Exception:
            continue

    if contidos:
        centro = poly.representative_point()
        # Ordenar por distância ao centro da região
        contidos.sort(key=lambda t: (t[2] - centro.x) ** 2 + (t[1] - centro.y) ** 2)
        nomes = [t[0] for t in contidos[:max_names]]
        nomes.sort()  # apresentar por ordem alfabética, já filtrados
        if len(contidos) > max_names:
            return f"{', '.join(nomes)} +{len(contidos) - max_names}"
        return ", ".join(nomes)

    # Fallback: descrição geográfica aproximada
    centroid = poly.representative_point()
    lat, lon = centroid.y, centroid.x
    fir_cx = (FIR_MINX + FIR_MAXX) / 2
    fir_cy = (FIR_MINY + FIR_MAXY) / 2
    ns = "Norte" if lat > fir_cy else "Sul"
    ew = "Interior" if lon > fir_cx else "Litoral"
    return f"Zona {ns}/{ew}"


_BASE_REASON_RE = re.compile(r"^BASE \d+ft")

def _dedupe_base_reasons(reasons):
    """
    Numa região que junta células com bases diferentes, manter só o motivo
    com a base mais baixa por limiar ("< 300ft", "< 500ft").
    """
    outros, por_limiar = [], {}
    for r in reasons:
        m = re.match(r"^BASE (\d+)ft (.*)$", r)
        if not m:
            outros.append(r)
            continue
        val, limiar = int(m.group(1)), m.group(2)
        if limiar not in por_limiar or val < por_limiar[limiar][0]:
            por_limiar[limiar] = (val, r)
    return sorted(outros + [r for _, r in por_limiar.values()])


def _aggregate_results(resultados):
    """
    Junta os resultados de decisão de várias células numa região: valor
    mais conservador para VIS e base, união do resto. Os fenómenos
    informativos (ICE/TURB moderados) não entram na assinatura e podem
    existir só em parte da região — fica registado como "parcial".
    """
    vis_vals, base_vals = [], []
    ts_s, turb_s, turb_l = set(), set(), set()
    ice_s, ice_l, mt_s, va_s, reasons_s = set(), set(), set(), set(), set()
    n_com_ice = n_com_turb = 0
    for res in resultados:
        (_d, vis, base, ts, turb, turb_layers,
         ice, ice_layers, mt_obsc, va, reasons) = res
        if vis is not None:
            vis_vals.append(vis)
        if base is not None:
            base_vals.append(base)
        ts_s.update(ts)
        turb_s.update(turb)
        turb_l.update(l for l in turb_layers if l)
        ice_s.update(ice)
        ice_l.update(l for l in ice_layers if l)
        mt_s.update(mt_obsc)
        va_s.update(va)
        reasons_s.update(reasons)
        n_com_ice += bool(ice)
        n_com_turb += bool(turb)
    return {
        "vis":          min(vis_vals) if vis_vals else None,
        "base":         min(base_vals) if base_vals else None,
        "ts":           sorted(ts_s),
        "turb":         sorted(turb_s),
        "turb_layers":  sorted(turb_l),
        "turb_parcial": bool(turb_s) and n_com_turb < len(resultados),
        "ice":          sorted(ice_s),
        "ice_layers":   sorted(ice_l),
        "ice_parcial":  bool(ice_s) and n_com_ice < len(resultados),
        "mt_obsc":      sorted(mt_s),
        "va":           sorted(va_s),
        "reasons":      _dedupe_base_reasons(reasons_s),
    }


def _absorb_values(alvo, peq):
    """
    Quando uma região absorve outra (lasca ou bolsa consolidada), os
    valores mostrados passam a cobrir ambas: o mais conservador para VIS e
    base, união para o resto. Até à 1.2 a região absorvente mantinha os
    seus — uma lasca com base 100 ft fundida numa região de 200 ft
    desaparecia do cartão.
    """
    for campo in ("turb", "ice"):
        # Parcial se já o era numa das partes, ou se só uma o tinha
        a_tem, p_tem = bool(alvo.get(campo)), bool(peq.get(campo))
        alvo[campo + "_parcial"] = bool(
            alvo.get(campo + "_parcial") or peq.get(campo + "_parcial")
            or (a_tem != p_tem))
    for campo in ("vis", "base"):
        vals = [v for v in (alvo.get(campo), peq.get(campo)) if v is not None]
        alvo[campo] = min(vals) if vals else None
    for campo in ("ts", "turb", "turb_layers", "ice", "ice_layers", "mt_obsc", "va"):
        alvo[campo] = sorted(set(alvo.get(campo, [])) | set(peq.get(campo, [])))
    alvo["reasons"] = _dedupe_base_reasons(set(alvo.get("reasons", [])) | set(peq.get("reasons", [])))
    alvo["notas"] = sorted(set(alvo.get("notas", [])) | set(peq.get("notas", [])))


def _refine_cells(cells, splitters, tol=1e-3):
    """
    Parte cada célula pelos polígonos `splitters` que a cobrem só
    parcialmente (entre tol e 1-tol da área). Devolve células que estão,
    cada uma, inteiramente dentro ou fora de cada splitter.
    """
    def _partes(geom):
        geom = _clean_poly(geom)
        if geom is None or geom.is_empty:
            return []
        return [g for g in getattr(geom, "geoms", [geom]) if g.area > 1e-9]

    for sp in splitters:
        novas = []
        for c in cells:
            if not c.intersects(sp):
                novas.append(c)
                continue
            inter = c.intersection(sp).area
            frac = inter / c.area
            # Com tol=0 o critério é absoluto (área > 1e-9 de cada lado),
            # o mesmo que _tiles_touching usa.
            parcial = (tol < frac < 1 - tol) if tol > 0 else \
                      (inter > 1e-9 and c.area - inter > 1e-9)
            if parcial:
                novas.extend(_partes(c.intersection(sp)) + _partes(c.difference(sp)))
            else:
                novas.append(c)
        cells = novas
    return cells


def compute_dynamic_regions(blocks):
    """
    Constrói regiões de decisão dinâmica com base na geometria REAL de cada
    fenómeno do GAMET (não em sectores fixos).

    Método: junta as fronteiras de todos os polígonos activos + fronteira da
    FIR, usa polygonize() para particionar a FIR em células atómicas (as
    intersecções reais entre todos os fenómenos), calcula a decisão completa
    para cada célula com a mesma lógica decision(), e funde células com a
    mesma decisão — agregando também os campos (VIS, BASE, TS, TURB, ICE,
    MT_OBSC, VA) para que cada região mostre o mesmo detalhe que um sector
    fixo mostrava.

    Devolve lista de dicts:
      {"polygon", "label", "decision", "vis", "base", "ts", "turb",
       "turb_layers", "ice", "ice_layers", "mt_obsc", "va", "reasons"}
    """
    relevant = [b for b in blocks
                if b.polygon is not None and not b.polygon.is_empty
                and b.polygon.geom_type in ("Polygon", "MultiPolygon")
                and b.phenomenon in ("VIS", "BASE_AGL", "BASE_AMSL", "TS",
                                       "TURB", "ICE", "MT_OBSC", "VA",
                                       "WSPD", "MTW", "WX")]

    def _empty_region():
        dec, vis, base, ts, turb, turb_layers, ice, ice_layers, mt_obsc, va, reasons = decision([])
        return [{
            "polygon": FIR_POLYGON, "label": label_region(FIR_POLYGON),
            "decision": dec, "vis": vis, "base": base, "ts": ts,
            "turb": turb, "turb_layers": turb_layers, "turb_parcial": False,
            "ice": ice, "ice_layers": ice_layers, "ice_parcial": False,
            "mt_obsc": mt_obsc, "va": va, "reasons": reasons, "notas": [],
        }]

    if not relevant:
        return _empty_region()

    # 1. Fronteiras de todos os polígonos relevantes + fronteira da FIR
    boundaries = [FIR_POLYGON.boundary]
    for b in relevant:
        boundaries.append(b.polygon.boundary)
    merged_lines = unary_union(boundaries)

    # 2. Particionar em células atómicas
    atomic_cells = [c for c in polygonize(merged_lines) if not c.is_empty and c.area > 1e-9]
    if not atomic_cells:
        return _empty_region()

    # 2b. Rede de segurança: o polygonize descarta segmentos cujas pontas
    # não coincidem EXACTAMENTE com outra linha, e a célula fica por
    # partir. Partir explicitamente qualquer célula que um fenómeno cubra
    # só em parte garante que cada célula está toda dentro ou toda fora.
    atomic_cells = _refine_cells(atomic_cells, [b.polygon for b in relevant])
    # Com bases AMSL, partir também pela grelha de relevo — a conversão
    # para AGL é feita quadrícula a quadrícula. Aqui sem tolerância
    # relativa: _terrain_max_ft conta qualquer quadrícula que a célula
    # toque com área, por isso a célula tem de ser partida mesmo por uma
    # sobreposição mínima (senão Évora herdava o MEF de uma vizinha).
    if any(b.phenomenon == "BASE_AMSL" for b in relevant):
        atomic_cells = _refine_cells(atomic_cells, TERRAIN_TILES, tol=0.0)

    # 3. Calcular decisão completa por célula (com base no ponto representativo)
    cell_results = []
    cell_notes   = []   # anotações (superfície / janela temporal) por célula
    for cell in atomic_cells:
        # Pertença por ÁREA, não por ponto. Cada célula atómica está
        # inteiramente dentro ou fora de cada fenómeno, por isso basta ver
        # se mais de metade dela está coberta. Até à v31 usava-se
        # representative_point(), que numa célula degenerada devolveu um
        # vértice da fronteira (-9, 38) — fora de TODOS os fenómenos — e
        # 12% da FIR saíram GO com trovoada embebida em toda a área.
        cell_area = cell.area
        events = []
        notas = set()
        for b in relevant:
            if b.polygon.intersection(cell).area < 0.5 * cell_area:
                continue
            if b.phenomenon == "BASE_AMSL":
                # Pior caso dentro da célula: terreno mais alto que ela toca.
                elev_ft = _terrain_max_ft(cell)
                agl_ft = max(0, round(b.value - elev_ft))
                events.append(("BASE", agl_ft, b.qualifier, b.layer))
            elif b.phenomenon == "BASE_AGL":
                events.append(("BASE", b.value, b.qualifier, b.layer))
            else:
                events.append((b.phenomenon, b.value, b.qualifier, b.layer))

            # Anotações que não alteram a decisão mas restringem o alcance
            # real do aviso — mostradas no briefing para o piloto saber
            # que o fenómeno não cobre tudo o que está desenhado.
            rotulo = _PHENOM_LABEL.get(b.phenomenon, b.phenomenon)
            if getattr(b, "surface", ""):
                notas.add(f"{rotulo}: apenas sobre {_SURFACE_LABEL.get(b.surface, b.surface)} "
                          f"(área já recortada)")
            if getattr(b, "window", ""):
                notas.add(f"{rotulo}: apenas {b.window}")

        dec_result = decision(events)
        cell_results.append((cell, dec_result))
        cell_notes.append(tuple(sorted(notas)))

    # 4. Agrupar células por (decisão + conjunto de causas).
    #
    # Agrupar só por decisão fazia com que faixas ADJACENTES com causas
    # diferentes — nevoeiro no Minho, gelo no Algarve, ambos NO-GO —
    # formassem um único cartão a listar todas as causas em todo o lado.
    # Um piloto no Algarve via "VIS 1000m FG" que estava a 500 km dele.
    #
    # Incluir a assinatura de causas no agrupamento garante que cada região
    # só mostra o que de facto se aplica à sua área.
    from collections import defaultdict

    def _cause_signature(res):
        """
        Identidade das causas de uma célula, para agrupamento.

        Usa apenas os MOTIVOS da decisão — não todos os fenómenos
        presentes. Fenómenos informativos (ICE ou TURB moderados) não
        alteram a decisão e, se entrassem na assinatura, partiriam zonas
        com o mesmo risco real em vários cartões: um GAMET típico passava
        de 3 para 8 regiões sem acrescentar informação útil.
        """
        # A base exacta não entra na assinatura, só o limiar que ela
        # violou: com bases AMSL cada quadrícula de relevo dá uma base AGL
        # diferente e o briefing partia-se em dezenas de cartões. A região
        # mostra a base mínima (a conservadora) — ver _dedupe_base_reasons.
        return tuple(sorted(_BASE_REASON_RE.sub("BASE #ft", r) for r in res[-1]))

    grouped_cells = defaultdict(list)   # (decisão, assinatura) -> células
    group_results = defaultdict(list)   # (decisão, assinatura) -> resultados
    group_notes   = defaultdict(set)    # (decisão, assinatura) -> anotações
    for (cell, res), notas in zip(cell_results, cell_notes):
        key = (res[0], _cause_signature(res), notas)
        grouped_cells[key].append(cell)
        group_results[key].append(res)
        group_notes[key].update(notas)

    # 5. Dentro de cada grupo, separar por componente conexo — duas bolsas
    # geograficamente distintas com as mesmas causas continuam a ser
    # regiões independentes.
    regions = []
    for grupo_id, (key, cells) in enumerate(grouped_cells.items()):
        dec_level = key[0]
        resultados = group_results[key]
        merged = unary_union(cells)
        components = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]

        for comp in components:
            if comp.is_empty or comp.area <= 1e-9:
                continue
            # Valores agregados SÓ com as células desta bolsa. Até à 1.2
            # eram agregados no grupo inteiro: duas bolsas separadas com as
            # mesmas causas (ex.: base 200 ft a norte, 100 ft a sul)
            # mostravam ambas a base mais baixa.
            meus = [res for cell, res in zip(cells, resultados)
                    if comp.intersection(cell).area > 0.5 * cell.area]
            regions.append(dict(
                polygon=comp,
                label=label_region(comp),
                decision=dec_level,
                notas=sorted(group_notes[key]),
                _grupo=grupo_id,
                **_aggregate_results(meus),
            ))

    # 6. Fundir fragmentos residuais.
    #
    # A partição em células atómicas pode gerar slivers — fatias muito
    # finas nas fronteiras entre fenómenos, sem significado operacional.
    # São absorvidos pela região vizinha compatível de maior área, para
    # não poluírem o briefing com cartões de 0,3% da FIR.
    regions = _merge_slivers(regions)
    regions = _consolidate_groups(regions)

    # Ordenar da pior decisão para a melhor e, dentro da mesma decisão,
    # da maior área para a menor (as zonas mais relevantes primeiro)
    _order = {"NO-GO": 0, "MARGINAL": 1, "GO": 2}
    regions.sort(key=lambda r: (_order.get(r["decision"], 3), -r["polygon"].area))
    return regions


_MAX_REGIOES = 8

def _consolidate_groups(regions, max_regioes=_MAX_REGIOES):
    """
    Se o briefing tiver demasiadas regiões, juntar as bolsas separadas que
    têm exactamente a mesma decisão e as mesmas causas numa só região
    (multipolígono). Não se perde informação — os valores já eram
    agregados por grupo — e evita-se um briefing com 30 cartões quando
    bases AMSL sobre relevo variado dão um padrão em xadrez.
    """
    if len(regions) > max_regioes:
        por_grupo = defaultdict(list)
        for r in regions:
            por_grupo[r.get("_grupo")].append(r)
        juntas = []
        for membros in por_grupo.values():
            base = dict(membros[0])
            if len(membros) > 1:
                for m in membros[1:]:
                    _absorb_values(base, m)
                poly = unary_union([m["polygon"] for m in membros])
                base["polygon"], base["label"] = poly, label_region(poly)
            juntas.append(base)
        regions = juntas
    for r in regions:
        r.pop("_grupo", None)
    return regions


def _merge_slivers(regions, min_area_frac=0.015):
    """
    Absorve regiões residuais (< 1,5% da FIR) na vizinha compatível.

    A prioridade é uma região da MESMA decisão e com as MESMAS causas, para
    não misturar motivos. Se não houver, funde-se com a vizinha da mesma
    decisão de maior área — a decisão nunca muda, pelo que não há risco de
    um NO-GO desaparecer. Uma região pequena que seja a única com aquela
    decisão é sempre preservada.
    """
    if len(regions) <= 1:
        return regions

    limite = min_area_frac * FIR_POLYGON.area
    grandes = [r for r in regions if r["polygon"].area >= limite]
    pequenas = [r for r in regions if r["polygon"].area < limite]
    if not pequenas or not grandes:
        return regions

    def _assinatura(r):
        return (r["decision"], r["vis"], r["base"], tuple(r["ts"]),
                tuple(r["turb"]), tuple(r["ice"]),
                tuple(r["mt_obsc"]), tuple(r["va"]))

    orfas = []
    for peq in pequenas:
        # 1ª escolha: mesma decisão e mesmas causas
        candidatos = [g for g in grandes if _assinatura(g) == _assinatura(peq)]
        # 2ª escolha: mesma decisão (motivos podem diferir, decisão não)
        if not candidatos:
            candidatos = [g for g in grandes if g["decision"] == peq["decision"]]
        if not candidatos:
            orfas.append(peq)   # única com esta decisão — preservar
            continue

        # Preferir uma que toque a região pequena; senão, a mais próxima
        tocam = [c for c in candidatos if c["polygon"].intersects(peq["polygon"])]
        alvo = (max(tocam, key=lambda c: c["polygon"].area) if tocam
                else min(candidatos, key=lambda c: c["polygon"].distance(peq["polygon"])))

        fundido = unary_union([alvo["polygon"], peq["polygon"]])
        if isinstance(fundido, MultiPolygon):
            # Não são contíguos — fundir perderia área da FIR. Preservar o
            # fragmento como região autónoma; é preferível um cartão extra
            # a um buraco no mapa.
            orfas.append(peq)
            continue
        alvo["polygon"] = fundido
        alvo["label"] = label_region(fundido)
        _absorb_values(alvo, peq)

    return grandes + orfas


def active_bulletins(bulletins, now=None):
    """
    A partir dos SIGMET/AIRMET LPPC lidos da página do IPMA, devolve
    (sigmets_activos, airmets_activos): os que estão dentro da validade e
    não foram cancelados por um "CNL SIGMET n". Os próprios boletins de
    cancelamento nunca contam como activos.

    Na dúvida (validade ilegível), o boletim conta como activo — é a
    leitura conservadora.
    """
    now = now or datetime.now(timezone.utc)
    cancelados = set()
    for b in bulletins:
        for m in re.finditer(r"\bCNL\s+(SIGMET|AIRMET)\s+(\S+)", b):
            cancelados.add((m.group(1), m.group(2)))
    sigmets, airmets = [], []
    for b in bulletins:
        cab = re.match(r"LPPC\s+(SIGMET|AIRMET)\s+(\S+)\s+VALID\s+(\d{2})(\d{2})(\d{2})/(\d{2})(\d{2})(\d{2})", b)
        if not cab:
            continue
        tipo, num = cab.group(1), cab.group(2)
        if re.search(r"\bCNL\s+(SIGMET|AIRMET)\b", b) or (tipo, num) in cancelados:
            continue
        d1, h1, m1, d2, h2, m2 = (int(cab.group(i)) for i in range(3, 9))
        ini = _build_utc_date(d1, h1, m1, now)
        fim = _build_utc_date(d2, h2, m2, ini) if ini else None
        if fim is not None and ini is not None and fim <= ini:
            fim = fim + timedelta(days=1)
        activo = (ini is None or fim is None) or (ini <= now < fim)
        if activo:
            (sigmets if tipo == "SIGMET" else airmets).append(b)
    return sigmets, airmets


# -------------------------------------------------
# ARQUIVO — GAMETs e SIGMETs recolhidos (ramo "dados" do repositório)
# -------------------------------------------------
# O índice (dados/indice.json) é gerado pelo scripts/recolher_gamet.py a
# cada recolha. Cada entrada traz o ficheiro, a hora de recolha e a validade
# (início/fim em UTC). As funções abaixo são puras — a rede fica de fora —
# para poderem ser testadas sem ligação.

def _iso_utc(txt):
    try:
        return datetime.strptime(txt, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def ultimo_gamet_valido(indice, agora=None):
    """
    Entrada do índice do GAMET arquivado que está em vigor em `agora`, ou
    None. Havendo vários (GAMET + AMD/COR), fica o de início mais recente e,
    dentro desse, o recolhido por último — uma emenda é sempre recolhida
    depois do original que corrige.
    """
    agora = agora or datetime.now(timezone.utc)
    validos = []
    for e in (indice or {}).get("gamets", []):
        ini, fim = _iso_utc(e.get("inicio")), _iso_utc(e.get("fim"))
        if ini and fim and ini <= agora < fim:
            validos.append((ini, e.get("recolhido", ""), e))
    if not validos:
        return None
    return max(validos, key=lambda t: (t[0], t[1]))[2]


def boletins_do_periodo(indice, inicio, fim):
    """
    SIGMET e AIRMET arquivados cuja validade se sobrepõe a [inicio, fim).
    Devolve (sigmets, airmets) — textos. Os boletins de cancelamento não
    contam, mas um SIGMET cancelado a meio conta na mesma: esteve em vigor
    durante parte do período, que é o que interessa para rever um GAMET
    antigo (leitura conservadora). Validade ilegível também conta.
    """
    sigmets, airmets = [], []
    for e in (indice or {}).get("sigmets", []):
        txt = e.get("texto", "")
        cab = re.match(r"LPPC\s+(SIGMET|AIRMET)\b", txt)
        if not cab or re.search(r"\bCNL\s+(SIGMET|AIRMET)\b", txt):
            continue
        ini, fim_b = _iso_utc(e.get("inicio")), _iso_utc(e.get("fim"))
        sobrepoe = (ini is None or fim_b is None or inicio is None or fim is None
                    or (ini < fim and inicio < fim_b))
        if sobrepoe:
            (sigmets if cab.group(1) == "SIGMET" else airmets).append(txt)
    return sigmets, airmets


def boletins_arquivados(indice, agora=None, horas=24):
    """
    Textos dos SIGMET/AIRMET arquivados recolhidos nas últimas `horas`
    (incluindo os CNL), para passar a active_bulletins() — que trata a
    validade e os cancelamentos. O corte evita que um SIGMET de outro mês
    com o mesmo dia seja lido como sendo deste (o boletim só traz o dia);
    um SIGMET dura no máximo 6 h, por isso 24 h é folga larga.
    """
    agora = agora or datetime.now(timezone.utc)
    out = []
    for e in (indice or {}).get("sigmets", []):
        rec = _iso_utc(e.get("recolhido"))
        if e.get("texto") and (rec is None or agora - timedelta(hours=horas) <= rec <= agora + timedelta(hours=1)):
            out.append(e["texto"])
    return out


def gamet_de_recurso(fetch_indice, fetch_texto, agora=None):
    """
    Recurso para a janela em que o IPMA já retirou o GAMET anterior e ainda
    não publicou o novo (~45 min antes de cada emissão): o último GAMET
    arquivado que continua em vigor.

    fetch_indice() → (ok, indice|erro); fetch_texto(ficheiro) → (ok, texto|erro).
    Devolve (texto, entrada, boletins_arquivados) ou (None, motivo, []).
    O texto só é aceite se a validade lida do próprio GAMET também o der
    como em vigor — não se confia apenas no nome do ficheiro.
    """
    agora = agora or datetime.now(timezone.utc)
    ok, indice = fetch_indice()
    if not ok:
        return None, f"arquivo indisponível ({indice})", []
    entrada = ultimo_gamet_valido(indice, agora)
    if entrada is None:
        return None, "nenhum GAMET em vigor no arquivo", []
    ok, texto = fetch_texto(entrada["ficheiro"])
    if not ok:
        return None, f"não foi possível ler {entrada['ficheiro']} ({texto})", []
    texto = texto.strip()
    ini, fim = parse_validity(texto)[:2]
    if not (ini and fim and ini <= agora < fim):
        return None, "o GAMET arquivado já não está em vigor", []
    return texto, entrada, boletins_arquivados(indice, agora)


def apply_sigmet_override(regions, sigmet_text):
    """
    Quando existe um SIGMET activo aplicável ao GAMET, força NO-GO em todas
    as regiões dinâmicas. Não temos a geometria exacta do SIGMET (o campo
    SIGMET APPLICABLE no GAMET não descreve fronteiras), pelo que a postura
    mais segura é tratá-lo como aplicável a toda a área coberta, em vez de
    tentar (erradamente) restringi-lo a uma parte da FIR.
    """
    reason = f"SIGMET activo aplicável — {sigmet_text[:120]}"
    for region in regions:
        region["decision"] = "NO-GO"
        if reason not in region["reasons"]:
            region["reasons"] = sorted(set(region["reasons"]) | {reason})
    return regions


def find_region_for_point(regions, lat, lon):
    """
    Devolve a região dinâmica que contém o ponto (lat, lon). Se o ponto
    cair fora de todas as regiões — o que só deve acontecer perto da
    fronteira aproximada da FIR (ex.: aeródromos no extremo do território,
    como Bragança) — devolve a região geometricamente mais próxima, desde
    que a distância seja pequena (< 0.2°, ~20km). Só devolve None se o
    ponto estiver claramente fora da área coberta pelo GAMET.
    """
    pt = Point(lon, lat)
    for region in regions:
        if region["polygon"].contains(pt):
            return region
    # Fallback: região mais próxima, com tolerância para folgas na
    # fronteira aproximada da FIR
    closest = min(regions, key=lambda r: r["polygon"].distance(pt), default=None)
    if closest is not None and closest["polygon"].distance(pt) < 0.2:
        return closest
    return None


def check_strong_wind(wind_data, threshold_kt=20, level="1000FT AGL"):
    """
    Verifica se algum dos vento reportados na Secção II excede um limiar de
    velocidade a baixa altitude — relevante para ultraleves, que têm
    limites de vento cruzado tipicamente mais apertados que aviação geral
    convencional. Isto é um AVISO GERAL informativo — não é geometricamente
    atribuído a nenhuma região dinâmica (o vento é reportado por estação
    pontual, não por área), e não altera a decisão GO/MARGINAL/NO-GO.

    Devolve lista de strings de aviso, ou [] se nada de relevante.
    """
    warnings = []
    for station in wind_data:
        levels = station.get("levels", {})
        entry = levels.get(level)
        if entry and entry.get("spd") is not None and entry["spd"] >= threshold_kt:
            warnings.append(f"{station['station']}: {entry['spd']}KT a {level}")
    return warnings

# -------------------------------------------------
# DECISION — v25
# -------------------------------------------------

# Hierarquia de risco TS (do mais grave para o menos grave)
TS_RISK = {
    "FRQ":       3,   # NO-GO
    "EMBD":      3,   # NO-GO
    "ISOL_EMBD": 2,   # NO-GO (ISOL mas embutida — imprevisível)
    "OCNL":      2,   # NO-GO
    "ISOL":      1,   # MARGINAL
    "GEN":       2,   # NO-GO (genérico sem qualificador — conservador)
}

def decision(events):
    vis_vals    = [v for t, v, *_ in events if t == "VIS"]
    base_vals   = [v for t, v, *_ in events if t == "BASE"]
    ts_vals     = [v for t, v, *_ in events if t == "TS"]
    turb_vals   = [v for t, v, *_ in events if t == "TURB"]
    ice_vals    = [v for t, v, *_ in events if t == "ICE"]
    mt_obsc     = [v for t, v, *_ in events if t == "MT_OBSC"]
    va_vals     = [v for t, v, *_ in events if t == "VA"]

    # Camadas verticais de TURB e ICE (para mostrar no briefing)
    turb_layers = [layer for t, v, q, layer in events if t == "TURB" and layer]
    ice_layers  = [layer for t, v, q, layer in events if t == "ICE"  and layer]

    # Separar LCA (local) do geral
    vis_lca  = [v for t, v, q, *_ in events if t == "VIS" and q == "LCA"]
    vis_gen  = [v for t, v, q, *_ in events if t == "VIS" and q != "LCA"]

    vis  = min(vis_vals)  if vis_vals  else None
    base = min(base_vals) if base_vals else None

    # Nível máximo de risco TS
    ts_max_risk = max((TS_RISK.get(v, 1) for v in ts_vals), default=0)

    reasons = []
    decision_level = "GO"

    # ---- Visibilidade ----
    # LCA não força NO-GO geral, mas é registada como aviso
    if vis_gen and min(vis_gen) < 1500:
        decision_level = "NO-GO"
        reasons.append(f"VIS {min(vis_gen)}m < 1500m")
    elif vis_lca and min(vis_lca) < 1500:
        # VIS local abaixo mínimo → MARGINAL (não NO-GO de área)
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"VIS LCA {min(vis_lca)}m < 1500m (local)")
    elif vis and vis < 3000:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        lca_note = " (LCA)" if vis_lca and vis in vis_lca else ""
        reasons.append(f"VIS{lca_note} {vis}m < 3000m")

    # ---- Base de nuvens ----
    if base is not None and base < 300:
        decision_level = "NO-GO"
        reasons.append(f"BASE {base}ft < 300ft")
    elif base is not None and base < 500:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"BASE {base}ft < 500ft")

    # ---- Cinzas vulcânicas — sempre NO-GO ----
    if va_vals:
        decision_level = "NO-GO"
        reasons.append("VA (cinzas vulcânicas) — NO-GO imediato")

    # ---- Montanhas obscurecidas — NO-GO para VFR ----
    if mt_obsc:
        decision_level = "NO-GO"
        reasons.append("MT OBSC (montanhas obscurecidas) — NO-GO VFR")

    # ---- Trovoadas ----
    if ts_max_risk >= 2:
        decision_level = "NO-GO"
        reasons.append(f"TS {'/'.join(_ts_label(v) for v in ts_vals)} (risco alto)")
    elif ts_max_risk == 1:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"TS {'/'.join(_ts_label(v) for v in ts_vals)}")

    # ---- Turbulência severa — NO-GO (risco de perda de controlo/estrutural,
    # especialmente crítico em ultraleves) ----
    if "SEV" in turb_vals:
        decision_level = "NO-GO"
        layer_note = f" {'/'.join(turb_layers)}" if turb_layers else ""
        reasons.append(f"TURB SEV{layer_note} — risco severo")

    # ---- Gelo severo — NO-GO (a generalidade dos ultraleves não tem
    # sistemas de degelo) ----
    if "SEV" in ice_vals:
        decision_level = "NO-GO"
        layer_note = f" {'/'.join(ice_layers)}" if ice_layers else ""
        reasons.append(f"ICE SEV{layer_note} — risco severo")

    # ---- Vento generalizado à superfície (SFC WSPD) — NO-GO a partir de
    # 30 kt: fora dos limites de qualquer ultraleve ----
    wspd_vals = [v for t, v, *_ in events if t == "WSPD"]
    if wspd_vals and max(wspd_vals) >= 30:
        decision_level = "NO-GO"
        reasons.append(f"SFC WSPD {max(wspd_vals)}KT ≥ 30KT (vento à superfície)")

    # ---- Onda de montanha (MTW). SEV → NO-GO; MOD → MARGINAL, ao contrário
    # da turbulência moderada: as descendentes junto ao relevo são perigosas
    # para aeronaves com pouca potência ----
    mtw_vals = [v for t, v, *_ in events if t == "MTW"]
    mtw_layers = [layer for t, v, q, layer in events if t == "MTW" and layer]
    mtw_note = f" {'/'.join(mtw_layers)}" if mtw_layers else ""
    if "SEV" in mtw_vals:
        decision_level = "NO-GO"
        reasons.append(f"MTW SEV{mtw_note} (onda de montanha) — risco severo")
    elif "MOD" in mtw_vals:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"MTW MOD{mtw_note} (onda de montanha)")

    # ---- Outros fenómenos severos de SIGWX — NO-GO ----
    wx_codes = sorted({c for t, v, *_ in events if t == "WX" for c in v.split("/")})
    if wx_codes:
        decision_level = "NO-GO"
        desc = ", ".join(f"{c} ({_SIGWX_SEVEROS.get(c, c)})" for c in wx_codes)
        reasons.append(f"SIGWX {desc}")

    return decision_level, vis, base, ts_vals, turb_vals, turb_layers, ice_vals, ice_layers, mt_obsc, va_vals, reasons

# -------------------------------------------------
# PDF EXPORT — v14
# -------------------------------------------------

def _pdf_briefing_page(pdf, regions, gamet_text, validity_label):
    """Página 1 — Decisão VFR por região dinâmica (empilhadas verticalmente)."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4
    ax.axis("off")
    fig.patch.set_facecolor("white")

    colors = {"GO": "#2ecc71", "MARGINAL": "#e67e22", "NO-GO": "#e74c3c"}
    y = 0.97

    ax.text(0.5, y, "LPPC GAMET – Briefing VFR", ha="center", va="top",
            fontsize=16, fontweight="bold", transform=ax.transAxes)
    y -= 0.03
    if validity_label:
        ax.text(0.5, y, validity_label, ha="center", va="top",
                fontsize=9, color="#555", transform=ax.transAxes)
    y -= 0.02
    ax.text(0.5, y, "Zonas calculadas com a geometria real do GAMET",
            ha="center", va="top", fontsize=7, color="#888",
            style="italic", transform=ax.transAxes)
    y -= 0.045

    for region in regions:
        dec         = region["decision"]
        vis         = region["vis"]
        base        = region["base"]
        ts          = region["ts"]
        turb        = region["turb"]
        turb_layers = region["turb_layers"]
        ice         = region["ice"]
        ice_layers  = region["ice_layers"]
        mt_obsc     = region["mt_obsc"]
        va_vals     = region["va"]
        reasons     = region["reasons"]
        pct         = 100 * region["polygon"].area / FIR_POLYGON.area
        color = colors.get(dec, "#888")

        # Cabeçalho da região: decisão em destaque à esquerda, label por
        # baixo. Antes, label e decisão partilhavam a mesma linha (x=0.05 e
        # x=0.75) e um label longo escrevia por cima da decisão.
        ax.text(0.05, y, f"{dec}", va="top", fontsize=11,
                fontweight="bold", color=color, transform=ax.transAxes)
        ax.text(0.24, y, f"({pct:.0f}% da FIR)", va="top", fontsize=8,
                color="#666", transform=ax.transAxes)
        y -= 0.024

        etiqueta = region["label"]
        if len(etiqueta) > 78:
            etiqueta = etiqueta[:75].rstrip(", ") + "…"
        ax.text(0.05, y, etiqueta, va="top", fontsize=8.5,
                fontweight="bold", color="#333", transform=ax.transAxes)
        y -= 0.026

        entries = [
            f"VIS:  {vis} m"        if vis  is not None else "VIS:  —",
            f"BASE: {base} ft AGL"  if base is not None else "BASE: —",
            f"TS:   {', '.join(_ts_label(v) for v in ts)}" if ts else "TS:   —",
        ]
        if turb:
            turb_str = ", ".join(
                f"{v} ({turb_layers[idx]}){_trend_text(turb_layers[idx])}" if idx < len(turb_layers) and turb_layers[idx] else v
                for idx, v in enumerate(turb)
            )
            if region.get("turb_parcial"):
                turb_str += " (parte)"
            entries.append(f"TURB: {turb_str}")
        else:
            entries.append("TURB: —")
        if ice:
            ice_str = ", ".join(
                f"{v} ({ice_layers[idx]}){_trend_text(ice_layers[idx])}" if idx < len(ice_layers) and ice_layers[idx] else v
                for idx, v in enumerate(ice)
            )
            if region.get("ice_parcial"):
                ice_str += " (parte)"
            entries.append(f"ICE:  {ice_str}")
        else:
            entries.append("ICE:  —")
        if va_vals:
            entries.append("VA:   CINZAS VULC.")
        if mt_obsc:
            entries.append("MTOBS: MONT. OBSC.")

        for entry in entries:
            ax.text(0.08, y, entry, va="top", fontsize=8,
                    fontfamily="monospace", transform=ax.transAxes)
            y -= 0.024

        if reasons:
            ax.text(0.08, y, "Motivos: " + "; ".join(reasons), va="top",
                    fontsize=7, color="#555", transform=ax.transAxes,
                    wrap=True)
            y -= 0.024

        notas_reg = annotate_window_notes(region.get("notas"),
                                          parse_validity(gamet_text)[0])
        if notas_reg:
            ax.text(0.08, y, "Alcance: " + "; ".join(notas_reg), va="top",
                    fontsize=7, color="#777", style="italic",
                    transform=ax.transAxes, wrap=True)
            y -= 0.024

        # Linha divisória entre regiões
        y -= 0.006
        ax.plot([0.05, 0.95], [y, y], color="#ddd", linewidth=0.5, transform=ax.transAxes)
        y -= 0.018

        if y < 0.15:  # sem espaço para mais — parar (texto bruto fica só com o que couber)
            break

    # Rodapé com texto bruto (se ainda houver espaço)
    if y > 0.12:
        y -= 0.01
        ax.text(0.05, y, "Texto GAMET original:", va="top", fontsize=7,
                fontweight="bold", color="#555", transform=ax.transAxes)
        y -= 0.025

        # Quebrar por palavras, não a meio delas. O corte anterior era
        # fixo em blocos de 100 caracteres, o que partia termos como
        # "W00835" em "W00" + "835" e tornava o texto difícil de conferir.
        import textwrap
        limpo = " ".join(gamet_text.split())
        raw_lines = textwrap.wrap(limpo, width=105)

        truncado = False
        for rl in raw_lines:
            if y < 0.035:
                truncado = True
                break
            ax.text(0.05, y, rl, va="top", fontsize=6,
                    fontfamily="monospace", color="#777", transform=ax.transAxes)
            y -= 0.019

        if truncado:
            ax.text(0.05, y, "[…] texto truncado — ver GAMET completo na app",
                    va="top", fontsize=6, style="italic", color="#999",
                    transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _pdf_map_page(pdf, regions):
    """Página 2 — Mapa com zonas dinâmicas (geometria real do GAMET)."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    colors = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    for region in regions:
        poly = region["polygon"]
        dec = region["decision"]
        geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        # Regiões muito estreitas quase desaparecem com o traço fino —
        # reforçar o contorno para continuarem visíveis no mapa impresso
        estreita = poly.area < 0.05 * FIR_POLYGON.area
        lw = 2.0 if estreita else 1.0
        for g in geoms:
            if g.is_empty or not hasattr(g, "exterior") or g.exterior is None:
                continue
            x, y = g.exterior.xy
            ax.fill(x, y, alpha=0.35, color=colors.get(dec, "grey"))
            ax.plot(x, y, color=colors.get(dec, "grey"), linewidth=lw)

    # Rotular com o código ICAO/LP em vez do nome completo. Os nomes
    # extensos dos 52 pontos sobrepunham-se e tornavam o mapa ilegível;
    # o código é curto e é o que um piloto reconhece de imediato.
    for name, (lat, lon) in CITIES.items():
        ax.plot(lon, lat, "ko", markersize=2.5)
        codigo = name[name.rfind("(") + 1:name.rfind(")")] if "(" in name else name
        ax.text(lon + 0.04, lat, codigo, fontsize=5.5, color="#333",
                va="center")

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title("Mapa VFR – FIR LPPC (zonas dinâmicas)", fontsize=12, fontweight="bold")

    # Mostrar na legenda apenas as decisões presentes — incluir MARGINAL
    # quando não existe nenhuma zona marginal induz em erro
    presentes = {r["decision"] for r in regions}
    handles = [Patch(facecolor=colors[d], alpha=0.35, label=d)
               for d in ("GO", "MARGINAL", "NO-GO") if d in presentes]
    handles.append(Line2D([0], [0], marker="o", color="black",
                          linestyle="None", label="Aeródromo / pista UL"))
    ax.legend(handles=handles, fontsize=8, loc="lower left")

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _pdf_secn2_page(pdf, fzlvl_min, qnh_min):
    """Página 3 — Dados adicionais Secção II."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.95, "Dados Adicionais – Secção II",
            ha="center", va="top", fontsize=14, fontweight="bold",
            transform=ax.transAxes)

    entries = []
    if fzlvl_min:
        entries.append(f"Nível de gelo mínimo (FZLVL): {fzlvl_min} ft AMSL")
    if qnh_min:
        entries.append(f"QNH mínimo: {qnh_min} hPa")

    y = 0.85
    for entry in entries:
        ax.text(0.1, y, entry, va="top", fontsize=11,
                transform=ax.transAxes)
        y -= 0.06

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def generate_pdf(regions, gamet_text, fzlvl_min, qnh_min, validity_label) -> bytes:
    """Gera um PDF completo (briefing + mapa + secção II) e devolve os bytes."""
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_briefing_page(pdf, regions, gamet_text, validity_label)
        _pdf_map_page(pdf, regions)
        if fzlvl_min or qnh_min:
            _pdf_secn2_page(pdf, fzlvl_min, qnh_min)
        # Metadados
        d = pdf.infodict()
        d["Title"]   = "LPPC GAMET Briefing VFR"
        d["Author"]  = f"GAMET Decoder v{APP_VERSION}"
        d["Subject"] = "Briefing meteorológico VFR – FIR LPPC"
    buf.seek(0)
    return buf.getvalue()


# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------

# Recurso ao arquivo quando o IPMA não tem GAMET (pedido no carregamento,
# mas só aqui o motor — parse_validity — já está definido).
if st.session_state.pop("_tentar_recurso", False):
    _txt_r, _info_r, _bol_arq = gamet_de_recurso(fetch_arquivo_indice, fetch_arquivo)
    if _txt_r:
        st.session_state["gamet_loaded"] = _txt_r
        st.session_state["gamet_loaded_at"] = (
            datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%MZ") + " (arquivo)")
        st.session_state["gamet_fonte"] = "arquivo_recurso"
        st.session_state["arquivo_entrada"] = _info_r
        # SIGMETs: os do arquivo (recolhidos de 15 em 15 min) mais os da
        # página do IPMA, se respondeu — a união é a leitura conservadora
        _pag = st.session_state.get("_pagina_sem_gamet") or []
        st.session_state["ipma_boletins"] = _bol_arq + [b for b in _pag if b not in _bol_arq]
        st.session_state["ipma_boletins_at"] = (st.session_state.get("_pagina_sem_gamet_at")
                                                or datetime.now(timezone.utc))
        st.session_state["ipma_boletins_fonte"] = (
            "página do IPMA + arquivo" if _pag else "arquivo (recolha de 15 em 15 min)")
        st.rerun()
    else:
        st.session_state["gamet_fetch_error"] = (
            st.session_state.get("gamet_fetch_error", "") + f"\n\nArquivo: {_info_r}.")
        st.rerun()   # o erro é mostrado lá em cima, no expander do IPMA

if st.button("🔍 Analisar GAMET") and gamet_text.strip():
    st.session_state["_active_gamet_text"] = gamet_text.strip()

if st.session_state.get("_active_gamet_text"):
    gamet_text = st.session_state["_active_gamet_text"]

    # ---- Validade ----
    validity_label = ""
    start_dt, end_dt, active = parse_validity(gamet_text)
    if start_dt and end_dt:
        fmt = "%d/%H%MZ"
        validity_label = f"Válido: {start_dt.strftime(fmt)} – {end_dt.strftime(fmt)}"
        label = f"⏱️ {validity_label}"
        if active:
            # Mostrar quanto tempo falta — ajuda a decidir se vale a pena
            # esperar pelo próximo GAMET antes de planear o voo
            restante = end_dt - datetime.now(timezone.utc)
            minutos = max(0, int(restante.total_seconds() // 60))
            horas, mins = divmod(minutos, 60)
            tempo = f"{horas}h{mins:02d}m" if horas else f"{mins} min"
            if minutos <= 30:
                st.warning(f"{label} ⏳ Expira em **{tempo}** — o próximo "
                           f"GAMET está prestes a ser emitido")
            else:
                st.success(f"{label} ✅ Em vigor · expira em {tempo}")
        else:
            st.warning(label + " ⚠️ FORA DO PERÍODO DE VALIDADE — dados podem estar desatualizados")

    blocks, fzlvl_min, qnh_min, wind_data = parse_gamet(gamet_text)
    dynamic_regions = compute_dynamic_regions(blocks)

    has_sigmet, sigmet_text = extract_sigmet_applicable(gamet_text)

    # De onde veio o GAMET em análise. Só conta se for exactamente o texto
    # carregado (se o utilizador o editou ou colou outro, é "manual").
    _gamet_e_o_carregado = gamet_text.strip() == st.session_state.get("gamet_loaded", "").strip()
    _fonte = st.session_state.get("gamet_fonte", "ipma") if _gamet_e_o_carregado else "manual"
    _entrada_arq = st.session_state.get("arquivo_entrada") or {}

    if _fonte == "arquivo_hist":
        st.warning(
            "📚 **GAMET DO ARQUIVO — não é o GAMET actual.** Recolhido às "
            f"{_entrada_arq.get('recolhido', '?')}. Serve para rever uma situação "
            "passada; não o uses para planear um voo.")
    elif _fonte == "arquivo_recurso":
        st.warning(
            "🕓 **O IPMA ainda não publicou o novo GAMET** (o anterior é retirado "
            "cerca de 45 min antes da emissão). A mostrar o **último GAMET "
            "arquivado, ainda em vigor** (recolhido às "
            f"{_entrada_arq.get('recolhido', '?')}). Recarrega dentro de alguns "
            "minutos para obter o novo.")

    # SIGMETs. Três casos:
    #  · GAMET actual (IPMA ou recurso ao arquivo): os SIGMET/AIRMET em vigor
    #    AGORA — lidos da página do IPMA e/ou do arquivo. Cobrem o caso que o
    #    GAMET não cobre: um SIGMET emitido DEPOIS do GAMET.
    #  · GAMET do arquivo: os SIGMETs arquivados que estiveram em vigor
    #    durante a validade desse GAMET.
    #  · GAMET colado à mão ou do histórico da sessão: não se sabe a que
    #    momento corresponde — só conta o "SIGMET APPLICABLE" do próprio texto.
    _bol = st.session_state.get("ipma_boletins")
    _bol_at = st.session_state.get("ipma_boletins_at")
    sig_ipma, air_ipma = ([], [])
    _verificado = False
    if _fonte in ("ipma", "arquivo_recurso") and _bol is not None:
        sig_ipma, air_ipma = active_bulletins(_bol)
        _verificado = True
        _onde = ("em vigor no IPMA" if _fonte == "ipma"
                 else f"em vigor ({st.session_state.get('ipma_boletins_fonte', 'arquivo')})")
    elif _fonte == "arquivo_hist" and st.session_state.get("arquivo_indice"):
        sig_ipma, air_ipma = boletins_do_periodo(
            st.session_state["arquivo_indice"],
            _iso_utc(_entrada_arq.get("inicio")), _iso_utc(_entrada_arq.get("fim")))
        _verificado = True
        _onde = "durante a validade deste GAMET (arquivo)"
    if sig_ipma:
        dynamic_regions = apply_sigmet_override(
            dynamic_regions, " | ".join(b[:80] for b in sig_ipma))
        st.error(
            f"🚨 **{len(sig_ipma)} SIGMET {_onde}**"
            + ("" if has_sigmet else " — **não referido no GAMET**, provavelmente "
               "emitido depois dele") + ". A decisão foi forçada a NO-GO em toda a "
            "área. Lê o SIGMET completo:\n\n"
            + "\n\n".join(f"`{b}`" for b in sig_ipma)
        )
    if air_ipma:
        st.warning(
            f"⚠️ **{len(air_ipma)} AIRMET {_onde}.** A app mostra-o mas "
            "não o interpreta — lê-o:\n\n"
            + "\n\n".join(f"`{b}`" for b in air_ipma)
        )
    if not _verificado:
        st.info("ℹ️ SIGMETs do IPMA **não verificados**: o GAMET em análise não "
                "foi carregado do IPMA nem do arquivo nesta sessão. Só conta o "
                "campo \"SIGMET APPLICABLE\" do próprio GAMET.")
    elif not sig_ipma and not air_ipma:
        if _fonte == "arquivo_hist":
            st.caption("✅ Nenhum SIGMET/AIRMET LPPC arquivado durante a validade "
                       "deste GAMET.")
        elif _bol_at:
            st.caption(f"✅ Sem SIGMET/AIRMET LPPC em vigor "
                       f"({st.session_state.get('ipma_boletins_fonte', 'página do IPMA')}, "
                       f"verificado às {_bol_at.strftime('%H:%MZ')}).")

    if has_sigmet:
        dynamic_regions = apply_sigmet_override(dynamic_regions, sigmet_text)
        st.error(
            "🚨 **SIGMET ACTIVO APLICÁVEL A ESTE GAMET.** "
            "Um SIGMET indica fenómenos que justificam alerta acima do que "
            "um GAMET rotineiro cobre. A decisão foi forçada a NO-GO em "
            "toda a área — consulta o SIGMET completo antes de voar; esta "
            "app não o substitui.\n\n"
            f"Texto reportado: {sigmet_text}"
        )

    if looks_unparseable(gamet_text):
        st.error(
            "⚠️ **Nenhum campo meteorológico reconhecido no texto.** "
            "Isto pode significar que o GAMET está incompleto, mal colado, "
            "ou num formato não suportado — **não** que as condições estão "
            "calmas. Confirma o texto antes de confiar na decisão abaixo."
        )

    wind_warnings = check_strong_wind(wind_data)
    if wind_warnings:
        st.warning(
            "💨 **Vento forte reportado a 1000ft AGL** (aviso geral — não "
            "afecta a decisão GO/MARGINAL/NO-GO nem está atribuído a uma "
            "região específica, já que o vento é reportado por estação "
            "pontual, não por área). Confirma os limites de vento cruzado "
            "da tua aeronave:\n\n" + "\n".join(f"- {w}" for w in wind_warnings)
        )

    # ---- Histórico (últimos 5) ----
    if "gamet_history" not in st.session_state:
        st.session_state["gamet_history"] = []
    history = st.session_state["gamet_history"]
    # Evitar duplicados consecutivos
    if not history or history[0]["text"] != gamet_text.strip():
        history.insert(0, {
            "text":      gamet_text.strip(),
            "timestamp": datetime.now(timezone.utc).strftime("%d/%m %H:%MZ"),
            "label":     validity_label or datetime.now(timezone.utc).strftime("%d/%m %H:%MZ"),
        })
        st.session_state["gamet_history"] = history[:5]

    # ---- Veredicto global ----
    # Responde de imediato à pergunta principal — "posso voar?" — sem
    # obrigar a interpretar N cartões de região primeiro.
    _area_fir = FIR_POLYGON.area
    _area_por_dec = {}
    for _reg in dynamic_regions:
        _d = _reg["decision"]
        _area_por_dec[_d] = _area_por_dec.get(_d, 0) + _reg["polygon"].area

    _pior = next((d for d in ("NO-GO", "MARGINAL", "GO") if d in _area_por_dec), "GO")
    _pct_pior = 100 * _area_por_dec.get(_pior, 0) / _area_fir

    if _pior == "GO":
        st.success("### ✅ GO — condições favoráveis em toda a FIR")
    else:
        _partes = [
            f"**{d}** {100 * _area_por_dec[d] / _area_fir:.0f}%"
            for d in ("NO-GO", "MARGINAL", "GO") if d in _area_por_dec
        ]
        _resumo = " · ".join(_partes)
        if _pior == "NO-GO":
            st.error(f"### 🔴 NO-GO em {_pct_pior:.0f}% da FIR\n\n{_resumo}")
        else:
            st.warning(f"### ⚠️ MARGINAL em {_pct_pior:.0f}% da FIR\n\n{_resumo}")

    # ---- Consulta rápida por aeródromo ----
    st.subheader("✈️ Consulta Rápida")
    airport_options = ["— Seleccionar —"] + sorted(AERODROMES.keys())
    # Manter a escolha entre análises — quem voa sempre do mesmo aeródromo
    # não tem de o seleccionar de cada vez
    _guardado = st.session_state.get("aerodromo_preferido", "— Seleccionar —")
    _idx = airport_options.index(_guardado) if _guardado in airport_options else 0
    selected_airport = st.selectbox(
        "Aeródromo de partida/chegada:",
        options=airport_options,
        index=_idx,
        help="Mostra a decisão VFR exacta para esse aeródromo, com base na "
             "geometria real do GAMET — não numa aproximação por sector. "
             "A escolha fica memorizada para as próximas análises. "
             "Coordenadas aproximadas — confirma sempre na AIP Portugal em vigor.",
    )
    if selected_airport != _guardado:
        st.session_state["aerodromo_preferido"] = selected_airport
    if selected_airport != "— Seleccionar —":
        lat, lon = AERODROMES[selected_airport]
        found = find_region_for_point(dynamic_regions, lat, lon)
        if found:
            dec = found["decision"]
            icon = {"GO": "✅", "MARGINAL": "⚠️", "NO-GO": "🔴"}.get(dec, "❔")
            if dec == "NO-GO":
                st.error(f"{icon} **{selected_airport}: {dec}**")
            elif dec == "MARGINAL":
                st.warning(f"{icon} **{selected_airport}: {dec}**")
            else:
                st.success(f"{icon} **{selected_airport}: {dec}**")
            if found["reasons"]:
                st.caption("Motivos: " + "; ".join(found["reasons"]))
        else:
            st.info(f"{selected_airport} está fora da FIR LPPC coberta por este GAMET.")

    # ---- Briefing (zonas dinâmicas — geometria real do GAMET) ----
    st.subheader("📋 Briefing")
    st.caption(
        "As zonas são calculadas a partir da geometria real do GAMET "
        "(não de sectores fixos) — cada região reflecte exactamente a área "
        "coberta pelos fenómenos meteorológicos reportados. "
        "Ordenadas da situação mais grave para a menos grave."
    )

    # Grelha por linhas: cria um novo conjunto de colunas a cada 3 regiões.
    # Antes usava-se um único st.columns(...) com cols[i % n], o que fazia
    # a 4.ª região empilhar por baixo da 1.ª — a ordem de leitura deixava
    # de seguir a gravidade e um NO-GO podia aparecer visualmente abaixo
    # de um GO.
    POR_LINHA = 3
    cols = []

    for i, region in enumerate(dynamic_regions):
        if i % POR_LINHA == 0:
            restantes = len(dynamic_regions) - i
            cols = st.columns(min(POR_LINHA, restantes))
        col = cols[i % POR_LINHA]

        dec         = region["decision"]
        vis         = region["vis"]
        base        = region["base"]
        ts          = region["ts"]
        turb        = region["turb"]
        turb_layers = region["turb_layers"]
        ice         = region["ice"]
        ice_layers  = region["ice_layers"]
        mt_obsc     = region["mt_obsc"]
        va_vals     = region["va"]
        reasons     = region["reasons"]
        pct         = 100 * region["polygon"].area / FIR_POLYGON.area

        with col:
            st.markdown(f"### {region['label']}")
            st.caption(f"{pct:.0f}% da FIR")

            if dec == "NO-GO":
                st.error("🔴 NO-GO")
            elif dec == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.write(f"👁️ VIS: {vis} m"       if vis  is not None else "👁️ VIS: —")
            st.write(f"☁️ BASE: {base} ft AGL" if base is not None else "☁️ BASE: —")
            st.write(f"⛈️ TS: {', '.join(_ts_label(v) for v in ts)}" if ts else "⛈️ TS: —")

            if turb:
                turb_str = ", ".join(
                    f"{v} ({turb_layers[idx]}){_trend_icon(turb_layers[idx])}" if idx < len(turb_layers) and turb_layers[idx] else v
                    for idx, v in enumerate(turb)
                )
                if region.get("turb_parcial"):
                    turb_str += " *(parte da zona)*"
                st.write(f"🌪 TURB: {turb_str}")
            else:
                st.write("🌪 TURB: —")

            if ice:
                ice_str = ", ".join(
                    f"{v} ({ice_layers[idx]}){_trend_icon(ice_layers[idx])}" if idx < len(ice_layers) and ice_layers[idx] else v
                    for idx, v in enumerate(ice)
                )
                if region.get("ice_parcial"):
                    ice_str += " *(parte da zona)*"
                st.write(f"❄️ ICE: {ice_str}")
            else:
                st.write("❄️ ICE: —")

            st.write("🌋 VA: ⚠️ CINZAS VULCÂNICAS" if va_vals else "🌋 VA: —")
            st.write("⛰️ MT OBSC: ⚠️ MONTANHAS OBSCURECIDAS" if mt_obsc else "⛰️ MT OBSC: —")

            if reasons:
                with st.expander("ℹ️ Motivos da decisão", expanded=True):
                    for r in reasons:
                        st.write(f"• {r}")

            # Anotações que restringem o alcance real do aviso — o
            # fenómeno não cobre necessariamente toda a área desenhada
            notas = annotate_window_notes(region.get("notas"), start_dt)
            if notas:
                st.caption("**Alcance restrito:**  \n" +
                           "  \n".join(f"· {n}" for n in notas))

    # ---- Mapa Interativo (Folium) ----
    st.subheader("🗺️ Mapa Interativo")
    st.caption("Zonas desenhadas com a geometria real do GAMET.")
    fcolors = {"GO": "#2ecc71", "MARGINAL": "#e67e22", "NO-GO": "#e74c3c"}

    if _FOLIUM_OK:
        fmap = folium.Map(
            location=[39.5, -8.5],
            zoom_start=6,
            tiles="OpenStreetMap",
        )

        for region in dynamic_regions:
            poly = region["polygon"]
            dec  = region["decision"]
            color = fcolors.get(dec, "#888")
            geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
            tooltip = f"{region['label']}: {dec}" + (f" — {'; '.join(region['reasons'])}" if region["reasons"] else "")
            for g in geoms:
                if g.is_empty or not hasattr(g, "exterior") or g.exterior is None:
                    continue
                coords = [[lat, lon] for lon, lat in zip(*g.exterior.xy)]
                folium.Polygon(
                    locations=coords,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.35,
                    weight=2,
                    tooltip=tooltip,
                ).add_to(fmap)

        for name, (lat, lon) in CITIES.items():
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color="black",
                fill=True,
                fill_color="black",
                fill_opacity=0.8,
                tooltip=name,
            ).add_to(fmap)
        # st.iframe substitui st.components.v1.html (descontinuado); manter
        # o antigo como recurso para versões do Streamlit sem st.iframe.
        if hasattr(st, "iframe"):
            st.iframe(fmap._repr_html_(), height=500)
        else:
            st.components.v1.html(fmap._repr_html_(), height=500)
    else:
        st.warning("Folium não instalado — mapa estático disponível no PDF.")

    # ---- Informação Secção II ----
    if fzlvl_min or qnh_min:
        st.subheader("🌡️ Dados Adicionais (Secção II)")
        c1, c2 = st.columns(2)
        with c1:
            if fzlvl_min:
                st.info(f"🧊 Nível de gelo mínimo (FZLVL): **{fzlvl_min} ft AMSL**")
        with c2:
            if qnh_min:
                st.info(f"🌡️ QNH mínimo: **{qnh_min} hPa**")

    # ---- Legenda ----
    with st.expander("📖 Legenda do Briefing", expanded=False):
        st.markdown("""
### 📐 Referência técnica

**Decisão VFR:**
- 🟢 GO – Condições VFR aceitáveis
- 🟠 MARGINAL – Próximo dos mínimos (precaução)
- 🔴 NO-GO – Abaixo dos mínimos ou TS de risco alto

**Campos:**
- 👁️ VIS – Visibilidade horizontal em metros. LCA = condição localizada (não cobre toda a área)
- ☁️ BASE – Base das nuvens significativas (SIG CLD) em ft AGL (acima do solo). Bases em AMSL são convertidas contra a elevação máxima da zona
- ⛈️ TS – Trovoadas: ISOL / OCNL / FRQ / EMBD
- 🌪 TURB – Turbulência: MOD (moderada) / SEV (severa)
- ❄️ ICE – Gelo em voo: MOD (moderado) / SEV (severo)

**Regras de decisão:**
- VIS < 1500 m → NO-GO (MARGINAL se LCA) · VIS < 3000 m → MARGINAL
- BASE < 300 ft AGL → NO-GO · BASE < 500 ft AGL → MARGINAL
- TS ISOL → MARGINAL · TS OCNL / GEN / ISOL/EMBD / EMBD / FRQ → NO-GO
- TURB ou ICE SEV/HVY → NO-GO (MOD é só informativo)
- MTW (onda de montanha) SEV → NO-GO · MOD → MARGINAL
- SFC WSPD ≥ 30 kt → NO-GO
- SIGWX: SQL, FZRA, FZDZ, DS, SS, GR, FC → NO-GO
- MT OBSC, VA, SIGMET em vigor → NO-GO

---

### 🧑‍✈️ O que significa para mim?

**Decisão:**
- 🟢 GO – As condições estão dentro dos mínimos. Voo VFR possível com atenção normal.
- 🟠 MARGINAL – As condições estão no limite. Voa apenas se tiveres experiência e alternativas claras. Monitoriza a meteorologia em voo.
- 🔴 NO-GO – Não descolares em VFR. As condições estão abaixo dos mínimos legais ou há trovoadas significativas.

**Visibilidade (VIS):**
- Abaixo de 3000m começas a ter dificuldade em ver e evitar obstáculos e outro tráfego.
- Abaixo de 1500m o voo VFR é ilegal na maioria das classes de espaço aéreo.
- LCA significa que a má visibilidade é localizada — pode ser nevoeiro numa zona específica, não em toda a rota.

**Base das nuvens (BASE):**
- Indica a que altura acima do solo começam as nuvens significativas previstas no GAMET (nebulosidade fragmentada ou encoberta, ou nuvens convectivas).
- Abaixo de 500ft AGL tens muito pouco espaço para voar por baixo das nuvens.
- Abaixo de 300ft AGL o voo VFR é praticamente impossível em segurança.

**Trovoadas (TS):**
- ISOL (isoladas) – Menos de 25% da área afetada. Visíveis e evitáveis, mas requerem desvio.
- OCNL (ocasionais) – Entre 25% e 50% da área. Difíceis de evitar completamente.
- FRQ (frequentes) – Mais de 50% da área. Praticamente impossível voar sem atravessar áreas perigosas.
- EMBD (embutidas) – Trovoadas escondidas dentro de nuvens. Não as consegues ver. Extremamente perigosas — evitar sempre.
- ISOL/EMBD – Isoladas mas embutidas em nuvens. Invisíveis ao piloto — tratar como OCNL.

**Turbulência (TURB):**
- MOD (moderada) – Dificulta o controlo da aeronave. Objetos soltos podem mover-se na cabine. Reduz o conforto e aumenta a fadiga.
- SEV (severa) – Pode causar perda temporária de controlo. Objetos podem ser projetados. Evitar esta área.

**Gelo em voo (ICE):**
- Forma-se quando a aeronave voa através de nuvens com temperatura abaixo de 0°C.
- MOD (moderado) – Acumulação significativa. Perigoso para aeronaves sem sistema anti-gelo.
- SEV (severo) – Acumulação rápida e intensa. Perigoso mesmo com sistema anti-gelo. Evitar.
- O FZLVL (nível de gelo) indica a altitude a partir da qual a temperatura desce abaixo de 0°C.

**QNH mínimo:**
- Pressão atmosférica mínima prevista na área. Usa este valor para calibrar o altímetro se voares para o ponto mais baixo da FIR.

**Outros fenómenos:**
- ⛰️ MT OBSC – Montanhas obscurecidas por nuvens ou neblina. NO-GO imediato para VFR — terreno elevado invisível.
- 🌋 VA – Cinzas vulcânicas. NO-GO imediato — perigo para motores e visibilidade.
- 💨 SFC WSPD – Vento médio generalizado à superfície (o GAMET só o indica a partir de 30 kt). NO-GO: fora dos limites de qualquer ultraleve.
- 🌊 MTW – Onda de montanha. SEV → NO-GO. MOD → MARGINAL: as descendentes junto ao relevo podem exceder a razão de subida de uma aeronave com pouca potência.
- SQL – Linha de borrasca · FZRA / FZDZ – Chuva / chuvisco que gela · DS / SS – Tempestade de poeira / areia · GR – Granizo · FC – Nuvem funil. Todos NO-GO.
- 🚨 SIGMET – Aviso de fenómeno perigoso. A app usa o campo "SIGMET APPLICABLE" do GAMET **e** os SIGMETs em vigor na página do IPMA (que podem ter saído depois do GAMET). Qualquer um deles põe NO-GO em toda a área — lê sempre o SIGMET completo.
- AIRMET – Mostrado se existir, mas não interpretado pela app.
- BLW – Abaixo de (ex: VIS BLW 1500M → visibilidade inferior a 1500m).
- ABV – Acima de (ex: VIS ABV 5000M → visibilidade superior a 5000m).
- HVY – Intensidade elevada (equivale a SEV para decisão VFR).
- INTSF – Fenómeno em intensificação (tendência de agravamento).
- WKN – Fenómeno em enfraquecimento (tendência de melhoria).
- STNR – Fenómeno estacionário.
- MOV – Fenómeno em movimento (ex: MOV NE 15KT).
""")

    # ---- Exportar PDF ----
    st.subheader("📄 Exportar Briefing")
    with st.spinner("A gerar PDF..."):
        pdf_bytes = generate_pdf(dynamic_regions, gamet_text, fzlvl_min, qnh_min, validity_label)
    fname = f"briefing_lppc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%MZ')}.pdf"
    st.download_button(
        label="⬇️ Descarregar Briefing PDF",
        data=pdf_bytes,
        file_name=fname,
        mime="application/pdf",
    )

    # ---- Vento por níveis ----
    if wind_data:
        st.subheader("💨 Vento e Temperatura por Níveis")
        levels = _WIND_LEVELS
        header = ["Nível"] + [s["station"] for s in wind_data]
        rows = []
        for lvl in levels:
            row = [lvl]
            for s in wind_data:
                entry = s["levels"].get(lvl)
                if entry:
                    sign = "+" if entry["temp"] >= 0 else ""
                    row.append(
                        f"{entry['dir']:03d}°/{entry['spd']:03d}kt "
                        f"{sign}{entry['temp']}°C"
                    )
                else:
                    row.append("—")
            rows.append(row)
        if _PANDAS_OK:
            df = pd.DataFrame(rows, columns=header)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            md = "| " + " | ".join(header) + " |\n"
            md += "| " + " | ".join(["---"] * len(header)) + " |\n"
            for row in rows:
                md += "| " + " | ".join(row) + " |\n"
            st.markdown(md)

# ---- Histórico de GAMETs ----
st.divider()
if st.session_state.get("gamet_history"):
    with st.expander("🕐 Histórico de GAMETs analisados", expanded=False):
        history = st.session_state["gamet_history"]
        for idx, entry in enumerate(history):
            col_lbl, col_btn = st.columns([4, 1])
            with col_lbl:
                st.write(f"**{idx+1}.** {entry['label']} _(analisado {entry['timestamp']})_")
            with col_btn:
                if st.button("Carregar", key=f"hist_{idx}"):
                    st.session_state["gamet_loaded"] = entry["text"]
                    st.session_state["gamet_fonte"] = "historico"
                    st.rerun()
