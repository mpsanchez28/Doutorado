# Especificação do protocolo corrigido de 2021

**Prioridade da frente de robustez.** A auditoria ([AUDITORIA_SELECAO.md](AUDITORIA_SELECAO.md))
mostrou que o protocolo original de 2021 usa informação posterior ao corte na seleção das
sementes, na elegibilidade e nos metadados. Este documento especifica a **avaliação principal
corrigida**. O piloto do T4 (Economia 2019) valida a infraestrutura, mas não a substitui.

- **Referência histórica preservada:** `main` em `477dcd1`, com os resultados em
  `runs/ltr_temporal/`, `runs/linha_base/` etc. Nada disso é alterado.
- **Saídas do protocolo corrigido (universo v2):**
  - `runs/robustez/t4/reconstrucao_<base>_2021_v2/`: inventário, lacunas e comparação com a v1;
  - `runs/robustez/t4/reconstrucao_<base>_2021_v2_coletado_{ate2026-10-08,h3}/`: os dois
    horizontes;
  - dados coletados em `data/robustez/t4/<base>_2021/`;
  - contabilidade em `runs/robustez/t4/coleta_<base>_2021/`.
- **Pastas sem `_v2`:** usam o universo v1 (defeituoso). Estão preservadas e marcadas
  `INVALIDO.json` (`runs/robustez/t4/INVALIDOS_v1.json`).
- **Decisões metodológicas** (classificação, estratégia temporal, estatística, neurais):
  [ESPECIFICACAO_METODOLOGICA.md](ESPECIFICACAO_METODOLOGICA.md), que prevalece sobre §5 deste
  documento.

**Estado (14/10/2026):**
- **Coleta autorizada** em 14/10/2026, com teto **total de 2.400 créditos** nas 4 bases.
  - 1ª rodada (lacunas v1), executada 13:39–14:35: 1.021 créditos.
  - 2ª rodada (lacunas v2 de Economia e Matemática), autorizada e executada às 15:05: 71
    créditos.
  - **Total: 1.092**, conferido na API.
- **Reconstrução v1:** executada 14:35–15:00 com o universo defeituoso (A0 da revisão). Foi
  **interrompida e invalidada**.
- **Reconstrução v2:** executada em Economia e Matemática, nos dois horizontes (§6).
- **3ª rodada** (complementação de Computação e Medicina, autorizada no mesmo teto, margem de 100),
  executada 16:20–17:03:
  - Computação **completa**: 595 créditos;
  - Medicina **INCOMPLETA**: 613 créditos; listas completas; enriquecimento parado no teto; faltam
    26.139 trabalhos e 470 instituições, ~533 créditos.
  - **Total de 2021: 2.300 de 2.400**; a API confere cada execução.
- **Entradas congeladas:** S1 (Economia, Matemática) e S2 (Computação, Medicina incompleta)
  (ESPECIFICACAO §2.4).
- **Desenho temporal [dependente de decisão]:** emenda E1, alternativas A e B (ESPECIFICACAO §3).
- **Métricas:** gravadas e **não examinadas**.

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
| **Alvos** | elegíveis com ≥ 1 coautoria nova em T1 | idem, sobre os elegíveis corrigidos | local | v2: Matemática 221 (3 anos) / 245 (completo); Economia 184 / 204 |
| **Candidatos** | `select_candidates` com as 1.000 sementes, laços ≤ 2021, teto 15 mil | **a mesma regra, aplicada só aos trabalhos das sementes do corte** (`candidate_universe_at_cut`); exclui só as sementes do corte; sementes fora do corte podem ser candidatas por laço legítimo | local | [verificado]: reprodução histórica com diferença 0 (teste separado); universo v2 com 0 violações. Tamanhos: 15.000 / 15.000 / 14.062 / 14.472 |
| **Expansão** | histórico 2017–2021 dos 15 mil | histórico 2017–2021 dos candidatos corrigidos; reaproveita os já coletados | lacunas | v2: novos 2.486 / 3.072 / 1.979 / 1.539, dos quais **ainda não consultados** 2.062 / 2.521 / 0 / 0 |
| **Limpeza e higienização** | sobre o corpus original | refeitas sobre o corpus corrigido; mesmas regras | local + ORCID | a executar |
| **Enriquecimento** | cache dos trabalhos do corpus original | cache + trabalhos novos da expansão | lacunas | incluído no custo |
| **KG** | KG ≤ 2021 | refeito sobre o corpus corrigido; `validate_kg` | local | a executar |
| **Treino temporal** | KG 2018 → rótulos 2019–2021; consultas = sementes + candidatos (até 3.000) | fase 2018 com o **próprio corte**: sementes sorteadas ≤ 2018, universo com laços ≤ 2018, corpus e enriquecimento próprios (ESPECIFICACAO §3.1) | local | [executado] em Economia e Matemática |
| **Avaliação** | estrita (principal) e padrão; M9; R@K, NDCG@10, Hits@K, MRR | idênticas | local | a executar |

**Custo da coleta das lacunas — estimativa HISTÓRICA da v1** (universo defeituoso; ±50%). Os
valores atuais estão em ESPECIFICACAO §7:

| | Medicina | Computação | Matemática | Economia | Total |
|---|---:|---:|---:|---:|---:|
| Candidatos novos | 745 | 1.451 | 1.943 | 1.533 | 5.672 |
| Trabalhos a coletar | ~3,8 mil | ~6,1 mil | ~8,0 mil | ~5,1 mil | ~23 mil |
| Créditos OpenAlex | ~186 | ~307 | ~402 | ~261 | **~1.160** |
| Leituras ORCID (gratuitas) | 408 | 839 | 1.022 | 211 | 2.480 |

Teto **autorizado** em 14/10/2026: **2.400 créditos** para as 4 bases, com o mesmo coletor do
piloto (contabilidade, retomada e parada no teto).

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
| **Corrigida — horizonte original** (descritiva) | 2021 | **2022-01-01 a 2026-10-08** | ~4,8 anos | `runs/robustez/t4/reconstrucao_<base>_2021_v2_coletado_ate2026-10-08/` |
| **Corrigida — 3 anos** (**principal**, ESPECIFICACAO §4.1) | 2021 | **2022-01-01 a 2024-12-31** | 3 anos | `…_2021_v2_coletado_h3/` |
| Piloto T4 | 2019 | 2020-01-01 a 2022-12-31 | 3 anos | `…_2019_v2_coletado_h3/` |
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

**Uso:** classificar cada E3 em "item criado até o corte", "item criado depois" e "sem data".
Reportar como **sensibilidade**, não como comprovação histórica.

**[executado]** em 14/10/2026 (`scripts/orcid_datas_reivindicacao.py`, leituras gratuitas).
- Elegíveis em 2021 com E3 "datado": Medicina 310 → 237, Computação 297 → 232, Matemática
  344 → 285, Economia 313 → 242.
- ~90% dos itens foram adicionados por integrações (Scopus, Crossref, WoS), não pela pessoa.
- Não altera a regra principal.

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
- **Correção:** a versão anterior dizia que ~300 alvos bastavam em Medicina. ~310 é o n para
  **80% de poder** (aproximação normal, α = 0,05 sem Bonferroni). Para a **precisão** desejada
  (semiamplitude ≤ δ/2) seriam necessários ~614, porque 1,96 × 2,2/√310 ≈ 0,245 pp > 0,175 pp.
  Poder e precisão são agora tratados separadamente (ESPECIFICACAO §4.5).
- Em Matemática e Economia, os alvos corrigidos (221 e 184 no horizonte de 3 anos) dão poder de
  ~7% e ~3% para δ em F1 (ESPECIFICACAO §7.4). O efeito observado na referência foi medido no
  teste já consultado e não serve de justificativa.

**Limitações da estimativa:**
- vem do protocolo original, não do corrigido;
- horizonte e treino diferentes;
- o horizonte de 3 anos tende a aumentar os zeros;
- a distribuição tem muitos zeros (IC por bootstrap);
- os alvos são tratados como independentes.

**Análise** (fixada em ESPECIFICACAO §4, que prevalece):
1. **Principal: Δ por área**, com IC do bootstrap de Poisson por pessoa no nível de F1 (98,75%), interpretado pela **estimativa e intervalo**, não só
   pela significância. Uma área sem significância não é tratada como ausência de efeito se o
   intervalo for compatível com δ, nem como presença se não for.
2. **Complementar: estimativa conjunta** com pesos fixados antes (§5.2). Responde à pergunta
   média e **não** é apresentada como prova de ganho em todas as áreas.
3. **Ampliação da amostra:** se a precisão por área for necessária, a opção auditada é
   **completar o sorteio 42** (sementes além das 1.000 primeiras: +152 em Economia, +415 em
   Matemática) antes dos sorteios 43–44 (ROBUSTEZ_T1_T4.md §3.6). A decisão não depende do
   resultado dos modelos e **não** será acionada por resultado (não se ampliam alvos para obter
   significância).

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
- **Estimativa:** média ponderada das médias por área. IC pelo **bootstrap de Poisson por
  pessoa**: um peso por pessoa canônica e réplica, o mesmo em todas as áreas e cortes
  (`coauthor_rec.eval.bootstrap`). Substitui o "estratificado por área, em blocos por pessoa",
  que não garantia a mesma multiplicidade para a mesma pessoa entre áreas.
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
| Elegíveis sem trabalho em T0 (*newcomers*) | **vazio por construção**: E5 (≥ 2 trabalhos) é calculado até o corte. Confirmado: 0 em Economia e Matemática 2021 e no piloto 2019. Só existem no protocolo histórico |

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
     todos). As incondicionais são medidas offline complementares; **não** validam uso real e não
     entram no teste pareado.
  4. Denominador de P@K quando a lista tem menos de K itens: K. O número de listas curtas é
     reportado.

### 5.4 Dependência estatística

**O que o intervalo considera:**
- **Bootstrap de Poisson por pessoa canônica** (ESPECIFICACAO §4.6): cada pessoa recebe um peso
  por réplica, aplicado a todas as suas observações;
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
5. **Entre cortes (T4):** com passado cumulativo, uma colaboração já observada **não** volta a
   ser nova. Repetições aparecem por:
   1. janelas sobrepostas que compartilham o mesmo primeiro evento;
   2. histórico incompleto (colaboração anterior fora da área ou sem resumo);
   3. mudança de identidade ou corpus entre cortes.

   "Colaboração recorrente" sendo nova duas vezes é defeito. Repetições são reportadas por
   tipo.

**Medidas planejadas:**
- reportar as contagens dessas sobreposições: alvos que compartilham coautores novos, pares
  recíprocos, trabalhos com positivos para > 1 alvo, pares repetidos entre cortes;
- **sensibilidade:** bootstrap em blocos por **componente** do grafo alvo–coautor-novo (alvos
  ligados por coautores novos em comum caem no mesmo bloco), e reestimativa removendo pares
  repetidos.

## 6. Execução (estado em 14/10/2026, 15:40)

| Etapa | Estado |
|---|---|
| Coleta 2021, lacunas v1 (4 bases) | executada, 1.021 créditos; dados válidos como dados |
| Reconstrução 2021 v1 | **inválida** (universo defeituoso); interrompida em Computação |
| Correção do universo (código, verificações, testes) | [implementado] [testado] |
| Piloto 2019 v2 (local, sem coleta) | [executado] [verificado]; métricas idênticas em 2 execuções |
| Coleta 2021, lacunas v2 de Economia e Matemática | executada: 18 + 53 = 71 créditos (API confere) |
| Reconstrução 2021 v2, Economia e Matemática, dois horizontes | [executado] [verificado: universo, KG, janelas, consultas] |
| Coleta de 2021 v2, Computação e Medicina | Computação completa (595); Medicina **INCOMPLETA** (613; enriquecimento pendente ~533) |
| Cópias congeladas S1/S2 e conjuntos recalculados | [executado] [verificado]; Economia e Matemática idênticas à v2 (exceto +2–5 trabalhos, E3) |
| Seleção de hiperparâmetros | **não executada**; desenho temporal **[dependente de decisão]** (ESPECIFICACAO §3, §5.1) |
| T1 completo | **suspenso** até a validação do pipeline corrigido |

Comandos usados (v2):

```bash
PYTHONHASHSEED=0 python scripts/reconstrucao_t4.py <base> --corte 2021 --n-sementes todas --sem-corpus      # inventário e lacunas v2
PYTHONHASHSEED=0 python scripts/coletor_t4.py <base> --corte 2021 --limite <teto> \
    --lacunas runs/robustez/t4/reconstrucao_<base>_2021_v2/lacunas.csv \
    --lacunas-anteriores runs/robustez/t4/reconstrucao_<base>_2021/lacunas.csv --prefixo v2_
scripts/reconstrucao_v2_econ_mat.sh                                                                          # piloto + 2 bases × 2 horizontes
```

Na 2ª rodada, cada base teve como teto o gasto anterior mais o dobro da estimativa empírica
(Economia 131; Matemática 314).
