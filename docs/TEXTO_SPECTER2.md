# Sinal textual forte: SPECTER2

Quarto passo da fase de modelagem. A [geração seletiva](GERACAO_SELETIVA.md) mostrou que o
gargalo do topo da lista é a **qualidade dos sinais**, não a geração de candidatos. O conteúdo
já é o grupo de maior peso nas áreas esparsas (36–45% do |SHAP| no LTR temporal), mas até aqui
era representado só por TF-IDF. Este passo troca, e depois combina, o TF-IDF por um encoder
científico moderno.

Código:
- `scripts/embed_specter2.py`: embeddings;
- `models/kg_generators.py`: gerador `texto_specter2` e função `text_variant`;
- opção `--texto` em `scripts/baseline_oracle.py` e `scripts/temporal_ltr.py`.

Resultados em [RESULTADOS_TEXTO_SPECTER2.md](RESULTADOS_TEXTO_SPECTER2.md).

## 1. Modelo

**SPECTER2** (Singh et al., 2023, *SciRepEval*) é o SciBERT treinado por contraste em
citações, em ~6 milhões de triplas de artigos de 23 áreas. Ele é acompanhado de *adapters*
por tarefa; usamos o de **proximidade** (`allenai/specter2`), indicado para encontrar artigos
parecidos.

- Entrada: `título [SEP] resumo`, até 512 tokens.
- Vetor do artigo: token `[CLS]`, 768 dimensões, normalizado L2.
- Perfil do autor: média dos vetores dos seus trabalhos **de T0**, renormalizada.
- Escore do par: cosseno dos perfis (só valores positivos geram candidato).

Por que SPECTER2 e não o SciBERT/SPECTER da qualificação:
- foi treinado para **similaridade entre artigos**, que é exatamente o uso aqui;
- cobre explicitamente medicina, computação, matemática e economia;
- supera o SPECTER original nas tarefas de proximidade do SciRepEval.

**Ambiente.** A biblioteca `adapters` exige um `transformers` mais novo que o do ambiente
principal. Os embeddings são gerados num ambiente isolado (`.venv-specter2`, criado com
`--system-site-packages` para reaproveitar o `torch`), que só escreve arquivos `.npz`. O resto
do pipeline não muda.
- Execução local na GPU do Mac (MPS): cerca de 34 trabalhos/s.
- Verificado que o adapter está ativo (`Stack[proximity]`) e altera os vetores.

## 2. Controle de vazamento

- Só trabalhos **até o fim de T0** recebem vetor (o script verifica). Os perfis do KG de 2018
  (treino temporal) usam apenas os trabalhos até 2018.
- **Ressalva:** o SPECTER2 foi pré-treinado com citações do Semantic Scholar, coletadas antes
  da sua publicação (2023), e elas podem incluir artigos de 2022–2023. O modelo pode, em tese,
  ter aprendido proximidades reforçadas por citações posteriores ao corte. É um vazamento
  **indireto e difuso**:
  - o modelo não vê coautorias;
  - ele não foi treinado nas nossas bases;
  - o efeito sobre artigos de até 2021 tende a ser pequeno.

  Fica declarado como limitação. Um teste de robustez seria comparar com um encoder treinado
  só com dados anteriores a 2021.

## 3. Desenho experimental

Três variantes do sinal textual, cada uma um sistema completo (geradores, União RRF e
atributos do LTR):

| Variante | Texto |
|---|---|
| `tfidf` | TF-IDF (o que vinha sendo usado) |
| `specter2` | SPECTER2 no lugar do TF-IDF |
| `ambos` | TF-IDF + SPECTER2 |

Avaliações:
1. **Gerador isolado** (`baseline_oracle.py --texto ambos`): R@50 e Alcance@1000 do SPECTER2
   comparados ao TF-IDF, no mesmo protocolo da linha de base.
2. **Modelo principal** (`temporal_ltr.py --texto …`): LTR temporal completo e ablação, nas
   avaliações estrita e padrão. Teste pareado contra a variante `tfidf`.

Ordem de execução: Economia, Matemática e Computação primeiro. Medicina (367 mil trabalhos de
T0) leva de 3 a 7 h localmente, conforme a carga da máquina, e roda em seguida.

## 4. Resultados e leitura — Computação, Matemática e Economia (11/10/2026)

Tabelas em [RESULTADOS_TEXTO_SPECTER2.md](RESULTADOS_TEXTO_SPECTER2.md). Medicina está em
processamento: embeddings de 367 mil trabalhos, cerca de 7 h locais.

**1. Como sinal isolado, o SPECTER2 é muito superior ao TF-IDF.**

| NDCG@10, gerador isolado (estrita) | Computação | Matemática | Economia |
|---|---:|---:|---:|
| TF-IDF | 0,65 | 1,67 | 0,56 |
| SPECTER2 | 1,54 | 3,24 | 1,08 |

O NDCG@10 dobra, aproximadamente. Em Economia, o R@50 padrão vai de 4,6 para 11,5, e o
alcance@1000 sobe em Computação e Economia.

**2. No modelo completo, o ganho desaparece.** O LTR temporal completo com SPECTER2, com
TF-IDF ou com os dois empata em todas as bases e avaliações. Nenhuma diferença é significativa
(α = 0,0016):

| R@50, estrita | Computação | Matemática | Economia |
|---|---:|---:|---:|
| TF-IDF | 6,21 | 11,85 | 7,37 |
| SPECTER2 | 6,25 | 12,44 | 6,95 |
| Os dois | 6,27 | 12,31 | 7,06 |

**3. Por quê: redundância com o KG.** O SPECTER2 ganha peso dentro do modelo (|SHAP| do grupo
texto de 11–18% com TF-IDF para 20–27% com SPECTER2), mas toma esse peso das outras relações
de conteúdo do KG (tópicos, citação e acoplamento), sem acrescentar acerto. É coerente com
o modo como o SPECTER2 foi treinado: por citações. O acoplamento bibliográfico e a citação
direta, que já estão no KG, capturam boa parte da mesma informação de forma explícita.

**4. Implicação para a tese.** É um resultado a favor do KG: **relações explícitas e auditáveis
(tópicos, citações) entregam no modelo final o mesmo que um encoder neural de 110 milhões de
parâmetros**. São mais baratas (sem GPU) e explicáveis (o caminho no KG justifica a
recomendação). O encoder continua útil onde o KG é pobre: autores sem citações ou tópicos em
comum com o alvo, e o regime cold. A análise por regime fica para depois de Medicina.

**Decisão provisória.** O TF-IDF continua no modelo principal, por ser mais simples e ter
desempenho igual. A decisão final depende de Medicina.
