(function(){
  let monitoring = true;
  const conf = document.getElementById('conf');
  const risk = document.getElementById('risk');
  const label = document.getElementById('statusLabel');
  const icon = document.getElementById('statusIcon');
  const sessionRisk = document.getElementById('sessionRisk');
  const lastVer = document.getElementById('lastVer');
  const log = document.getElementById('log');
  const btn = document.getElementById('toggleBtn');

  const messages = {
    genuine: ['Behavioral pattern matches enrolled profile','Keystroke dynamics analyzed','Scroll pattern verified','Gesture pattern matched','Session continuity confirmed'],
    verification_required: ['Minor deviation detected — monitoring','Touch pressure slightly off','Typing cadence drifting'],
    suspicious: ['Significant behavioral anomaly detected','Authentication confidence dropping','Behavioral mismatch — flagging session']
  };

  function addLog(msg, cls){
    const el = document.createElement('div');
    el.className = 'line ' + (cls||'muted');
    el.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    log.prepend(el);
    while (log.children.length > 30) log.removeChild(log.lastChild);
  }

  async function tick(){
    if (!monitoring) return;
    try {
      const r = await fetch('/api/auth/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
      const d = await r.json();
      if (!d.ok) return;
      // Apply random drift on the client to simulate real-time fluctuation
      const drift = (Math.random()-0.5)*10;
      const c = Math.max(20, Math.min(99, d.result.confidence + drift));
      const rk = Math.max(1, Math.min(99, 100-c));
      const status = c >= 85 ? 'genuine' : c >= 60 ? 'verification_required' : 'suspicious';
      const lbl = status==='genuine'?'Genuine User':status==='verification_required'?'Verification Required':'Suspicious User';
      conf.textContent = Math.round(c)+'%'; risk.textContent = Math.round(rk)+'%';
      label.textContent = lbl;
      label.className = status==='genuine'?'ok':status==='verification_required'?'warn':'bad';
      icon.textContent = status==='genuine'?'✅':status==='verification_required'?'🛡️':'⚠️';
      sessionRisk.textContent = rk<30?'Low':rk<60?'Medium':'High';
      lastVer.textContent = new Date().toLocaleTimeString();
      const pool = messages[status];
      addLog(pool[Math.floor(Math.random()*pool.length)], status==='genuine'?'ok':status==='verification_required'?'warn':'bad');
    } catch(e){ addLog('Network error during monitoring','bad'); }
  }

  btn.onclick = () => {
    monitoring = !monitoring;
    btn.textContent = monitoring ? 'Pause Monitoring' : 'Resume Monitoring';
    btn.className = 'btn ' + (monitoring ? 'btn-danger' : 'btn-primary');
    addLog(monitoring ? 'Monitoring resumed' : 'Monitoring paused', 'muted');
  };

  addLog('Real-time behavioral monitoring initiated','ok');
  tick();
  setInterval(tick, 2500);
})();
