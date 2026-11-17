import urllib.request, json, os, time

# Paper download links from Academia.edu (page 1 - 19 papers)
papers = [
    {"title": "HNC BioMolecule Adjacent Frequency Packet White Paper v", "download": "https://www.academia.edu/attachments/133364756/download_file?s=profile"},
    {"title": "EPAS HNC Integrated Harmonic Tech Stack v", "download": "https://www.academia.edu/attachments/132789824/download_file?s=profile"},
    {"title": "People of the Threshold v", "download": "https://www.academia.edu/attachments/132661192/download_file?s=profile"},
    {"title": "The Arctic Threshold v", "download": "https://www.academia.edu/attachments/132661011/download_file?s=profile"},
    {"title": "The Full Story v1 (1)", "download": "https://www.academia.edu/attachments/132659836/download_file?s=profile"},
    {"title": "From A to B v1 (1)", "download": "https://www.academia.edu/attachments/132657135/download_file?s=profile"},
    {"title": "The Atlantic Substrate v", "download": "https://www.academia.edu/attachments/132656145/download_file?s=profile"},
    {"title": "Validation Metrics Ledger v", "download": "https://www.academia.edu/attachments/132655775/download_file?s=profile"},
    {"title": "Atlantic Seaboard Substrate v", "download": "https://www.academia.edu/attachments/132648688/download_file?s=profile"},
    {"title": "Atlantic Seaboard Substrate v (duplicate)", "download": "https://www.academia.edu/attachments/132648682/download_file?s=profile"},
    {"title": "Pattern Recognition Archaeology Report v", "download": "https://www.academia.edu/attachments/132646080/download_file?s=profile"},
    {"title": "HNC White Paper v", "download": "https://www.academia.edu/attachments/132634043/download_file?s=profile"},
    {"title": "HNC Empirical Audit v", "download": "https://www.academia.edu/attachments/132633835/download_file?s=profile"},
    {"title": "Aureon whitepaper part", "download": "https://www.academia.edu/attachments/132601350/download_file?s=profile"},
    {"title": "Hnc protocol", "download": "https://www.academia.edu/attachments/132589325/download_file?s=profile"},
    {"title": "Antarctic briefing part 3", "download": "https://www.academia.edu/attachments/132585535/download_file?s=profile"},
    {"title": "Antarctic briefing part 2", "download": "https://www.academia.edu/attachments/132585473/download_file?s=profile"},
    {"title": "Antarctic briefing", "download": "https://www.academia.edu/attachments/132583939/download_file?s=profile"},
    {"title": "PEFCphiS Leckey", "download": "https://www.academia.edu/attachments/132568922/download_file?s=profile"},
]

# SCEMDA HNC LSC Academic White Paper has no download link visible

output_dir = os.path.expanduser(r"~\.kimi_openclaw\workspace\academia_downloads")
os.makedirs(output_dir, exist_ok=True)

results = []

for i, paper in enumerate(papers, 1):
    safe_title = "".join(c for c in paper["title"] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    output_path = os.path.join(output_dir, f"{i:02d}_{safe_title}.pdf")
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"[{i}/{len(papers)}] ALREADY EXISTS: {paper['title']}")
        results.append({"title": paper["title"], "status": "exists", "path": output_path})
        continue
    
    print(f"[{i}/{len(papers)}] Downloading: {paper['title']}...")
    try:
        req = urllib.request.Request(paper["download"], headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        resp = urllib.request.urlopen(req, timeout=60)
        data = resp.read()
        
        with open(output_path, 'wb') as f:
            f.write(data)
        
        size_kb = len(data) / 1024
        print(f"  -> SAVED: {size_kb:.1f} KB -> {output_path}")
        results.append({"title": paper["title"], "status": "downloaded", "size_kb": size_kb, "path": output_path})
        time.sleep(2)  # Be polite
    except Exception as e:
        print(f"  -> FAILED: {e}")
        results.append({"title": paper["title"], "status": "failed", "error": str(e)})

# Save results
with open(os.path.join(output_dir, "_download_results.json"), 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n=== DONE ===")
print(f"Downloaded: {sum(1 for r in results if r['status'] == 'downloaded')}")
print(f"Already had: {sum(1 for r in results if r['status'] == 'exists')}")
print(f"Failed: {sum(1 for r in results if r['status'] == 'failed')}")
