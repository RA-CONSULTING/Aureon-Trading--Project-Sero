import urllib.request, json

code = """(() => {
  const links = Array.from(document.querySelectorAll('a[href*="download_file"]'));
  links.forEach((a, i) => {
    setTimeout(() => { a.click(); console.log('Downloading ' + (i+1) + '/' + links.length); }, i * 3000);
  });
  return 'Triggered ' + links.length + ' downloads, spacing 3s apart';
})()"""

payload = json.dumps({'action': 'evaluate', 'args': {'code': code}, 'session': 'academia-transfer'}).encode()
req = urllib.request.Request('http://127.0.0.1:10086/command', data=payload, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
