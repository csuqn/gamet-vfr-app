# Relatório semanal — 2026-W45 (2 a 8 de Novembro de 2026)

Terceira semana completa do processo com agentes. Para comparar, uso a W44.

**Fontes:**
- os relatórios diários de 03-nov a 09-nov, que cobrem as 24 h anteriores e portanto os dias 2 a 8, com as adendas de 02, 03 e 04-nov;
- os PRs #33 a #44 e os comentários do revisor;
- as execuções do workflow "Testes" no main (todas verdes);
- o histórico de `main` e de `dados`;
- o arquivo `gamets/`, `sigmets/` e `falhas.log`;
- o relatório W44.

## a. Resumo executivo

- **Nenhuma decisão de voo esteve errada nesta semana.** Em 28 GAMETs e 1456 comparações aeródromo a aeródromo, o parser e o piloto concordaram a 100% (na W44, 97,3%).
- **Entraram 9 versões (4.5.1 → 4.7.4) e hoje a 4.7.5.** Duas eram erros optimistas latentes: o topo com duas barras e o `SFC WIND`. Outra era um erro optimista real na interface NiceGUI (pickle, 4.6.1). As restantes foram pedidos teus: calendário, motivos e notas das regiões fundidas, e Streamlit como principal.
- **Pior incidente: a NiceGUI (então a interface principal) ficou de 26-out a 3-nov sem mostrar o briefing quando havia AIRMETs lidos.** Ficava no ecrã o briefing anterior, que podia ser mais permissivo. O Streamlit não foi afectado. Foi corrigido na 4.6.1, com merge automático.
- **O valor desta semana veio do `analisar.py` e das verificações manuais e do revisor**, não do piloto: o piloto não encontrou nenhum erro sozinho. O `SFC WIND` foi apanhado pelo vocabulário do `analisar.py`; a superfície a meio da linha, pelo piloto (como dúvida) e pelo comparador.
- **Merge automático:** 4 merges (#34, #37, #39, #40) mais o #43 hoje. Todos correctos, 0 reversões, main sempre verde. O que era regra ou leitura ambígua ficou contigo.
- **Recomendação principal:** manter o merge automático e decidir o PR #44. Como prioridade técnica, uma lista de nomes de campo do Anexo 3 que o parser reconheça ou assinale. O `SFC WIND` mostrou que um nome de campo novo pode passar em silêncio.

## b. Recolha

### Por dia (data de recolha)

| Dia | GAMETs | AMD/COR | SIGMET/AIRMET | Linhas em `falhas.log` | Anormais |
|---|---|---|---|---|---|
| 02 | 4 | 0 | 1 SIGMET | 12 | 0 |
| 03 | 4 | 0 | 3 SIGMET | 10 | 0 |
| 04 | 4 | 0 | 0 | 9 | 0 |
| 05 | 4 | 0 | 4 SIGMET | 12 | 0 |
| 06 | 4 | 0 | 5 SIGMET | 11 | 0 |
| 07 | 4 | 0 | 3 SIGMET | 10 | 0 |
| 08 | 4 | 0 | 6 SIGMET | 23 | 11 `ConnectTimeout` (20:53–23:47Z; continuou até 09-nov 02:24Z, 20 no total) |
| **Total** | **28** | **0** | **22 SIGMET, 0 AIRMET** | **87** | **11 (+9 no dia 9)** |

- **Sem buracos de GAMET:** todos os períodos de 6 h têm o seu GAMET.
- **Falha de ligação ao IPMA** de 08-nov 20:53Z a 09-nov 02:24Z (~5 h 30). Não se perdeu nenhum GAMET. Pode faltar o **SIGMET T06** de 8-nov (a numeração salta do T05 para o T07). É só informação; não há nada a fazer do nosso lado.
- Na W44 houve 40 falhas anormais (2 episódios); nesta semana, 1 episódio.
- `sigmets/desconhecidos/`: nunca foi criado. Não apareceu nenhum formato de SIGMET inesperado.
- **Workflows:** "Recolha GAMET LPPC", "Testes" e "Publicar protótipo NiceGUI" estão activos. A cadeia de recolha não parou.
- **SIGMETs:**
  - quase todos são EMBD TS ou SEV TURB oceânicos (séries T/U, perto da Madeira e a SW);
  - a 8 e 9-nov houve pela primeira vez na semana SIGMETs sobre o continente (T03 a W da costa, T01/T02 de 9-nov e U01 SEV TURB FL230/340);
  - todos foram lidos com área e MOV e ficaram em NO-GO só na sua área;
  - **não houve nenhum NO-GO falso em toda a FIR** (na W44 houve 15 h, por causa dos `OF LINE` e do `S OF N33`).

## c. Qualidade da app

### Erros encontrados (2–9 nov)

| # | Data | Gravidade | Erro | Boletim real | Estado |
|---|---|---|---|---|---|
| F1 | 03-nov | **CRÍTICO (interface)** | NiceGUI: resultado com AIRMETs lidos não passava por pickle → briefing anterior no ecrã, ou "A carregar…" para sempre | GAMET 251500 + AIRMET 1 e 2 (arquivo) | Corrigido na 4.6.1 (#37, automático) |
| F2 | 05/06-nov | CRÍTICO latente | Topo com duas barras (`060-090/100/130HFT`): a base desaparecia em silêncio. Em SIG CLD dava GO | GAMET 060300 (Secção II) | Corrigido na 4.7.2 (#40, automático) |
| F3 | 07-nov | MENOR (apresentação) | Região fundida mostrava "CB ISOL" em pontos fora do CB | GAMET 061500 | Corrigido na 4.7.3 (#41, pedido teu) |
| F4 | 08-nov | MENOR (apresentação) | Notas "apenas sobre a costa e o mar" passavam para a região inteira | GAMET 061500 | Corrigido na 4.7.4 (#42, pedido teu) |
| F5 | 09-nov | CRÍTICO latente | `SFC WIND:` (nome do Anexo 3) ignorado em silêncio. Depois de outro campo, recortava-o | GAMETs 081500 e 082100 | Corrigido na 4.7.5 (#43, automático, hoje) |
| F6 | 09-nov | CRÍTICO latente | Superfície a meio da linha (`… AGL MAR AND COT ISOL/EMBD TCU/CB`) recorta o valor anterior | GAMET 081500 | **PR #44, contigo** |
| F7 | 03-nov | latente (interface) | NiceGUI: com duas análises sobrepostas, ganha a última a acabar | — (atraso artificial) | Pendente, sem PR |

Também entraram nesta semana, vindos da W44: a 4.5.1 (margem do SIGMET, #34, 2-nov), a 4.5.2 (BTN degenerado e COT em km, #35, pedido teu) e a 4.6 (graus sem minutos nos SIGMET, #33, OK teu).

### Formatos novos

- `060-090/100/130HFT` (duas barras no topo).
- `SFC WIND:` na Secção I.
- `W015` só com graus num polígono WI (T07; a 4.6 já o lê).
- A superfície depois do valor, a meio da linha.

### Fenómenos ainda não cobertos ou por decidir

- Os níveis dos SIGMET (`FL230/340`, `TOP FL380`) não restringem a decisão. O U01 de 9-nov (SEV TURB FL230/340) pôs NO-GO a 32 pontos, que já estavam em NO-GO pelo GAMET. Num dia calmo seria NO-GO por turbulência a FL230. É conservador, mas é um pendente teu desde a W42.
- `MOD/SEV` é sempre lido como SEV. Foi o que decidiu os 4 GAMETs de 8-nov: com MOD, uma parte ficaria GO ou MARGINAL. Os 4 pilotos fizeram a mesma leitura.

### Padrões repetidos

- **A forma como o IPMA escreve muda aos poucos:** `HTF`, intervalos no topo, duas barras e agora `SFC WIND`. Cada variação nova tende a passar em silêncio até alguém a notar. O vocabulário do `analisar.py` tem sido a rede de segurança.
- **A estrutura das linhas** (janela ou superfície a meio) continua a ser a área mais delicada (4.1, 4.3 e agora #44).

## d. Avaliação do processo com agentes

| Medida | W45 | W44 |
|---|---|---|
| GAMETs comparados | 28 | 28 |
| Aeródromos comparados | 1456 | 1456 |
| Em desacordo parser × piloto | **0** | 39 |
| Concordância | **100%** | 97,3% |
| Parser optimista (decisão) | 0 | 37 |
| Parser pessimista | 0 | 0 |
| Erro do piloto | 0 | 2 |
| Ambíguo | 0 | 0 |
| Falsos alarmes (erros do piloto ÷ diferenças) | — (0/0) | 5% |
| Erros do parser apanhados pelo piloto e não pelo `analisar.py` | 0 com efeito na decisão. 1 latente (F6), que o piloto assinalou como dúvida e o comparador confirmou | 1 (crítico) |
| Erros do parser fora da comparação | F2 (verificação manual), F5 (`analisar.py`) e F6 (comparador) | E3, E4, E6 |
| Agentes lançados | ~55 (28 piloto, ~15 comparador, 4 editor, ~8 revisor) | ~70 |
| Agentes falhados ou com resposta incompleta | 0. Houve 2 editores interrompidos e retomados a 2-nov, 1 lapso de contagem num piloto e 1 ficheiro de saída da app truncado por mim (detectado pelo comparador) | 0 |
| Tempo da tarefa diária | 11–20 min nos dias sem correcção; 1 h 25 a 3 h 20 com correcção | 12–50 min; ~2 h 15 |

**Leitura dos números:**
- **Concordar a 100% não prova que o piloto não seja útil.** A meteorologia da semana foi muito "binária": 16 dos 28 GAMETs tinham ≥ 95% da área com uma só decisão. Nenhum GAMET pôs à prova as fronteiras finas, como na W44.
- **O comparador continua a ir além do que lhe pedem.** Hoje verificou no código se o `SFC WIND` era lido e se a superfície recortava o BKN. Foi assim que apareceu o F6.
- **Os editores ficaram mais lentos:** ~50 e ~65 min hoje. As correcções incluem agora cópias de referência, comparação com o arquivo e geradores. Isto dá qualidade, mas o tempo da tarefa diária sobe para mais de 3 h nos dias com 2 correcções.
- **Às cegas:** os pilotos receberam só o texto do GAMET e o caminho do repositório, e declaram que não leram saídas da app. Nada indica que tenham visto resultados do parser.
- **Lição para mim (orquestração):** o ficheiro de saída da app que dou ao comparador não deve cortar motivos.

## e. Merge automático, PR a PR

| PR | Versão | Entrada | Porquê | Revisor | Comparação de versões |
|---|---|---|---|---|---|
| #34 | 4.5.1 | automático (2-nov) | erro optimista latente da margem do SIGMET; correcção | APROVADO | 0 mais permissivas (já no W44) |
| #35 | 4.5.2 | a teu pedido (2-nov) | BTN degenerado + COT em km | APROVADO | 0 mais permissivas; 17 244 pontos da grelha mais severos (faixa COT) |
| #33 | 4.6 | OK teu (2-nov) | graus sem minutos nos SIGMET | DÚVIDA → APROVADO (2.ª ronda) | **153 mais permissivas, provadas** (só o T02/T03 oceânicos de 1-nov) |
| #37 | 4.6.1 | automático (3-nov) | erro da NiceGUI (F1); correcção | APROVADO (browser, fork/spawn/forkserver) | 0/0 |
| #36 | 4.7 | merge teu (3-nov, 22:25Z) | calendário (funcionalidade, pedido teu); o merge foi bloqueado pelas permissões da sessão | DÚVIDA → APROVADO | 0/0 no motor |
| #38 | — | teu (3-nov) | documentação: Streamlit volta a principal | — | — |
| #39 | 4.7.1 | automático (4-nov) | texto do motivo (pedido teu, sem mudar decisões) | APROVADO | 0/0 |
| #40 | 4.7.2 | automático (6-nov) | erro optimista latente (F2) | APROVADO | 0/0 |
| #41 | 4.7.3 | 8-nov, fora da tarefa diária | motivos de regiões fundidas (F3, pedido teu) | APROVADO | 0/0 |
| #42 | 4.7.4 | 8-nov, fora da tarefa diária | notas de regiões fundidas (F4, pedido teu) | APROVADO | 0/0 |
| #43 | 4.7.5 | automático (hoje) | `SFC WIND` (F5) | APROVADO | 0/0 no arquivo; 21 mais permissivas em casos sintéticos, provadas (a 4.7.4 colava o vento ao campo anterior) |
| #44 | 4.7.6 | **contigo** | superfície a meio da linha (F6): escolha de leitura | **DÚVIDA** | 0/0 |

- **Reversões: 0.** O main esteve verde em todas as execuções do workflow "Testes".
- **Qualidade dos veredictos do revisor:**
  - não aprovou nada que tenha falhado depois;
  - no #33 e no #36 travou por razões certas: a margem ainda não estava provada, e o erro do pickle;
  - no #44 identificou que a variante não é a que serve para as duas leituras, e por isso não entrou pela excepção crítica.
  - Não vi nenhuma rejeição errada.
- **Decisões mais permissivas na semana:** 153 do #33, confirmadas: são boletins oceânicos a 118–178 NM, que antes punham NO-GO em toda a FIR. Há ainda as 21 sintéticas do #43, provadas pelo revisor caso a caso. Não fica nenhuma por provar.

## f. Riscos e incidentes

1. **NiceGUI sem briefing com AIRMETs (26-out → 3-nov 13:32Z).** Na interface principal da altura, um GAMET com AIRMETs lidos não mostrava o briefing novo. Colado ou do arquivo, ficava o briefing anterior: o 25/10 15–21Z mostrava o 09–15Z sem o nevoeiro dos AIRMETs. É **optimista**. O Streamlit dava a decisão certa. Durou ~8 dias, mas só se manifestava com AIRMETs em vigor ou em consultas ao arquivo de 25-out.
2. **`SFC WIND` ignorado (8-nov 14:51Z → 9-nov 09:22Z).** Nos dois GAMETs a área era mar e tudo já estava em NO-GO, por isso não teve efeito real.
3. **Superfície a meio da linha (F6) continua no main.** Só se manifesta se o valor anterior à superfície decidir (por exemplo, uma base < 500 ft). No arquivo só existe o 081500, sem efeito.
4. **Corrida da NiceGUI (F7)** continua latente. Agora é a interface de reserva.
5. **SIGMET T06 de 8-nov possivelmente em falta** no arquivo, durante a falha do IPMA. Só afecta a consulta histórica desse período, que de qualquer forma estava em NO-GO.

## g. Recomendações

1. **Manter o merge automático.** Em 3 semanas houve 9 merges automáticos e 0 reversões. A regra "na dúvida não entra" funcionou: #33, #36 e #44.
2. **Lista de nomes de campo:** o parser deve avisar quando a Secção I tem um nome de campo que não conhece (`SFC WIND` passou em silêncio porque não era campo, e por isso também não havia "Campo não interpretado"). Proposta: um aviso "Campo desconhecido" para `[A-Z ]+:` na Secção I fora da lista. Como é funcionalidade nova, **pergunto-te antes de implementar**.
3. **Decidir o #44** (ver h.1).
4. **Instruções aos agentes:** nenhuma mudança ao piloto (mantém-se a independência). No meu lado, dar ao comparador todos os motivos por ponto.
5. **Tempo dos editores:** aceitar 50–65 min por correcção. Não há razão para cortar nas comparações com o arquivo, que foram o que provou as correcções.
6. **Prioridades para a W46:** decidir os níveis dos SIGMET (pendente desde a W42) e a corrida da NiceGUI (F7).

## h. Decisões do Duarte

**Nesta semana**

- **2-nov:** "avança" com o #33 (4.6); "faz isso" ao BTN degenerado; "se ficar melhor, faz essa alteração" ao COT em km (4.5.2).
- **2/3-nov:** calendário no arquivo (4.7, #36), com merge feito por ti.
- **3-nov:** Streamlit volta a ser a interface principal (#38).
- **4-nov:** motivo de TURB/ICE/MTW só com a camada que decide (4.7.1).
- **7/8-nov:** motivos (4.7.3) e notas (4.7.4) das regiões fundidas: só pleno o que vale em toda a região.

**Pendentes**

1. **#44 (4.7.6):** em `… AGL MAR AND COT ISOL/EMBD TCU/CB …`, o CB fica só em MAR∪COT (leitura "a superfície qualifica o que vem a seguir", a escolhida) ou também em toda a área da subentrada (serve para as duas leituras, mais severa)? Há ainda dois reparos menores do revisor nos testes.
2. Aviso "Campo desconhecido" na Secção I (g.2): queres?
3. Níveis dos SIGMET acima de FL150 (desde a W42). O U01 FL230/340 de 9-nov é um exemplo.
4. Corrida da NiceGUI (F7): contador por página em `analisar_e_desenhar`?
5. Herdados da W44: `ENTIRE FIR` a meio da linha (#24 em pausa); "LCA não suaviza a base" no `CLAUDE.md`; faixa "SIGMET ACTIVO" para SIGMETs fora da área; 4.1 com superfície também na 1.ª parte; seguimentos do #12 e do alerta de recolha.
6. `S OF N38` só com graus na Secção I do GAMET (4.6 deixou-o como toda a FIR + aviso): fica para decidires.
