import streamlit as st
import re
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# -------------------------------------------------
# CONFIG
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
# ZONAS (FAIXAS DE LATITUDE)
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
    # MAPA
    # -------------------------------------------------
    st.subheader("🗺️ Mapa VFR – LPPC (esquemático)")

fig, ax = plt.subplots(figsize=(5, 8))

# Zonas esquemáticas (alturas iguais)
SCHEMATIC_BANDS = {
    "NORTE": (2, 3),
    "CENTRO": (1, 2),
    "SUL": (0, 1)
}

for z, (y0, y1) in SCHEMATIC_BANDS.items():
    status = zones[z][0]

    # Zona sem corte
    if status == "VFR POSSÍVEL":
        ax.axhspan(y0, y1, color="green", alpha=0.35)

    elif PARTIAL_CUTS[z]:
        cut_dir, lat = PARTIAL_CUTS[z][0]

        if cut_dir == "NORTH":
            ax.axhspan(y0 + 0.5, y1, color="red", alpha=0.35)
            ax.axhspan(y0, y0 + 0.5, color="green", alpha=0.35)
            ax.axhline(y0 + 0.5, linestyle="--", color="black")
        else:
            ax.axhspan(y0, y0 + 0.5, color="red", alpha=0.35)
            ax.axhspan(y0 + 0.5, y1, color="green", alpha=0.35)
            ax.axhline(y0 + 0.5, linestyle="--", color="black")

    else:
        ax.axhspan(y0, y1, color="red", alpha=0.35)

# Rótulos
ax.text(0.5, 2.5, "NORTE", ha="center", va="center", fontsize=12)
ax.text(0.5, 1.5, "CENTRO", ha="center", va="center", fontsize=12)
ax.text(0.5, 0.5, "SUL", ha="center", va="center", fontsize=12)

ax.set_xlim(0, 1)
ax.set_ylim(0, 3)
ax.set_xticks([])
ax.set_yticks([])

ax.set_title("VFR por zonas – Portugal Continental")

st.pyplot(fig)

    st.caption("Ferramenta de apoio à decisão. Não substitui o julgamento do piloto.")

