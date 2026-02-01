import streamlit as st
import re
import matplotlib.pyplot as plt

# -------------------------------------------------
# CONFIGURAÇÃO
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
# GEOMETRIA BASE
# -------------------------------------------------
LAT_MIN = 36.5
LAT_MAX = 42.5
Y_MIN = -4.5
Y_MAX = 14.0

def lat_to_y(lat):
    return Y_MIN + (lat - LAT_MIN) * (Y_MAX - Y_MIN) / (LAT_MAX - LAT_MIN)

# -------------------------------------------------
# ZONAS (APENAS VISUAIS)
# -------------------------------------------------
ZONE_Y = {
    "NORTE": (9.0, 14.0),
    "CENTRO": (4.0, 9.0),
    "SUL": (-4.5, 4.0)
}

# -------------------------------------------------
# EXTRAÇÃO DO CORTE GLOBAL
# -------------------------------------------------
def extract_cut(text):
    m = re.search(r"N OF N(\d{2})(\d{2})", text)
    if m:
        return ("NORTH", int(m.group(1)) + int(m.group(2)) / 60)

    m = re.search(r"S OF N(\d{2})(\d{2})", text)
    if m:
        return ("SOUTH", int(m.group(1)) + int(m.group(2)) / 60)

    return None

# -------------------------------------------------
# LÓGICA VFR GLOBAL (SIMPLIFICADA)
# -------------------------------------------------
def analyze_global(text):
    if re.search(r"BKN\s*004", text):
        return "VFR NO-GO", ["BKN 400 ft"]
    return "VFR OK", []

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    text = gamet_text.upper()
    cut = extract_cut(text)
    status, reasons = analyze_global(text)

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    # Fundo base (NO-GO)
    ax.axhspan(Y_MIN, Y_MAX, color="red", alpha=0.25)

    # Corte global
    if cut and status == "VFR NO-GO":
        direction, lat = cut
        cut_y = lat_to_y(lat)

        if direction == "NORTH":
            # SUL é OK
            ax.axhspan(Y_MIN, cut_y, color="green", alpha=0.25)
        else:
            # NORTE é OK
            ax.axhspan(cut_y, Y_MAX, color="green", alpha=0.25)

        ax.axhline(cut_y, linestyle="--", color="black")
        ax.text(0.75, cut_y + 0.1, f"{lat:.1f}N", fontsize=9)

    # Rótulos das zonas
    for z, (y0, y1) in ZONE_Y.items():
        ax.text(
            0.02,
            (y0 + y1) / 2,
            status if not reasons else status + "\n" + "\n".join(reasons),
            fontsize=8,
            va="center"
        )

    # -------------------------------------------------
    # CIDADES
    # -------------------------------------------------
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
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")
