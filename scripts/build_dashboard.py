"""Gera um dashboard HTML autocontido (docs/dashboard.html) a partir de
runs/final_comparison.json: tabelas interativas (toggle modelo↔métrica), seletores de
regime e K, gráficos (com IC95%) embutidos em base64, e comentários interpretativos.
Uso: python scripts/build_dashboard.py
"""
import base64
import json

from coauthor_rec.config import resolve

data = json.loads(resolve("runs/final_comparison.json").read_text())

ORDER = ["Topology (Graph Coauthor)", "Ideal Topology (Oracle)", "Hybrid (Graph + RandomForest)",
         "Text (SciBERT)", "GNN-rerank", "Hybrid-cand", "Sup-Hybrid", "Fusion (CNN+GNN)", "2-stage (RF→texto)"]
LBL = {"Topology (Graph Coauthor)": "Baseline (CN)", "Ideal Topology (Oracle)": "Oráculo (teto)",
       "Hybrid (Graph + RandomForest)": "Híbrido RF", "Text (SciBERT)": "Texto (SciBERT)",
       "GNN-rerank": "GNN-rerank", "Hybrid-cand": "Cand. híbridos", "Sup-Hybrid": "Sup-Hybrid", "Fusion (CNN+GNN)": "Fusão (CNN+GNN)", "2-stage (RF→texto)": "2 etapas (RF→texto)"}
ORDER = [m for m in ORDER if m in data]
KS = sorted(int(k) for k in data[ORDER[0]]["overall"])
METRICS = [["P", "Precision"], ["R", "Recall"], ["F1", "F1"],
           ["NDCG", "NDCG"], ["MRR", "MRR"], ["MAP", "MAP"]]
counts = data[ORDER[0]]["regime_counts"]


def b64(path):
    return base64.b64encode(resolve(path).read_bytes()).decode()


imgs = {r: b64(f"docs/metricas_{r}.png") for r in ("overall", "warm", "cool")}

payload = {"data": data, "order": ORDER, "labels": LBL, "ks": KS,
           "metrics": METRICS, "counts": counts, "imgs": imgs}

HTML = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard — Recomendação de Coautoria</title>
<style>
 :root{--bg:#0f1720;--card:#172331;--ink:#e7eef6;--mut:#9fb3c8;--ac:#1F4E79;--ac2:#3b82f6;--good:#16a34a;--line:#26384a}
 *{box-sizing:border-box} body{margin:0;font:14px/1.5 system-ui,Segoe UI,Roboto,Arial;background:var(--bg);color:var(--ink)}
 header{background:linear-gradient(120deg,#1F4E79,#0f1720);padding:22px 26px;border-bottom:1px solid var(--line)}
 h1{margin:0;font-size:20px} .sub{color:var(--mut);font-size:13px;margin-top:4px}
 main{padding:22px;max-width:1180px;margin:0 auto} .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:20px}
 .ctl{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
 label{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
 select,button{background:#0e1722;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:7px 11px;font:inherit;cursor:pointer}
 button.tg{background:var(--ac2);border-color:var(--ac2);color:#fff;font-weight:600}
 table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums} th,td{border:1px solid var(--line);padding:7px 9px;text-align:right}
 th{background:#11202f;color:var(--mut);font-weight:600} th.rh,td.rh{text-align:left;background:#11202f;color:var(--ink);font-weight:600;position:sticky;left:0}
 td.best{background:rgba(22,163,74,.18);color:#bbf7d0;font-weight:700}
 td .ci{color:var(--mut);font-size:11px}
 .note{color:var(--mut);font-size:12px;margin-top:8px}
 .grid{display:grid;grid-template-columns:1fr;gap:14px} img{width:100%;border-radius:8px;border:1px solid var(--line);background:#fff}
 h2{font-size:16px;margin:0 0 10px;color:#cfe0f0} .pill{display:inline-block;background:#0e1722;border:1px solid var(--line);border-radius:999px;padding:2px 10px;color:var(--mut);font-size:12px;margin-right:6px}
 ul{margin:8px 0 0 0;padding-left:20px} li{margin:5px 0} b.win{color:#86efac}
 .legend{font-size:12px;color:var(--mut);margin-top:6px}
</style></head><body>
<header><h1>Recomendação de Coautoria — Dashboard de Avaliação</h1>
<div class="sub">Split temporal T0→T1 · candidatos T0-ativos · IC95% por bootstrap (100 reamostragens, §4.6.3) · PYTHONHASHSEED=0</div></header>
<main>
 <div class="card">
  <div class="ctl">
   <div><label>Regime</label><br><select id="regime"><option value="overall">Geral</option><option value="warm">Warm</option><option value="cool">Cool</option></select></div>
   <div><label>Corte K</label><br><select id="k"></select></div>
   <button class="tg" id="invert">⇄ Inverter (modelo ↔ métrica)</button>
   <span class="pill" id="ncount"></span>
  </div>
  <div id="tablewrap" style="overflow-x:auto"></div>
  <div class="legend">Célula = <b>média</b> <span style="color:var(--mut)">[IC95%]</span> em %. Verde = melhor modelo <i>realista</i> da linha/coluna (exclui o Oráculo, que é teto). Oráculo = limite superior dado o espaço de candidatos topológico.</div>
 </div>
 <div class="card"><h2>Gráficos — métricas × K (barras = IC95%)</h2>
  <div class="grid"><img id="chart" alt="gráfico de métricas"></div>
  <div class="note">O gráfico acompanha o regime selecionado acima.</div>
 </div>
 <div class="card" id="comments"><h2>O que aconteceu & qual foi a melhor opção</h2></div>
</main>
<script>
const P = __PAYLOAD__;
const $ = s => document.querySelector(s);
const kSel = $('#k'); P.ks.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent='@'+k;o.selected=(k===10);kSel.appendChild(o);});
let inverted = false;
function val(model, scope, mk, k){
  const d = scope==='overall'? P.data[model].overall : P.data[model].by_regime[scope];
  const ci = scope==='overall'? P.data[model].overall_ci : P.data[model].by_regime_ci[scope];
  return {mean:d[k][mk]*100, lo:ci[k][mk][0]*100, hi:ci[k][mk][1]*100};
}
function fmt(v){return `${v.mean.toFixed(2)} <span class="ci">[${v.lo.toFixed(1)}–${v.hi.toFixed(1)}]</span>`;}
function bestRealistic(scope, mk, k){ // melhor modelo (exclui oráculo) p/ destacar
  let best=null, bv=-1;
  P.order.forEach(m=>{ if(m==='Ideal Topology (Oracle)')return; const v=val(m,scope,mk,k).mean; if(v>bv){bv=v;best=m;} });
  return best;
}
function render(){
  const scope=$('#regime').value, k=kSel.value;
  const n = scope==='overall'? Object.values(P.counts).reduce((a,b)=>a+b,0) : P.counts[scope];
  $('#ncount').textContent = `regime: ${scope} · n=${n}`;
  $('#chart').src = 'data:image/png;base64,'+P.imgs[scope];
  const best={}; P.metrics.forEach(([mk])=> best[mk]=bestRealistic(scope,mk,k));
  let h='<table><thead><tr>';
  if(!inverted){ // modelos nas COLUNAS, métricas nas LINHAS (padrão)
    h+='<th class="rh">Métrica \\ Modelo</th>'+P.order.map(m=>`<th>${P.labels[m]}</th>`).join('')+'</tr></thead><tbody>';
    P.metrics.forEach(([mk,ml])=>{ h+=`<tr><td class="rh">${ml}@${k}</td>`+P.order.map(m=>{const c=(m===best[mk])?' class="best"':'';return `<td${c}>${fmt(val(m,scope,mk,k))}</td>`;}).join('')+'</tr>'; });
  } else { // métricas nas COLUNAS, modelos nas LINHAS
    h+='<th class="rh">Modelo \\ Métrica</th>'+P.metrics.map(([mk,ml])=>`<th>${ml}@${k}</th>`).join('')+'</tr></thead><tbody>';
    P.order.forEach(m=>{ h+=`<tr><td class="rh">${P.labels[m]}</td>`+P.metrics.map(([mk])=>{const c=(m===best[mk])?' class="best"':'';return `<td${c}>${fmt(val(m,scope,mk,k))}</td>`;}).join('')+'</tr>'; });
  }
  h+='</tbody></table>'; $('#tablewrap').innerHTML=h;
}
$('#regime').onchange=render; kSel.onchange=render;
$('#invert').onclick=()=>{inverted=!inverted;render();};
$('#comments').insertAdjacentHTML('beforeend', __COMMENTS__);
render();
</script></body></html>"""

COMMENTS = """
<p><span class="pill">Contexto</span> Base de IA temática (45.732 autores; rede de coautoria
esparsa). Avaliação como predição de links futuros (T0→T1), restrita aos <b>autores ativos em T0</b>
(warm+cool+cold ≈ 2.003) — os newcomers, sem perfil em T0, são inatendíveis por qualquer modelo.</p>
<ul>
<li><b class="win">MODELO VENCEDOR — 2 etapas (RF→texto):</b> supera o RF de forma significativa em
TODOS os K e regimes (overall R@10 +0,48pp p=1,7e-10; R@200 +3,37pp p=4,5e-66; cool R@10 +0,90pp).
Une a precisão do RF no topo (estágio 1: 2-hop) ao alcance do texto na cauda (estágio 2).</li>
<li><b class="win">Melhor cobertura (Recall@200):</b> <b>Cand. híbridos</b> e <b>Texto (SciBERT)</b>
dominam (~6,8–7,6%) e <b>superam o oráculo topológico</b> — na rede esparsa, candidatos textuais
alcançam coautores fora da vizinhança de 2 saltos, que a topologia (e seu teto) não atinge.</li>
<li><b>Híbrido RF, GNN-rerank e Fusão (CNN+GNN)</b> ficam bem abaixo em recall (~3,6–4,0%): todos
ranqueiam candidatos de 2 saltos, gargalo fatal numa rede esparsa.</li>
<li><b class="win">No topo do ranking (R@10):</b> RF e GNN ainda lideram entre os realistas — a
estrutura ordena melhor as primeiras posições. A complementaridade persiste.</li>
<li><b>Cold-start (autores sem coautoria em T0):</b> os modelos topológicos ZERAM (2-hop vazio);
<b>só o texto recomenda</b> (Texto vs RF +6,2pp, p&lt;0,001). É o argumento central da tese.</li>
<li><b>Contraste com a base médica (densa):</b> lá o RF dominava o geral/topo. O valor do
multimodal <b>cresce com a esparsidade</b> da rede de colaboração.</li>
</ul>
<p><span class="pill">Recomendação</span> Em domínios amplos e pouco conectados (como IA) e no
<b>cold-start</b>, o <b class="win">texto / candidatos híbridos</b> é a melhor opção — alcança
parcerias que a topologia não vê. Em redes densas e no topo do ranking, a topologia (RF) segue
forte. <b>A fusão útil é de fontes de candidatos, não de representações</b> (a Fusão CNN+GNN, presa
a 2 saltos, empata a GNN). Caminho aberto: ranqueador supervisionado sobre o pool de candidatos
híbrido (estrutura ∪ texto).</p>
"""

html = (HTML.replace("__PAYLOAD__", json.dumps(payload))
            .replace("__COMMENTS__", json.dumps(COMMENTS)))
resolve("docs/dashboard.html").write_text(html, encoding="utf-8")
print(f"-> docs/dashboard.html ({len(html)//1024} KB)")
