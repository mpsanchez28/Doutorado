# Especificação do protocolo corrigido de 2021

**Prioridade da frente de robustez.** A auditoria ([AUDITORIA_SELECAO.md](AUDITORIA_SELECAO.md))
mostrou que o protocolo original de 2021 usa informação posterior ao corte na seleção das
sementes, na elegibilidade e nos metadados. Este documento especifica a **avaliação principal
corrigida**. O piloto do T4 (Economia 2019) valida a infraestrutura, mas não a substitui.

- **Referência histórica preservada:** `main` em `477dcd1`, com os resultados em
  `runs/ltr_temporal/`, `runs/linha_base/` etc. Nada disso é alterado.
- **Saídas do protocolo corrigido:** `runs/robustez/corrigido_2021/` (dados em
  `data/robustez/corrigido_2021/`).

**Estado:**
- **[especificado]**: este documento;
- **[inventariado]**: lacunas e custos medidos com dados locais
  (`scripts/reconstrucao_t4.py --corte 2021 --n-sementes todas --sem-corpus`);
- a coleta e a execução **não estão autorizadas**; dependem de nova autorização, com a
  estimativa abaixo.

## 1. Princípio

Reconstrução **retrospectiva pela data dos fatos, com metadados atuais**:
- cada etapa usa só fatos datados até 31/12/2021, mais os rótulos posteriores;
- os metadados (desambiguação, tópicos, afiliações, ORCID, resumos) são os de hoje.

Muda-se **uma coisa de cada vez** em relação à referência: a seleção e os componentes
dependentes. Modelo, hiperparâmetros, atributos e métricas ficam idênticos.

## 2. Componentes

| Componente | Referência (original) | Corrigido | Dados | Estado |
|---|---|---|---|---|
| **Seleção** | 1.000 primeiras sementes (ordem) do sorteio 42, qualquer ano de trabalho sorteado | **todas** as sementes do conjunto de 1.000 cujo trabalho sorteado tem ano ≤ 2021. Amostra retrospectiva **condicionada ao mecanismo original de seleção**, sem afirmar representatividade histórica | local | [inventariado]: 692 (Medicina), 696 (Computação), 741 (Matemática), 739 (Economia) |
| **Elegibilidade** | E1–E8 sobre todos os anos | E1–E8 com autorias ≤ 2021; **E3 sem relaxar** (§4) | local + cache ORCID | [executado]: elegíveis 310 / 297 / 344 / 313 |
| **Alvos** | elegíveis com ≥ 1 coautoria nova em T1 | idem, sobre os elegíveis corrigidos | local | a medir |
| **Candidatos** | `select_candidates` com as 1.000 sementes, laços ≤ 2021, teto 15 mil | a **mesma função** com as sementes corrigidas | local | [verificado]: a função reproduz o original nas 4 bases; teto atingido |
| **Expansão** | histórico 2017–2021 dos 15 mil | histórico 2017–2021 dos candidatos corrigidos; reaproveita os já coletados | lacunas | [inventariado]: 745 / 1.451 / 1.943 / 1.533 novos |
| **Limpeza e higienização** | sobre o corpus original | refeitas sobre o corpus corrigido; mesmas regras | local + ORCID | a executar |
| **Enriquecimento** | cache dos trabalhos do corpus original | cache + trabalhos novos da expansão | lacunas | incluído no custo |
| **KG** | KG ≤ 2021 | refeito sobre o corpus corrigido; `validate_kg` | local | a executar |
| **Treino temporal** | KG 2018 → rótulos 2019–2021; consultas = sementes + candidatos (até 3.000) | mesmas regras sobre o corpus corrigido | local | a executar |
| **Avaliação** | estrita (principal) e padrão; M9; R@K, NDCG@10, Hits@K, MRR | idênticas | local | a executar |

**Custo da coleta das lacunas** (estimativa da reconstrução com a função original; ±50%):

| | Medicina | Computação | Matemática | Economia | Total |
|---|---:|---:|---:|---:|---:|
| Candidatos novos | 745 | 1.451 | 1.943 | 1.533 | 5.672 |
| Trabalhos a coletar | ~3,8 mil | ~6,1 mil | ~8,0 mil | ~5,1 mil | ~23 mil |
| Créditos OpenAlex | ~186 | ~307 | ~402 | ~261 | **~1.160** |
| Leituras ORCID (gratuitas) | 408 | 839 | 1.022 | 211 | 2.480 |

Proposta de teto, a autorizar: **2.400 créditos** para as 4 bases, o dobro da estimativa,
com o mesmo coletor do piloto (contabilidade, retomada e parada no teto).

## 3. Horizonte dos rótulos

**Data exata de encerramento dos rótulos (horizonte original): 08/10/2026, inclusive.**
- A coleta foi feita em 09/10/2026. A última data de publicação observada no corpus é
  2026-10-08 em Medicina, Computação e Economia, e 2026-10-07 em Matemática
  (DOSSIE_CONSTRUCAO_BASE.md §4.8).
- Adota-se o mesmo fim para as 4 bases: trabalhos com `publication_date` ≤ 2026-10-08.
- Implementado em `scripts/reconstrucao_t4.py --fim-rotulos 2026-10-08`.

| Avaliação | Corte | Rótulos | Duração | Pasta de saída |
|---|---|---|---|---|
| Referência histórica (`477dcd1`) | 2021 | 2022-01-01 a 2026-10-08 (2026 incompleto) | ~4,8 anos | `runs/ltr_temporal/` |
| **Corrigida — reprodução com horizonte original** | 2021 | **2022-01-01 a 2026-10-08** | ~4,8 anos | `runs/robustez/t4/reconstrucao_<base>_2021_coletado_ate2026-10-08/` |
| **Corrigida — 3 anos, comparável ao T4** | 2021 | **2022-01-01 a 2024-12-31** | 3 anos | `…_2021_coletado_h3/` |
| Piloto T4 | 2019 | 2020-01-01 a 2022-12-31 | 3 anos | `…_2019_coletado_h3/` |
| T4 (demais cortes) | c | (c+1)-01-01 a (c+3)-12-31 | 3 anos | idem |

As duas avaliações corrigidas ficam **separadas**:
- **horizonte original:** compara-se à referência; só a seleção muda;
- **3 anos:** compara-se aos cortes do T4, com acompanhamento equivalente.

Qualquer comparação entre horizontes diferentes declara a diferença: horizontes longos têm mais
coautorias novas por alvo, o que muda o recall e o número de alvos avaliáveis.

## 4. Temporalidade do ORCID (E1/E3)

Dois conceitos diferentes:
- **(i) trabalho publicado até o corte e reivindicado no ORCID atual:** é o que o E3 mede hoje;
- **(ii) reivindicação comprovadamente disponível no corte:** não é medido.

Sem evidência histórica, o E3 (e o E1) é registrado como **critério retrospectivo baseado no
estado atual do ORCID**.

**O que os campos de data do ORCID significam** (verificado na documentação oficial,
[ORCID record — integration guide](https://info.orcid.org/documentation/integration-guide/orcid-record/),
14/10/2026):
- todo item do registro (inclusive cada trabalho) tem `created-date` e `last-modified-date`.
  São carimbos de **quando o item foi adicionado ou alterado no registro**, não a data de
  publicação;
- o elemento `source` identifica **quem** adicionou o item: a própria pessoa ou um cliente
  integrado (ex.: uma organização-membro que sincroniza publicações). O carimbo, então, pode
  refletir uma sincronização automática, e não um ato da pessoa;
- itens têm visibilidade (pública/privada). A API pública só devolve itens públicos **hoje**. Um
  item pode ter sido privado no corte e público agora, ou o contrário;
- a documentação **não informa** se apagar e reinserir um item reinicia o `created-date`.

**Consequências para o uso como evidência** (a verificar antes de usar):
- `created-date` ≤ corte é **indício** de que o item estava no registro antes do corte, mas
  **não** prova que estivesse público nem que os demais metadados (nomes, afiliações) fossem os
  de hoje;
- `created-date` > corte **não** prova ausência antes do corte (pode haver reinserção ou
  ressincronização);
- não equivale à data de publicação do trabalho, nem à disponibilidade dos metadados do OpenAlex
  naquele corte.

**Uso proposto [planejado]:** classificar cada E3 em "item criado até o corte", "item criado
depois" e "sem data". Reportar como **sensibilidade**, não como comprovação histórica. Exige reler
os registros ORCID das sementes (gratuito), porque o cache atual guarda só os DOIs extraídos.

## 5. Precisão estatística e amostra confirmatória

**Contraste principal (definido antes dos resultados corrigidos):**

  Δ = R@50(LambdaMART + KG) − R@50(LambdaMART só coautoria), pareado por alvo, avaliação estrita (C1).

- **Melhoria mínima relevante:** δ = 10% relativo ao R@50 do controle.
- **Precisão desejada:** semiamplitude do IC 95% de Δ ≤ δ/2.

**Incerteza esperada**, por reamostragem das diferenças pareadas **já disponíveis**
(`scripts/precisao_t4.py`; protocolo original, horizonte ~4,8 anos):

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| δ (pp de R@50) | 0,35 | 0,56 | 0,94 | 0,61 |
| DP de Δ (pp) | 2,2 | 4,4 | 14,1 | 12,7 |
| Fração de alvos com Δ = 0 | 72% | 81% | 76% | 77% |
| Semiamplitude do IC 95% com 160 alvos (pp) | 0,31 | 0,64 | 2,11 | 1,88 |
| n para 80% de poder com δ (aprox. normal) | ~310 | ~490 | ~1.760 | ~3.430 |

**Leitura.**
- A precisão não depende só da contagem de alvos. Ela depende da dispersão de Δ, que é muito
  maior nas áreas esparsas: poucos coautores novos por alvo e muitos zeros.
- Em Medicina, ~300 alvos bastam para δ.
- Em Matemática e Economia, nem os ~250 alvos corrigidos de 2021 atingem a precisão desejada
  **para δ de 10%**, embora detectem o efeito observado na referência (~+2 pp), que é bem maior
  que δ.

**Limitações da estimativa:**
- vem do protocolo original, não do corrigido;
- horizonte e treino diferentes;
- o horizonte de 3 anos tende a aumentar os zeros;
- a distribuição tem muitos zeros (IC por bootstrap);
- os alvos são tratados como independentes.

**Proposta de análise** (revista em 14/10/2026):
1. **Principal: Δ por área**, com IC 95%, interpretado pela **estimativa e intervalo**, não só
   pela significância. Uma área sem significância não é tratada como ausência de efeito se o
   intervalo for compatível com δ, nem como presença se não for.
2. **Complementar: estimativa conjunta** com pesos fixados antes (§5.2). Responde à pergunta
   média e **não** é apresentada como prova de ganho em todas as áreas.
3. **Ampliação da amostra:** se a precisão por área for necessária, a opção auditada é
   **completar o sorteio 42** (sementes além das 1.000 primeiras: +152 em Economia, +415 em
   Matemática) antes dos sorteios 43–44 (ROBUSTEZ_T1_T4.md §3.6). A decisão não depende do
   resultado dos modelos.

### 5.1 Qualificação da estimativa de precisão (`scripts/precisao_t4.py`)

- **Status:** planejamento **aproximado**, baseado no protocolo **anterior** (seleção original,
  corte 2021, horizonte ~4,8 anos). Não é uma previsão do protocolo corrigido.
- **Por que 10% relativos:** escolha **a priori**, não derivada dos dados. É a menor melhoria
  considerada de interesse prático para um ranqueador: um acerto a mais a cada dez que o controle
  já obtém. Convertida em pontos absolutos por base, sobre o R@50 médio do controle: δ = 0,35
  (Medicina), 0,56 (Computação), 0,94 (Matemática) e 0,61 pp (Economia). Outros δ podem ser
  reportados como sensibilidade.
- **O que cada número mede:**

| Número | Mede | Pressupõe |
|---|---|---|
| Semiamplitude do IC 95% | **precisão** (largura do intervalo) | nada sobre o efeito |
| Fração de IC que exclui 0 | detecção sob o efeito **observado** no protocolo anterior | aquele efeito |
| Poder aproximado para δ | fração de IC que exclui 0 se o efeito verdadeiro fosse exatamente δ (diferenças deslocadas) | a forma da distribuição observada |
| n para 80% de poder (normal) | aproximação grosseira | normalidade (ignora zeros e assimetria) |

- **Zeros e não zeros:**

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| Alvos com Δ = 0 | 72% | 81% | 76% | 77% |
| Entre os não nulos, positivos | 68% | 66% | 69% | 72% |
| Quantis P5 / P25 / P50 / P75 / P95 dos não nulos (pp) | −3,2 / −0,8 / +1,0 / +2,2 / +6,3 | −8,9 / −2,2 / +2,7 / +9,0 / +16,4 | −20,1 / −3,8 / +10,0 / +20,0 / +50,8 | −25,8 / −1,8 / +6,7 / +12,5 / +50,0 |

  Nas áreas esparsas, cada alvo tem poucos coautores novos, e um acerto a mais ou a menos move o
  R@50 do alvo em dezenas de pontos. Daí a grande dispersão.
- **Poder aproximado para δ** (reamostragem; ruidoso): Medicina ~0,66 com 160 alvos e ~0,94 com
  310; Computação ~0,50 e ~0,68; Matemática ~0,16 e ~0,18; Economia ~0,19 e ~0,13. Com 1.000
  alvos: 1,0 / 0,99 / 0,66 / 0,32.

### 5.2 Pergunta da análise conjunta (complementar, pesos fixados antes)

- **Pergunta:** *qual é, em média sobre as quatro áreas com peso igual, a diferença pareada de
  R@50 entre LambdaMART + KG e LambdaMART só coautoria?*
- **Pesos fixados agora:** **1/4 por área**, independentemente do número de alvos, para que
  Medicina não domine. Uma ponderação por número de alvos fica como sensibilidade.
- **Estimativa:** média ponderada das médias por área. IC por bootstrap **estratificado por área
  e em blocos por pessoa canônica**: reamostra pessoas, mantendo todos os pares e observações de
  cada uma. Isso trata a sobreposição de autores entre bases e, no T4, entre cortes.
- **O que a análise NÃO afirma:** um agregado positivo **não** prova ganho em cada área. Os
  efeitos e intervalos **por área** são sempre reportados e interpretados primeiro. O agregado
  responde só à pergunta média.
- **Sobreposição** (DOSSIE §4.3):
  - em 2021, alvos em comum entre bases = 0, e 1–5% das pessoas aparecem em mais de uma base
    (como candidatas e coautoras);
  - no T4, as **mesmas sementes** aparecem em vários cortes, então as observações por corte não
    são independentes. O bootstrap em blocos por pessoa e a leitura corte a corte tratam disso.
  - Pares (alvo, coautor) repetidos entre cortes ocorrem quando um coautor é "novo" em mais de
    uma janela. São contados, e o efeito é verificado retirando as repetições.

### 5.3 População avaliada e tratamento dos autores sem coautoria nova (definido antes da execução)

| Conjunto | Definição |
|---|---|
| Elegíveis | sementes do corte com E1–E8 ≤ c |
| **Alvos com positivos** | elegíveis com ≥ 1 coautoria nova no horizonte (após M9) |
| Elegíveis sem positivos | elegíveis sem nenhuma coautoria nova no horizonte |
| Elegíveis sem trabalho em T0 (*newcomers*) | entram como alvos com métricas zero, se tiverem positivos |

- **Métricas de ranking condicionais.** Recall@K, NDCG@K, MRR e Hits@K são calculados **só**
  sobre os alvos com positivos. São métricas **condicionais** ao evento "o autor teve ≥ 1
  coautoria nova no horizonte". Para os demais, não estão definidas (não há o que acertar).
- **Tratamento dos demais (pré-definido):**
  1. as contagens dos três conjuntos são sempre reportadas por área, com a fração de elegíveis
     sem positivos;
  2. métricas **incondicionais** complementares, calculadas sobre **todos** os elegíveis com
     trabalho em T0:
     - P@K_incond = Σ acertos@K dos alvos / (K × N elegíveis);
     - Hits@K_incond = alvos com ≥ 1 acerto no top-K / N elegíveis.

     Elas tratam o elegível sem positivos como lista sem acerto possível, sem exigir ranking
     adicional;
  3. a comparação entre modelos usa as métricas condicionais (mesmo conjunto de alvos para
     todos). As incondicionais servem para leitura de uso real, não para o teste pareado.

### 5.4 Dependência estatística

**O que o intervalo considera:**
- **Bootstrap em blocos por pessoa canônica**, estratificado por área: reamostram-se pessoas,
  levando juntas todas as suas observações;
- isso cobre o mesmo autor como alvo em **vários cortes** do T4 e o mesmo autor em **mais de uma
  área**. Em 2021, alvos em comum entre áreas = 0; ~1–5% das pessoas aparecem em mais de uma
  base, como candidatas ou coautoras.

**Dependências que permanecem** (não absorvidas pelo bloco por pessoa-alvo):
1. **Coautores compartilhados entre alvos:** o mesmo coautor novo pode ser positivo para vários
   alvos (por exemplo, quando dois alvos e ele publicam juntos). Os acertos desses alvos se
   correlacionam.
2. **Coautoria entre alvos:** dois alvos podem ser coautores novos um do outro. O mesmo par conta
   nos dois sentidos.
3. **Trabalhos compartilhados:** um único trabalho de T1 pode gerar positivos para vários alvos.
4. **Candidatos compartilhados:** o mesmo candidato forte aparece no top-K de muitos alvos, e
   erros sistemáticos nele se propagam.
5. **Entre cortes (T4):** além do mesmo alvo, o mesmo par (alvo, coautor) pode ser "novo" em mais
   de uma janela, se a colaboração recomeçar.

**Medidas planejadas:**
- reportar as contagens dessas sobreposições: alvos que compartilham coautores novos, pares
  recíprocos, trabalhos com positivos para > 1 alvo, pares repetidos entre cortes;
- **sensibilidade:** bootstrap em blocos por **componente** do grafo alvo–coautor-novo (alvos
  ligados por coautores novos em comum caem no mesmo bloco), e reestimativa removendo pares
  repetidos.

## 6. Sequência de execução (preparada; coleta depende de autorização)

O piloto de Economia/2019 validou a infraestrutura de ponta a ponta (ROBUSTEZ_T1_T4.md §3.5.1–3.5.4):
- **gasto real** de 818 créditos, conferido na API;
- checagens temporais aprovadas;
- reprodutibilidade exata.

O mesmo pipeline vale para 2021, com `--corte 2021`.

**Lacunas e custo de 2021** (inventário local já feito: `runs/robustez/t4/reconstrucao_<base>_2021/lacunas.csv`):
- só há **candidatos novos**: de 745 a 1.943 por base;
- não há anos faltantes para os já coletados, porque a janela 2017–2021 é a original;
- estimativa: ~1.160 créditos nas 4 bases, mais o enriquecimento dos trabalhos novos, incluído;
- no piloto, o gasto real ficou em 65% da estimativa.

**Teto proposto: 2.400 créditos para as 4 bases (a autorizar).**

Comandos, por base, depois da autorização:

```bash
PYTHONHASHSEED=0 python scripts/coletor_t4.py <base> --corte 2021 --limite <teto da base>
PYTHONHASHSEED=0 python scripts/reconstrucao_t4.py <base> --corte 2021 --n-sementes todas \
    --coletado data/robustez/t4/<base>_2021 --fim-rotulos 2026-10-08 --modelo     # reprodução, horizonte original
PYTHONHASHSEED=0 python scripts/reconstrucao_t4.py <base> --corte 2021 --n-sementes todas \
    --coletado data/robustez/t4/<base>_2021 --horizonte 3 --modelo               # 3 anos (2022–2024), comparável ao T4
```

Saídas **separadas** por horizonte (`…_coletado_ate2026-10-08/` e `…_coletado_h3/`), sem
sobrescrever a referência.

Ordem:
1. Economia e Matemática (mais baratas);
2. Computação;
3. Medicina (KG maior; reconstrução local mais pesada).

Depois:
4. comparação com a referência histórica, horizonte original, mesma tabela com as duas colunas;
5. só então o T1 completo, sobre o protocolo corrigido.

**Pendências antes de executar:**
- autorização do teto;
- decidir se o E3 com a data de criação dos itens do ORCID (§4) entra como sensibilidade já
  nesta rodada (exige ~4.000 leituras ORCID gratuitas).
