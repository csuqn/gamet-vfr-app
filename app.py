import streamlit as st
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
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union, polygonize
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Motor Cartográfico v16.0")

# -------------------------------------------------
# IPMA SELF-BRIEFING — fetch automático
# -------------------------------------------------

_SIGMET_URL = "https://brief-ng.ipma.pt/showsigmet.php"

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

def fetch_gamet_ipma() -> tuple:
    """
    Carrega o GAMET do LPPC directamente do Self-Briefing IPMA.
    O endpoint é público — não requer autenticação.
    Devolve (sucesso: bool, texto_ou_erro: str).
    """
    try:
        ts = int(time.time() * 1000)
        resp = requests.get(
            _SIGMET_URL,
            params={"_": ts},
            headers={"User-Agent": "Mozilla/5.0 (compatible; GAMET-Decoder/16.0)"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return False, f"Erro de ligação ao IPMA: {e}"

    # Remover tags HTML e normalizar espaços
    text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Isolar bloco LPPC GAMET ... =
    m = re.search(r"(LPPC\s+GAMET\s+VALID\s+.+?=)", text, re.DOTALL)
    if not m:
        return False, "GAMET do LPPC não encontrado. Pode não estar emitido ainda."

    return True, m.group(1).strip()


# -------------------------------------------------
# UI — carregamento automático
# -------------------------------------------------

# Auto-fetch ao arrancar se não há GAMET em sessão
if "gamet_loaded" not in st.session_state:
    with st.spinner("A carregar GAMET do Self-Briefing IPMA..."):
        ok, result = fetch_gamet_ipma()
    if ok:
        st.session_state["gamet_loaded"]    = result
        st.session_state["gamet_loaded_at"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%MZ")

with st.expander("📡 GAMET do IPMA", expanded=False):
    col_btn, col_next = st.columns([1, 2])
    with col_btn:
        if st.button("🔄 Recarregar GAMET"):
            with st.spinner("A carregar..."):
                ok, result = fetch_gamet_ipma()
            if ok:
                st.session_state["gamet_loaded"]    = result
                st.session_state["gamet_loaded_at"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%MZ")
                st.success("✅ GAMET actualizado!")
            else:
                st.error(f"❌ {result}")
    with col_next:
        nxt = next_gamet_time()
        st.info(f"⏭️ Próximo GAMET esperado: **{nxt.strftime('%H:%MZ')}** "
                f"(em {format_countdown(nxt)})")

    if "gamet_loaded_at" in st.session_state:
        st.caption(f"⏱️ Carregado às {st.session_state['gamet_loaded_at']}")

# Preencher text_area com GAMET carregado (ou vazio para input manual)
_default = st.session_state.get("gamet_loaded", "")

gamet_text = st.text_area(
    "Texto do GAMET (LPPC) — carregado automaticamente ou cole aqui",
    value=_default,
    height=200,
)

# -------------------------------------------------
# SECTORES
# -------------------------------------------------

SECTOR_NORTE = Polygon([
    (-8.843611, 41.867500), (-6.850000, 41.900000),
    (-6.621944, 41.700556), (-6.818333, 40.399444),
    (-8.016667, 39.383333), (-10.000000, 38.900000),
    (-9.784722, 39.348611), (-9.442500, 40.199722),
    (-9.368056, 40.382222), (-9.250000, 40.648889),
    (-9.186389, 40.827778),
]).buffer(0)

SECTOR_CENTRO = Polygon([
    (-6.818333, 40.399444), (-7.230000, 37.999444),
    (-9.000000, 38.000000), (-10.000000, 38.000000),
    (-10.000000, 38.900000), (-8.016667, 39.383333),
]).buffer(0)

SECTOR_SUL = Polygon([
    (-7.230000, 37.999444), (-7.383333, 35.966667),
    (-10.733333, 35.966667), (-9.000000, 38.000000),
]).buffer(0)

ZONES = {
    "SECTOR NORTE": SECTOR_NORTE,
    "SECTOR CENTRO": SECTOR_CENTRO,
    "SECTOR SUL": SECTOR_SUL,
}

FIR_POLYGON = unary_union(list(ZONES.values()))
FIR_MINX, FIR_MINY, FIR_MAXX, FIR_MAXY = FIR_POLYGON.bounds

# Elevação máxima aproximada por sector (ft) — para conversão AMSL→AGL
ZONE_ELEVATION = {
    "SECTOR NORTE": 1700,   # Serra da Estrela ~6500ft mas usamos máximo de terreno comum
    "SECTOR CENTRO": 900,
    "SECTOR SUL":    250,
}

# -------------------------------------------------
# CIDADES
# -------------------------------------------------

CITIES = {
    "Bragança":          (41.806, -6.756),
    "Viana do Castelo":  (41.693, -8.832),
    "Braga":             (41.545, -8.426),
    "Vila Real":         (41.300, -7.744),
    "Porto":             (41.149, -8.610),
    "Viseu":             (40.661, -7.909),
    "Aveiro":            (40.640, -8.653),
    "Guarda":            (40.537, -7.267),
    "Coimbra":           (40.203, -8.410),
    "Leiria":            (39.744, -8.807),
    "Castelo Branco":    (39.823, -7.493),
    "Santarém":          (39.236, -8.686),
    "Portalegre":        (39.292, -7.428),
    "Lisboa":            (38.722, -9.139),
    "Setúbal":           (38.524, -8.888),
    "Évora":             (38.571, -7.913),
    "Beja":              (38.015, -7.863),
    "Faro":              (37.019, -7.930),
}

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

# -------------------------------------------------
# NORMALIZE
# -------------------------------------------------

def normalize(text):
    text = text.upper()
    text = text.replace("–", "-").replace("\r\n", "\n").replace("\r", "\n")
    return text

# -------------------------------------------------
# VALIDADE
# -------------------------------------------------

def parse_validity(text):
    """Extrai período de validade e verifica se está ativo."""
    text = normalize(text)
    m = re.search(r"VALID\s+(\d{2})(\d{2})(\d{2})/(\d{2})(\d{2})(\d{2})", text)
    if not m:
        return None, None, False
    day_s, hh_s, mm_s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day_e, hh_e, mm_e = int(m.group(4)), int(m.group(5)), int(m.group(6))
    now = datetime.now(timezone.utc)
    try:
        start = now.replace(day=day_s, hour=hh_s, minute=mm_s, second=0, microsecond=0)
        end   = now.replace(day=day_e, hour=hh_e, minute=mm_e, second=0, microsecond=0)
        # Se end ficou antes de start, o GAMET cruza a fronteira do mês — avançar end 1 mês
        if end < start:
            # Incrementar mês manualmente (sem dependência de dateutil)
            month = end.month + 1
            year  = end.year + (1 if month > 12 else 0)
            month = 1 if month > 12 else month
            end = end.replace(year=year, month=month)
        active = start <= now <= end
        return start, end, active
    except Exception:
        return None, None, False

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

    # BTN N\d\d\d\d AND N\d\d\d\d  (latitude)
    for m in re.findall(r"BTN\s+N(\d{2})(\d{2})\s+AND\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat1 = int(m[0]) + int(m[1]) / 60
        lat2 = int(m[2]) + int(m[3]) / 60
        poly = _clean_poly(poly.intersection(box(FIR_MINX, min(lat1, lat2), FIR_MAXX, max(lat1, lat2))))

    # BTN W/E\d\d\d\d AND W/E\d\d\d\d  (longitude)
    for m in re.findall(r"BTN\s+([WE])(\d{2,3})(\d{2})\s+AND\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon1 = _lon(m[1], m[2], m[0])
        lon2 = _lon(m[4], m[5], m[3])
        poly = _clean_poly(poly.intersection(box(min(lon1, lon2), FIR_MINY, max(lon1, lon2), FIR_MAXY)))

    # N OF N\d\d\d\d
    for m in re.findall(r"N\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        poly = _clean_poly(poly.intersection(box(FIR_MINX, lat, FIR_MAXX, FIR_MAXY)))

    # S OF N\d\d\d\d
    for m in re.findall(r"S\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        poly = _clean_poly(poly.intersection(box(FIR_MINX, FIR_MINY, FIR_MAXX, lat)))

    # E OF W/E\d\d\d\d
    for m in re.findall(r"E\s+OF\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon = _lon(m[1], m[2], m[0])
        poly = _clean_poly(poly.intersection(box(lon, FIR_MINY, FIR_MAXX, FIR_MAXY)))

    # W OF W/E\d\d\d\d
    for m in re.findall(r"W\s+OF\s+([WE])(\d{2,3})(\d{2})", line):
        geo_found = True
        lon = _lon(m[1], m[2], m[0])
        poly = _clean_poly(poly.intersection(box(FIR_MINX, FIR_MINY, lon, FIR_MAXY)))

    return poly if geo_found else None

# -------------------------------------------------
# WIND PARSER — v16
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
        """True se a linha contém só nomes de estações (sem dígitos)."""
        return bool(re.match(r"^[A-Z][A-Z\s]+$", line)) and not re.search(r"\d", line)

    def _is_coord_line(line):
        return bool(re.search(r"N\d{4}\s+W\d{4,5}", line))

    def _is_level_line(line):
        return bool(re.match(r"(\d{4}FT\s+AGL|FL\d{3})", line))

    def flush_group(names, coords, lvl_lines):
        """Cria entradas de estação a partir de um grupo recolhido."""
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
    cur_names  = []
    cur_coords = []
    cur_levels = []

    for line in lines:
        if _is_station_name_line(line):
            # Novo grupo — flush anterior se existir
            if cur_names and cur_coords and cur_levels:
                stations.extend(flush_group(cur_names, cur_coords, cur_levels))
            cur_names  = line.split()
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
# PARSER — v16
# -------------------------------------------------

# Palavras-chave que NÃO devem ser confundidas com visibilidade ou altitude
_FL_PATTERN = re.compile(r"FL\d{2,3}")          # FL050, FL100, FL150 …
_HPA_PATTERN = re.compile(r"\d+\s*HPA")         # 986HPA, 1005HPA …

_TS_DISPLAY = {
    "ISOL_EMBD": "ISOL/EMBD",
}

def _ts_label(val):
    return _TS_DISPLAY.get(val, val)

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
    secn1 = re.sub(r"(\bVA\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(SIGMET\s+APPLICABLE)", r"\n\1", secn1)

    # Injetar quebras antes de qualificadores geográficos secundários na mesma linha
    # ex: "...010HFT AGL S OF N3845 ISOL..." → "...010HFT AGL\nS OF N3845 ISOL..."
    # Aplica-se a N OF, S OF, E OF, W OF, BTN quando precedidos de conteúdo meteorológico
    secn1 = re.sub(r"(\w)\s+(N\s+OF\s+N\d{4})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(S\s+OF\s+N\d{4})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(E\s+OF\s+[WE]\d{4,5})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(W\s+OF\s+[WE]\d{4,5})", r"\1\n\2", secn1)
    secn1 = re.sub(r"(\w)\s+(BTN\s+N\d{4})", r"\1\n\2", secn1)

    lines = [l.strip() for l in secn1.splitlines() if l.strip()]

    state = "IDLE"
    blocks = []
    current_polygon = FIR_POLYGON

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
        elif re.match(r"VA\b", line):
            new_state = "VA"
        elif re.match(r"SECN\s+I\b", line):
            state = "IDLE"
            current_polygon = FIR_POLYGON
            continue

        if new_state:
            state = new_state
            current_polygon = FIR_POLYGON  # reset geo ao mudar de campo
            # Remover a keyword da linha para processar só o conteúdo
            content = re.sub(
                r"^(SFC\s+VIS\s*:?|SIG\s+VIS\s*:?|VIS\s*:|SIG\s+CLD\s*:?|CLD\s*:|SIGWX\s*:?|TURB\s*:?|ICE\s*:?|MT\s+OBSC\s*:?|VA\s*:?)\s*",
                "", line
            ).strip()
        else:
            content = line

        if state == "IDLE":
            continue

        # ---- Contexto geográfico ----
        new_poly = extract_polygon(line)
        if new_poly is not None and not new_poly.is_empty:
            current_polygon = new_poly

        poly = current_polygon

        # ---- Qualificador local ----
        qualifier = ""
        if re.search(r"\bLCA\b", content):
            qualifier = "LCA"

        # ---- PARSE por estado ----

        if state == "VIS":
            vis_content = _FL_PATTERN.sub("", content)
            vis_content = _HPA_PATTERN.sub("", vis_content)

            # BLW/ABV: usar valor conservador (BLW X → X-1, ABV X → X+1)
            blw_m = re.search(r"\bBLW\s+(\d{3,4})M\b", vis_content)
            abv_m = re.search(r"\bABV\s+(\d{3,4})M\b", vis_content)
            if blw_m:
                val = int(blw_m.group(1)) - 1
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier))
            elif abv_m:
                val = int(abv_m.group(1)) + 1
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier))
            else:
                # Captura KM
                for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*KM\b", vis_content):
                    val = int(float(m.group(1)) * 1000)
                    blocks.append(MetBlock("VIS", poly, val, qualifier))

                # Intervalo: 2000-5000M → mínimo
                for m in re.finditer(r"\b(\d{3,4})-(\d{3,4})M\b", vis_content):
                    val = min(int(m.group(1)), int(m.group(2)))
                    if 100 <= val <= 9999:
                        blocks.append(MetBlock("VIS", poly, val, qualifier))

                # Valor simples
                for m in re.finditer(r"(?<!\d)(\d{3,4})M\b", vis_content):
                    pos = m.start()
                    if vis_content[max(0, pos - 5):pos].rstrip().endswith("-"):
                        continue
                    val = int(m.group(1))
                    if 100 <= val <= 9999:
                        blocks.append(MetBlock("VIS", poly, val, qualifier))

        elif state == "CLD":
            # Suporta "015-030/XXXHFT AGL", "015HFT AGL" e "035HFT AMSL"
            # Range HFT AGL
            for m in re.finditer(
                r"\b(\d{3})-(\d{3})(?:/[A-Z0-9]+)?HFT\s+AGL\b",
                content
            ):
                base_ft = int(m.group(1)) * 100
                blocks.append(MetBlock("BASE_AGL", poly, base_ft, qualifier))

            # Base única HFT AGL — excluir apenas se o dígito é precedido directamente por / ou -
            # ex: "004/020HFT" → skip (020 é topo do range)
            # ex: "TCU/CB 020HFT" → manter (/ pertence a TCU/CB, não ao número)
            for m in re.finditer(r"\b(\d{3})HFT\s+AGL\b", content):
                pos = m.start()
                # Verificar char imediatamente antes do número (ignorando espaços)
                pre = content[:pos].rstrip()
                if pre and pre[-1] in "-/":
                    continue
                base_ft = int(m.group(1)) * 100
                blocks.append(MetBlock("BASE_AGL", poly, base_ft, qualifier))

            # AMSL — converter para AGL usando elevação máxima do sector (conservador)
            for m in re.finditer(r"\b(\d{3})HFT\s+AMSL\b", content):
                pos = m.start()
                pre = content[:pos].rstrip()
                if pre and pre[-1] in "-/":
                    continue
                amsl_ft = int(m.group(1)) * 100
                blocks.append(MetBlock("BASE_AMSL", poly, amsl_ft, qualifier))

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
                blocks.append(MetBlock("TS", poly, ts_qualifier, qualifier))

        elif state == "TURB":
            layer = ""
            layer_m = re.search(r"(SFC/FL\d+|FL\d+/FL\d+|SFC/\d+FT|ABV\s+FL\d+)", content)
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
                                       layer + (f" {extra}" if extra else "")))

        elif state == "ICE":
            layer = ""
            layer_m = re.search(r"(ABV\s+FL\d+|FL\d+/FL\d+|SFC/FL\d+)", content)
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
                blocks.append(MetBlock("ICE", poly, severity, qualifier, layer + (f" {trend}" if trend else "")))

        elif state == "MT_OBSC":
            # Montanhas obscurecidas — sempre NO-GO para VFR
            # Só appenda quando a linha activa o estado (new_state presente)
            if new_state == "MT_OBSC":
                blocks.append(MetBlock("MT_OBSC", poly, "MT OBSC", qualifier))

        elif state == "VA":
            # Cinzas vulcânicas — sempre NO-GO
            if new_state == "VA":
                blocks.append(MetBlock("VA", poly, "VA", qualifier))

    # ---- Extração Secção II: FZLVL, QNH e vento ----
    fzlvl_values = [int(m) for m in re.findall(r"(\d{4,5})FT\s+AMSL", secn2)]
    fzlvl_min = min(fzlvl_values) if fzlvl_values else None

    qnh_m = re.search(r"MNM\s+QNH\s*:?\s*(\d{3,4})\s*HPA", secn2)
    qnh_min = int(qnh_m.group(1)) if qnh_m else None

    wind_data = parse_wind(secn2)

    return blocks, fzlvl_min, qnh_min, wind_data

# -------------------------------------------------
# BUILD
# -------------------------------------------------

def build_zone_data(blocks, threshold=0.15):
    zone_data = {z: [] for z in ZONES}

    for block in blocks:
        if block.polygon is None or block.polygon.is_empty:
            continue
        for zone, poly in ZONES.items():
            inter = poly.intersection(block.polygon)
            if inter.is_empty:
                continue
            coverage = inter.area / poly.area
            if coverage < threshold:
                continue
            if block.phenomenon == "BASE_AGL":
                zone_data[zone].append(("BASE", block.value, block.qualifier, block.layer))
            elif block.phenomenon == "BASE_AMSL":
                # Converter AMSL → AGL usando elevação máxima do sector (conservador)
                elev = ZONE_ELEVATION.get(zone, 0)
                agl_ft = max(0, block.value - elev)
                zone_data[zone].append(("BASE", agl_ft, block.qualifier, block.layer))
            else:
                zone_data[zone].append((block.phenomenon, block.value, block.qualifier, block.layer))

    return zone_data

def compute_dynamic_regions(blocks):
    """
    Constrói regiões de decisão dinâmica com base na geometria REAL de cada
    fenómeno do GAMET (não nos 3 sectores fixos).

    Método: junta as fronteiras de todos os polígonos activos + fronteira da
    FIR, usa polygonize() para particionar a FIR em células atómicas (as
    intersecções reais entre todos os fenómenos), calcula a decisão para cada
    célula com a mesma lógica decision(), e funde células com a mesma decisão.

    Devolve lista de tuplos (multipolygon, decision_level, reasons).
    """
    relevant = [b for b in blocks
                if b.polygon is not None and not b.polygon.is_empty
                and b.polygon.geom_type in ("Polygon", "MultiPolygon")
                and b.phenomenon in ("VIS", "BASE_AGL", "BASE_AMSL", "TS",
                                       "TURB", "ICE", "MT_OBSC", "VA")]

    if not relevant:
        dec, *_ = decision([])
        return [(FIR_POLYGON, dec, [])]

    # 1. Fronteiras de todos os polígonos relevantes + fronteira da FIR
    boundaries = [FIR_POLYGON.boundary]
    for b in relevant:
        boundaries.append(b.polygon.boundary)
    merged_lines = unary_union(boundaries)

    # 2. Particionar em células atómicas
    atomic_cells = [c for c in polygonize(merged_lines) if not c.is_empty and c.area > 1e-9]
    if not atomic_cells:
        dec, *_ = decision([])
        return [(FIR_POLYGON, dec, [])]

    # 3. Calcular decisão por célula (com base no ponto representativo)
    cell_results = []  # (cell, decision_level, reasons)
    for cell in atomic_cells:
        centroid = cell.representative_point()
        events = []
        for b in relevant:
            if not b.polygon.contains(centroid):
                continue
            if b.phenomenon == "BASE_AMSL":
                # Sem sector específico aqui — usar elevação média genérica
                agl_ft = max(0, b.value - 1000)
                events.append(("BASE", agl_ft, b.qualifier, b.layer))
            elif b.phenomenon == "BASE_AGL":
                events.append(("BASE", b.value, b.qualifier, b.layer))
            else:
                events.append((b.phenomenon, b.value, b.qualifier, b.layer))

        dec_level, *_rest, reasons = decision(events)
        cell_results.append((cell, dec_level, reasons))

    # 4. Fundir células com a mesma decisão
    from collections import defaultdict
    grouped = defaultdict(list)
    reasons_by_level = defaultdict(set)
    for cell, dec_level, reasons in cell_results:
        grouped[dec_level].append(cell)
        for r in reasons:
            reasons_by_level[dec_level].add(r)

    merged_regions = []
    for dec_level, cells in grouped.items():
        merged_poly = unary_union(cells)
        merged_regions.append((merged_poly, dec_level, sorted(reasons_by_level[dec_level])))

    return merged_regions

# -------------------------------------------------
# DECISION — v16
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

    return decision_level, vis, base, ts_vals, turb_vals, turb_layers, ice_vals, ice_layers, mt_obsc, va_vals, reasons

# -------------------------------------------------
# PDF EXPORT — v14
# -------------------------------------------------

def _pdf_briefing_page(pdf, results, gamet_text, validity_label):
    """Página 1 — Decisão VFR por sector."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4
    ax.axis("off")
    fig.patch.set_facecolor("white")

    colors = {"GO": "#2ecc71", "MARGINAL": "#e67e22", "NO-GO": "#e74c3c"}
    y = 0.97

    ax.text(0.5, y, "LPPC GAMET – Briefing VFR", ha="center", va="top",
            fontsize=16, fontweight="bold", transform=ax.transAxes)
    y -= 0.04
    if validity_label:
        ax.text(0.5, y, validity_label, ha="center", va="top",
                fontsize=9, color="#555", transform=ax.transAxes)
    y -= 0.04

    col_x = [0.05, 0.37, 0.69]
    for idx, z in enumerate(ZONES):
        dec, vis, base, ts, turb, turb_layers, ice, ice_layers, mt_obsc, va_vals, reasons = results[z]
        cx = col_x[idx]
        color = colors.get(dec, "#888")

        # Cabeçalho do sector — nome e decisão em linhas separadas
        ax.text(cx, y, z, va="top", fontsize=10, fontweight="bold",
                transform=ax.transAxes)
        ax.text(cx, y - 0.030, dec, va="top", fontsize=10, fontweight="bold",
                color=color, transform=ax.transAxes)

        dy = 0.038
        entries = [
            f"VIS:  {vis} m"        if vis  is not None else "VIS:  —",
            f"BASE: {base} ft AGL"  if base is not None else "BASE: —",
            f"TS:   {', '.join(_ts_label(v) for v in ts)}" if ts else "TS:   —",
        ]
        # TURB com camada
        if turb:
            turb_str = ", ".join(
                f"{v} ({turb_layers[idx]})" if idx < len(turb_layers) and turb_layers[idx] else v
                for idx, v in enumerate(turb)
            )
            entries.append(f"TURB: {turb_str}")
        else:
            entries.append("TURB: —")
        # ICE com camada
        if ice:
            ice_str = ", ".join(
                f"{v} ({ice_layers[idx]})" if idx < len(ice_layers) and ice_layers[idx] else v
                for idx, v in enumerate(ice)
            )
            entries.append(f"ICE:  {ice_str}")
        else:
            entries.append("ICE:  —")
        if va_vals:
            entries.append("VA:   CINZAS VULC.")
        if mt_obsc:
            entries.append("MTOBS: MONT. OBSC.")

        row_y = y - 0.068  # abaixo das 2 linhas do cabeçalho
        for entry in entries:
            ax.text(cx, row_y, entry, va="top", fontsize=8,
                    fontfamily="monospace", transform=ax.transAxes)
            row_y -= dy

        # Motivos
        if reasons:
            row_y -= 0.005
            ax.text(cx, row_y, "Motivos:", va="top", fontsize=7,
                    color="#555", transform=ax.transAxes)
            row_y -= dy * 0.8
            for r in reasons:
                ax.text(cx, row_y, f"  • {r}", va="top", fontsize=7,
                        color="#555", transform=ax.transAxes)
                row_y -= dy * 0.8

    # Rodapé com texto bruto
    y_raw = 0.38
    ax.plot([0.05, 0.95], [y_raw + 0.02, y_raw + 0.02],
            color="#ccc", linewidth=0.5, transform=ax.transAxes)
    ax.text(0.05, y_raw, "Texto GAMET original:", va="top", fontsize=7,
            fontweight="bold", color="#555", transform=ax.transAxes)
    raw_lines = [gamet_text[i:i+100] for i in range(0, min(len(gamet_text), 600), 100)]
    for rl in raw_lines:
        y_raw -= 0.03
        ax.text(0.05, y_raw, rl, va="top", fontsize=6,
                fontfamily="monospace", color="#777", transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _pdf_map_page(pdf, results):
    """Página 2 — Mapa por sector."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    colors = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    for z, poly in ZONES.items():
        dec = results[z][0]
        geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        for g in geoms:
            x, y = g.exterior.xy
            ax.fill(x, y, alpha=0.35, color=colors[dec])
            ax.plot(x, y, color=colors[dec], linewidth=1)

    for name, (lat, lon) in CITIES.items():
        ax.plot(lon, lat, "ko", markersize=3)
        ax.text(lon + 0.05, lat, name, fontsize=7)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_title("Mapa VFR – FIR LPPC", fontsize=12, fontweight="bold")
    ax.legend(handles=[
        Patch(facecolor="green",  alpha=0.35, label="GO"),
        Patch(facecolor="orange", alpha=0.35, label="MARGINAL"),
        Patch(facecolor="red",    alpha=0.35, label="NO-GO"),
        Line2D([0],[0], marker="o", color="black", linestyle="None", label="Cidade"),
    ])

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


def generate_pdf(results, gamet_text, fzlvl_min, qnh_min, validity_label) -> bytes:
    """Gera um PDF completo (briefing + mapa + secção II) e devolve os bytes."""
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_briefing_page(pdf, results, gamet_text, validity_label)
        _pdf_map_page(pdf, results)
        if fzlvl_min or qnh_min:
            _pdf_secn2_page(pdf, fzlvl_min, qnh_min)
        # Metadados
        d = pdf.infodict()
        d["Title"]   = "LPPC GAMET Briefing VFR"
        d["Author"]  = "GAMET Decoder v16.0"
        d["Subject"] = "Briefing meteorológico VFR – FIR LPPC"
    buf.seek(0)
    return buf.getvalue()


# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------

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
            st.success(label + " ✅ Em vigor")
        else:
            st.warning(label + " ⚠️ FORA DO PERÍODO DE VALIDADE — dados podem estar desatualizados")

    blocks, fzlvl_min, qnh_min, wind_data = parse_gamet(gamet_text)
    zone_data  = build_zone_data(blocks)
    results    = {z: decision(zone_data[z]) for z in ZONES}

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

    # ---- Briefing ----
    st.subheader("📋 Briefing")
    cols = st.columns(3)

    for i, z in enumerate(ZONES):
        dec, vis, base, ts, turb, turb_layers, ice, ice_layers, mt_obsc, va_vals, reasons = results[z]

        with cols[i]:
            st.markdown(f"### {z}")

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
                    f"{v} ({turb_layers[idx]})" if idx < len(turb_layers) and turb_layers[idx] else v
                    for idx, v in enumerate(turb)
                )
                st.write(f"🌪 TURB: {turb_str}")
            else:
                st.write("🌪 TURB: —")

            if ice:
                ice_str = ", ".join(
                    f"{v} ({ice_layers[idx]})" if idx < len(ice_layers) and ice_layers[idx] else v
                    for idx, v in enumerate(ice)
                )
                st.write(f"❄️ ICE: {ice_str}")
            else:
                st.write("❄️ ICE: —")

            st.write("🌋 VA: ⚠️ CINZAS VULCÂNICAS" if va_vals else "🌋 VA: —")
            st.write("⛰️ MT OBSC: ⚠️ MONTANHAS OBSCURECIDAS" if mt_obsc else "⛰️ MT OBSC: —")

            if reasons:
                with st.expander("ℹ️ Motivos da decisão", expanded=True):
                    for r in reasons:
                        st.write(f"• {r}")

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
- ☁️ BASE – Base das nuvens convectivas significativas em ft AGL (acima do solo)
- ⛈️ TS – Trovoadas: ISOL / OCNL / FRQ / EMBD
- 🌪 TURB – Turbulência: MOD (moderada) / SEV (severa)
- ❄️ ICE – Gelo em voo: MOD (moderado) / SEV (severo)

**Regras de decisão TS:**
- ISOL → MARGINAL
- OCNL / GEN / ISOL/EMBD / EMBD / FRQ → NO-GO

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
- Indica a que altitude as nuvens convectivas (trovoadas ou cumulus) começam.
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
        pdf_bytes = generate_pdf(results, gamet_text, fzlvl_min, qnh_min, validity_label)
    fname = f"briefing_lppc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%MZ')}.pdf"
    st.download_button(
        label="⬇️ Descarregar Briefing PDF",
        data=pdf_bytes,
        file_name=fname,
        mime="application/pdf",
    )

    # ---- Mapa Interativo (Folium) ----
    st.subheader("🗺️ Mapa Interativo")
    fcolors = {"GO": "#2ecc71", "MARGINAL": "#e67e22", "NO-GO": "#e74c3c"}

    show_dynamic = st.toggle(
        "🌐 Mostrar zonas dinâmicas (geometria real do GAMET)",
        value=False,
        help="Em vez dos 3 sectores fixos, desenha as regiões de decisão "
             "exactamente como o GAMET as define — as fronteiras seguem os "
             "qualificadores geográficos (N OF, S OF, BTN...) de cada fenómeno."
    )

    if _FOLIUM_OK:
        fmap = folium.Map(location=[39.5, -8.5], zoom_start=6, tiles="CartoDB positron")

        if show_dynamic:
            regions = compute_dynamic_regions(blocks)
            for poly, dec, reasons in regions:
                color = fcolors.get(dec, "#888")
                geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
                tooltip = dec + (f" — {'; '.join(reasons)}" if reasons else "")
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
        else:
            for z, poly in ZONES.items():
                dec = results[z][0]
                color = fcolors.get(dec, "#888")
                geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
                for g in geoms:
                    coords = [[lat, lon] for lon, lat in zip(*g.exterior.xy)]
                    folium.Polygon(
                        locations=coords,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.3,
                        weight=2,
                        tooltip=f"{z}: {dec}",
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
        st.components.v1.html(fmap._repr_html_(), height=500)
    else:
        st.warning("Folium não instalado — mapa estático disponível no PDF.")

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
                    st.rerun()
