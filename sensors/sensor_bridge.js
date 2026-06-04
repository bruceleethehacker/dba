/* sensor_bridge.js
 *
 * Browser / Capacitor sensor integration for the behavioral-auth client.
 * Captures DeviceMotion, DeviceOrientation, and (optional) Generic Sensor
 * API streams, debounces them, and POSTs batches to /api/v2/telemetry.
 *
 * On iOS Safari requestPermission() must be called from a user gesture –
 * call BAS.Sensors.requestPermission() inside a click handler.
 */
(function (global) {
  const BAS = (global.BAS = global.BAS || {});

  const cfg = {
    endpoint: "/api/v2/telemetry",
    flushMs: 2000,
    maxSamples: 200,
    token: null, // set via BAS.Sensors.setToken(t)
  };

  const buffers = { motion: [], sensors: [], taps: [], swipes: [], scrolling: [], typing: [] };
  let flushTimer = null;
  let activeSwipe = null;

  function setToken(t) { cfg.token = t; }

  function _push(channel, sample) {
    const buf = buffers[channel];
    if (!buf) return;
    buf.push(sample);
    if (buf.length > cfg.maxSamples) buf.shift();
  }

  async function requestPermission() {
    try {
      if (typeof DeviceMotionEvent !== "undefined" &&
          typeof DeviceMotionEvent.requestPermission === "function") {
        const r = await DeviceMotionEvent.requestPermission();
        return r === "granted";
      }
    } catch (e) { /* ignore */ }
    return true;
  }

  function start() {
    // accelerometer + gyroscope via DeviceMotion (broadly supported)
    window.addEventListener("devicemotion", (e) => {
      const a = e.accelerationIncludingGravity || {};
      const g = e.rotationRate || {};
      _push("motion", {
        t: performance.now(),
        ax: a.x || 0, ay: a.y || 0, az: a.z || 0,
        gx: g.alpha || 0, gy: g.beta || 0, gz: g.gamma || 0,
      });
    }, { passive: true });

    // touch / tap / swipe
    window.addEventListener("pointerdown", (e) => {
      activeSwipe = [{ t: performance.now(), x: e.clientX, y: e.clientY }];
      _push("taps", {
        t: performance.now(), x: e.clientX, y: e.clientY,
        pressure: e.pressure || 0, radius: (e.width || 0) / 2,
      });
    }, { passive: true });

    window.addEventListener("pointermove", (e) => {
      if (!activeSwipe) return;
      activeSwipe.push({ t: performance.now(), x: e.clientX, y: e.clientY });
    }, { passive: true });

    window.addEventListener("pointerup", () => {
      if (activeSwipe && activeSwipe.length > 2) buffers.swipes.push(activeSwipe);
      activeSwipe = null;
    }, { passive: true });

    // scroll velocity
    let lastY = window.scrollY, lastT = performance.now();
    window.addEventListener("scroll", () => {
      const t = performance.now();
      const dy = window.scrollY - lastY;
      const dt = Math.max(t - lastT, 1);
      _push("scrolling", { t, dy, vy: dy / dt * 1000 });
      lastY = window.scrollY; lastT = t;
    }, { passive: true });

    // typing
    document.addEventListener("keydown", (e) => {
      _push("typing", { type: "down", key: e.key, t: performance.now() });
    });
    document.addEventListener("keyup", (e) => {
      _push("typing", { type: "up", key: e.key, t: performance.now() });
    });

    if (flushTimer) clearInterval(flushTimer);
    flushTimer = setInterval(flush, cfg.flushMs);
  }

  async function flush() {
    const hasData = Object.values(buffers).some((b) => b.length > 0);
    if (!hasData) return;
    const payload = {
      typing: buffers.typing.splice(0),
      scrolling: buffers.scrolling.splice(0),
      taps: buffers.taps.splice(0),
      swipes: buffers.swipes.splice(0),
      motion: buffers.motion.splice(0),
    };
    try {
      await fetch(cfg.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(cfg.token ? { "X-Session-Token": cfg.token } : {}),
        },
        body: JSON.stringify(payload),
        keepalive: true,
      });
    } catch (e) { /* offline -> drop, next flush will retry with new data */ }
  }

  BAS.Sensors = { start, flush, requestPermission, setToken, _cfg: cfg };
})(window);
