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
# GEOMETRIA BASE
# -------------------------------------------------
LAT_MIN = 36.5
LAT_MAX = 42.5
Y_MIN = -4.5
Y_MAX = 14.0

def lat_to_y(lat):
    return Y_MIN + (lat - LAT_MIN) * (Y_MAX - Y_MIN) / (LAT_MAX - LAT_MIN)

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
# AVALIAÇÃO GLOBAL (SIMPLIFICADA)
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

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    # CASO COM CORTE
    if cut and status == "VFR NO-GO":
        direction, lat = cut
        cut_y = lat_to_y(lat)

        if direction == "NORTH":
            # Norte NO-GO
            ax.axhspan(cut_y, Y_MAX, color="red", alpha=0.30)
            ax.text(0.02, (cut_y + Y_MAX) / 2, f"VFR NO-GO\n{reason}", fontsize=9, va="center")

            # Sul OK
            ax.axhspan(Y_MIN, cut_y, color="green", alpha=0.30)
            ax.text(0.02, (Y_MIN + cut_y) / 2, "VFR OK", fontsize=9, va="center")

        else:
            # Sul NO-GO
            ax.axhspan(Y_MIN, cut_y, color="red", alpha=0.30)
            ax.text(0.02, (Y_MIN + cut_y) / 2, f"VFR NO-GO\n{reason}", fontsize=9, va="center")

            # Norte OK
            ax.axhspan(cut_y, Y_MAX, color="green", alpha=0.30)
            ax.text(0.02, (cut_y + Y_MAX) / 2, "VFR OK", fontsize=9, va="center")

        ax.axhline(cut_y, linestyle="--", color="black")
        ax.text(0.75, cut_y + 0.1, f"{lat:.1f}N", fontsize=9)

    # CASO SEM CORTE
    else:
        color = "green" if status == "VFR OK" else "red"
        ax.axhspan(Y_MIN, Y_MAX, color=color, alpha=0.30)
        label = status if not reason else f"{status}\n{reason}"
        ax.text(0.02, (Y_MIN + Y_MAX) / 2, label, fontsize=9, va="center")

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
