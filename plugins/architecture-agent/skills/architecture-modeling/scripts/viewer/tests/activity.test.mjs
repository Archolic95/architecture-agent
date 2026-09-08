import test from 'node:test';
import assert from 'node:assert/strict';
import {publicActivity,createActivityPoller,mountActivityPanel} from '../src/activity.mjs';

const snapshot={version:1,enabled:true,available:true,state:'running',events:[{id:'one',stage:'building',status:'active',message:'Creating columns from the selected structural grid.'}]};
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function timers(){let seq=0;const tasks=new Map();return {tasks,setTimer:(fn,ms)=>{tasks.set(++seq,{fn,ms});return seq;},clearTimer:id=>tasks.delete(id),run:ms=>{const found=[...tasks].find(([,task])=>task.ms===ms);assert(found,`Missing ${ms}ms timer`);tasks.delete(found[0]);found[1].fn();}};}

test('public progress uses only supplied events and excludes extra reasoning fields',()=>{
 const view=publicActivity({...snapshot,reasoning:'private',events:[{...snapshot.events[0],thoughts:'private'}]});
 assert.equal(view.title,'Building geometry');assert.equal(view.events.length,1);assert(!JSON.stringify(view).includes('private'));
 assert.equal(publicActivity({enabled:false}),null);
 assert.throws(()=>publicActivity({...snapshot,events:Array(13).fill(snapshot.events[0])}),/Invalid/);
 assert.throws(()=>publicActivity({...snapshot,events:[{...snapshot.events[0],stage:'hidden_reasoning'}]}),/Invalid/);
 assert.throws(()=>publicActivity({...snapshot,events:[{...snapshot.events[0],message:'x'.repeat(241)}]}),/Invalid/);
});

test('polls never overlap and stop aborts an outstanding request without updates',async()=>{
 const clock=timers();let calls=0,resolve,signal;const received=[];
 const poller=createActivityPoller({...clock,fetchSnapshot:s=>{signal=s;calls++;return new Promise(r=>resolve=r);},onSnapshot:s=>received.push(s)});
 poller.start();poller.start();assert.equal(calls,1);assert.equal([...clock.tasks.values()].filter(x=>x.ms===3000).length,0);
 resolve(snapshot);await flush();assert.equal(received.length,1);clock.run(3000);assert.equal(calls,2);
 poller.stop();assert.equal(signal.aborted,true);resolve({...snapshot,state:'ready'});await flush();assert.equal(received.length,1);assert.equal(clock.tasks.size,0);
});

test('no provider stops polling; temporary absent activity continues polling',async()=>{
 for(const available of [false,true]){const clock=timers();let calls=0;const received=[];
  const poller=createActivityPoller({...clock,fetchSnapshot:async()=>{calls++;return {enabled:false,available};},onSnapshot:s=>received.push(s)});
  poller.start();await flush();assert.deepEqual(received,[null]);assert.equal(clock.tasks.size,available?1:0);poller.stop();
 }
});

test('poll errors keep the last public snapshot and identical recovery clears error state',async()=>{
 const clock=timers();let calls=0,errors=0,healthy=0;const received=[];
 const poller=createActivityPoller({...clock,fetchSnapshot:async()=>{calls++;if(calls===2)throw new Error('network');return snapshot;},onSnapshot:s=>received.push(s),onError:()=>errors++,onHealthy:()=>healthy++});
 poller.start();await flush();clock.run(3000);await flush();assert.equal(errors,1);assert.equal(received.length,1);
 clock.run(3000);await flush();assert.equal(healthy,2);assert.equal(received.length,1);poller.stop();
});

test('hidden-page pause aborts polling and resume restarts it once',async()=>{
 const clock=timers();let calls=0,signal;const poller=createActivityPoller({...clock,fetchSnapshot:s=>{calls++;signal=s;return new Promise((_,reject)=>s.addEventListener('abort',()=>reject(Object.assign(new Error('paused'),{name:'AbortError'}))));},onSnapshot:()=>assert.fail('No complete snapshot expected')});
 poller.start();poller.pause();assert(signal.aborted);await flush();assert.equal(clock.tasks.size,0);poller.resume();assert.equal(calls,2);poller.resume();assert.equal(calls,2);poller.stop();await flush();assert.equal(clock.tasks.size,0);
});

test('a timed-out poll aborts and reports unavailable progress before scheduling a retry',async()=>{
 const clock=timers();let calls=0,errors=0,signal;
 const poller=createActivityPoller({...clock,fetchSnapshot:s=>{calls++;signal=s;return new Promise((_,reject)=>s.addEventListener('abort',()=>reject(Object.assign(new Error('timeout'),{name:'AbortError'}))));},onSnapshot:()=>assert.fail('No complete snapshot expected'),onError:()=>errors++});
 poller.start();clock.run(8000);await flush();assert(signal.aborted);assert.equal(calls,1);assert.equal(errors,1);assert.equal([...clock.tasks.values()].filter(t=>t.ms===3000).length,1);poller.stop();assert.equal(clock.tasks.size,0);
});

class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.hidden=false;this.textContent='';}
 set innerHTML(_){throw new Error('Unsafe HTML insertion');}
 append(...elements){this.children.push(...elements);}
 replaceChildren(...elements){this.children=[...elements];}
 setAttribute(name,value){this[name]=value;}
}
test('panel renders markup-shaped messages as plain text and cleans up page listeners',async()=>{
 const registrations=new Map(),doc={hidden:false,createElement:tag=>new Element(tag),addEventListener:(event,cb)=>registrations.set(event,cb),removeEventListener:event=>registrations.delete(event)},win={addEventListener:(event,cb)=>registrations.set(event,cb),removeEventListener:event=>registrations.delete(event)};
 const panel=new Element('details'),list=new Element('ol'),title=new Element('span'),notice=new Element('p');panel.hidden=true;
 const text='<img src=x onerror=steal()> literal project note';
 const cleanup=mountActivityPanel({panel,list,title,notice,api:async()=>({json:async()=>({...snapshot,events:[{...snapshot.events[0],message:text}]})}),document:doc,window:win});
 await flush();assert.equal(panel.hidden,false);assert.equal(title.textContent,'Building geometry');assert.equal(list.children[0].children[1].children[1].textContent,text);assert.equal(list.children[0].children[1].children[1].tag,'p');cleanup();assert.equal(registrations.size,0);
});
