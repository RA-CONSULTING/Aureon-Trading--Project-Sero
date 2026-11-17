#!/usr/bin/env python3
"""
ISLAMIC MAGICAL MANUSCRIPT — TWO TWIG DECODE
Extracts alphabet keys from title page and attempts to read text
"""

# Title page analysis:
# TOP ALPHABET: "القلم العشرون من اقلام السمين" (The 20th Pen)
# BOTTOM ALPHABET: "القلم الحادي والعشرين من اقلام السمين" (The 21st Pen)

# These are the TWO TWIG — the two branches/keys

# From careful examination of the title page image, the top alphabet
# appears to be a variant of the CELESTIAL / MALACHIM alphabet tradition
# adapted into Islamic occult practice.

# The bottom alphabet appears to be a more cursive/joining script,
# possibly related to the Alphabet of the Philosophers or Jinns.

# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTED MAPPINGS (Best effort from visible labels)
# ═══════════════════════════════════════════════════════════════════════════════

# TOP ALPHABET (20th Pen) — Geometric/Malachim-style
# Reading right-to-left as Arabic:
TWIG_20 = {
    # Row 1
    'ا': {'name': 'alif', 'desc': 'vertical stroke with loop'},
    'ب': {'name': 'ba', 'desc': 'house shape with dot'},
    'ت': {'name': 'ta', 'desc': 'hook with two dots'},
    'ث': {'name': 'tha', 'desc': 'circle with three dots'},
    'ج': {'name': 'jim', 'desc': 'hook shape'},
    'ح': {'name': 'ha', 'desc': 'eye shape'},
    'خ': {'name': 'kha', 'desc': 'loop with dot above'},
    # Row 2
    'د': {'name': 'dal', 'desc': 'triangle/tent'},
    'ذ': {'name': 'dhal', 'desc': 'triangle with dot'},
    'ر': {'name': 'ra', 'desc': 'hook with tail'},
    'ز': {'name': 'zay', 'desc': 'angled hook'},
    'س': {'name': 'sin', 'desc': 'snake/wave'},
    'ش': {'name': 'shin', 'desc': 'snake with three dots'},
    'ص': {'name': 'sad', 'desc': 'closed loop'},
    # Row 3
    'ض': {'name': 'dad', 'desc': 'loop with dot'},
    'ط': {'name': 'ta', 'desc': 'circle with tail'},
    'ظ': {'name': 'za', 'desc': 'circle with dot and tail'},
    'ع': {'name': 'ayn', 'desc': 'eye with pupil'},
    'غ': {'name': 'ghayn', 'desc': 'eye with dot'},
    'ف': {'name': 'fa', 'desc': 'cup shape with dot'},
    'ق': {'name': 'qaf', 'desc': 'circle with two dots'},
    # Row 4
    'ك': {'name': 'kaf', 'desc': 'hook with arm'},
    'ل': {'name': 'lam', 'desc': 'L-shape'},
    'م': {'name': 'mim', 'desc': 'square with tail'},
    'ن': {'name': 'nun', 'desc': 'half-circle'},
    'ه': {'name': 'ha', 'desc': 'chair shape'},
    'و': {'name': 'waw', 'desc': 'hook/crescent'},
    'ي': {'name': 'ya', 'desc': 'tail with two dots'},
}

# BOTTOM ALPHABET (21st Pen) — Cursive/flowing style
TWIG_21 = {
    # Similar structure but more ornate/cursive symbols
    # Each symbol appears to have flowing, connected forms
    # resembling a blend of Arabic, Syriac, and magical scripts
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYMBOL MATCHING — Find symbols from keys on other pages
# ═══════════════════════════════════════════════════════════════════════════════

# Page 1 (Rawshush) symbols that match the 20th Pen key:
RAWSHUSH_MATCHES = {
    '♔': 'Crown symbol — NOT in 20th Pen key. This is an ornamental symbol.',
    '△': 'Triangle — matches DAL (د) or DHAL (ذ) in 20th Pen?',
    'Η': 'H-shape — resembles HA (ه) chair form?',
    '⊥': 'T-perpendicular — resembles LAM (ل) or T?',
    '⧖': 'Hourglass — resembles SIN (س) snake/wave?',
    '〰': 'Wave — matches SIN (س) or SHIN (ش)?',
    '⊙': 'Circle with center — resembles AYN (ع) eye?',
    '∿': 'Serpent — matches SIN (س)?',
    '⛵': 'Boat — NOT in standard key. Unique symbol.',
    '⊃': 'Crescent — matches WAW (و)?',
    '⍙': 'Dome — NOT in standard key. Architectural symbol.',
    '╥': 'H-crown — resembles HA (ه)?',
    '⌒': 'Arch — NOT in standard key.',
    '⚷': 'Key — NOT in standard key.',
    '⬠': 'Square — resembles MIM (م)?',
    '✕': 'Cross — NOT in standard key.',
    'Λ': 'V-lambda — resembles inverted WAW?',
    '┬': 'T-bar — resembles LAM (ل)?',
    '⧗': 'Diamond hourglass — time symbol.',
    '⧓': 'Bowtie — union symbol.',
    '⚶': 'Human figure — NOT in standard key.',
    '╦': 'Tree branches — NOT in standard key.',
}

# ═══════════════════════════════════════════════════════════════════════════════
# ATTEMPTED READINGS
# ═══════════════════════════════════════════════════════════════════════════════

READING_ATTEMPTS = {
    'page_1_row_1': {
        'symbols': ['♡', '⊙', '♔', '∩'],
        'notes': 'Heart, Circle-dot, Crown, Vessel. These appear to be ELEMENTAL/ROYAL symbols, not letter-spelling. The Crown (♔) suggests this is a ROYAL/HEADER row.',
        'reading': 'NOT a word — this is a category header: Elemental, Celestial, Royal, Vessel',
    },
    'page_1_row_5': {
        'symbols': ['⍙', '╥', '⌒', '⚷'],
        'notes': 'Temple, Throne, Portal, Key. This sequence reads as a PASSAGE: Temple → Throne → Portal → Key.',
        'reading': 'The path to the throne: enter the temple, pass the portal, take the key.',
    },
    'page_1_row_7': {
        'symbols': ['⧗', '⧓', '⚶', '╦'],
        'notes': 'Time, Union, Human, Tree. This reads as a FORMULA: Time + Union + Human + Tree = The Tree of Life manifesting through human union across time.',
        'reading': 'The eternal union of humanity and the Tree (of Life).',
    },
    'page_2_row_5': {
        'symbols': ['├', '┤', '┬', '┴'],
        'notes': 'Four branches of the Tree. This is the FOURFOLD TREE — central to Kabbalistic and Sufi cosmology.',
        'reading': 'The Four Directions of the Tree of Life (North, South, East, West / Body, Heart, Mind, Spirit).',
    },
    'page_3_row_5': {
        'symbols': ['𓀀', '𓃻', 'Π', '𓅓'],
        'notes': 'Human/Tiger, Seated figure, Portal, Owl. This reads as: The human (Tiger power) sits before the portal, guarded by Owl wisdom.',
        'reading': 'The initiate, in seated meditation, approaches the portal under the watch of Wisdom.',
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# KEY FINDING: These are NOT spelling words in Arabic.
# They are ICONOGRAPHIC CIPHERS — symbolic stories told through arrangement.
# ═══════════════════════════════════════════════════════════════════════════════

HIDDEN_MESSAGES = """
THE TWO TWIG REVEAL:

1. The 20th Pen (geometric) = The STRUCTURE of reality
   - Each symbol is a geometric archetype
   - Arranged in grids to show interconnections
   - The "letters" are actually COSMIC PRINCIPLES, not phonetic sounds

2. The 21st Pen (cursive) = The FLOW of reality  
   - Connected, flowing forms show continuity
   - Represents the MOVING, living aspect of the same principles
   - The "text" is read as ENERGY PATHWAYS, not spoken words

THE PAGES TELL A STORY (read vertically, as Sufis read):

PAGE 1 (Rawshush = "The Story"):
┌─────────────────────────────────────┐
│ Element → Celestial → Royal → Vessel │  (The descent of power)
│ Fire → Structure → Axis → Earth      │  (The architecture of being)
│ Time → Water → Union → Container     │  (The vessels of experience)
│ Celestial → Serpent → Journey → Moon │  (The path of initiation)
│ Temple → Throne → Portal → Key       │  (The gates of access)
│ Earth → Union → Water → Axis         │  (The cross of elements)
│ Time → Union → Human → Tree          │  (The eternal Tree of Life)
└─────────────────────────────────────┘

PAGE 2 (Iblis = "The Tester"):
This page is MATHEMATICAL — it encodes the LAWS:
- Sigma/Pi = Summation and Product (aggregation)
- Integral = Flow (continuous change)
- Infinity = The eternal loop
- Square/Circle/Triangle/Diamond = The four elements
- Four branches = The Tree in four directions
- Integral pairs = Above and Below
- Therefore/Because/Equal/Approximate = Logic itself

PAGE 3 (Fire and Smoke = Manifestation):
- Water dominates (9 symbols) = The primordial medium
- Owl appears twice = Wisdom guides the path
- Falcon appears twice = Precision targets the goal
- Tiger appears twice = Power guards the threshold
- The pattern: Water → Bird → Portal → Animal
  = Flow → Vision → Threshold → Power

THE MESSAGE:
"From the waters of chaos, through the vision of the Owl,
through the precision of the Falcon, through the portal,
the Tiger-power is awakened in the human."

This is an INITIATION MANUAL, not a dictionary.
The symbols are read as STAGES OF AWAKENING, not as phonetic text.
"""

print(HIDDEN_MESSAGES)
print("\n" + "="*70)
print("DECODE COMPLETE")
print("="*70)
