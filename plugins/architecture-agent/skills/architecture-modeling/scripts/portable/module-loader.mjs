// Resolve this finite, acyclic bundle to in-page Blob modules, without file fetches.
export function buildModuleURLs(sources, makeURL = source => URL.createObjectURL(new Blob([source], {type:'text/javascript'}))) {
  const urls = new Map(), visiting = new Set();
  function build(name) {
    if (urls.has(name)) return urls.get(name);
    if (!Object.hasOwn(sources, name) || visiting.has(name)) throw new Error('Invalid portable module graph.');
    visiting.add(name);
    const source = sources[name].replace(/(^import\s+[^;\n]*?\s+from\s+)(['"])([^'"]+)\2/gm,
      (whole, prefix, quote, specifier) => {
        if (!specifier.startsWith('./') && !specifier.startsWith('../')) throw new Error('External portable module dependency.');
        const parent = name.split('/'); parent.pop();
        for (const part of specifier.split('/')) {
          if (part === '..') {if (!parent.length) throw new Error('Module escaped its bundle.'); parent.pop();}
          else if (part !== '.') parent.push(part);
        }
        return prefix + quote + build(parent.join('/')) + quote;
      });
    const url = makeURL(source, name);
    visiting.delete(name); urls.set(name, url);
    return url;
  }
  for (const name of Object.keys(sources)) build(name);
  return urls;
}
