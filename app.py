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
st.title("✈️ LPPC GAMET – Motor Cartográfico v4.40")

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=260
)

# -------------------------------------------------
# FIR BOUNDING BOX (WGS84)
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

ZONE_ELEVATION = {
    "NORTE": 1500,
    "CENTRO": 800,
    "SUL": 300,
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
# SPLIT PRINCIPAL
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
# INTERSECÇÃO GEOGRÁFICA
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
# PARSER
# -------------------------------------------------
def parse_gamet(text):

    text = normalize_text(text)
    sections = split_into_sections(text)
    zone_data = {z: [] for z in ZONES}

    for section in sections:

        # ---------------- VIS ----------------
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

        # ---------------- CLD (por blocos temporais) ----------------
        if section.startswith("CLD:") or section.startswith("SIG CLD:"):

            cld_body = section.split(":", 1)[1]

            # Divide apenas por blocos de tempo reais (XX/XX)
            blocks = re.split(r"\s(?=\d{2}/\d{2})", cld_body)

            for block in blocks:

                block_poly = extract_condition_polygon(block)

                for zone_name, zone_poly in ZONES.items():
                    if not zone_poly.intersects(block_poly):
                        continue

                    # AGL
                    for match in re.findall(r"\b(\d{3})-\d{3}(?:/\d{3})?HFT AGL", block):
                        zone_data[zone_name].append(("BASE", int(match) * 100))

                    # AMSL
                    for match in re.findall(r"\b(\d{3})-\d{3}(?:/\d{3})?HFT AMSL", block):
                        base_amsl = int(match) * 100
                        agl_est = base_amsl - ZONE_ELEVATION[zone_name]
                        if agl_est > 0:
                            zone_data[zone_name].append(("BASE", agl_est))

        # ---------------- TURB ----------------
        if section.startswith("TURB:"):

            section_poly = extract_condition_polygon(section)

            for zone_name, zone_poly in ZONES.items():
                if not zone_poly.intersects(section_poly):
                    continue

                if "SEV" in section:
                    zone_data[zone_name].append(("TURB", "SEV"))
                elif "MOD" in section:
                    zone_data[zone_name].append(("TURB", "MOD"))

        # ---------------- TS ----------------
        if re.search(r"\bISOL TS\b", section):
            for z in ZONES:
                zone_data[z].append(("TS", "ISOL"))
        elif re.search(r"\bOCNL TS\b", section):
            for z in ZONES:
                zone_data[z].append(("TS", "OCNL"))
        elif re.search(r"\bFRQ TS\b", section):
            for z in ZONES:
                zone_data[z].append(("TS", "FRQ"))
        elif re.search(r"(^|\s)TS(\s|$)", section):
            for z in ZONES:
                zone_data[z].append(("TS", "GEN"))

    return zone_data

# -------------------------------------------------
# DECISÃO (inalterada)
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

    # ---------------- BRIEFING ----------------
    st.subheader("📋 Briefing Detalhado")
    
    with st.expander("ℹ️ Legenda do Briefing"):
    st.markdown("""
**🔴 NO-GO** – Condições abaixo dos mínimos VFR definidos  
**⚠️ MARGINAL** – Condições próximas dos limites operacionais  
**✅ GO** – Condições favoráveis à operação VFR  

**👁️ Visibilidade** – Valor mínimo considerado (em metros)  
**☁️ Base** – Altura mínima da base das nuvens (ft AGL)  
**⛈️ TS** – Presença de trovoadas (Thunderstorms)  
**🌪️ Turbulência Severa** – Turbulência significativa  
**🌬️ Turbulência Moderada** – Turbulência operacionalmente relevante  
""")

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

    # ---------------- MAPA ----------------
    st.divider()
    st.subheader("🌍 Mapa VFR – WGS84")

    fig, ax = plt.subplots(figsize=(6, 9))
    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    zone_lat = {
        "NORTE": (39.5, 42.5),
        "CENTRO": (38.5, 39.5),
        "SUL": (36.5, 38.5),
    }

    for zone_name, (lat_min, lat_max) in zone_lat.items():
        ax.fill_between(
            [LON_MIN, LON_MAX],
            lat_min,
            lat_max,
            color=color_map[results[zone_name][0]],
            alpha=0.25
        )

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

    st.caption("Motor cartográfico v4.40 – CLD robusto por blocos temporais.")
