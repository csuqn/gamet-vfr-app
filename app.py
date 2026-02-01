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
# ZONAS (FAIXAS REAIS DE LATITUDE)
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

# -------------------------------------------------
# EXTRAÇÃO DE DETALHES
# -------------------------------------------------
def extract_details(text):
    details = {}

    vis = re.search(r"(\d{4})-(\d{4})M", text)
    if vis:
        details["VIS"] = f"{vis.group(1)}–{vis.group(2)} m"

    cld = re.search(r"(BKN|OVC)\s*(\d{3})-(\d{3})", text)
    if cld:
        details["CLD"] = f"{cld.group(1)} {cld.group(2)}–{cld.group(3)} ft AGL"

    ice = re.search(r"ICE.*?(ABV FL\d{2,3}|FL\d{2,3})", text)
    if ice:
        details["ICE"] = ice.group(1)

    return details

# -------------------------------------------------
# LÓGICA VFR
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    no_go = False

    vis = re.search(r"(\d{4})-(\d{4})M", text)
    if vis and int(vis.group(1)) < 3000:
        no_go = True
        reasons.append("VERY LOW VIS")

    if re.search(r"BKN 0{2,3}", text):
        no_go = True
        reasons.append("LOW CEILING")

    if no_go:
        return "NO-GO", reasons

    return "VFR POSSÍVEL", []

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------
if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    for z in PARTIAL_CUTS:
        PARTIAL_CUTS[z].clear()

    text = gamet_text.upper()
    zones = {}
    details = {}

    for z in ZONE_BANDS:
        ztext = filter_text_for_zone(text, z)
        zones[z] = analyze_zone(ztext)
        details[z] = extract_details(ztext)

    # -------------------------------
    # RESULTADOS TEXTO
    # -------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons) in zones.items():
        if status == "NO-GO":
            if PARTIAL_CUTS[z]:
                cut_dir, lat = PARTIAL_CUTS[z][0]
                st.error(f"{z}: NO-GO PARCIAL — {', '.join(reasons)}")
                st.write(f" • NO-GO a {'norte' if cut_dir=='NORTH' else 'sul'} de {lat:.1f}N")
                for k, v in details[z].items():
                    st.write(f"    – {k}: {v}")
                st.write(f" • VFR possível a {'sul' if cut_dir=='NORTH' else 'norte'} de {lat:.1f}N")
            else:
                st.error(f"{z}: NO-GO ABSOLUTO — {', '.join(reasons)}")
                for k, v in details[z].items():
                    st.write(f" • {k}: {v}")
        else:
            st.success(f"{z}: VFR possível")

    # -------------------------------------------------
    # MAPA ESQUEMÁTICO TOPOGRÁFICO COM CIDADES
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – Portugal Continental (esquemático)")

    fig, ax = plt.subplots(figsize=(6, 10))

    # Zonas para fundo
    ZONE_Y = {
        "NORTE": (8.5, 13.5),
        "CENTRO": (3.5, 8.5),
        "SUL": (-4.5, 3.5)
    }

    for z, (y0, y1) in ZONE_Y.items():
        status = zones[z][0]

        if status == "VFR POSSÍVEL":
            ax.axhspan(y0, y1, color="green", alpha=0.25)
        elif PARTIAL_CUTS[z]:
            mid = (y0 + y1) / 2
            ax.axhspan(mid, y1, color="red", alpha=0.25)
            ax.axhspan(y0, mid, color="green", alpha=0.25)
            ax.axhline(mid, linestyle="--", color="black")
        else:
            ax.axhspan(y0, y1, color="red", alpha=0.25)

    # Cidades (posições FIXAS) — VILA REAL CORRIGIDO
    cities = {
        # NORTE
        "Bragança":         (0.8, 13),
        "Viana do Castelo": (0.2, 12),
        "Braga":            (0.4, 11),
        "Vila Real":        (0.6, 10.5),  # <-- corrigido
        "Porto":            (0.3, 10),

        # CENTRO
        "Viseu":            (0.6, 8),
        "Guarda":           (0.8, 7),
        "Coimbra":          (0.5, 6),
        "Aveiro":           (0.3, 5),
        "Leiria":           (0.3, 4),
        "Castelo Branco":   (0.8, 3),

        # SUL
        "Santarém":         (0.4, 2),
        "Portalegre":       (0.8, 1),
        "Lisboa":           (0.3, 0),
        "Setúbal":          (0.3, -1),
        "Évora":            (0.6, -2),
        "Beja":             (0.7, -3),
        "Faro":             (0.7, -4),
    }

    for name, (x, y) in cities.items():
        ax.plot(x, y, "ko", markersize=3)
        ax.text(x + 0.015, y, name, va="center", fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_ylim(-4.5, 13.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Mapa esquemático de orientação (topológico)")

    st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")
