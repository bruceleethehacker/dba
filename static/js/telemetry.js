// Behavioral telemetry capture utilities
window.Telemetry = (function(){
  const features = {
    typing:  {avgSpeed:0,avgKeyDelay:0,backspaceCount:0,errorRate:0,avgPauseTime:0,samples:0},
    scrolling:{avgSpeed:0,totalDistance:0,avgStopTime:0,directionChanges:0,samples:0},
    tap:     {avgReactionTime:0,accuracy:0,avgInterval:0,avgDuration:0,samples:0},
    swipe:   {avgSpeed:0,avgDistance:0,avgAngle:0,avgDuration:0,samples:0},
    motion:  {stabilityScore:0,movementVariation:0,handlingPattern:'normal',samples:0}
  };
  const completed = {typing:false,scrolling:false,tap:false,swipe:false,motion:false};

  function captureTyping(input, target, onStats){
    let last=0, delays=[], start=null, backs=0, keys=0;
    input.addEventListener('keydown', e => {
      const now = performance.now();
      if (last) delays.push(now-last);
      last = now; keys++;
      if (!start) start = now;
      if (e.key === 'Backspace') backs++;
    });
    input.addEventListener('input', e => {
      const val = input.value;
      const elapsed = (performance.now()-start)/1000/60; // min
      const wpm = elapsed > 0 ? (val.length/5)/elapsed : 0;
      const avgDelay = delays.length ? delays.reduce((a,b)=>a+b,0)/delays.length : 0;
      let errs = 0; for(let i=0;i<val.length;i++) if(val[i]!==target[i]) errs++;
      features.typing = {
        avgSpeed: Math.round(wpm),
        avgKeyDelay: Math.round(avgDelay),
        backspaceCount: backs,
        errorRate: val.length ? errs/val.length : 0,
        avgPauseTime: Math.round(avgDelay*1.5),
        samples: keys
      };
      onStats(features.typing);
      if (val.length >= Math.min(target.length, 30) && keys > 15) { completed.typing = true; }
    });
  }

  function captureScroll(zone, onStats){
    let lastY=0, lastT=0, dist=0, speeds=[], dirChanges=0, lastDir=0, start=Date.now();
    zone.addEventListener('scroll', () => {
      const y = zone.scrollTop, t = performance.now();
      const dy = y-lastY, dt = t-lastT;
      if (dt>0){ speeds.push(Math.abs(dy)/dt*1000); dist += Math.abs(dy);
        const dir = Math.sign(dy);
        if (dir && lastDir && dir!==lastDir) dirChanges++;
        if (dir) lastDir = dir;
      }
      lastY=y; lastT=t;
      const avg = speeds.length ? speeds.reduce((a,b)=>a+b,0)/speeds.length : 0;
      features.scrolling = {avgSpeed:Math.round(avg),totalDistance:Math.round(dist),avgStopTime:0,directionChanges:dirChanges,samples:speeds.length};
      onStats(features.scrolling);
      if ((Date.now()-start) > 8000 && speeds.length > 10) completed.scrolling = true;
    });
  }

  function captureTaps(zone, btn, target, onStats, onDone){
    let count=0, reactions=[], lastShown=performance.now(), hits=0;
    const move = () => {
      const w = zone.clientWidth-56, h = zone.clientHeight-56;
      btn.style.left = Math.random()*w + 'px';
      btn.style.top  = Math.random()*h + 'px';
      lastShown = performance.now();
    };
    move();
    btn.addEventListener('click', () => {
      count++; hits++;
      reactions.push(performance.now()-lastShown);
      const avg = reactions.reduce((a,b)=>a+b,0)/reactions.length;
      features.tap = {avgReactionTime:Math.round(avg),accuracy:Math.round(hits/count*100),avgInterval:0,avgDuration:0,samples:count};
      onStats(features.tap, count, target);
      if (count >= target){ completed.tap = true; btn.style.display='none'; onDone&&onDone(); return; }
      move();
    });
  }

  function captureSwipes(zone, onStats){
    let sx=0,sy=0,st=0, speeds=[], dists=[], angles=[], durs=[];
    const start = e => { const p=e.touches?e.touches[0]:e; sx=p.clientX;sy=p.clientY;st=performance.now(); };
    const end   = e => {
      const p=e.changedTouches?e.changedTouches[0]:e;
      const dx=p.clientX-sx, dy=p.clientY-sy, dt=performance.now()-st;
      const d=Math.hypot(dx,dy); if(d<20)return;
      speeds.push(d/dt*1000); dists.push(d); durs.push(dt);
      angles.push(Math.atan2(dy,dx)*180/Math.PI);
      const avg=a=>a.reduce((x,y)=>x+y,0)/a.length;
      features.swipe = {avgSpeed:Math.round(avg(speeds)),avgDistance:Math.round(avg(dists)),avgAngle:Math.round(Math.abs(avg(angles))),avgDuration:Math.round(avg(durs)),samples:speeds.length};
      onStats(features.swipe);
      if (speeds.length >= 5) completed.swipe = true;
    };
    zone.addEventListener('mousedown',start); zone.addEventListener('mouseup',end);
    zone.addEventListener('touchstart',start,{passive:true}); zone.addEventListener('touchend',end);
  }

  function captureMotion(btn, onStats, onDone){
    btn.addEventListener('click', () => {
      btn.disabled = true; btn.textContent = 'Sampling…';
      let samples=[], i=0;
      const itv = setInterval(()=>{
        // Simulated stability: in real mobile app, use DeviceMotionEvent
        samples.push(80 + Math.random()*15);
        i++;
        if (i>=10){
          clearInterval(itv);
          const avg = samples.reduce((a,b)=>a+b,0)/samples.length;
          const variation = Math.max(...samples)-Math.min(...samples);
          features.motion = {stabilityScore:Math.round(avg),movementVariation:Math.round(variation),handlingPattern:'steady',samples:samples.length};
          onStats(features.motion);
          completed.motion = true;
          btn.textContent = 'Sample Complete'; onDone&&onDone();
        }
      }, 200);
    });
  }

  function getFeatures(){ return features; }
  function getCompleted(){ return completed; }
  return {captureTyping,captureScroll,captureTaps,captureSwipes,captureMotion,getFeatures,getCompleted};
})();

// ---- v2 sink: periodically forward features to the new telemetry engine ----
(function(){
  if (typeof window === 'undefined' || !window.Telemetry) return;
  let lastSent = 0;
  setInterval(() => {
    try {
      const f = window.Telemetry.getFeatures();
      const now = Date.now();
      if (now - lastSent < 2000) return;
      lastSent = now;
      fetch('/api/v2/telemetry', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify({
          typing: [], scrolling: [], taps: [], swipes: [], motion: [], sensors: [],
          features_snapshot: f
        })
      }).catch(()=>{});
    } catch (e) {}
  }, 2000);
})();
