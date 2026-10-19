# Relatório semanal — 2026-W42 (12 a 18 de Outubro de 2026)

O primeiro relatório semanal. A recolha arrancou a 14-out às 18:25Z e o teste contínuo oficialmente a 15-out, por isso a semana tem 4,5 dias de dados. O processo com agentes só começou a 18-out e tem **um** dia de dados. Não há semana anterior para comparar. Uso o dia 19-out (início da W43) só como segundo ponto de referência e digo-o sempre que o faço.

Fontes: relatórios diários de 14 a 18-out (só o de 18 tem "Métricas"), os PRs #1–#17 e os comentários do revisor, as 23 execuções do workflow "Testes", o histórico de `main` e `dados`, e o arquivo `gamets/` e `sigmets/`.

## a. Resumo executivo

- **A app ficou bastante mais fiável durante a semana, mas ainda não está fiável o suficiente para dispensar a leitura do GAMET.**
  - Entre a 1.4 e a 3.4 corrigiram-se **3 erros optimistas com efeito real**: CB embebido ignorado, SIGMETs sem "=" invisíveis e base sem AGL ignorada.
  - Corrigiram-se também **4 erros optimistas latentes**, mais 4 pessimistas e 3 de apresentação.
  - 6 dos ~14 erros tiveram a mesma origem: **os qualificadores geográficos**. É aí que continua o risco: hoje (19-out) apareceu outro formato novo, `S BTN`.
- **O processo com agentes funciona, mas ainda não provou valor próprio.** Num dia útil (18-out) os pilotos concordaram com a realidade em 100% das diferenças (0 falsos alarmes). O erro crítico que apanharam, porém, também já estava assinalado pelo `analisar.py`.
- **O merge automático comportou-se bem:**
  - 2 merges automáticos, ambos correctos; 0 reversões; `main` sempre verde.
  - O revisor travou 3 regressões optimistas antes de entrarem.
  - Tudo o que mudava regras foi para o Duarte, como devia.
- **Recomendação principal:** manter o merge automático. Prioridade da W43: fechar a família "qualificadores geográficos" (P1 de hoje). O caso SIGMET sem minutos e o dos níveis dos SIGMET (que vão continuar a aparecer com a série U oceânica) também precisam da tua decisão.

## b. Recolha

### Por dia (data de arquivo)

| Dia | GAMETs | AMD/COR | SIGMET/AIRMET | Linhas em `falhas.log` | Das quais anormais |
|---|---|---|---|---|---|
| 14 (a partir das 18:25Z) | 2 | 0 | 0 | 0 | 0 |
| 15 | 4 | 0 | 0 | 6 | 0 |
| 16 | 4 | 0 | 0 | 16 | 0 |
| 17 | 4 | 0 | 3 (SIGMET T01, T02; AIRMET 1) | 26 | 19 |
| 18 | 4 | 0 | 4 (SIGMET T01, T02, U01, U02) | 12 | 0 |
| **Total** | **18** | **0** | **7 (6 SIGMET, 1 AIRMET)** | **60** | **19** |

As linhas "normais" são a janela de ~30–45 min em que o IPMA retira o GAMET antes de publicar o seguinte, e nela a app recorre ao arquivo (1.6). Nenhum boletim foi parar a `sigmets/desconhecidos/` depois da 2.7.

### Buracos e falhas

1. **15-out:** o agendamento do GitHub falhou (intervalos de 2h17 e 5h20 em vez de 1 h). O GAMET 150900 só foi arquivado às 13:17Z, 4 h depois de entrar em vigor.
   - Correcção: PR #2 (duas vezes por hora) e, no mesmo dia, PR #3 (**recolha em cadeia**). Desde aí todos os GAMETs foram arquivados 6–20 min antes de entrarem em vigor.
2. **17-out, 12:14–17:28Z: 5h15 sem resposta de nenhum endpoint do IPMA** (19 linhas "nenhum endpoint").
   - O GAMET 171500 e o SIGMET T02 só foram arquivados às 17:30, este 3h30 depois de entrar em vigor.
   - Causa por apurar: IPMA em baixo ou bloqueio dos IPs do GitHub.
   - A app falhou em voz alta (sem GAMET → sem GO), como devia.
   - Mas **ninguém foi avisado durante a falha**: só se soube no relatório do dia seguinte.
3. 18-out: nada a assinalar. SIGMETs arquivados 0–10 min depois de entrarem em vigor.

### Workflows

- **"Recolha GAMET LPPC":** `active`. A cadeia funciona: cada execução dura ~5h30 e lança a seguinte. As do `schedule` aparecem `cancelled`, o que é o grupo de concorrência a funcionar.
- **"Testes":** criado a 17-out (#11). **23 execuções, 23 verdes**, incluindo os 4 merges no `main`.
- **"Publicar protótipo NiceGUI":** `active`.

## c. Qualidade da app

Versões da semana: 1.4 → 1.5 → 1.6 → 2.0 → 2.1 → 2.3 → 2.5 (com 2.4) → 2.6 → 2.7 → 3.0 → 3.1 → 3.2 → 3.3 → 3.4. São 13 versões em 5 dias e os testes passaram de 346 para 590.

### Erros encontrados, por gravidade

**CRÍTICOS: optimistas, com efeito real**

| # | Erro | Boletim real | Efeito | Estado |
|---|---|---|---|---|
| C1 | `ISOL/EMBD TCU/CB` em SIG CLD sem TS em SIGWX → GO | GAMET 160300/160900 | 9 aeródromos do NE em GO com CB embebido, sem menção | Corrigido na **2.0** (#5, mudança de regra, Duarte, 16-out 09:42) |
| C2 | SIGMET/AIRMET sem "=" final não eram lidos | SIGMET T01 171010/171410 e AIRMET 1 | A app mostrava "sem SIGMET" e a faixa **NIL** com um SIGMET EMBD TS em vigor | Corrigido na **2.7** (#12, **merge automático**, 17-out 17:30) |
| C3 | Base de SIG CLD sem AGL/AMSL ignorada | GAMETs 172100/180300 e 180300/180900 (`LCA BKN 002-008/010HFT`) | 26 aeródromo×GAMET em MARGINAL em vez de NO-GO | Corrigido na **3.3** (#14, Duarte escolheu AGL, 18-out 10:24) |

**Optimistas latentes: formato real, sem efeito na decisão nesse dia**

| # | Erro | Boletim real | Estado |
|---|---|---|---|
| L1 | VIS sem unidade (`LCA 5000 RA`). Um `LCA 1200 BR` desaparecia | GAMET 161500 | 2.5 (#9) |
| L2 | `BTN N4050 - N3840` com hífen não lido; a subentrada herdava a área anterior | GAMET 171500 | 3.1 (#15, **automático**) |
| L3 | Subentrada com área ilegível herdava em silêncio a área anterior | (o mesmo) | 3.4 (#17): toda a FIR + aviso |
| L4 | `NW OF W00800` lido como `W OF W00800` (diagonais sem `\b`) | encontrado pelo revisor, sem caso real | 3.4 (#17) |

**Pessimistas (MENOR)**

| # | Erro | Boletim real | Estado |
|---|---|---|---|
| P1 | `N OF … AND W OF …`: o segundo qualificador substituía o primeiro | GAMET 142100 | 1.5 (#1) |
| P2 | `BTN … AND … E OF …` sem AND: o BTN perdia-se (NO-GO em Faro, Beja, Bragança…) | GAMETs 162100, 170300 | 2.3 (#8) |
| P3 | Qualquer SIGMET → NO-GO em toda a FIR | SIGMET T01/T02 de 17-out | 3.0 (#13, mudança de regra, Duarte) |
| P4 | SIGMET referido mas já terminado continuava a pôr toda a FIR NO-GO | GAMET 171500 + T02 depois das 18Z | 3.2 (#16, mudança de regra, Duarte) |

**Apresentação (MENOR)**

- Janela `HH/HH` atribuída à subentrada anterior: um CB das 12–15Z aparecia como "09–11Z, já terminou". Corrigido na 2.3.
- Cartão GO de 45 km² junto ao Minho: 2.0.
- Motivos de regiões fundidas juntados. Corrigido em parte na 3.2. Hoje (19-out) voltou a aparecer um caso: "SIGMET T01" nos motivos de Cascais.
- Cartões sem pontos de 0,0–0,1% junto a Viana do Castelo (17-out): pendente, sem importância.

### Formatos novos vistos na semana

- `LAN AND COT LCA` repetido (150300): lido bem.
- `SIG CLD::` com dois pontos duplicados (170900): lido bem.
- VIS sem unidade: L1.
- `BTN … - …` com hífen: L2.
- Base `HFT` sem referência: C3.
- SIGMET/AIRMET sem "=": C2.
- Primeira série **U** de SIGMETs: TURB SEV oceânica a FL230–440, longe da costa. Área legível no U01.
- Já na W43:
  - coordenada de SIGMET só com graus (`W018`) → toda a FIR NO-GO (pessimista);
  - `S BTN …` (ambíguo).

### Fenómenos ou campos ainda não cobertos

- **AIRMET:** mostrado, não interpretado. Só apareceu 1 na semana (TURB MOD, coerente com a decisão).
- **Níveis dos SIGMET** (`FL230/440`, `TOP FL420`): não restringem a decisão. Com a série U oceânica isto vai pesar cada vez mais, quando uma área for ilegível ou tocar a FIR continental.
- **WIND/T em altitude** (até 35 kt a 1000–2000 ft em Viseu em vários dias): não entra, por regra (só SFC WSPD).
- **Secção II** (CLD, PSYS): não entra, por regra.

### Padrões repetidos

1. **Qualificadores geográficos:** P1, P2, L2, L3, L4 e, hoje, o `S BTN`. O IPMA escreve as áreas com muita liberdade (AND opcional, hífen, cardinais soltos). Cada formato novo, até agora, foi lido em silêncio de forma errada, em vez de dar aviso. A 3.4 começou a inverter isto: área ilegível → toda a FIR + aviso. A família ainda não está fechada.
2. **Campos que desaparecem em silêncio:** C1, C3 e L1. O alerta "campo sem fenómeno" do `analisar.py` apanhou o C3. O C1 e o L1 escapavam-lhe.
3. **SIGMETs:** C2 e P3/P4. O primeiro contacto com boletins reais (17-out) revelou dois problemas no mesmo dia.

## d. Avaliação do processo com agentes

O processo entrou no `main` a 17-out às 11:22 (#11). O primeiro relatório com pilotos e comparadores é o de 18-out. Os números da W42 são de **um único dia**. O dia 19-out vai entre parênteses como referência (é W43).

| Medida | W42 (18-out) | (19-out) |
|---|---|---|
| GAMETs analisados | 4 | 4 |
| Aeródromos comparados | 208 | 208 |
| Concordância parser × piloto | 182/208 = **87,5%** | 207/208 = 99,5% |
| Diferenças: parser optimista | 26 (1 causa: C3) | 0 |
| Diferenças: parser pessimista | 0 | 0 |
| Diferenças: erro do piloto | 0 | 1 (LPPT "por prudência" em COT) |
| Diferenças: ambíguo | 0 | 0 (mais 1 ambíguo sem diferença) |
| **Taxa de falsos alarmes** (erros do piloto ÷ diferenças) | **0%** (0/26) | 100% (1/1) |
| Erros do parser apanhados pelo piloto que o `analisar.py` não apanharia | **0**: o C3 já tinha o alerta "campo sem fenómeno" | 0 |
| Erros apanhados pelo comparador por iniciativa própria | 1 (L2, ao investigar a palavra desconhecida "-") | 1 caso ambíguo (`S BTN`), que nenhum alerta automático apanha |
| Agentes lançados / com falha | 12 / 0 (1 deslize de contagem) | 6 / 0 (1 deslize de contagem) |
| Tempo da tarefa | ~38 min | ~35 min |

**Leitura honesta:**

- **Valor acrescentado ainda por demonstrar.** Na W42 o piloto não apanhou nenhum erro que o script não apanhasse. Confirmou e quantificou o C3 (26 aeródromos), o que deu confiança para o classificar como CRÍTICO. O valor real até agora veio mais do **comparador** (L2 na W42, `S BTN` na W43), que investiga os casos limite, do que do piloto.
- **O C1 (CB em SIG CLD) é o caso de referência.** Foi apanhado só por revisão manual, a 16-out, antes dos agentes. O `analisar.py` não o via, porque o campo gerava a base. É exactamente o tipo de erro que o piloto deve apanhar. Mantém-se a aposta.
- **Os pilotos ficaram às cegas quanto ao resultado da app.** Receberam só o texto do GAMET e o caminho do repositório, e declaram ter lido apenas o `CLAUDE.md` e as coordenadas. Mas o `CLAUDE.md` descreve as convenções da app (base sem referência = AGL, MOD/SEV = SEV…). O piloto não é independente das **regras**, e isso é desejável. Já não seria se o `CLAUDE.md` passasse a descrever casos concretos de forma que o piloto copie a leitura da app. Até agora não se viu isso.
- **Dois deslizes de contagem em 8 pilotos** (totais que não batem com as listas). Não afectam decisões, mas sujam as métricas.

## e. Merge automático, PR a PR

A regra existe desde o #11 (17-out 11:22). Os PRs #1–#10 foram anteriores e foste tu a integrá-los.

| PR | Versão | Como entrou | Revisor | Mais permissivas na comparação de versões | Comentário |
|---|---|---|---|---|---|
| #12 | 2.7 SIGMET sem "=" (C2) | **Automático**, 17-out 17:30 | APROVADO (463/463; 4 dos 6 testes novos falham no `main`) | 0 | Correcto. Era um erro CRÍTICO activo, e entrar sem esperar foi o comportamento certo |
| #13 | 3.0 SIGMET só na sua área | Duarte, 17-out 18:10 ("[Precisa do Duarte]": mudança de regra) | **3 REJEITADOS** (FCST AT, polígono que se cruza, coordenadas mistas, margem < 10 NM, MOV desde OBS AT, hora inválida), depois APROVADO | **70, provadas**: todas a > 10 NM do SIGMET (mín. 14,0 NM) e iguais à decisão do GAMET sozinho | O revisor apanhou 6 casos optimistas antes de entrarem |
| #14 | 3.3 base sem AGL/AMSL (C3) | Duarte, 18-out 10:24 | DÚVIDA (AGL ou AMSL?) | 0 (26 mais severas, as pretendidas) | A dúvida era legítima. Mas o erro CRÍTICO ficou no `main` **mais 3 h** depois de ter a correcção pronta (ver g) |
| #15 | 3.1 BTN com hífen (L2) | **Automático**, 18-out 07:33 | APROVADO | 0 / 0 | Correcto. Mudou só a geometria de 1 bloco, verificada contra o texto |
| #16 | 3.2 SIGMET terminado; motivos | Duarte, 18-out 09:48 | 3 rondas corrigidas; DÚVIDA só por ser mudança de regra | **216, provadas**: todas o caso pretendido (T02 expirado às 18Z) | Correcto |
| #17 | 3.4 área ilegível → toda a FIR; diagonais | Duarte, 19-out 06:31 (combinado) | Versão completa **DÚVIDA**: `SW OF` passava a `W OF` e Bragança ia de NO-GO a MARGINAL. Reduzida → APROVADO. Diagonais 9c86865 **DÚVIDA** (6 mais permissivas no fuzz) → 0767f53 APROVADO | 0 / 0 em 19 GAMETs reais; fuzz 2 000 + 10 800 sem nenhuma mais permissiva | O revisor travou 2 regressões optimistas introduzidas pela própria correcção |

- **Reversões:** 0. O `main` nunca esteve vermelho.
- **Qualidade dos veredictos do revisor:** não há caso conhecido em que tenha aprovado algo que não devia, nem rejeitado algo certo. Encontrou **8+ problemas optimistas reais** em código novo (#13 e #17), quase todos com fuzz próprio. Foi a peça mais valiosa do processo nesta semana.
- **Decisões mais permissivas da semana:** 286 (70 + 216), todas em mudanças de regra que tu aprovaste, e todas provadas. Nenhuma em merges automáticos.

## f. Riscos e incidentes

Situações em que a app publicada esteve **mais permissiva** do que devia, com dados reais:

1. **C1, 16-out 03:00–09:00Z (6 h, toda a validade do GAMET 160300):** GO em Bragança, Chaves, Vila Real, Mirandela, Mogadouro, Viseu, Seia, Cabeceiras e Cabeço da Vaca, com `ISOL/EMBD TCU/CB` previsto. A correcção (2.0) entrou às 09:42, depois de a validade acabar.
2. **C2, 17-out ~10:10–17:30Z:**
   - Com o GAMET 170900 (SIGMET NIL), a app ignorava o SIGMET T01 (EMBD TS, NE) e mostrava a faixa **NIL**.
   - Na decisão o efeito foi limitado. O próprio GAMET 170900 já punha TS/CB `ISOL/EMBD` a E de 8°W (NO-GO no NE). A parte exposta foi a faixa "NIL" e a fatia do T01 + 10 NM fora da zona de TS do GAMET. Não refiz o cálculo aeródromo a aeródromo com a 2.6.
   - O T01 terminou às 14:10. Depois disso, com a falha do IPMA e sem o GAMET 171500, a app já não mostrava GO.
   - Exposição efectiva: **~4 h**.
3. **C3, 17-out ~20:46Z a 18-out 10:24Z (~13h40):** GAMETs 172100 e 180300. Nevoeiro com base a 200 ft dava MARGINAL em vez de NO-GO em 26 aeródromo×GAMET (Lisboa, Cascais, Santarém, Ponte de Sor, Faro, Portimão…). Foi sobretudo de noite, mas inclui 06–09Z de 18-out.
4. **Latentes (L1–L4):** sem exposição real conhecida.

Riscos que continuam abertos (W43):

- **`S BTN`** (19-out): se a intenção era "S OF N3800", Faro, Portimão e Lagos estiveram em GO com previsão de base a 200 ft das 23 às 03Z. Fica AMBÍGUO, para tu decidires.
- **Falha do IPMA sem alerta:** uma interrupção de horas só se descobre no relatório do dia seguinte.
- **Níveis dos SIGMET não usados:** hoje é pessimista. Não há caso optimista conhecido.

## g. Recomendações

1. **Manter o merge automático tal como está.**
   - 2 de 2 correctos.
   - As salvaguardas (mudança de regra → Duarte; mais permissivas por provar → Duarte) funcionaram nos 4 casos em que deviam.
   - O revisor está a fazer o trabalho pesado bem.
2. **Ajuste a considerar (decisão tua):**
   - **Caso:** erro **CRÍTICO** confirmado cuja correcção só torna decisões **mais severas** (0 mais permissivas), mas com uma escolha entre duas leituras conservadoras (caso do #14).
   - **Proposta:** permitir o merge automático da variante **mais conservadora** e perguntar-te depois.
   - **Porquê:** o #14 deixou um erro crítico 3 h a mais em produção à espera de uma escolha entre duas opções seguras.
3. **Agente `piloto`:**
   - Pedir-lhe que **não escreva totais**, ou que os conte da tabela, para acabar com os deslizes de contagem.
   - Dizer-lhe explicitamente que `COT` é uma faixa de 10 km da costa atlântica e que os estuários contam como terra. Está no `CLAUDE.md` só de forma indirecta, e foi a causa do único falso alarme.
4. **Alerta de recolha:** quando `falhas.log` tiver mais de ~1 h seguida de "nenhum endpoint", a recolha (GitHub Actions) devia abrir uma issue ou mandar notificação. O buraco de 17-out só se viu no dia seguinte.
5. **`analisar.py`:**
   - acrescentar "-" ao vocabulário (falso positivo repetido em 18 e 19-out);
   - acrescentar um alerta para cardinal solto antes de `BTN`/coordenada (assinatura do `S BTN`).
6. **Prioridades da W43:**
   - (i) decidir e corrigir o `S BTN` (P1 de 19-out);
   - (ii) coordenadas de SIGMET sem minutos (P2 de 19-out);
   - (iii) decidir se os níveis dos SIGMET (FL > 150) devem passar a excluir o SIGMET da decisão VFR. Seria a 4.0, mudança de regra;
   - (iv) decidir se queres interpretar AIRMETs (funcionalidade nova: não implementei, só pergunto);
   - (v) actualizar no `CLAUDE.md` o número de testes (diz 595; são 590 + 1 saltado).

## h. Decisões do Duarte

**Nesta semana**

- 14-out: aprovar a 1.5 (AND entre qualificadores).
- 15-out:
  - recolha duas vezes por hora (#2);
  - recolha em cadeia (#3);
  - arquivo de GAMETs com recurso entre emissões (#4, 1.6).
- 16-out:
  - **CB em SIG CLD, opção (b)**: ISOL → MARGINAL; EMBD/OCNL/FRQ → NO-GO; TCU sozinho não conta (#5, 2.0);
  - juntar as bolsas a < 25 km;
  - arquivo sem hora de recolha (#6).
- 17-out:
  - redesenho para telemóvel (#7/#9);
  - NiceGUI passa a interface principal (#10, 2.6);
  - **relatório com agentes e merge automático** (#11);
  - **SIGMET só na sua área + 10 NM** (#13, 3.0).
- 18-out:
  - **base sem referência = AGL** (#14, 3.3);
  - **SIGMET referido já terminado deixa de contar** (#16, 3.2);
  - **área ilegível → toda a FIR + aviso, e diagonais** (#17, 3.4, integrado a 19-out 06:31 como combinado).

**Pendentes**

1. `S BTN N3720 - N3800` (relatório de 19-out, P1): opção (a), (b) ou (c)? Recomendo a (b).
2. Coordenadas de SIGMET sem minutos (`W018`) (relatório de 19-out, P2): aceitar como `nn°00'`?
3. Níveis dos SIGMET acima de FL150: devem deixar de contar para VFR?
4. AIRMETs: queres que passem a ser interpretados?
5. O ajuste ao merge automático da recomendação g.2.
6. Seguimento antigo do revisor do #12: parar o boletim antes de boletins de outras FIR numa página sem `<pre>`. Ainda não feito.
