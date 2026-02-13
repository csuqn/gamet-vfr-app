import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")
st.title("✈️ LPPC GAMET – Briefing VFR Geográfico (GA Realista)")

gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=350
)

# -------------------------------------------------
# DEFINIÇÃO DAS ZONAS
# -------------------------------------------------
ZONES = {
    "NORTE": {"min_lat": 39.5, "max_lat": 42.5},
    "CENTRO": {"min_lat": 38.5, "max_lat": 39.5},
    "SUL": {"min_lat": 36.5, "max_lat": 38.5}
}

# -------------------------------------------------
# DETETAR ZONAS POR EXPRESSÃO GEOGRÁFICA
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
# PARSER GEOGRÁFICO
# -------------------------------------------------
def parse_gamet_geographical(text):

    text = text.upper()
    lines = text.splitlines()

    zone_data = {z: [] for z in ZONES}

    for line in lines:

        affected_zones = zones_from_lat_condition(line)

        # VIS RANGES
        ranges = re.findall(r"(\d{4})-(\d{4})M", line)
        for low, _ in ranges:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(low)))

        # VIS SINGLE
        singles = re.findall(r"\b(\d{4})M\b", line)
        for val in singles:
            for z in affected_zones:
                zone_data[z].append(("VIS", int(val)))

        # CLOUD BASE
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

    # SOFT SCORING
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

    zone_data = parse_gamet_geographical(gamet_text)
    results = {z: decision_for_zone(zone_data[z]) for z in ZONES}

    st.subheader("📋 Briefing Meteorológico por Zona")

    for zone in ZONES:

        decision, reasons, vis, base, ts, turb_sev, turb_mod = results[zone]

        with st.container():

            st.markdown(f"### 🗺️ {zone}")

            # DECISÃO DESTACADA
            if decision == "NO-GO":
                if any("Visibilidade < 3000m" in r or "Base < 500ft" in r for r in reasons):
                    st.error("🔴 HARD LIMIT ATIVO – NO-GO")
                else:
                    st.error("❌ NO-GO")
            elif decision == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.markdown("**Condições Detetadas:**")

            if vis is not None:
                st.write(f"👁️ Visibilidade mínima: {vis} m")
            else:
                st.write("👁️ Visibilidade: —")

            if base is not None:
                if base == 0:
                    st.write("☁️ Base mínima: SFC (0 ft)")
                else:
                    st.write(f"☁️ Base mínima: {base} ft")
            else:
                st.write("☁️ Base: —")

            st.write(f"⛈️ Trovoadas: {'Sim' if ts else 'Não detetadas'}")

            if turb_sev:
                st.write("🌪️ Turbulência: Severa")
            elif turb_mod:
                st.write("🌬️ Turbulência: Moderada")
            else:
                st.write("🌬️ Turbulência: Não significativa")

            if reasons:
                st.markdown("**Fatores Limitantes:**")
                for r in reasons:
                    st.write(f"• {r}")

            st.divider()

    # ---------------- MAPA ----------------
    st.subheader("🗺️ Mapa VFR – Decisão Geográfica")

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

    cities = {
        "Bragança": (0.8, 13.5),
        "Viana do Castelo": (0.2, 12.6),
        "Braga": (0.4, 11.8),
        "Vila Real": (0.6, 11.0),
        "Porto": (0.3, 10.5),
        "Viseu": (0.6, 8.6),
        "Aveiro": (0.3, 8.0),
        "Guarda": (0.8, 7.4),
        "Coimbra": (0.5, 6.6),
        "Leiria": (0.3, 5.6),
        "Castelo Branco": (0.8, 5.9),
        "Santarém": (0.4, 3.0),
        "Portalegre": (0.8, 3.0),
        "Lisboa": (0.3, 2.0),
        "Setúbal": (0.3, 1.2),
        "Évora": (0.6, 0.2),
        "Beja": (0.7, -1.0),
        "Faro": (0.7, -2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.legend(
        handles=[
            Patch(facecolor="green", alpha=0.25, label="GO"),
            Patch(facecolor="orange", alpha=0.25, label="MARGINAL"),
            Patch(facecolor="red", alpha=0.25, label="NO-GO"),
            Line2D([0], [0], marker="o", color="black",
                   linestyle="None", markersize=4, label="Cidade")
        ],
        loc="lower left",
        fontsize=8
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Decisão VFR por Zona")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui julgamento do piloto.")




