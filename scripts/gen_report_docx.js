const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, LevelFormat, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, Footer,
} = require("docx");

const ROOT = process.argv[2], OUT = process.argv[3];
const D = JSON.parse(fs.readFileSync(ROOT + "/runs/final_comparison.json"));   // base IA (T0-ativos, 8 modelos)
const AI = JSON.parse(fs.readFileSync(ROOT + "/runs/cool_cold_frac0.8.json"));  // base IA (cool/cold)

const AC = "1F4E79", ZEBRA = "EEF3F8", GOOD = "DDEBD8", BAD = "F8D7DA", CW = 9360;
const bd = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
const cm = { top: 60, bottom: 60, left: 90, right: 90 };
const txt = (t, o = {}) => new TextRun({ text: t, ...o });
const P = (c, o = {}) => new Paragraph({ children: Array.isArray(c) ? c : [txt(c)], ...o });
const H = (n, t) => new Paragraph({ heading: n, children: [txt(t)] });
const hc = (t, w) => new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: { fill: AC, type: ShadingType.CLEAR }, verticalAlign: VerticalAlign.CENTER, children: [P([txt(t, { bold: true, color: "FFFFFF", size: 18 })])] });
const bc = (t, w, o = {}) => new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: cm, shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined, verticalAlign: VerticalAlign.CENTER, children: [P([txt(String(t), { bold: !!o.bold, size: 18 })], { alignment: o.align || AlignmentType.LEFT })] });
function table(widths, header, rows) {
  const tr = [new TableRow({ tableHeader: true, children: header.map((h, i) => hc(h, widths[i])) })];
  rows.forEach((r, ri) => tr.push(new TableRow({ children: r.map((c, i) => bc(c.t ?? c, widths[i], { fill: c.fill ?? (ri % 2 ? ZEBRA : undefined), bold: c.bold, align: c.align })) })));
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: widths, rows: tr });
}
const bullets = items => items.map(it => new Paragraph({ numbering: { reference: "b", level: 0 }, children: Array.isArray(it) ? it : [txt(it)] }));
const numbered = items => items.map(it => new Paragraph({ numbering: { reference: "n", level: 0 }, children: Array.isArray(it) ? it : [txt(it)] }));
const img = (file, w, h, cap) => [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80 }, children: [new ImageRun({ type: "png", data: fs.readFileSync(ROOT + "/docs/" + file), transformation: { width: w, height: h }, altText: { title: file, description: file, name: file } })] }),
  P([txt(cap, { italics: true, size: 16, color: "666666" })], { alignment: AlignmentType.CENTER, spacing: { after: 120 } })];

const R = (j, m, sc, mk, k) => (sc === "overall" ? j[m].overall : j[m].by_regime[sc])[k][mk] * 100;
const cnt = D["Topology (Graph Coauthor)"].regime_counts;
const aicnt = AI["Topology (Graph Coauthor)"].regime_counts;
const BASE = "Topology (Graph Coauthor)";
const MM = [["Hybrid (Graph + RandomForest)", "Híbrido RF"], ["Text (SciBERT)", "Texto (SciBERT)"],
            ["GNN-rerank", "GNN-rerank"], ["Hybrid-cand", "Cand. híbridos"], ["Sup-Hybrid", "Sup-Hybrid"],
            ["Fusion (CNN+GNN)", "Fusão (CNN+GNN)"], ["Ideal Topology (Oracle)", "Oráculo (teto)"]];
const baselineCmp = () => {
  const b = R(D, BASE, "overall", "R", "200");
  const rows = [[{ t: "Baseline (Common Neighbors)" }, { t: b.toFixed(2), align: AlignmentType.RIGHT }, { t: "—", align: AlignmentType.RIGHT }, { t: R(D, BASE, "overall", "MRR", "10").toFixed(2), align: AlignmentType.RIGHT }, { t: R(D, BASE, "overall", "NDCG", "10").toFixed(2), align: AlignmentType.RIGHT }]];
  MM.forEach(([m, l]) => { const r = R(D, m, "overall", "R", "200"); const dl = r - b;
    rows.push([{ t: l }, { t: r.toFixed(2), align: AlignmentType.RIGHT }, { t: (dl >= 0 ? "+" : "") + dl.toFixed(2), align: AlignmentType.RIGHT, fill: (m !== "Ideal Topology (Oracle)" && dl > 0) ? GOOD : (dl < 0 ? BAD : undefined), bold: true }, { t: R(D, m, "overall", "MRR", "10").toFixed(2), align: AlignmentType.RIGHT }, { t: R(D, m, "overall", "NDCG", "10").toFixed(2), align: AlignmentType.RIGHT }]); });
  return table([3200, 1500, 1500, 1580, 1580], ["Modelo", "Recall@200", "Δ vs Baseline", "MRR@10", "NDCG@10"], rows);
};
const aiTable = () => {
  const MA = [["Topology (Graph Coauthor)", "Baseline (CN)"], ["Hybrid (Graph + RandomForest)", "Híbrido RF"], ["Text (SciBERT)", "Texto"], ["Hybrid-cand", "Cand. híbridos"]];
  const rows = MA.map(([m, l]) => { const co = R(AI, m, "cool", "R", "200"), cd = R(AI, m, "cold", "R", "200");
    return [{ t: l }, { t: co.toFixed(1), align: AlignmentType.RIGHT, fill: co >= 7 ? GOOD : undefined }, { t: cd.toFixed(1), align: AlignmentType.RIGHT, fill: cd >= 4 ? GOOD : (cd < 0.1 ? BAD : undefined), bold: true }]; });
  return table([4000, 2680, 2680], ["Modelo", `cool R@200 (n=${aicnt.cool})`, `cold R@200 (n=${aicnt.cold})`], rows);
};

const doc = new Document({
  styles: { default: { document: { run: { font: "Arial", size: 21 } } }, paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, color: AC, font: "Arial" }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, color: AC, font: "Arial" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } }] },
  numbering: { config: [
    { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 280 } } } }] },
    { reference: "n", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 280 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 4, color: AC, space: 6 } }, children: [txt("coauthor-rec · Relatório científico · pág. ", { size: 16, color: "666666" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "666666" })] })] }) },
    children: [
      ...Array(4).fill(0).map(() => P("")),
      P([txt("Predição de Coautorias com CNN e GNN", { size: 40, bold: true, color: AC })], { alignment: AlignmentType.CENTER }),
      P(""), P([txt("Relatório Científico — Construção, Resultados e Validação da Tese", { size: 22, color: "333333" })], { alignment: AlignmentType.CENTER }),
      ...Array(5).fill(0).map(() => P("")),
      table([3000, 6360], ["Campo", "Valor"], [
        ["Doutorando", "Marcos Paulo Sanchez"], ["Orientador", "Prof. Dr. Luciano A. Digiampietri"],
        ["Programa", "PPgSI — EACH/USP"],
        ["Bases", "Médica (snowball, densa) e IA temática (45.732 autores, esparsa)"],
        ["Protocolo", "Predição de links T0→T1; IC95% bootstrap; Wilcoxon+Bonferroni; PYTHONHASHSEED=0"]]),
      new Paragraph({ children: [new PageBreak()] }),
      P([txt("Sumário", { size: 26, bold: true, color: AC })]),
      new TableOfContents("Sumário", { hyperlink: true, headingStyleRange: "1-2" }),
      new Paragraph({ children: [new PageBreak()] }),

      H(HeadingLevel.HEADING_1, "1. Resumo executivo"),
      P("Investigamos a recomendação de coautores como predição de links futuros, comparando, sob um protocolo único, abordagens estruturais (topologia, Random Forest, GNN heterogênea) e textuais (SciBERT/CNN), além de sua fusão e do enriquecimento por IA Generativa. Principal achado: o gargalo não é a representação, e sim a GERAÇÃO DE CANDIDATOS — a topologia alcança apenas ~5% dos coautores futuros (mesmo a 3 saltos), enquanto o sinal textual recupera colaborações fora da estrutura. Em redes esparsas (domínio de IA) e, sobretudo, no cold-start, o texto é decisivo — onde a topologia é nula, é a única fonte de sinal. A hipótese da tese confirma-se numa forma refinada (ver Seção 9)."),

      H(HeadingLevel.HEADING_1, "2. Problema e hipóteses"),
      P("Problema: dado um autor-alvo e seu histórico até um instante T0, recomendar potenciais novos coautores, validando contra colaborações reais observadas no período seguinte T1."),
      P([txt("Hipótese central (qualificação): ", { bold: true }), txt("a combinação de representações textuais (CNN) e estruturais (GNN) supera cada uma isolada.")]),
      P([txt("Hipótese refinada (este trabalho): ", { bold: true }), txt("o valor do sinal textual está em ampliar o espaço de candidatos para além da vizinhança topológica — sendo decisivo quando a rede é esparsa ou o autor não tem histórico (cold-start), e complementar (não dominante no topo) quando há estrutura rica.")]),

      H(HeadingLevel.HEADING_1, "3. Arquitetura e fluxo metodológico"),
      P("O sistema organiza-se em coleta/preparação, construção do Grafo de Conhecimento heterogêneo, duas vertentes de modelagem (estrutural e textual), geração de candidatos e avaliação temporal estratificada por regime de conectividade (warm/cool/cold)."),
      ...img("diagrama_fluxo.png", 620, 350, "Figura 1 — Fluxo metodológico. O gargalo está na geração de candidatos."),

      H(HeadingLevel.HEADING_1, "4. Construção passo a passo (a partir do baseline)"),
      P("Cada etapa segue o ciclo científico motivação → método → resultado → conclusão. O baseline de referência é o Common Neighbors (heurística de vizinhança de 2 saltos)."),
      ...numbered([
        [txt("Baseline (Common Neighbors). ", { bold: true }), txt("Método: candidatos de 2 saltos ranqueados por nº de vizinhos em comum. Resultado: referência consistente, forte no topo do ranking. Conclusão: ponto de partida; limitado pela topologia.")],
        [txt("Random Forest (reranking supervisionado). ", { bold: true }), txt("Método: RF sobre features topológicas (CN, Jaccard, Adamic-Adar) nos candidatos de 2 saltos. Resultado: ganho significativo de recall sobre o baseline. Conclusão: combinar sinais topológicos ajuda — mas continua preso ao 2-hop.")],
        [txt("Módulo textual (SciBERT/CNN). ", { bold: true }), txt("Método: embeddings de título+abstract; similaridade entre autores. Resultado: fraco no geral, mas forte em baixa conectividade. Conclusão: o conteúdo carrega sinal que a estrutura não tem.")],
        [txt("GNN heterogênea. ", { bold: true }), txt("Método: reranker 2-hop com agregação sobre o KG. Resultado: empata o RF. Conclusão: a representação profunda não supera o RF sob o mesmo espaço de candidatos.")],
        [txt("Fusão end-to-end (CNN+GNN). ", { bold: true }), txt("Método: z_texto ⊕ z_grafo → camada densa. Resultado: empata a GNN. Conclusão: fundir representações não basta.")],
        [txt("Enriquecimento por IA Generativa. ", { bold: true }), txt("Método: atributos de alto nível (estilo, contribuição) extraídos por LLM (OpenAI e Claude) como nós do KG. Resultado: neutro/negativo. Conclusão: categorias ruidosas não agregam.")],
        [txt("Candidatos híbridos (estrutura ∪ texto). ", { bold: true }), txt("Método: ampliar o pool com vizinhos textuais. Resultado: empata/supera o RF em cobertura; o ganho vem do alcance. Conclusão: o gargalo era a geração de candidatos.")],
      ]),

      H(HeadingLevel.HEADING_1, "5. Comparação com o baseline"),
      P([txt("Δ vs Baseline = ganho em Recall@200 sobre o Common Neighbors (base de IA, autores ativos em T0). ", {}), txt("Verde = ganho; vermelho = perda. Oráculo = teto topológico.", { italics: true })]),
      baselineCmp(),
      ...img("metricas_overall.png", 600, 337, "Figura 2 — Métricas × K (autores ativos em T0; barras = IC95%)."),

      H(HeadingLevel.HEADING_1, "6. O insight central: o espaço de candidatos"),
      P("Os modelos topológicos só recomendam quem está a 2 saltos. Em redes esparsas isso alcança pouquíssimos coautores futuros; o texto traz candidatos fora da estrutura."),
      ...img("diagrama_candidatos.png", 640, 268, "Figura 3 — Por que o texto alcança o que a topologia não vê."),
      P([txt("Exemplo concreto (regime cool). ", { bold: true }), txt("O autor Icek Ajzen (3 coautores em T0) volta a colaborar, em T1, com Martin Fishbein — dupla de referência da Teoria do Comportamento Planejado. O modelo Textual recupera essa coautoria na 4ª posição; o Random Forest e o Baseline não a trazem nem no top-50, pois Fishbein está fora da vizinhança de 2 saltos de Ajzen. A afinidade temática (texto) prevê a colaboração que a estrutura não alcança.")]),

      H(HeadingLevel.HEADING_1, "7. Avanço principal: cold-start"),
      P("Coletamos uma base temática de IA (45.732 autores) que popula os regimes de baixa conectividade (cool n=783, cold n=53). Com poder estatístico real:"),
      aiTable(),
      ...img("ai_cool_cold.png", 620, 238, "Figura 4 — Recall@K por regime (base de IA). No cold, topologia ≈ 0; só o texto sobe."),
      P([txt("No cold-start os modelos topológicos zeram (vizinhança vazia); apenas o texto recomenda (Texto vs RF +6,2pp, p=0,0009). Em cool, texto/híbridos superam o RF (+4,0pp, p=1,2×10⁻²³).", {})]),

      H(HeadingLevel.HEADING_1, "8. Experimentos de validação"),
      P([txt("8.1 Compensa ir para 3 saltos? ", { bold: true }), txt("Medindo o alcance (fração de coautores futuros no pool) e o custo (tamanho do pool):")]),
      table([2200, 1790, 1790, 1790, 1790], ["regime", "alcance 2-hop", "alcance 3-hop", "pool 2-hop", "pool 3-hop"], [
        ["geral", "3,5%", "4,9%", "22", "82"], ["warm", "3,8%", "5,6%", "33", "119"],
        ["cool", "3,3%", "4,0%", "8", "33"], [{ t: "cold" }, { t: "0%", bold: true }, { t: "0%", bold: true }, "0", "0"]]),
      P("Não compensa: +1–2pp de alcance ao custo de ~4× mais candidatos; zero em cold. Mesmo a 3 saltos, a topologia alcança só ~5% dos coautores futuros — ~95% estão fora do grafo.", { spacing: { before: 80 } }),
      P([txt("8.2 A riqueza heterogênea da KG ajuda a GNN? ", { bold: true }), txt("Ablação (mesmas features/épocas/seed):")]),
      table([4680, 2340, 2340], ["GNN", "warm R@200", "cool R@200"], [
        ["KG completo (6 relações)", "4,01%", "3,35%"], ["só co-autoria", "4,00%", "3,35%"]]),
      P("Idênticos: as relações extras (venue, conceito, instituição, citação) e o enriquecimento GenAI não agregam à recomendação. O sinal de grafo útil é a co-autoria.", { spacing: { before: 80 } }),

      H(HeadingLevel.HEADING_1, "9. Validação da tese"),
      table([4200, 2080, 3080], ["Hipótese", "Veredito", "Evidência"], [
        [{ t: "Fusão CNN+GNN > cada isolada (literal)" }, { t: "Não confirmada", fill: BAD, bold: true }, "Fusão empata GNN/RF (warm 3,99/cool 3,35)"],
        [{ t: "Texto amplia candidatos > topologia (refinada)" }, { t: "Confirmada", fill: GOOD, bold: true }, "cool +4,0pp p=1e-23; supera oráculo topológico"],
        [{ t: "Texto essencial no cold-start" }, { t: "Confirmada", fill: GOOD, bold: true }, "topologia 0%; texto 6,2% (p<0,001)"],
        [{ t: "Enriquecimento GenAI melhora a GNN" }, { t: "Não confirmada", fill: BAD, bold: true }, "ablação: KG completo ≈ só co-autoria"]]),
      P([txt("Veredito geral: ", { bold: true }), txt("a tese é validada em forma refinada — a contribuição multimodal não está em fundir representações, e sim em usar a semântica textual para ampliar o espaço de candidatos, decisiva em redes esparsas e no cold-start, onde a topologia falha. É um resultado positivo, defensável e original.")]),

      H(HeadingLevel.HEADING_1, "10. Discussão — lacunas, dados semânticos e combinações"),
      P([txt("Lacunas (a explorar): ", { bold: true }), txt("encoder congelado (sem fine-tuning); learning-to-rank sobre o pool híbrido; GNN com atenção (HAN); ablação do sinal textual (título × abstract × conceitos); generalização a mais domínios.")]),
      P([txt("Mais dados semânticos: ", { bold: true })]),
      ...bullets([
        "Texto completo (introdução/conclusão), não só o abstract.",
        "Referências como texto (títulos citados, contexto de citação).",
        "Perfil textual agregado do autor e conceitos/venue como texto.",
        "Ponderação temporal dos abstracts (deriva de interesse).",
        "Fine-tuning contrastivo do encoder em pares de coautoria; SPECTER2 (citation-informed).",
      ]),
      P([txt("Combinações promissoras: ", { bold: true })]),
      ...bullets([
        "Duas etapas: texto gera candidatos (recall) → RF reranqueia a união (precisão no topo).",
        "Learning-to-rank (LightGBM/LambdaMART) sobre o pool híbrido com features calibradas.",
        "Score fusion ponderado por regime (peso do texto ↑ em cool/cold).",
        "Encoder fine-tuned combinado às estratégias acima.",
      ]),

      H(HeadingLevel.HEADING_1, "11. Caminhos futuros (sequência pós-trabalho)"),
      ...numbered([
        "Reranker de duas etapas (texto-recall → topologia-precisão) — o avanço mais provável sobre o RF.",
        "Fine-tuning do encoder científico e ablação dos sinais textuais.",
        "Estudo de generalização multi-domínio (denso × esparso) e curva densidade × ganho do texto.",
        "Recomendação explicável (por que este coautor?) usando os sinais textuais.",
        "Artigos: (a) cold-start de coautoria com semântica; (b) o gargalo de candidatos em redes esparsas.",
      ]),

      H(HeadingLevel.HEADING_1, "12. Conclusão"),
      P("O trabalho caracteriza, com rigor estatístico e em dois domínios contrastantes, onde cada fonte de informação importa na recomendação de coautoria. A estrutura domina autores bem conectados e o topo do ranking; a semântica textual é insubstituível quando a estrutura é esparsa ou ausente (cold-start). A contribuição central — a fusão útil é de fontes de candidatos, não de representações — reorienta o problema e abre caminhos claros de continuidade para a tese e para artigos."),
    ],
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("escrito", OUT, (b.length / 1024 | 0) + "KB"); });
