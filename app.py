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

# -------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------
def lat_to_y(lat):
    # 36.5N → -4.5 | 42.5N → 14.0
    return -4.5 + (lat - 36.5) * (18.5 / 6.0)


def extract_global_cut(text):
    """
    Procura cortes do tipo N OF N3700 / S OF N3700
    Assume que o GAMET é coerente e devolve o mais restritivo.
    """
    north_of = re.findall(r"N OF N(\d{2})(\d{2})", text)
    south_of = re.findall(r"S OF N(\d{2})(\d{2})", text)

    if north_of:
        deg, minu = north_of[0]
        return ("NORTH", int(deg) + int(minu) / 60)

    if south_of:
        deg, minu = south_of[0]
        return ("SOUTH", int(deg) + int(minu) / 60)

    return None

# -------------------------------------------------
# LÓGICA VFR
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    status = "VFR OK"

    vis_matches = re.findall(r"(\d{4})M", text)
    if vis_matches:
        min_vis = min(int(v) for v in vis_matches)
        if min_vis < 3000:
            return "VFR NO-GO", [f"VIS {min_vis} m"]
        elif min_vis < 5000:
            status = "VFR MARGINAL"
            reasons.append(f"VIS {min_vis} m")

    cld = re.search(r"(BKN|OVC)[ /]*(\d{3})", text)
    if cld:
        base_ft = int(cld.group(2)) * 100
        if base_ft < 500:
            return "VFR NO-GO", [f"{cld.group(1)} {base_ft} ft"]
        elif base_ft < 1500:
            status = "VFR MARGINAL"
            reasons.append(f"{cld.group(1)} {base_ft} ft")

    return status, reasons

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    text = gamet_text.upper()

    # Corte global
    global_cut = extract_global_cut(text)

    zones = {}
    for z, (zmin, zmax) in ZONE_BANDS.items():
        ztext = text  # GAMET completo (o corte é tratado globalmente)
        zones[z] = analyze_zone(ztext)

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    ZONE_Y = {
        "NORTE": (9.0, 14.0),
        "CENTRO": (4.0, 9.0),
        "SUL": (-4.5, 4.0)
    }

    # Desenho das zonas
    for z, (y0, y1) in ZONE_Y.items():
        status, reasons = zones[z]

        if status == "VFR OK":
            ax.axhspan(y0, y1, color="green", alpha=0.25)
        elif status == "VFR MARGINAL":
            ax.axhspan(y0, y1, color="yellow", alpha=0.35)
        else:
            ax.axhspan(y0, y1, color="red", alpha=0.25)

        if show_reasons:
            label = status if not reasons else status + "\n" + "\n".join(reasons)
            ax.text(0.02, (y0 + y1) / 2, label, fontsize=8, va="center")

    # Linha global
    if global_cut:
        _, lat = global_cut
        y = lat_to_y(lat)
        ax.axhline(y, linestyle="--", color="black")
        ax.text(0.75, y + 0.1, f"{lat:.1f}N", fontsize=8)

    # CIDADES
    cities = {
        "Bragança": (0.8, 13.5),
        "Porto": (0.3, 10.5),
        "Coimbra": (0.5, 6.6),
        "Lisboa": (0.3, 2.0),
        "Faro": (0.7, -2.2),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 14.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")

