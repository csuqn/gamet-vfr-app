import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Briefing VFR Geográfico (GA Realista)")

gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=300
)

# -------------------------------------------------
# ZONAS
# -------------------------------------------------
ZONES = {
    "NORTE": {"min_lat": 39.5, "max_lat": 42.5},
    "CENTRO": {"min_lat": 38.5, "max_lat": 39.5},
    "SUL": {"min_lat": 36.5, "max_lat": 38.5}
}

# -------------------------------------------------
# GEOGRAFIA
# -------------------------------------------------
def zones_from_lat_condition(line):

    match = re.search(r"([NS])\s+OF\s+N(\d{2})(\d{2})", line)

    if not match:
        return list(ZONES.keys())

    direction = match.group(1)
    lat_deg = int(match.group(2))
    lat_min = int(match.group(3))
    latitude = lat_deg + lat_min / 60

    affected = []

    for zone, limits in ZONES.items():
        zone_mid = (limits["min_lat"] + limits["max_lat"]) / 2

        if direction == "N" and zone_mid > latitude:
            affected.append(zone)
        elif direction == "S" and zone_mid < latitude:
            affected.append(zone)

    return affected

# -------------------------------------------------
# PARSER
# -------------------------------------------------
def parse_gamet(text):

    text = text.upper()
    lines = text.splitlines()
    zone_data = {z: [] for z in ZONES}

    for line in lines:

        affected_zones = zones_from_lat_condition(line)

        ranges = re.findall(r"(\d{4})-(\d{4})M", line)
        for low, _ in ranges:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(low)))

        singles = re.findall(r"\b(\d{4})M\b", line)
        for val in singles:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(val)))

        bases = re.findall(r"(BKN|OVC)\s?(\d{3})", line)
        for _, base in bases:
            for z in affected_zones:
                zone_data[z].append(("BASE", int(base) * 100))

        if "TS" in line:
            for z in affected_zones:
                zone_data[z].append(("TS", 1))

        if "TURB" in line:
            if "SEV" in line:
                for z in affected_zones:
                    zone_data[z].append(("TURB", "SEV"))
            elif "MOD" in line:
                for z in affected_zones:
                    zone_data[z].append(("TURB", "MOD"))

    return zone_data

# -------------------------------------------------
# MOTOR GA REALISTA
# -------------------------------------------------
def decision_for_zone(events):

    vis_values = [v for t, v in events if t == "VIS"]
    base_values = [v for t, v in events if t == "BASE"]

    vis = min(vis_values) if vis_values else None
    base = min(base_values) if base_values else None

    ts = any(t == "TS" for t, _ in events)
    turb_sev = any(t == "TURB" and v == "SEV" for t, v in events)
    turb_mod = any(t == "TURB" and v == "MOD" for t, v in events)

    # HARD LIMITS
    if vis is not None and vis < 3000:
        return "NO-GO", ["Visibilidade < 3000m"], vis, base, ts, turb_sev, turb_mod

    if base is not None and base < 500:
        return "NO-GO", ["Base < 500ft"], vis, base, ts, turb_sev, turb_mod

    # SOFT
    score = 0
    reasons = []

    if vis is not None and 3000 <= vis < 5000:
        score += 30
        reasons.append("Vis 3000–5000m")

    if base is not None and 500 <= base < 1500:
        score += 40
        reasons.append("Base 500–1500ft")

    if ts:
        score += 50
        reasons.append("Trovoadas isoladas")

    if turb_sev:
        score += 45
        reasons.append("Turb severa")
    elif turb_mod:
        score += 25
        reasons.append("Turb moderada")

    if score >= 140:
        decision = "NO-GO"
    elif score >= 70:
        decision = "MARGINAL"
    else:
        decision = "GO"

    return decision, reasons, vis, base, ts, turb_sev, turb_mod


# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    zone_data = parse_gamet(gamet_text)
    results = {z: decision_for_zone(zone_data[z]) for z in ZONES}

    # -------------------------------------------------
    # RESUMO EXECUTIVO
    # -------------------------------------------------
    st.subheader("📌 Resumo Executivo")

    summary_cols = st.columns(3)

    for i, zone in enumerate(ZONES):
        decision = results[zone][0]

        if decision == "NO-GO":
            summary_cols[i].error(f"{zone}\nNO-GO")
        elif decision == "MARGINAL":
            summary_cols[i].warning(f"{zone}\nMARGINAL")
        else:
            summary_cols[i].success(f"{zone}\nGO")

    st.divider()

    # -------------------------------------------------
    # PAINEL TIPO COCKPIT
    # -------------------------------------------------
    st.subheader("📋 Briefing Meteorológico Detalhado")

    cols = st.columns(3)

    for i, zone in enumerate(ZONES):

        decision, reasons, vis, base, ts, turb_sev, turb_mod = results[zone]

        with cols[i]:

            st.markdown(f"### 🗺️ {zone}")

            # DECISÃO
            if decision == "NO-GO":
                if any("Visibilidade < 3000m" in r or "Base < 500ft" in r for r in reasons):
                    st.error("🔴 HARD LIMIT")
                else:
                    st.error("❌ NO-GO")
            elif decision == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.markdown("**Condições:**")

            if vis is not None:
                st.write(f"👁️ {vis} m")
            else:
                st.write("👁️ —")

            if base is not None:
                if base == 0:
                    st.write("☁️ SFC")
                else:
                    st.write(f"☁️ {base} ft")
            else:
                st.write("☁️ Base significativa não reportada")

            st.write(f"⛈️ {'Sim' if ts else 'Não'}")

            if turb_sev:
                st.write("🌪️ Severa")
            elif turb_mod:
                st.write("🌬️ Moderada")
            else:
                st.write("🌬️ Não significativa")

            if reasons:
                st.markdown("**Limitantes:**")
                for r in reasons:
                    st.write(f"• {r}")

    st.divider()

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR")

    fig, ax = plt.subplots(figsize=(6, 10))
    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

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




