# Avaliação multidimensional e explicabilidade sistemática

Fecha duas lacunas da qualificação (slide 15): **avaliação além do ranqueamento**
(diversidade e novidade) e **explicabilidade sistemática**. Base: IA, 2.003 autores-alvo
T0-ativos, catálogo de 32.835 autores recomendáveis. Reprodução:

```bash
PYTHONHASHSEED=0 python scripts/beyond_accuracy.py        # diversidade/novidade/cobertura
PYTHONHASHSEED=0 python scripts/explain_systematic.py     # explicabilidade sistemática
```

---

## 1. Diversidade, novidade e cobertura (lacuna #5)

Métricas *beyond-accuracy* (`src/coauthor_rec/eval/beyond.py`), reportadas **ao lado do
Recall** — isoladas não querem dizer nada (um recomendador aleatório é diverso e novo ao
máximo e inútil).

- **ILD@K** (diversidade intra-lista) = 1 − cosseno médio par-a-par dos perfis SciBERT.
- **Novidade@K** = auto-informação média −log₂ p(c), p(c) = grau de coautoria T0 / N.
- **Cobertura@K** = fração do catálogo que chega a ser recomendada a algum alvo.

### Resultados (K = 10)
| Modelo | Recall | ILD (diversidade) | Novidade | Cobertura |
|---|---:|---:|---:|---:|
| Baseline (2-hop) | 0,94% | **0,088** | 9,74 | 8,1% |
| Híbrido RF | 2,09% | 0,074 | 10,77 | 17,0% |
| Texto (SciBERT) | 1,41% | 0,035 | 11,51 | 15,6% |
| **2 etapas (RF→texto)** | **2,57%** | 0,056 | **12,05** | **24,0%** |

Em K = 20 a cobertura do 2 etapas chega a **34,2%** do catálogo (vs 10,0% do baseline).

### Novidade por regime (K = 10)
| Modelo | warm | cool | cold |
|---|---:|---:|---:|
| Baseline | 10,07 | 9,30 | 8,83 |
| 2 etapas | 11,93 | 12,12 | **13,67** |

### Leitura
- O **2 etapas domina**: melhor Recall **e** maior novidade **e** maior cobertura. Ele não
  compra acurácia recomendando hubs óbvios — ao contrário, alcança autores long-tail.
- O **baseline** tem a maior ILD (recomendados estruturalmente espalhados), mas é o pior em
  acurácia: diversidade sem relevância.
- O **texto** é o menos diverso (ILD 0,035) — coerente: ranqueia por afinidade temática,
  logo os recomendados são tematicamente próximos entre si.
- A **novidade cresce do warm ao cold** nos modelos textuais (8,8 → 13,7): no cold-start o
  sistema recomenda justamente autores pouco conectados que a topologia nunca alcançaria.

---

## 2. Explicabilidade sistemática (lacuna #3)

Em vez de explicar **um** par (demo `scripts/explain.py`), quantifica-se **toda**
recomendação do modelo vencedor por mecanismo de evidência, em T0:

- **Estrutural** = há coautor(es) em comum (alcance topológico 2-hop).
- **Temática** = há conceito(s) OpenAlex em comum (afinidade explícita).
- *Explicável* = estrutural **ou** temática.

### Resultados (2 etapas, top-10)
| Recorte | Explicável | Estrutural | Temática | Sem explicação | conc. comuns | cosseno |
|---|---:|---:|---:|---:|---:|---:|
| **Todas** | 99,4% | 60,9% | 98,6% | 0,6% | 5,3 | 0,93 |
| regime warm | 99,5% | 78,0% | 98,9% | 0,5% | 5,7 | 0,93 |
| regime cool | 99,4% | 39,6% | 98,3% | 0,6% | 4,6 | 0,93 |
| regime cold | 97,0% | **0,0%** | **97,0%** | 3,0% | 7,4 | 0,96 |
| **Acertos (T1)** | **100,0%** | 83,0% | 99,7% | 0,0% | 6,3 | 0,93 |

### Leitura (valida a tese)
- Quase **toda** recomendação é justificável (99,4%); entre as que **acertam** (viraram
  coautoria real em T1), **100%** têm explicação e 99,7% têm afinidade temática.
- A explicação **migra de estrutural para temática conforme esfria o regime**: warm 78%
  estrutural → cold **0%** estrutural, 97% temática. É a evidência interpretável do
  argumento central: sem coautores prévios, o que sustenta a recomendação é o **tema**.
- O cosseno alto e estável (~0,93–0,96) mostra que o sinal textual está presente em todos
  os regimes; a topologia é que desaparece no cold-start.

---

## Conclusão para a tese
As duas dimensões antes ausentes agora estão cobertas e **convergem com o achado
principal**: o modelo de 2 etapas não só é mais preciso, como é mais **diverso na medida
certa**, mais **novo** (long-tail), explora muito mais o **catálogo** e é **quase sempre
explicável** — e, no cold-start, essa explicação é inteiramente **temática**, confirmando
que o valor multimodal está em **ampliar e justificar o espaço de candidatos**, não em
fundir representações. Artefatos: `runs/beyond/beyond.json`,
`runs/beyond/explain_systematic.json`.
