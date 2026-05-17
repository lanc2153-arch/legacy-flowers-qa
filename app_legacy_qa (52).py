"""
Legacy Flowers QA — App completa con Supabase + Causas por criterio
"""
import io
import json
import math
from datetime import datetime, date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import streamlit as st
from supabase import create_client, Client

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ═══════════════════════════════════════════
# ⚙️  CONFIG
# ═══════════════════════════════════════════
st.set_page_config(page_title="Legacy Flowers QA", page_icon="🌹",
                   layout="wide", initial_sidebar_state="collapsed")

ROJO  = "#c00000"   # se mantiene en app
VERDE = "#2e7d32"
GRIS  = "#d9d9d9"

# Paleta PDF corporativa sobria
PDF_AZUL      = "#1a3a5c"   # azul oscuro encabezados
PDF_AZUL_MED  = "#4a6fa5"   # azul medio secciones
PDF_AZUL_CLAR = "#eef2f7"   # gris azulado muy claro
PDF_NC        = "#e57373"   # rojo pastel NC
PDF_C         = "#81c784"   # verde pastel conforme
PDF_NARANJA   = "#6b7f95"   # gris medio acento
COLORES_TORTA = ["#4a6fa5","#e57373","#81c784","#ffb74d",
                 "#ba68c8","#4db6ac","#f06292","#64b5f6"]

# Criterios con sus causas
CRITERIOS_PROD = [
    "Condición de armado",
    "Apertura",
    "Tamaño de Botón",
    "Condición de flor",
    "Fitosanidad en Botón",
    "Longitud de tallo",
    "Condición de tallo/Follaje",
    "Fitosanidad en tallo/Follaje",
]

CAUSAS_MAT = {
    "Capuchón":     ["Capuchón no corresponde", "Capuchón mal ubicado", "Capuchón en mal estado sucio/roto"],
    "Preservante":  ["Preservante no corresponde", "Preservante mal ubicado", "Preservante en mal estado sucio/roto"],
    "Caucho/Cinta": ["Caucho/Cinta no corresponde", "Caucho/Cinta mal ubicado", "Caucho/Cinta en mal estado sucio/roto"],
    "UPC":          ["UPC no corresponde", "UPC mal ubicado", "UPC en mal estado sucio/roto"],
}

CAUSAS = {
    "Apertura": ["Abierto", "Cerrado", "Mezclado"],
    "Condición de armado": [
        "Armado incorrecto (redondo-cuadrado)",
        "Desnivel",
        "Incorrecto número de tallos",
        "Incorrecta receta",
        "Variedad restringida",
    ],
    "Tamaño de Botón": [
        "Inconsistencia de tamaños de cabeza dentro del mismo ramo",
        "Tamaño de botón no pertenece a grado",
    ],
    "Condición de flor": [
        "Maltrato en flor",
        "Daño por presión",
        "Sobredespétale/Residuos de pétalos",
        "Bordeamiento/Flor quemada",
        "Residuo de producto",
        "Deshidratación",
    ],
    "Fitosanidad en Botón": [
        "Hongos en flor",
        "Presencia de plagas",
        "Daño por plagas",
    ],
    "Longitud de tallo": [
        "Tallo corto dentro del ramo",
        "Longitud de ramo incorrecta",
        'Mal corte "residuos"',
    ],
    "Condición de tallo/Follaje": [
        "Maltrato en follaje",
        "Follaje quemado/residuos",
        "Remoción de follaje/Desespine incorrecto",
    ],
    "Fitosanidad en tallo/Follaje": [
        "Hongos en follaje",
        "Presencia de plagas en follaje",
        "Daño por plagas",
    ],
}

CRITERIOS_MAT = [
    "Capuchón", "Preservante", "Caucho/Cinta", "UPC",
]

COL_PROD = {
    "Condición de armado":        "armado",
    "Apertura":                   "apertura",
    "Tamaño de Botón":            "tamano",
    "Condición de flor":          "condicion_flor",
    "Fitosanidad en Botón":       "fitosanidad",
    "Longitud de tallo":          "longitud",
    "Condición de tallo/Follaje": "condicion_tallos",
    "Fitosanidad en tallo/Follaje": "fitosanidad_tallos",
}
COL_MAT = {
    "Capuchón":     "capuchon",
    "Preservante":  "preservante",
    "Caucho/Cinta": "caucho",
    "UPC":          "upc",
}

COLORES_CAUSAS = [
    "#c00000","#e65100","#f57c00","#fbc02d","#388e3c",
    "#0288d1","#7b1fa2","#c2185b","#00796b","#5d4037",
]

# ═══════════════════════════════════════════
# 🎨  CSS
# ═══════════════════════════════════════════
st.markdown(f"""
<style>
  h2.title-red {{color:{ROJO};font-weight:bold;font-size:1.15rem;
    text-align:center;text-transform:uppercase;line-height:1.3;}}
  .section-title {{background:{GRIS};font-weight:bold;padding:6px;
    border:1px solid #000;margin-top:18px;text-align:center;font-size:.9rem;}}
  .meta-table {{border-collapse:collapse;font-size:.78rem;width:180px;}}
  .meta-table td {{border:1px solid #000;padding:4px;}}
  .calc-box {{background:#f5f5f5;border:1px solid #ccc;padding:14px;border-radius:6px;margin-top:10px;}}
  .calc-row {{display:flex;justify-content:space-between;margin-bottom:6px;}}
  .nc {{color:{ROJO};font-weight:bold;}} .c {{color:{VERDE};font-weight:bold;}}
  .stRadio > div {{flex-direction:row !important;gap:10px;}}
  .causas-box {{background:#fff5f5;border:1px solid #ffcccc;border-radius:6px;padding:10px;margin-top:6px;}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════
# 💾  SUPABASE
# ═══════════════════════════════════════════
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

def save_to_supabase(record: dict):
    sb = get_supabase()
    row = {
        "timestamp": record["timestamp"], "fecha": record["fecha"],
        "finca": record["finca"], "producto": record["producto"], "po": record["po"],
        "ramos_proc": record["ramos_proc"], "ramos_eval": record["ramos_eval"],
        "porc_muestra": record["porc_muestra"], "auditor": record["auditor"],
        "total_fallas": record["total_fallas"],
        "porc_nc": record["porc_nc"], "porc_c": record["porc_c"],
        "obs_generales": record["obs_generales"],
        "firma_auditor": record["firma_auditor"], "firma_resp": record["firma_resp"],
    }
    for crit, col in COL_PROD.items():
        d = record["prod_data"][crit]
        row[f"prod_{col}_status"] = d["status"]
        row[f"prod_{col}_qty"]    = d["qty"]
        row[f"prod_{col}_obs"]    = d["obs"]
        row[f"prod_{col}_causas"] = json.dumps(d.get("causas_ramos", {}))
    for crit, col in COL_MAT.items():
        d = record["mat_data"][crit]
        row[f"mat_{col}_status"] = d["status"]
        row[f"mat_{col}_qty"]    = d["qty"]
        row[f"mat_{col}_obs"]    = d["obs"]
        row[f"mat_{col}_causas"] = json.dumps(d.get("causas_ramos", {}))
    sb.table("checklists").insert(row).execute()

def load_from_supabase(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    sb = get_supabase()
    resp = (sb.table("checklists").select("*")
              .gte("fecha", fecha_ini).lte("fecha", fecha_fin)
              .order("fecha").execute())
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

# ═══════════════════════════════════════════
# 📊  TORTAS
# ═══════════════════════════════════════════
def _pie(ax, label, qty_nc, total, color_nc=None, color_c=None):
    if color_nc is None: color_nc = PDF_NC
    if color_c  is None: color_c  = PDF_AZUL_MED
    qty_c = max(total - qty_nc, 0)
    sizes = [qty_nc, qty_c] if qty_nc > 0 else [0, max(total, 1)]
    _, _, ats = ax.pie(sizes, colors=[color_nc, color_c],
                       explode=[0.05, 0] if qty_nc > 0 else [0, 0],
                       autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
                       startangle=90, pctdistance=0.75,
                       wedgeprops=dict(edgecolor="white", linewidth=2))
    for at in ats:
        at.set_fontsize(9); at.set_fontweight("bold"); at.set_color("white")
    ax.set_title(label, fontsize=8, fontweight="bold", pad=5, wrap=True,
                 color=PDF_AZUL)
    ax.set_facecolor("#f8f9fa")


def make_pie_global_causas(causas_ramos: dict, total: int) -> io.BytesIO:
    """Torta única con todas las causas consolidadas."""
    if not causas_ramos: return None
    labels  = list(causas_ramos.keys())
    valores = [max(v, 1) for v in causas_ramos.values()]
    clrs    = COLORES_TORTA[:len(labels)]

    fig, (ax_pie, ax_bar) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle("Consolidado de Causas — Todos los Criterios",
                 fontsize=12, fontweight="bold", color=PDF_AZUL)

    # Torta
    wedges, texts, ats = ax_pie.pie(
        valores, colors=clrs,
        autopct=lambda p: f"{p:.1f}%" if p > 1 else "",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=1.5))
    for at in ats:
        at.set_fontsize(8); at.set_fontweight("bold"); at.set_color("white")
    ax_pie.set_facecolor("#f8f9fa")
    ax_pie.set_title("Distribución por causa", fontsize=10,
                     fontweight="bold", color=PDF_AZUL)

    # Barras horizontales
    y_pos = range(len(labels))
    bars = ax_bar.barh(list(y_pos), valores, color=clrs, edgecolor="white", height=0.6)
    ax_bar.set_yticks(list(y_pos))
    short_labels = [l[:35]+"…" if len(l)>35 else l for l in labels]
    ax_bar.set_yticklabels(short_labels, fontsize=8)
    ax_bar.set_xlabel("Ramos", fontsize=9, color=PDF_AZUL)
    ax_bar.set_facecolor("#f8f9fa")
    ax_bar.set_title("Ramos por causa", fontsize=10,
                     fontweight="bold", color=PDF_AZUL)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    for bar, val in zip(bars, valores):
        pct = val/total*100 if total > 0 else 0
        ax_bar.text(bar.get_width()+0.2, bar.get_y()+bar.get_height()/2,
                    f"{val} ({pct:.1f}%)", va="center", fontsize=8, color=PDF_AZUL)
    ax_bar.invert_yaxis()

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf


def make_pie_criterio_completo(criterio, causas_ramos, qty_nc, total) -> io.BytesIO:
    """2 tortas lado a lado: general NC/C + desglose por causas."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("#f8f9fa")

    # Torta 1 — General NC vs C
    qty_c = max(total - qty_nc, 0)
    ax1 = axes[0]
    sizes1 = [qty_nc, qty_c] if qty_nc > 0 else [0, max(total,1)]
    _, _, ats = ax1.pie(
        sizes1, colors=[PDF_NC, PDF_AZUL_MED],
        explode=[0.05, 0] if qty_nc > 0 else [0,0],
        autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=2))
    for at in ats:
        at.set_fontsize(10); at.set_fontweight("bold"); at.set_color("white")
    ax1.set_title(f"NC vs Conforme\n{qty_nc} NC de {total} evaluados",
                  fontsize=10, fontweight="bold", color=PDF_AZUL, pad=8)
    ax1.set_facecolor("#f8f9fa")
    ax1.legend(["No Conforme","Conforme"], loc="lower center",
               fontsize=8, frameon=False, ncol=2)

    # Torta 2 — Desglose por causas
    ax2 = axes[1]
    if causas_ramos:
        labels2  = list(causas_ramos.keys())
        valores2 = [max(v,1) for v in causas_ramos.values()]
        clrs2    = COLORES_TORTA[:len(labels2)]
        _, _, ats2 = ax2.pie(
            valores2, colors=clrs2,
            autopct=lambda p: f"{p:.1f}%" if p > 1 else "",
            startangle=90, pctdistance=0.70,
            wedgeprops=dict(edgecolor="white", linewidth=1.5))
        for at in ats2:
            at.set_fontsize(9); at.set_fontweight("bold"); at.set_color("white")
        short = [l[:25]+"…" if len(l)>25 else l for l in labels2]
        ax2.legend(short, loc="lower center", fontsize=7,
                   frameon=False, ncol=1, bbox_to_anchor=(0.5,-0.15))
        total_causas = sum(causas_ramos.values())
        ax2.set_title(f"Causas — {criterio}\n{total_causas} ramos con causa asignada",
                      fontsize=10, fontweight="bold", color=PDF_AZUL, pad=8)
    else:
        ax2.text(0.5, 0.5, "Sin causas\nasignadas",
                 ha="center", va="center", fontsize=12, color="#888888",
                 transform=ax2.transAxes)
        ax2.set_title(f"Causas — {criterio}", fontsize=10,
                      fontweight="bold", color=PDF_AZUL, pad=8)
    ax2.set_facecolor("#f8f9fa")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf


def make_pie_criterios(criterios, data, total, title) -> io.BytesIO:
    n = len(criterios); cols = 3; rows = math.ceil(n / cols) + 1
    fig, axes = plt.subplots(rows, cols, figsize=(cols*3.5, rows*3.2))
    fig.suptitle(title, fontsize=13, fontweight="bold", color=ROJO, y=1.01)
    axes = axes.flatten()
    total_nc = 0
    for i, c in enumerate(criterios):
        qty = data[c]["qty"]; total_nc += qty
        _pie(axes[i], c, qty, total)
    last = (rows-1)*cols
    for j in range(n, last): axes[j].set_visible(False)
    mid = last + 1
    axes[last].set_visible(False)
    if last+2 < len(axes): axes[last+2].set_visible(False)
    _pie(axes[mid], f"RESUMEN {title}", total_nc, total,
         color_nc="#8b0000", color_c="#1b5e20")
    axes[mid].set_title(f"RESUMEN\n{total_nc} NC / {total} ramos",
                        fontsize=9, fontweight="bold", color="#8b0000", pad=5)
    fig.legend(handles=[mpatches.Patch(color=PDF_NC, label="No Conforme"),
                        mpatches.Patch(color=PDF_AZUL_MED, label="Conforme")],
               loc="lower center", ncol=2, fontsize=9, frameon=False)
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0); return buf


def make_pie_causas(criterio, causas_list, causas_marcadas, qty_nc, total) -> io.BytesIO:
    """Torta de causas para un criterio NC."""
    if not causas_marcadas:
        return None
    conteos = {c: 1 for c in causas_marcadas}
    labels  = list(conteos.keys())
    sizes   = list(conteos.values())
    clrs    = COLORES_TORTA[:len(labels)]

    fig, ax = plt.subplots(figsize=(7, 4))
    wedges, texts, autotexts = ax.pie(
        sizes, colors=clrs, startangle=90,
        autopct=lambda p: f"{p:.1f}%",
        pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=1.5),
    )
    for at in autotexts:
        at.set_fontsize(9); at.set_fontweight("bold"); at.set_color("white")
    ax.set_title(f"Causas: {criterio}\n({qty_nc} ramos NC de {total} evaluados)",
                 fontsize=10, fontweight="bold", color=ROJO, pad=8)
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5),
              fontsize=8, frameon=False)
    plt.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0); return buf


def make_pie_global(prod_data, mat_data, total) -> io.BytesIO:
    nc_p = sum(v["qty"] for v in prod_data.values())
    nc_m = sum(v["qty"] for v in mat_data.values())
    nc_t = nc_p + nc_m; c_t = max(total - nc_t, 0)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    fig.suptitle("RESUMEN GLOBAL DE CALIDAD", fontsize=13, fontweight="bold", color=ROJO)
    _pie(axes[0], "NC Producto",   nc_p, total)
    _pie(axes[1], "NC Materiales", nc_m, total, color_nc=PDF_NARANJA)
    axes[2].pie([nc_t, c_t] if nc_t > 0 else [0, 1], colors=[PDF_NC, PDF_AZUL_MED],
                autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
                startangle=90, pctdistance=0.75,
                wedgeprops=dict(edgecolor="white", linewidth=1.5),
                explode=[0.04, 0] if nc_t > 0 else [0, 0])
    axes[2].set_title("C vs NC Total", fontsize=10, fontweight="bold", pad=6)
    fig.legend(handles=[mpatches.Patch(color=PDF_NC, label="No Conforme"),
                        mpatches.Patch(color=PDF_AZUL_MED, label="Conforme")],
               loc="lower center", ncol=2, fontsize=9, frameon=False)
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0); return buf

# ═══════════════════════════════════════════
# 📄  PDF
# ═══════════════════════════════════════════
def generar_pdf(record: dict) -> bytes:
    import os
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.8*cm, rightMargin=1.8*cm)
    styles  = getSampleStyleSheet()
    rl_azul  = colors.HexColor(PDF_AZUL)
    rl_azulm = colors.HexColor(PDF_AZUL_MED)
    rl_azulc = colors.HexColor(PDF_AZUL_CLAR)
    rl_nc    = colors.HexColor(PDF_NC)
    rl_c     = colors.HexColor(PDF_C)
    rl_gris  = colors.HexColor(GRIS)
    story = []

    sec = ParagraphStyle("sec", parent=styles["Heading2"],
                         textColor=colors.white, backColor=rl_azul,
                         fontSize=10, spaceAfter=4, spaceBefore=8,
                         leftIndent=6, borderPadding=(4,4,4,6))

    # ── ENCABEZADO ─────────────────────────────────────────────
    logo_path = "Legaci_flowers.png"
    try:
        consecutivo_pdf = record.get("consecutivo", "001")
    except:
        consecutivo_pdf = "001"

    logo_cell = Image(logo_path, width=5*cm, height=1.8*cm) if os.path.exists(logo_path) else                 Paragraph("<b>LEGACY FLOWERS</b>",
                          ParagraphStyle("lf", parent=styles["Normal"],
                                         fontSize=13, textColor=rl_azul))

    t_meta_right = Table([
        ["Consecutivo:", consecutivo_pdf],
        ["Versión:", "001"],
        ["Fecha:", record["fecha"]],
        ["Página:", "1 de 1"],
    ], colWidths=[2.6*cm, 2.4*cm])
    t_meta_right.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#aaaaaa")),
        ("BACKGROUND",(0,0),(0,-1),rl_azulc),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))

    t_header = Table([[
        logo_cell,
        Paragraph("Lista de Chequeo Aseguramiento de Calidad<br/>"
                  "<b>Producto Terminado en Finca</b>",
                  ParagraphStyle("hdr", parent=styles["Normal"], fontSize=11,
                                 textColor=rl_azul, fontName="Helvetica-Bold",
                                 alignment=1, leading=16)),
        t_meta_right,
    ]], colWidths=[5.5*cm, 7*cm, 5.5*cm])
    t_header.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("BOX",(0,0),(-1,-1),1.5,rl_azul),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.HexColor("#aaaaaa")),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),
    ]))
    story.append(t_header)
    story.append(Paragraph("F-CHK-PTF-001-V01",
        ParagraphStyle("cod", parent=styles["Normal"], fontSize=7.5,
                       textColor=colors.HexColor("#888888"), spaceAfter=6)))
    story.append(HRFlowable(width="100%", thickness=2, color=rl_azul, spaceAfter=8))

    # ── DATOS GENERALES ────────────────────────────────────────
    meta = [
        ["Finca",            record["finca"],    "PO",               record["po"]],
        ["Fecha",            record["fecha"],     "Auditor",          record["auditor"]],
        ["Producto",         record["producto"],  "Ramos Procesados", str(record["ramos_proc"])],
        ["Ramos Evaluados",  str(record["ramos_eval"]),
         "% Muestra",        f"{record['porc_muestra']:.1f}%"],
    ]
    t_datos = Table(meta, colWidths=[3.5*cm, 6*cm, 3.5*cm, 5*cm])
    t_datos.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),rl_azulc),
        ("BACKGROUND",(2,0),(2,-1),rl_azulc),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
        ("FONTNAME",(1,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#bbbbbb")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white, colors.HexColor("#f4f8fc")]),
    ]))
    story.append(t_datos)
    story.append(Spacer(1, 0.3*cm))

    # ── RESUMEN NUMÉRICO ───────────────────────────────────────
    total = record["ramos_eval"]
    nc    = record["total_fallas"]
    t_res = Table([
        ["TOTAL EVALUADOS", str(total), "RAMOS CON FALLAS", str(nc)],
        ["% CONFORME",      f"{record['porc_c']:.2f}%",
         "% NO CONFORME",   f"{record['porc_nc']:.2f}%"],
    ], colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    t_res.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),rl_azulc),
        ("BACKGROUND",(2,0),(2,-1),rl_azulc),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),10),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#aaaaaa")),
        ("TEXTCOLOR",(1,1),(1,1),rl_c),
        ("TEXTCOLOR",(3,1),(3,1),rl_nc),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("FONTSIZE",(1,1),(1,1),13),
        ("FONTSIZE",(3,1),(3,1),13),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 0.35*cm))

    # ── OBSERVACIONES ──────────────────────────────────────────
    if record.get("obs_generales"):
        obs_box = Table([[
            Paragraph(f"<b>Observaciones:</b> {record['obs_generales']}",
                      ParagraphStyle("obs", parent=styles["Normal"], fontSize=9, leading=13))
        ]], colWidths=[18*cm])
        obs_box.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#fffbe6")),
            ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#f0c040")),
            ("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(obs_box)
        story.append(Spacer(1, 0.3*cm))

    # ── FIRMAS ─────────────────────────────────────────────────
    firma_a = record.get("firma_auditor","") or "________________________________"
    firma_r = record.get("firma_resp","")    or "________________________________"
    story.append(Spacer(1, 0.5*cm))
    t_firmas = Table([
        [Paragraph(f"<b>Auditor:</b> {firma_a}",
                   ParagraphStyle("fa", parent=styles["Normal"], fontSize=9)),
         Paragraph(f"<b>Responsable:</b> {firma_r}",
                   ParagraphStyle("fr", parent=styles["Normal"], fontSize=9))],
        [Paragraph("<font size=8 color='#666666'>_______________________________<br/>Firma Auditor de Calidad</font>",
                   ParagraphStyle("lfa", parent=styles["Normal"], alignment=1)),
         Paragraph("<font size=8 color='#666666'>_______________________________<br/>Firma Responsable de Finca</font>",
                   ParagraphStyle("lfr", parent=styles["Normal"], alignment=1))],
    ], colWidths=[9*cm, 9*cm])
    t_firmas.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("LINEBELOW",(0,0),(-1,0),0.8,colors.HexColor(PDF_AZUL)),
    ]))
    story.append(t_firmas)
    story.append(Spacer(1, 0.3*cm))

    # ── TABLA EN PÁGINA 1 ──────────────────────────────────────
    story.append(Paragraph("TABLA DETALLADA DE CRITERIOS Y OBSERVACIONES", sec))
    story.append(Spacer(1,0.2*cm))

    tabla_p1 = [["#","Categoría","Criterio","Estado","Ramos NC","Causas / Observación"]]
    fc_p1 = []; idx_p1 = 1
    for cat, crits, data in [("Producto", CRITERIOS_PROD, record["prod_data"]),
                               ("Materiales", CRITERIOS_MAT, record["mat_data"])]:
        for c in crits:
            v = data[c]
            cr = v.get("causas_ramos", {})
            if cr:
                causas_txt = ", ".join([f"{k}: {vv} ramos" for k,vv in cr.items()])
            elif v.get("obs"):
                causas_txt = v["obs"]
            else:
                causas_txt = "—"
            tabla_p1.append([str(idx_p1), cat, c, v["status"],
                          str(v["qty"]) if v["status"]=="NC" else "0", causas_txt])
            fc_p1.append((idx_p1, v["status"]=="NC"))
            idx_p1 += 1

    td_p1 = Table(tabla_p1, colWidths=[0.6*cm,2.3*cm,3.8*cm,1.4*cm,1.6*cm,8.3*cm])
    sty_p1 = [
        ("BACKGROUND",(0,0),(-1,0),rl_azul),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#bbbbbb")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#d5f5e3"), colors.HexColor("#d5f5e3")]),
    ]
    for ri, es_nc in fc_p1:
        if es_nc:
            sty_p1 += [
                ("BACKGROUND",(0,ri),(-1,ri),colors.HexColor("#ffd5d5")),
                ("TEXTCOLOR",(3,ri),(3,ri),rl_nc),
                ("FONTNAME",(3,ri),(3,ri),"Helvetica-Bold"),
            ]
    td_p1.setStyle(TableStyle(sty_p1))
    story.append(td_p1)

    # Pie de página
    story.append(Spacer(1, 0.2*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor("#cccccc"), spaceAfter=3))
    story.append(Paragraph(
        f"<font size=7 color='#999999'>Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} "
        f"| Legacy Flowers S.A.S | F-CHK-PTF-001-V01</font>",
        ParagraphStyle("pie", parent=styles["Normal"], alignment=1)))

    # ── TORTAS PRODUCTO ────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("GRÁFICAS POR CRITERIO — PRODUCTO", sec))
    story.append(Spacer(1,0.3*cm))
    story.append(Image(make_pie_criterios(CRITERIOS_PROD, record["prod_data"], total, "Producto"),
                       width=18*cm, height=18*cm))

    # ── TORTAS MATERIALES + GLOBAL ─────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("GRÁFICAS POR CRITERIO — MATERIALES", sec))
    story.append(Spacer(1,0.3*cm))
    story.append(Image(make_pie_criterios(CRITERIOS_MAT, record["mat_data"], total, "Materiales"),
                       width=18*cm, height=12*cm))
    story.append(Spacer(1,0.4*cm))
    story.append(Paragraph("RESUMEN GLOBAL", sec))
    story.append(Image(make_pie_global(record["prod_data"], record["mat_data"], total),
                       width=18*cm, height=7*cm))

    # ── CAUSAS POR CRITERIO ────────────────────────────────────
    causas_imgs = []
    for crit in CRITERIOS_PROD:
        d = record["prod_data"][crit]
        if d["status"] == "NC" and d.get("causas_ramos"):
            img = make_pie_causas(crit, CAUSAS.get(crit,[]), d["causas_ramos"], d["qty"], total)
            if img: causas_imgs.append(img)
    for crit in CRITERIOS_MAT:
        d = record["mat_data"][crit]
        if d["status"] == "NC" and d.get("causas_ramos"):
            img = make_pie_causas(crit, CAUSAS_MAT.get(crit,[]), d["causas_ramos"], d["qty"], total)
            if img: causas_imgs.append(img)

    # Gráficas por criterio NC — una por página, 2 tortas lado a lado
    criterios_nc = []
    for crit in CRITERIOS_PROD:
        d = record["prod_data"][crit]
        if d["status"] == "NC":
            criterios_nc.append((crit, d.get("causas_ramos",{}), d["qty"]))
    for crit in CRITERIOS_MAT:
        d = record["mat_data"][crit]
        if d["status"] == "NC":
            criterios_nc.append((crit, d.get("causas_ramos",{}), d["qty"]))

    if criterios_nc:
        story.append(PageBreak())
        story.append(Paragraph("DETALLE POR CRITERIO — NC vs CONFORME y CAUSAS", sec))
        story.append(Spacer(1,0.3*cm))
        for crit, cr, qty_nc_crit in criterios_nc:
            try:
                cr_safe = cr if isinstance(cr, dict) else {}
                img = make_pie_criterio_completo(crit, cr_safe, int(qty_nc_crit), int(total))
                if img:
                    story.append(Image(img, width=18*cm, height=7.5*cm))
                    story.append(Spacer(1,0.3*cm))
            except Exception as e:
                story.append(Paragraph(f"Error generando gráfica: {crit}",
                             ParagraphStyle("err", parent=styles["Normal"],
                                            textColor=colors.red)))

        # Torta global consolidada de TODAS las causas
        todas_causas_ramos = {}
        for crit in CRITERIOS_PROD:
            d = record["prod_data"][crit]
            for causa, ramos in d.get("causas_ramos", {}).items():
                todas_causas_ramos[causa] = todas_causas_ramos.get(causa, 0) + ramos
        for crit in CRITERIOS_MAT:
            d = record["mat_data"][crit]
            for causa, ramos in d.get("causas_ramos", {}).items():
                todas_causas_ramos[causa] = todas_causas_ramos.get(causa, 0) + ramos

        if todas_causas_ramos:
            story.append(Spacer(1,0.4*cm))
            story.append(Paragraph("RESUMEN GLOBAL DE TODAS LAS CAUSAS", sec))
            story.append(Spacer(1,0.3*cm))
            img_global_causas = make_pie_global_causas(todas_causas_ramos, total)
            if img_global_causas:
                story.append(Image(img_global_causas, width=18*cm, height=10*cm))


    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════
# 🖼️  ENCABEZADO
# ═══════════════════════════════════════════
def render_header():
    hoy = datetime.now().strftime("%d/%m/%Y")
    c1,c2,c3 = st.columns([0.8,2,1])
    with c1:
        try: st.image("Legaci_flowers.png", width=160)
        except: st.write("🌹 Legacy Flowers")
    with c2:
        st.markdown("<h2 class='title-red'>Lista de Chequeo Aseguramiento de Calidad<br>"
                    "Producto Terminado en Finca</h2>", unsafe_allow_html=True)
    with c3:
        # Consecutivo automático desde Supabase
        try:
            sb = get_supabase()
            resp = sb.table("checklists").select("id", count="exact").execute()
            consecutivo = str((resp.count or 0) + 1).zfill(3)
        except:
            consecutivo = "---"
        st.markdown(f"""<table class="meta-table">
            <tr><td>Consecutivo:</td><td><b>{consecutivo}</b></td></tr>
            <tr><td>Versión:</td><td><b>001</b></td></tr>
            <tr><td>Fecha:</td><td>{hoy}</td></tr></table>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════
# 🧩  FILA DE CRITERIO
# ═══════════════════════════════════════════
def criterio_row(criterio, prefix, ramos_eval) -> dict:
    ks = f"{prefix}_st"; kq = f"{prefix}_qty"; ko = f"{prefix}_obs"

    c1, c2, c3, c4 = st.columns([2, 1.2, 1.5, 2.5])
    with c1:
        st.markdown(f"**{criterio}**")
    with c2:
        status = st.radio("E", ["C","NC"], key=ks, horizontal=True,
                          label_visibility="collapsed")
    is_nc = status == "NC"
    with c3:
        if is_nc:
            causas_list_preview = CAUSAS.get(criterio, CAUSAS_MAT.get(criterio, []))
            if causas_list_preview:
                # Calcular suma previa para mostrar en el campo NC
                suma_previa = sum(
                    int(st.session_state.get(f"{prefix}_qtyc_{ci}", 0))
                    for ci in range(len(causas_list_preview))
                    if st.session_state.get(f"{prefix}_causa_{ci}", False)
                )
                qty = suma_previa
                color_nc = "#1e8449" if suma_previa > 0 else "#aaaaaa"
                st.markdown(
                    f"<div style='padding-top:4px;'>"
                    f"<span style='color:#888;font-size:0.75rem;'>Total NC</span><br>"
                    f"<b style='color:{color_nc};font-size:1.25rem;'>{suma_previa}</b>"
                    f"<span style='color:#bbb;font-size:0.72rem;'> ramos</span></div>",
                    unsafe_allow_html=True)
            else:
                qty = st.number_input("NC", min_value=0,
                                      max_value=int(ramos_eval) if ramos_eval > 0 else 9999,
                                      step=1, key=kq, help="Ramos que NO cumplen")
        else:
            if kq in st.session_state: st.session_state[kq] = 0
            qty = 0
            st.markdown("<span style='color:#2e7d32;font-size:1.3rem;'>✔</span>",
                        unsafe_allow_html=True)
    with c4:
        st.write("")

    causas_ramos = {}
    obs = ""

    if is_nc:
        causas_list = CAUSAS.get(criterio, CAUSAS_MAT.get(criterio, []))
        if causas_list:
            st.markdown(
                f"<div style='background:#eef2f7;border-left:4px solid #4a6fa5;"
                f"padding:10px 16px;border-radius:6px;margin:6px 0;'>"
                f"<b style='color:#1a3a5c;font-size:0.9rem;'>Causas — {criterio}</b></div>",
                unsafe_allow_html=True)

            for ci, causa in enumerate(causas_list):
                ckey = f"{prefix}_causa_{ci}"
                qkey = f"{prefix}_qtyc_{ci}"
                col_chk, col_num, col_pct = st.columns([3, 1.5, 2])
                with col_chk:
                    selec = st.checkbox(causa, key=ckey)
                with col_num:
                    if selec:
                        rc = st.number_input(
                            "Ramos", min_value=0,
                            max_value=9999,
                            step=1, key=qkey,
                            label_visibility="collapsed")
                        causas_ramos[causa] = int(rc)
                    else:
                        if qkey in st.session_state:
                            st.session_state[qkey] = 0
                        st.write("")
                with col_pct:
                    if selec:
                        total_hasta_ahora = sum(causas_ramos.values())
                        v = causas_ramos.get(causa, 0)
                        if total_hasta_ahora > 0:
                            pct = v / total_hasta_ahora * 100
                            col = "#c0392b" if pct > 50 else "#e67e22" if pct > 20 else "#4a6fa5"
                            st.markdown(
                                f"<div style='padding-top:5px;'>"
                                f"<b style='color:{col};font-size:0.9rem;'>{pct:.0f}%</b>"
                                f"<span style='color:#bbb;font-size:0.72rem;'> del total</span></div>",
                                unsafe_allow_html=True)
                    else:
                        st.write("")




        obs = st.text_input("Observación adicional", key=ko,
                            placeholder="Observación adicional...",
                            label_visibility="collapsed")
    else:
        if ko in st.session_state: st.session_state[ko] = ""

    return {"status": status, "qty": int(qty), "obs": obs,
            "causas_ramos": causas_ramos, "causas": list(causas_ramos.keys())}

# ═══════════════════════════════════════════
# 📝  FORMULARIO
# ═══════════════════════════════════════════
def render_form():
    fk = st.session_state.get("form_key", 0)
    st.markdown('<div class="section-title">📋 DATOS GENERALES</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        finca    = st.text_input("Finca",    key=f"finca_{fk}")
        fecha    = st.date_input("Fecha",    date.today(), key=f"fecha_{fk}")
        producto = st.text_input("Producto", key=f"producto_{fk}")
        auditor  = st.text_input("Nombre Auditor", key=f"auditor_{fk}")
    with c2:
        po         = st.text_input("PO", key=f"po_{fk}")
        ramos_proc = st.number_input("Ramos Procesados",          min_value=0, step=1, key=f"ramos_proc_{fk}")
        ramos_eval = st.number_input("Ramos Evaluados (Muestra)", min_value=1, step=1, key=f"ramos_eval_{fk}")
        porc_m = (ramos_eval/ramos_proc*100) if ramos_proc>0 else 0
        color_m = VERDE if porc_m>=10 else ROJO
        st.markdown(f"""<div style="background:#f5f5f5;border:1px solid #ccc;border-radius:4px;
                        padding:8px 12px;margin-top:4px;">
            <span style="font-size:.8rem;color:#555;">% Muestra sobre procesado:</span><br>
            <span style="font-size:1.3rem;font-weight:bold;color:{color_m};">{porc_m:.1f}%</span>
            <span style="font-size:.75rem;color:#888;">&nbsp;({int(ramos_eval)} de {int(ramos_proc)} ramos)</span>
            </div>""", unsafe_allow_html=True)
    st.divider()

    # CRITERIOS PRODUCTO
    st.markdown('<div class="section-title">✅ CRITERIO ESTÁNDAR PRODUCTO</div>', unsafe_allow_html=True)
    h1,h2,h3,h4 = st.columns([2,1.2,1.5,2.5])
    with h1: st.caption("**Criterio**")
    with h2: st.caption("**Estado**")
    with h3: st.caption("**Cant. NC**")
    with h4: st.caption("**Causas / Observación**")

    prod_data = {}
    for i,c in enumerate(CRITERIOS_PROD):
        prod_data[c] = criterio_row(c, f"prod_{i}_{fk}", ramos_eval)
        st.divider()

    # CRITERIOS MATERIALES
    st.markdown('<div class="section-title">📦 CRITERIO ESTÁNDAR MATERIALES</div>', unsafe_allow_html=True)
    h1,h2,h3,h4 = st.columns([2,1.2,1.5,2.5])
    with h1: st.caption("**Criterio**")
    with h2: st.caption("**Estado**")
    with h3: st.caption("**Cant. NC**")
    with h4: st.caption("**Observación**")

    mat_data = {}
    for i,c in enumerate(CRITERIOS_MAT):
        mat_data[c] = criterio_row(c, f"mat_{i}_{fk}", ramos_eval)
        st.divider()

    # CÁLCULOS
    st.markdown('<div class="section-title">📊 CÁLCULOS DE CALIDAD</div>', unsafe_allow_html=True)
    total_f = sum(v["qty"] for v in prod_data.values()) + sum(v["qty"] for v in mat_data.values())
    porc_nc = (total_f/ramos_eval*100) if ramos_eval>0 else 0
    porc_c  = 100 - porc_nc
    st.markdown(f"""<div class="calc-box">
        <div class="calc-row"><span>Total Ramos con Fallas:</span><span class="nc">{total_f}</span></div>
        <hr>
        <div class="calc-row"><span>% No Conforme:</span><span class="nc">{porc_nc:.2f}%</span></div>
        <div class="calc-row"><span>% Conforme:</span><span class="c">{porc_c:.2f}%</span></div>
        </div>""", unsafe_allow_html=True)
    st.divider()

    obs_gen       = st.text_area("Observaciones Generales", key=f"obs_gen_{fk}")
    firma_auditor = st.text_input("Firma Auditor",          key=f"firma_auditor_{fk}")
    firma_resp    = st.text_input("Firma Responsable",      key=f"firma_resp_{fk}")

    if st.button("💾 GUARDAR CHECKLIST", type="primary", use_container_width=True):
        record = {
            "timestamp": datetime.now().isoformat(),
            "fecha": str(fecha), "finca": finca, "producto": producto, "po": po,
            "ramos_proc": int(ramos_proc), "ramos_eval": int(ramos_eval),
            "porc_muestra": round(porc_m,2), "auditor": auditor,
            "prod_data": prod_data, "mat_data": mat_data,
            "total_fallas": total_f, "porc_nc": round(porc_nc,2), "porc_c": round(porc_c,2),
            "obs_generales": obs_gen, "firma_auditor": firma_auditor, "firma_resp": firma_resp,
        }
        # Validar que criterios NC tengan al menos una causa si hay causas disponibles
        errores_causas = []
        for crit in CRITERIOS_PROD + CRITERIOS_MAT:
            d = prod_data[crit] if crit in CRITERIOS_PROD else mat_data[crit]
            causas_disponibles = CAUSAS.get(crit, CAUSAS_MAT.get(crit, []))
            if d["status"] == "NC" and causas_disponibles and not d.get("causas_ramos"):
                errores_causas.append(f"**{crit}**: selecciona al menos una causa")

        if errores_causas:
            st.warning("⚠️ Advertencia: algunos criterios NC no tienen causas seleccionadas:")
            for err in errores_causas:
                st.markdown(f"• {err}")

        try:
            save_to_supabase(record)
            st.session_state["ultimo_record"] = record
            st.session_state["guardado_ok"] = True
            st.session_state["form_key"] = st.session_state.get("form_key", 0) + 1
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
    
    # Mostrar mensaje de éxito después del rerun
    if st.session_state.get("guardado_ok"):
        st.success("✅ ¡Checklist guardado correctamente! Puedes llenar uno nuevo.")
        st.session_state["guardado_ok"] = False

# ═══════════════════════════════════════════
# 📈  HISTORIAL + PDF
# ═══════════════════════════════════════════
def _parse_causas_json(val):
    """Convierte JSON guardado en Supabase a dict {causa: ramos}."""
    if not val: return {}
    try:
        result = json.loads(val)
        if isinstance(result, dict):
            return {k: int(v) for k,v in result.items()}
        return {}
    except:
        return {}

def _row_to_record(row) -> dict:
    prod_data = {c: {
        "status":      row.get(f"prod_{col}_status","C"),
        "qty":         int(row.get(f"prod_{col}_qty",0) or 0),
        "obs":         row.get(f"prod_{col}_obs","") or "",
        "causas_ramos": _parse_causas_json(row.get(f"prod_{col}_causas","")),
        "causas":      list(_parse_causas_json(row.get(f"prod_{col}_causas","")).keys()),
    } for c,col in COL_PROD.items()}
    mat_data = {c: {
        "status":      row.get(f"mat_{col}_status","C"),
        "qty":         int(row.get(f"mat_{col}_qty",0) or 0),
        "obs":         row.get(f"mat_{col}_obs","") or "",
        "causas_ramos": _parse_causas_json(row.get(f"mat_{col}_causas","")),
        "causas":      list(_parse_causas_json(row.get(f"mat_{col}_causas","")).keys()),
    } for c,col in COL_MAT.items()}
    return {**row, "prod_data":prod_data, "mat_data":mat_data,
            "ramos_eval":   int(row.get("ramos_eval",1) or 1),
            "porc_muestra": float(row.get("porc_muestra",0) or 0),
            "total_fallas": int(row.get("total_fallas",0) or 0),
            "porc_nc":      float(row.get("porc_nc",0) or 0),
            "porc_c":       float(row.get("porc_c",100) or 100)}

def render_dashboard():
    st.markdown('<div class="section-title">📈 HISTORIAL Y GENERACIÓN DE PDF</div>',
                unsafe_allow_html=True)
    if "ultimo_record" in st.session_state:
        st.info("📄 Último checklist guardado listo para exportar:")
        if st.button("📥 Generar PDF del último checklist"):
            with st.spinner("Generando PDF…"):
                pdf = generar_pdf(st.session_state["ultimo_record"])
            nombre = f"QA_{st.session_state['ultimo_record']['finca']}_{st.session_state['ultimo_record']['fecha']}.pdf".replace(" ","_")
            st.download_button("⬇️ Descargar PDF", data=pdf, file_name=nombre,
                               mime="application/pdf", use_container_width=True)
    st.markdown("---")
    st.subheader("📅 Generar PDF por rango de fechas")
    c1,c2 = st.columns(2)
    with c1: fi = st.date_input("Fecha inicio", key="fi")
    with c2: ff = st.date_input("Fecha fin",    key="ff")

    if st.button("🔍 Buscar registros del periodo"):
        with st.spinner("Consultando Supabase…"):
            try: df = load_from_supabase(str(fi), str(ff))
            except Exception as e: st.error(f"Error: {e}"); return
        if df.empty: st.warning("No hay registros en ese rango."); return
        st.success(f"**{len(df)}** registros entre {fi} y {ff}.")
        st.dataframe(df[["fecha","finca","auditor","ramos_eval",
                          "total_fallas","porc_c","porc_nc"]], use_container_width=True)
        st.session_state["df_periodo"] = df

    if "df_periodo" in st.session_state:
        df = st.session_state["df_periodo"]
        st.markdown("**Selecciona qué PDF generar:**")
        col_a, col_b = st.columns(2)
        
        with col_a:
            # PDF de un registro específico
            opciones = [f"{row['fecha']} | {row['finca']} | {row['auditor']}" 
                       for _, row in df.iterrows()]
            seleccionado = st.selectbox("📋 PDF de un registro específico:", opciones, key="sel_registro")
            if st.button("📥 Generar PDF del registro seleccionado"):
                idx_sel = opciones.index(seleccionado)
                rec = _row_to_record(df.iloc[idx_sel].to_dict())
                with st.spinner("Generando PDF…"):
                    pdf = generar_pdf(rec)
                nombre = f"QA_{rec['finca']}_{rec['fecha']}.pdf".replace(" ","_")
                st.download_button("⬇️ Descargar PDF", data=pdf,
                                   file_name=nombre, mime="application/pdf",
                                   use_container_width=True, key="dl_individual")
        
        with col_b:
            # PDF consolidado del periodo
            if st.button("📄 Generar PDF consolidado del periodo"):
                with st.spinner("Generando PDF…"):
                    from pypdf import PdfWriter, PdfReader
                    writer = PdfWriter()
                    for _,row in df.iterrows():
                        rec = _row_to_record(row.to_dict())
                        for page in PdfReader(io.BytesIO(generar_pdf(rec))).pages:
                            writer.add_page(page)
                    out = io.BytesIO(); writer.write(out); pdf_final = out.getvalue()
                nombre = f"QA_Periodo_{fi}_{ff}.pdf".replace(" ","_")
                st.download_button("⬇️ Descargar PDF del periodo", data=pdf_final,
                                   file_name=nombre, mime="application/pdf",
                                   use_container_width=True, key="dl_periodo")

# ═══════════════════════════════════════════
# 🚀  MAIN
# ═══════════════════════════════════════════
def main():
    render_header()
    tab1,tab2 = st.tabs(["📝 Nuevo Checklist","📊 Historial & PDF"])
    with tab1: render_form()
    with tab2: render_dashboard()

if __name__ == "__main__":
    main()
