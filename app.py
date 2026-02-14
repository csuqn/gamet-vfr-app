import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from shapely.geometry import box

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Motor Cartográfico v4.8")

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=260
)

# -------------------------------------------------
# FIR BOUNDING BOX
# -------------------------------------------------
LAT_MIN, LAT_MAX = 36.5, 42.5
LON_MIN, LON_MAX = -9.5, -6.0
FIR_POLYGON = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

# -------------------------------------------------
# ZONAS
# -------------------------------------------------
ZONES = {
    "NORTE": box(LON_MIN, 39.5, LON_MAX, 42.5),
    "CENTRO": box(LON_MIN, 38.5, LON_MAX, 39.5),
    "SUL": box(LON_MIN, 36.5, LON_MAX, 38.5),
}

# -------------------------------------------------
# NORMALIZAÇÃO
# -------------------------------------------------
def normalize_text(text):
    text = text.upper()
    text = text.replace("0F", "OF")
    text = text.replace("O F", "OF")
    text = re.sub(r"\s+", " ", text)
    return text

# -------------------------------------------------
# SPLIT POR FENÓMENO
# -------------------------------------------------
def split_into_sections(text):
    pattern = r"(SFC VIS:|VIS:|SIGWX:|SIG CLD:|CLD:|TURB:|ICE:|MT OBSC:)"
    parts = re.split(pattern, text)
    sections = []

    for i in range(1, len(parts), 2):
        marker = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((marker + content).strip())

    return sections

# -------------------------------------------------
# SPLIT GEOGRÁFICO
# -------------------------------------------------
def split_subblocks(section):
    geo_pattern = r"(N OF|S OF|E OF|W OF|BTW)"
    matches = list(re.finditer(geo_pattern, section))

    if not matches:
        return [section]

    subblocks = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        subblocks.append(section[start:end].strip())

    return subblocks

# -------------------------------------------------
# POLÍGONO CONDIÇÃO
# -------------------------------------------------
def build_condition_polygon(text_block):

    condition_poly = FIR_POLYGON

    for match in re.findall(r"N OF N(\d{2})(\d{2})", text_block):
        lat = int(match[0]) + int(match[1]) / 60
        poly = box(LON_MIN, lat, LON_MAX, LAT_MAX)
        condition_poly = condition_poly.intersection(poly)

    for match in re.findall(r"S OF N(\d{2})(\d{2})", text_block):
        lat = int(match[0]) + int(match[1]) / 60
        poly = box(LON_MIN, LAT_MIN, LON_MAX, lat)
        condition_poly = condition_poly.intersection(poly)

    for match in re.findall(r"E OF W(\d{2})(\d{2})", text_block):
        lon = -(int(match[0]) + int(match[1]) / 60)
        poly = box(lon, LAT_MIN, LON_MAX, LAT_MAX)
        condition_poly = condition_poly.intersection(poly)

    for match in re.findall(r"W OF W(\d{2})(\d{2})", text_block):
        lon = -(int(match[0]) + int(match[1]) / 60)
        poly = box(LON_MIN, LAT_MIN, lon, LAT_MAX)
        condition_poly = condition_poly.intersection(poly)

    if condition_poly.is_empty:
        condition_poly = FIR_POLYGON

    return condition_poly

# -------------------------------------------------
# PARSER
# -------------------------------------------------
def parse_gamet(text):

    text = normalize_text(text)
    sections = split_into_sections(text)
    zone_data = {z: [] for z in ZONES}

    for section in sections:

        subblocks = split_subblocks(section)

        for block in subblocks:

            condition_poly = build_condition_polygon(block)

            for zone_name, zone_poly in ZONES.items():

                if not zone_poly.intersects(condition_poly):
                    continue

                # ---------------- VIS ----------------
                if "ABV" not in block:
                    for low, _ in re.findall(r"(\d{4})-(\d{4})M", block):
                        zone_data[zone_name].append(("VIS", int(low)))

                    for val in re.findall(r"\b(\d{4})M\b", block):
                        zone_data[zone_name].append(("VIS", int(val)))

                # ---------------- BASE ----------------
                if section.startswith("CLD:") or section.startswith("SIG CLD:"):
                    for base_min, _ in re.findall(r"(\d{3})-(\d{3})/?.*?HFT", block):
                        zone_data[zone_name].append(("BASE", int(base_min) * 100))

                # ---------------- TS ----------------
                if re.search(r"\bTS\b", block):
                    zone_data[zone_name].append(("TS", 1))

                # ---------------- TURB ----------------
                if "TURB:" in section:
                    if "SEV" in block:
                        zone_data[zone_name].append(("TURB", "SEV"))
                    elif "MOD" in block:
                        zone_data[zone_name].append(("TURB", "MOD"))

    return zone_data

# -------------------------------------------------
# DECISÃO
# -------------------------------------------------
def decision_for_zone(events):

    vis = min([v for t, v in events if t == "VIS"], default=None)
    base = min([v for t, v in events if t == "BASE"], default=None)
    ts = any(t == "TS" for t, _ in events)
    turb_sev = any(t == "TURB" and v == "SEV" for t, v in events)
    turb_mod = any(t == "TURB" and v == "MOD" for t, v in events)

    if vis is not None and vis < 3000:
        return "NO-GO", vis, base, ts, turb_sev, turb_mod

    if base is not None and base < 500:
        return "NO-GO", vis, base, ts, turb_sev, turb_mod

    score = 0
    if vis and 3000 <= vis < 5000: score += 30
    if base and 500 <= base < 1500: score += 40
    if ts: score += 50
    if turb_sev: score += 45
    elif turb_mod: score += 35   # Ajustado

    if score >= 140:
        decision = "NO-GO"
    elif score >= 70:
        decision = "MARGINAL"
    else:
        decision = "GO"

    return decision, vis, base, ts, turb_sev, turb_mod

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    zone_data = parse_gamet(gamet_text)
    results = {z: decision_for_zone(zone_data[z]) for z in ZONES}

    st.subheader("📋 Briefing Detalhado")

    with st.expander("ℹ️ Legenda"):
        st.markdown("""
👁️ **Visibilidade mínima**  
☁️ **Base de nuvens (ft AGL)**  
⛈️ **Trovoadas (TS)**  
🌬️ **Turbulência moderada**  
🌪️ **Turbulência severa**
""")

    cols = st.columns(3)

    for i, z in enumerate(ZONES):
        decision, vis, base, ts, turb_sev, turb_mod = results[z]

        with cols[i]:
            st.markdown(f"### {z}")

            if decision == "NO-GO":
                st.error("🔴 NO-GO")
            elif decision == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.write(f"👁️ {vis} m" if vis else "👁️ —")
            st.write(f"☁️ {base} ft" if base else "☁️ —")
            st.write(f"⛈️ {'Sim' if ts else 'Não'}")

            if turb_sev:
                st.write("🌪️ Severa")
            elif turb_mod:
                st.write("🌬️ Moderada")
            else:
                st.write("🌬️ Não significativa")

    # Mapa
    st.divider()
    st.subheader("🗺️ Mapa VFR")

    fig, ax = plt.subplots(figsize=(6, 8.5))

    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}
    zone_y = {"NORTE": (9,14), "CENTRO": (4,9), "SUL": (-4.5,4)}

    for z, (y0, y1) in zone_y.items():
        ax.axhspan(y0, y1, color=color_map[results[z][0]], alpha=0.25)

    cities = {
        "Bragança": (0.8,13.5),
        "Viana do Castelo": (0.2,12.6),
        "Braga": (0.4,11.8),
        "Vila Real": (0.6,11.0),
        "Porto": (0.3,10.5),
        "Viseu": (0.6,8.6),
        "Aveiro": (0.3,8.0),
        "Guarda": (0.8,7.4),
        "Coimbra": (0.5,6.6),
        "Leiria": (0.3,5.6),
        "Castelo Branco": (0.8,5.9),
        "Santarém": (0.4,3.0),
        "Portalegre": (0.8,3.0),
        "Lisboa": (0.3,2.0),
        "Setúbal": (0.3,1.2),
        "Évora": (0.6,0.2),
        "Beja": (0.7,-1.0),
        "Faro": (0.7,-2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=4)
        ax.text(x + 0.02, y, name, fontsize=8, va="center")

    ax.set_xlim(0,1)
    ax.set_ylim(-4.5,14)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Decisão VFR por Zona")

    ax.legend(handles=[
        Patch(facecolor="green",alpha=0.25,label="GO"),
        Patch(facecolor="orange",alpha=0.25,label="MARGINAL"),
        Patch(facecolor="red",alpha=0.25,label="NO-GO"),
        Line2D([0],[0],marker='o',color='black',linestyle='None',label='Cidade')
    ])

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.pyplot(fig)

    st.caption("Motor cartográfico com interseção geométrica real.")



