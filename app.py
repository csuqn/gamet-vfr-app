import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")
st.title("✈️ LPPC GAMET – Análise VFR Geográfica")

gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=350
)

# -------------------------------------------------
# DEFINIÇÃO DAS ZONAS
# -------------------------------------------------
ZONES = {
    "NORTE": {"min_lat": 39.5, "max_lat": 90},
    "CENTRO": {"min_lat": 38.5, "max_lat": 39.5},
    "SUL": {"min_lat": -90, "max_lat": 38.5}
}

# -------------------------------------------------
# FUNÇÃO AUXILIAR – DETETAR ZONA POR LATITUDE
# -------------------------------------------------
def zones_from_lat_condition(condition):

    match = re.search(r"([NS])\s?OF\s?N(\d{2})(\d{2})", condition)

    if not match:
        return list(ZONES.keys())  # aplica globalmente

    direction = match.group(1)
    lat_deg = int(match.group(2))
    lat_min = int(match.group(3))

    latitude = lat_deg + lat_min / 60

    affected = []

    for zone, limits in ZONES.items():
        if direction == "N" and limits["max_lat"] >= latitude:
            if limits["min_lat"] >= latitude:
                affected.append(zone)
        elif direction == "S" and limits["min_lat"] <= latitude:
            if limits["max_lat"] <= latitude:
                affected.append(zone)

    return affected if affected else list(ZONES.keys())


# -------------------------------------------------
# PARSER GEOGRÁFICO
# -------------------------------------------------
def parse_gamet_geographical(text):

    text = text.upper()
    lines = text.splitlines()

    zone_data = {
        "NORTE": [],
        "CENTRO": [],
        "SUL": []
    }

    for line in lines:

        affected_zones = zones_from_lat_condition(line)

        # VIS
        vis_matches = re.findall(r"(\d{4})-(\d{4})M", line)
        for low, _ in vis_matches:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(low)))

        singles = re.findall(r"\b(\d{4})M\b", line)
        for val in singles:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(val)))

        # CLOUD BASE
        if "BKN" in line or "OVC" in line:
            bases = re.findall(r"(BKN|OVC)\s?(\d{3})", line)
            for _, base in bases:
                for z in affected_zones:
                    zone_data[z].append(("BASE", int(base) * 100))

        # TS
        if "TS" in line:
            for z in affected_zones:
                zone_data[z].append(("TS", 1))

        # TURB
        if "TURB" in line:
            if "SEV" in line:
                for z in affected_zones:
                    zone_data[z].append(("TURB", "SEV"))
            elif "MOD" in line:
                for z in affected_zones:
                    zone_data[z].append(("TURB", "MOD"))

    return zone_data


# -------------------------------------------------
# MOTOR POR ZONA
# -------------------------------------------------
def decision_for_zone(zone_events):

    vis = min([v for t, v in zone_events if t == "VIS"], default=None)
    base = min([v for t, v in zone_events if t == "BASE"], default=None)
    ts = any(t == "TS" for t, _ in zone_events)
    turb_sev = any(t == "TURB" and v == "SEV" for t, v in zone_events)
    turb_mod = any(t == "TURB" and v == "MOD" for t, v in zone_events)

    # HARD LIMITS
    if vis is not None and vis < 3000:
        return "NO-GO", ["Visibilidade < 3000m"]

    if base is not None and base < 500:
        return "NO-GO", ["Base < 500ft"]

    # SOFT
    score = 0
    reasons = []

    if vis is not None and vis < 5000:
        score += 40
        reasons.append("Vis 3000–5000m")

    if base is not None and base < 1500:
        score += 50
        reasons.append("Base 500–1500ft")

    if ts:
        score += 60
        reasons.append("Trovoadas")

    if turb_sev:
        score += 60
        reasons.append("Turb severa")
    elif turb_mod:
        score += 35
        reasons.append("Turb moderada")

    if score >= 100:
        return "NO-GO", reasons
    elif score >= 50:
        return "MARGINAL", reasons
    else:
        return "GO", reasons


# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    zone_data = parse_gamet_geographical(gamet_text)

    results = {}

    for zone in ZONES.keys():
        decision, reasons = decision_for_zone(zone_data[zone])
        results[zone] = (decision, reasons)

    st.subheader("📋 Resultado por Zona")

    for zone, (decision, reasons) in results.items():

        if decision == "NO-GO":
            st.error(f"{zone}: ❌ NO-GO")
        elif decision == "MARGINAL":
            st.warning(f"{zone}: ⚠️ MARGINAL")
        else:
            st.success(f"{zone}: ✅ GO")

        for r in reasons:
            st.write(f"• {r}")

        st.divider()

    # ---------------- MAPA ----------------
    st.subheader("🗺️ Mapa VFR – Decisão Geográfica")

    fig, ax = plt.subplots(figsize=(6, 10))

    color_map = {
        "GO": "green",
        "MARGINAL": "orange",
        "NO-GO": "red"
    }

    ZONE_Y = {
        "NORTE": (9.0, 14.0),
        "CENTRO": (4.0, 9.0),
        "SUL": (-4.5, 4.0)
    }

    for zone, (y0, y1) in ZONE_Y.items():
        decision = results[zone][0]
        ax.axhspan(y0, y1, color=color_map[decision], alpha=0.18)

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Decisão VFR por Zona")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui julgamento do piloto.")
