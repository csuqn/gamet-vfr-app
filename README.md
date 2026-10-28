# LPPC GAMET – Motor Cartográfico

**Briefing meteorológico VFR para Portugal Continental, a partir do GAMET.**

### 👉 [Abrir a app](https://gamet-vfr-app.onrender.com/)

<sub>Se a app estiver parada há mais de 15 minutos, a primeira abertura demora
cerca de 1 minuto (plano gratuito do Render). Versão de reserva, com o mesmo
motor: [Streamlit](https://gamet-vfr-app-bxdwwklaarl2kdpiprmhu5.streamlit.app/).</sub>

Uma app web que lê o GAMET da FIR de Lisboa, percebe o que ele diz e onde, e
mostra num mapa onde se pode voar em VFR (**GO**), onde é preciso cautela
(**MARGINAL**) e onde não se deve voar (**NO-GO**), zona a zona e aeródromo a
aeródromo. Pensada para pilotos de ultraleves e de aviação geral em VFR.

> ⚠️ **Ferramenta de apoio à decisão, não de decisão.** Não substitui o
> briefing oficial nem a leitura do GAMET, METAR, TAF e SIGMET pelo próprio
> piloto. Uma previsão pode falhar, e a app pode ter erros. A responsabilidade
> da decisão de voo é sempre do piloto em comando.

---

## Índice

1. [O problema que resolve](#1-o-problema-que-resolve)
2. [O que é um GAMET](#2-o-que-é-um-gamet)
3. [Como usar a app](#3-como-usar-a-app)
4. [Como ler o briefing](#4-como-ler-o-briefing)
5. [Exemplo real](#5-exemplo-real)
6. [Como a app decide](#6-como-a-app-decide)
7. [Como a app desenha as zonas](#7-como-a-app-desenha-as-zonas)
8. [Limitações conhecidas](#8-limitações-conhecidas)
9. [Fontes dos dados](#9-fontes-dos-dados)
10. [Qualidade e testes](#10-qualidade-e-testes)
11. [Para programadores](#11-para-programadores)
12. [Perguntas frequentes](#12-perguntas-frequentes)

---

## 1. O problema que resolve

O GAMET é a previsão oficial para voos a baixa altitude, mas é escrito num
código compacto, pensado para meteorologistas e controladores:

```
SFC VIS:N OF N3840 MAR AND COT LCA 0200-5000M FG/BR
SIG CLD:N OF N3840 MAR AND COT LCA BKN 002-008/012HFT AGL
```

Para saber se se pode voar de Alqueidão para Évora é preciso descodificar cada
campo, imaginar no mapa onde fica "a norte de 38°40'", perceber se "MAR AND
COT" inclui a rota, e cruzar tudo com os mínimos VFR. É lento e fácil de
errar, sobretudo quando o GAMET tem vários fenómenos sobrepostos.

A app faz esse trabalho: lê o texto, desenha cada fenómeno na sua área real e
dá uma decisão clara para cada zona, sem perder o detalhe de **porquê**.

## 2. O que é um GAMET

O GAMET (*GAMET Area Forecast*) é emitido pelo IPMA para a área continental da
FIR de Lisboa, abaixo do FL150, a cada 6 horas (períodos de validade 03–09,
09–15, 15–21 e 21–03 UTC, com emendas `AMD` quando a previsão muda). Tem duas
secções:

- **Secção I — fenómenos significativos:** visibilidade à superfície
  (`SFC VIS`), nuvens significativas (`SIG CLD`), trovoada e tempo severo
  (`SIGWX`), turbulência (`TURB`), gelo (`ICE`), onda de montanha (`MTW`),
  vento generalizado à superfície (`SFC WSPD`), montanhas obscurecidas
  (`MT OBSC`), cinzas vulcânicas (`VA`) e os SIGMET aplicáveis.
- **Secção II — informação geral:** sistemas de pressão, nebulosidade,
  vento e temperatura por níveis em seis estações, nível de congelação
  (`FZLVL`) e QNH mínimo.

Cada fenómeno pode vir limitado no espaço (`N OF N3840`, `BTN N3900 AND
N4130`, `E OF W00800`), à superfície (`MAR` mar, `LAN` terra, `COT` costa), no
tempo (`11/15` = só das 11 às 15 UTC) e na extensão (`ISOL`, `OCNL`, `FRQ`,
`LCA` = localmente).

## 3. Como usar a app

1. **Abre a [app](https://gamet-vfr-app.onrender.com/).** O GAMET em vigor é carregado do IPMA e analisado logo — o briefing aparece no topo.
   - A app foi desenhada primeiro para o telemóvel (tema escuro, que se lê
     bem ao sol); no computador os cartões das zonas ficam lado a lado.
   - Se o IPMA não responder, a app explica o que falhou. Podes colar o GAMET
     à mão na caixa de texto (no fundo da página), ou indicar um endereço
     alternativo no painel "📡 Ligação ao IPMA".
   - O botão **🔄 Recarregar GAMET** vai buscar a versão mais recente.
   - **Entre GAMETs:** o IPMA retira o GAMET anterior cerca de 45 minutos
     antes de publicar o novo. Nesse intervalo a app carrega o último GAMET
     do arquivo que ainda está em vigor, com um aviso bem visível, e os
     SIGMETs em vigor (da página do IPMA e do arquivo).
2. **Lê o resultado**, de cima para baixo:
   - faixa com a validade, o tempo que falta para expirar e o estado dos
     SIGMETs (`NIL`, `ACTIVO` ou `N/VERIF.` quando não foi possível verificar);
   - avisos importantes (SIGMET, texto ilegível, vento forte);
   - veredicto global (ex.: "NO-GO em 11% da FIR"), com uma barra das três decisões;
   - o teu aeródromo, os cartões das zonas e, em separadores, o mapa, o vento
     e temperatura, a Secção II, o texto do GAMET e a legenda;
   - o PDF.
3. **🔍 Analisar GAMET** (no fundo) só é preciso se colares ou editares o texto.

A app também funciona sem internet, com o GAMET colado à mão.

**📚 Arquivo de GAMETs.** No painel com esse nome podes abrir qualquer GAMET
recolhido desde 14/10/2026 (escolhe o dia e o período) e analisá-lo como se
fosse o actual. É analisado com os SIGMETs que estiveram em vigor durante a
sua validade — nunca com os de agora — e aparece sempre com o aviso "GAMET
DO ARQUIVO — não é o GAMET actual". Serve para rever situações passadas,
não para planear um voo.

## 4. Como ler o briefing

**Avisos no topo**
- 🚨 **SIGMET:** NO-GO na área do SIGMET, com 10 NM de margem (e estendida
  na direcção do movimento, se o SIGMET se desloca). Se a área não for legível,
  ou se o GAMET só indicar o identificador do SIGMET sem o texto completo estar
  disponível, NO-GO em toda a área. Um SIGMET referido pelo GAMET que já
  expirou ou foi cancelado deixa de contar (com aviso). Lê sempre o SIGMET completo.
- ⚠️ **AIRMET:** desde a 4.0 entra na decisão com as mesmas regras do GAMET
  (visibilidade, base, trovoada/CB, onda de montanha, montanhas obscurecidas,
  vento), só na área do AIRMET (sem margem). O aviso diz o que a app leu de
  cada AIRMET e o efeito; os motivos das zonas dizem "AIRMET n — …". Um AIRMET
  que a app não consiga ler dá MARGINAL na sua área, com aviso.
- ⚠️ **Nenhum campo reconhecido:** a app não percebeu o texto. Isto **não**
  significa que o tempo está calmo; confirma o GAMET.
- 💨 **Vento forte a 1000 ft AGL** (20 kt ou mais numa estação): aviso
  informativo, para confirmares os limites de vento cruzado da tua aeronave.
- ⏳ **GAMET a expirar ou fora de validade:** espera pelo próximo, ou confirma
  que estás a ver o actual.

**✈️ O meu aeródromo.** Escolhe um aeródromo ou pista de ultraleves (52
pontos, com coordenadas oficiais do eVFR) e vês logo a decisão nesse local e
os motivos. A app lembra-se do último que escolheste.

**📋 Briefing por regiões.** Um cartão por zona, da pior para a melhor:
- **decisão** (GO / MARGINAL / NO-GO) e percentagem da área;
- **nome da zona**, pelos aeródromos que lá caem (ex.: "Braga, Porto, Vila
  Real +5");
- **valores** de visibilidade, base das nuvens e CB/trovoada em destaque;
  turbulência, gelo, VA e MT OBSC por baixo, quando existem;
- **motivos da decisão**, ou seja, que regra a tornou NO-GO ou MARGINAL;
- **alcance restrito**: avisos que só se aplicam a parte do que está desenhado
  (ex.: "só sobre o mar", "apenas 11–15Z — já terminou").

**🗺️ Mapa** (separador). As zonas a verde, âmbar e vermelho sobre o mapa,
com todos os aeródromos e pistas. Podes aproximar e clicar.

**🌡️ Secção II e Vento/Temp** (separadores). Nível de congelação mínimo, QNH
mínimo e tabela de vento e temperatura por níveis nas seis estações (Bragança, Porto, Viseu, Lisboa,
Évora e Faro).

**📄 PDF.** O briefing completo, com o mapa e o texto original do GAMET, para
guardar ou imprimir.

## 5. Exemplo real

GAMET de 14/10/2026, válido das 15 às 21 UTC:

```
SFC VIS:N OF N3840 MAR AND COT LCA 0200-5000M FG/BR
SIG CLD:N OF N3840 MAR AND COT LCA BKN 002-008/012HFT AGL
TURB:S OF N3700 LCA MOD SFC/FL040
SIGMET APPLICABLE: AT TIME OF ISSUE NIL
```

Em linguagem corrente: nevoeiro e neblina, localmente com visibilidade até
200 m, e nuvens com base entre 200 e 800 ft, a norte de 38°40' (latitude de
Lisboa), mas só sobre o mar e a faixa costeira; turbulência moderada no
Algarve.

O que a app mostra:
- **NO-GO** no mar e na faixa costeira a norte de 38°40' (cerca de 11% da
  área): base das nuvens a 200 ft, abaixo do mínimo de 300 ft.
- **GO** no resto do país. A turbulência moderada no Algarve aparece como
  informação, porque não altera a decisão.

## 6. Como a app decide

Em cada zona, a app aplica estas regras. Fica a pior decisão que se aplicar.

| Condição | Decisão | Porquê |
|---|---|---|
| Visibilidade < 1500 m | NO-GO | Abaixo dos mínimos VFR |
| Visibilidade < 1500 m, mas local (`LCA`) | MARGINAL | Pode ser contornável |
| Visibilidade < 3000 m | MARGINAL | Perto dos mínimos |
| Base das nuvens < 300 ft AGL | NO-GO | Sem margem sobre o terreno e obstáculos |
| Base das nuvens < 500 ft AGL | MARGINAL | Margem reduzida |
| Trovoada isolada (`ISOL TS`) | MARGINAL | Contornável com cuidado |
| Trovoada ocasional, frequente ou embebida | NO-GO | Não contornável em segurança |
| Turbulência ou gelo **severos** | NO-GO | A maioria dos ultraleves não tem margem estrutural nem degelo |
| Turbulência ou gelo moderados | informativo | Mostrado, mas não muda a decisão |
| Onda de montanha (`MTW`) severa | NO-GO | Risco severo |
| Onda de montanha (`MTW`) moderada | MARGINAL | Descendentes junto ao relevo que podem exceder a razão de subida de uma aeronave com pouca potência |
| Vento generalizado à superfície (`SFC WSPD`) ≥ 30 kt | NO-GO | Fora dos limites de qualquer ultraleve |
| Linha de borrasca, chuva ou chuvisco que gela, tempestade de poeira ou areia, granizo, nuvem funil (`SQL`, `FZRA`, `FZDZ`, `DS`, `SS`, `GR`, `FC`) | NO-GO | Fenómenos severos |
| Montanhas obscurecidas (`MT OBSC`) | NO-GO | Risco de voo controlado contra o terreno |
| Cinzas vulcânicas (`VA`) | NO-GO | — |
| AIRMET em vigor | As regras acima, na área do AIRMET (sem margem, estendida pelo movimento) | Área ilegível → toda a FIR; fenómeno ilegível → MARGINAL, com aviso |
| SIGMET em vigor | NO-GO na área do SIGMET + 10 NM (estendida pelo movimento) | O SIGMET completo do IPMA traz a área (polígono, círculo ou qualificadores). Sem área legível, ou só com o identificador no GAMET: NO-GO em toda a área |

**Princípios por trás das regras**
- **Na dúvida, a leitura conservadora.** Errar para o lado pessimista é
  incómodo; errar para o lado optimista é perigoso. Quando há vários valores
  numa zona, conta o pior (visibilidade e base mínimas).
- **Bases em AMSL** são convertidas para AGL contra a **elevação máxima** do
  terreno na zona (MEF do SkyDemon por quadrícula de 1° × 30'), ou seja, a
  pior situação que se encontra lá.
- **Falhar em voz alta.** Se a app não perceber o texto, avisa. Nunca mostra
  um GO silencioso. Desde a 3.9, uma parte da Secção I que a app não consegue
  ler (ex.: gralha do IPMA numa base de nuvem) aparece no briefing como
  "Campo não interpretado" — e não entra na decisão.
- **Sem IA.** A app usa regras fixas e expressões regulares. O mesmo GAMET dá
  sempre o mesmo resultado, e um erro é sempre localizável e corrigível.

## 7. Como a app desenha as zonas

Não há sectores fixos. Cada fenómeno do GAMET é desenhado na sua área exacta:

1. A área do GAMET, isto é, os limites oficiais da FIR abaixo do FL245, com a
   fronteira terrestre e a linha de costa.
2. Cada qualificador corta essa área: `N OF N3840` fica com a parte a norte de
   38°40'; `MAR` só com o mar; `COT` com uma faixa de 10 km para cada lado da
   costa.
3. Todos os fenómenos são sobrepostos, e o mapa fica dividido nas zonas onde a
   combinação é a mesma.
4. Em cada zona é aplicada a tabela de decisão; zonas vizinhas com o mesmo
   resultado e os mesmos motivos são juntas.

Assim, um nevoeiro no Minho não põe Bragança em NO-GO, e uma trovoada no
Algarve não afecta Lisboa.

## 8. Limitações conhecidas

- **SIGMETs:** a app lê os que estão em vigor na página do IPMA no momento
  em que o GAMET é carregado (e indica a hora da verificação). Um SIGMET que
  saia depois disso só aparece ao carregares de novo. Com um GAMET colado à
  mão, só conta o campo `SIGMET APPLICABLE` do próprio GAMET.
- **Arquivo:** é recolhido de 15 em 15 minutos, por isso um GAMET ou SIGMET
  que tenha estado publicado menos tempo do que isso pode faltar. No recurso
  entre GAMETs, um SIGMET emitido há menos de 15 minutos só aparece se a
  página do IPMA o mostrar.
- **AIRMETs** (desde a 4.0) entram na decisão, como os SIGMETs só quando o
  GAMET vem do IPMA ou do arquivo. Os níveis (`FL015`) não restringem a
  decisão.
- **Janelas horárias** (`11/15`) são anotadas, com indicação de se já
  começaram ou terminaram, mas não mudam a decisão: a previsão pode
  atrasar-se ou antecipar-se. Desde a 4.2, quando uma janela já terminou e
  isso muda a decisão, o veredicto, os cartões e o aeródromo mostram também,
  numa linha secundária, a decisão do **resto do período** (ex.: "Resto do
  período (12–15Z): GO · pior do período: MARGINAL"). A decisão principal
  continua a ser a pior de todo o período.
- **Os limiares de decisão** foram definidos pelo autor para ultraleves e
  aviação geral VFR; não são uma norma oficial.
- **Estuários** (Tejo, Minho) contam como terra para efeitos de `MAR`/`LAN`.
- **A faixa costeira** (`COT`) usa 10 km para cada lado da costa; a OACI não
  fixa uma largura.
- **O GAMET é uma previsão.** A app pode descodificá-lo na perfeição e o
  tempo real ser diferente.

## 9. Fontes dos dados

| Dado | Fonte |
|---|---|
| GAMET e SIGMET | IPMA — Self-Briefing |
| Limites da área do GAMET | eAIP Portugal, ENR 2.1 — sectores inferiores da FIR (SFC–FL245) |
| Fronteira terrestre | Natural Earth 1:10m, forçada a passar pelos pontos de fronteira do ENR 2.1 |
| Linha de costa | NAV Portugal |
| Aeródromos e pistas de ultraleves | eVFR da NAV Portugal (AD 2.2 e AD 4.2) |
| Relevo (MEF) | SkyDemon |
| Mapa de fundo | OpenStreetMap |

## 10. Qualidade e testes

- **1856 testes automáticos** cobrem a leitura do texto, a geometria, as
  decisões, os dados aeronáuticos e a app completa. Cada erro alguma vez
  encontrado tem um teste que impede que volte a aparecer.
- **Verificação cruzada:** em centenas de GAMETs gerados, a decisão de cada
  zona é comparada com um cálculo feito directamente ponto a ponto, em cada
  aeródromo.
- **Teste contínuo com boletins reais:** desde Outubro de 2026, os GAMETs e
  SIGMETs do IPMA são recolhidos de 15 em 15 minutos pelo GitHub Actions e
  analisados todos os dias (um script automático e uma revisão manual). Os
  boletins e os relatórios diários estão no ramo [`dados`](../../tree/dados).
- **Nenhuma alteração entra sem aprovação:** qualquer correcção é proposta
  como *pull request*, com o boletim real que expôs o problema, e só é
  aplicada depois de aprovada pelo autor.

## 11. Para programadores

```bash
pip install -r requirements.txt -r requirements-dev.txt
cd nicegui_app && python main.py   # a app principal (NiceGUI), http://localhost:8080
streamlit run app.py               # a versão de reserva (Streamlit)
python3 -m pytest                  # os testes (1856)
```

| Ficheiro / pasta | Conteúdo |
|---|---|
| `app.py` | O motor (recolha, leitura, geometria, decisão, análise, PDF) e a interface Streamlit |
| `nicegui_app/` | A interface principal (NiceGUI, publicada no Render); usa o motor do `app.py` |
| `tests/` | Testes automáticos |
| `scripts/recolher_gamet.py` | Recolha de GAMETs e SIGMETs (GitHub Actions) |
| `scripts/analisar.py` | Análise automática de boletins reais |
| `.github/workflows/` | Recolha contínua, de 15 em 15 minutos |
| `CLAUDE.md` | Notas técnicas: arquitectura, princípios, armadilhas conhecidas |
| ramo `dados` | Boletins recolhidos, `indice.json` (lido pela app) e relatórios diários |

## 12. Perguntas frequentes

**A app diz GO. Posso voar?**
Não só por isso. GO significa que o GAMET não prevê nada que viole os mínimos
VFR nessa zona. Continuas a ter de ver METAR, TAF, SIGMET, NOTAM e as
condições reais, e de decidir tu.

**Porque é que a minha zona está NO-GO se o aviso é "local" (`LCA`)?**
Para a visibilidade, `LCA` baixa a decisão para MARGINAL. Para nuvens baixas e
trovoada não: uma base a 200 ft, mesmo local, pode fechar um vale ou uma
aproximação.

**Porque é que há turbulência no cartão mas a zona está GO?**
Turbulência e gelo moderados são mostrados como informação, mas não mudam a
decisão. Só os severos dão NO-GO.

**O que acontece se o IPMA mudar o site?**
A app tenta vários endereços conhecidos e explica o que falhou. Podes colar o
GAMET à mão ou indicar o novo endereço nas opções.
