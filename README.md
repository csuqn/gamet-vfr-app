# LPPC GAMET – Motor Cartográfico

Descodificador de GAMETs da FIR de Lisboa (Portugal Continental) para pilotos
VFR e de ultraleves. Transforma o texto do GAMET num briefing com decisões
**GO / MARGINAL / NO-GO** por zona, num mapa interactivo e num PDF.

> ⚠️ **Ferramenta de apoio à decisão.** Não substitui o briefing oficial nem a
> leitura do GAMET, METAR, TAF e SIGMET pelo piloto. A responsabilidade da
> decisão de voo é sempre do piloto em comando.

## O que faz

- Vai buscar o GAMET actual ao Self-Briefing do IPMA (ou aceita-o colado à mão).
- Interpreta a Secção I — visibilidade, nuvens, trovoada, turbulência, gelo,
  montanhas obscurecidas, cinzas vulcânicas — e o campo `SIGMET APPLICABLE`.
- Desenha as zonas afectadas com a geometria real de cada fenómeno, incluindo
  os qualificadores geográficos (`N OF`, `BTN`…) e de superfície (`MAR`,
  `LAN`, `COT`).
- Calcula a decisão em cada zona e mostra-a no mapa, por aeródromo e por pista
  de ultraleves (52 pontos), com consulta rápida.
- Mostra vento, temperatura, FZLVL e QNH da Secção II, e exporta tudo em PDF.

A app é **determinística**: regras fixas e expressões regulares, sem IA. O
mesmo GAMET dá sempre o mesmo resultado.

## Regras de decisão

| Condição | Decisão |
|---|---|
| VIS < 1500 m | NO-GO (MARGINAL se for local, `LCA`) |
| VIS < 3000 m | MARGINAL |
| Base < 300 ft AGL | NO-GO |
| Base < 500 ft AGL | MARGINAL |
| TS ISOL | MARGINAL |
| TS OCNL / FRQ / EMBD | NO-GO |
| TURB ou ICE severos | NO-GO |
| MT OBSC, cinzas vulcânicas | NO-GO |
| SIGMET aplicável | NO-GO em toda a área |

Na dúvida, a app escolhe sempre a leitura mais conservadora. Bases em AMSL são
convertidas para AGL contra a elevação máxima da zona.

## Fontes dos dados

| Dado | Fonte |
|---|---|
| GAMET e SIGMET | IPMA — Self-Briefing |
| Limites da área do GAMET | eAIP Portugal, ENR 2.1 (sectores inferiores da FIR) |
| Fronteira terrestre | Natural Earth 1:10m, ajustada aos pontos do ENR 2.1 |
| Linha de costa | NAV Portugal |
| Aeródromos e pistas UL | eVFR da NAV Portugal (AD 2 e AD 4) |
| Relevo (MEF) | SkyDemon |

## Teste contínuo com boletins reais

Desde Outubro de 2026, os GAMETs e SIGMETs do IPMA são recolhidos de hora a
hora (GitHub Actions) e analisados todos os dias. Os boletins e os relatórios
diários estão no ramo [`dados`](../../tree/dados). Qualquer correcção à app é
proposta como *pull request* e só entra depois de aprovada.

## Para programadores

```bash
pip install -r requirements.txt -r requirements-dev.txt
streamlit run app.py      # a app
python3 -m pytest         # 323 testes
```

Detalhes técnicos, princípios e armadilhas conhecidas em [`CLAUDE.md`](CLAUDE.md).
