"""
SafeDrive AI - Work Order PDF Report Generator
Generates multi-page PDF executive reports for municipal repair work orders using ReportLab.
"""

import os
import sys
import time
import math
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Group, Line
from reportlab.graphics.charts.piecharts import Pie

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

EXPORTS_DIR = os.path.join(BASE_DIR, 'data', 'exports')
os.makedirs(EXPORTS_DIR, exist_ok=True)

def generate_work_order_pdf(work_orders: List[Dict[str, Any]], region: str = "Bangalore") -> str:
    date_str = time.strftime("%Y-%m-%d")
    filename = f"WorkOrders_{region}_{date_str}.pdf"
    pdf_path = os.path.join(EXPORTS_DIR, filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0B0F19')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#008080')
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1F2937')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    story = []

    # Calculate overall stats
    total_budget = sum(wo.get('total_cost', 0.0) for wo in work_orders)
    total_orders = len(work_orders)
    total_hours = sum(wo.get('total_labor_hours', 0.0) for wo in work_orders)
    total_defects = sum(wo.get('defect_count', 0) for wo in work_orders)

    priority_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for wo in work_orders:
        p = wo.get('priority', 'MEDIUM').upper()
        if p in priority_counts:
            priority_counts[p] += 1
        else:
            priority_counts["MEDIUM"] += 1

    # =========================================================================
    # PAGE 1: EXECUTIVE SUMMARY
    # =========================================================================
    story.append(Paragraph("SafeDrive AI — Work Order Executive Report", title_style))
    story.append(Paragraph(f"Region: <b>{region}</b> | Date Generated: <b>{date_str}</b> | System Telemetry: Active", subtitle_style))
    story.append(Spacer(1, 15))

    # Executive Stats Cards Table
    stats_data = [
        [
            Paragraph("<b>TOTAL BUDGET</b>", body_style),
            Paragraph("<b>WORK ORDERS</b>", body_style),
            Paragraph("<b>TOTAL HOURS</b>", body_style),
            Paragraph("<b>DEFECTS COVERED</b>", body_style)
        ],
        [
            Paragraph(f"<font size=14 color='#008080'><b>${total_budget:,.2f}</b></font>", body_style),
            Paragraph(f"<font size=14 color='#111827'><b>{total_orders}</b></font>", body_style),
            Paragraph(f"<font size=14 color='#111827'><b>{total_hours:,.1f} hrs</b></font>", body_style),
            Paragraph(f"<font size=14 color='#EF4444'><b>{total_defects}</b></font>", body_style)
        ]
    ]

    stats_table = Table(stats_data, colWidths=[130, 130, 130, 130])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F3F4F6')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Priority Distribution & Work Order Breakdown", h2_style))
    story.append(Spacer(1, 10))

    # Pie Chart
    pie_drawing = Drawing(520, 160)
    pie = Pie()
    pie.x = 180
    pie.y = 15
    pie.width = 130
    pie.height = 130
    pie.data = [
        priority_counts.get("CRITICAL", 0),
        priority_counts.get("HIGH", 0),
        priority_counts.get("MEDIUM", 0),
        priority_counts.get("LOW", 0)
    ]
    pie.labels = [
        f"Critical ({priority_counts.get('CRITICAL', 0)})",
        f"High ({priority_counts.get('HIGH', 0)})",
        f"Medium ({priority_counts.get('MEDIUM', 0)})",
        f"Low ({priority_counts.get('LOW', 0)})"
    ]
    pie.slices[0].fillColor = colors.HexColor('#EF4444')
    pie.slices[1].fillColor = colors.HexColor('#F59E0B')
    pie.slices[2].fillColor = colors.HexColor('#EAB308')
    pie.slices[3].fillColor = colors.HexColor('#3B82F6')
    pie_drawing.add(pie)
    story.append(pie_drawing)
    story.append(Spacer(1, 15))

    # Executive Summary Table of Work Orders
    summary_headers = [Paragraph("<b>Code</b>", table_header_style), Paragraph("<b>Road Corridor</b>", table_header_style), Paragraph("<b>Priority</b>", table_header_style), Paragraph("<b>Defects</b>", table_header_style), Paragraph("<b>Est. Cost</b>", table_header_style), Paragraph("<b>Hours</b>", table_header_style)]
    summary_rows = [summary_headers]
    for wo in work_orders:
        p = wo.get('priority', 'MEDIUM').upper()
        p_color = '#EF4444' if p == 'CRITICAL' else ('#F59E0B' if p == 'HIGH' else '#3B82F6')
        summary_rows.append([
            Paragraph(f"<b>{wo.get('work_order_code', '')}</b>", body_style),
            Paragraph(wo.get('road_name', ''), body_style),
            Paragraph(f"<font color='{p_color}'><b>{p}</b></font>", body_style),
            Paragraph(str(wo.get('defect_count', 0)), body_style),
            Paragraph(f"${wo.get('total_cost', 0.0):,.2f}", body_style),
            Paragraph(f"{wo.get('total_labor_hours', 0.0):.1f}h", body_style)
        ])

    sum_table = Table(summary_rows, colWidths=[90, 160, 70, 60, 80, 60])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0B0F19')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(sum_table)

    story.append(PageBreak())

    # =========================================================================
    # PAGES 2 to N: INDIVIDUAL WORK ORDER DETAILS (ONE PAGE PER WORK ORDER)
    # =========================================================================
    for idx, wo in enumerate(work_orders, 1):
        wo_code = wo.get('work_order_code', f'WO-2026-{idx:04d}')
        road_name = wo.get('road_name', 'Corridor')
        priority = wo.get('priority', 'MEDIUM').upper()
        cost = wo.get('total_cost', 0.0)
        hours = wo.get('total_labor_hours', 0.0)
        crew_size = wo.get('crew_size', math.ceil(hours / 8.0) or 1)
        crew_name = wo.get('crew_name', f'Crew Team {chr(65 + (idx % 6))}')
        defects_list = wo.get('defects', [])

        story.append(Paragraph(f"Work Order {wo_code} — {road_name}", title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#008080'), spaceBefore=4, spaceAfter=12))

        p_color = '#EF4444' if priority == 'CRITICAL' else ('#F59E0B' if priority == 'HIGH' else '#3B82F6')
        
        meta_data = [
            [
                Paragraph(f"<b>Priority Level:</b> <font color='{p_color}'><b>{priority}</b></font>", body_style),
                Paragraph(f"<b>Total Cost Est:</b> <font color='#10B981'><b>${cost:,.2f}</b></font>", body_style),
                Paragraph(f"<b>Labor Required:</b> <b>{hours:.1f} Hours</b>", body_style)
            ],
            [
                Paragraph(f"<b>Defect Count:</b> <b>{len(defects_list)} items</b>", body_style),
                Paragraph(f"<b>Recommended Crew:</b> <b>{crew_size} Technicians</b>", body_style),
                Paragraph(f"<b>Assigned Crew:</b> <b>{crew_name}</b>", body_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[170, 170, 180])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F3F4F6')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        story.append(Paragraph("Identified Road Defects & Location Inventory", h2_style))
        story.append(Spacer(1, 6))

        defect_headers = [
            Paragraph("<b>Defect ID</b>", table_header_style),
            Paragraph("<b>Type</b>", table_header_style),
            Paragraph("<b>Severity</b>", table_header_style),
            Paragraph("<b>Depth / Dim</b>", table_header_style),
            Paragraph("<b>GPS Coordinates</b>", table_header_style),
            Paragraph("<b>Repair Cost</b>", table_header_style)
        ]
        defect_rows = [defect_headers]

        for d in defects_list[:14]:  # limit to fit nicely on single page
            d_id = d.get('id') or f"DEF-{d.get('raw_id', 0):05d}"
            d_type = (d.get('type') or 'Pothole').capitalize()
            d_sev = d.get('severity', 'Medium')
            d_depth = d.get('depth_cm', 5.0)
            d_w = d.get('width_cm', 30.0)
            d_l = d.get('length_cm', 40.0)
            d_lat = d.get('lat', 12.97)
            d_lng = d.get('lng', 77.59)
            
            from src.analytics.cost_calculator import calculate_defect_cost
            d_cost_val = calculate_defect_cost(d)["repair_cost"]

            sev_color = '#EF4444' if d_sev == 'Critical' else ('#F59E0B' if d_sev == 'High' else '#3B82F6')
            
            defect_rows.append([
                Paragraph(f"<b>{d_id}</b>", body_style),
                Paragraph(d_type, body_style),
                Paragraph(f"<font color='{sev_color}'><b>{d_sev}</b></font>", body_style),
                Paragraph(f"{d_depth}cm ({d_w}x{d_l}cm)", body_style),
                Paragraph(f"{d_lat:.4f}, {d_lng:.4f}", body_style),
                Paragraph(f"${d_cost_val:.2f}", body_style)
            ])

        def_table = Table(defect_rows, colWidths=[80, 75, 75, 110, 110, 70])
        def_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(def_table)
        story.append(Spacer(1, 14))

        story.append(Paragraph("Standard Repair & Safety Instructions", h2_style))
        story.append(Spacer(1, 4))
        instructions_text = (
            "1. Deploy traffic control cones & warning signs 50m upstream prior to excavation.<br/>"
            "2. Clean cavity thoroughly of debris, dust, and standing water.<br/>"
            "3. Apply hot asphalt emulsion tack coat to bottom and vertical edges.<br/>"
            "4. Fill with hot mix asphalt in 50mm lifts and compact using vibratory roller.<br/>"
            "5. Verify smooth surface transition (+/- 2mm tolerance) before reopening lane."
        )
        story.append(Paragraph(instructions_text, body_style))

        story.append(PageBreak())

    # =========================================================================
    # LAST PAGE: METHODOLOGY & DISCLAIMER
    # =========================================================================
    story.append(Paragraph("Methodology & System Disclaimer", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#008080'), spaceBefore=4, spaceAfter=15))

    meth_text = (
        "<b>SafeDrive AI Telemetry & Cost Model Methodology</b><br/>"
        "This work order report was generated automatically by SafeDrive AI's HD Mapping & Predictive Analytics Engine. "
        "Defect locations, severity classifications, and 3D volume approximations are derived from monocular camera telemetry and multi-sensor fusion.<br/><br/>"
        "<b>Cost Estimation Formulae:</b><br/>"
        "• Defect Volume (L): V = (depth_cm × width_cm × length_cm × 0.6) / 1000<br/>"
        "• Asphalt Mass (kg): M = V × 2.4<br/>"
        "• Material Cost ($): Asphalt (kg) × $0.50/kg<br/>"
        "• Labor Cost ($): max(15 min, V × 2 min) × $0.80/min<br/>"
        "• Base Equipment & Mobilization ($): $50.00 fixed rate per site<br/>"
        "• Vehicle Damage Risk ($): P(damage) × Annual Traffic Volume × $150 average claim<br/><br/>"
        "<b>Disclaimer:</b> Field repair crews should conduct site inspection to verify underground utility clearances before heavy excavation."
    )
    story.append(Paragraph(meth_text, body_style))

    doc.build(story)
    print(f"Work Order PDF generated successfully at: {pdf_path}")
    return pdf_path

if __name__ == "__main__":
    from backend.api.defects_db import query_defects
    from src.analytics.cost_calculator import calculate_defect_cost

    defects = query_defects(limit=10000)
    road_groups = {}
    for d in defects:
        r = d.get('road_name') or 'Corridor'
        if r not in road_groups:
            road_groups[r] = []
        road_groups[r].append(d)

    sample_wos = []
    idx = 1
    for road, d_list in road_groups.items():
        total_cost = sum(calculate_defect_cost(d)["repair_cost"] for d in d_list)
        total_labor_min = sum(calculate_defect_cost(d)["labor_min"] for d in d_list)
        total_hours = total_labor_min / 60.0
        
        has_critical = any(d['severity'] == 'Critical' for d in d_list)
        has_high = any(d['severity'] == 'High' for d in d_list)
        priority = "CRITICAL" if has_critical else ("HIGH" if has_high else "MEDIUM")

        sample_wos.append({
            "work_order_code": f"WO-2026-{idx:04d}",
            "road_name": road,
            "defect_count": len(d_list),
            "total_cost": total_cost,
            "total_labor_hours": total_hours,
            "priority": priority,
            "defects": d_list
        })
        idx += 1

    generate_work_order_pdf(sample_wos, "Bangalore")
