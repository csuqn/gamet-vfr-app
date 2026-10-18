"""
LPPC GAMET — protótipo da interface em NiceGUI.

Corre em paralelo com a app Streamlit (app.py), que continua a ser a app
publicada. O motor é o MESMO (ver motor.py); aqui só muda a interface.

    pip install -r nicegui_app/requirements.txt
    python nicegui_app/main.py          # http://localhost:8080
"""
import json
import os
import re
from datetime import datetime, timezone

from nicegui import app, run, ui

from motor import M, APP

_SRC = APP.read_text(encoding="utf-8")
# O mesmo CSS e a mesma legenda da app Streamlit (uma só fonte)
_CSS = re.search(r'_CSS = """\n<style>\n(.*?)</style>\n"""', _SRC, re.S).group(1)
_LEGENDA = re.search(r'st\.markdown\("""\n(### 📐 Referência técnica.*?)"""\)', _SRC, re.S).group(1)

_EXTRA_CSS = """
body { background:#0E151C; color:#E6EDF3; }
.nicegui-content { max-width: 1100px; margin: 0 auto; padding: 12px 16px 48px; gap: 10px; }
.gv-alerta { border-radius:12px; padding:12px 14px; font-size:14px; line-height:1.5; border:1px solid; }
.gv-alerta code { white-space: pre-wrap; word-break: break-word; font-size:12px; }
.gv-erro  { background:#3A1414; border-color:#7A2A26; color:#FBD5D1; }
.gv-aviso { background:#3D3110; border-color:#7A6420; color:#F8E4B0; }
.gv-info  { background:#16314A; border-color:#2C5A82; color:#D3E8FA; }
.gv-sec { font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.1em; color:#8FA3B5;
          font-weight:600; margin-top:8px; }
.q-tab { min-height: 44px; }
.q-tabs { border-bottom: 1px solid #22303C; }
.gv-txt { font-family:'IBM Plex Mono',monospace; font-size:12.5px; white-space:pre-wrap;
          word-break:break-word; background:#15202A; border:1px solid #22303C; border-radius:12px; padding:12px; }
.q-field__native, .q-field__input { color:#E6EDF3 !important; }
.leaflet-tooltip.gv-lbl { background: rgba(14,21,28,.85); color:#E6EDF3; border:0; box-shadow:none;
  font-family:'IBM Plex Mono',monospace; font-size:10px; padding:0 4px; border-radius:3px; }
.leaflet-tooltip.gv-lbl::before { display:none; }
"""


def _md(txt):
    """**negrito** e `código` → HTML (o resto escapado)."""
    t = M._e(txt)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t.replace("\n", "<br>")


# ---------------------------------------------------------------------
# Análise — a mesma função do motor que a app Streamlit usa
# (analisar_gamet, em app.py). Aqui só se desenha o resultado.
# ---------------------------------------------------------------------
def analisar(texto, fonte, boletins=None, boletins_at=None, boletins_fonte="",
             indice=None, entrada=None, boletins_arquivo=None):
    return M.analisar_gamet(texto, fonte, boletins, boletins_at, boletins_fonte,
                            indice, entrada, boletins_arquivo=boletins_arquivo)


def _boletins_arquivo_recentes():
    """SIGMETs arquivados nas últimas 24 h (incl. expirados), para saber se um
    SIGMET referido no GAMET já terminou. Sem arquivo → None."""
    try:
        ok, idx = M.fetch_arquivo_indice()
        return M.boletins_arquivados(idx, datetime.now(timezone.utc)) if ok else None
    except Exception:  # noqa: BLE001
        return None


def obter_gamet_actual():
    """IPMA; se não houver GAMET publicado, o último em vigor do arquivo."""
    ok, res = M.fetch_gamet_ipma("")
    if ok:
        return dict(texto=res, fonte="ipma",
                    boletins=M.extract_bulletins_from_html(M._IPMA_LAST["raw"]),
                    boletins_at=M._IPMA_LAST["at"], boletins_fonte="página do IPMA", erro=None,
                    arquivo=_boletins_arquivo_recentes())
    pagina = M.extract_bulletins_from_html(M._IPMA_LAST["sem_gamet"])
    txt, info, arq = M.gamet_de_recurso(M.fetch_arquivo_indice, M.fetch_arquivo)
    if txt:
        return dict(texto=txt, fonte="arquivo_recurso", boletins=arq + [b for b in pagina if b not in arq],
                    boletins_at=datetime.now(timezone.utc),
                    boletins_fonte="página do IPMA + arquivo" if pagina else "arquivo", erro=res,
                    arquivo=arq)
    return dict(texto="", fonte=None, boletins=None, boletins_at=None, boletins_fonte="",
                erro=f"{res}\n\nArquivo: {info}.")


# ---------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------
@ui.page("/")
async def pagina():
    ui.add_head_html('<meta name="theme-color" content="#0E151C">'
                     f"<style>{_CSS}{_EXTRA_CSS}</style>")
    ui.dark_mode(True)
    ui.colors(primary="#7CC4FF", dark="#0E151C", dark_page="#0E151C")

    estado = {"aerodromo": app.storage.user.get("aerodromo") if _STORAGE else None}

    ui.html('<div class="gv-head"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
            'stroke="#7CC4FF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M2 16l20-6-20-6 4 6-4 6z"></path><path d="M6 10h8"></path></svg>'
            f'<div><b>LPPC GAMET</b><small>BRIEFING VFR · v{M.APP_VERSION}</small></div></div>'
            ).classes("w-full")

    briefing = ui.column().classes("w-full gap-3")
    with briefing:
        ui.spinner(size="lg", color="primary")
        ui.label("A carregar o GAMET…").classes("gv-k")

    def desenhar(r):
        briefing.clear()
        with briefing:
            ui.html(M.html_faixa(r["faixa_val"], r["faixa_exp"], *r["faixa_sig"])).classes("w-full")
            for tipo, txt in r["avisos"]:
                if tipo == "ok":
                    ui.html(f'<div class="gv-k" style="font-size:12px">{_md(txt)}</div>').classes("w-full")
                else:
                    ui.html(f'<div class="gv-alerta gv-{tipo}">{_md(txt)}</div>').classes("w-full")
            ui.html(M.html_veredicto(r["por_dec"], r["area"])).classes("w-full")

            opcoes = sorted(M.AERODROMES.keys())
            res_ad = ui.html("").classes("w-full")

            def mostrar_ad(nome):
                estado["aerodromo"] = nome
                if _STORAGE:
                    app.storage.user["aerodromo"] = nome
                if nome:
                    la, lo = M.AERODROMES[nome]
                    res_ad.set_content(M.html_aerodromo(nome, M.find_region_for_point(r["regioes"], la, lo)))
                else:
                    res_ad.set_content("")

            ui.select(opcoes, label="O meu aeródromo", with_input=True, clearable=True,
                      value=estado["aerodromo"] if estado["aerodromo"] in opcoes else None,
                      on_change=lambda e: mostrar_ad(e.value)).classes("w-full").props("dark outlined")
            res_ad.move(target_index=-1)
            mostrar_ad(estado["aerodromo"] if estado["aerodromo"] in opcoes else None)

            ui.label(f"BRIEFING POR REGIÕES · {len(r['regioes'])}").classes("gv-sec")
            cartoes = "".join(
                M.html_regiao(g, 100 * g["polygon"].area / r["area"],
                              M.annotate_window_notes(g.get("notas"), r["ini"]))
                for g in r["regioes"])
            ui.html(f'<div class="gv-regioes">{cartoes}</div>').classes("w-full")

            with ui.tabs().classes("w-full").props("dense align=left active-color=primary indicator-color=primary no-caps") as tabs:
                t_mapa = ui.tab("Mapa")
                t_vento = ui.tab("Vento/Temp")
                t_s2 = ui.tab("Secção II")
                t_txt = ui.tab("Texto GAMET")
                t_leg = ui.tab("Legenda")
            with ui.tab_panels(tabs, value=t_mapa).classes("w-full").style("background:transparent"):
                with ui.tab_panel(t_mapa).classes("p-0"):
                    m = ui.leaflet(center=(39.6, -8.2), zoom=6).classes("w-full").style(
                        "height:460px;border-radius:14px;border:1px solid #22303C")
                    for g in r["regioes"]:
                        cor = M._DEC_BARRA.get(g["decision"], "#888")
                        geoms = g["polygon"].geoms if hasattr(g["polygon"], "geoms") else [g["polygon"]]
                        dica = f"{g['label']}: {g['decision']}" + (f" — {'; '.join(g['reasons'])}" if g["reasons"] else "")
                        for p in geoms:
                            if p.is_empty or getattr(p, "exterior", None) is None:
                                continue
                            camada = m.generic_layer(name="polygon", args=[
                                [[la, lo] for lo, la in p.exterior.coords],
                                {"color": cor, "fillColor": cor, "fillOpacity": 0.35, "weight": 2}])
                            camada.run_method("bindTooltip", dica)
                    # Aeródromos (círculo escuro) e pistas de ultraleves (círculo
                    # branco). Nome e designador ao passar o rato (no telemóvel,
                    # ao tocar no ponto). Criados de uma vez em JavaScript.
                    pontos = [[la, lo, nome, nome in M.ULTRALIGHT_STRIPS]
                              for nome, (la, lo) in M.AERODROMES.items()]
                    m.run_map_method("fitBounds", [[36.9, -9.9], [42.2, -6.1]])
                    ui.run_javascript(f"""
                        const pts = {json.dumps(pontos)};
                        const go = () => {{
                          const el = getElement({m.id});
                          if (!el || !el.map || !window.L) return setTimeout(go, 200);
                          const map = el.map;
                          for (const [la, lo, nome, ul] of pts) {{
                            L.circleMarker([la, lo], {{radius: ul ? 3 : 4, weight: 1.5, color: '#0E151C',
                              fillColor: ul ? '#FFFFFF' : '#0E151C', fillOpacity: 1}})
                             .bindTooltip(nome, {{direction: 'right', offset: [6, 0], className: 'gv-lbl'}})
                             .addTo(map);
                          }}
                        }};
                        go();""")
                with ui.tab_panel(t_vento).classes("p-0"):
                    if r["wind"]:
                        cols = [{"name": "n", "label": "Nível", "field": "n", "align": "left"}] + [
                            {"name": s["station"], "label": s["station"], "field": s["station"], "align": "left"}
                            for s in r["wind"]]
                        linhas = []
                        for lvl in M._WIND_LEVELS:
                            lin = {"n": lvl}
                            for s in r["wind"]:
                                e = s["levels"].get(lvl)
                                lin[s["station"]] = (f"{e['dir']:03d}°/{e['spd']:03d}kt "
                                                     f"{'+' if e['temp'] >= 0 else ''}{e['temp']}°C") if e else "—"
                            linhas.append(lin)
                        ui.table(columns=cols, rows=linhas).classes("w-full").props("dark flat dense")
                    else:
                        ui.label("Este GAMET não traz vento e temperatura por níveis.").classes("gv-k")
                with ui.tab_panel(t_s2).classes("p-0"):
                    q = f"{r['qnh']} hPa" if r["qnh"] else "—"
                    z = f"{r['fz']} ft AMSL" if r["fz"] else "—"
                    ui.html('<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px">'
                            f'<div class="gv-tile"><span class="gv-k">QNH MÍN.</span><br><span class="gv-v">{M._e(q)}</span></div>'
                            f'<div class="gv-tile"><span class="gv-k">ISO 0 °C MÍN. (FZLVL)</span><br><span class="gv-v">{M._e(z)}</span></div>'
                            '</div>').classes("w-full")
                with ui.tab_panel(t_txt).classes("p-0"):
                    ui.html(f'<div class="gv-txt">{M._e(r["texto"])}</div>').classes("w-full")
                with ui.tab_panel(t_leg).classes("p-0"):
                    ui.markdown(_LEGENDA)

            async def pdf():
                dados = await run.cpu_bound(_gerar_pdf, r["regioes"], r["texto"], r["fz"], r["qnh"], r["validity_label"])
                ui.download(dados, f"briefing_lppc_{datetime.now(timezone.utc):%Y%m%d_%H%MZ}.pdf")
            ui.button("Descarregar briefing (PDF)", icon="download", on_click=pdf).classes("w-full").props(
                "unelevated color=primary text-color=dark size=lg no-caps")
            ui.html('<p class="gv-nota">Ferramenta de apoio à decisão. Não substitui o briefing '
                    'oficial nem o juízo do piloto.</p>')

    def erro(msg):
        briefing.clear()
        with briefing:
            ui.html(f'<div class="gv-alerta gv-erro">{_md(msg)}</div>').classes("w-full")

    # ---- Controlos (fim da página) ----
    ui.label("GAMET E ARQUIVO").classes("gv-sec")
    with ui.expansion("Texto do GAMET (colar ou editar)", icon="edit_note").classes("w-full gv-card"):
        caixa = ui.textarea(placeholder="LPPC GAMET VALID …").classes("w-full").props("dark outlined autogrow")

        async def analisar_colado():
            if caixa.value.strip():
                desenhar(await run.cpu_bound(analisar, caixa.value.strip(), "manual"))
        ui.button("Analisar este texto", icon="search", on_click=analisar_colado).classes("w-full").props("outline no-caps")

    with ui.expansion("Arquivo de GAMETs", icon="inventory_2").classes("w-full gv-card"):
        ui.label("GAMETs recolhidos do IPMA desde 14/10/2026. Para rever situações "
                 "passadas — não para planear um voo.").classes("gv-k")
        zona_arq = ui.column().classes("w-full")

        async def abrir_arquivo():
            zona_arq.clear()
            ok, idx = await run.io_bound(M.fetch_arquivo_indice)
            with zona_arq:
                if not ok:
                    ui.label(f"Não foi possível ler o arquivo: {idx}").classes("gv-k")
                    return
                lista = sorted(idx["gamets"], key=lambda e: (e.get("inicio") or "", e["recolhido"]), reverse=True)
                opc = {i: f"{(e.get('inicio') or '')[8:10]}/{(e.get('inicio') or '')[5:7]} "
                          f"{(e.get('inicio') or '')[11:13]}–{(e.get('fim') or '')[11:13]}Z"
                          + ("" if e.get("tipo", "GAMET") == "GAMET" else f" {e['tipo']}")
                       for i, e in enumerate(lista)}
                sel = ui.select(opc, value=0 if opc else None, label="GAMET").classes("w-full").props("dark outlined")

                async def carregar():
                    e = lista[sel.value]
                    ok2, txt = await run.io_bound(M.fetch_arquivo, e["ficheiro"])
                    if not ok2:
                        ui.notify(f"Não foi possível ler o GAMET: {txt}", type="negative")
                        return
                    txt = re.sub(r"\s+", " ", txt).strip()
                    caixa.value = txt
                    desenhar(await run.cpu_bound(analisar, txt, "arquivo_hist", None, None, "", idx, e))
                    ui.run_javascript("window.scrollTo({top:0,behavior:'smooth'})")
                ui.button("Carregar e analisar", on_click=carregar).classes("w-full").props("outline no-caps")
        ui.button("Abrir arquivo", icon="folder_open", on_click=abrir_arquivo).props("flat no-caps")

    async def carregar_actual():
        g = await run.io_bound(obter_gamet_actual)
        if not g["texto"]:
            erro("**Não foi possível obter o GAMET.** Cola o texto em baixo.\n\n" + g["erro"])
            return
        caixa.value = g["texto"]
        desenhar(await run.cpu_bound(analisar, g["texto"], g["fonte"], g["boletins"],
                                     g["boletins_at"], g["boletins_fonte"], None, None,
                                     g.get("arquivo")))

    ui.button("Recarregar GAMET", icon="refresh", on_click=carregar_actual).classes("w-full").props("flat no-caps")
    await ui.context.client.connected()
    await carregar_actual()


def _gerar_pdf(*a):
    return M.generate_pdf(*a)


_STORAGE = bool(os.environ.get("STORAGE_SECRET"))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="LPPC GAMET – VFR", port=int(os.environ.get("PORT", 8080)), dark=True,
           reload=False, show=False, favicon="✈️",
           storage_secret=os.environ.get("STORAGE_SECRET"))
