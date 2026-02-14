import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Briefing VFR Geográfico (FASE 4)")

gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=250
)

# -------------------------------------------------
# DEFINIÇÃO DAS ZONAS (com latitude e longitude)
# -------------------------------------------------
ZONES = {
    "NORTE": {
        "lat_min": 39.5, "lat_max": 42.5,
        "lon_min": -9.5, "lon_max": -6.0
    },
    "CENTRO": {
        "lat_min": 38.5, "lat_max": 39.5,
        "lon_min": -9.5, "lon_max": -6.0
    },
    "SUL": {
        "lat_min": 36.5, "lat_max": 38.5,
        "lon_min": -9.5, "lon_max": -6.0
    }
}

# -------------------------------------------------
# PARSER GEOGRÁFICO AVANÇADO
# -------------------------------------------------
def zones_from_condition(line):

    line = line.upper()
    affected = set(ZONES.keys())

    # N OF
    match = re.search(r"N OF N(\d{2})(\d{2})", line)
    if match:
        lat = int(match.group(1)) + int(match.group(2)) / 60
        new = set()
        for z, lim in ZONES.items():
            lat_mid = (lim["lat_min"] + lim["lat_max"]) / 2
            if lat_mid > lat:
                new.add(z)
        affected &= new

    # S OF
    match = re.search(r"S OF N(\d{2})(\d{2})", line)
    if match:
        lat = int(match.group(1)) + int(match.group(2)) / 60
        new = set()
        for z, lim in ZONES.items():
            lat_mid = (lim["lat_min"] + lim["lat_max"]) / 2
            if lat_mid < lat:
                new.add(z)
        affected &= new

    # E OF
    match = re.search(r"E OF W(\d{2})(\d{2})", line)
    if match:
        lon = -(int(match.group(1)) + int(match.group(2)) / 60)
        new = set()
        for z, lim in ZONES.items():
            lon_mid = (lim["lon_min"] + lim["lon_max"]) / 2
            if lon_mid > lon:
                new.add(z)
        affected &= new

    # W OF
    match = re.search(r"W OF W(\d{2})(\d{2})", line)
    if match:
        lon = -(int(match.group(1)) + int(match.group(2)) / 60)
        new = set()
        for z, lim in ZONES.items():
            lon_mid = (lim["lon_min"] + lim["lon_max"]) / 2
            if lon_mid < lon:
                new.add(z)
        affected &= new

    # BTW latitude band
    match = re.search(r"BTW N(\d{2})(\d{2}) AND N(\d{2})(\d{2})", line)
    if match:
        lat1 = int(match.group(1)) + int(match.group(2)) / 60
        lat2 = int(match.group(3)) + int(match.group(4)) / 60
        lower = min(lat1, lat2)
        upper = max(lat1, lat2)

        new = set()
        for z, lim in ZONES.items():
            lat_mid = (lim["lat_min"] + lim["lat_max"]) / 2
            if lower <= lat_mid <= upper:
                new.add(z)
        affected &= new

    return list(affected)

# -------------------------------------------------
# PARSER METEOROLÓGICO
# -------------------------------------------------
def parse_gamet(text):

    text = text.upper()
    lines = text.splitlines()
    zone_data = {z: [] for z in ZONES}

    for line in lines:

        affected_zones = zones_from_condition(line)

        # VIS
        for low, _ in re.findall(r"(\d{4})-(\d{4})M", line):
            for z in affected_zones:
                zone_data[z].append(("VIS", int(low)))

        for val in re.findall(r"\b(\d{4})M\b", line):
            for z in affected_zones:
                zone_data[z].append(("VIS", int(val)))

        # BASE
        for _, base in re.findall(r"(BKN|OVC)\s?(\d{3})", line):
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

    vis_vals = [v for t, v in events if t == "VIS"]
    base_vals = [v for t, v in events if t == "BASE"]

    vis = min(vis_vals) if vis_vals else None
    base = min(base_vals) if base_vals else None

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

    # RESUMO EXECUTIVO
    st.subheader("📌 Resumo Executivo")
    cols = st.columns(3)

    for i, zone in enumerate(ZONES):
        decision = results[zone][0]
        if decision == "NO-GO":
            cols[i].error(f"{zone}\nNO-GO")
        elif decision == "MARGINAL":
            cols[i].warning(f"{zone}\nMARGINAL")
        else:
            cols[i].success(f"{zone}\nGO")

    st.divider()

    # MAPA
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
        ax.axhspan(y0, y1, color=color_map[decision], alpha=0.2)

    # TODAS AS CIDADES RESTAURADAS
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
        ax.plot(x, y, "ko", markersize=4)
        ax.text(x + 0.02, y, name, va="center", fontsize=9)

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Decisão VFR por Zona")

    ax.legend(handles=[
        Patch(facecolor="green", alpha=0.2, label="GO"),
        Patch(facecolor="orange", alpha=0.2, label="MARGINAL"),
        Patch(facecolor="red", alpha=0.2, label="NO-GO"),
        Line2D([0], [0], marker='o', color='black', linestyle='None', label='Cidade')
    ])

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui julgamento do piloto.")





