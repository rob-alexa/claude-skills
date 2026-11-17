// Minimal Chrome DevTools Protocol client for the Salesforce mobile app's WebView on an Android
// emulator. SKILL.md, section "Blank pages or "Loading..." in a signed-in app", says when to reach
// for it. It talks to whatever is forwarded to port 9333:
//   adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>
// Usage: node webview-cdp.mjs eval "<js expression>"              -> prints the expression's value
//        node webview-cdp.mjs watch <seconds> [reload|"<js expr>"] -> logs requests, failures,
//                                                                     console, and navigations
// Needs Node 22 or later (global fetch and WebSocket). In bash, single-quote an expression that
// uses $A, or the shell expands it to nothing.
const [mode, arg, extra] = process.argv.slice(2);
const list = await (await fetch('http://127.0.0.1:9333/json/list')).json();
const page = list.find(p => p.type === 'page');
if (!page) { console.log('no page target'); process.exit(1); }
console.log('target:', page.url.slice(0, 300));
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const reqs = new Map();
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  const p = m.params || {};
  switch (m.method) {
    case 'Network.requestWillBeSent': reqs.set(p.requestId, p.request.url); console.log('REQ', p.request.method, p.request.url.slice(0, 220)); break;
    case 'Network.responseReceived': console.log('RES', p.response.status, p.response.url.slice(0, 220)); break;
    case 'Network.loadingFailed': console.log('FAIL', p.errorText, p.blockedReason || '', p.corsErrorStatus ? JSON.stringify(p.corsErrorStatus) : '', (reqs.get(p.requestId) || '').slice(0, 220)); break;
    case 'Runtime.consoleAPICalled':
      console.log('CONSOLE', p.type, p.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 400));
      for (const a of p.args) if (a.objectId && /error|warn/i.test(p.type + JSON.stringify(p.args.map(x => x.value)))) send('Runtime.callFunctionOn', { objectId: a.objectId, functionDeclaration: 'function(){try{return JSON.stringify(this,Object.getOwnPropertyNames(this)).slice(0,1500)}catch(e){return String(this)}}', returnByValue: true }).then(r => console.log('  OBJ', r.result?.result?.value));
      break;
    case 'Runtime.exceptionThrown': console.log('EXC', JSON.stringify(p.exceptionDetails).slice(0, 600)); break;
    case 'Log.entryAdded': console.log('LOG', p.entry.level, p.entry.source, p.entry.text.slice(0, 400), (p.entry.url || '').slice(0, 200)); break;
    case 'Page.frameNavigated': console.log('NAV', p.frame.parentId ? 'child' : 'main', p.frame.url.slice(0, 300)); break;
  }
};
await new Promise(r => ws.onopen = r);
if (mode === 'eval') {
  const r = await send('Runtime.evaluate', { expression: arg, returnByValue: true, awaitPromise: true });
  console.log(JSON.stringify(r.result?.result?.value ?? r.result, null, 1));
} else if (mode === 'watch') {
  await send('Network.enable'); await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
  if (extra === 'reload') await send('Page.reload', { ignoreCache: true });
  else if (extra) { const r = await send('Runtime.evaluate', { expression: extra, returnByValue: true, awaitPromise: true }); console.log('EVAL', JSON.stringify(r.result?.result?.value ?? r.result).slice(0, 1500)); }
  await new Promise(r => setTimeout(r, Number(arg || 20) * 1000));
}
ws.close(); process.exit(0);
