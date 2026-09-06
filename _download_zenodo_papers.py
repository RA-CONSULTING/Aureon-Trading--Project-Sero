import requests, os, re, json, time
from urllib.parse import urljoin

# DOIs from ORCID profile
papers = [
    {"doi": "10.5281/zenodo.17546501", "title": "The Harmonic Nexus Core (HNC): A Unified Framework for Emergent Spacetime and Coherent Information Dynamics", "date": "2025-07-13"},
    {"doi": "10.5281/zenodo.17548802", "title": "Electro-Plasma-Acoustic Shield (EPAS): A Multi-Layer Active Defense System for Spacecraft Protection", "date": "2025"},
    {"doi": "10.5281/zenodo.17527831", "title": "Harmonic Reality Framework and the Master Equations Tree", "date": "2025"},
    {"doi": "10.5281/zenodo.17529232", "title": "Modeling Light Dynamics Through Astronomical Phenomena", "date": "2025"},
    {"doi": "10.5281/zenodo.17531249", "title": "Quantum Gravity in the Act (QGITA): A Two-Stage Consensus Framework for Detecting Structural Events in Complex Signals", "date": "2025"},
    {"doi": "10.5281/zenodo.17531133", "title": "Quantum Gravity in the Act (QGITA): A Two-Stage Framework for High-Fidelity Event Detection in Complex Signals", "date": "2025"},
    {"doi": "10.5281/zenodo.17546276", "title": "Tandem in Unity: Unifying Resonant Fields in Physics, AI, and Consciousness", "date": "2025"},
    {"doi": "10.5281/zenodo.17529246", "title": "The Barons' Banner: The Hidden Architecture of Mathematical Deception", "date": "2025"},
    {"doi": "10.5281/zenodo.17546413", "title": "The Harmonic Nexus Core and Auris Conjecture: A Unified Framework for Emergent Spacetime, Symbolic Cognition, and Field-Consciousness Interaction", "date": "2025"},
    {"doi": "10.5281/zenodo.17573586", "title": "The LuminaCell v2 Architecture: A High-Power Coherent Light Source Based on a Contactless Quantum Interference Core", "date": "2025"},
    {"doi": "10.5281/zenodo.17531331", "title": "The Math Angel Protocol: A Mathematical Framework for Quantifying and Visualizing Consciousness as the Fundamental Substrate of Reality", "date": "2025"},
    {"doi": "10.5281/zenodo.17529554", "title": "A Dynamic Systems Model of Coherence Grounded in Astronomical Phenomena", "date": "2025"},
]

download_dir = r'C:\Users\user\.kimi_openclaw\workspace\zenodo_papers'
os.makedirs(download_dir, exist_ok=True)

results = []

for i, paper in enumerate(papers, 1):
    record_id = paper["doi"].split(".")[-1]
    url = f"https://zenodo.org/api/records/{record_id}"
    
    try:
        print(f"\n[{i}/{len(papers)}] Fetching metadata for: {paper['title'][:50]}...")
        resp = requests.get(url, timeout=30)
        data = resp.json()
        
        files = data.get("files", [])
        pdf_files = [f for f in files if f.get("key", "").endswith(".pdf")]
        
        if pdf_files:
            pdf = pdf_files[0]
            pdf_url = pdf.get("links", {}).get("self", "")
            filename = pdf.get("key", "")
            size = pdf.get("size", 0)
            
            print(f"  Found PDF: {filename} ({size/1024/1024:.2f} MB)")
            
            # Download PDF
            download_path = os.path.join(download_dir, f"{i:02d}_{record_id}.pdf")
            if os.path.exists(download_path) and os.path.getsize(download_path) == size:
                print(f"  Already downloaded, skipping.")
            else:
                print(f"  Downloading...")
                r = requests.get(pdf_url, timeout=60)
                with open(download_path, 'wb') as f:
                    f.write(r.content)
                print(f"  Saved: {download_path}")
            
            results.append({
                "index": i,
                "doi": paper["doi"],
                "title": paper["title"],
                "date": paper["date"],
                "pdf_path": download_path,
                "filename": filename,
                "size_mb": size / 1024 / 1024,
                "status": "downloaded"
            })
        else:
            print(f"  No PDF found for this record.")
            results.append({
                "index": i,
                "doi": paper["doi"],
                "title": paper["title"],
                "status": "no_pdf"
            })
            
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "index": i,
            "doi": paper["doi"],
            "title": paper["title"],
            "status": f"error: {e}"
        })
    
    time.sleep(1)  # Be nice to Zenodo's API

# Save results
with open(os.path.join(download_dir, "download_manifest.json"), 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n=== DONE ===")
print(f"Downloaded: {sum(1 for r in results if r['status'] == 'downloaded')}/{len(papers)}")
for r in results:
    if r['status'] == 'downloaded':
        print(f"  [{r['index']}] {r['title'][:50]}... ({r['size_mb']:.1f} MB)")
