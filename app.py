
import streamlit as st
import re
import matplotlib.pyplot as plt

# -------------------------------------------------
# CONFIGURAÇÃO STREAMLIT
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")
st.title("✈️ LPPC GAMET – Análise VFR")

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=330
)

show_reasons = st.checkbox("Mostrar motivos no mapa", value=True)

# -------------------------------------------------
# ZONAS (LATITUDES APROXIMADAS)
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

PARTIAL_CUTS = {z: [] for z in ZONE_BANDS}

# -------------------------------------------------
# FUNÇÕES ESPACIAIS
# -------------------------------------------------
def line_applies_to_zone(line, zone):
    zmin, zmax = ZONE_BANDS[zone]

    north_of = re.search(r"N OF N(\d{2})(\d{2})", line)
    south_of = re.search(r"S OF N(\d{2})(\d{2})", line)

    if north_of:
        lat = int(north_of.group(1)) + int(north_of.group(2)) / 60
        if zmax < lat:
            return False
        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("NORTH", lat))
        return True

    if south_of:
        lat = int(south_of.group(1)) + int(south_of.group(2)) / 60
        if zmin > lat:
            return False
        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("SOUTH", lat))
        return True

    return True


def filter_text_for_zone(text, zone):
    return " ".join(
        line for line in text.splitlines()
        if line_applies_to_zone(line, zone)
    )


def lat_to_y(lat):
    # 36.5N → -4.5 | 42.5N → 14.0
    return -4.5 + (lat - 36.5) * (18.5 / 6.0)

# -------------------------------------------------
# LÓGICA VFR
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    status = "VFR OK"
    blocking = False

    vis_matches = re.findall(r"(\d{4})M", text)
    if vis_matches:
        min_vis = min(int(v) for v in vis_matches)
        if min_vis < 3000:
            return "VFR NO-GO", [f"VIS {min_vis} m"], True
        elif min_vis < 5000:
            status = "VFR MARGINAL"
            reasons.append(f"VIS {min_vis} m")

    cld = re.search(r"(BKN|OVC)[ /]*(\d{3})", text)
    if cld:
        base_ft = int(cld.group(2)) * 100
        if base_ft < 500:
            return "VFR NO-GO", [f"{cld.group(1)} {base_ft} ft"], True
        elif base_ft < 1500:
            status = "VFR MARGINAL"
            reasons.append(f"{cld.group(1)} {base_ft} ft")

    return status, reasons, blocking

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}

    for z in ZONE_BANDS:
        ztext = filter_text_for_zone(text, z)
        zones[z] = analyze_zone(ztext)

    # -------------------------------------------------
    # MAPA ESQUEMÁTICO
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    ZONE_Y = {
        "NORTE": (9.0, 14.0),
        "CENTRO": (4.0, 9.0),
        "SUL": (-4.5, 4.0)
    }

    for z, (y0, y1) in ZONE_Y.items():
        status, reasons, blocking = zones[z]

        if status == "VFR NO-GO" and blocking and PARTIAL_CUTS[z]:
            cut_dir, lat = PARTIAL_CUTS[z][0]
            cut_y = lat_to_y(lat)

            # 🔧 CORREÇÃO CRÍTICA
            cut_y = max(y0, min(y1, cut_y))

            if cut_dir == "NORTH":
                ax.axhspan(cut_y, y1, color="red", alpha=0.25)
                ax.axhspan(y0, cut_y, color="green", alpha=0.25)
            else:
                ax.axhspan(y0, cut_y, color="red", alpha=0.25)
                ax.axhspan(cut_y, y1, color="green", alpha=0.25)

            ax.axhline(cut_y, linestyle="--", color="black")

        else:
            if status == "VFR OK":
                ax.axhspan(y0, y1, color="green", alpha=0.25)
            elif status == "VFR MARGINAL":
                ax.axhspan(y0, y1, color="yellow", alpha=0.35)
            else:
                ax.axhspan(y0, y1, color="red", alpha=0.25)

        if show_reasons:
            label = status if not reasons else status + "\n" + "\n".join(reasons)
            ax.text(0.02, (y0 + y1) / 2, label, fontsize=8, va="center")

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")

