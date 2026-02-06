import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# -------------------------------------------------
# CONFIGURAÇÃO
# -------------------------------------------------
st.set_page_config(page_title="LPPC GAMET – VFR", layout="centered")

col1, col2 = st.columns([0.95, 0.05])
with col1:
    st.title("✈️ LPPC GAMET – Análise VFR")
with col2:
    st.tooltip(
        "ℹ️",
        """
VIS < 3000 m ⇒ NO-GO global
BKN/OVC < 500 ft ⇒ NO-GO (parcial só com N/S OF)
Fenómenos não-VFR não bloqueiam
Decisão sempre conservadora
Não substitui o julgamento do piloto
"""
    )

# -------------------------------------------------
# INPUT
# -------------------------------------------------
gamet_text = st.text_area(
    "Cole aqui o texto completo do GAMET (LPPC)",
    height=330
)

# -------------------------------------------------
# ZONAS (latitudes aproximadas)
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

PARTIAL_CUTS = {z: [] for z in ZONE_BANDS}

# -------------------------------------------------
# FUNÇÕES ESPACIAIS (APENAS PARA CLD)
# -------------------------------------------------
def line_applies_to_zone(line, zone):
    zmin, zmax = ZONE_BANDS[zone]
    is_vfr_relevant = "CLD" in line

    north_of = re.search(r"N OF N(\d{2})(\d{2})", line)
    south_of = re.search(r"S OF N(\d{2})(\d{2})", line)

    if north_of and is_vfr_relevant:
        lat = int(north_of.group(1)) + int(north_of.group(2)) / 60
        if zmax < lat:
            return False
        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("NORTH", lat))
        return True

    if south_of and is_vfr_relevant:
        lat = int(south_of.group(1)) + int(south_of.group(2)) / 60
        if zmin > lat:
            return False
        if zmin < lat < zmax:
            PARTIAL_CUTS[zone].append(("SOUTH", lat))
        return True

    return True


def filter_text_for_zone(text, zone):
    return "\n".join(
        line for line in text.splitlines()
        if line_applies_to_zone(line, zone)
    )

# -------------------------------------------------
# PARSING
# -------------------------------------------------
def extract_min_visibility(text):
    """
    VIS global: se existir VIS < 3000 m em qualquer parte,
    resulta em NO-GO global.
    """
    values = []

    for line in text.splitlines():
        if "VIS" not in line:
            continue

        for m in re.findall(r"(\d{4})-(\d{4})M", line):
            values.append(int(m[0]))

        for m in re.findall(r"VIS\s*(\d{4})M", line):
            values.append(int(m))

        for m in re.findall(r"LOC\s*(\d{4})M", line):
            values.append(int(m))

    return min(values) if values else None


def extract_min_cloud_base(text):
    """
    Base mínima de nuvens BKN/OVC.
    """
    clouds = []

    for m in re.findall(r"(BKN|OVC)\s*(\d{3})", text):
        clouds.append((m[0], int(m[1]) * 100))

    return min(clouds, key=lambda x: x[1]) if clouds else None

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}

    # -------------------------------------------------
    # REGRA ABSOLUTA: VIS GLOBAL
    # -------------------------------------------------
    global_vis = extract_min_visibility(text)

    if global_vis is not None and global_vis < 3000:
        # NO-GO GLOBAL
        for z in ZONE_BANDS:
            zones[z] = (
                "NO-GO",
                [f"VIS: {global_vis} m"],
                ["VIS < 3000 m"]
            )
    else:
        # Avaliação por CLD
        for z in ZONE_BANDS:
            ztext = filter_text_for_zone(text, z)
            reasons = []
            limiting = []

            cloud = extract_min_cloud_base(ztext)
            if cloud:
                ctype, base = cloud
                reasons.append(f"BASE DAS NUVENS: {ctype} {base} ft")
                if base < 500:
                    limiting.append("Base das nuvens < 500 ft")

            if limiting:
                zones[z] = ("NO-GO", reasons, limiting)
            else:
                zones[z] = ("VFR POSSÍVEL", ["Sem limitações significativas"], [])

    # -------------------------------------------------
    # RESULTADOS TEXTO
    # -------------------------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons, limiting) in zones.items():

        if status == "NO-GO":
            st.error(f"{z}: NO-GO")
        else:
            st.success(f"{z}: VFR POSSÍVEL")

        for r in reasons:
            st.write(f" • {r}")
        if limiting:
            st.write(f" • Critério limitante: {limiting[0]}")

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
        status = zones[z][0]
        color = "green" if status == "VFR POSSÍVEL" else "red"
        ax.axhspan(y0, y1, color=color, alpha=0.25)

    # -------------------------------------------------
    # CIDADES (COMPLETO, DEFINITIVO)
    # -------------------------------------------------
    cities = {
        # NORTE
        "Bragança":         (0.8, 13.5),
        "Viana do Castelo": (0.2, 12.6),
        "Braga":            (0.4, 11.8),
        "Vila Real":        (0.6, 11.0),
        "Porto":            (0.3, 10.5),

        # CENTRO
        "Viseu":            (0.6, 8.6),
        "Aveiro":           (0.3, 8.0),
        "Guarda":           (0.8, 7.4),
        "Coimbra":          (0.5, 6.6),
        "Leiria":           (0.3, 5.6),
        "Castelo Branco":   (0.8, 5.9),

        # SUL
        "Santarém":         (0.4, 3.0),
        "Portalegre":       (0.8, 3.0),
        "Lisboa":           (0.3, 2.0),
        "Setúbal":          (0.3, 1.2),
        "Évora":            (0.6, 0.2),
        "Beja":             (0.7, -1.0),
        "Faro":             (0.7, -2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    # -------------------------------------------------
    # LEGENDA
    # -------------------------------------------------
    ax.legend(
        handles=[
            Patch(facecolor="red", alpha=0.25, label="🟥 NO-GO"),
            Patch(facecolor="green", alpha=0.25, label="🟩 VFR POSSÍVEL"),
            Line2D([0], [0], linestyle="--", color="black", label="Limite aproximado GAMET")
        ],
        loc="lower left",
        fontsize=8
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de decisão VFR")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")


