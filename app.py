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

# -------------------------------------------------
# ESCALA GEOGRÁFICA REAL
# -------------------------------------------------
LAT_MIN = 36.5
LAT_MAX = 42.5
Y_MIN = -4.5
Y_MAX = 14.0

def lat_to_y(lat):
    return Y_MIN + (lat - LAT_MIN) * (Y_MAX - Y_MIN) / (LAT_MAX - LAT_MIN)

# -------------------------------------------------
# CIDADES (LATITUDE REAL)
# -------------------------------------------------
CITIES = {
    "Bragança": (0.75, 41.81),
    "Porto":    (0.30, 41.15),
    "Coimbra":  (0.50, 40.21),
    "Lisboa":   (0.30, 38.72),
    "Faro":     (0.70, 37.02),
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
# ANÁLISE GLOBAL (SIMPLIFICADA)
# -------------------------------------------------
def analyze(text):
    if re.search(r"BKN\s*004", text):
        return "VFR NO-GO", "BKN 400 ft"
    return "VFR OK", None

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    text = gamet_text.upper()
    cut = extract_cut(text)
    status, reason = analyze(text)

    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    # -----------------------------
    # DESENHO DAS ÁREAS
    # -----------------------------
    if cut and status == "VFR NO-GO":
        direction, lat = cut
        cut_y = lat_to_y(lat)

        if direction == "NORTH":
            ax.axhspan(cut_y, Y_MAX, color="red", alpha=0.30)
            ax.text(0.02, (cut_y + Y_MAX) / 2, f"VFR NO-GO\n{reason}", fontsize=9, va="center")

            ax.axhspan(Y_MIN, cut_y, color="green", alpha=0.30)
            ax.text(0.02, (Y_MIN + cut_y) / 2, "VFR OK", fontsize=9, va="center")

        else:
            ax.axhspan(Y_MIN, cut_y, color="red", alpha=0.30)
            ax.text(0.02, (Y_MIN + cut_y) / 2, f"VFR NO-GO\n{reason}", fontsize=9, va="center")

            ax.axhspan(cut_y, Y_MAX, color="green", alpha=0.30)
            ax.text(0.02, (cut_y + Y_MAX) / 2, "VFR OK", fontsize=9, va="center")

        ax.axhline(cut_y, linestyle="--", color="black")
        ax.text(0.78, cut_y + 0.1, f"{lat:.1f}N", fontsize=9)

    else:
        color = "green" if status == "VFR OK" else "red"
        ax.axhspan(Y_MIN, Y_MAX, color=color, alpha=0.30)

    # -----------------------------
    # CIDADES (AGORA COERENTES)
    # -----------------------------
    for name, (x, lat) in CITIES.items():
        y = lat_to_y(lat)
        ax.plot(x, y, "ko", markersize=4)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")
