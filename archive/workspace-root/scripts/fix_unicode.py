with open('generate_deirbhle_graphics.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('print("✓', 'print("[OK]')

with open('generate_deirbhle_graphics.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
