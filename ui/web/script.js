(function(){
  // --- paramètres caméra exposés dès le début ---
  let camHeightDeg = 15;
  let camTiltDeg   = 0;
  let omegaDegPerSec = 20;

  // API appelée par PyQt (toujours définie)
  window.setCameraParams = function(hDeg, tDeg, speedDeg){
    camHeightDeg   = +hDeg;
    camTiltDeg     = +tDeg;
    omegaDegPerSec = Math.max(0, +speedDeg);
  };

  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d", { alpha: true });

  function resize(){
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    canvas.width  = window.innerWidth  * dpr;
    canvas.height = window.innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  const cfg = { lat:64, lon:64, R:1.0, px:2.0, fov:600, camRadius:3.2, color:"#00C8FF" };

  // Maillage sphère
  const pts=[];
  for(let i=0;i<cfg.lat;i++){
    const v=i/(cfg.lat-1), th=v*Math.PI;
    for(let j=0;j<cfg.lon;j++){
      const u=j/cfg.lon, ph=u*Math.PI*2;
      pts.push({
        x: cfg.R*Math.sin(th)*Math.cos(ph),
        y: cfg.R*Math.cos(th),
        z: cfg.R*Math.sin(th)*Math.sin(ph)
      });
    }
  }

  let camThetaDeg = 0;
  let lastT = performance.now();
  const toRad = d => d*Math.PI/180;

  function frame(now){
    const dt = (now - lastT) / 1000; lastT = now;
    camThetaDeg = (camThetaDeg + omegaDegPerSec * dt) % 360;

    const theta=toRad(camThetaDeg), elev=toRad(camHeightDeg), tilt=toRad(camTiltDeg);
    const w=window.innerWidth, h=window.innerHeight, cx=w/2, cy=h/2;
    ctx.clearRect(0,0,w,h);

    const SCALE=0.45*Math.min(w,h);
    const cosT=Math.cos(theta), sinT=Math.sin(theta);
    const cosP=Math.cos(elev),  sinP=Math.sin(elev);
    const cosL=Math.cos(tilt),  sinL=Math.sin(tilt);

    const list=[];
    for(const q of pts){
      let X =  cosT*q.x - sinT*q.z;
      let Z =  sinT*q.x + cosT*q.z;
      let Y =  q.y;

      let Y2 =  cosP*Y - sinP*Z;
      let Z2 =  sinP*Y + cosP*Z;

      let X3 =  cosL*X - sinL*Y2;
      let Y3 =  sinL*X + cosL*Y2;
      let Z3 =  Z2;

      const zc = Z3 + cfg.camRadius;
      const s  = cfg.fov/(cfg.fov+zc*SCALE);
      list.push({ x:cx+X3*SCALE*s, y:cy-Y3*SCALE*s, z:zc, r:Math.max(0.5,1.2*s)*cfg.px });
    }

    list.sort((a,b)=>b.z-a.z);
    ctx.fillStyle = cfg.color;
    for(const p of list){ ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fill(); }

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
