import urllib.request, json

# Check if there are any dialogs blocking downloads
code = """(() => {
  // Check for any modal dialogs, cookie banners, or download confirmation
  const dialogs = document.querySelectorAll('[role="dialog"], .modal, .overlay, .popup');
  const buttons = Array.from(document.querySelectorAll('button')).filter(b => 
    b.textContent.toLowerCase().includes('download') || 
    b.textContent.toLowerCase().includes('confirm') ||
    b.textContent.toLowerCase().includes('allow')
  );
  return JSON.stringify({
    dialogs: dialogs.length,
    dialogTexts: Array.from(dialogs).map(d => d.textContent.substring(0,200)),
    buttons: buttons.map(b => b.textContent.trim()).slice(0,10)
  });
})()"""

payload = json.dumps({'action': 'evaluate', 'args': {'code': code}, 'session': 'academia-transfer'}).encode()
req = urllib.request.Request('http://127.0.0.1:10086/command', data=payload, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
