#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o arquivo final dashboard_eleva.html a partir de dashboard_data.json
(produzido por build_dashboard.py) + a logo da Eleva Brasil.

Rodar depois de build_dashboard.py:
    python3 build_dashboard.py && python3 generate_html.py
"""
import json
import base64
from pathlib import Path

BASE = Path(__file__).parent
DATA_FILE = BASE / "dashboard_data.json"
LOGO_FILE = BASE / "eleva_logo.jpg"
OUT_FILE = BASE / "dashboard_eleva.html"

with open(DATA_FILE, encoding="utf-8") as f:
    D = json.load(f)

with open(LOGO_FILE, "rb") as f:
    LOGO_B64 = base64.b64encode(f.read()).decode()


def brl(v, casas=0):
    s = f"{v:,.{casas}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return "R$ " + s


def brl_m(v):
    s = f"{v/1_000_000:,.2f}"
    return "R$ " + s.replace(",", "§").replace(".", ",").replace("§", ".") + " M"


def pct(v, casas=1):
    s = f"{v:,.{casas}f}"
    return s.replace(".", ",") + "%"


def fmt_int(v):
    return f"{v:,.0f}".replace(",", ".")


def delta_html(var_pct, favor_up=True):
    """Retorna HTML de seta+percentual, verde se favorável, vermelho se desfavorável."""
    if var_pct is None:
        return '<span class="delta neutral">— sem comparação</span>'
    up = var_pct >= 0
    favoravel = up if favor_up else (not up)
    cls = "good" if favoravel else "critical"
    arrow = "▲" if up else "▼"
    return f'<span class="delta {cls}">{arrow} {pct(abs(var_pct))}</span>'


# ---------------------------------------------------------------------------
# CSS (bloco estático, sem f-string para não conflitar com chaves)
# ---------------------------------------------------------------------------
CSS = """
:root{
  --bg-deep:#0a1f3d;
  --bg-deep-2:#0d2a52;
  --card-bg:#ffffff;
  --ink-primary:#0b1220;
  --ink-secondary:#52606d;
  --ink-muted:#8a94a3;
  --hairline:#e6e9ee;
  --good:#0ca30c;
  --good-bg:#e8f7e8;
  --warning:#c98500;
  --warning-bg:#fff6e0;
  --critical:#d03b3b;
  --critical-bg:#fdeaea;
  --neutral:#2a78d6;
  --neutral-bg:#eaf2fc;
  --radius:14px;
  --shadow: 0 1px 2px rgba(10,20,40,0.06), 0 6px 20px rgba(10,20,40,0.10);
}
*{box-sizing:border-box;}
body{
  margin:0; padding:0;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: linear-gradient(180deg, var(--bg-deep) 0%, var(--bg-deep-2) 100%);
  color:#fff;
  min-height:100vh;
}
.wrap{ max-width:1440px; margin:0 auto; padding:22px 28px 60px; }

/* header */
.header{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:6px 4px 20px; flex-wrap:wrap; }
.header-left{ display:flex; align-items:center; gap:16px; }
.logo{ height:52px; width:auto; border-radius:8px; background:#fff; padding:6px 10px; }
.title-block h1{ margin:0; font-size:22px; font-weight:700; letter-spacing:.2px; }
.title-block .sub{ margin-top:2px; font-size:13px; color:#b9c6dc; }
.header-right{ text-align:right; font-size:12.5px; color:#b9c6dc; line-height:1.5; }
.header-right b{ color:#fff; }

/* section title */
.section-title{ display:flex; align-items:baseline; gap:10px; margin:26px 2px 12px; }
.section-title h2{ margin:0; font-size:14.5px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; color:#dce6f5; }
.section-title .hint{ font-size:12px; color:#8fa2c2; }

/* grid */
.grid{ display:grid; gap:14px; }
.grid > *{ min-width:0; }
.grid-5{ grid-template-columns: repeat(5, 1fr); }
.grid-4{ grid-template-columns: repeat(4, 1fr); }
.grid-3{ grid-template-columns: repeat(3, 1fr); }
.grid-2{ grid-template-columns: 1.3fr 1fr; }
@media (max-width:1200px){ .grid-5{grid-template-columns:repeat(3,1fr);} .grid-4{grid-template-columns:repeat(2,1fr);} .grid-3{grid-template-columns:repeat(2,1fr);} .grid-2{grid-template-columns:1fr;} }
@media (max-width:720px){
  .grid-5,.grid-4,.grid-3{grid-template-columns:1fr;}
  .wrap{ padding:16px 14px 40px; }
  .occ-row{
    grid-template-columns: 1fr 50px;
    grid-template-areas: "name pct" "total total" "stack stack";
    row-gap:6px;
  }
  .occ-name{ grid-area:name; }
  .occ-pct{ grid-area:pct; }
  .occ-total{ grid-area:total; text-align:left; }
  .occ-stack{ grid-area:stack; }
}

/* cards */
.card{ background:var(--card-bg); color:var(--ink-primary); border-radius:var(--radius); box-shadow:var(--shadow); padding:16px 18px; }
.card h3{ margin:0 0 10px; font-size:12.5px; font-weight:700; text-transform:uppercase; letter-spacing:.4px; color:var(--ink-secondary); }
.kpi-value{ font-size:34px; font-weight:800; line-height:1; letter-spacing:-.5px; }
.kpi-unit{ font-size:13px; font-weight:600; color:var(--ink-muted); margin-left:6px; }
.kpi-sub{ margin-top:8px; font-size:12.5px; color:var(--ink-secondary); }
.kpi-row{ display:flex; align-items:baseline; gap:6px; flex-wrap:wrap; }
.delta{ font-weight:700; font-size:13px; }
.delta.good{ color:var(--good); }
.delta.critical{ color:var(--critical); }
.delta.neutral{ color:var(--ink-muted); font-weight:600; }
.tag{ display:inline-block; font-size:11px; font-weight:700; padding:2px 8px; border-radius:20px; margin-left:6px; }
.tag.good{ background:var(--good-bg); color:var(--good); }
.tag.warning{ background:var(--warning-bg); color:var(--warning); }
.tag.critical{ background:var(--critical-bg); color:var(--critical); }
.tag.neutral{ background:var(--neutral-bg); color:var(--neutral); }
.card-mini-note{ margin-top:10px; padding-top:10px; border-top:1px solid var(--hairline); font-size:11.5px; color:var(--ink-muted); }

/* frota mix card */
.mix-bar{ display:flex; height:14px; border-radius:8px; overflow:hidden; margin:10px 0 8px; }
.mix-seg-disp{ background:var(--neutral); }
.mix-seg-contr{ background:var(--good); }
.mix-seg-manut{ background:var(--critical); }
.mix-legend{ display:flex; gap:14px; font-size:12px; color:var(--ink-secondary); flex-wrap:wrap; }
.mix-legend span{ display:inline-flex; align-items:center; gap:5px; }
.dot{ width:9px; height:9px; border-radius:50%; display:inline-block; }
.dot.disp{background:var(--neutral);} .dot.contr{background:var(--good);} .dot.manut{background:var(--critical);}

/* tables */
.table-card{ background:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow); padding:16px 18px 8px; color:var(--ink-primary); }
.table-card h3{ margin:0 0 4px; font-size:13.5px; font-weight:700; color:var(--ink-primary); }
.table-card .hint{ font-size:11.5px; color:var(--ink-muted); margin-bottom:10px; display:block; }
.tbl-scroll{ max-height:430px; overflow-y:auto; overflow-x:auto; -webkit-overflow-scrolling:touch; border-top:1px solid var(--hairline); }
table{ width:100%; min-width:640px; border-collapse:collapse; font-size:12.5px; }
@media (max-width:720px){
  .tbl-scroll{ max-height:60vh; }
  table{ min-width:600px; }
}
thead th{ position:sticky; top:0; background:#fafbfd; text-align:right; padding:8px 8px; font-weight:700; color:var(--ink-secondary); border-bottom:1px solid var(--hairline); white-space:nowrap; }
thead th:first-child, thead th:nth-child(2){ text-align:left; }
tbody td{ padding:6px 8px; text-align:right; border-bottom:1px solid #f1f3f6; white-space:nowrap; }
tbody td:first-child, tbody td:nth-child(2){ text-align:left; }
tbody tr:hover{ background:#f7f9fc; }
.num-crit{ color:var(--critical); font-weight:700; }
.num-good{ color:var(--good); font-weight:700; }
.num-neutral{ color:var(--neutral); font-weight:700; }
.bar-cell{ display:inline-block; height:6px; border-radius:4px; vertical-align:middle; margin-right:6px; }

/* occupancy stacked rows */
.occ-row{ display:grid; grid-template-columns: 200px 60px 1fr 70px; align-items:center; gap:10px; padding:9px 0; border-bottom:1px solid var(--hairline); font-size:12.5px; }
.occ-row:last-child{ border-bottom:none; }
.occ-name{ font-weight:700; color:var(--ink-primary); }
.occ-total{ color:var(--ink-muted); text-align:right; }
.occ-stack{ display:flex; height:16px; border-radius:6px; overflow:hidden; background:#f1f3f6; }
.occ-pct{ text-align:right; font-weight:700; color:var(--ink-primary); }

/* chart */
.chart-wrap{ position:relative; }
.tooltip{ position:absolute; pointer-events:none; background:#0b1220; color:#fff; font-size:12px; padding:6px 9px; border-radius:8px; box-shadow:0 4px 14px rgba(0,0,0,.25); opacity:0; transform:translate(-50%,-110%); transition:opacity .08s; white-space:nowrap; z-index:5; }
.axis-label{ font-size:10.5px; fill:var(--ink-muted); }

/* alerts */
.alert-list{ display:flex; flex-direction:column; gap:10px; }
.alert-item{ display:flex; gap:10px; padding:11px 14px; border-radius:10px; font-size:13px; line-height:1.45; }
.alert-item.critical{ background:var(--critical-bg); color:#7a1f1f; }
.alert-item.warning{ background:var(--warning-bg); color:#6b4a00; }
.alert-item.good{ background:var(--good-bg); color:#0d5c0d; }
.alert-icon{ font-size:15px; }

/* quality */
.quality-list{ display:flex; flex-direction:column; gap:10px; }
.quality-item{ padding:10px 14px; border-radius:10px; background:#f7f9fc; border:1px solid var(--hairline); font-size:12.5px; color:var(--ink-secondary); line-height:1.5; }
.quality-item b{ color:var(--ink-primary); }

/* footer */
.footer{ margin-top:34px; padding-top:16px; border-top:1px solid rgba(255,255,255,.12); font-size:11.5px; color:#93a3bf; text-align:center; }

/* impressão / PDF */
@media print{
  body{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .wrap{ max-width:none; padding:10px 16px 30px; }
  .card, .table-card{ break-inside: avoid; }
  .tbl-scroll{ max-height:none; overflow:visible; }
  thead th{ position:static; }
}
"""

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
header_html = f"""
<div class="header">
  <div class="header-left">
    <img class="logo" src="data:image/jpeg;base64,{LOGO_B64}" alt="Eleva Brasil" />
    <div class="title-block">
      <h1>Dashboard Gerencial de Operações</h1>
      <div class="sub">Visão Executiva &middot; Eleva Brasil</div>
    </div>
  </div>
  <div class="header-right">
    Atualizado em <b>{D['gerado_em']}</b><br/>
    Fonte: Faturamento, Status de Máquinas e Taxa de Ocupação
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Linha 1 - KPIs de frota
# ---------------------------------------------------------------------------
frota = D["frota"]
kpi_frota = f"""
<div class="grid grid-5">
  <div class="card">
    <h3>Total de Máquinas</h3>
    <div class="kpi-value">{fmt_int(frota['total'])}</div>
    <div class="mix-bar">
      <div class="mix-seg-disp" style="width:{frota['disponivel_pct']:.2f}%"></div>
      <div class="mix-seg-contr" style="width:{frota['contrato_pct']:.2f}%"></div>
      <div class="mix-seg-manut" style="width:{frota['manutencao_pct']:.2f}%"></div>
    </div>
    <div class="mix-legend">
      <span><i class="dot disp"></i>Disp. {fmt_int(frota['disponivel'])}</span>
      <span><i class="dot contr"></i>Contrato {fmt_int(frota['contrato'])}</span>
      <span><i class="dot manut"></i>Manut. {fmt_int(frota['manutencao'])}</span>
    </div>
  </div>
  <div class="card">
    <h3>Máquinas Disponíveis</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--neutral)">{fmt_int(frota['disponivel'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub">{pct(frota['disponivel_pct'])} da frota &middot; <span class="delta neutral">sem histórico p/ comparação</span></div>
  </div>
  <div class="card">
    <h3>Máquinas em Contrato</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--good)">{fmt_int(frota['contrato'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub">{pct(frota['contrato_pct'])} da frota &middot; <span class="delta neutral">sem histórico p/ comparação</span></div>
  </div>
  <div class="card">
    <h3>Máquinas em Manutenção</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--critical)">{fmt_int(frota['manutencao'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub">{pct(frota['manutencao_pct'])} da frota <span class="tag critical">crítico</span></div>
  </div>
  <div class="card">
    <h3>Taxa de Ocupação Geral</h3>
    <div class="kpi-row"><span class="kpi-value">{pct(frota['ocupacao_pct'])}</span></div>
    <div class="kpi-sub">Em Contrato &divide; Total de Máquinas</div>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Linha 2 - Faturamento
# ---------------------------------------------------------------------------
fat = D["faturamento"]
kpi_fat = f"""
<div class="grid grid-4">
  <div class="card">
    <h3>Faturamento do Ano (YTD, líquido)</h3>
    <div class="kpi-value">{brl_m(fat['ytd_liquido'])}</div>
    <div class="kpi-sub">{delta_html(fat['ytd_var_pct'], favor_up=True)} vs. mesmo período de {int(fat['corte_label'][-4:])-1} ({brl_m(fat['ytd_liquido_ant'])})</div>
  </div>
  <div class="card">
    <h3>Faturamento do Mês (MTD, líquido)</h3>
    <div class="kpi-value">{brl_m(fat['mtd_liquido'])}</div>
    <div class="kpi-sub">{delta_html(fat['mtd_var_pct'], favor_up=True)} vs. mesmo período de {int(fat['corte_label'][-4:])-1} ({brl_m(fat['mtd_liquido_ant'])})</div>
  </div>
  <div class="card">
    <h3>Último Mês Fechado ({fat['mes_fechado_label']})</h3>
    <div class="kpi-value">{brl_m(fat['mes_fechado_liquido'])}</div>
    <div class="kpi-sub">{delta_html(fat['mes_fechado_var_pct'], favor_up=True)} vs. mesmo mês do ano anterior ({brl_m(fat['mes_fechado_liquido_ant'])})</div>
  </div>
  <div class="card">
    <h3>Bruto &rarr; Líquido (Ano)</h3>
    <div class="kpi-value" style="font-size:22px">{brl_m(fat['ytd_bruto'])} <span style="color:var(--ink-muted);font-size:15px">bruto</span></div>
    <div class="kpi-sub">Deduções (desconto + IRF): {brl_m(fat['ytd_deducoes'])} &rarr; Líquido: <b>{brl_m(fat['ytd_liquido'])}</b></div>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Linha 3 - Potencial de Faturamento (capital parado)
# ---------------------------------------------------------------------------
pot = D["potencial"]
kpi_pot = f"""
<div class="grid grid-3">
  <div class="card">
    <h3>Receita Ativa (Em Contrato)</h3>
    <div class="kpi-value" style="color:var(--good)">{brl_m(pot['receita_ativa'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_ativa'])} do potencial mensal da frota</div>
  </div>
  <div class="card">
    <h3>Potencial Parado (Disponível)</h3>
    <div class="kpi-value" style="color:var(--neutral)">{brl_m(pot['receita_parada'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_parada'])} do potencial mensal &middot; <span class="tag warning">capital parado</span></div>
  </div>
  <div class="card">
    <h3>Receita Perdida (Em Manutenção)</h3>
    <div class="kpi-value" style="color:var(--critical)">{brl_m(pot['receita_perdida_manut'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_perdida_manut'])} do potencial mensal <span class="tag critical">maior gargalo</span></div>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Gráfico - Evolução do Faturamento Mensal (SVG + tooltip)
# ---------------------------------------------------------------------------
serie = D["serie_mensal"]
vals = [p["valor"] for p in serie]
vmax = max(vals) if vals else 1
n = len(serie)
chart_w, chart_h = 980, 220
pad_l, pad_r, pad_t, pad_b = 10, 10, 10, 26
plot_w = chart_w - pad_l - pad_r
plot_h = chart_h - pad_t - pad_b
bar_gap = 4
bar_w = (plot_w / n) - bar_gap if n else 10

MESES_PT = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun", 7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

bars_svg = []
labels_svg = []
for i, p in enumerate(serie):
    ano_s, mes_s = p["mes"].split("-")
    label = f"{MESES_PT[int(mes_s)]}/{ano_s[2:]}"
    h = (p["valor"] / vmax) * plot_h if vmax else 0
    x = pad_l + i * (bar_w + bar_gap)
    y = pad_t + (plot_h - h)
    is_last = (i == n - 1)
    color = "var(--neutral)" if not is_last else "var(--good)"
    bars_svg.append(
        f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h,2):.1f}" rx="3" '
        f'fill="{color}" data-label="{label}{" (parcial)" if is_last else ""}" data-value="{brl_m(p["valor"])}"></rect>'
    )
    if i % 2 == 0 or is_last:
        labels_svg.append(f'<text class="axis-label" x="{x+bar_w/2:.1f}" y="{chart_h-6}" text-anchor="middle">{label}</text>')

chart_svg = f"""
<div class="chart-wrap">
  <svg viewBox="0 0 {chart_w} {chart_h}" width="100%" height="{chart_h}" id="revChart">
    {''.join(bars_svg)}
    {''.join(labels_svg)}
  </svg>
  <div class="tooltip" id="chartTooltip"></div>
</div>
"""

chart_card = f"""
<div class="table-card">
  <h3>Evolução do Faturamento Líquido Mensal</h3>
  <span class="hint">Últimos {n} meses com dado &middot; o mês mais recente é parcial (até {fat['corte_label']}) &middot; um lote de abertura/migração contábil de 31/05/2024 foi excluído deste gráfico para não distorcer a tendência</span>
  {chart_svg}
</div>
"""

# ---------------------------------------------------------------------------
# Gráfico - Comparativo Anual (Ano Atual x Ano Anterior, mês a mês)
# ---------------------------------------------------------------------------
comp = D["comparativo_anual"]
comp_meses = comp["meses"]
comp_vals = [m["atual"] for m in comp_meses if m["atual"] is not None] + [m["anterior"] for m in comp_meses if m["anterior"] is not None]
comp_vmax = max(comp_vals) if comp_vals else 1

yoy_w, yoy_h = 980, 220
yoy_pad_l, yoy_pad_r, yoy_pad_t, yoy_pad_b = 10, 10, 10, 26
yoy_plot_w = yoy_w - yoy_pad_l - yoy_pad_r
yoy_plot_h = yoy_h - yoy_pad_t - yoy_pad_b
n_months = 12
group_w = yoy_plot_w / n_months
bar_gap_inner = 3
group_pad = 8
yoy_bar_w = (group_w - group_pad - bar_gap_inner) / 2

yoy_bars = []
yoy_labels = []
mes_atual_num = comp_meses_idx = None
for i, m in enumerate(comp_meses):
    gx = yoy_pad_l + i * group_w
    is_current_month = m["atual"] is not None and (i + 1 == max(mm["mes"] for mm in comp_meses if mm["atual"] is not None))
    # barra ano anterior (sempre, quando existir)
    if m["anterior"] is not None:
        h_ant = (m["anterior"] / comp_vmax) * yoy_plot_h
        x_ant = gx + group_pad / 2
        y_ant = yoy_pad_t + (yoy_plot_h - h_ant)
        yoy_bars.append(
            f'<rect class="bar" x="{x_ant:.1f}" y="{y_ant:.1f}" width="{yoy_bar_w:.1f}" height="{max(h_ant,2):.1f}" rx="3" '
            f'fill="var(--ink-muted)" data-label="{m["mes_label"]}/{str(comp["ano_anterior"])[2:]}" data-value="{brl_m(m["anterior"])}"></rect>'
        )
    # barra ano atual (só até o mês corrente)
    if m["atual"] is not None:
        h_atu = (m["atual"] / comp_vmax) * yoy_plot_h
        x_atu = gx + group_pad / 2 + yoy_bar_w + bar_gap_inner
        y_atu = yoy_pad_t + (yoy_plot_h - h_atu)
        color = "var(--good)" if not is_current_month else "var(--neutral)"
        label_suffix = " (parcial)" if is_current_month else ""
        yoy_bars.append(
            f'<rect class="bar" x="{x_atu:.1f}" y="{y_atu:.1f}" width="{yoy_bar_w:.1f}" height="{max(h_atu,2):.1f}" rx="3" '
            f'fill="{color}" data-label="{m["mes_label"]}/{str(comp["ano_atual"])[2:]}{label_suffix}" data-value="{brl_m(m["atual"])}"></rect>'
        )
    yoy_labels.append(f'<text class="axis-label" x="{gx+group_w/2:.1f}" y="{yoy_h-6}" text-anchor="middle">{m["mes_label"]}</text>')

yoy_svg = f"""
<div class="chart-wrap">
  <svg viewBox="0 0 {yoy_w} {yoy_h}" width="100%" height="{yoy_h}" id="yoyChart">
    {''.join(yoy_bars)}
    {''.join(yoy_labels)}
  </svg>
  <div class="tooltip" id="yoyTooltip"></div>
</div>
"""

proj_delta = delta_html(comp["projecao_vs_ano_anterior_pct"], favor_up=True) if comp["projecao_vs_ano_anterior_pct"] is not None else '<span class="delta neutral">—</span>'

yoy_card = f"""
<div class="table-card">
  <h3>Comparativo Anual — {comp['ano_atual']} x {comp['ano_anterior']}</h3>
  <span class="hint">Faturamento líquido mês a mês &middot; <i class="dot" style="background:var(--ink-muted)"></i>{comp['ano_anterior']} &middot; <i class="dot contr"></i>{comp['ano_atual']} (mês corrente parcial em <i class="dot disp"></i>) &middot; meses futuros de {comp['ano_atual']} ainda não existem, não são zero</span>
  {yoy_svg}
  <div class="mix-legend" style="margin:4px 0 14px; gap:22px;">
    <span><b>Total {comp['ano_anterior']} (ano completo):</b>&nbsp;{brl_m(comp['total_ano_anterior_completo']) if comp['total_ano_anterior_completo'] else '—'}</span>
    <span><b>Projeção de fechamento {comp['ano_atual']}:</b>&nbsp;{brl_m(comp['projecao_fechamento_ano'])} {proj_delta}</span>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Tabela - Taxa de Ocupação por Tipo do Modelo (linhas com stacked bar)
# ---------------------------------------------------------------------------
tipos = D["tipos_tabela"]
occ_rows = []
for t in tipos:
    occ_rows.append(f"""
    <div class="occ-row">
      <div class="occ-name">{t['tipo']}</div>
      <div class="occ-total">{fmt_int(t['total'])} un.</div>
      <div class="occ-stack" title="Disponível {t['disp_pct']}% · Em Contrato {t['contrato_pct']}% · Manutenção {t['manut_pct']}%">
        <div style="width:{t['disp_pct']}%; background:var(--neutral)"></div>
        <div style="width:{t['contrato_pct']}%; background:var(--good)"></div>
        <div style="width:{t['manut_pct']}%; background:var(--critical)"></div>
      </div>
      <div class="occ-pct">{pct(t['contrato_pct'])}</div>
    </div>""")

occ_table_card = f"""
<div class="table-card">
  <h3>Taxa de Ocupação por Tipo do Modelo</h3>
  <span class="hint">Ordenado por quantidade de equipamentos &middot; barra: <i class="dot disp"></i>Disponível <i class="dot contr"></i>Em Contrato <i class="dot manut"></i>Manutenção &middot; % à direita = ocupação</span>
  {''.join(occ_rows)}
</div>
"""

# ---------------------------------------------------------------------------
# Tabela - Disponibilidade por Modelo (scroll)
# ---------------------------------------------------------------------------
modelos = D["modelos_tabela"]
rows = []
for m in modelos:
    manut_cls = "num-crit" if m["manutencao_pct"] >= 60 else ("" if m["manutencao_pct"] < 40 else "num-crit")
    disp_cls = "num-neutral" if m["disponivel"] >= 5 else ""
    flag = ""
    if m["manutencao_pct"] >= 70 and m["total"] >= 5:
        flag = '<span class="tag critical">manutenção crítica</span>'
    elif m["disponivel"] >= 5:
        flag = '<span class="tag neutral">capital parado</span>'
    elif m["ocupacao_pct"] >= 80:
        flag = '<span class="tag good">alta demanda</span>'
    rows.append(f"""<tr>
      <td>{m['modelo']}</td>
      <td>{m['tipo'].title()}</td>
      <td class="{disp_cls}">{fmt_int(m['disponivel'])}</td>
      <td>{fmt_int(m['contrato'])}</td>
      <td class="{manut_cls}">{fmt_int(m['manutencao'])}</td>
      <td>{fmt_int(m['total'])}</td>
      <td>{pct(m['ocupacao_pct'])}</td>
      <td>{flag}</td>
    </tr>""")

modelos_table_card = f"""
<div class="table-card">
  <h3>Disponibilidade por Modelo</h3>
  <span class="hint">{len(modelos)} modelos &middot; ordenado por total de equipamentos &middot; role para ver todos</span>
  <div class="tbl-scroll">
    <table>
      <thead><tr>
        <th>Modelo</th><th>Tipo</th><th>Disponível</th><th>Contrato</th><th>Manutenção</th><th>Total</th><th>Ocupação %</th><th>Observação</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Tabela - Equipamentos Disponíveis para Locação (unidade a unidade)
# ---------------------------------------------------------------------------
equip_disp = D["equipamentos_disponiveis"]
equip_rows = []
for e in equip_disp:
    equip_rows.append(f"""<tr>
      <td>{e['patrimonio']}</td>
      <td>{e['modelo']}</td>
      <td>{e['tipo'].title()}</td>
      <td>{e['serie']}</td>
      <td>{e['serie_fabricante']}</td>
    </tr>""")

equip_disp_card = f"""
<div class="table-card">
  <h3>Equipamentos Disponíveis para Locação</h3>
  <span class="hint">{len(equip_disp)} unidades com Status = Disponível agora &middot; patrimônio individual &middot; role para ver todas &middot; a planilha de origem não traz data nem localização, então "dias parado" e "localização" não aparecem aqui</span>
  <div class="tbl-scroll">
    <table>
      <thead><tr>
        <th>Patrimônio</th><th>Modelo</th><th>Tipo</th><th>Nº de Série</th><th>Nº Série Fabricante</th>
      </tr></thead>
      <tbody>{''.join(equip_rows)}</tbody>
    </table>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
icon_map = {"critical": "🔴", "warning": "🟡", "good": "🟢"}
alert_items = []
for a in D["alertas"]:
    alert_items.append(f'<div class="alert-item {a["nivel"]}"><span class="alert-icon">{icon_map[a["nivel"]]}</span><div>{a["texto"]}</div></div>')

alerts_card = f"""
<div class="table-card">
  <h3>Alertas / Pontos de Atenção</h3>
  <span class="hint">Gerados a partir dos dados das planilhas &mdash; nenhum valor estimado</span>
  <div class="alert-list" style="margin:10px 0 14px">{''.join(alert_items)}</div>
</div>
"""

# ---------------------------------------------------------------------------
# Qualidade dos Dados
# ---------------------------------------------------------------------------
quality_items = []
for q in D["quality_notes"]:
    quality_items.append(f'<div class="quality-item">{q["icon"]} <b>{q["title"]}</b><br/>{q["detail"]}</div>')

quality_card = f"""
<div class="table-card">
  <h3>Qualidade dos Dados</h3>
  <span class="hint">Verificações automáticas feitas antes de calcular os indicadores acima</span>
  <div class="quality-list" style="margin:10px 0 14px">{''.join(quality_items)}</div>
</div>
"""

# ---------------------------------------------------------------------------
# Página final
# ---------------------------------------------------------------------------
JS = """
<script>
(function(){
  function wireChart(svgId, tipId){
    var svg = document.getElementById(svgId);
    var tip = document.getElementById(tipId);
    if(!svg || !tip) return;
    var bars = svg.querySelectorAll('.bar');
    bars.forEach(function(bar){
      bar.addEventListener('mousemove', function(e){
        var rect = svg.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
        tip.style.opacity = 1;
        tip.innerHTML = '<b>' + bar.getAttribute('data-label') + '</b><br/>' + bar.getAttribute('data-value');
        bar.style.opacity = 0.75;
      });
      bar.addEventListener('mouseleave', function(){ tip.style.opacity = 0; bar.style.opacity = 1; });
    });
  }
  wireChart('revChart', 'chartTooltip');
  wireChart('yoyChart', 'yoyTooltip');
})();
</script>
"""

html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<title>Dashboard Gerencial - Eleva Brasil</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  {header_html}

  {quality_card}

  <div class="section-title"><h2>Frota</h2><span class="hint">Situação atual dos equipamentos</span></div>
  {kpi_frota}

  <div class="section-title"><h2>Faturamento</h2><span class="hint">Valores líquidos, salvo indicação em contrário</span></div>
  {kpi_fat}

  <div class="section-title"><h2>Potencial de Faturamento</h2><span class="hint">Onde está o dinheiro da frota, por status</span></div>
  {kpi_pot}

  <div class="grid grid-2" style="margin-top:14px; align-items:start;">
    {chart_card}
    {occ_table_card}
  </div>

  <div class="section-title"><h2>Comparativo Anual</h2><span class="hint">Momento atual x mesmo momento do ano passado</span></div>
  <div style="margin-top:4px;">
    {yoy_card}
  </div>

  <div class="grid grid-2" style="margin-top:14px; align-items:start;">
    {modelos_table_card}
    {equip_disp_card}
  </div>

  <div class="footer">
    Dashboard Gerencial de Operações &middot; Eleva Brasil &middot; gerado automaticamente a partir da API da LOC1 (Faturamento, Status de Máquinas e Taxa de Ocupação) &middot; corte de dados: {fat['corte_label']}
  </div>
</div>
{JS}
</body>
</html>
"""

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("dashboard_eleva.html gerado em:", OUT_FILE)
