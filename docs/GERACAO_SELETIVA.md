# Geração seletiva em cascata

Terceiro passo da fase de modelagem, depois da [linha de base](LINHA_BASE.md) e da
[ablação do KG](ABLACAO_KG.md). Código: `models/kg_ltr.py` (`cascade_pairs`, `stage1_params`),
`scripts/cascade_eval.py`, `scripts/report_cascata.py`. Resultados em
[RESULTADOS_GERACAO_SELETIVA.md](RESULTADOS_GERACAO_SELETIVA.md).

## 1. Motivação

Na avaliação padrão (LINHA_BASE.md §9), entre as coautorias novas **alcançáveis**, a maior
perda das áreas densas estava na geração. Elas estão ligadas ao alvo por algum meta-caminho do
KG, mas ficam fora dos 1.000 candidatos que o ranqueador recebe: 68% em Medicina e 58% em
Computação.

O top-1000 vinha da União RRF, em que cada gerador pesa igual. Ela não sabe, por exemplo, que
em Medicina uma posição alta em "mesma instituição" vale mais que uma posição alta em
"tópicos".

## 2. Desenho

```
13 geradores ──► união dos top-1000 de cada um (conjunto ampliado; mediana 4.600–5.400 por alvo)
                         │
         etapa 1: LightGBM binário (pontual) dá uma nota a cada candidato
                         │  top-1000
         etapa 2: LambdaMART (o mesmo do treino temporal) ordena
```

- **Conjunto ampliado.** Inclui o top-1000 de popularidade, ausente da União RRF. Em Medicina,
  pesquisadores muito produtivos são coautores frequentes.
- **Etapa 1.** Usa os mesmos atributos da etapa 2, mais a nota e a posição na União RRF.
  Hiperparâmetros: 300 árvores de 15 folhas, ≥ 200 pares por folha, L2 = 5. Treina com todos
  os positivos e 2% dos negativos, porque o conjunto ampliado tem milhões de pares por base;
  como só a ordem importa, a subamostragem não distorce a seleção.
- **Treino temporal com metades disjuntas.** As consultas de treino (sementes + candidatos com
  coautoria nova em 2019–2021, até 4.000) são divididas ao acaso em duas metades:
  - a metade A treina a etapa 1;
  - a metade B recebe o top-1000 escolhido pela etapa 1 e treina a etapa 2.

  Assim, a etapa 2 aprende com listas produzidas por um modelo que não viu aquelas consultas,
  exatamente como no teste.
- **Teste.** KG 2021 → T1, mesmos alvos e gabaritos (estrito e padrão) da linha de base.

**Variantes da etapa 2:**
- só a etapa 1, sem etapa 2;
- etapa 1 → LTR com os atributos do treino temporal;
- etapa 1 → LTR com a nota da etapa 1 como atributo extra.

**Comparações** (teste pareado, Bonferroni): a cascata contra o LTR temporal sobre a União RRF
(RESULTADOS_LTR_TEMPORAL.md) e contra a própria União RRF.

**Ressalva de comparação.** A etapa 2 da cascata treina com cerca de 2.000 consultas (a metade
B). O LTR temporal de referência treinou com 3.000. A comparação é, portanto, conservadora
contra a cascata.

## 3. Resultados e leitura (11/10/2026)

**1. A etapa 1 gera melhor, sobretudo em Medicina.** Alcance@1000 na avaliação padrão:

| | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| União RRF | 30,5 | 38,8 | 65,7 | 57,5 |
| Etapa 1 | 37,5 | 42,7 | 70,2 | 62,9 |
| Ganho relativo | **+23%** | +10% | +7% | +9% |

O ganho é maior onde o gargalo de geração era maior. Na etapa 1 de Medicina, Adamic-Adar e
PageRank respondem por 64% do ganho: a etapa 1 aprende a confiar na vizinhança de coautoria,
que a RRF diluía com listas densas de tópico e texto. Nas outras bases, ela se apoia sobretudo
na própria nota da RRF, refinada por acoplamento e tópicos.

**2. O ganho de geração não chega ao topo da lista.** O resultado final da cascata empata com o
LTR temporal sobre a União RRF em todas as bases e métricas. Nenhuma diferença é significativa:

| R@50 / R@200, avaliação padrão | Medicina | Computação | Matemática | Economia |
|---|---:|---:|---:|---:|
| LTR temporal (União RRF → LTR) | 12,1 / 21,0 | 23,8 / 32,9 | 37,2 / 53,8 | 33,6 / 47,3 |
| Cascata (etapa 1 → LTR) | 12,1 / 20,9 | 23,5 / 33,5 | 36,3 / 53,9 | 33,5 / 47,1 |

As coautorias recuperadas a mais entram na lista, mas ficam entre as posições 200 e 1.000.
Com os sinais atuais, elas são indistinguíveis dos não-coautores. São justamente os casos
difíceis, que a RRF já deixava de fora por terem sinais fracos.

**3. Leitura.** Para listas do tamanho que um usuário consome (top-10 a top-200), o gargalo
**não é a geração, e sim a qualidade dos sinais** que separam um futuro coautor de um candidato
qualquer. Há espaço na ordenação: no top-1000 da etapa 1 estão 37,5% (Medicina) a 70,2%
(Matemática) das coautorias alcançáveis, e o top-50 acerta 12% a 37%. Mais candidatos não
ajudam enquanto o ranqueador não souber distingui-los.

**Decisões.**
- O **LTR temporal sobre a União RRF continua sendo o modelo principal**: mais simples, com o
  mesmo desempenho no topo.
- A cascata fica documentada como resultado negativo informativo, e como opção para cenários
  de listas longas (ex.: triagem de 1.000 nomes).
- O próximo passo deve atacar os **sinais**, não a geração: conteúdo forte (SPECTER2 no lugar
  do TF-IDF), que já é o grupo de maior peso nas áreas esparsas.
