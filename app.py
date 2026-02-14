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
    height=260
)

# -------------------------------------------------
# DEFINIÇÃO DAS ZONAS
# -------------------------------------------------
ZONES = {
    "NORTE": {"lat_min": 39.5, "lat_max": 42.5, "lon_min": -9.5, "lon_max": -6.0},
    "CENTRO": {"lat_min": 38.5, "lat_max": 39.5, "lon_min": -9.5, "lon_max": -6.0},
    "SUL": {"lat_min": 36.5, "lat_max": 38.5, "lon_min": -9.5, "lon_max": -6.0},
}

# -------------------------------------------------
# FUNÇÃO AUXILIAR
# -------------------------------------------------
def zone_midpoint(zone):
    z = ZONES[zone]
    return (
        (z["lat_min"] + z["lat_max"]) / 2,
        (z["lon_min"] + z["lon_max"]) / 2,
    )

# -------------------------------------------------
# PARSER GEOGRÁFICO AVANÇADO
# -------------------------------------------------
def zones_from_condition(line):

    line = line.upper()
    affected = set(ZONES.keys())

    # --- N OF ---
    for match in re.findall(r"N OF N(\d{2})(\d{2})", line):
        lat = int(match[0]) + int(match[1]) / 60
        tmp = set()
        for z in ZONES:
            lat_mid, _ = zone_midpoint(z)
            if lat_mid > lat:
                tmp.add(z)
        affected &= tmp

    # --- S OF ---
    for match in re.findall(r"S OF N(\d{2})(\d{2})", line):
        lat = int(match[0]) + int(match[1]) / 60
        tmp = set()
        for z in ZONES:
            lat_mid, _ = zone_midpoint(z)
            if lat_mid < lat:
                tmp.add(z)
        affected &= tmp

    # --- E OF ---
    for match in re.findall(r"E OF W(\d{2})(\d{2})", line):
        lon = -(int(match[0]) + int(match[1]) / 60)
        tmp = set()
        for z in ZONES:
            _, lon_mid = zone_midpoint(z)
            if lon_mid > lon:
                tmp.add(z)
        affected &= tmp

    # --- W OF ---
    for match in re.findall(r"W OF W(\d{2})(\d{2})", line):
        lon = -(int(match[0]) + int(match[1]) / 60)
        tmp = set()
        for z in ZONES:
            _, lon_mid = zone_midpoint(z)
            if lon_mid < lon:
                tmp.add(z)
        affected &= tmp

    # --- BTW latitude band ---
    for match in re.findall(r"BTW N(\d{2})(\d{2}) AND N(\d{2})(\d{2})", line):
        lat1 = int(match[0]) + int(match[1]) / 60
        lat2 = int(match[2]) + int(match[3]) / 60
        lower, upper = min(lat1, lat2), max(lat1, lat2)
        tmp = set()
        for z in ZONES:
            lat_mid, _ = zone_midpoint(z)
            if lower <= lat_mid <= upper:
                tmp.add(z)
        affected &= tmp

    return list(affected) if affected else list(ZONES.keys())

# -------------------------------------------------
# PARSER METEOROLÓGICO
# -------------------------------------------------
def parse_gamet(text):

    lines = text.upper().splitlines()
    zone_data = {z: [] for z in ZONES}

    for line in lines:

        zones = zones_from_condition(line)

        # VIS
        for low, _ in re.findall(r"(\d{4})-(\d{4})M", line):
            for z in zones:
                zone_data[z].append(("VIS", int(low)))

        for val in re.findall(r"\b(\d{4})M\b", line):
            for z in zones:
                zone_data[z].append(("VIS", int(val)))

        # BASE
        for _, base in re.findall(r"(BKN|OVC)\s?(\d{3})", line):
            for z in zones:
                zone_data[z].append(("BASE", int(base) * 100))

        # TS
        if "TS" in line:
            for z in zones:
                zone_data[z].append(("TS", 1))

        # TURB
        if "TURB" in line:
            level = "SEV" if "SEV" in line else "MOD" if "MOD" in line else None
            if level:
                for z in zones:
                    zone_data[z].append(("TURB", level))

    return zone_data

# -------------------------------------------------
# MOTOR DECISÃO GA
# -------------------------------------------------
def decision_for_zone(events):

    vis = min([v for t, v in events if t == "VIS"], default=None)
    base = min([v for t, v in events if t == "BASE"], default=None)

    ts = any(t == "TS" for t, _ in events)
    turb_sev = any(t == "TURB" and v == "SEV" for t, v in events)
    turb_mod = any(t == "TURB" and v == "MOD" for t, v in events)

    # HARD LIMITS
    if vis is not None and vis < 3000:
        return "NO-GO", vis, base, ts, turb_sev, turb_mod

    if base is not None and base < 500:
        return "NO-GO", vis, base, ts, turb_sev, turb_mod

    # SCORING
    score = 0

    if vis and 3000 <= vis < 5000:
        score += 30
    if base and 500 <= base < 1500:
        score += 40
    if ts:
        score += 50
    if turb_sev:
        score += 45
    elif turb_mod:
        score += 25

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

    # RESUMO
    st.subheader("📌 Resumo Executivo")
    cols = st.columns(3)

    for i, z in enumerate(ZONES):
        decision = results[z][0]
        if decision == "NO-GO":
            cols[i].error(f"{z}\nNO-GO")
        elif decision == "MARGINAL":
            cols[i].warning(f"{z}\nMARGINAL")
        else:
            cols[i].success(f"{z}\nGO")

    st.divider()

    # MAPA
    st.subheader("🗺️ Mapa VFR")

    fig, ax = plt.subplots(figsize=(6, 10))
    color_map = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    zone_y = {
        "NORTE": (9, 14),
        "CENTRO": (4, 9),
        "SUL": (-4.5, 4)
    }

    for z, (y0, y1) in zone_y.items():
        ax.axhspan(y0, y1, color=color_map[results[z][0]], alpha=0.2)

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
        ax.text(x + 0.02, y, name, fontsize=8, va="center")

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





