// Risk popup. window.showAlertPopup(alert) where alert = {severity,title,reason,action,score,id}
(function(){
  let openId = null;

  function close(){
    const b = document.querySelector('.bas-alert-backdrop');
    if (b) b.remove();
    openId = null;
  }

  window.showAlertPopup = function(alert){
    if (!alert) return;
    // de-dupe: don't reshow same alert id
    if (alert.id && alert.id === openId) return;
    close();
    openId = alert.id || Date.now();

    const sev = (alert.severity || 'warning');
    const backdrop = document.createElement('div');
    backdrop.className = 'bas-alert-backdrop';
    backdrop.innerHTML = `
      <div class="bas-alert-modal ${sev}" role="alertdialog" aria-modal="true">
        <div class="bas-alert-icon">${sev === 'critical' ? '⚠' : '!'}</div>
        <div class="bas-alert-title">${escapeHtml(alert.title || 'Suspicious activity detected')}</div>
        <p class="bas-alert-reason">${escapeHtml(alert.reason || '')}</p>
        <p class="bas-alert-action">${escapeHtml(alert.action || '')}</p>
        <p class="bas-alert-meta">Score: ${(alert.score ?? 0).toFixed ? alert.score.toFixed(3) : alert.score} · ${new Date(alert.ts || Date.now()).toLocaleTimeString()}</p>
        <div class="bas-alert-btns">
          <button class="ghost" data-act="dismiss">Dismiss</button>
          <button class="primary" data-act="verify">Re-verify now</button>
        </div>
      </div>`;
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
    backdrop.querySelector('[data-act="dismiss"]').addEventListener('click', close);
    backdrop.querySelector('[data-act="verify"]').addEventListener('click', () => {
      close();
      if (window.toast) window.toast('Please complete the verification challenge.', 'info');
      // Hook: navigate to auth page if available
      if (typeof window.onAlertVerify === 'function') window.onAlertVerify(alert);
      else if (sev === 'critical') window.location.href = '/auth';
    });
    document.body.appendChild(backdrop);
  };

  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }
})();
