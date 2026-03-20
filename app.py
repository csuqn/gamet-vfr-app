import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union
from dataclasses import dataclass

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Motor Cartográfico v10.8 FINAL")

gamet_text = st.text_area("Cole aqui o texto completo do GAMET (LPPC)", height=300)

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

ZONE_ELEVATION = {
    "SECTOR NORTE": 1700,
    "SECTOR CENTRO": 900,
    "SECTOR SUL": 250,
}

# -------------------------------------------------
# CIDADES
# -------------------------------------------------

CITIES = {
    "Bragança": (41.806, -6.756),
    "Viana do Castelo": (41.693, -8.832),
    "Braga": (41.545, -8.426),
    "Vila Real": (41.300, -7.744),
    "Porto": (41.149, -8.610),
    "Viseu": (40.661, -7.909),
    "Aveiro": (40.640, -8.653),
    "Guarda": (40.537, -7.267),
    "Coimbra": (40.203, -8.410),
    "Leiria": (39.744, -8.807),
    "Castelo Branco": (39.823, -7.493),
    "Santarém": (39.236, -8.686),
    "Portalegre": (39.292, -7.428),
    "Lisboa": (38.722, -9.139),
    "Setúbal": (38.524, -8.888),
    "Évora": (38.571, -7.913),
    "Beja": (38.015, -7.863),
    "Faro": (37.019, -7.930),
}

# -------------------------------------------------
# DATA MODEL
# -------------------------------------------------

@dataclass
class MetBlock:
    phenomenon: str
    polygon: object
    value: object

# -------------------------------------------------
# NORMALIZE
# -------------------------------------------------

def normalize(text):
    text = text.upper()
    text = text.replace("–", "-")
    return text

# -------------------------------------------------
# GEO
# -------------------------------------------------

def extract_polygon(line):
    poly = FIR_POLYGON
    geo_found = False

    for m in re.findall(r"BTN N(\d{2})(\d{2}) AND N(\d{2})(\d{2})", line):
        geo_found = True
        lat1 = int(m[0]) + int(m[1])/60
        lat2 = int(m[2]) + int(m[3])/60
        poly = poly.intersection(box(FIR_MINX, min(lat1, lat2), FIR_MAXX, max(lat1, lat2)))

    for m in re.findall(r"S OF N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1])/60
        poly = poly.intersection(box(FIR_MINX, FIR_MINY, FIR_MAXX, lat))

    for m in re.findall(r"N OF N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1])/60
        poly = poly.intersection(box(FIR_MINX, lat, FIR_MAXX, FIR_MAXY))

    for m in re.findall(r"W OF W(\d{2})(\d{2})", line):
        geo_found = True
        lon = -(int(m[0]) + int(m[1])/60)
        poly = poly.intersection(box(FIR_MINX, FIR_MINY, lon, FIR_MAXY))

    for m in re.findall(r"E OF W(\d{2})(\d{2})", line):
        geo_found = True
        lon = -(int(m[0]) + int(m[1])/60)
        poly = poly.intersection(box(lon, FIR_MINY, FIR_MAXX, FIR_MAXY))

    if not geo_found:
        return FIR_POLYGON

    return poly if not poly.is_empty else None

# -------------------------------------------------
# FSM PARSER
# -------------------------------------------------

def parse_gamet(text):

    text = normalize(text)
    raw_lines = text.splitlines()

    if len(raw_lines) <= 1:
        lines = re.split(
            r"(?=SFC VIS|VIS:|SIG CLD|CLD:|SIGWX|TURB|ICE|SECN)",
            text
        )
    else:
        lines = [l.strip() for l in raw_lines if l.strip()]

    state = "IDLE"
    blocks = []

for line in lines:

    line = line.strip()
    if not line:
        continue

    if line.startswith("SECN"):
        state = "IDLE"
        continue

    if line.startswith("SFC VIS") or line.startswith("VIS:"):
        state = "VIS"
        line = line.split(":",1)[1] if ":" in line else ""
    elif line.startswith("SIG CLD") or line.startswith("CLD:"):
        state = "CLD"
        line = line.split(":",1)[1] if ":" in line else ""
    elif line.startswith("SIGWX"):
        state = "SIGWX"
        line = line.split(":",1)[1] if ":" in line else ""
    elif line.startswith("TURB"):
        state = "TURB"
        line = line.split(":",1)[1] if ":" in line else ""
    elif line.startswith("ICE"):
        state = "ICE"
        line = line.split(":",1)[1] if ":" in line else ""

    if not line or state == "IDLE":
        continue

    # ✅ AQUI entra o patch correto
    new_poly = extract_polygon(line)

    if new_poly:
        current_polygon = new_poly

    poly = current_polygon

        if state == "VIS":
            for m in re.finditer(r"\b(\d{3,4})\s*-\s*(\d{3,4})M\b", line):
                blocks.append(MetBlock("VIS", poly, int(m.group(1))))
            for m in re.finditer(r"\b(\d{3,4})M\b", line):
                if not re.search(rf"{m.group(1)}\s*-\s*\d{{3,4}}M", line):
                    blocks.append(MetBlock("VIS", poly, int(m.group(1))))
            if re.search(r"\b9999\b", line):
                blocks.append(MetBlock("VIS", poly, 9999))
            if "P6KM" in line:
                blocks.append(MetBlock("VIS", poly, 6000))

        elif state == "CLD":

            for m in re.finditer(r"\b(\d{3})\s*-\s*(\d{3})(?:/\d{3})?HFT AGL\b", line):
                blocks.append(MetBlock("BASE_AGL", poly, int(m.group(1))*100))

            for m in re.finditer(r"\b(\d{3})HFT AGL\b", line):
                if not re.search(rf"{m.group(1)}\s*-\s*\d{{3}}(?:/\d{{3}})?HFT AGL", line):
                    blocks.append(MetBlock("BASE_AGL", poly, int(m.group(1))*100))

            for m in re.finditer(r"\b(\d{3})\s*-\s*(\d{3})(?:/\d{3})?HFT AMSL\b", line):
                blocks.append(MetBlock("BASE_AMSL", poly, int(m.group(1))*100))

            for m in re.finditer(r"\b(\d{3})HFT AMSL\b", line):
                if not re.search(rf"{m.group(1)}\s*-\s*\d{{3}}(?:/\d{{3}})?HFT AMSL", line):
                    blocks.append(MetBlock("BASE_AMSL", poly, int(m.group(1))*100))

        elif state == "SIGWX":
            if "FRQ TS" in line:
                blocks.append(MetBlock("TS", poly, "FRQ"))
            elif "OCNL TS" in line:
                blocks.append(MetBlock("TS", poly, "OCNL"))
            elif "ISOL TS" in line:
                blocks.append(MetBlock("TS", poly, "ISOL"))
            elif re.search(r"\bTS\b", line):
                blocks.append(MetBlock("TS", poly, "GEN"))

        elif state == "TURB":
            if "SEV" in line:
                blocks.append(MetBlock("TURB", poly, "SEV"))
            elif "MOD" in line:
                blocks.append(MetBlock("TURB", poly, "MOD"))

        elif state == "ICE":
            if "SEV" in line:
                blocks.append(MetBlock("ICE", poly, "SEV"))
            elif "MOD" in line:
                blocks.append(MetBlock("ICE", poly, "MOD"))

    return blocks

# -------------------------------------------------
# BUILD + DECISION
# -------------------------------------------------

def build_zone_data(blocks, area_threshold=0.15):
    """
    Distribui eventos meteorológicos por sector com base na percentagem
    de área afetada (evita contaminação de sectores inteiros).
    
    area_threshold: fração mínima de área (ex: 0.15 = 15%)
    """

    zone_data = {z: [] for z in ZONES}

    for block in blocks:

        if block.polygon is None or block.polygon.is_empty:
            continue

        for zone_name, zone_poly in ZONES.items():

            # Interseção real
            intersection = zone_poly.intersection(block.polygon)

            if intersection.is_empty:
                continue

            # Percentagem de área afetada
            try:
                coverage = intersection.area / zone_poly.area
            except ZeroDivisionError:
                coverage = 0

            # Filtro por threshold
            if coverage < area_threshold:
                continue

            # --- Aplicação do fenómeno ---

            if block.phenomenon == "BASE_AMSL":

                agl = block.value - ZONE_ELEVATION[zone_name]

                # Segurança: evitar valores negativos irreais
                if agl <= 0:
                    agl = 0

                zone_data[zone_name].append(("BASE", agl))

            elif block.phenomenon == "BASE_AGL":

                zone_data[zone_name].append(("BASE", block.value))

            else:
                zone_data[zone_name].append((block.phenomenon, block.value))

    return zone_data

def decision(events):

    vis = min([v for t,v in events if t=="VIS"], default=None)
    base = min([v for t,v in events if t=="BASE"], default=None)
    ts = [v for t,v in events if t=="TS"]
    turb = [v for t,v in events if t=="TURB"]
    ice = [v for t,v in events if t=="ICE"]

    if vis is not None and vis < 1500:
        return "NO-GO", vis, base, ts, turb, ice
    if base is not None and base < 300:
        return "NO-GO", vis, base, ts, turb, ice
    if vis is not None and vis < 3000:
        return "MARGINAL", vis, base, ts, turb, ice
    if base is not None and base < 500:
        return "MARGINAL", vis, base, ts, turb, ice

    return "GO", vis, base, ts, turb, ice

# -------------------------------------------------
# EXECUTION
# -------------------------------------------------

if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    blocks = parse_gamet(gamet_text)
    zone_data = build_zone_data(blocks)
    results = {z: decision(zone_data[z]) for z in ZONES}

    st.subheader("📋 Briefing")
    cols = st.columns(3)

    for i,z in enumerate(ZONES):

        dec, vis, base, ts, turb, ice = results[z]

        with cols[i]:

            st.markdown(f"### {z}")

            if dec=="NO-GO":
                st.error("🔴 NO-GO")
            elif dec=="MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.write(f"👁️ VIS: {vis} m" if vis is not None else "👁️ VIS: —")
            st.write(f"☁️ BASE: {base} ft AGL" if base is not None else "☁️ BASE: —")
            st.write(f"⛈️ TS: {', '.join(ts)}" if ts else "⛈️ TS: —")
            st.write(f"🌪 TURB: {', '.join(turb)}" if turb else "🌪 TURB: —")
            st.write(f"❄ ICE: {', '.join(ice)}" if ice else "❄ ICE: —")

    st.subheader("🌍 Mapa")

    fig, ax = plt.subplots(figsize=(7, 10))
    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    for zone_name, poly in ZONES.items():
        decision_value = results[zone_name][0]

        if isinstance(poly, MultiPolygon):
            geoms = poly.geoms
        else:
            geoms = [poly]

        for g in geoms:
            x, y = g.exterior.xy
            ax.fill(x, y, alpha=0.25, color=color_map[decision_value])
            ax.plot(x, y, linewidth=1)

    for name, (lat, lon) in CITIES.items():
        ax.plot(lon, lat, "ko", markersize=4)
        ax.text(lon + 0.05, lat, name, fontsize=8)

    ax.set_xlim(FIR_MINX - 0.3, FIR_MAXX + 0.3)
    ax.set_ylim(FIR_MINY - 0.3, FIR_MAXY + 0.3)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linestyle="--", alpha=0.4)

    ax.legend(handles=[
        Patch(facecolor="green", alpha=0.25, label="GO"),
        Patch(facecolor="orange", alpha=0.25, label="MARGINAL"),
        Patch(facecolor="red", alpha=0.25, label="NO-GO"),
        Line2D([0], [0], marker='o', color='black',
               linestyle='None', label='Cidade')
    ])

    st.pyplot(fig)
