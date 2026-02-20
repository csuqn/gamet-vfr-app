import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Motor Cartográfico v4.51")

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=260
)

# -------------------------------------------------
# LIMITES ORIGINAIS (RESTaurados)
# -------------------------------------------------
LAT_MIN, LAT_MAX = 36.5, 42.5
LON_MIN, LON_MAX = -9.5, -6.0

# -------------------------------------------------
# SECTORES LOWER OFICIAIS (AIP ENR 2.1)
# -------------------------------------------------

SECTOR_NORTE_LOWER = Polygon([
    (-8.83750, 41.88556),
    (-6.81833, 40.39944),
    (-8.01667, 39.38333),
    (-10.00000, 38.90000),
    (-9.78472, 39.34861),
    (-9.44250, 40.19972),
    (-9.36806, 40.38222),
    (-9.25139, 40.64889),
    (-9.18639, 40.82778),
])

SECTOR_CENTRO_LOWER = Polygon([
    (-6.81833, 40.39944),
    (-7.20639, 37.99917),
    (-9.00000, 38.00000),
    (-9.20000, 38.00000),
    (-9.46667, 38.00000),
    (-10.00000, 38.00000),
    (-10.00000, 38.90000),
    (-8.01667, 39.38333),
])

SECTOR_SUL_LOWER = Polygon([
    (-7.20639, 37.99917),
    (-7.38833, 37.12500),
    (-7.38639, 36.67111),
    (-7.38333, 35.96667),
    (-10.73333, 35.96667),
    (-9.46667, 38.00000),
    (-9.20000, 38.00000),
    (-9.00000, 38.00000),
])

ZONES = {
    "SECTOR NORTE": SECTOR_NORTE_LOWER,
    "SECTOR CENTRO": SECTOR_CENTRO_LOWER,
    "SECTOR SUL": SECTOR_SUL_LOWER,
}

# União real dos sectores = FIR operacional
FIR_POLYGON = unary_union(ZONES.values())

ZONE_ELEVATION = {
    "SECTOR NORTE": 1700,
    "SECTOR CENTRO": 900,
    "SECTOR SUL": 250,
}

# -------------------------------------------------
# NORMALIZAÇÃO (INALTERADO)
# -------------------------------------------------
def normalize_text(text):
    text = text.upper()
    text = text.replace("0F", "OF")
    text = text.replace("O F", "OF")
    text = re.sub(r"\s+", " ", text)
    return text

# -------------------------------------------------
# SPLIT PRINCIPAL (INALTERADO)
# -------------------------------------------------
def split_into_sections(text):
    pattern = r"(SFC VIS:|VIS:|SIGWX:|SIG CLD:|CLD:|TURB:|ICE:|MT OBSC:|MTW:)"
    parts = re.split(pattern, text)
    sections = []

    for i in range(1, len(parts), 2):
        marker = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((marker + content).strip())

    return sections

# -------------------------------------------------
# INTERSECÇÃO GEOGRÁFICA (BASE REAL FIR)
# -------------------------------------------------
def extract_condition_polygon(text):

    condition_poly = FIR_POLYGON
    geo_found = False

    for match in re.findall(r"N OF N(\d{2})(\d{2})", text):
        geo_found = True
        lat = int(match[0]) + int(match[1]) / 60
        condition_poly = condition_poly.intersection(
            box(LON_MIN, lat, LON_MAX, LAT_MAX)
        )

    for match in re.findall(r"S OF N(\d{2})(\d{2})", text):
        geo_found = True
        lat = int(match[0]) + int(match[1]) / 60
        condition_poly = condition_poly.intersection(
            box(LON_MIN, LAT_MIN, LON_MAX, lat)
        )

    for match in re.findall(r"E OF W(\d{2})(\d{2})", text):
        geo_found = True
        lon = -(int(match[0]) + int(match[1]) / 60)
        condition_poly = condition_poly.intersection(
            box(lon, LAT_MIN, LON_MAX, LAT_MAX)
        )

    for match in re.findall(r"W OF W(\d{2})(\d{2})", text):
        geo_found = True
        lon = -(int(match[0]) + int(match[1]) / 60)
        condition_poly = condition_poly.intersection(
            box(LON_MIN, LAT_MIN, lon, LAT_MAX)
        )

    if not geo_found:
        return FIR_POLYGON

    return condition_poly

# -------------------------------------------------
# PARSER (EXATAMENTE v4.41)
# -------------------------------------------------
def parse_gamet(text):

    text = normalize_text(text)
    sections = split_into_sections(text)
    zone_data = {z: [] for z in ZONES}

    for section in sections:

        # VIS
        if section.startswith("VIS:") or section.startswith("SFC VIS:"):

            section_poly = extract_condition_polygon(section)

            for zone_name, zone_poly in ZONES.items():
                if not zone_poly.intersects(section_poly):
                    continue

                ranges = re.findall(r"(\d{4})-(\d{4})M", section)
                singles = re.findall(r"\b(\d{4})M\b", section)

                used = set()
                for low, _ in ranges:
                    used.add(low)
                    zone_data[zone_name].append(("VIS", int(low)))

                for val in singles:
                    if val not in used:
                        zone_data[zone_name].append(("VIS", int(val)))

        # CLD
        if section.startswith("CLD:") or section.startswith("SIG CLD:"):

            cld_body = section.split(":", 1)[1]
            blocks = re.split(r"\s(?=\d{2}/\d{2})", cld_body)

            for block in blocks:

                block_poly = extract_condition_polygon(block)

                for zone_name, zone_poly in ZONES.items():
                    if not zone_poly.intersects(block_poly):
                        continue

                    for match in re.findall(r"\b(\d{3})-\d{3}(?:/\d{3})?HFT AGL", block):
                        zone_data[zone_name].append(("BASE", int(match) * 100))

                    for match in re.findall(r"\b(\d{3})-\d{3}(?:/\d{3})?HFT AMSL", block):
                        base_amsl = int(match) * 100
                        agl_est = base_amsl - ZONE_ELEVATION[zone_name]
                        if agl_est > 0:
                            zone_data[zone_name].append(("BASE", agl_est))

        # TURB
        if section.startswith("TURB:"):

            section_poly = extract_condition_polygon(section)

            for zone_name, zone_poly in ZONES.items():
                if not zone_poly.intersects(section_poly):
                    continue

                if "SEV" in section:
                    zone_data[zone_name].append(("TURB", "SEV"))
                elif "MOD" in section:
                    zone_data[zone_name].append(("TURB", "MOD"))

        # TS
        if re.search(r"\bISOL TS\b", section):
            section_poly = extract_condition_polygon(section)
            for zone_name, zone_poly in ZONES.items():
                if zone_poly.intersects(section_poly):
                    zone_data[zone_name].append(("TS", "ISOL"))

        elif re.search(r"\bOCNL TS\b", section):
            section_poly = extract_condition_polygon(section)
            for zone_name, zone_poly in ZONES.items():
                if zone_poly.intersects(section_poly):
                    zone_data[zone_name].append(("TS", "OCNL"))

        elif re.search(r"\bFRQ TS\b", section):
            section_poly = extract_condition_polygon(section)
            for zone_name, zone_poly in ZONES.items():
                if zone_poly.intersects(section_poly):
                    zone_data[zone_name].append(("TS", "FRQ"))

        elif re.search(r"(^|\s)TS(\s|$)", section):
            section_poly = extract_condition_polygon(section)
            for zone_name, zone_poly in ZONES.items():
                if zone_poly.intersects(section_poly):
                    zone_data[zone_name].append(("TS", "GEN"))

    return zone_data

# -------------------------------------------------
# DECISÃO (INALTERADA)
# -------------------------------------------------
def decision_for_zone(events):

    vis = min([v for t, v in events if t == "VIS"], default=None)
    base = min([v for t, v in events if t == "BASE"], default=None)

    ts_flag = any(t == "TS" for t, _ in events)
    turb_sev = any(t == "TURB" and v == "SEV" for t, v in events)
    turb_mod = any(t == "TURB" and v == "MOD" for t, v in events)

    if vis is not None:
        if vis < 1500:
            return "NO-GO", vis, base, ts_flag, turb_sev, turb_mod
        elif vis < 3000:
            return "MARGINAL", vis, base, ts_flag, turb_sev, turb_mod

    if base is not None:
        if base < 300:
            return "NO-GO", vis, base, ts_flag, turb_sev, turb_mod
        elif base < 500:
            return "MARGINAL", vis, base, ts_flag, turb_sev, turb_mod

    score = 0
    if turb_sev:
        score += 45
    elif turb_mod:
        score += 30

    if score >= 60:
        decision = "MARGINAL"
    else:
        decision = "GO"

    return decision, vis, base, ts_flag, turb_sev, turb_mod

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    zone_data = parse_gamet(gamet_text)
    results = {z: decision_for_zone(zone_data[z]) for z in ZONES}

    st.subheader("📋 Briefing Detalhado")
    cols = st.columns(3)

    for i, z in enumerate(ZONES):
        decision, vis, base, ts_flag, turb_sev, turb_mod = results[z]

        with cols[i]:
            st.markdown(f"### {z}")

            if decision == "NO-GO":
                st.error("🔴 NO-GO")
            elif decision == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.write(f"👁️ {vis} m" if vis is not None else "👁️ —")
            st.write(f"☁️ {base} ft AGL" if base is not None else "☁️ —")
            st.write(f"⛈️ {'Sim' if ts_flag else 'Não'}")

            if turb_sev:
                st.write("🌪️ Turbulência Severa")
            elif turb_mod:
                st.write("🌬️ Turbulência Moderada")
            else:
                st.write("🌬️ Turbulência Não Significativa")

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.divider()
    st.subheader("🌍 Mapa VFR – Sectores LOWER Oficiais")

    fig, ax = plt.subplots(figsize=(7, 10))
    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    for zone_name, poly in ZONES.items():
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.25, color=color_map[results[zone_name][0]])
        ax.plot(x, y)

    cities = {
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

    for name, (lat, lon) in cities.items():
        ax.plot(lon, lat, "ko", markersize=4)
        ax.text(lon + 0.05, lat, name, fontsize=8, va="center")

    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    ax.set_xlabel("Longitude (°W)")
    ax.set_ylabel("Latitude (°N)")
    ax.grid(True, linestyle="--", alpha=0.4)

    ax.legend(handles=[
        Patch(facecolor="green", alpha=0.25, label="GO"),
        Patch(facecolor="orange", alpha=0.25, label="MARGINAL"),
        Patch(facecolor="red", alpha=0.25, label="NO-GO"),
        Line2D([0], [0], marker='o', color='black',
               linestyle='None', label='Cidade')
    ])

    st.pyplot(fig)

    st.caption("Motor cartográfico v4.51 – Versão Estável Auditada")
