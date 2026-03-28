import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
import urllib.request
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
    fig = go.Figure()
    for curve in st.session_state['curves']:
        fig.add_trace(go.Scatter(
            x=curve['data']["Pressure (bar)"],
            y=curve['data']["Flow (m³/h)"],
            mode='lines+markers',
            name=f"{curve['rpm']} RPM",
            line=dict(shape='spline', smoothing=0.8, width=3)
        ))
    live_df = edited_df.dropna()
    if not live_df.empty:
        fig.add_trace(go.Scatter(
            x=live_df["Pressure (bar)"], y=live_df["Flow (m³/h)"],
            mode='lines+markers', name="Current input",
            line=dict(dash='dash', color='gray')
        ))
    fig.update_layout(
        xaxis=dict(title="Pressure (bar)", gridcolor='lightgray'),
        yaxis=dict(title="Flow (m³/h)", gridcolor='lightgray', rangemode="tozero"),
        height=450, template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
BRAND_BLUE  = colors.HexColor('#004b95')
BRAND_LIGHT = colors.HexColor('#eaf0fb')
GREY_LINE   = colors.HexColor('#cccccc')
WHITE       = colors.white
TEXT_DARK   = colors.HexColor('#1a1a2e')

COLOR_PALETTE = ['#004b95', '#e63946', '#2a9d8f', '#e9c46a', '#f4a261', '#264653']


def fetch_logo_bytes():
    """Load FPS logo from local folder (same directory as this script)."""
    import os
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "FPS_Logo_Wit_fc mailhandtekening.png")
    try:
        with open(logo_path, "rb") as f:
            return io.BytesIO(f.read())
    except Exception:
        return None


def build_chart_image(all_curves):
    """Render pump curves with matplotlib → PNG bytes (no kaleido)."""
    fig_mpl, ax = plt.subplots(figsize=(11, 5))
    for i, curve in enumerate(all_curves):
        col = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        x = curve['data']["Pressure (bar)"].tolist()
        y = curve['data']["Flow (m³/h)"].tolist()
        ax.plot(x, y, marker='o', linewidth=2.5, color=col,
                label=f"{curve['rpm']} RPM", markersize=7)
    ax.set_xlabel("Pressure (bar)", fontsize=11)
    ax.set_ylabel("Flow (m³/h)", fontsize=11)
    ax.set_title("Pump Performance Curves", fontsize=13, fontweight='bold', color='#004b95')
    ax.legend(fontsize=9, loc='best')
    ax.grid(True, linestyle='--', alpha=0.45)
    ax.set_facecolor('#f9fbff')
    fig_mpl.patch.set_facecolor('white')
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    plt.tight_layout()
    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig_mpl)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# DISPLACEMENT PARSER HELPER
# ---------------------------------------------------------------------------
def parse_displacement(disp_raw):
    """
    Parse displacement string to float (L/rev).
    Accepts formats like: "0,58", "0.58", "0,58 L/rev", "0.58l/rev"
    Returns float or None if parsing fails.
    """
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
        topMargin=46*mm,
        bottomMargin=20*mm
    )

    # ── STYLES ──────────────────────────────────────────────────────────────
    S = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    s_doc_title = style('DocTitle', fontSize=15, fontName='Helvetica-Bold',
                        textColor=WHITE, alignment=TA_LEFT, leading=18)
    s_doc_sub   = style('DocSub',   fontSize=9,  fontName='Helvetica',
                        textColor=colors.HexColor('#cce0ff'), alignment=TA_LEFT)
    s_section   = style('Section',  fontSize=11, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#000000'), spaceBefore=8, spaceAfter=3,
                        borderPad=2)
    s_body      = style('Body',     fontSize=9,  fontName='Helvetica',
                        textColor=TEXT_DARK, leading=13)
    s_footer    = style('Footer',   fontSize=7.5, fontName='Helvetica',
                        textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
    s_cell_hdr  = style('CellHdr',  fontSize=9,  fontName='Helvetica-Bold',
                        textColor=WHITE, alignment=TA_CENTER)
    s_cell      = style('Cell',     fontSize=9,  fontName='Helvetica',
                        textColor=TEXT_DARK, alignment=TA_CENTER)

    # ── HEADER / FOOTER CALLBACKS ────────────────────────────────────────────
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
            canvas.drawImage(
                ImageReader(logo_buf),
                PAGE_W - MARGIN - logo_size,
                PAGE_H - 36*mm,
                width=logo_size, height=logo_size,
                mask='auto', preserveAspectRatio=True
            )

        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(MARGIN, PAGE_H - 18*mm, "Pump Performance Test Certificate")
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#ffd5d5'))
        canvas.drawString(MARGIN, PAGE_H - 25*mm,
            "FPS Pompen B.V.  ·  Tichelerstraat 6, 7202 BC Zutphen  ·  +31 575 218127  ·  info@fps-pompen.nl")

        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#ffd5d5'))
        doc_date = meta.get("Test Date", "")
        canvas.drawRightString(PAGE_W - MARGIN - 42*mm, PAGE_H - 33*mm,
                               f"Date: {doc_date}  |  Page {document.page}")
        canvas.restoreState()

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#f0f4fa'))
        canvas.rect(0, 0, PAGE_W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#000000'))
        canvas.rect(0, 14*mm, PAGE_W, 0.5*mm, fill=1, stroke=0)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(MARGIN, 5*mm,
            f"Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  FPS Pump Test App  ·  ")
        canvas.drawRightString(PAGE_W - MARGIN, 5*mm,
            f"Page {document.page}")
        canvas.restoreState()

    def on_page(canvas, document):
        draw_header(canvas, document)
        draw_footer(canvas, document)

    # ── HELPER: two-column info table ───────────────────────────────────────
    def info_table(rows):
        data = []
        for label, value in rows:
            data.append([
                Paragraph(f"<b>{label}</b>", s_body),
                Paragraph(str(value), s_body)
            ])
        t = Table(data, colWidths=[55*mm, 105*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, -1), BRAND_LIGHT),
            ('BACKGROUND',    (1, 0), (1, -1), WHITE),
            ('ROWBACKGROUNDS',(1, 0), (1, -1), [WHITE, colors.HexColor('#f7f9fd')]),
            ('GRID',          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROUNDEDCORNERS',(0, 0), (-1, -1), 3),
        ]))
        return t

    def section_header(text):
        return [
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#000000'),
                       spaceAfter=2, spaceBefore=8),
            Paragraph(text, s_section),
        ]

    # ── Bepaal of DHS sectie actief is ──────────────────────────────────────
    V = parse_displacement(meta.get("Displacement", ""))
    dhs_active = V is not None  # True → extra sectie + Declaration wordt §5

    # ── BUILD STORY ─────────────────────────────────────────────────────────
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
        ("Displacement", meta.get("Displacement", "—")),
        ("Test Date",    meta.get("Test Date",    "—")),
        ("Operator",     meta.get("Operator",     "—")),
    ]))
    story.append(Spacer(1, 4*mm))

    # ── 2. PERFORMANCE CHART ─────────────────────────────────────────────────
    story += section_header("2.  Performance Chart")
    chart_buf = build_chart_image(all_curves)
    story.append(RLImage(chart_buf, width=175*mm, height=85*mm))
    story.append(Spacer(1, 3*mm))

    # ── 3. MEASUREMENT DATA ──────────────────────────────────────────────────
    story += section_header("3.  Measurement Data")

    for curve in all_curves:
        rpm_label = Paragraph(f"<b>Speed: {curve['rpm']} RPM</b>", s_body)
        story.append(KeepTogether([rpm_label, Spacer(1, 2*mm)]))

        hdr = [Paragraph("Pressure (bar)", s_cell_hdr),
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

    # ── 4. SLIP / DHS ANALYSIS (alleen als displacement ingevuld is) ─────────
    if dhs_active:
        story += section_header("4.  Slip / DHS Analysis")
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Displacement (V): <b>{meta.get('Displacement', '')} </b>  |  "
            f"Q<sub>theo</sub> = V \u00d7 n  |  "
            f"Slip = Q<sub>theo</sub> \u2212 Q<sub>act</sub>  |  "
            f"DHS = Slip / V",
            s_body
        ))
        story.append(Spacer(1, 3*mm))

        for curve in all_curves:
            n = curve['rpm']  # RPM

            rpm_label = Paragraph(f"<b>Speed: {n} RPM  \u2014  "
                                  f"Q<sub>theo</sub> = {V:.3f} \u00d7 {n} = "
                                  f"{V * n:.1f} L/min</b>", s_body)
            story.append(rpm_label)
            story.append(Spacer(1, 2*mm))

            # Tabelheader
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
                q_act_lmin = q_m3h * 1000.0 / 60.0   # m³/h → L/min
                q_theo     = V * n                    # L/min (constant per curve)
                slip       = q_theo - q_act_lmin      # L/min
                dhs        = slip / V                 # RPM

                tdata.append([
                    Paragraph(f"{n}",              s_cell),
                    Paragraph(f"{pressure:.2f}",   s_cell),
                    Paragraph(f"{q_act_lmin:.1f}", s_cell),
                    Paragraph(f"{dhs:.1f}",        s_cell),
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

    # ── DECLARATION: §4 zonder DHS, §5 met DHS ───────────────────────────────
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

    # ── BUILD ─────────────────────────────────────────────────────────────────
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
