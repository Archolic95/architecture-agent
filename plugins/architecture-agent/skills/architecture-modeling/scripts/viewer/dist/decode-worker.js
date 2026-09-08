importScripts('./vendor/rhino3dm.js');
const ready=Promise.all([rhino3dm({locateFile:name=>new URL('./vendor/'+name,self.location.href).href}),import('./decode.mjs')]);
self.onmessage=async event=>{try{const [rhino,{decodeDocument}]=await ready;self.postMessage({ok:true,result:decodeDocument(rhino,event.data)});}catch(e){self.postMessage({ok:false,error:e.message||String(e)});}};
