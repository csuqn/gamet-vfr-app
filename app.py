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
# ZONAS (LATITUDES APROXIMADAS)
# -------------------------------------------------
ZONE_BANDS = {
    "NORTE": (39.5, 42.5),
    "CENTRO": (38.5, 39.5),
    "SUL": (36.5, 38.5)
}

PARTIAL_CUTS = {z: [] for z in ZONE_BANDS}

# -------------------------------------------------
# FUNÇÕES ESPACIAIS (INALTERADAS)
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
# PARSING ROBUSTO
# -------------------------------------------------
def extract_visibility(text):
    values = []

    # 0800-5000M
    for m in re.findall(r"(\d{4})-(\d{4})M", text):
        values.append(int(m[0]))

    # VIS 3000M
    for m in re.findall(r"VIS\s*(\d{4})M", text):
        values.append(int(m))

    return min(values) if values else None


def extract_ceiling(text):
    bases = []

    for m in re.findall(r"(BKN|OVC)\s*(\d{3})", text):
        bases.append(int(m[1]) * 100)

    return min(bases) if bases else None

# -------------------------------------------------
# LÓGICA VFR MELHORADA
# -------------------------------------------------
def analyze_zone(text):
    reasons = []
    status = "VFR OK"

    vis = extract_visibility(text)
    cld = extract_ceiling(text)

    # VIS
    if vis is not None:
        if vis < 3000:
            return "VFR NO-GO", [f"VIS {vis} m"]
        elif vis < 5000:
            status = "VFR MARGINAL"
            reasons.append(f"VIS {vis} m")
        else:
            reasons.append("VIS ≥ 5000 m")

    # CEILING
    if cld is not None:
        if cld < 500:
            return "VFR NO-GO", [f"CEILING {cld} ft"]
        elif cld < 1500:
            status = "VFR MARGINAL"
            reasons.append(f"CEILING {cld} ft")
        else:
            reasons.append(f"CEILING {cld} ft")

    return status, reasons

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
    # RESULTADOS TEXTO (MELHORADOS)
    # -------------------------------------------------
    st.subheader("📋 Resultado VFR por zona")

    for z, (status, reasons) in zones.items():
        if status == "VFR NO-GO":
            st.error(f"{z}: {status}")
        elif status == "VFR MARGINAL":
            st.warning(f"{z}: {status}")
        else:
            st.success(f"{z}: {status}")

        for r in reasons:
            st.write(f" • {r}")

    # -------------------------------------------------
    # MAPA (INTACTO)
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

        if status == "VFR OK":
            ax.axhspan(y0, y1, color="green", alpha=0.25)
        elif status == "VFR MARGINAL":
            ax.axhspan(y0, y1, color="yellow", alpha=0.35)
        else:
            ax.axhspan(y0, y1, color="red", alpha=0.25)

    # CIDADES (INALTERADAS)
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
