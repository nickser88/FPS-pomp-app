import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus.flowables import Flowable
from reportlab.lib.utils import ImageReader
import io
import datetime

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(page_title="FPS Pump Test Expert", layout="wide",
                   initial_sidebar_state="expanded")

if 'curves'       not in st.session_state: st.session_state['curves']       = []
if 'pdf_bytes'    not in st.session_state: st.session_state['pdf_bytes']    = None
if 'pdf_filename' not in st.session_state: st.session_state['pdf_filename'] = "rapport.pdf"

st.markdown("""
<style>
.main { background-color: #f5f7f9; }
.stButton>button {
    width: 100%; border-radius: 5px; height: 3em;
    background-color: #004b95; color: white; font-weight: 600;
}
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    import os as _os
    _logo_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                               "FPS_Logo_Wit_fc mailhandtekening.png")
    if _os.path.exists(_logo_path):
        st.image(_logo_path, width=120)
    st.header("Project Details")
    klant        = st.text_input("Customer name",  placeholder="Customer name")
    merk         = st.text_input("Pump Brand",      placeholder="Brand")
    pomp_type    = st.text_input("Type / Model",    placeholder="Type/Model")
    sn           = st.text_input("Serial No",       placeholder="S/N")
    maxpressure  = st.text_input("Max. Pressure",   placeholder="bar")
    maxtemp      = st.text_input("Max. Temp",       placeholder="°C")
    maxspeed     = st.text_input("Max. Speed",      placeholder="RPM")
    vermogen     = st.number_input("Power (kW)", min_value=0.0, step=0.1, format="%.1f")
    seal         = st.text_input("Seal Type",       placeholder="Seal")
    sealfaces    = st.text_input("Seal Faces",      placeholder="xx V xx")
    elastomer    = st.text_input("Elastomer",       placeholder="EPDM,KFM,HNBR,etc")
    displacement = st.text_input("Displacement",    placeholder="x,xx L/rev")
    datum        = st.date_input("Test Date", datetime.date.today())
    operator     = st.text_input("Operator",        placeholder="Name")
    st.divider()
    if st.button("🗑️ Clear all measurements"):
        st.session_state['curves']    = []
        st.session_state['pdf_bytes'] = None
        st.rerun()

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
BRAND_BLUE  = colors.HexColor('#004b95')
BRAND_LIGHT = colors.HexColor('#eaf0fb')
GREY_LINE   = colors.HexColor('#cccccc')
WHITE       = colors.white
TEXT_DARK   = colors.HexColor('#1a1a2e')

# Primaire kleuren voor Flow-curves
COLOR_PALETTE = ['#004b95', '#e63946', '#2a9d8f', '#e9c46a', '#f4a261', '#264653']
# Lichtere varianten voor DHS-curves (zelfde volgorde)
DHS_PALETTE  = ['#6699cc', '#ff8fa3', '#76c7bb', '#f5d98a', '#f9c49a', '#6e8f9e']


def parse_displacement(disp_raw):
    """Parse displacement string naar float (L/rev)."""
    if not disp_raw or not disp_raw.strip():
        return None
    clean = (disp_raw
             .strip()
             .replace(",", ".")
             .lower()
             .replace("l/rev", "")
             .replace("l/omw", "")
             .strip())
    try:
        val = float(clean)
        return val if val > 0 else None
    except ValueError:
        return None


def calc_dhs(curve, V):
    """
    Berekent DHS (hele RPM) voor elk datapunt in de curve.
    V = displacement in L/rev, n = toerental in RPM.
    """
    n = curve['rpm']
    result = []
    for _, row in curve['data'].iterrows():
        q_act_lmin = row['Flow (m³/h)'] * 1000.0 / 60.0   # m³/h → L/min
        q_theo     = V * n                                  # L/min
        dhs        = round((q_theo - q_act_lmin) / V)      # heel getal
        result.append(dhs)
    return result


def fetch_logo_bytes():
    """Laad FPS-logo uit dezelfde map als dit script."""
    import os
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "FPS_Logo_Wit_fc mailhandtekening.png")
    try:
        with open(logo_path, "rb") as f:
            return io.BytesIO(f.read())
    except Exception:
        return None


def build_chart_image(all_curves, displacement_raw=""):
    """
    Matplotlib chart met dubbele Y-as (twinx):
      Links  (blauw)  → Flow (m³/h)  — doorgetrokken lijn met ronde markers
      Rechts (grijs)  → DHS  (RPM)   — gestippelde lijn met vierkante markers
                                        (alleen als displacement beschikbaar is)
    """
    V = parse_displacement(displacement_raw)
    fig_mpl, ax1 = plt.subplots(figsize=(11, 5))
    ax2 = ax1.twinx() if V else None

    for i, curve in enumerate(all_curves):
        col_flow = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        col_dhs  = DHS_PALETTE[i % len(DHS_PALETTE)]
        x = curve['data']["Pressure (bar)"].tolist()
        y = curve['data']["Flow (m³/h)"].tolist()
        n = curve['rpm']

        # Flow op linker Y-as
        ax1.plot(x, y, marker='o', linewidth=2.5, color=col_flow,
                 label=f"{n} RPM – Flow", markersize=7)

        # DHS op rechter Y-as
        if V and ax2 is not None:
            dhs_vals = calc_dhs(curve, V)
            ax2.plot(x, dhs_vals, marker='s', linewidth=2, color=col_dhs,
                     linestyle='--', label=f"{n} RPM – DHS", markersize=6)

    # Linker as opmaak
    ax1.set_xlabel("Pressure (bar)", fontsize=11)
    ax1.set_ylabel("Flow (m³/h)", fontsize=11, color='#004b95')
    ax1.tick_params(axis='y', labelcolor='#004b95')
    ax1.set_title("Pump Performance Curves", fontsize=13, fontweight='bold', color='#004b95')
    ax1.grid(True, linestyle='--', alpha=0.45)
    ax1.set_facecolor('#f9fbff')
    ax1.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax1.xaxis.set_minor_locator(ticker.AutoMinorLocator())

    # Rechter as opmaak
    if V and ax2 is not None:
        ax2.set_ylabel("DHS (RPM)", fontsize=11, color='#888888')
        ax2.tick_params(axis='y', labelcolor='#888888')
        ax2.yaxis.set_minor_locator(ticker.AutoMinorLocator())

    # Gecombineerde legenda
    lines1, labels1 = ax1.get_legend_handles_labels()
    if V and ax2 is not None:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='best')
    else:
        ax1.legend(lines1, labels1, fontsize=9, loc='best')

    fig_mpl.patch.set_facecolor('white')
    plt.tight_layout()
    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig_mpl)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
st.title("💧 Pump Performance Test Certificate")
col1, col2 = st.columns([1, 1.5], gap="large")

with col1:
    st.subheader("1. Measurements")
    actueel_rpm = st.number_input("Speed (RPM)", value=1500, step=50)
    df_init = pd.DataFrame({"Pressure (bar)": [None], "Flow (m³/h)": [None]})
    st.caption("Add rows with the ＋ at the bottom of the table:")
    edited_df = st.data_editor(
        df_init, num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "Pressure (bar)": st.column_config.NumberColumn(format="%.2f"),
            "Flow (m³/h)":    st.column_config.NumberColumn(format="%.2f"),
        }
    )
    if st.button("➕ Add this speed to chart"):
        clean = edited_df.dropna()
        if not clean.empty:
            st.session_state['curves'].append({
                "rpm":  actueel_rpm,
                "data": clean.sort_values("Pressure (bar)")
            })
            st.session_state['pdf_bytes'] = None
            st.success(f"✅ Curve for {actueel_rpm} RPM saved!")
        else:
            st.error("Please enter Pressure and Flow data first.")

with col2:
    st.subheader("2. Pump Curves")

    V_live = parse_displacement(displacement)

    # Dubbele Y-as via Plotly make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for i, curve in enumerate(st.session_state['curves']):
        x        = curve['data']["Pressure (bar)"].tolist()
        y        = curve['data']["Flow (m³/h)"].tolist()
        n        = curve['rpm']
        col_flow = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        col_dhs  = DHS_PALETTE[i % len(DHS_PALETTE)]

        # Flow-curve — linker Y-as
        fig.add_trace(
            go.Scatter(
                x=x, y=y,
                mode='lines+markers',
                name=f"{n} RPM – Flow",
                line=dict(shape='spline', smoothing=0.8, width=3, color=col_flow),
                marker=dict(size=8, color=col_flow),
            ),
            secondary_y=False,
        )

        # DHS-curve — rechter Y-as (alleen als displacement ingevuld)
        if V_live:
            dhs_vals = calc_dhs(curve, V_live)
            fig.add_trace(
                go.Scatter(
                    x=x, y=dhs_vals,
                    mode='lines+markers',
                    name=f"{n} RPM – DHS",
                    line=dict(shape='spline', smoothing=0.8, width=2,
                              color=col_dhs, dash='dash'),
                    marker=dict(size=7, symbol='square', color=col_dhs),
                ),
                secondary_y=True,
            )

    # Live preview huidige invoer (geen DHS)
    live_df = edited_df.dropna()
    if not live_df.empty:
        fig.add_trace(
            go.Scatter(
                x=live_df["Pressure (bar)"], y=live_df["Flow (m³/h)"],
                mode='lines+markers', name="Current input",
                line=dict(dash='dot', color='gray', width=2),
            ),
            secondary_y=False,
        )

    fig.update_xaxes(title_text="Pressure (bar)", gridcolor='lightgray')
    fig.update_yaxes(
        title_text="Flow (m³/h)",
        secondary_y=False,
        gridcolor='lightgray',
        rangemode="tozero",
        title_font=dict(color='#004b95'),
        tickfont=dict(color='#004b95'),
    )
    fig.update_yaxes(
        title_text="DHS (RPM)",
        secondary_y=True,
        rangemode="tozero",
        title_font=dict(color='#888888'),
        tickfont=dict(color='#888888'),
        showgrid=False,
    )
    fig.update_layout(
        height=450,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# PDF GENERATION
# ---------------------------------------------------------------------------
def generate_pdf(all_curves, meta):
    buf = io.BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 15 * mm

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=46*mm, bottomMargin=20*mm
    )

    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    s_section  = style('Section', fontSize=11, fontName='Helvetica-Bold',
                       textColor=colors.HexColor('#000000'), spaceBefore=8, spaceAfter=3)
    s_body     = style('Body',    fontSize=9,  fontName='Helvetica',
                       textColor=TEXT_DARK, leading=13)
    s_cell_hdr = style('CellHdr', fontSize=9,  fontName='Helvetica-Bold',
                       textColor=WHITE, alignment=TA_CENTER)
    s_cell     = style('Cell',    fontSize=9,  fontName='Helvetica',
                       textColor=TEXT_DARK, alignment=TA_CENTER)

    logo_buf = fetch_logo_bytes()

    def draw_header(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#990000'))
        canvas.rect(0, PAGE_H - 38*mm, PAGE_W, 38*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#770000'))
        canvas.rect(0, PAGE_H - 39.5*mm, PAGE_W, 1.5*mm, fill=1, stroke=0)
        if logo_buf:
            logo_buf.seek(0)
            logo_size = 28*mm
            canvas.drawImage(ImageReader(logo_buf),
                             PAGE_W - MARGIN - logo_size, PAGE_H - 36*mm,
                             width=logo_size, height=logo_size,
                             mask='auto', preserveAspectRatio=True)
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(MARGIN, PAGE_H - 18*mm, "Pump Performance Test Certificate")
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#ffd5d5'))
        canvas.drawString(MARGIN, PAGE_H - 25*mm,
            "FPS Pompen B.V.  ·  Tichelerstraat 6, 7202 BC Zutphen  ·  +31 575 218127  ·  info@fps-pompen.nl")
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#ffd5d5'))
        canvas.drawRightString(PAGE_W - MARGIN - 42*mm, PAGE_H - 33*mm,
                               f"Date: {meta.get('Test Date', '')}  |  Page {document.page}")
        canvas.restoreState()

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#faf0f0"))
        canvas.rect(0, 0, PAGE_W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#000000'))
        canvas.rect(0, 14*mm, PAGE_W, 0.5*mm, fill=1, stroke=0)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(MARGIN, 5*mm,
            f"Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  FPS Pump Test App")
        canvas.drawRightString(PAGE_W - MARGIN, 5*mm, f"Page {document.page}")
        canvas.restoreState()

    def on_page(canvas, document):
        draw_header(canvas, document)
        draw_footer(canvas, document)

    def info_table(rows):
        data = [[Paragraph(f"<b>{l}</b>", s_body), Paragraph(str(v), s_body)]
                for l, v in rows]
        t = Table(data, colWidths=[55*mm, 105*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, -1), BRAND_LIGHT),
            ('BACKGROUND',    (1, 0), (1, -1), WHITE),
            ('ROWBACKGROUNDS',(1, 0), (1, -1), [WHITE, colors.HexColor("#fdf7f7")]),
            ('GRID',          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return t

    def section_header(text):
        return [
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#000000'),
                       spaceAfter=2, spaceBefore=8),
            Paragraph(text, s_section),
        ]

    V = parse_displacement(meta.get("Displacement", ""))
    dhs_active = V is not None

    story = []

    # ── 1. PROJECT INFORMATION ───────────────────────────────────────────────
    story += section_header("1.  Project Information")
    story.append(Spacer(1, 4*mm))
    story.append(info_table([
        ("Customer",     meta.get("Customer",     "—")),
        ("Pump",         meta.get("Pump",         "—")),
        ("Serial No",    meta.get("Serial No",    "—")),
        ("Max Pressure", meta.get("Max Pressure", "—") + "  bar"),
        ("Max Temp",     meta.get("Max Temp",     "—") + "  °C"),
        ("Max Speed",    meta.get("Max Speed",    "—") + "  RPM"),
        ("Power",        str(meta.get("Power (kW)", "—")) + "  kW"),
        ("Seal Type",    meta.get("Seal Type",    "—")),
        ("Seal Faces",   meta.get("Seal Faces",   "—")),
        ("Elastomer",    meta.get("Elastomer",    "—")),
        ("Displacement", meta.get("Displacement", "—") + "  L/rev"),
        ("Test Date",    meta.get("Test Date",    "—")),
        ("Operator",     meta.get("Operator",     "—")),
    ]))
    story.append(Spacer(1, 4*mm))

    # ── 2. PERFORMANCE CHART (dubbele Y-as via matplotlib twinx) ────────────
    story += section_header("2.  Performance Chart")
    chart_buf = build_chart_image(all_curves, meta.get("Displacement", ""))
    story.append(RLImage(chart_buf, width=175*mm, height=85*mm))
    story.append(Spacer(1, 3*mm))

    # ── 3. MEASUREMENT DATA ──────────────────────────────────────────────────
    story += section_header("3.  Measurement Data")
    for curve in all_curves:
        story.append(KeepTogether([
            Paragraph(f"<b>Speed: {curve['rpm']} RPM</b>", s_body),
            Spacer(1, 2*mm)
        ]))
        hdr   = [Paragraph("Pressure (bar)", s_cell_hdr),
                 Paragraph("Flow (m³/h)", s_cell_hdr)]
        tdata = [hdr]
        for _, row in curve['data'].iterrows():
            tdata.append([
                Paragraph(f"{row['Pressure (bar)']:.2f}", s_cell),
                Paragraph(f"{row['Flow (m³/h)']:.2f}",   s_cell),
            ])
        mt = Table(tdata, colWidths=[55*mm, 55*mm])
        mt.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#990000')),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRAND_LIGHT, WHITE]),
            ('GRID',          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(KeepTogether([mt, Spacer(1, 3*mm)]))

    # ── 4. SLIP / DHS ANALYSIS (alleen als displacement ingevuld) ────────────
    if dhs_active:
        story += section_header("4.  Slip / DHS Analysis")
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Displacement (V): <b>{meta.get('Displacement', '')} L/rev</b>  |  "
            f"Q<sub>theo</sub> = V \u00d7 n  |  "
            f"Slip = Q<sub>theo</sub> \u2212 Q<sub>act</sub>  |  "
            f"DHS = Slip / V",
            s_body
        ))
        story.append(Spacer(1, 3*mm))

        for curve in all_curves:
            n = curve['rpm']
            story.append(Paragraph(
                f"<b>Speed: {n} RPM  \u2014  "
                f"Q<sub>theo</sub> = {V:.3f} \u00d7 {n} = {V * n:.1f} L/min</b>",
                s_body
            ))
            story.append(Spacer(1, 2*mm))

            hdr = [
                Paragraph("Speed (RPM)",    s_cell_hdr),
                Paragraph("Pressure (bar)", s_cell_hdr),
                Paragraph("Q act (L/min)",  s_cell_hdr),
                Paragraph("DHS (RPM)",      s_cell_hdr),
            ]
            tdata = [hdr]
            for _, row in curve['data'].iterrows():
                pressure   = row['Pressure (bar)']
                q_m3h      = row['Flow (m³/h)']
                q_act_lmin = q_m3h * 1000.0 / 60.0
                dhs        = round((V * n - q_act_lmin) / V)
                tdata.append([
                    Paragraph(f"{n}",              s_cell),
                    Paragraph(f"{pressure:.2f}",   s_cell),
                    Paragraph(f"{q_act_lmin:.1f}", s_cell),
                    Paragraph(f"{dhs}",            s_cell),
                ])

            mt = Table(tdata, colWidths=[40*mm, 40*mm, 45*mm, 45*mm])
            mt.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#990000')),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRAND_LIGHT, WHITE]),
                ('GRID',          (0, 0), (-1, -1), 0.4, GREY_LINE),
                ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(KeepTogether([mt, Spacer(1, 3*mm)]))

    # ── DECLARATION ──────────────────────────────────────────────────────────
    decl_nr = "5" if dhs_active else "4"
    story += section_header(f"{decl_nr}.  Declaration")
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "This test certificate confirms that the above pump was tested under the "
        "conditions stated and that the results are a true and accurate record of "
        "the measurements taken at the specified date.",
        s_body
    ))
    story.append(Spacer(1, 8*mm))
    sig_data = [
        [Paragraph("Tested by:", s_body),
         Paragraph("Signature:", s_body),
         Paragraph("Date:", s_body)],
        [Paragraph(meta.get("Operator", ""), s_body),
         Paragraph("_________________________", s_body),
         Paragraph(meta.get("Test Date", ""), s_body)],
    ]
    sig_table = Table(sig_data, colWidths=[55*mm, 75*mm, 45*mm])
    sig_table.setStyle(TableStyle([
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, GREY_LINE),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# EXPORT SECTION
# ---------------------------------------------------------------------------
st.divider()
st.subheader("3. Report")
c1, c2 = st.columns(2)

with c1:
    if st.button("📄 Generate PDF Report"):
        if not st.session_state['curves']:
            st.error("No saved curves found! Add at least one speed curve first.")
        else:
            meta = {
                "Customer":     klant,
                "Pump":         f"{merk} {pomp_type}".strip(),
                "Serial No":    sn,
                "Max Pressure": maxpressure,
                "Max Temp":     maxtemp,
                "Max Speed":    maxspeed,
                "Power (kW)":   vermogen,
                "Seal Type":    seal,
                "Seal Faces":   sealfaces,
                "Elastomer":    elastomer,
                "Displacement": displacement,
                "Test Date":    str(datum),
                "Operator":     operator,
            }
            with st.spinner("Generating professional PDF…"):
                try:
                    pdf_bytes = generate_pdf(st.session_state['curves'], meta)
                    st.session_state['pdf_bytes']    = pdf_bytes
                    st.session_state['pdf_filename'] = \
                        f"FPS_PumpTest_{klant}_{datum}.pdf".replace(" ", "_")
                    st.success("✅ PDF ready — click Download below!")
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")

    if st.session_state['pdf_bytes']:
        st.download_button(
            label="📥 Download PDF",
            data=st.session_state['pdf_bytes'],
            file_name=st.session_state['pdf_filename'],
            mime="application/pdf",
        )

with c2:
    if st.session_state['curves']:
        export_list = []
        for c in st.session_state['curves']:
            tmp = c['data'].copy()
            tmp['RPM'] = c['rpm']
            export_list.append(tmp)
        full_df = pd.concat(export_list)
        st.download_button(
            "📂 Download CSV data",
            full_df.to_csv(index=False).encode('utf-8'),
            file_name=f"FPS_PumpData_{klant}_{datum}.csv".replace(" ", "_"),
            mime="text/csv"
        )
