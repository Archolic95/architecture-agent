const status = document.getElementById('portable-status');
try {
  const bundle = JSON.parse(document.getElementById('portable-package').textContent);
  if (!globalThis.crypto?.subtle) throw new Error('File verification is unavailable. Open this downloaded HTML in a current desktop browser.');
  const sources = {};
  for (const [name, entry] of Object.entries(bundle.modules)) {
    const bytes = Uint8Array.from(atob(entry.base64), character => character.charCodeAt(0));
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2,'0')).join('');
    if (digest !== entry.sha256) throw new Error('A portable viewer module failed its integrity check.');
    sources[name] = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
  }
  const urls = buildModuleURLs(sources);
  const {initializePortable} = await import(urls.get('portable-api.mjs'));
  await initializePortable(bundle.payload);
  status.textContent = 'Files verified · opening model';
  await import(urls.get('app.mjs'));
  const shown = document.getElementById('counts').textContent.includes('display objects');
  status.textContent = shown ? 'Offline model · files verified' : 'Files verified · preview unavailable';
  status.dataset.state = shown ? 'ready' : 'preview-unavailable';
  document.getElementById('welcome').querySelector('h2').textContent = 'Preview unavailable';
  document.getElementById('welcome').querySelector('p').textContent = 'The native model remains available through Download model.';
  window.addEventListener('pagehide', () => {for (const url of urls.values()) URL.revokeObjectURL(url);}, {once:true});
} catch (error) {
  status.textContent = error.message || String(error);
  status.dataset.state = 'error';
  document.getElementById('welcome').querySelector('h2').textContent = 'Could not open this portable model';
  document.getElementById('welcome').querySelector('p').textContent = 'The files must pass integrity checks before viewing or downloading. Ask for the original model files if this browser cannot open the package.';
}
