import {mkdir,copyFile,cp,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
await mkdir('dist/vendor',{recursive:true});
await cp('src','dist',{recursive:true});
const files = [
 ['node_modules/three/build/three.module.js','dist/vendor/three.module.js'],
 ['node_modules/three/LICENSE','dist/vendor/THREE-LICENSE.txt'],
 ['node_modules/rhino3dm/rhino3dm.js','dist/vendor/rhino3dm.js'],
 ['node_modules/rhino3dm/rhino3dm.wasm','dist/vendor/rhino3dm.wasm'],
 ['RHINO3DM-LICENSE.txt','dist/vendor/RHINO3DM-LICENSE.txt'],
];
for(const [a,b] of files) await copyFile(a,b);
const inventory=[];
for(const [,path] of files){const bytes=await readFile(path);inventory.push({path,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});}
await writeFile('dist/vendor/README.txt','Three.js 0.128.0 (MIT), rhino3dm 8.32.2 (MIT). Sources: https://github.com/mrdoob/three.js and https://github.com/mcneel/rhino3dm. No CDN requests. See THIRD-PARTY-NOTICES.md in package.\n');
await writeFile('dist/build-manifest.json',JSON.stringify({version:'0.1.0',dependencies:{three:'0.128.0',rhino3dm:'8.32.2'},files:inventory},null,2));
console.log('Built offline viewer assets in dist/');
