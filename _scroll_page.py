import urllib.request, json, time

# Scroll down to load more papers
code = """(() => {
  window.scrollTo(0, document.body.scrollHeight);
  return 'Scrolled to bottom: ' + document.body.scrollHeight + 'px';
})()"""

payload = json.dumps({'action': 'evaluate', 'args': {'code': code}, 'session': 'academia-transfer'}).encode()
req = urllib.request.Request('http://127.0.0.1:10086/command', data=payload, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
