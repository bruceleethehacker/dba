// Tiny dependency-free toast helper. window.toast(msg, type?, ms?)
(function(){
  function ensureStack(){
    let s = document.querySelector('.bas-toast-stack');
    if (!s){ s = document.createElement('div'); s.className='bas-toast-stack'; document.body.appendChild(s); }
    return s;
  }
  window.toast = function(message, type, ms){
    try{
      const stack = ensureStack();
      const el = document.createElement('div');
      el.className = 'bas-toast ' + (type || 'info');
      el.textContent = message;
      stack.appendChild(el);
      setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateY(8px)';
        setTimeout(()=>el.remove(), 250); }, ms || 3200);
    } catch(e){ /* noop */ }
  };
})();
