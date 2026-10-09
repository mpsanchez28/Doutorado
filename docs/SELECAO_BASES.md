# Seleção das bases (recortes por área) — H3

**Decisão (09/10/2026):** 4 recortes, todos no **nível de campo** (Concepts nível 0 do
OpenAlex), formando um gradiente de densidade de coautoria para testar a **H3** ("o ganho do
texto cresce com a esparsidade da rede"). Configuração: `configs/bases.yaml`.

| Ordem | Base | Concept (nível 0) | Wikidata | Works no OpenAlex | Densidade esperada |
|---:|---|---|---|---:|---|
| 1 | Medicina | `C71924100` Medicine | Q11190 | ~83M | alta |
| 2 | Ciência da Computação | `C41008148` Computer science | Q21198 | ~165M | intermediária |
| 3 | Matemática | `C33923547` Mathematics | Q395 | ~42M | baixa |
| 4 | Economia | `C162324750` Economics | Q8134 | ~23M | baixa |

IDs conferidos na API (nome e nível). Os IDs Wikidata servem também ao alinhamento
ontológico pedido pela banca (T16).

## Justificativas
- **Gradiente:** a variável da H3 é a densidade da rede de coautoria; os 4 campos cobrem do
  polo denso (equipes grandes, Medicina) ao esparso (1–3 autores, Matemática e Economia).
- **Dois polos baixos (Matemática e Economia):** dão robustez à extremidade esparsa (n=4 em
  vez de n=3) — as duas ficam próximas em densidade, então divergências entre elas medem a
  variância da própria tendência.
- **Nível de campo para todas, incluindo Computação:** compara "campo × campo". A base IA
  (5 sub-conceitos), usada em todos os experimentos até out/2026, fica como **legado** (fora
  do gradiente) para reprodutibilidade.
- **Mesmo protocolo para todas:** coleta temática, parada por **autores distintos**
  (`target_authors: 60000`) — densidade passa a ser propriedade da área, não da coleta.
  Medicina (antes *snowball*) e Computação (antes sub-campo, parada por works) são re-coletadas.

## Achado crítico: a ordem padrão da API enviesa a densidade

A consulta temática devolve os trabalhos **ordenados por citações (decrescente)**. Como só
coletamos uma fração ínfima de cada campo (~0,1–0,3%), a ordem **vira a amostra**.
Comparação de autores/artigo (n=200 por célula, seed 42, ≥2004, inglês, com abstract):

| Área | Mais citados (média · mediana) | Amostra aleatória (média · mediana) | Inflação |
|---|---:|---:|---:|
| Medicina | 15,9 · 7 | **5,3 · 4** | 3,0× |
| Computação | 6,6 · 3 | **3,4 · 2** | 1,9× |
| Economia | 8,1 · 3 | **2,9 · 2** | 2,8× |
| Matemática | 5,4 · 3 | **3,1 · 2** | 1,7× |

Nos mais citados, **Economia pareceria mais densa que Computação** — o gradiente se inverte
e a H3 seria testada sobre um artefato. Com amostragem aleatória, o gradiente esperado
aparece: Medicina > Computação > Matemática ≈ Economia.

**Implicação para resultados anteriores:** a base IA legada também foi coletada pelos mais
citados — é o "topo citado" da IA. Declarar como limitação; a re-coleta permite comparar.

## Amostragem proposta (pendente de aprovação)
Amostra aleatória **pura** de trabalhos é representativa, mas fragmenta a rede (autores
raramente reaparecem → verdade fundamental vazia). Proposta que concilia
representatividade e estrutura:

1. Sortear trabalhos aleatórios da área (`sample` + várias `seed`, reprodutível) → autores
   desses trabalhos = **candidatos a semente**.
2. Manter como sementes os autores **elegíveis** (higienização E1–E8, `docs/HIGIENIZACAO.md`).
3. Coletar o **histórico completo** de cada semente na área (2004–2026) → seus coautores
   entram no catálogo; T0/T1 das sementes ficam completos.
4. Parar ao atingir `target_authors` pessoas distintas.

Responde também à crítica "uma semente gera viés": são milhares de sementes aleatórias.
