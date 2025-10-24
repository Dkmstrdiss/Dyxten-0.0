// Sphere fixe, couleur unie, axes alignés (aucune rotation ni pulsation).
(function () {
  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d", { alpha: true });

  // Plein écran + DPI
  function resize() {
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const cssW = window.innerWidth, cssH = window.innerHeight;
    canvas.width  = Math.max(1, Math.floor(cssW * dpr));
    canvas.height = Math.max(1, Math.floor(cssH * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // Paramètres fixes
  const cfg = {
    lat: 64,            // densité verticale
    lon: 64,            // densité horizontale
    R: 1.0,             // rayon unité
    px: 2.0,            // taille point
    camZ: 3.0,          // caméra sur l’axe Z
    fov: 600,           // projection
    color: "#20D0FF"    // COULEUR UNIE
  };

  // Maillage sphère (aucun déphasage, alignement vertical garanti)
  const pts = [];
  for (let i = 0; i < cfg.lat; i++) {
    const v = i / (cfg.lat - 1);          // 0..1
    const theta = v * Math.PI;            // 0..π  (pôles sur l’axe vertical Y)
    for (let j = 0; j < cfg.lon; j++) {
      const u = j / cfg.lon;              // 0..1
      const phi = u * Math.PI * 2;        // 0..2π
      const x = cfg.R * Math.sin(theta) * Math.cos(phi);
      const y = cfg.R * Math.cos(theta);
      const z = cfg.R * Math.sin(theta) * Math.sin(phi);
      pts.push({ x, y, z, zsort: 0 });
    }
  }

  // AUCUNE rotation ni pulsation
  function frame() {
    const w = window.innerWidth, h = window.innerHeight;
    const cx = w * 0.5, cy = h * 0.5;
    ctx.clearRect(0, 0, w, h);

    // Échelle auto pour remplir sans couper
    const SCALE = 0.45 * Math.min(w, h);

    // Projection simple sur Z
    const list = pts;
    for (let k = 0; k < list.length; k++) {
      const p = list[k];
      const zc = p.z + cfg.camZ;
      const s = cfg.fov / (cfg.fov + zc * SCALE);
      const X = cx + p.x * SCALE * s;
      const Y = cy - p.y * SCALE * s;
      p.px = X; p.py = Y; p.r = Math.max(0.5, 1.2 * s) * cfg.px; p.zsort = zc;
    }

    // Peinture dos→face
    list.sort((a, b) => b.zsort - a.zsort);

    ctx.fillStyle = cfg.color;  // couleur unie
    for (let i = 0; i < list.length; i++) {
      const q = list[i];
      ctx.beginPath();
      ctx.arc(q.px, q.py, q.r, 0, Math.PI * 2);
      ctx.fill();
    }

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
