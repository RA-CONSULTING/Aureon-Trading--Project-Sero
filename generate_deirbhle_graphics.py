#!/usr/bin/env python3
"""Deirbhle Gallagher Beauty - Promotional Graphics Generator
   Generates branded images matching the pink/elegant aesthetic."""

from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = "C:/Users/user/.kimi_openclaw/workspace/deirbhle_graphics"
os.makedirs(OUT_DIR, exist_ok=True)

# Brand colors
PINK_BG = (240, 210, 220)       # Soft pink background
DARK_PINK = (180, 90, 120)      # Darker pink for headings
GOLD = (210, 170, 100)          # Gold accents
WHITE = (255, 255, 255)
DARK_TEXT = (80, 50, 60)        # Dark brownish text

# Fonts
FONT_DIR = "C:/Windows/Fonts"

def get_font(name, size):
    path = os.path.join(FONT_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# Try elegant fonts
script_font = get_font("Gabriola.ttf", 48)      # Decorative script
script_font_sm = get_font("Gabriola.ttf", 36)
script_font_lg = get_font("Gabriola.ttf", 64)
body_font = get_font("segoeui.ttf", 22)
body_font_sm = get_font("segoeui.ttf", 18)
body_font_lg = get_font("segoeui.ttf", 28)
print_font = get_font("segoepr.ttf", 24)
print_font_sm = get_font("segoepr.ttf", 18)
print_font_lg = get_font("segoepr.ttf", 32)

def draw_gradient_bg(draw, width, height, color1, color2, direction='vertical'):
    """Simple gradient background"""
    for i in range(height if direction == 'vertical' else width):
        ratio = i / (height if direction == 'vertical' else width)
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        if direction == 'vertical':
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, height)], fill=(r, g, b))

def draw_decorative_line(draw, x1, y1, x2, y2, color, width=2):
    """Draw a decorative line with small dots at ends"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    draw.ellipse([x1-4, y1-4, x1+4, y1+4], fill=color)
    draw.ellipse([x2-4, y2-4, x2+4, y2+4], fill=color)

def draw_simple_butterfly(draw, cx, cy, size, color):
    """Draw a simple symmetrical butterfly"""
    # Left wing
    draw.polygon([
        (cx - size//2, cy - size//3),
        (cx - size, cy - size),
        (cx - size//4, cy - size*1.5),
        (cx, cy)
    ], fill=color)
    draw.polygon([
        (cx - size//2, cy + size//3),
        (cx - size, cy + size),
        (cx - size//4, cy + size*1.5),
        (cx, cy)
    ], fill=color)
    # Right wing (mirror)
    draw.polygon([
        (cx + size//2, cy - size//3),
        (cx + size, cy - size),
        (cx + size//4, cy - size*1.5),
        (cx, cy)
    ], fill=color)
    draw.polygon([
        (cx + size//2, cy + size//3),
        (cx + size, cy + size),
        (cx + size//4, cy + size*1.5),
        (cx, cy)
    ], fill=color)
    # Body
    draw.line([(cx, cy - size//2), (cx, cy + size//2)], fill=color, width=3)

def draw_simple_line_face(draw, cx, cy, size, color):
    """Draw a minimalist single-line face silhouette"""
    # Profile outline - simplified
    points = [
        (cx - size//2, cy + size//2),  # chin
        (cx - size//2, cy - size//4),  # jaw
        (cx - size//3, cy - size//2),  # cheek
        (cx, cy - size),                 # forehead
        (cx + size//4, cy - size*0.9),  # top
        (cx + size//3, cy - size//2),   # back of head
        (cx + size//3, cy + size//3),   # neck
    ]
    draw.line(points, fill=color, width=2, joint='curve')
    # Eye (closed, peaceful)
    draw.arc([cx - size//4, cy - size//2, cx, cy - size//3], start=0, end=180, fill=color, width=2)
    # Lips
    draw.arc([cx - size//3, cy - size//8, cx - size//8, cy + size//8], start=0, end=180, fill=color, width=2)

def draw_floral_corner(draw, x, y, size, color, corner='tl'):
    """Draw decorative floral corner element"""
    # Simple flower-like dots
    for i in range(5):
        angle = i * 72
        import math
        rad = math.radians(angle)
        px = x + int(size * 0.3 * math.cos(rad))
        py = y + int(size * 0.3 * math.sin(rad))
        draw.ellipse([px-3, py-3, px+3, py+3], fill=color)
    draw.ellipse([x-5, y-5, x+5, y+5], fill=color)

def create_services_menu():
    """1. Services & Price List"""
    img = Image.new('RGB', (1080, 1350), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    # Subtle gradient overlay
    draw_gradient_bg(draw, 1080, 1350, (240, 210, 220), (235, 200, 215), 'vertical')
    
    # Decorative border
    margin = 40
    draw.rectangle([margin, margin, 1080-margin, 1350-margin], outline=DARK_PINK, width=2)
    draw.rectangle([margin+5, margin+5, 1080-margin-5, 1350-margin-5], outline=GOLD, width=1)
    
    y = 80
    
    # Logo text
    draw.text((540, y), "Deirbhle Gallagher", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    y += 70
    draw.text((540, y), "Beauty", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 50
    
    # Decorative line
    draw_decorative_line(draw, 300, y, 780, y, GOLD, 2)
    y += 30
    
    draw.text((540, y), "BEAUTY THERAPIST / MAKEUP ARTIST", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    y += 60
    
    # Services section
    draw.text((540, y), "Our Services", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 50
    draw_decorative_line(draw, 400, y, 680, y, GOLD, 1)
    y += 40
    
    services = [
        ("Lash Lift & Tint", "€45"),
        ("Brow Lamination", "€40"),
        ("Brow Tint & Wax", "€25"),
        ("Hybrid Lashes", "€55"),
        ("Classic Lashes", "€50"),
        ("Russian Volume", "€65"),
        ("Full Face Makeup", "€50"),
        ("Bridal Makeup", "€85"),
        ("Evening Makeup", "€60"),
        ("Microblading Consultation", "Free"),
    ]
    
    for service, price in services:
        draw.text((200, y), service, font=body_font, fill=DARK_TEXT, anchor="lm")
        # Dotted line
        draw.text((600, y), ". . . . . . . . . . . . . . . . . . .", font=body_font_sm, fill=GOLD)
        draw.text((880, y), price, font=body_font, fill=DARK_PINK, anchor="lm")
        y += 45
    
    y += 20
    draw_decorative_line(draw, 300, y, 780, y, GOLD, 2)
    y += 40
    
    draw.text((540, y), "Gift Vouchers Available", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 40
    draw.text((540, y), "Book your appointment today", font=body_font, fill=DARK_TEXT, anchor="mm")
    y += 30
    draw.text((540, y), "F92 X3XC", font=body_font, fill=DARK_PINK, anchor="mm")
    
    # Butterfly decoration
    draw_simple_butterfly(draw, 540, 1260, 25, DARK_PINK)
    
    img.save(f"{OUT_DIR}/01_services_menu.png")
    print("[OK] 01_services_menu.png created")

def create_book_now_post():
    """2. Instagram 'Book Now' Post"""
    img = Image.new('RGB', (1080, 1080), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    # Gradient
    draw_gradient_bg(draw, 1080, 1080, (240, 210, 220), (230, 190, 210), 'vertical')
    
    # Decorative corners
    draw_floral_corner(draw, 60, 60, 40, DARK_PINK, 'tl')
    draw_floral_corner(draw, 1020, 60, 40, DARK_PINK, 'tr')
    draw_floral_corner(draw, 60, 1020, 40, DARK_PINK, 'bl')
    draw_floral_corner(draw, 1020, 1020, 40, DARK_PINK, 'br')
    
    y = 180
    
    # Enhanced by Deirbhle branding
    draw.text((540, y), "Enhanced", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    y += 60
    draw.text((540, y), "by Deirbhle", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 60
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 50
    
    draw.text((540, y), "Your Beauty Journey", font=print_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 50
    draw.text((540, y), "Starts Here", font=print_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 80
    
    # Features
    features = [
        "✧ Professional Lash Extensions",
        "✧ Expert Brow Sculpting",
        "✧ Luxury Makeup Artistry",
        "✧ Beauty Therapy & Skincare",
    ]
    for feat in features:
        draw.text((540, y), feat, font=body_font, fill=DARK_TEXT, anchor="mm")
        y += 50
    
    y += 30
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 50
    
    # Call to action box
    box_margin = 80
    draw.rectangle([box_margin, y, 1080-box_margin, y+120], fill=(220, 170, 190), outline=GOLD, width=2)
    draw.text((540, y+35), "BOOK YOUR APPOINTMENT", font=body_font_lg, fill=WHITE, anchor="mm")
    draw.text((540, y+85), "DM us or call to secure your slot", font=body_font_sm, fill=WHITE, anchor="mm")
    y += 160
    
    draw.text((540, y), "F92 X3XC", font=body_font, fill=DARK_PINK, anchor="mm")
    y += 40
    draw.text((540, y), "Deirbhle Gallagher Beauty", font=print_font_sm, fill=DARK_TEXT, anchor="mm")
    
    # Simple face silhouette at bottom
    draw_simple_line_face(draw, 540, 980, 60, (200, 160, 180))
    
    img.save(f"{OUT_DIR}/02_book_now_post.png")
    print("[OK] 02_book_now_post.png created")

def create_gift_voucher():
    """3. Gift Voucher Template"""
    img = Image.new('RGB', (1200, 600), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    # Elegant gradient
    draw_gradient_bg(draw, 1200, 600, (240, 210, 220), (220, 180, 200), 'horizontal')
    
    # Ornate border
    margin = 30
    draw.rectangle([margin, margin, 1200-margin, 600-margin], outline=DARK_PINK, width=3)
    draw.rectangle([margin+8, margin+8, 1200-margin-8, 600-margin-8], outline=GOLD, width=2)
    draw.rectangle([margin+16, margin+16, 1200-margin-16, 600-margin-16], outline=DARK_PINK, width=1)
    
    # Left side - brand
    draw.text((300, 120), "Deirbhle", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    draw.text((300, 190), "Gallagher", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    draw.text((300, 250), "Beauty", font=script_font, fill=DARK_PINK, anchor="mm")
    
    draw_decorative_line(draw, 150, 290, 450, 290, GOLD, 2)
    
    draw.text((300, 330), "BEAUTY THERAPIST", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    draw.text((300, 360), "MAKEUP ARTIST", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    
    # Butterfly
    draw_simple_butterfly(draw, 300, 450, 35, DARK_PINK)
    
    # Divider
    draw.line([(600, 80), (600, 520)], fill=GOLD, width=2)
    
    # Right side - voucher details
    draw.text((900, 120), "GIFT VOUCHER", font=body_font_lg, fill=DARK_PINK, anchor="mm")
    draw_decorative_line(draw, 750, 160, 1050, 160, GOLD, 1)
    
    draw.text((900, 210), "This voucher entitles the", font=body_font, fill=DARK_TEXT, anchor="mm")
    draw.text((900, 250), "bearer to beauty services", font=body_font, fill=DARK_TEXT, anchor="mm")
    draw.text((900, 290), "to the value of:", font=body_font, fill=DARK_TEXT, anchor="mm")
    
    # Value box
    draw.rectangle([750, 330, 1050, 430], fill=(240, 220, 230), outline=DARK_PINK, width=2)
    draw.text((900, 380), "€_______", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    
    draw.text((900, 480), "Valid for 12 months from date of issue", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    draw.text((900, 510), "F92 X3XC", font=body_font_sm, fill=DARK_PINK, anchor="mm")
    
    img.save(f"{OUT_DIR}/03_gift_voucher.png")
    print("[OK] 03_gift_voucher.png created")

def create_loyalty_card():
    """4. Loyalty Card - 10 treatments = 1 free"""
    img = Image.new('RGB', (1080, 650), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    draw_gradient_bg(draw, 1080, 650, (240, 210, 220), (225, 195, 210), 'vertical')
    
    margin = 30
    draw.rectangle([margin, margin, 1080-margin, 650-margin], outline=DARK_PINK, width=2)
    
    y = 60
    draw.text((540, y), "Enhanced by Deirbhle", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 50
    draw.text((540, y), "Loyalty Card", font=body_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 40
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 50
    
    draw.text((540, y), "Collect 10 stamps and receive", font=body_font, fill=DARK_TEXT, anchor="mm")
    y += 40
    draw.text((540, y), "your 11th treatment FREE", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 60
    
    # Stamp circles
    start_x = 120
    circle_y = y + 40
    spacing = 90
    for i in range(10):
        cx = start_x + i * spacing
        draw.ellipse([cx-30, circle_y-30, cx+30, circle_y+30], outline=DARK_PINK, width=2)
        draw.text((cx, circle_y), str(i+1), font=body_font_sm, fill=(200, 160, 180), anchor="mm")
    
    y = circle_y + 80
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 40
    
    draw.text((540, y), "F92 X3XC", font=body_font, fill=DARK_PINK, anchor="mm")
    y += 35
    draw.text((540, y), "Deirbhle Gallagher Beauty", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    
    # Small butterfly
    draw_simple_butterfly(draw, 540, 610, 20, GOLD)
    
    img.save(f"{OUT_DIR}/04_loyalty_card.png")
    print("[OK] 04_loyalty_card.png created")

def create_aftercare_card():
    """5. Aftercare Instructions Card"""
    img = Image.new('RGB', (1080, 1400), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    draw_gradient_bg(draw, 1080, 1400, (240, 210, 220), (235, 200, 215), 'vertical')
    
    margin = 50
    draw.rectangle([margin, margin, 1080-margin, 1400-margin], outline=DARK_PINK, width=2)
    draw.rectangle([margin+5, margin+5, 1080-margin-5, 1400-margin-5], outline=GOLD, width=1)
    
    y = 80
    draw.text((540, y), "Enhanced by Deirbhle", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 55
    draw.text((540, y), "Aftercare Guide", font=body_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 50
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 60
    
    # Lash extension aftercare
    draw.text((540, y), "Lash Extension Aftercare", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 55
    
    lash_tips = [
        "Avoid water and steam for the first 24-48 hours",
        "Do not use oil-based products near your lashes",
        "Brush lashes daily with a clean spoolie",
        "Avoid rubbing, pulling, or sleeping face-down",
        "Book infills every 2-3 weeks for best results",
    ]
    for tip in lash_tips:
        draw.text((120, y), "◆", font=body_font, fill=GOLD, anchor="lm")
        draw.text((160, y), tip, font=body_font, fill=DARK_TEXT, anchor="lm")
        y += 50
    
    y += 30
    draw_decorative_line(draw, 300, y, 780, y, GOLD, 1)
    y += 50
    
    # Brow lamination aftercare
    draw.text((540, y), "Brow Lamination Aftercare", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 55
    
    brow_tips = [
        "Keep brows dry for the first 24 hours",
        "Avoid makeup and skincare products on brows for 24h",
        "Do not rub or touch the brow area excessively",
        "Apply nourishing oil after 24 hours to condition",
    ]
    for tip in brow_tips:
        draw.text((120, y), "◆", font=body_font, fill=GOLD, anchor="lm")
        draw.text((160, y), tip, font=body_font, fill=DARK_TEXT, anchor="lm")
        y += 50
    
    y += 30
    draw_decorative_line(draw, 300, y, 780, y, GOLD, 1)
    y += 50
    
    # General
    draw.text((540, y), "General Tips", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 55
    
    general_tips = [
        "Always patch test 48 hours before new treatments",
        "Stay hydrated for healthier skin and lashes",
        "Follow your therapist's personalised advice",
        "Questions? Message us anytime — we're here to help",
    ]
    for tip in general_tips:
        draw.text((120, y), "◆", font=body_font, fill=GOLD, anchor="lm")
        draw.text((160, y), tip, font=body_font, fill=DARK_TEXT, anchor="lm")
        y += 50
    
    y += 40
    draw.text((540, y), "Thank you for choosing Deirbhle Gallagher Beauty", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    y += 35
    draw.text((540, y), "F92 X3XC", font=body_font, fill=DARK_PINK, anchor="mm")
    
    # Butterfly at bottom
    draw_simple_butterfly(draw, 540, 1350, 25, DARK_PINK)
    
    img.save(f"{OUT_DIR}/05_aftercare_card.png")
    print("[OK] 05_aftercare_card.png created")

def create_business_card():
    """6. Business Card (front and back concept)"""
    # Front
    img = Image.new('RGB', (1050, 600), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    draw_gradient_bg(draw, 1050, 600, (240, 210, 220), (230, 195, 210), 'horizontal')
    
    # Center text
    draw.text((525, 200), "Deirbhle Gallagher", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    draw.text((525, 270), "Beauty", font=script_font, fill=DARK_PINK, anchor="mm")
    
    draw_decorative_line(draw, 325, 320, 725, 320, GOLD, 2)
    
    draw.text((525, 360), "BEAUTY THERAPIST / MAKEUP ARTIST", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    
    # Butterfly accent
    draw_simple_butterfly(draw, 525, 450, 30, DARK_PINK)
    
    draw.text((525, 520), "F92 X3XC", font=body_font_sm, fill=DARK_PINK, anchor="mm")
    
    img.save(f"{OUT_DIR}/06a_business_card_front.png")
    print("[OK] 06a_business_card_front.png created")
    
    # Back
    img2 = Image.new('RGB', (1050, 600), PINK_BG)
    draw2 = ImageDraw.Draw(img2)
    
    draw_gradient_bg(draw2, 1050, 600, (240, 210, 220), (230, 195, 210), 'horizontal')
    
    draw2.text((525, 120), "Enhanced by Deirbhle", font=script_font, fill=DARK_PINK, anchor="mm")
    
    draw_decorative_line(draw2, 325, 170, 725, 170, GOLD, 2)
    
    y = 230
    details = [
        "Lash Extensions & Lifts",
        "Brow Lamination & Sculpting",
        "Professional Makeup Artistry",
        "Beauty Therapy & Skincare",
        "Gift Vouchers Available",
    ]
    for detail in details:
        draw2.text((525, y), detail, font=body_font, fill=DARK_TEXT, anchor="mm")
        y += 45
    
    y += 20
    draw2.text((525, y), "F92 X3XC", font=body_font_lg, fill=DARK_PINK, anchor="mm")
    y += 50
    draw2.text((525, y), "Book your appointment today", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    
    # Small butterfly
    draw_simple_butterfly(draw2, 525, 540, 20, GOLD)
    
    img2.save(f"{OUT_DIR}/06b_business_card_back.png")
    print("[OK] 06b_business_card_back.png created")

def create_welcome_story():
    """7. Instagram Story - Welcome"""
    img = Image.new('RGB', (1080, 1920), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    # Vertical gradient
    draw_gradient_bg(draw, 1080, 1920, (240, 210, 220), (220, 185, 205), 'vertical')
    
    # Top decoration
    draw_floral_corner(draw, 50, 50, 50, DARK_PINK, 'tl')
    draw_floral_corner(draw, 1030, 50, 50, DARK_PINK, 'tr')
    
    y = 300
    draw.text((540, y), "Welcome to", font=print_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 80
    
    draw.text((540, y), "Enhanced", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    y += 70
    draw.text((540, y), "by Deirbhle", font=script_font, fill=DARK_PINK, anchor="mm")
    y += 80
    
    draw_decorative_line(draw, 300, y, 780, y, GOLD, 3)
    y += 60
    
    draw.text((540, y), "Where Beauty Meets Artistry", font=body_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 80
    
    # Features with bullet points
    features = [
        "Lash Extensions & Lifts",
        "Brow Lamination & Tinting",
        "Professional Makeup",
        "Beauty Therapy",
    ]
    for feat in features:
        draw.text((540, y), "✧  " + feat + "  ✧", font=body_font, fill=DARK_TEXT, anchor="mm")
        y += 60
    
    y += 60
    
    # CTA button area
    draw.rectangle([200, y, 880, y+120], fill=(210, 150, 180), outline=GOLD, width=3)
    draw.text((540, y+40), "BOOK NOW", font=body_font_lg, fill=WHITE, anchor="mm")
    draw.text((540, y+85), "F92 X3XC", font=body_font, fill=WHITE, anchor="mm")
    y += 180
    
    draw.text((540, y), "Follow us for updates & offers", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    y += 50
    draw.text((540, y), "@enhancedbydeirbhle", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    
    # Bottom decoration
    draw_floral_corner(draw, 50, 1870, 50, DARK_PINK, 'bl')
    draw_floral_corner(draw, 1030, 1870, 50, DARK_PINK, 'br')
    
    # Center butterfly
    draw_simple_butterfly(draw, 540, 1750, 40, DARK_PINK)
    
    img.save(f"{OUT_DIR}/07_welcome_story.png")
    print("[OK] 07_welcome_story.png created")

def create_thank_you_card():
    """8. Thank You Card for clients"""
    img = Image.new('RGB', (1080, 1080), PINK_BG)
    draw = ImageDraw.Draw(img)
    
    draw_gradient_bg(draw, 1080, 1080, (240, 210, 220), (235, 205, 218), 'vertical')
    
    # Ornate border
    margin = 60
    draw.rectangle([margin, margin, 1080-margin, 1080-margin], outline=DARK_PINK, width=2)
    draw.rectangle([margin+8, margin+8, 1080-margin-8, 1080-margin-8], outline=GOLD, width=1)
    
    # Corner flourishes
    draw_floral_corner(draw, 90, 90, 35, DARK_PINK, 'tl')
    draw_floral_corner(draw, 990, 90, 35, DARK_PINK, 'tr')
    draw_floral_corner(draw, 90, 990, 35, DARK_PINK, 'bl')
    draw_floral_corner(draw, 990, 990, 35, DARK_PINK, 'br')
    
    y = 200
    draw.text((540, y), "Thank You", font=script_font_lg, fill=DARK_PINK, anchor="mm")
    y += 80
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 60
    
    draw.text((540, y), "For choosing", font=body_font_lg, fill=DARK_TEXT, anchor="mm")
    y += 55
    draw.text((540, y), "Deirbhle Gallagher Beauty", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 80
    
    draw.text((540, y), "It was a pleasure having you", font=body_font, fill=DARK_TEXT, anchor="mm")
    y += 45
    draw.text((540, y), "We can't wait to see you again", font=body_font, fill=DARK_TEXT, anchor="mm")
    y += 80
    
    draw_decorative_line(draw, 340, y, 740, y, GOLD, 2)
    y += 60
    
    draw.text((540, y), "Don't forget to tag us", font=body_font, fill=DARK_TEXT, anchor="mm")
    y += 45
    draw.text((540, y), "@enhancedbydeirbhle", font=print_font_lg, fill=DARK_PINK, anchor="mm")
    y += 60
    
    draw.text((540, y), "Leave us a review — your feedback means the world", font=body_font_sm, fill=DARK_TEXT, anchor="mm")
    y += 50
    
    draw.text((540, y), "F92 X3XC", font=body_font, fill=DARK_PINK, anchor="mm")
    
    # Center butterfly below text
    draw_simple_butterfly(draw, 540, 850, 35, GOLD)
    
    img.save(f"{OUT_DIR}/08_thank_you_card.png")
    print("[OK] 08_thank_you_card.png created")

if __name__ == "__main__":
    print("=" * 50)
    print("Deirbhle Gallagher Beauty - Graphics Generator")
    print("=" * 50)
    create_services_menu()
    create_book_now_post()
    create_gift_voucher()
    create_loyalty_card()
    create_aftercare_card()
    create_business_card()
    create_welcome_story()
    create_thank_you_card()
    print("=" * 50)
    print(f"All images saved to: {OUT_DIR}")
    print("=" * 50)
