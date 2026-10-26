# Relatório semanal — 2026-W43 (19 a 25 de Outubro de 2026)

Primeira semana completa do processo com agentes (7 relatórios diários com "Métricas"). Comparação com a W42, que só tinha **um** dia de agentes (18-out); digo-o sempre que comparo.

Fontes: relatórios diários de 19 a 25-out (e o de 26-out para o fim do dia 25), PRs #18–#25 e os comentários do revisor, as 21 execuções do workflow "Testes" da semana (runs 24–44), o histórico de `main` e `dados`, o arquivo `gamets/` e `sigmets/`, e o relatório semanal W42.

## a. Resumo executivo

- **A app está mais fiável do que há uma semana e não teve nenhum erro do parser com efeito numa decisão real desde 19-out.** Nos 27 GAMETs da semana o parser concordou com o piloto em 1385/1404 aeródromos (98,6%); as 19 diferenças foram todas erros do piloto. Entraram 6 versões (3.5 → 3.10) que fecharam 5 erros optimistas *latentes* (formato real, ainda sem efeito) e acrescentaram dois avisos que fazem a app "falhar em voz alta".
- **O único episódio optimista real da semana não é um bug, é uma lacuna de desenho:** a 25-out, 18:10–21:00Z, dois **AIRMETs** observavam nevoeiro (base 200 ft, VIS 200 m) a N de 39°30' e a app mostrou GO (com aviso). Interpretar AIRMETs está pendente de decisão tua desde a W42.
- **O processo com agentes funciona e é barato, mas o piloto não acrescentou nada nesta semana:** 0 erros do parser apanhados só por ele; 100% das diferenças foram falsos alarmes dele. Os erros encontrados vieram do `analisar.py` (HTF), do comparador (`S BTN`) e sobretudo do **revisor** (topo em intervalo, MT OBSC/VA, vírgula nos KM, ENTIRE FIR, mais 2 regressões travadas).
- **Merge automático:** 1 merge automático (#20, correcto), 0 reversões, `main` sempre verde (21/21). Tudo o que era regra ou funcionalidade foi para ti.
- **Recomendação principal:** decidir os AIRMETs (pelo menos a versão mínima: deixar de mostrar GO "limpo" com AIRMET em vigor). Manter o merge automático como está.

## b. Recolha

### Por dia (data de arquivo)

| Dia | GAMETs | AMD/COR | SIGMET/AIRMET | Linhas em `falhas.log` | Das quais anormais |
|---|---|---|---|---|---|
| 19 | 4 | 0 | 1 (SIGMET T01 191520/191700) | 12 | 0 |
| 20 | 3 | 0 | 0 | 29 | ~22 (IPMA não emitiu o 200300) |
| 21 | 4 | 0 | 2 (SIGMET U01, U02 — oceânicos) | 12 | 0 |
| 22 | 4 | 0 | 0 | 9 | 0 |
| 23 | 4 | 0 | 0 | 11 | 0 |
| 24 | 4 | 0 | 0 | 13 | 0 |
| 25 | 4 | 0 | 2 (AIRMET 1, 2 — nevoeiro OBS) | 9 | 0 |
| **Total** | **27** | **0** | **5 (3 SIGMET, 2 AIRMET)** | **95** | **~22** |

W42 (4,5 dias): 18 GAMETs, 7 SIGMET/AIRMET, 19 linhas anormais.

### Buracos e falhas

1. **20-out, 03:00–~08:50Z:** o IPMA não publicou o GAMET 200300/200900 (confirmado por ti às 07:21Z: "No active SIGMET/AIRMET/GAMET for LPPC"). A recolha e a app comportaram-se bem: sem GAMET em vigor, a app mostra o diagnóstico, não um GO.
2. Fora disso, só as janelas normais de ~30–45 min antes de cada emissão (o recurso ao arquivo cobre-as). **Nenhuma falha de acesso (HTTP) ao IPMA na semana** (na W42 houve 5h15 a 17-out).
3. Todos os GAMETs foram arquivados 5–20 min antes de entrarem em vigor; SIGMETs/AIRMETs 0–6 min depois de começarem.
4. Nenhum boletim em `sigmets/desconhecidos/` (a pasta continua a não existir).

### Workflows

- **"Recolha GAMET LPPC":** `active` toda a semana; a cadeia de ~5h30 nunca partiu (execuções 47 → 126). As `schedule` canceladas são o grupo de concorrência.
- **"Testes":** 21 execuções na semana (runs 24–44), **21 verdes**, incluindo 7 merges no `main`.
- **"Publicar protótipo NiceGUI":** `active`, sem execuções relevantes.
- A tarefa diária passou de 07:01Z para 08:01Z a 26-out (fim da hora de Verão); continua às 08:00 de Lisboa.

## c. Qualidade da app

Versões da semana: 3.4 → **3.5** (19-out) → **3.6** (20) → **3.7**, **3.8**, **3.9**, **3.10** (21). Testes: 590 → 1272 recolhidos (1271 passam, 1 salta sem NiceGUI). O `CLAUDE.md` diz 1270.

### Erros encontrados, por gravidade

**Optimistas com efeito real (ou potencial) numa decisão**

| # | Erro | Boletim real | Efeito | Estado |
|---|---|---|---|---|
| C4 | Cardinal solto antes de BTN ignorado em silêncio (`S BTN N3720 - N3800`) | GAMET 182100/190300 | AMBÍGUO: se a intenção era "S OF N3800", Faro, Portimão e Lagos ficaram GO com base 200 ft prevista, 23–03Z (18/19-out) | **Corrigido na 3.5** (#18, opção (b) tua: união com o semiplano + aviso "Área alargada"), 19-out 11:15 |
| A1 | AIRMETs não entram na decisão | AIRMET 1 e 2 de 25-out (`BKN … 002HFT AGL`, `VIS 0200-5000M FG/BR`, OBS, N de N3930) | GO em todo o continente 18:10–21:00Z; pelas regras seriam NO-GO 25 pontos | **Por desenho** — pergunta pendente desde a W42 |

**Optimistas latentes (formato real ou plausível, sem efeito nesse dia)**

| # | Erro | Origem | Estado |
|---|---|---|---|
| L5 | Gralha `HTF` descartava a base de nuvem (`BKN 008/010HTF`) | GAMET 201500, alerta "campo sem fenómeno" do `analisar.py` | 3.7 (#20, **automático**) |
| L6 | Topo em intervalo descartava a base (`002/010-015HFT`) | revisor do #20; formato real na Secção II | 3.8 (#21, tu) |
| L7 | MT OBSC/VA: só a 1.ª subentrada gerava bloco | revisor do #22 | 3.10 (#23) |
| L8 | `LCA 1,5KM` lido como 5000 m | revisor do #22 | 3.10 (#23) |
| L9 | `ENTIRE FIR` a meio da linha ignorado (`MT OBSC: N OF N4100 LAN ENTIRE FIR` → 41 GO) | revisor do #22 | **Pendente** — PR #24 fechado em pausa por ti (4 rejeições) |
| L10 | 2.º valor ilegível na mesma subentrada perde-se sem aviso (`3000M BR 1O00M FG`) | revisor do #22 | Deixado de fora por decisão tua |

**Pessimistas (MENOR)**

| # | Erro | Boletim real | Estado |
|---|---|---|---|
| P5 | Coordenada de SIGMET só com graus (`W018`) → NO-GO em toda a FIR 18/19-out 23:30–02:00Z por uma TURB a FL230+ a 700 km | SIGMET U02 182330 | 3.5 (#18, tu) |
| P6 | `MT OBSC: NIL` / `VA: NIL` e abertura vazia → toda a FIR | sintético | Mantido por decisão tua (conservador) |

**Apresentação / ferramenta (MENOR)**

- Faixa "SIGMET ACTIVO" a vermelho com um SIGMET oceânico sem efeito (U01/U02, 18 e 21-out): pendente, sugestão "ACTIVO (fora da área)".
- Motivo "SIGMET T01" em Cascais, fora do T01 + 10 NM (19-out): pendente; decisão certa.
- `looks_unparseable()` aceitaria `HAZARDOUS WX NIL` só por haver `CLD:` na Secção II (20-out): sem caso real; pendente.
- `analisar.py`: falsos alarmes "-" (3.5), `HAZARDOUS WX` e `RA/DZ/BR` (#25): corrigidos.

**Funcionalidades novas pedidas por ti:** nota "Nuvens baixas na Secção II" (3.6) e aviso "Campo não interpretado" (3.9). Nenhuma muda decisões.

### Formatos novos vistos na semana

- `S BTN …` (cardinal solto antes de BTN) — C4.
- Coordenada de SIGMET só com graus (`W018`, `W013`) — P5; o `W013` do U02 de 21-out já foi lido bem.
- Gralha `HTF` e topo em intervalo `050-090/100-130HTF` — L5, L6.
- `SECN I HAZARDOUS WX NIL` **sem** a linha `SIGMET APPLICABLE` (192100, 200900, 240300, 240900, 241500) — tratado bem (faixa N/VERIF. só se não houver verificação).
- Tempo presente com três partes `RA/DZ/BR` — só o script.
- Base de 300 ft exactamente no limiar (210900) — MARGINAL, correcto pela regra "< 300".
- AIRMETs de nevoeiro **OBS** a cobrir metade do continente sem AMD do GAMET (25-out) — A1.

### Fenómenos ou campos ainda não cobertos

- **AIRMET** (A1): mostrado, não interpretado. Foi o caso mais relevante da semana.
- **Níveis dos SIGMET** (FL230/440, FL160/400…): continuam a não restringir. Na W43 os SIGMETs oceânicos já não pesaram (área legível desde a 3.5), mas um SIGMET de altitude sobre o continente ainda poria NO-GO para VFR.
- `ENTIRE FIR` a meio da linha (L9), em pausa.
- Secção II e WIND/T: fora da decisão por regra (a 3.6 só avisa).

### Padrões repetidos

1. **"Campos que desaparecem em silêncio"** foi a família da semana (L5–L8, L10). A 3.9 inverteu isto de vez: qualquer subentrada sem fenómeno passa a dar aviso nas duas interfaces. Desde a 3.9, 0 avisos no arquivo.
2. **Qualificadores geográficos** acalmaram: só o `S BTN` (C4) e o `ENTIRE FIR` (L9). Nenhum formato novo de área entre 20 e 25-out.
3. **Nevoeiro/estratos baixos `LCA BKN 002`** aparecem em quase todas as madrugadas (base ≤ 200 ft em 6 dos 27 GAMETs). A leitura "LCA não suaviza a base" foi levantada como dúvida por pilotos em 4 dias diferentes — app e pilotos concordam sempre, mas a regra não está escrita de forma explícita (ver g.3).

## d. Avaliação do processo com agentes

| Medida | W42 (só 18-out) | **W43 (19–25-out)** |
|---|---|---|
| GAMETs analisados | 4 | **27** |
| Aeródromos comparados | 208 | **1404** |
| Concordância parser × piloto | 182/208 = 87,5% | **1385/1404 = 98,6%** |
| Diferenças: parser optimista | 26 (1 causa: C3) | **0** |
| Diferenças: parser pessimista | 0 | **0** |
| Diferenças: erro do piloto | 0 | **19** (2 causas: LPPT "por prudência" em COT, 19-out; Secção II tratada como SIG CLD, 18 pontos, 20-out) |
| Diferenças: ambíguo | 0 | **0** (+1 ambíguo sem diferença: `S BTN`) |
| **Taxa de falsos alarmes** (erros do piloto ÷ diferenças) | 0% | **100%** (19/19) |
| Erros do parser apanhados pelo piloto que o `analisar.py` não apanharia | 0 | **0** |
| Erros apanhados por outra peça | comparador: L2 | `analisar.py`: L5; comparador: C4; **revisor: L6–L10** |
| Agentes lançados / falhados | 12 / 0 | **55** (27 piloto, 18 comparador, 2 editor, 2 revisor nas tarefas diárias; mais 4 revisões do #24 noutra sessão) / **0** |
| Respostas incompletas | 1 deslize de contagem | 3 deslizes de contagem do piloto (19, 21, 22-out), sem efeito |
| Tempo da tarefa diária | ~38 min | 35 / 12 / 40 / 20 / 25 / 8 / 15 min (média ~22) |

**Leitura honesta:**

- **O piloto não acrescentou valor próprio nesta semana.** Não apanhou nenhum erro do parser; as 19 diferenças foram erros dele. Em 20-out errou de forma instrutiva: aplicou a regra da base à Secção II — o que acabou por levar à nota da 3.6, mas como funcionalidade, não como erro do parser. Num dia como o 21-out (HTF) leu a gralha "bem" e concordou com a app por acaso; só o `analisar.py` deu o alarme.
- **O valor está no revisor** (5 erros optimistas latentes encontrados e 1 regressão travada no #18; 4 rejeições fundamentadas no #24) e, em segundo lugar, no **comparador** (C4, que nenhum alerta automático apanhava).
- **Mesmo assim, o piloto continua a ser a única peça capaz de apanhar o tipo C1** (fenómeno lido de forma errada sem nenhum alerta). Não houve nenhum caso destes na semana, por isso não há dados para julgar. Custa ~4 agentes/dia e ~5 min.
- **Os pilotos ficaram às cegas quanto ao resultado da app**: receberam só o texto e o caminho do repositório. Mas o `CLAUDE.md` passou a descrever muitos casos concretos (GAMETs 201500, 182100, 192100…), com a leitura da app. Ainda não se viu um piloto copiar uma leitura, mas o risco cresceu (ver g.4).
- Os comparadores, em dias de acordo total, limitam-se a confirmar; correm em ~10 s.

## e. Merge automático, PR a PR

| PR | Versão | Como entrou | Revisor | Mais permissivas na comparação de versões | Comentário |
|---|---|---|---|---|---|
| #18 | 3.5 `S BTN` + coordenadas só com graus | Tu, 19-out 11:15 ("[Precisa do Duarte]": regras) | d043ce1 **REJEITADO** (a junção por AND encolhia a área: LP58/LP78 NO-GO → GO); 618dff5 **APROVADO** | Sem `--indice`: 0 (3 mais severas pretendidas). Com `--indice`: **47, provadas** (todas do U02, ≥ 60 NM da FIR, FL230/440) | O revisor travou uma regressão optimista. Trazia por engano o parágrafo "Excepção para erros CRÍTICOS" no `CLAUDE.md` — o revisor detectou-o e tu aprovaste-o |
| #19 | 3.6 nota de nuvens baixas na Secção II | Tu, 20-out 19:55 | DÚVIDA (só por ser funcionalidade nova) | 0 / 0 (1000 variantes) | Correcto |
| #20 | 3.7 `HTF` | **Automático**, 21-out 07:23 | **APROVADO** | 0 / 0 | Correcto: erro optimista latente, correcção estreita (só `_CLD_BASE_RE`) |
| #21 | 3.8 topo em intervalo | Tu, 21-out 07:41 | **Não corrido** (o editor devolveu PRECISA DO DUARTE) | 0 / 0 | A dúvida era real (a nota da Secção II passou de 2 para 18 em 28 GAMETs). Entrou sem revisor — único caso da semana |
| #22 | 3.9 aviso "Campo não interpretado" | Tu, 21-out 14:09 | **APROVADO** (e encontrou L7–L10) | 0 decisões alteradas em 3463 GAMETs | Correcto |
| #23 | 3.10 MT OBSC/VA por subentrada; vírgula nos KM | Tu (autorizaste lançar tudo), 21-out 14:30 | **APROVADO** | 0 / 0 no arquivo; nos sintéticos `3,2KM` 2000 → 3200 m (mais permissivo, **provado**: igual a `3.2KM`) | Teria cumprido os critérios do merge automático |
| #24 | 3.11 `ENTIRE FIR` a meio da linha | **Fechado sem merge** (22-out, em pausa por ti) | **4 × REJEITADO**, todas com casos concretos mais permissivos por hora ou por região | — | O revisor fez exactamente o que devia; a abordagem "linhas virtuais" mostrou-se frágil |
| #25 | `analisar.py` (vocabulário) | Tu, 23-out 08:37 | — (só o script) | n/a | Correcto; 0 falsos alarmes desde aí |

- **Merges automáticos: 1** (#20). **Reversões: 0.** O `main` nunca esteve vermelho.
- A **excepção para erros CRÍTICOS** (19-out) não foi usada: não houve nenhum erro crítico com escolha entre leituras.
- **Qualidade do revisor:** nenhum caso conhecido de aprovação indevida ou de rejeição injusta. 6 rejeições na semana, todas com reprodução concreta.
- **Decisões mais permissivas da semana:** 47 (#18, U02) + os casos sintéticos de vírgula do #23 — todas provadas, todas em PRs que tu integraste. **Nenhuma em merges automáticos.**

## f. Riscos e incidentes

Situações em que a app publicada esteve mais permissiva do que devia (ou podia estar):

1. **19-out 00:00–03:00Z (parte W43 do episódio C4):** `S BTN N3720 - N3800` com base 200 ft. Se a intenção era "S OF N3800", Faro, Portimão e Lagos estiveram em GO. Ambíguo; o GAMET seguinte (190300) alargou de facto o nevoeiro à costa algarvia, o que favorece a leitura larga. Corrigido na 3.5 (depois de a validade acabar).
2. **25-out 18:10–21:00Z (A1):** GO em todo o continente com AIRMETs a observar base 200 ft e VIS 200 m a N de 39°30' (25 pontos). Mitigado pelo aviso em destaque e por ser sobretudo depois do pôr do Sol (~18:30Z), mas a faixa e os cartões diziam GO. Por desenho.
3. **Latentes L5–L10:** nenhuma exposição real conhecida; L9 e L10 continuam abertos.

Sem incidentes de recolha (o 20-out foi o IPMA a não emitir; a app não mostrou GO).

Riscos abertos:

- AIRMET (A1) — o mais provável de se repetir: nevoeiro nocturno observado é frequente nesta época.
- `ENTIRE FIR` a meio da linha (L9) — ainda não visto num GAMET real.
- Falha prolongada do IPMA continua sem alerta imediato (recomendação g.4 da W42, por fazer); esta semana não houve nenhuma.

## g. Recomendações

1. **Manter o merge automático tal como está.** 1/1 correcto, as salvaguardas funcionaram (5 PRs com regra/funcionalidade foram para ti), o revisor rejeitou 6 vezes com razão. O #23 mostra que, mesmo para correcções, entrar contigo não custou nada esta semana.
2. **Decidir os AIRMETs** (prioridade 1). Opção mínima, sem mexer em regras de decisão: com AIRMET em vigor, o veredicto e a faixa deixam de dizer GO "limpo" (ex.: "GO — AIRMET em vigor"). Opção completa (4.0): AIRMET com área legível → fenómeno com as regras normais, como os SIGMETs da 3.0.
3. **Escrever no `CLAUDE.md` a regra "LCA não suaviza a base de nuvem"** (só a VIS LCA < 1500 m é MARGINAL). Os pilotos levantaram a dúvida em 4 dias; a app e eles concordam, mas a tabela só o diz por omissão. Confirma primeiro que é mesmo essa a intenção (base LCA < 300 ft → NO-GO).
4. **Agente `piloto`:** (i) dizer-lhe explicitamente que a Secção II não entra na decisão (causa de 18 dos 19 falsos alarmes); (ii) não escrever totais, ou contá-los da tabela (3 deslizes); (iii) para o manter às cegas, passar-lhe só a tabela de regras e a secção "Geografia" do `CLAUDE.md`, não os casos concretos.
5. **Agente `editor`:** quando devolver PRECISA DO DUARTE, correr na mesma o revisor antes de te passar o PR (o #21 entrou sem revisão independente).
6. **Prioridades da W44:** (i) AIRMETs; (ii) retomar ou arquivar o L9 (`ENTIRE FIR`) com a alternativa simples "linha com ENTIRE FIR → linha inteira em toda a FIR + aviso"; (iii) níveis dos SIGMET acima de FL150; (iv) alerta de recolha (> 1 h sem resposta do IPMA); (v) faixa "ACTIVO (fora da área)"; (vi) actualizar o número de testes no `CLAUDE.md` (1270 → 1272 recolhidos).

## h. Decisões do Duarte

**Nesta semana**

- 19-out: `S BTN` → **opção (b)** (união com o semiplano + aviso); **coordenadas de SIGMET só com graus** aceites como `nn°00'`; **excepção ao merge automático para erros CRÍTICOS** (variante mais conservadora entra sozinha). Tudo na 3.5 (#18).
- 20-out: confirmaste que o IPMA não emitiu o 200300; pediste a **nota de nuvens baixas na Secção II** (3.6, #19).
- 21-out: #21 **opção 1** (aceitar a nota da Secção II com AS/AC contra o MEF); pediste o **aviso "Campo não interpretado"** (3.9, #22) e lançar tudo no mesmo dia (3.10, #23); `MT OBSC: NIL`/abertura vazia **ficam conservadores**; 2.º valor ilegível **fica de fora**; âmbito do #24 reduzido a `ENTIRE FIR`.
- 22-out: **#24 em pausa** (fechado; não retomar automaticamente).
- 23-out: correcção do vocabulário do `analisar.py` (#25).

**Pendentes**

1. **AIRMETs**: interpretar (4.0) ou, no mínimo, não mostrar GO "limpo" com AIRMET em vigor? (W42 h.4; caso real a 25-out.)
2. Níveis dos SIGMET acima de FL150: deixam de contar para VFR? (W42 h.3.)
3. `ENTIRE FIR` a meio da linha (L9): retomar com a alternativa simples?
4. Confirmar "LCA não suaviza a base" e escrevê-lo no `CLAUDE.md` (g.3).
5. Faixa "SIGMET ACTIVO" para SIGMETs fora da área; motivo "SIGMET T01" em Cascais (19-out, P3/P4).
6. Seguimento antigo do revisor do #12 (parar o boletim antes de boletins de outras FIR numa página sem `<pre>`) e alerta de recolha (W42 g.4).
