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
LOGO_FILE = BASE / "eleva_logo.png"
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
    """Abaixo de R$ 1 milhao mostra em K (milhares); a partir de R$ 1 milhao, em M."""
    if abs(v) < 1_000_000:
        s = f"{v/1_000:,.1f}"
        return "R$ " + s.replace(",", "§").replace(".", ",").replace("§", ".") + " K"
    s = f"{v/1_000_000:,.2f}"
    return "R$ " + s.replace(",", "§").replace(".", ",").replace("§", ".") + " M"


def brl_m1(v):
    """Versao compacta (1 casa decimal), tudo junto, pra rotulo em cima de barra: R$5,3M
    ou R$24,8K abaixo de R$ 1 milhao."""
    if abs(v) < 1_000_000:
        s = f"{v/1_000:,.1f}"
        return "R$" + s.replace(",", "§").replace(".", ",").replace("§", ".") + "K"
    s = f"{v/1_000_000:,.1f}"
    return "R$" + s.replace(",", "§").replace(".", ",").replace("§", ".") + "M"


def pct(v, casas=1):
    s = f"{v:,.{casas}f}"
    return s.replace(".", ",") + "%"


def fmt_int(v):
    return f"{v:,.0f}".replace(",", ".")


ROTULO_OPCAO = {"Disponivel": "Disponível"}  # valor interno (LOC1) -> texto exibido
STATUS_ROTULO = {"Disponivel": ("Disponível", "st-disp"), "Em Contrato": ("Em Contrato", "st-contr"), "Em Manutenção": ("Em Manutenção", "st-manut")}


def ordem_alfabetica(valores):
    """Ordena opções de filtro alfabeticamente ignorando acento e maiúsculas."""
    import unicodedata
    chave = lambda v: unicodedata.normalize("NFKD", ROTULO_OPCAO.get(v, v)).encode("ascii", "ignore").decode().casefold()
    return sorted(set(valores), key=chave)


def multiselect_html(elem_id, label, options):
    """Filtro de seleção múltipla (botão + painel com checkboxes e busca).
    O JS (wireMultiSelect, no bloco <script> final) liga o comportamento -
    aqui só o HTML/estado inicial (nada selecionado = "todos")."""
    options = ordem_alfabetica(options)
    opts_html = "".join(f'<label class="ms-option"><input type="checkbox" value="{o}"/><span>{ROTULO_OPCAO.get(o, o)}</span></label>' for o in options)
    if not options:
        opts_html = '<div class="ms-empty">Nenhuma opção disponível.</div>'
    return f"""<div class="ms-wrap" id="{elem_id}">
      <button type="button" class="ms-btn" data-label="{label}">{label} (todos)</button>
      <div class="ms-panel">
        <input type="text" class="ms-search" placeholder="Buscar {label.lower()}..." />
        <div class="ms-actions"><a data-act="all">Marcar todos</a><a data-act="none">Limpar</a></div>
        <div class="ms-options">{opts_html}</div>
      </div>
    </div>"""


def delta_html(var_pct, favor_up=True):
    """Retorna HTML de seta+percentual, verde se favorável, vermelho se desfavorável."""
    if var_pct is None:
        return '<span class="delta neutral">— sem comparação</span>'
    up = var_pct >= 0
    favoravel = up if favor_up else (not up)
    cls = "good" if favoravel else "critical"
    arrow = "▲" if up else "▼"
    return f'<span class="delta {cls}">{arrow} {pct(abs(var_pct))}</span>'


def hbar_svg(rows, value_fmt, color="var(--neutral)", label_w=210, chart_w=560, row_h=27):
    """Gráfico de barras horizontais simples: rows = [(label, value), ...], já
    ordenado do maior pro menor. Cada barra mostra o rótulo à esquerda e o
    valor formatado logo depois do fim da barra (sem tooltip - valor sempre visível)."""
    vmax = max((v for _, v in rows), default=1) or 1
    bar_area = chart_w - label_w - 70
    h = len(rows) * row_h + 6
    parts = []
    for i, (label, value) in enumerate(rows):
        y = 6 + i * row_h
        bar_w = max((value / vmax) * bar_area, 2) if vmax else 2
        parts.append(
            f'<text x="{label_w - 10}" y="{y + 15}" text-anchor="end" font-size="11.5" fill="var(--ink-secondary)">{label}</text>'
            f'<rect x="{label_w}" y="{y + 4}" width="{bar_w:.1f}" height="16" rx="4" fill="{color}"></rect>'
            f'<text x="{label_w + bar_w + 8:.1f}" y="{y + 15}" font-size="11" font-weight="700" fill="var(--ink-primary)">{value_fmt(value)}</text>'
        )
    return f'<svg viewBox="0 0 {chart_w} {h}" width="100%" height="{h}">{"".join(parts)}</svg>'


def vbar_svg(rows, value_fmt, color="var(--neutral)", w=980, h=190):
    """Histograma de barras verticais: rows = [(label, value), ...]."""
    pad_l, pad_r, pad_t, pad_b = 10, 10, 20, 26
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    n = max(len(rows), 1)
    group_w = plot_w / n
    bar_w = group_w * 0.5
    vmax = max((v for _, v in rows), default=1) or 1
    parts = []
    for i, (label, value) in enumerate(rows):
        bx = pad_l + i * group_w + (group_w - bar_w) / 2
        bh = (value / vmax) * plot_h if vmax else 0
        by = pad_t + (plot_h - bh)
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{max(bh, 2):.1f}" rx="3" fill="{color}"></rect>'
            f'<text class="bar-value" x="{bx + bar_w / 2:.1f}" y="{max(by - 6, 10):.1f}" text-anchor="middle">{value_fmt(value)}</text>'
            f'<text class="axis-label" x="{bx + bar_w / 2:.1f}" y="{h - 6}" text-anchor="middle">{label}</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{"".join(parts)}</svg>'


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
  --status-disp:#0ca30c;
  --status-contr:#2a78d6;
  --status-contr-text:#2a78d6;
  --status-manut:#d03b3b;
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

/* app shell / sidebar de navegação */
.app-shell{ display:flex; align-items:flex-stretch; min-height:100vh; }
.sidebar{ width:216px; flex-shrink:0; padding:22px 14px; display:flex; flex-direction:column; gap:6px; background:rgba(0,0,0,.14); border-right:1px solid rgba(255,255,255,.08); }
.sidebar-top{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin:2px 2px 18px; }
.sidebar-logo{ height:40px; width:auto; border-radius:8px; background:#fff; padding:8px 12px; }
.sidebar-toggle{ background:rgba(255,255,255,.08); border:none; color:#b9c6dc; width:26px; height:26px; flex-shrink:0; border-radius:7px; cursor:pointer; font-size:14px; line-height:1; display:flex; align-items:center; justify-content:center; transition:background .12s, color .12s; }
.sidebar-toggle:hover{ background:rgba(255,255,255,.18); color:#fff; }
.sidebar-toggle-open{ position:fixed; top:20px; left:16px; z-index:30; display:none; }
.app-shell.sidebar-collapsed .sidebar{ display:none; }
.app-shell.sidebar-collapsed .sidebar-toggle-open{ display:flex; }
.tab-btn{ display:block; width:100%; text-align:left; background:transparent; border:none; color:#b9c6dc; padding:11px 14px; border-radius:9px; cursor:pointer; font-size:13px; font-weight:600; font-family:inherit; transition:background .12s, color .12s; }
.tab-btn:hover{ background:rgba(255,255,255,.06); color:#fff; }
.tab-btn.active{ background:rgba(255,255,255,.12); color:#fff; }
.app-main{ flex:1; min-width:0; }
.tab-page{ display:none; }
.tab-page.active{ display:block; }
@media (max-width:900px){
  .app-shell{ flex-direction:column; }
  .sidebar{ width:100%; flex-direction:row; align-items:center; gap:4px; padding:10px 12px; overflow-x:auto; border-right:none; border-bottom:1px solid rgba(255,255,255,.08); }
  .sidebar-top{ margin:0 10px 0 0; }
  .sidebar-logo{ height:32px; padding:6px 9px; }
  .sidebar-toggle, .sidebar-toggle-open{ display:none !important; }
  .tab-btn{ width:auto; white-space:nowrap; padding:9px 13px; }
}

/* header */
.header{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:6px 4px 20px; flex-wrap:wrap; }
.header-left{ display:flex; align-items:center; gap:16px; }
.logo{ height:72px; width:auto; border-radius:10px; background:#fff; padding:12px 18px; }
@media (max-width:720px){ .logo{ height:52px; padding:10px 14px; } }
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
.grid-5 .kpi-value{ font-size:26px; white-space:nowrap; }
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
.mix-seg-disp{ background:var(--status-disp); }
.mix-seg-contr{ background:var(--status-contr); }
.mix-seg-manut{ background:var(--status-manut); }
.mix-legend{ display:flex; gap:14px; font-size:12px; color:var(--ink-secondary); flex-wrap:wrap; }
.mix-legend span{ display:inline-flex; align-items:center; gap:5px; }
.dot{ width:9px; height:9px; border-radius:50%; display:inline-block; }
.dot.disp{background:var(--status-disp);} .dot.contr{background:var(--status-contr);} .dot.manut{background:var(--status-manut);}

/* tables */
.table-card{ background:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow); padding:16px 18px 8px; color:var(--ink-primary); }
.table-card h3{ margin:0 0 4px; font-size:13.5px; font-weight:700; color:var(--ink-primary); }
.table-card .hint{ font-size:11.5px; color:var(--ink-muted); margin-bottom:10px; display:block; }
.filter-row{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:2px 0 12px; }
.filter-select{ height:34px; box-sizing:border-box; font-size:12.5px; padding:0 12px; border-radius:8px; border:1px solid #dfe3ea; background:#fff; color:var(--ink-primary); font-family:inherit; cursor:pointer; transition:border-color .12s; }
.filter-select:hover{ border-color:#c3cad6; }
.filter-search{ width:190px; cursor:text; padding-left:32px; background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%238a94a3' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M20 20l-3.5-3.5'/%3E%3C/svg%3E") no-repeat 11px center; }
.filter-row .hint{ margin:0 0 0 auto; display:inline; font-size:12px; }
.filter-select:focus{ outline:2px solid var(--neutral); outline-offset:1px; }
.filter-clear{ height:34px; box-sizing:border-box; font-size:12.5px; padding:0 14px; border-radius:8px; border:1px solid transparent; background:transparent; color:var(--neutral); font-weight:600; font-family:inherit; cursor:pointer; }
.filter-clear:hover{ background:var(--neutral-bg); }
tr.filtro-oculto{ display:none; }

/* filtro de seleção múltipla (checkbox dropdown) */
.ms-wrap{ position:relative; }
.ms-btn{ height:34px; box-sizing:border-box; font-size:12.5px; padding:0 32px 0 12px; border-radius:8px; border:1px solid #dfe3ea; background:#fff; color:var(--ink-primary); font-family:inherit; cursor:pointer; white-space:nowrap; position:relative; transition:border-color .12s, background .12s; }
.ms-btn:after{ content:''; position:absolute; right:13px; top:50%; width:6px; height:6px; border-right:1.6px solid var(--ink-muted); border-bottom:1.6px solid var(--ink-muted); transform:translateY(-70%) rotate(45deg); }
.ms-btn:hover{ border-color:#c3cad6; }
.ms-btn.active{ border-color:var(--neutral); color:var(--neutral); background:var(--neutral-bg); font-weight:600; }
.ms-btn.active:after{ border-color:var(--neutral); }
.ms-panel{ display:none; position:absolute; top:calc(100% + 5px); left:0; z-index:30; background:#fff; border:1px solid var(--hairline); border-radius:10px; box-shadow:var(--shadow); padding:8px; width:240px; }
.ms-panel.open{ display:block; }
.ms-search{ width:100%; box-sizing:border-box; padding:6px 8px; margin-bottom:6px; border:1px solid var(--hairline); border-radius:6px; font-size:12px; font-family:inherit; color:var(--ink-primary); }
.ms-actions{ display:flex; justify-content:space-between; font-size:11px; margin-bottom:6px; }
.ms-actions a{ color:var(--neutral); text-decoration:none; cursor:pointer; }
.ms-actions a:hover{ text-decoration:underline; }
.ms-options{ max-height:220px; overflow-y:auto; }
.ms-option{ display:flex; align-items:center; gap:7px; padding:5px 4px; font-size:12.5px; color:var(--ink-primary); cursor:pointer; border-radius:5px; }
.ms-option:hover{ background:#f4f6f9; }
.ms-option input{ margin:0; accent-color:var(--neutral); flex-shrink:0; }
.ms-option span{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ms-empty{ font-size:12px; color:var(--ink-muted); padding:6px 4px; }
@media (max-width:520px){
  .ms-panel{ position:fixed; left:12px; right:12px; top:auto; width:auto; max-height:60vh; }
}
.tbl-scroll{ max-height:430px; overflow-y:auto; overflow-x:auto; -webkit-overflow-scrolling:touch; border-top:1px solid var(--hairline); }
table{ width:100%; min-width:640px; border-collapse:collapse; font-size:12.5px; }
.table-narrow table{ min-width:0; }
@media (max-width:720px){
  .tbl-scroll{ max-height:60vh; }
  table{ min-width:600px; }
  .table-narrow table{ min-width:0; }
}
thead th{ position:sticky; top:0; background:#fafbfd; text-align:right; padding:8px 8px; font-weight:700; color:var(--ink-secondary); border-bottom:1px solid var(--hairline); white-space:nowrap; }
thead th:first-child, thead th:nth-child(2){ text-align:left; }
tbody td{ padding:6px 8px; text-align:right; border-bottom:1px solid #f1f3f6; white-space:nowrap; }
tbody td:first-child, tbody td:nth-child(2){ text-align:left; }
/* tabelas por equipamento (Saúde da Frota): texto à esquerda, data ao centro, números à direita */
table.tbl-equip{ font-size:12px; font-variant-numeric:tabular-nums; }
table.tbl-equip thead th, table.tbl-equip tbody td{ padding:6px 7px; }
table.tbl-equip thead th{ white-space:normal; vertical-align:bottom; line-height:1.25; }
table.tbl-equip th:nth-child(-n+5), table.tbl-equip td:nth-child(-n+5){ text-align:left; }
table.tbl-equip th:nth-child(6), table.tbl-equip td:nth-child(6){ text-align:center; }
table.tbl-texto3 th:nth-child(-n+3), table.tbl-texto3 td:nth-child(-n+3){ text-align:left; }
.table-narrow table.tbl-texto3{ font-size:12px; }
.table-narrow table.tbl-texto3 thead th, .table-narrow table.tbl-texto3 tbody td{ padding:6px 7px; }
.ms-option.ms-off{ display:none !important; }
.lbl-short{ display:none; }
table.tbl-og{ min-width:0; font-variant-numeric:tabular-nums; }
table.tbl-og thead th{ white-space:normal; vertical-align:bottom; line-height:1.25; }
.occ-row.occ-row-fab{ grid-template-columns:100px 78px 1fr 56px; }
table.tbl-og th:first-child, table.tbl-og td:first-child{ text-align:left; }
table.tbl-og-par th:nth-child(-n+5), table.tbl-og-par td:nth-child(-n+5){ text-align:left; }
table.tbl-og-par td:first-child{ color:var(--ink-muted); width:20px; }
.grid-2-iguais{ grid-template-columns:1fr 1fr; }
@media (max-width:1200px){ .grid-2-iguais{ grid-template-columns:1fr; } }
.vazio{ padding:26px 10px; text-align:center; color:var(--ink-muted); font-size:13px; }
.v-short{ display:none; }
.yoy-mob{ display:none; }

/* ===== celular ===== */
@media (max-width:720px){
  /* menu fixo no topo, 3 abas sempre visíveis */
  .sidebar{ position:sticky; top:0; z-index:40; background:var(--bg-deep); padding:8px 10px; gap:2px; box-shadow:0 2px 10px rgba(0,0,0,.25); }
  .sidebar-top{ margin:0 6px 0 0; }
  .sidebar-logo{ height:28px; padding:5px 8px; }
  .tab-btn{ flex:1; text-align:center; padding:9px 6px; font-size:13px; }
  .lbl-long{ display:none; }
  .lbl-short{ display:inline; }

  /* cabeçalho compacto: um logo só (o do menu), título em uma linha */
  .header{ padding:0 2px 4px; gap:4px; }
  .header .logo{ display:none; }
  .title-block h1{ font-size:19px; }
  .title-block .sub{ font-size:12px; }
  .header-right{ text-align:left; font-size:11.5px; }
  .hdr-fonte{ display:none; }
  .section-title{ margin:20px 2px 10px; flex-wrap:wrap; row-gap:2px; }

  /* cartões em 2 colunas; o primeiro de cada grupo ocupa a linha inteira */
  .grid{ gap:10px; }
  .grid-5, .grid-3{ grid-template-columns:1fr 1fr; }
  .grid-5 > :first-child, .grid-3 > :first-child{ grid-column:1 / -1; }
  .card{ padding:13px 14px; }
  .card h3{ font-size:11px; margin-bottom:8px; }
  .kpi-value, .grid-5 .kpi-value{ font-size:23px; }
  .grid-5 > :first-child .kpi-value, .grid-3 > :first-child .kpi-value{ font-size:30px; }
  .kpi-unit{ font-size:12px; }
  .kpi-row{ flex-wrap:wrap; row-gap:0; }
  .kpi-value{ white-space:nowrap; }
  .kpi-sub{ font-size:11.5px; }

  /* Comparativo Anual: versão própria */
  .yoy-desk{ display:none; }
  .yoy-mob{ display:block; }

  /* tabelas: só as colunas essenciais, sem arrastar para o lado */
  table.tbl-disp th:nth-child(3), table.tbl-disp td:nth-child(3){ display:none; }
  #tabelaModelos{ min-width:0; }
  #tabelaModelos{ font-size:12px; }
  #tabelaModelos thead th, #tabelaModelos tbody td{ padding:6px 5px; }
  .table-card{ padding:14px 12px 8px; }
  #tabelaModelos th:nth-child(2), #tabelaModelos td:nth-child(2),
  #tabelaModelos th:nth-child(3), #tabelaModelos td:nth-child(3),
  #tabelaModelos th:nth-child(7), #tabelaModelos td:nth-child(7),
  #tabelaModelos th:nth-child(9), #tabelaModelos td:nth-child(9){ display:none; }
  #tabelaSaude, table.tbl-nunca{ min-width:0; }
  #tabelaSaude th:nth-child(3), #tabelaSaude td:nth-child(3),
  #tabelaSaude th:nth-child(4), #tabelaSaude td:nth-child(4),
  #tabelaSaude th:nth-child(6), #tabelaSaude td:nth-child(6),
  #tabelaSaude th:nth-child(7), #tabelaSaude td:nth-child(7),
  #tabelaSaude th:nth-child(8), #tabelaSaude td:nth-child(8),
  #tabelaSaude th:nth-child(10), #tabelaSaude td:nth-child(10){ display:none; }
  .v-long{ display:none; }
  .v-short{ display:inline; }
  table.tbl-equip td.col-patr{ white-space:normal; min-width:98px; }
  table.tbl-equip td .tag{ font-size:9.5px; padding:1px 5px; }
  table.tbl-tipo-saude thead th, table.tbl-tipo-af thead th{ white-space:normal; vertical-align:bottom; }
  table.tbl-tipo-saude thead th, table.tbl-tipo-saude tbody td, table.tbl-tipo-af thead th, table.tbl-tipo-af tbody td{ padding:6px 5px; }
  table.tbl-tipo-saude td:first-child, table.tbl-tipo-af td:first-child{ max-width:112px; font-size:11px; overflow-wrap:anywhere; }
  #tabelaSaude{ font-size:11.5px; }
  #tabelaSaude thead th, #tabelaSaude tbody td{ padding:6px 3px; }
  #tabelaSaude td.col-patr{ padding-left:2px; }
  table.tbl-tipo-saude, table.tbl-tipo-af{ min-width:0; font-size:12px; }
  table.tbl-tipo-saude td:first-child, table.tbl-tipo-af td:first-child{ white-space:normal; }
  table.tbl-tipo-saude th:nth-child(3), table.tbl-tipo-saude td:nth-child(3),
  table.tbl-tipo-saude th:nth-child(4), table.tbl-tipo-saude td:nth-child(4),
  table.tbl-tipo-saude th:nth-child(5), table.tbl-tipo-saude td:nth-child(5),
  table.tbl-og{ font-size:11.5px; }
  .occ-row.occ-row-fab{ grid-template-columns:1fr 50px; }
  table.tbl-og thead th, table.tbl-og tbody td{ padding:6px 4px; white-space:normal; }
  table.tbl-og-fab th:nth-child(2), table.tbl-og-fab td:nth-child(2),
  table.tbl-og-ret th:nth-child(5), table.tbl-og-ret td:nth-child(5),
  table.tbl-og-par th:nth-child(1), table.tbl-og-par td:nth-child(1),
  table.tbl-og-par th:nth-child(4), table.tbl-og-par td:nth-child(4),
  table.tbl-og-par th:nth-child(6), table.tbl-og-par td:nth-child(6),
  table.tbl-og-idade th:nth-child(4), table.tbl-og-idade td:nth-child(4),
  table.tbl-tipo-af th:nth-child(4), table.tbl-tipo-af td:nth-child(4),
  table.tbl-tipo-af th:nth-child(6), table.tbl-tipo-af td:nth-child(6),
  table.tbl-tipo-af th:nth-child(3), table.tbl-tipo-af td:nth-child(3),
  table.tbl-tipo-af th:nth-child(5), table.tbl-tipo-af td:nth-child(5){ display:none; }
  table.tbl-equip td.col-patr::after{ content:attr(data-sub); display:block; margin-top:1px; font-size:11px; font-weight:400; color:var(--ink-muted); }
  #tabelaSaude th:nth-child(2), #tabelaSaude td:nth-child(2),
  #tabelaSaude th:nth-child(5), #tabelaSaude td:nth-child(5),
  table.tbl-nunca th:nth-child(2), table.tbl-nunca td:nth-child(2),
  table.tbl-nunca th:nth-child(5), table.tbl-nunca td:nth-child(5),
  table.tbl-nunca th:nth-child(3), table.tbl-nunca td:nth-child(3),
  table.tbl-nunca th:nth-child(4), table.tbl-nunca td:nth-child(4),
  table.tbl-nunca th:nth-child(6), table.tbl-nunca td:nth-child(6){ display:none; }
}
table.tbl-equip tbody tr:hover td{ background:#f7f9fc; }
table.tbl-equip td.col-patr{ font-weight:600; }
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
.bar-value{ font-size:9px; font-weight:700; fill:var(--ink-primary); }

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
    <img class="logo" src="data:image/png;base64,{LOGO_B64}" alt="Eleva Brasil" />
    <div class="title-block">
      <h1>Dashboard Gerencial de Operações</h1>
      <div class="sub">Visão Executiva &middot; Eleva Brasil</div>
    </div>
  </div>
  <div class="header-right">
    Atualizado em <b>{D['gerado_em']}</b><br/>
    <span class="hdr-fonte">Fonte: Faturamento, Status de Máquinas e Taxa de Ocupação</span>
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
      <span>Disp. {fmt_int(frota['disponivel'])}</span>
      <span>Contrato {fmt_int(frota['contrato'])}</span>
      <span>Manut. {fmt_int(frota['manutencao'])}</span>
    </div>
  </div>
  <div class="card">
    <h3>Máquinas Disponíveis</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-disp)">{fmt_int(frota['disponivel'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub">{pct(frota['disponivel_pct'])} da frota</div>
  </div>
  <div class="card">
    <h3>Máquinas em Contrato</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-contr-text)">{fmt_int(frota['contrato'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub">{pct(frota['contrato_pct'])} da frota</div>
  </div>
  <div class="card">
    <h3>Máquinas em Manutenção</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-manut)">{fmt_int(frota['manutencao'])}</span><span class="kpi-unit">máq.</span></div>
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
<div class="grid grid-3">
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
</div>
"""

# ---------------------------------------------------------------------------
# Linha 3 - Potencial de Faturamento (capital parado)
# ---------------------------------------------------------------------------
pot = D["potencial"]
kpi_pot = f"""
<div class="grid grid-3">
  <div class="card">
    <h3>Potencial Parado (Disponível)</h3>
    <div class="kpi-value" style="color:var(--status-disp)">{brl_m(pot['receita_parada'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_parada'])} do potencial mensal &middot; <span class="tag warning">capital parado</span></div>
  </div>
  <div class="card">
    <h3>Receita Ativa (Em Contrato)</h3>
    <div class="kpi-value" style="color:var(--status-contr-text)">{brl_m(pot['receita_ativa'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_ativa'])} do potencial mensal da frota</div>
  </div>
  <div class="card">
    <h3>Receita Perdida (Em Manutenção)</h3>
    <div class="kpi-value" style="color:var(--status-manut)">{brl_m(pot['receita_perdida_manut'])}<span class="kpi-unit">/mês</span></div>
    <div class="kpi-sub">{pct(pot['pct_perdida_manut'])} do potencial mensal <span class="tag critical">maior gargalo</span></div>
  </div>
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
        yoy_bars.append(
            f'<text class="bar-value" x="{x_ant+yoy_bar_w/2:.1f}" y="{max(y_ant-4, 10):.1f}" text-anchor="middle">{brl_m1(m["anterior"])}</text>'
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
        yoy_bars.append(
            f'<text class="bar-value" x="{x_atu+yoy_bar_w/2:.1f}" y="{max(y_atu-4, 10):.1f}" text-anchor="middle">{brl_m1(m["atual"])}</text>'
        )
    yoy_labels.append(f'<text class="axis-label" x="{gx+group_w/2:.1f}" y="{yoy_h-6}" text-anchor="middle">{m["mes_label"]}</text>')

# Versão celular: viewBox estreito e alto, sem rótulo de valor em cada barra
# (ficariam ilegíveis); o valor aparece no toque, pelo mesmo tooltip.
ym_w, ym_h = 360, 230
ym_pad_l, ym_pad_r, ym_pad_t, ym_pad_b = 4, 4, 8, 22
ym_plot_h = ym_h - ym_pad_t - ym_pad_b
ym_group_w = (ym_w - ym_pad_l - ym_pad_r) / n_months
ym_bar_w = (ym_group_w - 6 - 2) / 2
ym_parts = []
mes_corrente = max((mm["mes"] for mm in comp_meses if mm["atual"] is not None), default=None)
for i, m in enumerate(comp_meses):
    gx = ym_pad_l + i * ym_group_w
    for j, (valor, ano, cor) in enumerate([
        (m["anterior"], comp["ano_anterior"], "var(--ink-muted)"),
        (m["atual"], comp["ano_atual"], "var(--neutral)" if m["mes"] == mes_corrente else "var(--good)"),
    ]):
        if valor is None:
            continue
        bh = valor / comp_vmax * ym_plot_h
        bx = gx + 3 + j * (ym_bar_w + 2)
        sufixo = " (parcial)" if j == 1 and m["mes"] == mes_corrente else ""
        ym_parts.append(
            f'<rect class="bar" x="{bx:.1f}" y="{ym_pad_t + ym_plot_h - bh:.1f}" width="{ym_bar_w:.1f}" height="{max(bh, 2):.1f}" rx="2" '
            f'fill="{cor}" data-label="{m["mes_label"]}/{str(ano)[2:]}{sufixo}" data-value="{brl_m(valor)}"></rect>'
        )
    ym_parts.append(f'<text class="axis-label" x="{gx + ym_group_w / 2:.1f}" y="{ym_h - 6}" text-anchor="middle">{m["mes_label"]}</text>')

yoy_svg = f"""
<div class="chart-wrap yoy-desk">
  <svg viewBox="0 0 {yoy_w} {yoy_h}" width="100%" height="{yoy_h}" id="yoyChart">
    {''.join(yoy_bars)}
    {''.join(yoy_labels)}
  </svg>
  <div class="tooltip" id="yoyTooltip"></div>
</div>
<div class="chart-wrap yoy-mob">
  <svg viewBox="0 0 {ym_w} {ym_h}" width="100%" id="yoyChartMob">
    {''.join(ym_parts)}
  </svg>
  <div class="tooltip" id="yoyTooltipMob"></div>
  <div class="hint" style="text-align:center;margin-top:2px;">Toque numa barra para ver o valor</div>
</div>
"""

proj_delta = delta_html(comp["projecao_vs_ano_anterior_pct"], favor_up=True) if comp["projecao_vs_ano_anterior_pct"] is not None else '<span class="delta neutral">—</span>'

yoy_card = f"""
<div class="table-card">
  <h3>Comparativo Anual — {comp['ano_atual']} x {comp['ano_anterior']}</h3>
  <span class="hint">Faturamento líquido mês a mês &middot; <i class="dot" style="background:var(--ink-muted)"></i>{comp['ano_anterior']} &middot; <i class="dot" style="background:var(--good)"></i>{comp['ano_atual']} (mês corrente parcial em <i class="dot" style="background:var(--neutral)"></i>)</span>
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
        <div style="width:{t['disp_pct']}%; background:var(--status-disp)"></div>
        <div style="width:{t['contrato_pct']}%; background:var(--status-contr)"></div>
        <div style="width:{t['manut_pct']}%; background:var(--status-manut)"></div>
      </div>
      <div class="occ-pct">{pct(t['contrato_pct'])}</div>
    </div>""")

occ_table_card = f"""
<div class="table-card">
  <h3>Taxa de Ocupação por Tipo do Modelo</h3>
  <span class="hint">barra: <i class="dot disp"></i>Disponível <i class="dot contr"></i>Em Contrato <i class="dot manut"></i>Manutenção &middot; % à direita = ocupação</span>
  {''.join(occ_rows)}
</div>
"""

# ---------------------------------------------------------------------------
# Tabela - Disponibilidade por Modelo (scroll)
# ---------------------------------------------------------------------------
modelos = D["modelos_tabela"]
rows = []
obs_labels = {"critical": "Manutenção crítica", "neutral": "Capital parado", "good": "Alta demanda"}
for m in modelos:
    manut_cls = "num-crit" if m["manutencao_pct"] >= 60 else ("" if m["manutencao_pct"] < 40 else "num-crit")
    disp_cls = "num-neutral" if m["disponivel"] >= 5 else ""
    obs_kind = ""
    if m["manutencao_pct"] >= 70 and m["total"] >= 5:
        obs_kind = "critical"
    elif m["disponivel"] >= 5:
        obs_kind = "neutral"
    elif m["ocupacao_pct"] >= 80:
        obs_kind = "good"
    obs_label = obs_labels.get(obs_kind, "")
    flag = f'<span class="tag {obs_kind}">{obs_label.lower()}</span>' if obs_kind else ""
    tipo_title = m['tipo'].title()
    rows.append(f"""<tr data-modelo="{m['modelo']}" data-fabricante="{m['fabricante']}" data-tipo="{tipo_title}" data-obs="{obs_label or "Sem observação"}">
      <td>{m['modelo']}</td>
      <td>{m['fabricante']}</td>
      <td>{tipo_title}</td>
      <td class="{disp_cls}">{fmt_int(m['disponivel'])}</td>
      <td>{fmt_int(m['contrato'])}</td>
      <td class="{manut_cls}">{fmt_int(m['manutencao'])}</td>
      <td>{fmt_int(m['total'])}</td>
      <td>{pct(m['ocupacao_pct'])}</td>
      <td>{flag}</td>
    </tr>""")

modelos_unicos = sorted({m['modelo'] for m in modelos})
fabricantes_unicos = sorted({m['fabricante'] for m in modelos})
tipos_unicos = sorted({m['tipo'].title() for m in modelos})
obs_unicas = ["Manutenção crítica", "Capital parado", "Alta demanda", "Sem observação"]

modelos_table_card = f"""
<div class="table-card">
  <h3>Disponibilidade por Modelo</h3>
  <span class="hint">{len(modelos)} modelos &middot; ordenado por total de equipamentos &middot; role para ver todos &middot; filtros permitem selecionar mais de um valor</span>
  <div class="filter-row">
    {multiselect_html('filtroTipo', 'Tipo', tipos_unicos)}
    {multiselect_html('filtroFabricante', 'Fabricante', fabricantes_unicos)}
    {multiselect_html('filtroModelo', 'Modelo', modelos_unicos)}
    {multiselect_html('filtroObs', 'Observação', obs_unicas)}
    <button class="filter-clear" id="filtroLimpar" type="button">Limpar</button>
    <span class="hint" id="filtroContagem"></span>
  </div>
  <div class="tbl-scroll">
    <table id="tabelaModelos" class="tbl-texto3">
      <thead><tr>
        <th>Modelo</th><th>Fabricante</th><th>Tipo</th><th><span class="lbl-long">Disponível</span><span class="lbl-short">Disp.</span></th><th><span class="lbl-long">Contrato</span><span class="lbl-short">Contr.</span></th><th><span class="lbl-long">Manutenção</span><span class="lbl-short">Manut.</span></th><th>Total</th><th><span class="lbl-long">Ocupação %</span><span class="lbl-short">Ocup.</span></th><th>Observação</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Tabela - Equipamentos Disponíveis (unidade a unidade)
# ---------------------------------------------------------------------------
equip_disp = D["equipamentos_disponiveis"]
equip_rows = []
for e in equip_disp:
    equip_rows.append(f"""<tr>
      <td>{e['modelo']}</td>
      <td>{e['fabricante']}</td>
      <td>{e['tipo'].title()}</td>
      <td>{e['serie']}</td>
    </tr>""")

equip_disp_card = f"""
<div class="table-card table-narrow">
  <h3>Equipamentos Disponíveis</h3>
  <div class="tbl-scroll">
    <table class="tbl-texto3 tbl-disp">
      <thead><tr>
        <th>Modelo</th><th>Fabricante</th><th>Tipo</th><th>Nº de Série</th>
      </tr></thead>
      <tbody>{''.join(equip_rows)}</tbody>
    </table>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# ABA "Ocupação Financeira da Frota" - Valor de Aquisição
# ---------------------------------------------------------------------------
af = D["ativo_fixo"]
af_tipos = D["ativo_fixo_tipos"]

af_alerta = ""
if af["sem_registro_qtd"] > 0:
    af_alerta = f"""
<div class="alert-item critical" style="margin-bottom:18px;">
  <span class="alert-icon">🔴</span>
  <div><b>Cobertura de dados patrimoniais:</b> {af['sem_registro_qtd']} de {fmt_int(af['total_maquinas'])} equipamentos
  ({pct(af['sem_registro_pct'])} da frota) sem valor de compra registrado na planilha de Ativo Fixo — entram nas
  contagens acima mas com valor R$ 0,00. Nº de série: {', '.join(af['sem_registro_lista'])}.</div>
</div>
"""

og = D["ocupacao_gerencial"]
og_meta = og.get("meta_ocup_financeira_pct")
og_tipo_map = {t["nome"]: t for t in og["por_tipo"]}


def pct_ou_traco(v):
    return pct(v) if v is not None else "—"


# --- 1) Cartões de capital -------------------------------------------------
cap_total = af["total_valor"] or 1
seg = lambda v: v / cap_total * 100
gap = af["ocupacao_financeira_pct"] - af["ocupacao_fisica_pct"]
if gap >= 0:
    gap_txt = "As máquinas de maior valor estão mais alugadas que as de menor valor"
    gap_tag = '<span class="tag good">sinal positivo</span>'
else:
    gap_txt = "As máquinas de maior valor estão MENOS alugadas que as de menor valor"
    gap_tag = '<span class="tag critical">atenção</span>'
meta_html = ""
if og_meta:
    falta = max(og_meta / 100 * af["total_valor"] - af["contrato_v"], 0)
    meta_html = (f'<div class="kpi-sub" style="margin-top:6px;">Meta {pct(og_meta)} &middot; '
                 + (f'faltam <b>{brl_m(falta)}</b> em contrato' if falta > 0 else '<b>meta atingida</b>') + '</div>')

og_kpis = f"""
<div class="grid grid-5">
  <div class="card">
    <h3>Capital Investido</h3>
    <div class="kpi-value">{brl_m(af['total_valor'])}</div>
    <div class="mix-bar">
      <div class="mix-seg-contr" style="width:{seg(af['contrato_v']):.2f}%"></div>
      <div class="mix-seg-disp" style="width:{seg(af['disponivel_v']):.2f}%"></div>
      <div class="mix-seg-manut" style="width:{seg(af['manutencao_v']):.2f}%"></div>
    </div>
    <div class="kpi-sub">{fmt_int(af['total_maquinas'])} máquinas &middot; valor de compra</div>
  </div>
  <div class="card">
    <h3>Capital Produtivo (Em Contrato)</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-contr-text)">{brl_m(af['contrato_v'])}</span></div>
    <div class="kpi-sub">{pct(af['ocupacao_financeira_pct'])} do capital &middot; {fmt_int(af['contrato_n'])} máq.</div>
    {meta_html}
  </div>
  <div class="card">
    <h3>Capital Parado (Disponível)</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-disp)">{brl_m(af['disponivel_v'])}</span></div>
    <div class="kpi-sub">{pct(seg(af['disponivel_v']))} do capital &middot; {fmt_int(af['disponivel_n'])} máq.</div>
  </div>
  <div class="card">
    <h3>Capital em Manutenção</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-manut)">{brl_m(af['manutencao_v'])}</span></div>
    <div class="kpi-sub">{pct(seg(af['manutencao_v']))} do capital &middot; {fmt_int(af['manutencao_n'])} máq.</div>
  </div>
  <div class="card">
    <h3>Ocupação Física x Financeira</h3>
    <div class="kpi-row"><span class="kpi-value">{pct(af['ocupacao_fisica_pct'])}</span><span class="kpi-unit">x</span><span class="kpi-value">{pct(af['ocupacao_financeira_pct'])}</span></div>
    <div class="kpi-sub">{gap_txt} {gap_tag}</div>
  </div>
</div>
"""

# --- 6) Evolução da ocupação (histórico diário) ---------------------------
hist = og["historico"]
if len(hist) >= 2:
    hw, hh, hpl, hpr, hpt, hpb = 980, 220, 40, 14, 12, 26
    vals = [v for h in hist for v in (h["ocup_fisica_pct"], h["ocup_financeira_pct"]) if v is not None]
    if og_meta:
        vals.append(og_meta)
    vmin, vmax = max(min(vals) - 5, 0), min(max(vals) + 5, 100)
    vmax = vmax if vmax > vmin else vmin + 1
    X = lambda i: hpl + (hw - hpl - hpr) * (i / (len(hist) - 1))
    Y = lambda v: hpt + (hh - hpt - hpb) * (1 - (v - vmin) / (vmax - vmin))
    def linha(chave, cor):
        pts = " ".join(f"{X(i):.1f},{Y(h[chave]):.1f}" for i, h in enumerate(hist) if h[chave] is not None)
        return f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2.5" stroke-linejoin="round"/>'
    grade = "".join(
        f'<line x1="{hpl}" x2="{hw - hpr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="var(--hairline)"/>'
        f'<text class="axis-label" x="{hpl - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.0f}%</text>'
        for v in [vmin + (vmax - vmin) * k / 4 for k in range(5)])
    passo = max(1, len(hist) // 8)
    rotulos = "".join(
        f'<text class="axis-label" x="{X(i):.1f}" y="{hh - 6}" text-anchor="middle">{h["data"][8:10]}/{h["data"][5:7]}</text>'
        for i, h in enumerate(hist) if i % passo == 0 or i == len(hist) - 1)
    meta_linha = (f'<line x1="{hpl}" x2="{hw - hpr}" y1="{Y(og_meta):.1f}" y2="{Y(og_meta):.1f}" stroke="var(--warning)" stroke-dasharray="6 4"/>'
                  if og_meta else "")
    hist_corpo = f"""<svg viewBox="0 0 {hw} {hh}" width="100%">{grade}{meta_linha}{linha('ocup_fisica_pct', 'var(--ink-muted)')}{linha('ocup_financeira_pct', 'var(--neutral)')}{rotulos}</svg>"""
    hist_hint = (f'Uma medição por dia desde {hist[0]["data"][8:10]}/{hist[0]["data"][5:7]}/{hist[0]["data"][:4]} &middot; '
                 '<i class="dot" style="background:var(--neutral)"></i>Financeira <i class="dot" style="background:var(--ink-muted)"></i>Física'
                 + (' &middot; <span style="color:var(--warning)">- - meta</span>' if og_meta else ''))
else:
    hist_corpo = '<div class="vazio">A coleta diária começa com a publicação desta versão. O gráfico aparece a partir do 2º dia e fica mais útil com algumas semanas de dados.</div>'
    hist_hint = "Ocupação física e financeira, uma medição por dia"
og_hist_card = f"""
<div class="table-card">
  <h3>Evolução da Ocupação</h3>
  <span class="hint">{hist_hint}</span>
  {hist_corpo}
</div>
"""

# Seção de evolução fica desligada até a coleta diária ser aprovada
# (gravação depende do workflow - GRAVAR_HISTORICO=1).
MOSTRAR_EVOLUCAO = False
og_hist_secao = (f"""<div class="section-title"><h2>Evolução</h2><span class="hint">Ocupação dia a dia</span></div>
  {og_hist_card}
""" if MOSTRAR_EVOLUCAO else "")

# --- 2) Ocupação financeira por Fabricante --------------------------------
fab_rows, fab_tab = [], []
for f in og["por_fabricante"]:
    c = f["capital"] or 1
    fab_rows.append(f"""
    <div class="occ-row occ-row-fab">
      <div class="occ-name">{f['nome']}</div>
      <div class="occ-total">{brl_m(f['capital'])}</div>
      <div class="occ-stack" title="Em Contrato {f['capital_contrato']/c*100:.1f}% · Disponível {f['capital_disponivel']/c*100:.1f}% · Manutenção {f['capital_manutencao']/c*100:.1f}% do capital">
        <div style="width:{f['capital_contrato']/c*100:.2f}%; background:var(--status-contr)"></div>
        <div style="width:{f['capital_disponivel']/c*100:.2f}%; background:var(--status-disp)"></div>
        <div style="width:{f['capital_manutencao']/c*100:.2f}%; background:var(--status-manut)"></div>
      </div>
      <div class="occ-pct">{pct_ou_traco(f['ocup_financeira_pct'])}</div>
    </div>""")
    manut_cls = ' class="num-crit"' if (f["manut_capital_pct"] or 0) >= 40 else ""
    fab_tab.append(f"""<tr>
      <td>{f['nome']}</td><td>{fmt_int(f['qtd'])}</td><td>{brl_m(f['capital'])}</td>
      <td>{pct_ou_traco(f['ocup_fisica_pct'])}</td><td><b>{pct_ou_traco(f['ocup_financeira_pct'])}</b></td>
      <td{manut_cls}>{pct_ou_traco(f['manut_capital_pct'])}</td>
    </tr>""")
og_fab_card = f"""
<div class="grid grid-2 grid-2-iguais" style="align-items:stretch;">
  <div class="table-card">
    <h3>Capital por Fabricante e Status</h3>
    <span class="hint">barra = capital investido: <i class="dot contr"></i>Em Contrato <i class="dot disp"></i>Disponível <i class="dot manut"></i>Manutenção &middot; % à direita = ocupação financeira</span>
    {''.join(fab_rows)}
  </div>
  <div class="table-card">
    <h3>Ocupação por Fabricante</h3>
    <span class="hint">Ordenado por capital investido</span>
    <div class="tbl-scroll">
      <table class="tbl-og tbl-og-fab">
        <thead><tr><th>Fabricante</th><th>Máq.</th><th>Capital</th><th>Ocup. Física</th><th>Ocup. Financeira</th><th>Capital em Manut.</th></tr></thead>
        <tbody>{''.join(fab_tab)}</tbody>
      </table>
    </div>
  </div>
</div>
"""

# --- 3) Retorno sobre o capital ------------------------------------------
def retorno_tabela(itens, rotulo, titulo_fn=lambda n: n):
    linhas = []
    for r in itens:
        ret = r["retorno_pct"]
        ret_cls = "num-good" if (ret or 0) >= 100 else ""
        linhas.append(f"""<tr>
          <td>{titulo_fn(r['nome'])}</td><td>{brl_m(r['capital'])}</td><td>{brl_m(r['faturamento'])}</td>
          <td class="{ret_cls}">{pct_ou_traco(ret)}</td><td>{pct_ou_traco(r['despesa_capital_pct'])}</td>
        </tr>""")
    return f"""
  <div class="table-card">
    <h3>Retorno por {rotulo}</h3>
    <span class="hint">Faturamento e despesas acumulados desde o início dos registros &divide; capital investido</span>
    <div class="tbl-scroll">
      <table class="tbl-og tbl-og-ret">
        <thead><tr><th>{rotulo}</th><th>Capital</th><th>Faturamento Acum.</th><th>Fat. &divide; Capital</th><th>Despesas &divide; Capital</th></tr></thead>
        <tbody>{''.join(linhas)}</tbody>
      </table>
    </div>
  </div>"""
og_ret_card = f"""
<div class="grid grid-2 grid-2-iguais" style="align-items:stretch;">
  {retorno_tabela(og['por_fabricante'], 'Fabricante')}
  {retorno_tabela(og['por_tipo'], 'Tipo', lambda n: n.title())}
</div>
"""

# --- 4) Top 10 máquinas caras paradas -------------------------------------
par_rows = []
for i, e in enumerate(og["parados_top10"], 1):
    idade_txt = f"{e['idade_anos']:.1f} anos".replace(".", ",") if e["idade_anos"] is not None else "—"
    st_cls = "num-crit" if e["status"] == "Em Manutenção" else "num-good"
    par_rows.append(f"""<tr>
      <td>{i}</td><td class="col-patr">{e['patrimonio']}</td><td>{e['modelo']}</td><td>{e['fabricante']}</td>
      <td class="{st_cls}">{STATUS_ROTULO.get(e['status'], (e['status'],))[0]}</td><td>{idade_txt}</td><td><b>{brl(e['valor_compra'], 0)}</b></td>
    </tr>""")
par_total = sum(e["valor_compra"] for e in og["parados_top10"])
og_parados_card = f"""
<div class="table-card">
  <h3>As 10 Máquinas de Maior Valor Fora de Contrato</h3>
  <span class="hint">Disponíveis ou em manutenção agora &middot; somam {brl_m(par_total)} em capital parado</span>
  <div class="tbl-scroll">
    <table class="tbl-og tbl-og-par">
      <thead><tr><th>#</th><th>Patrimônio</th><th>Modelo</th><th>Fabricante</th><th>Status</th><th>Idade</th><th>Valor de Compra</th></tr></thead>
      <tbody>{''.join(par_rows)}</tbody>
    </table>
  </div>
</div>
"""

# --- 5) Capital por idade -------------------------------------------------
id_rows = []
for r in og["por_idade"]:
    id_rows.append(f"""<tr>
      <td>{r['nome']}</td><td>{fmt_int(r['qtd'])}</td><td>{brl_m(r['capital'])}</td><td>{pct(r['capital'] / cap_total * 100)}</td>
      <td>{pct_ou_traco(r['ocup_fisica_pct'])}</td><td><b>{pct_ou_traco(r['ocup_financeira_pct'])}</b></td>
    </tr>""")
og_idade_card = f"""
<div class="table-card">
  <h3>Capital por Idade da Frota</h3>
  <span class="hint">Idade desde a data de compra &middot; ajuda a decidir renovação e venda</span>
  <div class="tbl-scroll">
    <table class="tbl-og tbl-og-idade">
      <thead><tr><th>Idade</th><th>Máq.</th><th>Capital</th><th>% do Capital</th><th>Ocup. Física</th><th>Ocup. Financeira</th></tr></thead>
      <tbody>{''.join(id_rows)}</tbody>
    </table>
  </div>
</div>
"""

# --- Por Tipo (tabela existente + ocupação física/financeira) -------------
af_rows = []
for t in sorted(af_tipos, key=lambda x: x["total"], reverse=True):
    g = og_tipo_map.get(t["tipo"], {})
    af_rows.append(f"""<tr>
      <td>{t['tipo']}</td>
      <td>{fmt_int(t['total'])}</td>
      <td>{fmt_int(t['disponivel'])}</td>
      <td>{fmt_int(t['contrato'])}</td>
      <td>{fmt_int(t['manutencao'])}</td>
      <td>{brl(t['valor'], 2)}</td>
      <td>{pct_ou_traco(g.get('ocup_fisica_pct'))}</td>
      <td><b>{pct_ou_traco(g.get('ocup_financeira_pct'))}</b></td>
    </tr>""")

af_page = f"""
<div class="wrap">
  <div class="header">
    <div class="header-left">
      <img class="logo" src="data:image/png;base64,{LOGO_B64}" alt="Eleva Brasil" />
      <div class="title-block">
        <h1>Ocupação Financeira da Frota</h1>
        <div class="sub">Eleva Brasil</div>
      </div>
    </div>
    <div class="header-right">
      Atualizado em <b>{af['gerado_em']}</b><br/>
      <span class="hdr-fonte">Fonte: Status ao vivo (API LOC1) + Valor de Compra (planilha Ativo Fixo)</span>
    </div>
  </div>

  {af_alerta}

  <div class="section-title"><h2>Capital da Frota</h2><span class="hint">Quanto do capital investido está trabalhando agora</span></div>
  {og_kpis}

  {og_hist_secao}
  <div class="section-title"><h2>Por Fabricante</h2><span class="hint">Onde o capital de cada marca está</span></div>
  {og_fab_card}

  <div class="section-title"><h2>Retorno sobre o Capital</h2><span class="hint">Quanto cada real investido já devolveu</span></div>
  {og_ret_card}

  <div class="section-title"><h2>Onde Está o Dinheiro Parado</h2><span class="hint">Prioridade para locação ou manutenção</span></div>
  {og_parados_card}

  <div class="section-title"><h2>Idade da Frota</h2><span class="hint">Capital e ocupação por faixa de idade</span></div>
  {og_idade_card}

  <div class="section-title"><h2>Por Tipo de Equipamento</h2><span class="hint">Ordenado por total de equipamentos</span></div>
  <div class="table-card">
    <div class="tbl-scroll">
      <table class="tbl-tipo-af">
        <thead><tr>
          <th>Tipo</th><th>Total</th><th>Disponível</th><th>Em Contrato</th><th>Em Manutenção</th><th>Valor Aquisição</th><th>Ocup. Física</th><th>Ocup. Financeira</th>
        </tr></thead>
        <tbody>{''.join(af_rows)}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Dashboard de Ocupação Financeira da Frota &middot; Eleva Brasil &middot; métrica principal: Valor de Compra (Ativo Fixo) &middot; status/contagem ao vivo via API LOC1, valor atualizado quando a planilha de Ativo Fixo for reenviada.
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# ABA "Saúde da Frota" - por equipamento (Valor de Compra x Faturamento x
# Despesas acumulados, cruzado com status ao vivo da API)
# ---------------------------------------------------------------------------
sf = D["saude_frota"]
sf_tipos = D["saude_por_tipo"]
sf_tabela = D["saude_tabela"]
sf_hist = D["saude_idade_hist"]
sf_nunca_lista = D["saude_nunca_alugado_lista"]

sf_lucro_color = "var(--good)" if sf["lucro_acumulado_total"] >= 0 else "var(--critical)"
idade_media_txt = f"{sf['idade_media_anos']:.1f} anos".replace(".", ",") if sf["idade_media_anos"] is not None else "—"

# --- gráficos (estado inicial, sem filtro - o JS redesenha ao filtrar) ------
sf_comp_svg = hbar_svg(
    sorted([(t["tipo"].title(), t["total"]) for t in sf_tipos], key=lambda x: x[1], reverse=True),
    fmt_int, color="var(--neutral)"
)
sf_valor_svg = hbar_svg(
    [(t["tipo"].title(), t["valor_compra"]) for t in sf_tipos],  # já vem ordenado por valor investido
    brl_m1, color="var(--status-contr)"
)
sf_idade_hist_svg = vbar_svg([(h["faixa"], h["qtd"]) for h in sf_hist], fmt_int, color="var(--good)")

sf_comp_card = f"""
<div class="table-card">
  <h3>Composição da Frota por Tipo</h3>
  <span class="hint">Quantidade de equipamentos por Tipo de Modelo</span>
  <div id="sfCompChartWrap">{sf_comp_svg}</div>
</div>
"""

sf_valor_card = f"""
<div class="table-card">
  <h3>Valor Investido por Tipo</h3>
  <span class="hint">Soma do Valor de Compra por Tipo de Modelo</span>
  <div id="sfValorChartWrap">{sf_valor_svg}</div>
</div>
"""

sf_idade_card = f"""
<div class="table-card">
  <h3>Distribuição de Idade da Frota</h3>
  <span class="hint">Anos desde a compra (ou fabricação, quando a data de compra não é conhecida)</span>
  <div id="sfIdadeChartWrap">{sf_idade_hist_svg}</div>
</div>
"""



def status_html(status):
    rotulo, cls = STATUS_ROTULO.get(status, (status, ""))
    return f'<span class="st {cls}">{rotulo}</span>'


def sub_patr(e):
    """Linha de apoio sob o Patrimônio no celular (Modelo · Status)."""
    return f"{e['modelo']} · {STATUS_ROTULO.get(e['status'], (e['status'],))[0]}"


def valor_duplo(v):
    """Valor completo no computador, resumido (R$ 1,15 M) no celular."""
    return f'<span class="v-long">{brl(v, 0)}</span><span class="v-short">{brl_m(v)}</span>'


sf_nunca_rows = []
for e in sf_nunca_lista:
    idade_txt = f"{e['idade_anos']:.1f} anos".replace(".", ",") if e["idade_anos"] is not None else "—"
    sf_nunca_rows.append(f"""<tr>
      <td class="col-patr" data-sub="{sub_patr(e)}">{e['patrimonio']}</td>
      <td>{e['modelo']}</td>
      <td>{e['fabricante']}</td>
      <td>{e['tipo'].title()}</td>
      <td>{status_html(e['status'])}</td>
      <td>{e['data_compra'] or '—'}</td>
      <td>{idade_txt}</td>
      <td>{valor_duplo(e['valor_compra'])}</td>
    </tr>""")

sf_nunca_card = f"""
<div class="table-card table-narrow">
  <h3>Equipamentos que Nunca Geraram Faturamento</h3>
  <span class="hint" id="sfNuncaHint">{fmt_int(sf['qtd_nunca_alugado'])} no total ({fmt_int(sf['qtd_nunca_alugado_disponivel'])} disponíveis agora) &middot; {brl_m(sf['valor_nunca_alugado'])} em capital parado &middot; os 15 de maior valor investido</span>
  <div class="tbl-scroll">
    <table class="tbl-equip tbl-nunca">
      <thead><tr>
        <th>Patrimônio</th><th>Modelo</th><th>Fabricante</th><th>Tipo</th><th>Status</th><th>Data de Compra</th><th>Idade</th><th>Valor de Compra</th>
      </tr></thead>
      <tbody id="sfNuncaTbody">{''.join(sf_nunca_rows)}</tbody>
    </table>
  </div>
</div>
"""

sf_tipo_rows = []
for t in sf_tipos:
    roi_txt = pct(t["roi_pct"]) if t["roi_pct"] is not None else "—"
    roi_cls = "num-good" if (t["roi_pct"] or 0) >= 0 else "num-crit"
    sf_tipo_rows.append(f"""<tr>
      <td>{t['tipo']}</td>
      <td>{fmt_int(t['total'])}</td>
      <td>{brl(t['valor_compra'], 0)}</td>
      <td>{brl(t['faturamento'], 0)}</td>
      <td>{brl(t['despesas'], 0)}</td>
      <td>{brl(t['lucro'], 0)}</td>
      <td class="{roi_cls}">{roi_txt}</td>
    </tr>""")

sf_por_tipo_card = f"""
<div class="table-card">
  <h3>Saúde da Frota por Tipo de Equipamento</h3>
  <span class="hint">Ordenado por valor investido &middot; Lucro = Faturamento acumulado &minus; Despesas acumuladas &middot; ROI% = Lucro &divide; Valor de Compra</span>
  <div class="tbl-scroll">
    <table class="tbl-tipo-saude">
      <thead><tr>
        <th>Tipo</th><th>Qtd.</th><th>Valor de Compra</th><th>Faturamento Acum.</th><th>Despesas Acum.</th><th>Lucro Acum.</th><th>ROI %</th>
      </tr></thead>
      <tbody id="sfTipoTbody">{''.join(sf_tipo_rows)}</tbody>
    </table>
  </div>
</div>
"""

sf_rows = []
for e in sf_tabela:
    roi_txt = pct(e["roi_pct"]) if e["roi_pct"] is not None else "—"
    roi_cls = "" if e["roi_pct"] is None else ("num-good" if e["roi_pct"] >= 0 else "num-crit")
    idade_txt = f"{e['idade_anos']:.1f} anos".replace(".", ",") if e["idade_anos"] is not None else "—"
    tipo_title = e['tipo'].title()
    registro_flag = "" if e["tem_registro_financeiro"] else '<span class="tag warning">sem registro</span>'
    sf_rows.append(f"""<tr data-patrimonio="{e['patrimonio']}" data-modelo="{e['modelo']}" data-fabricante="{e['fabricante']}" data-tipo="{tipo_title}" data-status="{e['status']}">
      <td class="col-patr" data-sub="{sub_patr(e)}">{e['patrimonio']}</td>
      <td>{e['modelo']}</td>
      <td>{e['fabricante']}</td>
      <td>{tipo_title}</td>
      <td>{status_html(e['status'])}</td>
      <td>{e['data_compra'] or '—'}</td>
      <td>{idade_txt}</td>
      <td>{brl(e['valor_compra'], 0)}</td>
      <td>{registro_flag or valor_duplo(e['faturamento'])}</td>
      <td>{brl(e['despesas'], 0)}</td>
      <td>{valor_duplo(e['lucro'])}</td>
      <td class="{roi_cls}">{roi_txt}</td>
    </tr>""")

sf_modelos_unicos = sorted({e['modelo'] for e in sf_tabela})
sf_fabricantes_unicos = sorted({e['fabricante'] for e in sf_tabela})
sf_tipos_unicos = sorted({e['tipo'].title() for e in sf_tabela})
sf_status_unicos = ["Disponivel", "Em Contrato", "Em Manutenção"]

sf_tabela_card = f"""
<div class="table-card">
  <h3>Equipamentos — Cadastro Completo</h3>
  <span class="hint" id="sfCadastroHint">{len(sf_tabela)} de {len(sf_tabela)} equipamentos &middot; ordenado por Lucro Acumulado &middot; role para ver todos</span>
  <div class="tbl-scroll">
    <table id="tabelaSaude" class="tbl-equip">
      <thead><tr>
        <th>Patrimônio</th><th>Modelo</th><th>Fabricante</th><th>Tipo</th><th>Status</th><th>Data de Compra</th><th>Idade</th><th>Valor de Compra</th><th><span class="lbl-long">Faturamento Acum.</span><span class="lbl-short">Fat.</span></th><th>Despesas Acum.</th><th><span class="lbl-long">Lucro Acum.</span><span class="lbl-short">Lucro</span></th><th>ROI %</th>
      </tr></thead>
      <tbody id="tabelaSaudeBody">{''.join(sf_rows)}</tbody>
    </table>
  </div>
</div>
"""

# Dados por equipamento embutidos pro filtro global recalcular tudo no cliente
# (sem round-trip ao servidor) - só campos já públicos, sem dado de cliente.
sf_raw_json = json.dumps([
    {
        "patrimonio": e["patrimonio"], "modelo": e["modelo"], "fabricante": e["fabricante"], "tipo": e["tipo"].title(),
        "status": e["status"], "data_compra": e["data_compra"], "idade": e["idade_anos"], "valor_compra": e["valor_compra"],
        "faturamento": e["faturamento"], "despesas": e["despesas"], "lucro": e["lucro"],
        "roi": e["roi_pct"], "tem_registro": e["tem_registro_financeiro"],
    }
    for e in sf_tabela
], ensure_ascii=False)

sf_filtro_card = f"""
<div class="table-card" style="margin-bottom:14px;">
  <h3>Filtrar Frota</h3>
  <span class="hint">Selecione um ou mais valores de Tipo, Fabricante, Modelo e/ou Status, e/ou busque por Patrimônio - todos os números, gráficos e tabelas desta página recalculam na hora</span>
  <div class="filter-row" style="margin-top:10px;">
    <input class="filter-select filter-search" type="text" id="sfTopPatrimonio" placeholder="Buscar patrimônio" autocomplete="off" />
    {multiselect_html('sfTopTipo', 'Tipo', sf_tipos_unicos)}
    {multiselect_html('sfTopFabricante', 'Fabricante', sf_fabricantes_unicos)}
    {multiselect_html('sfTopModelo', 'Modelo', sf_modelos_unicos)}
    {multiselect_html('sfTopStatus', 'Status', sf_status_unicos)}
    <button class="filter-clear" id="sfTopLimpar" type="button">Limpar filtros</button>
    <span class="hint" id="sfTopContagem">{len(sf_tabela)} de {len(sf_tabela)} equipamentos selecionados</span>
  </div>
</div>
"""

sf_frota_card = f"""
<div class="grid grid-5">
  <div class="card">
    <h3>Total de Máquinas</h3>
    <div class="kpi-value" id="sfFrotaTotal">{fmt_int(frota['total'])}</div>
    <div class="mix-bar">
      <div class="mix-seg-disp" id="sfFrotaSegDisp" style="width:{frota['disponivel_pct']:.2f}%"></div>
      <div class="mix-seg-contr" id="sfFrotaSegContr" style="width:{frota['contrato_pct']:.2f}%"></div>
      <div class="mix-seg-manut" id="sfFrotaSegManut" style="width:{frota['manutencao_pct']:.2f}%"></div>
    </div>
    <div class="mix-legend">
      <span id="sfFrotaLegDisp">Disp. {fmt_int(frota['disponivel'])}</span>
      <span id="sfFrotaLegContr">Contrato {fmt_int(frota['contrato'])}</span>
      <span id="sfFrotaLegManut">Manut. {fmt_int(frota['manutencao'])}</span>
    </div>
  </div>
  <div class="card">
    <h3>Máquinas Disponíveis</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-disp)" id="sfFrotaDispVal">{fmt_int(frota['disponivel'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub" id="sfFrotaDispPct">{pct(frota['disponivel_pct'])} da frota</div>
  </div>
  <div class="card">
    <h3>Máquinas em Contrato</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-contr-text)" id="sfFrotaContrVal">{fmt_int(frota['contrato'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub" id="sfFrotaContrPct">{pct(frota['contrato_pct'])} da frota</div>
  </div>
  <div class="card">
    <h3>Máquinas em Manutenção</h3>
    <div class="kpi-row"><span class="kpi-value" style="color:var(--status-manut)" id="sfFrotaManutVal">{fmt_int(frota['manutencao'])}</span><span class="kpi-unit">máq.</span></div>
    <div class="kpi-sub" id="sfFrotaManutPct">{pct(frota['manutencao_pct'])} da frota</div>
  </div>
  <div class="card">
    <h3>Taxa de Ocupação</h3>
    <div class="kpi-row"><span class="kpi-value" id="sfFrotaOcup">{pct(frota['ocupacao_pct'])}</span></div>
    <div class="kpi-sub">Em Contrato &divide; Total de Máquinas (neste filtro)</div>
  </div>
</div>
"""

sf_page = f"""
<div class="wrap">
  <div class="header">
    <div class="header-left">
      <img class="logo" src="data:image/png;base64,{LOGO_B64}" alt="Eleva Brasil" />
      <div class="title-block">
        <h1>Saúde da Frota</h1>
        <div class="sub">Valor de Compra x Faturamento x Despesas, por equipamento &middot; Eleva Brasil</div>
      </div>
    </div>
    <div class="header-right">
      Atualizado em <b>{sf['gerado_em']}</b><br/>
      <span class="hdr-fonte">Fonte: Status ao vivo (API LOC1) + Ativo Fixo + Faturamento e Despesa por Equipamento</span>
    </div>
  </div>

  {sf_filtro_card}

  <div class="section-title"><h2>Frota</h2><span class="hint">Situação atual dos equipamentos, considerando o filtro acima</span></div>
  {sf_frota_card}

  <div class="section-title"><h2>Panorama</h2><span class="hint" id="sfPanoramaHint">{fmt_int(sf['total_equipamentos'])} equipamentos &middot; valores acumulados desde a origem das planilhas</span></div>
  <div class="grid grid-5">
    <div class="card">
      <h3>Valor Investido (Frota)</h3>
      <div class="kpi-value" id="sfKpiValor">{brl_m(sf['valor_compra_total'])}</div>
      <div class="kpi-sub">Soma do Valor de Compra de todos os equipamentos</div>
    </div>
    <div class="card">
      <h3>Faturamento Acumulado</h3>
      <div class="kpi-value" id="sfKpiFat">{brl_m(sf['faturamento_acumulado_total'])}</div>
      <div class="kpi-sub">Soma por equipamento (todos os tipos de nota)</div>
    </div>
    <div class="card">
      <h3>Despesas Acumuladas</h3>
      <div class="kpi-value" id="sfKpiDesp">{brl_m(sf['despesas_acumuladas_total'])}</div>
      <div class="kpi-sub">Soma do Valor de Despesas por equipamento</div>
    </div>
    <div class="card">
      <h3>Lucro Acumulado</h3>
      <div class="kpi-value" id="sfKpiLucro" style="color:{sf_lucro_color}">{brl_m(sf['lucro_acumulado_total'])}</div>
      <div class="kpi-sub">Faturamento &minus; Despesas &middot; ROI médio <span id="sfKpiRoiMedio">{pct(sf['roi_medio_pct'])}</span></div>
    </div>
    <div class="card">
      <h3>Idade Média da Frota</h3>
      <div class="kpi-value" id="sfKpiIdade">{idade_media_txt}</div>
    </div>
  </div>

  <div class="section-title"><h2>Composição e Investimento</h2><span class="hint">Por Tipo de Modelo</span></div>
  <div class="grid grid-2">
    {sf_comp_card}
    {sf_valor_card}
  </div>

  <div class="section-title"><h2>Idade da Frota</h2><span class="hint">Anos desde a compra, por faixa</span></div>
  {sf_idade_card}

  <div class="section-title"><h2>Pontos de Atenção</h2><span class="hint">Gerados a partir dos dados por equipamento</span></div>
  <div class="grid grid-4">
    <div class="card">
      <h3>Recuperaram o Investimento</h3>
      <div class="kpi-value" id="sfKpiRecuperouPct">{pct(sf['pct_recuperou_investimento'])}</div>
      <div class="kpi-sub">dos equipamentos com Valor de Compra registrado &middot; Faturamento &ge; Valor de Compra</div>
    </div>
    <div class="card">
      <h3>Nunca Alugados</h3>
      <div class="kpi-value" style="color:var(--critical)" id="sfKpiNuncaQtd">{fmt_int(sf['qtd_nunca_alugado'])}<span class="kpi-unit">equip.</span></div>
      <div class="kpi-sub" id="sfKpiNuncaSub">{brl_m(sf['valor_nunca_alugado'])} investidos, sem faturamento registrado <span class="tag critical">atenção</span></div>
    </div>
    <div class="card">
      <h3>Despesa Alta</h3>
      <div class="kpi-value" style="color:var(--critical)" id="sfKpiDespAltaQtd">{fmt_int(sf['qtd_despesa_alta'])}<span class="kpi-unit">equip.</span></div>
      <div class="kpi-sub">Despesas &ge; 50% do Faturamento acumulado <span class="tag critical">atenção</span></div>
    </div>
    <div class="card">
      <h3>Sem Registro Financeiro</h3>
      <div class="kpi-value" style="color:var(--warning)" id="sfKpiSemRegQtd">{fmt_int(sf['qtd_sem_registro_financeiro'])}<span class="kpi-unit">equip.</span></div>
      <div class="kpi-sub">Não aparecem na planilha de Faturamento e Despesa por Equipamento</div>
    </div>
  </div>

  <div style="margin-top:14px;">
    {sf_nunca_card}
  </div>

  <div style="margin-top:14px;">
    {sf_por_tipo_card}
  </div>

  <div style="margin-top:14px;">
    {sf_tabela_card}
  </div>

  <div class="footer">
    Saúde da Frota &middot; Eleva Brasil &middot; status/contagem ao vivo via API LOC1, Valor de Compra e Faturamento/Despesa atualizados quando as planilhas forem reenviadas.
  </div>
</div>
<script type="application/json" id="sfRawData">{sf_raw_json}</script>
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
      bar.addEventListener('click', function(e){
        bars.forEach(function(b){ b.style.opacity = 1; });
        bar.dispatchEvent(new MouseEvent('mousemove', {clientX: e.clientX, clientY: e.clientY}));
      });
    });
  }
  wireChart('yoyChart', 'yoyTooltip');
  wireChart('yoyChartMob', 'yoyTooltipMob');

  var tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      var target = btn.getAttribute('data-tab');
      tabBtns.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      document.querySelectorAll('.tab-page').forEach(function(p){ p.classList.remove('active'); });
      document.getElementById('tab-' + target).classList.add('active');
      if(window.innerWidth <= 900) window.scrollTo(0, 0);
    });
  });

  var shell = document.querySelector('.app-shell');
  var collapseBtn = document.getElementById('sidebarCollapse');
  var expandBtn = document.getElementById('sidebarExpand');
  function setCollapsed(collapsed){
    shell.classList.toggle('sidebar-collapsed', collapsed);
    try{ localStorage.setItem('eleva_sidebar_collapsed', collapsed ? '1' : '0'); }catch(e){}
  }
  if(collapseBtn) collapseBtn.addEventListener('click', function(){ setCollapsed(true); });
  if(expandBtn) expandBtn.addEventListener('click', function(){ setCollapsed(false); });
  try{
    if(localStorage.getItem('eleva_sidebar_collapsed') === '1') setCollapsed(true);
  }catch(e){}

  // Filtro de seleção múltipla (checkbox dropdown) - usado tanto na tabela
  // "Disponibilidade por Modelo" quanto no filtro global da Saúde da Frota.
  // Liga o comportamento a um bloco já renderizado por multiselect_html() em
  // generate_html.py: botão que abre um painel com busca + checkboxes.
  function wireMultiSelect(id, onChange){
    var wrap = document.getElementById(id);
    if(!wrap) return null;
    var btn = wrap.querySelector('.ms-btn');
    var panel = wrap.querySelector('.ms-panel');
    var search = wrap.querySelector('.ms-search');
    var checkboxes = Array.prototype.slice.call(wrap.querySelectorAll('.ms-options input[type=checkbox]'));
    var label = btn.getAttribute('data-label');
    var selected = new Set();

    function updateBtn(){
      btn.classList.toggle('active', selected.size > 0);
      if(selected.size === 0) btn.textContent = label + ' (todos)';
      else if(selected.size === 1){
        var v = Array.from(selected)[0];
        var cbSel = checkboxes.filter(function(c){ return c.value === v; })[0];
        btn.textContent = label + ': ' + (cbSel ? cbSel.nextElementSibling.textContent : v);
      }
      else btn.textContent = label + ' (' + selected.size + ' selecionados)';
    }
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      var wasOpen = panel.classList.contains('open');
      document.querySelectorAll('.ms-panel.open').forEach(function(p){ p.classList.remove('open'); });
      if(!wasOpen) panel.classList.add('open');
    });
    panel.addEventListener('click', function(e){ e.stopPropagation(); });
    checkboxes.forEach(function(cb){
      cb.addEventListener('change', function(){
        if(cb.checked) selected.add(cb.value); else selected.delete(cb.value);
        updateBtn();
        onChange();
      });
    });
    var actAll = wrap.querySelector('[data-act="all"]');
    var actNone = wrap.querySelector('[data-act="none"]');
    if(actAll) actAll.addEventListener('click', function(e){
      e.preventDefault();
      checkboxes.forEach(function(cb){ if(cb.parentElement.style.display !== 'none' && !cb.parentElement.classList.contains('ms-off')){ cb.checked = true; selected.add(cb.value); } });
      updateBtn(); onChange();
    });
    if(actNone) actNone.addEventListener('click', function(e){
      e.preventDefault();
      checkboxes.forEach(function(cb){ cb.checked = false; });
      selected.clear();
      updateBtn(); onChange();
    });
    if(search) search.addEventListener('input', function(){
      var q = search.value.toLowerCase();
      checkboxes.forEach(function(cb){
        var lbl = cb.parentElement;
        lbl.style.display = lbl.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
      });
    });

    return {
      getSelected: function(){ return selected; },
      clear: function(){ checkboxes.forEach(function(cb){ cb.checked = false; }); selected.clear(); updateBtn(); },
      // Mostra só as opções que existem dados com os outros filtros aplicados;
      // opção marcada que ficou indisponível é desmarcada. Devolve true se mudou a seleção.
      setAvailable: function(avail){
        var mudou = false;
        checkboxes.forEach(function(cb){
          var ok = avail.has(cb.value);
          cb.parentElement.classList.toggle('ms-off', !ok);
          if(!ok && cb.checked){ cb.checked = false; selected.delete(cb.value); mudou = true; }
        });
        if(mudou) updateBtn();
        return mudou;
      }
    };
  }

  // Filtros encadeados: cada filtro só oferece valores que existem nos itens
  // que passam pelos OUTROS filtros (ex.: Tipo = Manipulador -> Modelo e
  // Fabricante só listam manipuladores). filtros = [{ms, valor: item -> string}];
  // base = predicado extra aplicado a todos (ex.: busca por patrimônio).
  function encadearFiltros(itens, filtros, base){
    var mudou;
    do {
      mudou = false;
      filtros.forEach(function(f){
        if(!f.ms) return;
        var disponiveis = new Set();
        itens.forEach(function(it){
          if(base && !base(it)) return;
          var passa = filtros.every(function(g){
            if(g === f || !g.ms) return true;
            var sel = g.ms.getSelected();
            return sel.size === 0 || sel.has(g.valor(it));
          });
          if(passa) disponiveis.add(f.valor(it));
        });
        if(f.ms.setAvailable(disponiveis)) mudou = true;
      });
    } while(mudou);
  }
  document.addEventListener('click', function(){
    document.querySelectorAll('.ms-panel.open').forEach(function(p){ p.classList.remove('open'); });
  });

  var tabela = document.getElementById('tabelaModelos');
  if(tabela){
    var contagem = document.getElementById('filtroContagem');
    var linhas = Array.prototype.slice.call(tabela.querySelectorAll('tbody tr'));

    function attr(nome){ return function(tr){ return tr.getAttribute(nome); }; }
    function aplicarFiltros(){
      encadearFiltros(linhas, [
        {ms: msTipo, valor: attr('data-tipo')}, {ms: msFabricante, valor: attr('data-fabricante')},
        {ms: msModelo, valor: attr('data-modelo')}, {ms: msObs, valor: attr('data-obs')}
      ]);
      var selModelo = msModelo.getSelected(), selTipo = msTipo.getSelected(), selObs = msObs.getSelected(), selFab = msFabricante.getSelected();
      var visiveis = 0;
      linhas.forEach(function(tr){
        var ok = (selModelo.size === 0 || selModelo.has(tr.getAttribute('data-modelo')))
              && (selFab.size === 0 || selFab.has(tr.getAttribute('data-fabricante')))
              && (selTipo.size === 0 || selTipo.has(tr.getAttribute('data-tipo')))
              && (selObs.size === 0 || selObs.has(tr.getAttribute('data-obs')));
        tr.classList.toggle('filtro-oculto', !ok);
        if(ok) visiveis++;
      });
      contagem.textContent = (selModelo.size || selTipo.size || selObs.size || selFab.size) ? ('· ' + visiveis + ' de ' + linhas.length + ' modelos') : '';
    }
    var msModelo = wireMultiSelect('filtroModelo', aplicarFiltros);
    var msFabricante = wireMultiSelect('filtroFabricante', aplicarFiltros);
    var msTipo = wireMultiSelect('filtroTipo', aplicarFiltros);
    var msObs = wireMultiSelect('filtroObs', aplicarFiltros);
    var limparBtn = document.getElementById('filtroLimpar');
    if(limparBtn) limparBtn.addEventListener('click', function(){
      [msModelo, msFabricante, msTipo, msObs].forEach(function(ms){ if(ms) ms.clear(); });
      aplicarFiltros();
    });
  }

  var sfDataEl = document.getElementById('sfRawData');
  if(sfDataEl){
    var sfRaw = JSON.parse(sfDataEl.textContent);
    var sfRows = Array.prototype.slice.call(document.querySelectorAll('#tabelaSaudeBody tr'));

    function sfFmtInt(v){ return Math.round(v).toLocaleString('pt-BR'); }
    var sfStatusRotulo = {'Disponivel': ['Disponível', 'st-disp'], 'Em Contrato': ['Em Contrato', 'st-contr'], 'Em Manutenção': ['Em Manutenção', 'st-manut']};
    function sfStatusHtml(st){ var r = sfStatusRotulo[st] || [st, '']; return '<span class="st ' + r[1] + '">' + r[0] + '</span>'; }
    function sfBrl(v){ return 'R$ ' + Math.round(v).toLocaleString('pt-BR'); }
    function sfBrlM(v){
      if(Math.abs(v) < 1000000){ return 'R$ ' + (v/1000).toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' K'; }
      return 'R$ ' + (v/1000000).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' M';
    }
    function sfBrlM1(v){
      if(Math.abs(v) < 1000000){ return 'R$' + (v/1000).toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + 'K'; }
      return 'R$' + (v/1000000).toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + 'M';
    }
    function sfPct(v){ return v.toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + '%'; }

    function sfHbarSvg(rows, fmt, color){
      var labelW = 210, chartW = 560, rowH = 27;
      var vmax = 1;
      rows.forEach(function(r){ if(r[1] > vmax) vmax = r[1]; });
      var barArea = chartW - labelW - 70;
      var h = rows.length * rowH + 6;
      var parts = [];
      rows.forEach(function(r, i){
        var y = 6 + i * rowH;
        var barW = Math.max((r[1] / vmax) * barArea, 2);
        parts.push(
          '<text x="' + (labelW - 10) + '" y="' + (y + 15) + '" text-anchor="end" font-size="11.5" fill="var(--ink-secondary)">' + r[0] + '</text>' +
          '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + barW.toFixed(1) + '" height="16" rx="4" fill="' + color + '"></rect>' +
          '<text x="' + (labelW + barW + 8).toFixed(1) + '" y="' + (y + 15) + '" font-size="11" font-weight="700" fill="var(--ink-primary)">' + fmt(r[1]) + '</text>'
        );
      });
      return '<svg viewBox="0 0 ' + chartW + ' ' + h + '" width="100%" height="' + h + '">' + parts.join('') + '</svg>';
    }

    function sfVbarSvg(rows, fmt, color){
      var w = 980, h = 190, padL = 10, padR = 10, padT = 20, padB = 26;
      var plotW = w - padL - padR, plotH = h - padT - padB;
      var n = Math.max(rows.length, 1);
      var groupW = plotW / n, barW = groupW * 0.5;
      var vmax = 1;
      rows.forEach(function(r){ if(r[1] > vmax) vmax = r[1]; });
      var parts = [];
      rows.forEach(function(r, i){
        var bx = padL + i * groupW + (groupW - barW) / 2;
        var bh = (r[1] / vmax) * plotH;
        var by = padT + (plotH - bh);
        parts.push(
          '<rect x="' + bx.toFixed(1) + '" y="' + by.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + Math.max(bh, 2).toFixed(1) + '" rx="3" fill="' + color + '"></rect>' +
          '<text class="bar-value" x="' + (bx + barW / 2).toFixed(1) + '" y="' + Math.max(by - 6, 10).toFixed(1) + '" text-anchor="middle">' + fmt(r[1]) + '</text>' +
          '<text class="axis-label" x="' + (bx + barW / 2).toFixed(1) + '" y="' + (h - 6) + '" text-anchor="middle">' + r[0] + '</text>'
        );
      });
      return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '">' + parts.join('') + '</svg>';
    }

    var sfIdadeFaixas = [[0, 3, '0–2 anos'], [3, 6, '3–5 anos'], [6, 11, '6–10 anos'], [11, 16, '11–15 anos'], [16, 21, '16–20 anos'], [21, Infinity, '+20 anos']];

    var sfMsTipo = wireMultiSelect('sfTopTipo', sfRecompute);
    var sfMsFabricante = wireMultiSelect('sfTopFabricante', sfRecompute);
    var sfMsModelo = wireMultiSelect('sfTopModelo', sfRecompute);
    var sfMsStatus = wireMultiSelect('sfTopStatus', sfRecompute);
    var sfTopPatrimonio = document.getElementById('sfTopPatrimonio');
    var sfTopContagem = document.getElementById('sfTopContagem');

    function sfFiltered(){
      var selTipo = sfMsTipo.getSelected(), selFab = sfMsFabricante.getSelected(), selModelo = sfMsModelo.getSelected(), selStatus = sfMsStatus.getSelected();
      var vPatrimonio = sfTopPatrimonio.value.trim().toUpperCase();
      return sfRaw.filter(function(e){
        return (selTipo.size === 0 || selTipo.has(e.tipo)) && (selFab.size === 0 || selFab.has(e.fabricante))
            && (selModelo.size === 0 || selModelo.has(e.modelo)) && (selStatus.size === 0 || selStatus.has(e.status))
            && (!vPatrimonio || e.patrimonio.toUpperCase().indexOf(vPatrimonio) !== -1);
      });
    }

    function sfEncadear(){
      var vPatrimonio = sfTopPatrimonio.value.trim().toUpperCase();
      encadearFiltros(sfRaw, [
        {ms: sfMsTipo, valor: function(e){ return e.tipo; }}, {ms: sfMsFabricante, valor: function(e){ return e.fabricante; }},
        {ms: sfMsModelo, valor: function(e){ return e.modelo; }}, {ms: sfMsStatus, valor: function(e){ return e.status; }}
      ], function(e){ return !vPatrimonio || e.patrimonio.toUpperCase().indexOf(vPatrimonio) !== -1; });
    }

    function sfRecompute(){
      sfEncadear();
      var rows = sfFiltered();
      var n = rows.length;
      var valorCompra = 0, fat = 0, desp = 0, idadeSum = 0, idadeN = 0;
      var comValorCompra = 0, recuperou = 0, semRegistro = 0, despesaAlta = 0;
      var dispCount = 0, contrCount = 0, manutCount = 0;
      var nuncaAlugado = [];
      var porTipo = {};
      rows.forEach(function(e){
        valorCompra += e.valor_compra;
        fat += e.faturamento;
        desp += e.despesas;
        if(e.idade !== null){ idadeSum += e.idade; idadeN++; }
        if(e.valor_compra > 0){
          comValorCompra++;
          if(e.faturamento >= e.valor_compra) recuperou++;
        }
        if(!e.tem_registro) semRegistro++;
        if(e.faturamento > 0 && (e.despesas / e.faturamento) >= 0.5) despesaAlta++;
        if(e.faturamento <= 0) nuncaAlugado.push(e);
        if(e.status === 'Disponivel') dispCount++;
        else if(e.status === 'Em Contrato') contrCount++;
        else if(e.status === 'Em Manutenção') manutCount++;
        if(!porTipo[e.tipo]) porTipo[e.tipo] = {tipo: e.tipo, total: 0, valor: 0, fat: 0, desp: 0};
        var g = porTipo[e.tipo];
        g.total++; g.valor += e.valor_compra; g.fat += e.faturamento; g.desp += e.despesas;
      });
      var lucro = fat - desp;
      var lucroColor = lucro >= 0 ? 'var(--good)' : 'var(--critical)';

      // Frota
      document.getElementById('sfFrotaTotal').textContent = sfFmtInt(n);
      document.getElementById('sfFrotaSegDisp').style.width = (n ? dispCount / n * 100 : 0) + '%';
      document.getElementById('sfFrotaSegContr').style.width = (n ? contrCount / n * 100 : 0) + '%';
      document.getElementById('sfFrotaSegManut').style.width = (n ? manutCount / n * 100 : 0) + '%';
      document.getElementById('sfFrotaLegDisp').textContent = 'Disp. ' + sfFmtInt(dispCount);
      document.getElementById('sfFrotaLegContr').textContent = 'Contrato ' + sfFmtInt(contrCount);
      document.getElementById('sfFrotaLegManut').textContent = 'Manut. ' + sfFmtInt(manutCount);
      document.getElementById('sfFrotaDispVal').textContent = sfFmtInt(dispCount);
      document.getElementById('sfFrotaDispPct').textContent = (n ? sfPct(dispCount / n * 100) : '—') + ' da frota';
      document.getElementById('sfFrotaContrVal').textContent = sfFmtInt(contrCount);
      document.getElementById('sfFrotaContrPct').textContent = (n ? sfPct(contrCount / n * 100) : '—') + ' da frota';
      document.getElementById('sfFrotaManutVal').textContent = sfFmtInt(manutCount);
      document.getElementById('sfFrotaManutPct').textContent = (n ? sfPct(manutCount / n * 100) : '—') + ' da frota';
      document.getElementById('sfFrotaOcup').textContent = n ? sfPct(contrCount / n * 100) : '—';

      // Panorama
      document.getElementById('sfPanoramaHint').textContent = sfFmtInt(n) + ' equipamentos · valores acumulados desde a origem das planilhas';
      document.getElementById('sfKpiValor').textContent = sfBrlM(valorCompra);
      document.getElementById('sfKpiFat').textContent = sfBrlM(fat);
      document.getElementById('sfKpiDesp').textContent = sfBrlM(desp);
      var kpiLucro = document.getElementById('sfKpiLucro');
      kpiLucro.textContent = sfBrlM(lucro);
      kpiLucro.style.color = lucroColor;
      document.getElementById('sfKpiRoiMedio').textContent = valorCompra ? sfPct(lucro / valorCompra * 100) : '—';
      document.getElementById('sfKpiIdade').textContent = idadeN ? (idadeSum / idadeN).toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' anos' : '—';

      // Pontos de Atenção
      document.getElementById('sfKpiRecuperouPct').textContent = comValorCompra ? sfPct(recuperou / comValorCompra * 100) : '—';
      var valorNunca = nuncaAlugado.reduce(function(s, e){ return s + e.valor_compra; }, 0);
      var nuncaDisp = nuncaAlugado.filter(function(e){ return e.status === 'Disponivel'; }).length;
      document.getElementById('sfKpiNuncaQtd').innerHTML = sfFmtInt(nuncaAlugado.length) + '<span class="kpi-unit">equip.</span>';
      document.getElementById('sfKpiNuncaSub').innerHTML = sfBrlM(valorNunca) + ' investidos, sem faturamento registrado <span class="tag critical">atenção</span>';
      document.getElementById('sfKpiDespAltaQtd').innerHTML = sfFmtInt(despesaAlta) + '<span class="kpi-unit">equip.</span>';
      document.getElementById('sfKpiSemRegQtd').innerHTML = sfFmtInt(semRegistro) + '<span class="kpi-unit">equip.</span>';

      // Gráficos: composição, valor investido e idade
      var tipoList = Object.keys(porTipo).map(function(k){ return porTipo[k]; });
      var compRows = tipoList.slice().sort(function(a, b){ return b.total - a.total; }).map(function(g){ return [g.tipo, g.total]; });
      var valorRows = tipoList.slice().sort(function(a, b){ return b.valor - a.valor; }).map(function(g){ return [g.tipo, g.valor]; });
      document.getElementById('sfCompChartWrap').innerHTML = compRows.length ? sfHbarSvg(compRows, sfFmtInt, 'var(--neutral)') : '<span class="hint">Nenhum equipamento neste filtro.</span>';
      document.getElementById('sfValorChartWrap').innerHTML = valorRows.length ? sfHbarSvg(valorRows, sfBrlM1, 'var(--status-contr)') : '<span class="hint">Nenhum equipamento neste filtro.</span>';

      var idadeRows = sfIdadeFaixas.map(function(f){
        var qtd = rows.filter(function(e){ return e.idade !== null && e.idade >= f[0] && e.idade < f[1]; }).length;
        return [f[2], qtd];
      });
      document.getElementById('sfIdadeChartWrap').innerHTML = sfVbarSvg(idadeRows, sfFmtInt, 'var(--good)');

      // Tabela "Nunca Geraram Faturamento" (top 15 por valor de compra)
      nuncaAlugado.sort(function(a, b){ return b.valor_compra - a.valor_compra; });
      var nuncaTop = nuncaAlugado.slice(0, 15);
      document.getElementById('sfNuncaHint').textContent = sfFmtInt(nuncaAlugado.length) + ' no total (' + sfFmtInt(nuncaDisp) + ' disponíveis agora) · ' + sfBrlM(valorNunca) + ' em capital parado · os 15 de maior valor investido';
      document.getElementById('sfNuncaTbody').innerHTML = nuncaTop.map(function(e){
        var idadeTxt = e.idade !== null ? e.idade.toLocaleString('pt-BR', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' anos' : '—';
        var subPatr = e.modelo + ' · ' + (sfStatusRotulo[e.status] || [e.status])[0];
        return '<tr><td class="col-patr" data-sub="' + subPatr + '">' + e.patrimonio + '</td><td>' + e.modelo + '</td><td>' + e.fabricante + '</td><td>' + e.tipo + '</td>' +
          '<td>' + sfStatusHtml(e.status) + '</td><td>' + (e.data_compra || '—') + '</td><td>' + idadeTxt + '</td><td><span class="v-long">' + sfBrl(e.valor_compra) + '</span><span class="v-short">' + sfBrlM(e.valor_compra) + '</span></td></tr>';
      }).join('') || '<tr><td colspan="8">Nenhum equipamento neste filtro.</td></tr>';

      // Tabela "Saúde da Frota por Tipo de Equipamento" (ordenada por valor investido)
      var tipoOrdenado = tipoList.slice().sort(function(a, b){ return b.valor - a.valor; });
      document.getElementById('sfTipoTbody').innerHTML = tipoOrdenado.map(function(g){
        var gLucro = g.fat - g.desp;
        var roi = g.valor > 0 ? gLucro / g.valor * 100 : null;
        var roiTxt = roi !== null ? sfPct(roi) : '—';
        var roiCls = (roi || 0) >= 0 ? 'num-good' : 'num-crit';
        return '<tr><td>' + g.tipo + '</td><td>' + sfFmtInt(g.total) + '</td><td>' + sfBrl(g.valor) + '</td><td>' + sfBrl(g.fat) + '</td>' +
          '<td>' + sfBrl(g.desp) + '</td><td>' + sfBrl(gLucro) + '</td><td class="' + roiCls + '">' + roiTxt + '</td></tr>';
      }).join('') || '<tr><td colspan="7">Nenhum equipamento neste filtro.</td></tr>';

      // Tabela "Cadastro Completo": mostra/oculta linhas já renderizadas
      var selTipo2 = sfMsTipo.getSelected(), selFab2 = sfMsFabricante.getSelected(), selModelo2 = sfMsModelo.getSelected(), selStatus2 = sfMsStatus.getSelected();
      var vPatrimonio = sfTopPatrimonio.value.trim().toUpperCase();
      sfRows.forEach(function(tr){
        var ok = (selTipo2.size === 0 || selTipo2.has(tr.getAttribute('data-tipo')))
              && (selFab2.size === 0 || selFab2.has(tr.getAttribute('data-fabricante')))
              && (selModelo2.size === 0 || selModelo2.has(tr.getAttribute('data-modelo')))
              && (selStatus2.size === 0 || selStatus2.has(tr.getAttribute('data-status')))
              && (!vPatrimonio || tr.getAttribute('data-patrimonio').toUpperCase().indexOf(vPatrimonio) !== -1);
        tr.classList.toggle('filtro-oculto', !ok);
      });
      document.getElementById('sfCadastroHint').textContent = sfFmtInt(n) + ' de ' + sfFmtInt(sfRaw.length) + ' equipamentos · ordenado por Lucro Acumulado · role para ver todos';
      sfTopContagem.textContent = sfFmtInt(n) + ' de ' + sfFmtInt(sfRaw.length) + ' equipamentos selecionados';
    }

    sfTopPatrimonio.addEventListener('input', sfRecompute);
    var sfTopLimpar = document.getElementById('sfTopLimpar');
    if(sfTopLimpar) sfTopLimpar.addEventListener('click', function(){
      [sfMsTipo, sfMsFabricante, sfMsModelo, sfMsStatus].forEach(function(ms){ ms.clear(); });
      sfTopPatrimonio.value = '';
      sfRecompute();
    });
  }
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
<div class="app-shell">
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-top">
      <img class="sidebar-logo" src="data:image/png;base64,{LOGO_B64}" alt="Eleva Brasil" />
      <button class="sidebar-toggle" id="sidebarCollapse" title="Ocultar menu" aria-label="Ocultar menu">&laquo;</button>
    </div>
    <button class="tab-btn active" data-tab="exec"><span class="lbl-long">Visão Executiva</span><span class="lbl-short">Executiva</span></button>
    <button class="tab-btn" data-tab="af"><span class="lbl-long">Ocupação Financeira da Frota</span><span class="lbl-short">Ocupação</span></button>
    <button class="tab-btn" data-tab="saude"><span class="lbl-long">Saúde da Frota</span><span class="lbl-short">Saúde</span></button>
  </nav>
  <button class="sidebar-toggle sidebar-toggle-open" id="sidebarExpand" title="Mostrar menu" aria-label="Mostrar menu">&raquo;</button>
  <div class="app-main">

    <div id="tab-exec" class="tab-page active">
      <div class="wrap">
        {header_html}

        <div class="section-title"><h2>Frota</h2><span class="hint">Situação atual dos equipamentos</span></div>
        {kpi_frota}

        <div class="section-title"><h2>Potencial de Faturamento</h2><span class="hint">Onde está o dinheiro da frota, por status</span></div>
        {kpi_pot}

        <div class="section-title"><h2>Faturamento</h2><span class="hint">Valores líquidos, salvo indicação em contrário</span></div>
        {kpi_fat}

        <div class="section-title"><h2>Comparativo Anual</h2><span class="hint">Momento atual x mesmo momento do ano passado</span></div>
        <div style="margin-top:4px;">
          {yoy_card}
        </div>

        <div class="grid grid-2" style="margin-top:14px; align-items:stretch;">
          {occ_table_card}
          {equip_disp_card}
        </div>

        <div style="margin-top:14px;">
          {modelos_table_card}
        </div>

        <div class="footer">
          Dashboard Gerencial de Operações &middot; Eleva Brasil &middot; gerado automaticamente a partir da API da LOC1 (Faturamento, Status de Máquinas e Taxa de Ocupação) &middot; corte de dados: {fat['corte_label']}
        </div>
      </div>
    </div>

    <div id="tab-af" class="tab-page">
      {af_page}
    </div>

    <div id="tab-saude" class="tab-page">
      {sf_page}
    </div>

  </div>
</div>
{JS}
</body>
</html>
"""

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("dashboard_eleva.html gerado em:", OUT_FILE)
