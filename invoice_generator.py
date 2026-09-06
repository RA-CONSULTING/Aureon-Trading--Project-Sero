#!/usr/bin/env python3
"""
R&A CONSULTING Invoice Generator
Format: Exact match to Grove Builders CIS invoice benchmark
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_invoice():
    # Image dimensions (landscape, matching the narrow receipt format)
    width, height = 600, 1200
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a monospace font for the table
    try:
        font_large = ImageFont.truetype("arial.ttf", 22)
        font_medium = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # ── COMPANY HEADER ──
    y = 30
    draw.text((30, y), "R&A CONSULTING AND BROKERAGE SERVICES LTD", fill='black', font=font_large)
    y += 35
    draw.text((30, y), "G Leckey R+A Consult", fill='black', font=font_medium)
    y += 28
    draw.text((30, y), "Month to 7/7/26", fill='black', font=font_medium)
    y += 40
    
    # ── TABLE ──
    # Table columns: Pd | Pd | Gross | less CITB | Gross-CITB | less CIS 20% | Nett £
    # From benchmark: 4760, 4480, 9240, 64.68, 9175.32, 1835.06, 7340.26
    
    # Table dimensions
    table_top = y
    col_x = [30, 100, 170, 250, 340, 430, 520]
    col_widths = [65, 65, 75, 85, 85, 90, 80]
    headers = ["Pd", "Pd", "Gross", "less CITB", "Gross-CITB", "less CIS 20%", "Nett £"]
    
    # Draw header row
    row_height = 30
    for i, (header, x) in enumerate(zip(headers, col_x)):
        draw.rectangle([x, table_top, x + col_widths[i], table_top + row_height], outline='black', width=1)
        draw.text((x + 5, table_top + 5), header, fill='black', font=font_small)
    
    # Draw data row
    data_row = ["4760", "4480", "9240", "64.68", "9175.32", "1835.06", "7340.26"]
    y = table_top + row_height
    for i, (val, x) in enumerate(zip(data_row, col_x)):
        draw.rectangle([x, y, x + col_widths[i], y + row_height], outline='black', width=1)
        draw.text((x + 5, y + 5), val, fill='black', font=font_small)
    
    # ── HANDWRITTEN NOTE ──
    y += row_height + 30
    draw.text((30, y), "Please forward an Invoice Before 7 July", fill='black', font=font_medium)
    
    # ── SAVE ──
    output_path = "R_A_CONSULTING_Invoice_2026-07-07.png"
    img.save(output_path)
    print(f"Invoice saved: {output_path}")
    return output_path

if __name__ == "__main__":
    create_invoice()
