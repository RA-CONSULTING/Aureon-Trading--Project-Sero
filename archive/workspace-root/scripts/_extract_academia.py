import urllib.request, json, os

code = r"""(() => {
  const papers = [];
  document.querySelectorAll('a[href*="download_file"]').forEach(a => {
    const card = a.closest('article') || a.closest('[class*="paper"]') || a.parentElement?.parentElement?.parentElement;
    const titleLink = card?.querySelector('a[href*="academia.edu/"]');
    const title = titleLink ? titleLink.textContent.trim() : 'unknown';
    papers.push({title: title, download: a.href});
  });
  return JSON.stringify({count: papers.length, papers: papers});
})()"""

payload = json.dumps({'action': 'evaluate', 'args': {'code': code}, 'session': 'academia-transfer'}).encode()
req = urllib.request.Request('http://127.0.0.1:10086/command', data=payload, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
