# Sensibilidade ao teto de coautores por artigo (T3)

Resposta à banca (Thiago): *"por que 50 e não 20?"*. Re-avaliação na base IA com
`max_coauthors_per_work` ∈ {10, 20, 50, ∞}. Reprodução:

```bash
PYTHONHASHSEED=0 python scripts/sens_cap.py   # -> runs/sens_cap/sens_cap.json
```

## Resultados (Recall@K, base IA, alvos T0-ativos)
| Teto | Arestas de coautoria | Modelo | R@10 | R@50 | R@200 |
|---:|---:|---|---:|---:|---:|
| **10** | 52.455 | Baseline | 1,06 | 1,55 | 2,42 |
| | | Híbrido RF | 2,22 | 4,02 | 5,75 |
| | | **2 etapas** | **3,38** | **6,44** | **9,10** |
| **20** | 75.749 | Baseline | 0,94 | 1,28 | 1,65 |
| | | Híbrido RF | 2,04 | 3,63 | 5,27 |
| | | **2 etapas** | **2,50** | **6,00** | **8,40** |
| **50** | 109.338 | Baseline | 0,94 | 1,20 | 1,29 |
| | | Híbrido RF | 2,09 | 3,29 | 3,74 |
| | | **2 etapas** | **2,57** | **5,11** | **7,10** |
| **∞** | 187.358 | Baseline | 0,88 | 1,17 | 1,22 |
| | | Híbrido RF | 1,92 | 3,03 | 3,35 |
| | | **2 etapas** | **2,36** | **4,74** | **6,64** |

## Leitura
1. **A conclusão é robusta ao teto.** Em *todos* os cortes (10, 20, 50, ∞) a ordem
   **2 etapas > Híbrido RF > Baseline** se mantém, com o 2 etapas dominando em todo K. A
   escolha entre 20 e 50 **não muda o veredito** — que é o ponto da pergunta da banca.
2. **Por que o Recall absoluto cai quando o teto sobe?** Porque o teto **redefine a verdade
   fundamental**: com teto maior, artigos de muitos autores geram mais arestas de coautoria
   (52 mil → 187 mil), então há mais coautores "possíveis" e o denominador de `C_new(a)`
   cresce — a mesma tarefa fica mecanicamente mais difícil. Ou seja, os números **não são
   comparáveis entre tetos** (tarefas diferentes); o que se compara é a **ordem dos modelos**,
   que é invariante.
3. **Justifica o teto de 50.** O salto de arestas de 50→∞ (109k→187k, +71%) mostra que os
   consórcios de muitos autores geram uma fração grande de arestas de baixa informação; o teto
   as remove sem alterar a conclusão. O teto de 50 é um meio-termo defensável (a base IA tem
   ~6,6 autores/artigo; a maioria dos artigos nem chega ao teto).

> Nota metodológica para a tese: reportar o teto como **hiperparâmetro do protocolo** com este
> teste de sensibilidade em anexo, e sempre comparar modelos **sob o mesmo teto**.
