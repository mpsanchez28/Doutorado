# Revisão de consistência dos protocolos (ROBUSTEZ_T1_T4 × PROTOCOLO_CORRIGIDO_2021)

**Data:** 14/10/2026.

**Escopo:** revisão documental, com verificações leves e somente leitura. Nada foi coletado,
reconfigurado ou commitado; os documentos revisados **não** foram editados. Este relatório
propõe alterações. As que mudam escopo, população, regra de elegibilidade ou decisão inferencial
dependem de aprovação.

**Estado no início da revisão:**
- branch `research/t1-t4-robustez`, HEAD `0282d2f` (13:46);
- alterações locais: só os 3 arquivos do dossiê e o `CLAUDE.md` (não versionados);
- em andamento: `scripts/reconstrucao_2021_4bases.sh`, lançado às 13:41. Às 14:41 estava em
  Matemática, com Economia concluída nos dois horizontes.
- **Não foi interrompido**, mas ver o **achado A0**: os resultados dessa execução não devem ser
  usados.

**Legenda:**
- **Status:** VERIFICADO · DIVERGENTE · NÃO LOCALIZADO · PROPOSTA;
- **Impacto:** DOC (só documentação) · TESTE (verificação adicional) · DECISÃO (decisão
  científica, exige aprovação).

---

## Resolução (14/10/2026, tarde, depois das decisões do usuário)

As decisões estão consolidadas em
[ESPECIFICACAO_METODOLOGICA.md](ESPECIFICACAO_METODOLOGICA.md). O texto original da revisão
segue abaixo, sem alteração, como registro.

| Ponto | Resolução | Verificação |
|---|---|---|
| **A0 — universo** | Corrigido: `candidate_universe_at_cut` (só trabalhos das sementes do corte) e `check_candidate_universe` (aborta se algum candidato não tiver laço ≤ c com semente do corte, ou se for semente do corte). Sementes fora do corte podem ser candidatas por laço legítimo. Corrigido também em `auditoria_sorteios.py` | `tests/test_universo_candidatos.py` (5 testes, incluindo o defeito v1 detectado e a reprodução histórica como teste separado); 0 violações em todas as execuções v2 |
| A0 — execuções v1 | Reconstrução interrompida às ~15:00. Pastas preservadas com `INVALIDO.json`; registro em `runs/robustez/t4/INVALIDOS_v1.json` | — |
| A0 — corpus | Os trabalhos coletados só entram no corpus se forem de candidatos do universo v2 (antes, toda a pasta coletada entrava) | `compose_corpus` |
| A0 — coletor | Não reconsulta candidatos já consultados (lacunas anteriores ou `ids_por_lote`). Lotes com prefixo por versão. Conferência na API por execução | teste no mesmo arquivo; API: 18 e 53 créditos, iguais à contagem |
| A0 — piloto 2019 | Refeito localmente, sem coleta: universo 13.939 → 11.499 (todos já consultados). Alvos iguais (159); alcançáveis 532 → 507 | ROBUSTEZ §3.5.6; métricas idênticas em 2 execuções |
| A0 — 2021 | Lacunas recalculadas com o código corrigido: Economia 330 e Matemática 572 não consultados. Coletados (71 créditos). Reconstrução v2 nos dois horizontes | ESPECIFICACAO §7 |
| A0 — Computação e Medicina | Não coletadas: ~1,0–1,7 mil créditos, contra um saldo de 1.308 | ESPECIFICACAO §7.3 |
| 1 — estado | PROTOCOLO atualizado: coleta autorizada e executada, caminhos reais, v1 invalidada | — |
| 2 — classificação | **Reanálise retrospectiva temporal**, com a lista do que foi consultado e decidido depois. Confirmação independente fica para dados reservados futuros | ESPECIFICACAO §1 |
| 3 — validação temporal | Fase de treino com **o próprio corte**: sementes sorteadas ≤ c−3, universo com laços ≤ c−3, corpus e enriquecimento próprios. Seleção única: validação cruzada por pessoa na fase c−3, com remoção dos pares simétricos. A binária é identificada como classificador pontual. **[pendente: confirmação]**, porque substitui a validação 2015 → 2018 registrada antes | `training_phase` com asserções; ESPECIFICACAO §3 |
| 4 — denominadores | Newcomers vazios por construção (confirmado: 0); P@K com denominador K; "uso real" retirado | ESPECIFICACAO §2 |
| 5 — estatística | Por área principal; agregado 1/4 complementar; δ em pp de R@50 (10% do controle histórico); famílias F1/F2/F3; poder e precisão separados; os dois sentidos de "80%" separados | ESPECIFICACAO §4, §7.4 (poder de ~3–7% para δ em Economia e Matemática) |
| 6 — dependência | Bootstrap de Poisson por pessoa implementado; mesmo peso para a mesma identidade em todas as áreas e cortes; limites declarados; taxonomia das repetições | `tests/test_bootstrap_poisson.py` (4 testes) |
| 7 — neurais | Tabela fechada; N3 (atributo) ≠ N6 (ranqueador); contrastes da GNN com o restante constante (N3 × N0, N4 × N2a, N5 × N2b) | ESPECIFICACAO §5 |
| 8 — duas etapas | Previsões fora da amostra temporais (módulo da fase c−6 → treino; módulo da fase c−3 → teste); sem *cross-fitting* por pessoa | ESPECIFICACAO §5.1 (limitação da fase 2015 [pendente]) |
| 9 — histórico × reconstruído | Comparação principal dentro da versão; interseção como complemento | ESPECIFICACAO §6 |
| 10 — pendências | Continuam abertas: impacto do resumo nos rótulos, teto de 50, auditoria manual de identidade. **Nova:** o cache ORCID compartilhado muda entre execuções, por isso as execuções gravam a impressão digital e a avaliação final congela um instantâneo | ESPECIFICACAO §2 |

**Testes de software:** 92 passando. Isso **não** constitui validação científica.

---

## A0. Achado prioritário — universo de candidatos da reconstrução (defeito de implementação)

| | |
|---|---|
| **Status** | **DIVERGENTE**: o código diverge da especificação. É um defeito real, não só documental |
| **Fonte** | `scripts/reconstrucao_t4.py:137` (`select_candidates(sa[...], set(sc["author_id"]), …)`); `scripts/auditoria_sorteios.py:103,105`; especificação: PROTOCOLO_CORRIGIDO_2021 §2 ("candidatos: a mesma função com as sementes corrigidas") e ROBUSTEZ §3.3 item 3 ("coautores **dessas** sementes") |
| **O que acontece** | `sa` contém as autorias dos trabalhos de **todas** as 1.000 sementes. `select_candidates` conta como candidato todo autor desses trabalhos que não seja semente **do corte**. Entram, portanto, (i) coautores de sementes **excluídas** do corte (sorteadas por trabalho > c) e (ii) as próprias sementes excluídas |
| **Por que a validação não pegou** | a checagem de reprodução usa as 1.000 sementes, caso em que o universo é o certo |
| **Verificação** | recálculo com o universo restrito aos trabalhos das sementes do corte (`runs/robustez/revisao_candidatos_universo.json`) |

| Corte | Usados | Corrigidos | Usados fora do corrigido | Sementes excluídas usadas como candidatas | Corrigidos sem histórico coletado |
|---|---:|---:|---:|---:|---:|
| Economia 2019 (piloto) | 13.939 | 11.499 | 2.440 | 221 | **0** |
| Economia 2021 | 15.000 | 14.472 | 2.173 | 161 | 330 |
| Matemática 2021 | 15.000 | 14.062 | 3.046 | 196 | 572 |
| Computação 2021 | 15.000 | 15.000 | 3.113 | 187 | 2.521 |
| Medicina 2021 | 15.000 | 15.000 | 2.637 | 191 | 2.062 |

**Impacto: DECISÃO + TESTE.**
- O **protocolo histórico (`477dcd1`) não é afetado**: ele usa as 1.000 sementes.
- **Piloto 2019:** o conjunto corrigido está contido no coletado, então basta refazer a execução
  técnica localmente. Os números técnicos documentados (13.939 candidatos; 159 alvos; positivos
  de treino e teste) passam a ser **histórico de uma versão defeituosa**.
- **Reconstrução 2021 em andamento:** os resultados vão para
  `runs/robustez/t4/reconstrucao_<base>_2021_coletado_{ate2026-10-08,h3}/` e devem ser
  **marcados como inválidos**, sem apagar. Ela pode terminar (só consome CPU) ou ser
  interrompida, por decisão sua.
- **Coleta 2021 (1.021 créditos):** coletou também candidatos que saem do conjunto corrigido
  (desperdício, não contaminação). Faltam os históricos dos corrigidos que nunca foram
  coletados: 330 + 572 + 2.521 + 2.062 candidatos.

**Custo estimado da lacuna nova**, pelo custo real por candidato da coleta de 2021: Economia
91/1.533, Matemática 198/1.943, Computação 321/1.451 e Medicina 411/745 créditos por candidato.

| Base | Créditos |
|---|---:|
| Economia | ~20 |
| Matemática | ~58 |
| Computação | ~560 |
| Medicina | ~1.140 |
| **Total** | **~1.780** |

Isso está **acima** do saldo do teto atual (2.400 − 1.021 = 1.379). Não altero o teto.

**Alteração mínima recomendada:**
1. Corrigir a chamada: `select_candidates(sa[sa.work_id.isin(trabalhos das sementes do corte)], …)`,
   igual ao recálculo acima. O mesmo vale em `auditoria_sorteios.py`, cujas contagens de
   candidatos estão infladas pelo mesmo motivo.
2. Teste novo: candidatos ⊆ coautores das sementes do corte; nenhuma semente excluída entre os
   candidatos.
3. Versionar a saída: nova pasta, sem sobrescrever.

**Decisões necessárias:**
- (a) autorizar a coleta da lacuna nova (~1.780 créditos, acima do teto atual), **ou**
- (b) fazer o protocolo corrigido primeiro em Economia e Matemática (~80 créditos, cabe no
  saldo) e decidir Computação e Medicina depois, **ou**
- (c) outra opção de escopo, que exige aprovação.

**O que pode continuar:** nada que dependa dos candidatos de 2021. O piloto 2019 corrigido é
local e pode rodar depois da correção do código.

---

## 1. Versão e estado operacional

| # | Ponto | Status | Fonte | Impacto | Alteração mínima |
|---|---|---|---|---|---|
| 1.1 | O PROTOCOLO diz que a coleta e a execução **não estão autorizadas** e que o teto é "a autorizar" | **DIVERGENTE** | PROTOCOLO l.17–18, 53, 266, 281 × autorização registrada na conversa de 14/10/2026 e execução em `runs/robustez/t4/coleta_2021_4bases.log` (13:39–14:35; total 1.021/2.400) | DOC | Trocar por: "coleta **autorizada** em 14/10/2026 (teto total 2.400); **executada** 13:39–14:35; gasto 1.021, conferido na API". Manter a estimativa antiga (~1.160) como histórico |
| 1.2 | As saídas oficiais citadas no PROTOCOLO (`runs/robustez/corrigido_2021/`, `data/robustez/corrigido_2021/`) não existem | **DIVERGENTE** | PROTOCOLO l.10–11 × pastas reais `data/robustez/t4/<base>_2021/` e `runs/robustez/t4/reconstrucao_<base>_2021_coletado_{ate2026-10-08,h3}/` | DOC | Unificar nos caminhos reais. Depois de A0, acrescentar um sufixo de versão (ex.: `…_v2`) |
| 1.3 | ROBUSTEZ §6, linha 8, marca o protocolo corrigido como [planejado], com estimativa de inventário (0,3–4,6 mil créditos por base) | **DIVERGENTE** | ROBUSTEZ l.467 | DOC | Status: "coleta executada (1.021); reconstrução executada com defeito A0 (inválida); refazer". Custo atual: o real por base. As estimativas antigas ficam como histórico |
| 1.4 | Datas: lançamento × commit × versão usada | **VERIFICADO** | coleta lançada 13:39 com `coletor_t4.py` = `05442aa` (sem mudança até `0282d2f`); reconstrução lançada 13:41 (espera) e iniciada 14:35 com `reconstrucao_t4.py` idêntico a `0282d2f` (commit 13:46; `git diff` vazio) | DOC | Registrar no PROTOCOLO, para cada execução: lançamento, *hash* do código carregado e commit posterior |
| 1.5 | Piloto: 1.688 candidatos novos (planejamento) × 1.560 (resultado) | **VERIFICADO** (causa medida) | recálculo com as 500 primeiras × as 628 sementes. A diferença são exatamente as **128 sementes acrescentadas**, que eram candidatas na versão de 500 (não há candidato em B fora de A). É sintoma do defeito A0 | DOC + A0 | Registrar a causa medida. As duas contagens são da versão defeituosa |
| 1.6 | "596 disponíveis; usadas 500" no ROBUSTEZ (versão `00f823c`) × o código daquela versão contaria 628 | **DIVERGENTE / NÃO LOCALIZADO** | `git show 00f823c:scripts/reconstrucao_t4.py` l.87–90 conta direto do bruto; o 596 vinha do inventário. O `relatorio.json` daquela execução foi sobrescrito (mesma pasta) | DOC | Registrar que o 596 foi transcrito do inventário, não do relatório da execução, e que o relatório original não foi preservado |

## 2. Reprodução, reanálise e confirmação — linha do tempo do que já foi examinado

| Momento | O que foi examinado | Rótulos | Fonte |
|---|---|---|---|
| 10/10 | Escolha dos hiperparâmetros: **4 variantes** (padrão; reg. lambdarank; **reg. binária** — objetivo `binary`, classificação pontual, **não** LambdaMART; truncamento 1.000), por validação cruzada de alvos em Economia | T1 original (2022+) de Economia | ABLACAO_KG §2; `docs/ABLACAO_KG.md` l.100 |
| 10–11/10 | Ablação, treino temporal, avaliação padrão, cascata e SPECTER2 nas 4 bases: métricas R@K, NDCG, Hits, SHAP; variante "parâmetros padrão" também examinada | T1 original (2022+), estrita e padrão | RESULTADOS_ABLACAO_KG, RESULTADOS_LTR_TEMPORAL, RESULTADOS_GERACAO_SELETIVA, RESULTADOS_TEXTO_SPECTER2 |
| 14/10 | Piloto T1 (3 sementes) e diagnóstico descritivo por subconjunto (R@50, NDCG@10, diferenças pareadas) | T1 original | ROBUSTEZ §5 (versão `00f823c`); RESULTADOS_AUDITORIA_2021 |
| 14/10 | Piloto T4 2019 e reconstrução 2021: métricas **gravadas e não examinadas** | 2020–2022; 2022–2026/2024 | `metricas_por_alvo.parquet` (não aberto) |
| 14/10 | Emenda: piloto de **500 → 628** sementes, decidida depois do resultado técnico de 189 elegíveis / 121 alvos (contagens, não desempenho) | — | ROBUSTEZ §3.4 (registro de 14/10) |
| 14/10 | Plano confirmatório (4 variantes, validação 2015 → 2018) registrado | — | ROBUSTEZ §3.5.5 |

**Classificação que as evidências sustentam:**
- **Reprodução:** a configuração histórica sobre o protocolo corrigido.
- **Reanálise temporal pré-especificada:** a escolha entre as **mesmas 4 variantes** por
  validação temporal ≤ 2021, aplicada ao teste de 2021. O teste de 2022+ **já foi consultado**
  em 10–11/10 com essas variantes e com esses alvos históricos, e os alvos corrigidos são um
  subconjunto próximo. Registrar um arquivo de configuração novo **não** torna esse teste
  independente.
  - **Status: PROPOSTA.** Rotular o plano de ROBUSTEZ §3.5.5 como "reanálise temporal
    pré-especificada", não "confirmação".
  - **Impacto: DECISÃO.**
- **Confirmação com independência justificada:** exigiria rótulos ainda não consultados. Ex.: o
  horizonte 2025-01-01 a 2026-10-08 é parte dos rótulos já examinados no protocolo original;
  logo, **não há janela intocada** no corpus atual.
  - Opções:
    - (i) declarar que não há confirmação estritamente independente e tratar tudo como
      reanálise pré-especificada;
    - (ii) reservar um corte futuro (dados de 2027, coleta futura).
  - **Status: PROPOSTA. Impacto: DECISÃO.**
- **Exploração:** todas as análises de 10–11/10 e o piloto.
- **Nenhuma reanálise é descartada.**

## 3. Validação temporal executável

| # | Ponto | Status | Fonte | Impacto |
|---|---|---|---|---|
| 3.1 | Estratégia única de seleção | **PROPOSTA**: ROBUSTEZ §3.5.5 traz a principal (KG ≤ 2015 → 2016–2018; validação KG ≤ 2018 → 2019–2021) **e** uma alternativa em aberto ("validar só com 2018 → 2019–2021…"). Isso viola "uma única estratégia antes do teste" | ROBUSTEZ §3.5.5 | DECISÃO |
| 3.2 | Inventário por fase (Economia, aproximado sobre o bruto, com o universo corrigido de A0) | **VERIFICADO** (leve) | tabela abaixo | TESTE |
| 3.3 | População da validação | **DIVERGENTE** com a frase "nenhum rótulo depois de c é consultado": vale para **rótulos**, mas as consultas e os candidatos das fases 2015/2018 são selecionados com laços ≤ 2021, informação **posterior** a cada fase | ROBUSTEZ §3.5.5 | DOC + DECISÃO |
| 3.4 | "Regularizada binária" muda o objetivo | **VERIFICADO**: `objective="binary"` (classificação pontual), não lambdarank | experimento de 10/10 (script de rascunho, fora do repositório: **NÃO LOCALIZADO no repo**); ABLACAO_KG §2 | DOC |

**Inventário por fase — Economia** (sementes do corte 2021 = 739; candidatos corrigidos =
14.472; positivos aproximados, sobre o bruto e só das sementes):

| Fase | KG até | Rótulos | Sementes com trabalho | Trabalhos das sementes | Candidatos nos trabalhos das sementes | Trabalhos da expansão | Positivos das sementes (aprox.) |
|---|---:|---|---:|---:|---:|---:|---:|
| Treino de seleção | 2015 | 2016–2018 | 625 | 15.343 | 8.121 | **0** | 3.182 |
| Validação | 2018 | 2019–2021 | 677 | 20.203 | 11.107 | 29.897 (2017–2018) | 3.665 |
| Teste | 2021 | 2022–2024 | 739 | 24.760 | 14.472 | 74.916 | 3.064 |

- Sem histórico complementar antes de 2017, a fase 2015 tem os candidatos **só** pelos trabalhos
  compartilhados com as sementes: 8.121 aparecem, mas com histórico truncado. A cobertura difere
  muito entre as fases.
- Features e transformações (TF-IDF, PPR, graus) são recalculadas em cada KG, só com dados ≤ KG
  (§4.4 abaixo). As consultas e os candidatos não.

**Alternativas, com custo:**
- **(i) Treino retrospectivo disponível em 2021** (recomendada como principal). Seleção por
  validação 2018 → 2019–2021 **com a população do protocolo corrigido**. Declarar que é escolha
  feita "em 2021, com dados ≤ 2021", não simulação de 2018.
  - Uma única divisão: treino KG ≤ 2015 → 2016–2018; validação KG ≤ 2018 → 2019–2021.
  - Custo local.
- **(ii) Simulação integral de 2018:** reconstruir sementes, candidatos e expansão com laços
  ≤ 2018 (como o T4 de 2018). Custo: coleta da reconstrução de 2018 (o inventário anterior
  estimava ~1,0 mil créditos só em Economia, com o mesmo defeito A0 a corrigir) **mais**
  hiperparâmetros por corte.
- **(iii) Validação temporal interna** (divisão por consultas dentro de 2019–2021): é mais
  barata, mas mistura período de treino e de validação. Não recomendada.

## 4. Elegibilidade, newcomers e denominadores

| # | Ponto | Status | Fonte | Impacto |
|---|---|---|---|---|
| 4.1 | "Elegíveis sem trabalho em T0 (*newcomers*)" no protocolo corrigido | **DIVERGENTE**: com E5 ≥ 2 trabalhos calculado **até o corte**, o grupo é vazio. Verificado: Economia 2021 corrigido tem regimes warm 173 / cool 29 / cold 2 / **newcomer 0**; piloto 2019: 0. Os 15 / 32 / 22 / 28 newcomers existem só no protocolo **histórico**, em que E5 usa todos os anos | PROTOCOLO l.220; `reconstrucao_<base>_2021_coletado_*/alvos.csv`; `runs/linha_base/<base>.json` | DOC |
| 4.2 | Futuros coautores ausentes em T0 | **VERIFICADO**: continuam no denominador estrito (`gt` inclui todos os coautores novos) | `eval/protocol.py` (`gt` × `gt_t0`) | DOC (explicitar) |
| 4.3 | Alvos com positivos estritos, mas sem positivos alcançáveis | **VERIFICADO**: existem. Ex.: Economia 2021, horizonte original: 204 alvos estritos × 127 na avaliação padrão (77 só estritos) | `relatorio.json › protocolo` | DOC |
| 4.4 | P@K com lista < K | **PROPOSTA**: o conjunto tem 1.000 candidatos por alvo (≥ K); para listas menores, usar denominador **K** (conservador) e reportar o número de listas curtas | `ranking_report` não calcula P@K; P@K_incond definido em PROTOCOLO §5.3 | DOC |
| 4.5 | "Incondicionais servem para leitura de uso real" | **DIVERGENTE** (afirmação forte demais) | PROTOCOLO l.236 | DOC: trocar por "medidas offline incondicionais; não validam uso real" |
| 4.6 | Não relaxar E5 para conservar newcomers | **VERIFICADO** (nenhuma proposta de relaxar) | — | — |

**Conjuntos e denominadores (proposta de texto, sem mudança de regra):**
- **elegíveis:** E1–E8 ≤ c;
- **alvos estritos:** elegíveis com ≥ 1 coautoria nova no horizonte, após M9. Denominador por
  alvo = todos os coautores novos;
- **alvos padrão:** alvos estritos com ≥ 1 coautor novo presente em T0. Denominador = só esses;
- **elegíveis sem positivos:** grupo distinto, só contado.

## 5. Efeitos por área, agregação e precisão

| # | Ponto | Status | Fonte | Impacto |
|---|---|---|---|---|
| 5.1 | ROBUSTEZ §4.1 chama de "proposta confirmatória" a **estimativa conjunta** × PROTOCOLO §5 adota **por área** como principal | **DIVERGENTE** | ROBUSTEZ l.401; PROTOCOLO §5 (l.150–158) | DOC: manter a decisão única do PROTOCOLO (por área principal; conjunto complementar) e alinhar o ROBUSTEZ |
| 5.2 | "Em Medicina, ~300 alvos bastam para δ" | **DIVERGENTE**: ~310 é o n para 80% de poder (aprox. normal). Para semiamplitude ≤ δ/2: 1,96 × 2,2/√310 ≈ **0,245 pp** > 0,175 pp (δ/2). Precisaria de ~614 | PROTOCOLO l.138; `runs/robustez/precisao.json` | DOC (sem nova meta de coleta) |
| 5.3 | Referência de δ | **PROPOSTA**: δ_abs = 10% do R@50 médio do **controle (LTR só coautoria) no protocolo histórico publicado** (0,35 / 0,56 / 0,94 / 0,61 pp), fixado agora como constante. A alternativa "10% do controle no protocolo corrigido" depende do resultado e não é recomendada | `precisao.json` | DECISÃO |
| 5.4 | Unidade estatística e famílias | **PROPOSTA**: unidade = pessoa-alvo. Famílias para Bonferroni: por área **e** por horizonte, com o conjunto {C1 R@50, C1 NDCG@10, C2 R@50, C4 × 2 baselines}. C3 é descritiva (sem teste) | — | DECISÃO |
| 5.5 | "Conclusão em 80% das execuções" | **PROPOSTA**: C1/C2 = Δ > 0 com IC 95% > 0 (Bonferroni da família) em ≥ 4 de 5 execuções por área. **C3** = em cada execução, a participação média do conteúdo (\|SHAP\| tópicos + citação + texto) no polo esparso (média de Matemática e Economia) é maior que no polo denso (média de Medicina e Computação); vale se ocorrer em ≥ 4 de 5 | ROBUSTEZ §4 | DECISÃO |
| 5.6 | CV ≤ 10% | **VERIFICADO** como estabilidade numérica; reformular para não sugerir superioridade | ROBUSTEZ §4.2 | DOC |
| 5.7 | Não acrescentar alvos, cortes ou sementes para obter significância | **VERIFICADO**: a ampliação (completar o sorteio 42) foi justificada antes dos resultados. Registrar que não será acionada por resultado | PROTOCOLO §5 item 3 | DOC |

## 6. Dependência e sobreposição

| # | Ponto | Status | Fonte | Impacto |
|---|---|---|---|---|
| 6.1 | Mesma multiplicidade de reamostragem para a mesma pessoa em todas as áreas e cortes | **DIVERGENTE**: o texto diz "estratificado por área, em blocos por pessoa". Sorteios independentes por área **não** garantem a mesma multiplicidade | PROTOCOLO §5.2, §5.4 | DOC + TESTE |
| 6.2 | Análise por componentes | **PROPOSTA**: reportar número de blocos, distribuição de tamanhos e maior componente; não tratar poucos blocos como solução | PROTOCOLO §5.4 | TESTE |
| 6.3 | "Novo em mais de uma janela, se a colaboração recomeçar" | **DIVERGENTE**: com passado cumulativo, colaboração já observada não volta a ser nova. A repetição legítima é **janelas sobrepostas compartilhando o mesmo primeiro evento** | PROTOCOLO l.257 | DOC |

**Proposta para 6.1:** *bootstrap* de Poisson por pessoa. Cada pessoa canônica recebe **um**
peso ~ Poisson(1) por réplica, aplicado a **todas** as suas observações em todas as áreas e
cortes. A estratificação por área vira só um diagnóstico (proporções por área em cada réplica).

**Taxonomia das repetições (6.3), a reportar por tipo:**
1. sobreposição de janelas (mesmo primeiro evento visto em dois cortes);
2. histórico incompleto (colaboração anterior fora da área ou sem resumo, que faz parecer nova);
3. mudança de corpus ou identidade entre cortes;
4. colaboração recorrente (não pode ser "nova" duas vezes no passado cumulativo; se aparecer, é
   defeito).

Remover as repetições do tipo 1 responde "o efeito em eventos distintos". Mantê-las responde
"o efeito por corte". Os dois são reportados.

A seção de dependências residuais do PROTOCOLO §5.4 é mantida.

## 7. Comparações CNN/GNN

| # | Ponto | Status | Fonte | Impacto |
|---|---|---|---|---|
| 7.1 | N2b × N2a e N5 × N4 como controles da convolução | **VERIFICADO** | ROBUSTEZ §5 | — |
| 7.2 | N4 × N0 mede o **pacote** (texto treinável + GNN), não a GNN isolada | **DIVERGENTE**: o texto diz "N4 vs N0 (a GNN acrescenta?)" | ROBUSTEZ §5 | DOC |
| 7.3 | Contrastes planejados N4 × N2a e N5 × N2b (efeito da GNN dado o braço textual) | **PROPOSTA**, se as demais entradas forem idênticas | — | DECISÃO (menor) |
| 7.4 | N3 × N6 | **DIVERGENTE / ambíguo**: N3 ("R-GCN … decodificador DistMult") e N6 ("R-GCN + KG sozinha") parecem o mesmo modelo | ROBUSTEZ §5 | DOC + DECISÃO |
| 7.5 | Composição de N2a/N2b | **NÃO LOCALIZADO**: não está dito se o escore treinável **substitui** ou **soma** ao TF-IDF | ROBUSTEZ §5 | DECISÃO |
| 7.6 | GNN sem LambdaMART sobre o top-1000 da RRF | **PROPOSTA**: descrever como "ranqueador neural sobre candidatos compartilhados", não como gerador | — | DOC |
| 7.7 | "LTR só coautoria" | **PROPOSTA**: rotular como "controle de ranqueamento sobre candidatos gerados com o KG", não como pipeline sem KG | ABLACAO_KG; RESULTADOS_* | DOC |

**Proposta mínima** (sem modelos novos):
- **N3** = LambdaMART + KG + escore da R-GCN, com texto TF-IDF (contribuição da GNN dado o
  ranqueador);
- **N6** = R-GCN sozinha, como ranqueador sobre o top-1000 compartilhado;
- **N2a/N2b** = N0 + escore textual treinável, **mantendo** o TF-IDF.

## 8. Treinamento em duas etapas (módulos neurais → LambdaMART)

**Status: NÃO LOCALIZADO** na especificação atual. **Impacto: DECISÃO.**

**Proposta de especificação** (*stacking* temporal fora da amostra):

| Etapa | Módulo neural treinado com | Escores produzidos para | Rótulos vistos pelo módulo |
|---|---|---|---|
| Atributo para o **treino** do LambdaMART | grafo/textos ≤ c−6, rótulos (c−6, c−3] | pares do treino do LambdaMART (KG ≤ c−3, rótulos (c−3, c]) | só ≤ c−3 |
| Atributo para o **teste** | grafo/textos ≤ c−3, rótulos (c−3, c] | pares do teste (KG ≤ c) | só ≤ c |

- O módulo **nunca** pontua um par cujo rótulo viu.
- Registram-se períodos, rótulos vistos e versão (*hash* de código e pesos) de cada módulo.
- Alternativa: *cross-fitting* por pessoa dentro do mesmo período, em K dobras. É mais simples,
  mas mistura períodos. Não recomendada como principal.
- Custo: o módulo é treinado duas vezes por corte.

## 9. Comparação histórica × reconstruída

**Status: PROPOSTA. Impacto: DOC.**
- Entre as versões mudam **ao mesmo tempo**: sementes (~30% saem), elegibilidade (E1–E8 ≤
  2021), candidatos (universo e laços; ver A0), expansão, KG e, portanto, gabarito e alvos.
- A diferença entre médias de populações diferentes **não** é atribuível a um fator.
- A comparação principal entre modelos ocorre **dentro** de cada versão (mesmos alvos,
  candidatos e gabarito).
- Uma análise na **interseção de alvos** é complementar e precisa informar se os gabaritos
  coincidem. Eles podem diferir pelo corpus (identidades, trabalhos) e pela M9.

## 10. Pendências que continuam abertas

| Pendência | Status | Fonte |
|---|---|---|
| Impacto do resumo obrigatório nos **rótulos** e nas coautorias anteriores | **aberta** (medido só o efeito na população de sementes e elegíveis) | `runs/robustez/diagnostico_resumo.json`; PENDENCIAS P-02 |
| Teto de 50 sobre coautorias anteriores | **aberta** (não medida) | PENDENCIAS P-12 |
| Auditoria manual de identidade | **aberta** (sem resultados) | `audit_sample.csv` (`verificado_ok` vazio) |
| Versão de rótulos | se a definição de rótulos mudar (ex.: correção A0 muda candidatos e alcance, mas não a regra de rótulo), criar versão nova e listar resultados a reavaliar | — |

---

## O que pode continuar e o que depende de fechar a especificação

| Pode continuar | Depende de decisão ou correção |
|---|---|
| A reconstrução em andamento pode terminar (só CPU), com saídas marcadas inválidas. **Recomendo interromper** para liberar a máquina; decisão sua | Correção de A0 (código e teste) antes de qualquer reconstrução nova |
| Edições só de documentação (itens marcados DOC) | Coleta da lacuna nova (~1.780 créditos, acima do teto) ou redução de escopo |
| Piloto 2019 refeito localmente depois da correção de A0 (sem coleta) | Estratégia única de validação (3.1), δ (5.3), famílias (5.4), critério de 80% (5.5) |
| | Classificação reprodução/reanálise/confirmação (§2) |
| | N3/N6/N2a/N2b e o *stacking* temporal (§7–8) |

## Decisões indispensáveis antes de congelar a avaliação final

1. **A0:** aprovar a correção do universo de candidatos e escolher entre coletar a lacuna nova
   (~1.780 créditos, acima do teto), reduzir o escopo inicial a Economia e Matemática, ou outra
   via.
2. **Classificação inferencial:** aceitar que a escolha pelas 4 variantes sobre 2022+ é
   **reanálise temporal pré-especificada**, não confirmação independente, ou reservar dados
   futuros.
3. **Estratégia única de seleção de hiperparâmetros:** treino retrospectivo disponível em 2021
   (2015 → 2016–2018 / 2018 → 2019–2021) **ou** simulação integral de 2018 (com coleta).
4. **δ, unidade, famílias de multiplicidade e critério operacional de "80%"** (§5.3–5.5).
5. **Definições N3/N6/N2a/N2b** e o *stacking* temporal dos módulos neurais (§7–8).

Os testes de software passando **não** constituem validação científica do protocolo.
