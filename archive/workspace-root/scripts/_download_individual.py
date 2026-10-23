import urllib.request, json, time, os

# Papers to download individually (navigate to page → click download)
papers = [
    {"title": "People of the Threshold v", "url": "https://www.academia.edu/166176974/People_of_the_Threshold_v", "dl_ref": "@e55"},
    {"title": "The Arctic Threshold v", "url": "https://www.academia.edu/166176699/The_Arctic_Threshold_v", "dl_ref": "@e59"},
    {"title": "The Full Story v1 (1)", "url": "https://www.academia.edu/166174774/The_Full_Story_v1_1_", "dl_ref": "@e63"},
    {"title": "From A to B v1 (1)", "url": "https://www.academia.edu/166170160/From_A_to_B_v1_1_", "dl_ref": "@e67"},
    {"title": "The Atlantic Substrate v", "url": "https://www.academia.edu/166168500/The_Atlantic_Substrate_v", "dl_ref": "@e71"},
    {"title": "Validation Metrics Ledger v", "url": "https://www.academia.edu/166167858/Validation_Metrics_Ledger_v", "dl_ref": "@e75"},
    {"title": "Pattern Recognition Archaeology Report v", "url": "https://www.academia.edu/166139651/Pattern_Recognition_Archaeology_Report_v", "dl_ref": "@e87"},
    {"title": "Hnc protocol", "url": "https://www.academia.edu/165979504/Hnc_protocol", "dl_ref": "@e106"},
    {"title": "Antarctic briefing part 3", "url": "https://www.academia.edu/165957073/Antarctic_briefing_part_3", "dl_ref": "@e110"},
    {"title": "Antarctic briefing part 2", "url": "https://www.academia.edu/165956876/Antarctic_briefing_part_2", "dl_ref": "@e114"},
    {"title": "Antarctic briefing", "url": "https://www.academia.edu/165954166/Antarctic_briefing", "dl_ref": "@e118"},
]

downloads_dir = os.path.expanduser(r"~\Downloads")
results = []

for i, paper in enumerate(papers, 1):
    print(f"\n[{i}/{len(papers)}] Processing: {paper['title']}")
    
    # Navigate to paper page
    nav_payload = json.dumps({
        'action': 'navigate',
        'args': {'url': paper['url']},
        'session': 'academia-transfer'
    }).encode()
    req = urllib.request.Request('http://127.0.0.1:10086/command', data=nav_payload, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    time.sleep(3)
    
    # Click download
    click_payload = json.dumps({
        'action': 'click',
        'args': {'ref': paper['dl_ref']},
        'session': 'academia-transfer'
    }).encode()
    req = urllib.request.Request('http://127.0.0.1:10086/command', data=click_payload, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req)
    print(f"  Clicked download: {resp.read().decode()[:100]}")
    
    # Wait for download
    time.sleep(5)
    
    # Check for new PDF in Downloads
    new_pdfs = [f for f in os.listdir(downloads_dir) if f.endswith('.pdf')]
    # Get most recent
    if new_pdfs:
        recent = max(new_pdfs, key=lambda f: os.path.getmtime(os.path.join(downloads_dir, f)))
        mtime = os.path.getmtime(os.path.join(downloads_dir, recent))
        if time.time() - mtime < 15:  # Downloaded in last 15 seconds
            print(f"  -> DOWNLOADED: {recent}")
            results.append({"title": paper['title'], "file": recent, "status": "ok"})
        else:
            print(f"  -> No new download detected")
            results.append({"title": paper['title'], "status": "failed"})
    else:
        results.append({"title": paper['title'], "status": "failed"})

print(f"\n=== RESULTS ===")
for r in results:
    print(f"{r['status'].upper()}: {r['title']}")
