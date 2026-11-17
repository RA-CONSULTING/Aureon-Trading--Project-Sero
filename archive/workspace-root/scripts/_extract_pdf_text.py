import PyPDF2, os, glob, json

pdf_dir = r'C:\Users\user\.kimi_openclaw\workspace\zenodo_papers'
results = []

for pdf_file in sorted(glob.glob(os.path.join(pdf_dir, '*.pdf'))):
    try:
        print(f"Reading: {os.path.basename(pdf_file)}")
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except:
                pass
        
        # Save extracted text
        text_file = pdf_file.replace('.pdf', '.txt')
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        results.append({
            'file': os.path.basename(pdf_file),
            'pages': len(reader.pages),
            'chars': len(text),
            'text_file': text_file
        })
        print(f"  Pages: {len(reader.pages)}, Chars: {len(text)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            'file': os.path.basename(pdf_file),
            'error': str(e)
        })

with open(os.path.join(pdf_dir, 'extraction_manifest.json'), 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n=== DONE ===")
print(f"Extracted: {sum(1 for r in results if 'pages' in r)}/{len(results)}")
