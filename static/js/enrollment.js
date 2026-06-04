(function(){
  const prog = document.getElementById('prog');
  const progLabel = document.getElementById('progLabel');
  const finishBtn = document.getElementById('finishBtn');
  const target = 'The quick brown fox jumps over the lazy dog near the river bank.';

  function updateProgress(){
    const c = Telemetry.getCompleted();
    const done = Object.values(c).filter(Boolean).length;
    const pct = Math.round(done/5*100);
    prog.style.width = pct+'%';
    progLabel.textContent = pct+'% complete ('+done+'/5 modalities)';
    finishBtn.disabled = done < 4;
  }

  Telemetry.captureTyping(
    document.getElementById('typingInput'), target,
    s => { document.getElementById('typingStats').textContent = `WPM: ${s.avgSpeed} · Delay: ${s.avgKeyDelay}ms · Errors: ${(s.errorRate*100).toFixed(1)}%`; updateProgress(); }
  );
  Telemetry.captureScroll(
    document.getElementById('scrollZone'),
    s => { document.getElementById('scrollStats').textContent = `Speed: ${s.avgSpeed} · Distance: ${s.totalDistance}px · Direction changes: ${s.directionChanges}`; updateProgress(); }
  );
  Telemetry.captureTaps(
    document.getElementById('tapZone'), document.getElementById('tapBtn'), 10,
    (s,c,t) => { document.getElementById('tapStats').textContent = `Taps: ${c}/${t} · Reaction: ${s.avgReactionTime}ms · Accuracy: ${s.accuracy}%`; updateProgress(); }
  );
  Telemetry.captureSwipes(
    document.getElementById('swipeZone'),
    s => { document.getElementById('swipeStats').textContent = `Swipes: ${s.samples} · Speed: ${s.avgSpeed}px/s · Distance: ${s.avgDistance}px`; updateProgress(); }
  );
  Telemetry.captureMotion(
    document.getElementById('motionBtn'),
    s => { document.getElementById('motionStats').textContent = `Stability: ${s.stabilityScore}% · Variation: ${s.movementVariation}`; updateProgress(); }
  );

  finishBtn.onclick = async () => {
    finishBtn.disabled = true; finishBtn.textContent = 'Processing…';
    const r = await fetch('/api/enrollment', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Telemetry.getFeatures())});
    const d = await r.json();
    if (d.ok) location.href = '/report'; else { finishBtn.disabled=false; finishBtn.textContent='Retry'; alert(d.error||'Failed'); }
  };
})();
