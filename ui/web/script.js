(function(){
  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d", { alpha: true });

  // --- sizing fiable: couvre la fenêtre, gère DPR, centré dès le 1er frame
  function sizeToContainer() {
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    canvas.width  = Math.max(1, Math.round(rect.width  * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  const ro = new ResizeObserver(sizeToContainer);
  ro.observe(document.getElementById("canvas-wrap"));
  sizeToContainer(); // important: avant premier dessin

  // --- config sphère
  const cfg = {
    latSteps: 64, lonSteps: 64, R: 1.0,
    pointPx: 2.0, fov: 600, camZ: 3.2,
    rotX: 0.15, rotY: 0.25, rotZ: 0.35,
    phaseX: 0.0020, phaseY: 0.0015, phaseZ: 0.0025,
    colorSpeed: 0.0075, pulseAmp: 0.06, pulseSpeed: 1.4
  };

  // points sphère
  const pts = [];
  for (let i=0;i<cfg.latSteps;i++){
    const v = i/(cfg.latSteps-1), th = v*Math.PI;
    for (let j=0;j<cfg.lonSteps;j++){
      const u = j/cfg.lonSteps, ph = u*Math.PI*2;
      const x = cfg.R*Math.sin(th)*Math.cos(ph);
      const y = cfg.R*Math.cos(th);
      const z = cfg.R*Math.sin(th)*Math.sin(ph);
      pts.push({x,y,z,slice:i,idx:i*cfg.lonSteps+j});
    }
  }

  // rotations
  const rx=(p,a)=>({x:p.x, y:p.y*Math.cos(a)-p.z*Math.sin(a), z:p.y*Math.sin(a)+p.z*Math.cos(a)});
  const ry=(p,a)=>({x:p.x*Math.cos(a)+p.z*Math.sin(a), y:p.y, z:-p.x*Math.sin(a)+p.z*Math.cos(a)});
  const rz=(p,a)=>({x:p.x*Math.cos(a)-p.y*Math.sin(a), y:p.x*Math.sin(a)+p.y*Math.cos(a), z:p.z});

  let t0 = performance.now();

  function frame(t){
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const cx = w*0.5, cy = h*0.5;
    // fond transparent: pas de fillRect noir/blanc
    ctx.clearRect(0,0,w,h);

    const ax = t*0.001*cfg.rotX, ay = t*0.001*cfg.rotY, az = t*0.001*cfg.rotZ;
    const pulse = 1.0 + cfg.pulseAmp*Math.sin(t*0.001*(Math.PI*cfg.pulseSpeed));

    const P = [];
    for (let k=0;k<pts.length;k++){
      const p0 = pts[k];
      let p = {x:p0.x*pulse, y:p0.y*pulse, z:p0.z*pulse};
      p = rx(p, ax + p0.slice*cfg.phaseX);
      p = ry(p, ay + p0.slice*cfg.phaseY);
      p = rz(p, az + p0.slice*cfg.phaseZ);

      const zc = p.z + cfg.camZ;
      const scale = cfg.fov / (cfg.fov + zc*300);
      const x2 = cx + p.x*300*scale;
      const y2 = cy - p.y*300*scale;

      const hue = (Math.sin(t*0.75*0.01 + p0.idx*0.001)*0.5+0.5)*360;
      const r = Math.max(0.5, 1.4*scale)*cfg.pointPx;
      P.push({x:x2,y:y2,z:zc,r,hue});
    }
    P.sort((a,b)=>b.z-a.z);

    for (let i=0;i<P.length;i++){
      const q=P[i];
      ctx.beginPath();
      ctx.fillStyle=`hsl(${q.hue.toFixed(1)},75%,75%)`;
      ctx.arc(q.x,q.y,q.r,0,Math.PI*2);
      ctx.fill();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
