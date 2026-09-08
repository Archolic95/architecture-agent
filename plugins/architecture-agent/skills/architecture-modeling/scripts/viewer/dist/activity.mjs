export const STAGE_LABELS = Object.freeze({
  preparing: 'Preparing design', building: 'Building geometry',
  checking: 'Checking outputs', reviewing: 'Reviewing',
  revising: 'Revising', ready: 'Ready',
});

export function publicActivity(snapshot) {
  if (snapshot?.enabled === false) return null;
  if (snapshot?.version !== 1 || snapshot?.enabled !== true || !['running','ready','failed','idle'].includes(snapshot.state) || !Array.isArray(snapshot.events) || snapshot.events.length > 12) {
    throw new Error('Invalid activity snapshot');
  }
  const ids = new Set();
  const events = snapshot.events.map(event => {
    if (!event || typeof event.id !== 'string' || !event.id.length || event.id.length > 80 || ids.has(event.id) || !Object.hasOwn(STAGE_LABELS,event.stage) || !['active','done','failed'].includes(event.status) || typeof event.message !== 'string' || event.message.length > 240) {
      throw new Error('Invalid activity event');
    }
    ids.add(event.id);
    return {id:event.id, stage:event.stage, label:STAGE_LABELS[event.stage], status:event.status, message:event.message};
  });
  const active = [...events].reverse().find(event => event.status === 'active');
  const title = {ready:'Ready', failed:'Needs attention', idle:'Waiting'}[snapshot.state] || active?.label || 'In progress';
  return {state:snapshot.state, title, events:events.slice(-4)};
}

// Serial requests: schedule the next poll only after the current one settles.
// No interval-based synthetic progression, and callbacks never touch the model.
export function createActivityPoller({fetchSnapshot,onSnapshot,onError=()=>{},onHealthy=()=>{},isVisible=()=>true,
  delay=3000,timeout=8000,setTimer=setTimeout,clearTimer=clearTimeout}) {
  let stopped=false,paused=false,pending=false,timer=null,controller=null,lastKey=null;
  async function poll() {
    timer=null;
    if (stopped || paused || !isVisible() || pending) return;
    pending=true;controller=new AbortController();
    const abortTimer=setTimer(()=>controller?.abort(),timeout);
    try {
      const raw=await fetchSnapshot(controller.signal), snapshot=publicActivity(raw);
      if (!stopped && !paused) {
        onHealthy();
        const key=JSON.stringify(snapshot);
        if(key!==lastKey){onSnapshot(snapshot);lastKey=key;}
        // No provider means there is nothing to poll for this viewer session.
        if(snapshot===null && raw.available===false)stopped=true;
      }
    } catch(error) {
      if(!stopped && !paused)onError();
    } finally {
      clearTimer(abortTimer);controller=null;pending=false;
      if(!stopped && !paused && isVisible())timer=setTimer(poll,delay);
    }
  }
  return {
    start(){if(!stopped && !paused && !pending && timer===null)void poll();},
    pause(){paused=true;if(timer!==null)clearTimer(timer);timer=null;controller?.abort();},
    resume(){if(stopped)return;paused=false;if(!pending && timer===null)void poll();},
    stop(){stopped=true;if(timer!==null)clearTimer(timer);timer=null;controller?.abort();},
  };
}

export function mountActivityPanel({panel,list,title,notice,api,document,window}) {
  const controller=createActivityPoller({
    fetchSnapshot:async signal=>(await api('/api/activity',{signal})).json(),
    isVisible:()=>!document.hidden,
    onSnapshot:snapshot=>{
      panel.hidden=!snapshot;
      if(!snapshot)return;
      title.textContent=snapshot.title;panel.dataset.state=snapshot.state;notice.hidden=true;
      list.replaceChildren();
      for(const event of snapshot.events){
        const item=document.createElement('li');item.className='activity-event';item.dataset.status=event.status;
        const marker=document.createElement('span');marker.className='activity-marker';marker.setAttribute('aria-label',{active:'In progress',done:'Completed',failed:'Failed'}[event.status]);marker.textContent={active:'',done:'✓',failed:'!'}[event.status];
        const body=document.createElement('div'),label=document.createElement('strong');label.textContent=event.label;body.append(label);
        if(event.message){const message=document.createElement('p');message.textContent=event.message;body.append(message);}
        item.append(marker,body);list.append(item);
      }
    },
    onError:()=>{if(!panel.hidden){notice.hidden=false;notice.textContent='Updates paused. Your model is still available.';}},
    onHealthy:()=>{notice.hidden=true;},
  });
  const visibility=()=>document.hidden?controller.pause():controller.resume();
  const cleanup=()=>{controller.stop();document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',cleanup);};
  document.addEventListener('visibilitychange',visibility);window.addEventListener('pagehide',cleanup);controller.start();
  return cleanup;
}
