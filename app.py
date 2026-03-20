import streamlit as st
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union
from dataclasses import dataclass
from datetime import datetime, timezone

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

st.set_page_config(page_title="LPPC GAMET – VFR", layout="wide")
st.title("✈️ LPPC GAMET – Motor Cartográfico v11.0")

gamet_text = st.text_area("Cole aqui o texto completo do GAMET (LPPC)", height=300)

# -------------------------------------------------
# SECTORES
# -------------------------------------------------

SECTOR_NORTE = Polygon([
    (-8.843611, 41.867500), (-6.850000, 41.900000),
    (-6.621944, 41.700556), (-6.818333, 40.399444),
    (-8.016667, 39.383333), (-10.000000, 38.900000),
    (-9.784722, 39.348611), (-9.442500, 40.199722),
    (-9.368056, 40.382222), (-9.250000, 40.648889),
    (-9.186389, 40.827778),
]).buffer(0)

SECTOR_CENTRO = Polygon([
    (-6.818333, 40.399444), (-7.230000, 37.999444),
    (-9.000000, 38.000000), (-10.000000, 38.000000),
    (-10.000000, 38.900000), (-8.016667, 39.383333),
]).buffer(0)

SECTOR_SUL = Polygon([
    (-7.230000, 37.999444), (-7.383333, 35.966667),
    (-10.733333, 35.966667), (-9.000000, 38.000000),
]).buffer(0)

ZONES = {
    "SECTOR NORTE": SECTOR_NORTE,
    "SECTOR CENTRO": SECTOR_CENTRO,
    "SECTOR SUL": SECTOR_SUL,
}

FIR_POLYGON = unary_union(list(ZONES.values()))
FIR_MINX, FIR_MINY, FIR_MAXX, FIR_MAXY = FIR_POLYGON.bounds

# -------------------------------------------------
# CIDADES
# -------------------------------------------------

CITIES = {
    "Bragança":          (41.806, -6.756),
    "Viana do Castelo":  (41.693, -8.832),
    "Braga":             (41.545, -8.426),
    "Vila Real":         (41.300, -7.744),
    "Porto":             (41.149, -8.610),
    "Viseu":             (40.661, -7.909),
    "Aveiro":            (40.640, -8.653),
    "Guarda":            (40.537, -7.267),
    "Coimbra":           (40.203, -8.410),
    "Leiria":            (39.744, -8.807),
    "Castelo Branco":    (39.823, -7.493),
    "Santarém":          (39.236, -8.686),
    "Portalegre":        (39.292, -7.428),
    "Lisboa":            (38.722, -9.139),
    "Setúbal":           (38.524, -8.888),
    "Évora":             (38.571, -7.913),
    "Beja":              (38.015, -7.863),
    "Faro":              (37.019, -7.930),
}

# -------------------------------------------------
# DATA MODEL
# -------------------------------------------------

@dataclass
class MetBlock:
    phenomenon: str
    polygon: object
    value: object
    qualifier: str = ""   # LCA, EMBD, etc.
    layer: str = ""       # SFC/FL050, ABV FL070, etc.

# -------------------------------------------------
# NORMALIZE
# -------------------------------------------------

def normalize(text):
    text = text.upper()
    text = text.replace("–", "-").replace("\r\n", "\n").replace("\r", "\n")
    return text

# -------------------------------------------------
# VALIDADE
# -------------------------------------------------

def parse_validity(text):
    """Extrai período de validade e verifica se está ativo."""
    m = re.search(r"VALID\s+(\d{2})(\d{2})(\d{2})/(\d{2})(\d{2})(\d{2})", text)
    if not m:
        return None, None, False
    day_s, hh_s, mm_s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day_e, hh_e, mm_e = int(m.group(4)), int(m.group(5)), int(m.group(6))
    now = datetime.now(timezone.utc)
    # Constrói datetimes no mês/ano corrente
    try:
        start = now.replace(day=day_s, hour=hh_s, minute=mm_s, second=0, microsecond=0)
        end   = now.replace(day=day_e, hour=hh_e, minute=mm_e, second=0, microsecond=0)
        active = start <= now <= end
        return start, end, active
    except Exception:
        return None, None, False

# -------------------------------------------------
# GEO
# -------------------------------------------------

def extract_polygon(line):
    poly = FIR_POLYGON
    geo_found = False

    for m in re.findall(r"BTN\s+N(\d{2})(\d{2})\s+AND\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat1 = int(m[0]) + int(m[1]) / 60
        lat2 = int(m[2]) + int(m[3]) / 60
        poly = poly.intersection(box(FIR_MINX, min(lat1, lat2), FIR_MAXX, max(lat1, lat2)))

    for m in re.findall(r"N\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        poly = poly.intersection(box(FIR_MINX, lat, FIR_MAXX, FIR_MAXY))

    for m in re.findall(r"S\s+OF\s+N(\d{2})(\d{2})", line):
        geo_found = True
        lat = int(m[0]) + int(m[1]) / 60
        poly = poly.intersection(box(FIR_MINX, FIR_MINY, FIR_MAXX, lat))

    return poly if geo_found else None

# -------------------------------------------------
# PARSER — v11 (corrigido)
# -------------------------------------------------

# Palavras-chave que NÃO devem ser confundidas com visibilidade ou altitude
_FL_PATTERN = re.compile(r"FL\d{2,3}")          # FL050, FL100, FL150 …
_HPA_PATTERN = re.compile(r"\d+\s*HPA")         # 986HPA, 1005HPA …

_TS_DISPLAY = {
    "ISOL_EMBD": "ISOL/EMBD",
}

def _ts_label(val):
    return _TS_DISPLAY.get(val, val)

def parse_gamet(text):

    text = normalize(text)

    # ---- Separar Secções I e II ----
    secn_split = re.split(r"SECN\s+II", text, maxsplit=1)
    secn1 = secn_split[0]
    # Secção II guardada para extração futura (vento, FZLVL, QNH)
    secn2 = secn_split[1] if len(secn_split) > 1 else ""

    # ---- Injetar quebras antes de campos conhecidos ----
    secn1 = re.sub(r"(SECN\s+I\b)", r"\n\1\n", secn1)
    secn1 = re.sub(r"(SFC\s+VIS|VIS\s*:)", r"\n\1", secn1)
    secn1 = re.sub(r"(SIG\s+CLD|CLD\s*:)", r"\n\1", secn1)
    secn1 = re.sub(r"(SIGWX\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(TURB\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(\bICE\b\s*:?)", r"\n\1", secn1)
    secn1 = re.sub(r"(SIGMET\s+APPLICABLE)", r"\n\1", secn1)

    lines = [l.strip() for l in secn1.splitlines() if l.strip()]

    state = "IDLE"
    blocks = []
    current_polygon = FIR_POLYGON

    for raw_line in lines:

        line = raw_line.strip()
        if not line:
            continue

        # Ignorar linha SIGMET APPLICABLE
        if line.startswith("SIGMET"):
            state = "IDLE"
            continue

        # ---- Detetar mudança de estado ----
        new_state = None
        if re.match(r"SFC\s+VIS|VIS\s*:", line):
            new_state = "VIS"
        elif re.match(r"SIG\s+CLD|CLD\s*:", line):
            new_state = "CLD"
        elif re.match(r"SIGWX", line):
            new_state = "SIGWX"
        elif re.match(r"TURB", line):
            new_state = "TURB"
        elif re.match(r"ICE", line):
            new_state = "ICE"
        elif re.match(r"SECN\s+I\b", line):
            state = "IDLE"
            current_polygon = FIR_POLYGON
            continue

        if new_state:
            state = new_state
            # Remover a keyword da linha para processar só o conteúdo
            content = re.sub(
                r"^(SFC\s+VIS\s*:?|VIS\s*:|SIG\s+CLD\s*:?|CLD\s*:|SIGWX\s*:?|TURB\s*:?|ICE\s*:?)\s*",
                "", line
            ).strip()
        else:
            content = line

        if state == "IDLE":
            continue

        # ---- Contexto geográfico ----
        new_poly = extract_polygon(line)
        if new_poly is not None and not new_poly.is_empty:
            current_polygon = new_poly

        poly = current_polygon

        # ---- Qualificador local ----
        qualifier = ""
        if re.search(r"\bLCA\b", content):
            qualifier = "LCA"

        # ---- PARSE por estado ----

        if state == "VIS":
            # FIX: ignorar FL\d+ e HPA ao procurar metros de visibilidade
            # Remove tokens FL### e ###HPA antes de procurar metros
            vis_content = _FL_PATTERN.sub("", content)
            vis_content = _HPA_PATTERN.sub("", vis_content)

            # Captura KM (ex: 2.5KM → 2500m)
            for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*KM\b", vis_content):
                val = int(float(m.group(1)) * 1000)
                blocks.append(MetBlock("VIS", poly, val, qualifier))

            # Captura metros (3-4 dígitos seguidos de M)
            # Exige que NÃO seja precedido de HFT ou FL
            for m in re.finditer(r"(?<!\d)(\d{3,4})M\b", vis_content):
                val = int(m.group(1))
                # Sanity check: visibilidade plausível (100m a 9999m)
                if 100 <= val <= 9999:
                    blocks.append(MetBlock("VIS", poly, val, qualifier))

        elif state == "CLD":
            # FIX CRÍTICO: suporta formato "015-030/XXXHFT AGL" e "015HFT AGL"
            # Padrão: BASE[-TOPO[/TOPO2]]HFT AGL
            for m in re.finditer(
                r"\b(\d{3})-(\d{3})(?:/[A-Z]+)?HFT\s+AGL\b",
                content
            ):
                base_ft = int(m.group(1)) * 100
                blocks.append(MetBlock("BASE_AGL", poly, base_ft, qualifier))

            # Base única sem range (ex: 030HFT AGL)
            for m in re.finditer(r"\b(\d{3})HFT\s+AGL\b", content):
                # Verificar que não faz parte de um range já capturado
                pos = m.start()
                before = content[max(0, pos-4):pos]
                if "-" not in before:
                    base_ft = int(m.group(1)) * 100
                    blocks.append(MetBlock("BASE_AGL", poly, base_ft, qualifier))

        elif state == "SIGWX":
            # FIX: EMBD tratado separadamente e eleva risco
            embd = bool(re.search(r"\bEMBD\b", content))
            ts_qualifier = ""

            if "FRQ" in content:
                ts_qualifier = "FRQ"
            elif "OCNL" in content:
                ts_qualifier = "OCNL"
            elif "ISOL" in content:
                ts_qualifier = "ISOL"

            if "TS" in content or "CB" in content:
                # EMBD eleva: ISOL/EMBD → tratado como OCNL para decisão
                if embd and ts_qualifier == "ISOL":
                    ts_qualifier = "ISOL_EMBD"
                elif embd and not ts_qualifier:
                    ts_qualifier = "EMBD"
                elif not ts_qualifier:
                    ts_qualifier = "GEN"
                blocks.append(MetBlock("TS", poly, ts_qualifier, qualifier))

        elif state == "TURB":
            # FIX: captura camada vertical
            layer = ""
            layer_m = re.search(r"(SFC/FL\d+|FL\d+/FL\d+|SFC/\d+FT|ABV\s+FL\d+)", content)
            if layer_m:
                layer = layer_m.group(1)

            if "SEV" in content:
                severity = "SEV"
            elif "MOD" in content:
                severity = "MOD"
            else:
                severity = None

            if severity:
                blocks.append(MetBlock("TURB", poly, severity, qualifier, layer))

        elif state == "ICE":
            # FIX: captura nível de gelo
            layer = ""
            layer_m = re.search(r"(ABV\s+FL\d+|FL\d+/FL\d+|SFC/FL\d+)", content)
            if layer_m:
                layer = layer_m.group(1)

            if "SEV" in content:
                severity = "SEV"
            elif "MOD" in content:
                severity = "MOD"
            else:
                severity = None

            if severity:
                blocks.append(MetBlock("ICE", poly, severity, qualifier, layer))

    # ---- Extração Secção II: FZLVL e QNH mínimo ----
    fzlvl_values = [int(m) for m in re.findall(r"(\d{4,5})FT\s+AMSL", secn2)]
    fzlvl_min = min(fzlvl_values) if fzlvl_values else None

    qnh_m = re.search(r"MNM\s+QNH\s*:?\s*(\d{3,4})\s*HPA", secn2)
    qnh_min = int(qnh_m.group(1)) if qnh_m else None

    return blocks, fzlvl_min, qnh_min

# -------------------------------------------------
# BUILD
# -------------------------------------------------

def build_zone_data(blocks, threshold=0.15):
    zone_data = {z: [] for z in ZONES}

    for block in blocks:
        if block.polygon is None or block.polygon.is_empty:
            continue
        for zone, poly in ZONES.items():
            inter = poly.intersection(block.polygon)
            if inter.is_empty:
                continue
            coverage = inter.area / poly.area
            if coverage < threshold:
                continue
            if block.phenomenon == "BASE_AGL":
                zone_data[zone].append(("BASE", block.value, block.qualifier, block.layer))
            else:
                zone_data[zone].append((block.phenomenon, block.value, block.qualifier, block.layer))

    return zone_data

# -------------------------------------------------
# DECISION — v11 (TS penalizado, LCA contextualizado)
# -------------------------------------------------

# Hierarquia de risco TS (do mais grave para o menos grave)
TS_RISK = {
    "FRQ":       3,   # NO-GO
    "EMBD":      3,   # NO-GO
    "ISOL_EMBD": 2,   # NO-GO (ISOL mas embutida — imprevisível)
    "OCNL":      2,   # NO-GO
    "ISOL":      1,   # MARGINAL
    "GEN":       2,   # NO-GO (genérico sem qualificador — conservador)
}

def decision(events):
    vis_vals  = [v for t, v, *_ in events if t == "VIS"]
    base_vals = [v for t, v, *_ in events if t == "BASE"]
    ts_vals   = [v for t, v, *_ in events if t == "TS"]
    turb_vals = [v for t, v, *_ in events if t == "TURB"]
    ice_vals  = [v for t, v, *_ in events if t == "ICE"]

    # Separar LCA (local) do geral
    vis_lca  = [v for t, v, q, *_ in events if t == "VIS" and q == "LCA"]
    vis_gen  = [v for t, v, q, *_ in events if t == "VIS" and q != "LCA"]

    vis  = min(vis_vals)  if vis_vals  else None
    base = min(base_vals) if base_vals else None

    # Nível máximo de risco TS
    ts_max_risk = max((TS_RISK.get(v, 1) for v in ts_vals), default=0)

    reasons = []
    decision_level = "GO"

    # ---- Visibilidade ----
    # LCA não força NO-GO geral, mas é registada como aviso
    if vis_gen and min(vis_gen) < 1500:
        decision_level = "NO-GO"
        reasons.append(f"VIS {min(vis_gen)}m < 1500m")
    elif vis_lca and min(vis_lca) < 1500:
        # VIS local abaixo mínimo → MARGINAL (não NO-GO de área)
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"VIS LCA {min(vis_lca)}m < 1500m (local)")
    elif vis and vis < 3000:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        lca_note = " (LCA)" if vis_lca and vis in vis_lca else ""
        reasons.append(f"VIS{lca_note} {vis}m < 3000m")

    # ---- Base de nuvens ----
    if base is not None and base < 300:
        decision_level = "NO-GO"
        reasons.append(f"BASE {base}ft < 300ft")
    elif base is not None and base < 500:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"BASE {base}ft < 500ft")

    # ---- Trovoadas — FIX CRÍTICO ----
    if ts_max_risk >= 2:
        decision_level = "NO-GO"
        reasons.append(f"TS {'/'.join(ts_vals)} (risco alto)")
    elif ts_max_risk == 1:
        if decision_level == "GO":
            decision_level = "MARGINAL"
        reasons.append(f"TS {'/'.join(ts_vals)} (ISOL)")

    return decision_level, vis, base, ts_vals, turb_vals, ice_vals, reasons

# -------------------------------------------------
# EXECUÇÃO
# -------------------------------------------------

if st.button("🔍 Analisar GAMET") and gamet_text.strip():

    # ---- Validade ----
    start_dt, end_dt, active = parse_validity(gamet_text)
    if start_dt and end_dt:
        fmt = "%d/%H%MZ"
        label = f"⏱️ Válido: {start_dt.strftime(fmt)} – {end_dt.strftime(fmt)}"
        if active:
            st.success(label + " ✅ Em vigor")
        else:
            st.warning(label + " ⚠️ FORA DO PERÍODO DE VALIDADE — dados podem estar desatualizados")

    blocks, fzlvl_min, qnh_min = parse_gamet(gamet_text)
    zone_data  = build_zone_data(blocks)
    results    = {z: decision(zone_data[z]) for z in ZONES}

    # ---- Briefing ----
    st.subheader("📋 Briefing")
    cols = st.columns(3)

    for i, z in enumerate(ZONES):
        dec, vis, base, ts, turb, ice, reasons = results[z]

        with cols[i]:
            st.markdown(f"### {z}")

            if dec == "NO-GO":
                st.error("🔴 NO-GO")
            elif dec == "MARGINAL":
                st.warning("⚠️ MARGINAL")
            else:
                st.success("✅ GO")

            st.write(f"👁️ VIS: {vis} m"             if vis  is not None else "👁️ VIS: —")
            st.write(f"☁️ BASE: {base} ft AGL"       if base is not None else "☁️ BASE: —")
            st.write(f"⛈️ TS: {', '.join(_ts_label(v) for v in ts)}"   if ts   else "⛈️ TS: —")
            st.write(f"🌪 TURB: {', '.join(turb)}"   if turb else "🌪 TURB: —")
            st.write(f"❄ ICE: {', '.join(ice)}"      if ice  else "❄ ICE: —")

            if reasons:
                with st.expander("ℹ️ Motivos da decisão"):
                    for r in reasons:
                        st.write(f"• {r}")

    # ---- Informação Secção II ----
    if fzlvl_min or qnh_min:
        st.subheader("🌡️ Dados Adicionais (Secção II)")
        c1, c2 = st.columns(2)
        with c1:
            if fzlvl_min:
                st.info(f"🧊 Nível de gelo mínimo (FZLVL): **{fzlvl_min} ft AMSL**")
        with c2:
            if qnh_min:
                st.info(f"🌡️ QNH mínimo: **{qnh_min} hPa**")

    # ---- Legenda ----
    with st.expander("📖 Legenda do Briefing", expanded=False):
        st.markdown("""
**Decisão VFR:**
- 🟢 GO – Condições VFR aceitáveis
- 🟠 MARGINAL – Próximo dos mínimos (precaução)
- 🔴 NO-GO – Abaixo dos mínimos ou TS de risco alto

**Campos:**
- 👁️ VIS – Visibilidade (m); LCA = condição localizada
- ☁️ BASE – Base de nuvens significativas (ft AGL)
- ⛈️ TS – Trovoadas: ISOL (isolada) / OCNL / FRQ / EMBD (embutida)
- 🌪 TURB – Turbulência: MOD / SEV
- ❄ ICE – Gelo: MOD / SEV

**Regras de decisão TS:**
- ISOL → MARGINAL
- OCNL / GEN / ISOL_EMBD / EMBD / FRQ → NO-GO
""")

    # ---- Mapa ----
    st.subheader("🌍 Mapa")
    fig, ax = plt.subplots(figsize=(7, 10))
    colors = {"GO": "green", "MARGINAL": "orange", "NO-GO": "red"}

    for z, poly in ZONES.items():
        dec = results[z][0]
        geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        for g in geoms:
            x, y = g.exterior.xy
            ax.fill(x, y, alpha=0.3, color=colors[dec])
            ax.plot(x, y, color=colors[dec], linewidth=1)

    for name, (lat, lon) in CITIES.items():
        ax.plot(lon, lat, "ko", markersize=4)
        ax.text(lon + 0.05, lat, name, fontsize=8)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(handles=[
        Patch(facecolor="green",  alpha=0.3, label="GO"),
        Patch(facecolor="orange", alpha=0.3, label="MARGINAL"),
        Patch(facecolor="red",    alpha=0.3, label="NO-GO"),
        Line2D([0], [0], marker="o", color="black", linestyle="None", label="Cidade"),
    ])

    st.pyplot(fig)
