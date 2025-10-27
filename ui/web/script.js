(function(){
  // API immédiatement dispo
  window.setDyxtenParams = window.setDyxtenParams || function(_) {};

  const state = {
    camera: { camRadius:3.2, camHeightDeg:15, camTiltDeg:0, omegaDegPerSec:20, fov:600 },
    geometry: {
      topology:"uv_sphere",
      R:1.0, lat:64, lon:64, N:4096, phi_g:3.883222,
      R_major:1.2, r_minor:0.45,
      eps1:1.0, eps2:1.0, ax:1.0, ay:1.0, az:1.0,
      geo_level:1, mobius_w:0.4
    },
    appearance: {
      color:"#00C8FF", colors:"#00C8FF@0,#FFFFFF@1", opacity:1.0, px:2.0,
      palette:"uniform", paletteK:2,
      h0:200, dh:0, wh:0,
      blendMode:"source-over", shape:"circle",
      alphaDepth:0.0,
      noiseScale:1.0, noiseSpeed:0.0,
      pxModMode:"none", pxModAmp:0, pxModFreq:0, pxModPhaseDeg:0
    },
    dynamics: { rotX:0, rotY:0, rotZ:0, pulseA:0, pulseW:1, pulsePhaseDeg:0, rotPhaseMode:"none", rotPhaseDeg:0 },
    distribution: { pr:"uniform_area", dmin_px:0 },
    mask: { enabled:false, mode:"none", angleDeg:30, bandHalfDeg:20, lonCenterDeg:0, lonWidthDeg:30, softDeg:10, invert:false },
    system: { Nmax:50000, dprClamp:2.0, depthSort:true, transparent:true }
  };

  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d", { alpha: true });

  function resize(){
    const dpr = Math.max(1, Math.min(state.system.dprClamp || 2, window.devicePixelRatio || 1));
    canvas.width  = Math.floor(window.innerWidth  * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);

  // --------- Génération géométrie
  let basePoints = [];

  function gen_uv_sphere(R, lat, lon){
    const out = [];
    for(let i=0;i<lat;i++){
      const v=i/(lat-1), th=v*Math.PI;
      for(let j=0;j<lon;j++){
        const u=j/lon, ph=u*2*Math.PI;
        out.push({ x:R*Math.sin(th)*Math.cos(ph), y:R*Math.cos(th), z:R*Math.sin(th)*Math.sin(ph) });
      }
    }
    return out;
  }
  function gen_fibo_sphere(N, R, phi_g){
    const out=[]; const denom=Math.max(1,N-1);
    for(let i=0;i<N;i++){
      const z=1-2*i/denom; const r=Math.sqrt(Math.max(0,1-z*z)); const phi=i*phi_g;
      out.push({ x:R*r*Math.cos(phi), y:R*z, z:R*r*Math.sin(phi) });
    }
    return out;
  }
  function gen_disk_phyllo(N, R, phi_g){
    const out=[];
    for(let k=0;k<N;k++){
      const theta=k*phi_g; const r=R*Math.sqrt(k/Math.max(1,(N-1)));
      out.push({ x:r*Math.cos(theta), y:0, z:r*Math.sin(theta) });
    }
    return out;
  }
  function gen_torus(Rmaj, rmin, lat, lon, scaleR){
    const out=[];
    for(let i=0;i<lat;i++){
      const v=i/lat; const th=v*2*Math.PI;
      const cth=Math.cos(th), sth=Math.sin(th);
      const ring = Rmaj + rmin*cth;
      for(let j=0;j<lon;j++){
        const u=j/lon; const ph=u*2*Math.PI;
        const cph=Math.cos(ph), sph=Math.sin(ph);
        const x = (ring*cph) * scaleR;
        const y = (rmin*sth) * scaleR;
        const z = (ring*sph) * scaleR;
        out.push({x,y,z});
      }
    }
    return out;
  }
  function sgnpow(u, p){ const a=Math.abs(u); const e=2/Math.max(1e-6,p); return Math.sign(u)*Math.pow(a,e); }
  function gen_superquadric(R, eps1, eps2, ax, ay, az, lat, lon){
    const out=[];
    for(let i=0;i<lat;i++){
      const t = -0.5*Math.PI + (i/(lat-1))*Math.PI;
      for(let j=0;j<lon;j++){
        const ph = -Math.PI + (j/lon)*2*Math.PI;
        const ct = Math.cos(t), st=Math.sin(t);
        const cph=Math.cos(ph), sph=Math.sin(ph);
        const x = R * ax * sgnpow(cph, eps1) * sgnpow(ct, eps2);
        const y = R * ay * sgnpow(st,  eps2);
        const z = R * az * sgnpow(sph, eps1) * sgnpow(ct, eps2);
        out.push({x,y,z});
      }
    }
    return out;
  }
  function normScale(v, R){ const n=Math.hypot(v[0],v[1],v[2])||1; return [R*v[0]/n, R*v[1]/n, R*v[2]/n]; }
  function gen_geodesic(R, level){
    const t = (1 + Math.sqrt(5)) / 2;
    let verts = [
      [-1,  t,  0],[ 1,  t,  0],[-1, -t,  0],[ 1, -t,  0],
      [ 0, -1,  t],[ 0,  1,  t],[ 0, -1, -t],[ 0,  1, -t],
      [ t,  0, -1],[ t,  0,  1],[-t,  0, -1],[-t,  0,  1]
    ].map(v=>normScale(v, R));
    let faces = [
      [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
      [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
      [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
      [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]
    ];
    const midpointCache = new Map();
    function mid(a,b){
      const key = a<b ? `${a}-${b}` : `${b}-${a}`;
      if (midpointCache.has(key)) return midpointCache.get(key);
      const m = [(verts[a][0]+verts[b][0])/2,(verts[a][1]+verts[b][1])/2,(verts[a][2]+verts[b][2])/2];
      const idx = verts.push(normScale(m, R)) - 1;
      midpointCache.set(key, idx);
      return idx;
    }
    for(let l=0;l<level;l++){
      const nf=[]; midpointCache.clear();
      for(const f of faces){
        const [a,b,c]=f; const ab=mid(a,b), bc=mid(b,c), ca=mid(c,a);
        nf.push([a,ab,ca],[b,bc,ab],[c,ca,bc],[ab,bc,ca]);
      }
      faces = nf;
    }
    const out=[];
    for(const f of faces){
      const A=verts[f[0]], B=verts[f[1]], C=verts[f[2]];
      const x=(A[0]+B[0]+C[0])/3, y=(A[1]+B[1]+C[1])/3, z=(A[2]+B[2]+C[2])/3;
      const p = normScale([x,y,z], R); out.push({x:p[0],y:p[1],z:p[2]});
    }
    return out;
  }
  function gen_mobius(R, w, lat, lon){
    const out=[];
    for(let i=0;i<lon;i++){
      const u = i/lon * 2*Math.PI;
      for(let j=0;j<lat;j++){
        const v = -w/2 + (j/(lat-1))*w;
        const x = (R + v*Math.cos(u/2)) * Math.cos(u);
        const y = v * Math.sin(u/2);
        const z = (R + v*Math.cos(u/2)) * Math.sin(u);
        out.push({x,y,z});
      }
    }
    return out;
  }
  function rebuildGeometry(){
    const g=state.geometry;
    if(g.topology==="uv_sphere") basePoints=gen_uv_sphere(g.R,g.lat,g.lon);
    else if(g.topology==="fibo_sphere") basePoints=gen_fibo_sphere(Math.min(g.N,state.system.Nmax||g.N),g.R,g.phi_g);
    else if(g.topology==="disk_phyllotaxis") basePoints=gen_disk_phyllo(Math.min(g.N,state.system.Nmax||g.N),g.R,g.phi_g);
    else if(g.topology==="torus") basePoints=gen_torus(g.R_major, g.r_minor, g.lat, g.lon, g.R);
    else if(g.topology==="superquadric") basePoints=gen_superquadric(g.R, g.eps1, g.eps2, g.ax, g.ay, g.az, g.lat, g.lon);
    else if(g.topology==="geodesic") basePoints=gen_geodesic(g.R, g.geo_level|0);
    else if(g.topology==="mobius") basePoints=gen_mobius(g.R, g.mobius_w, g.lat, g.lon);
    else basePoints=gen_uv_sphere(g.R,g.lat,g.lon);
  }

  // --------- Utils
  const toRad = d => d*Math.PI/180;
  const clamp01 = x => Math.max(0, Math.min(1, x));

  function parseStops(s){
    // "#ff0@0,#0ff@0.5,#00f@1" → [{c:"#ff0",t:0},...], positions auto si omises
    const parts = (s||"").split(",").map(t=>t.trim()).filter(Boolean);
    if (parts.length===0) return [{c:"#00C8FF",t:0},{c:"#FFFFFF",t:1}];
    const raw = parts.map(p=>{
      const [c,pos] = p.split("@");
      const t = (pos===undefined || pos==="") ? null : Math.max(0, Math.min(1, parseFloat(pos)));
      return {c: c.trim(), t};
    });
    // distribue les nulls uniformément
    const withPos = [];
    let free = raw.filter(r=>r.t===null).length;
    let idx=0;
    for (const r of raw){
      if (r.t===null){ withPos.push({c:r.c, t: free>1 ? (idx/(free-1)) : (idx?1:0) }); idx++; }
      else withPos.push({c:r.c, t:r.t});
    }
    withPos.sort((a,b)=>a.t-b.t);
    // clamp et unique extrémités
    if (withPos[0].t>0) withPos.unshift({c:withPos[0].c, t:0});
    if (withPos[withPos.length-1].t<1) withPos.push({c:withPos[withPos.length-1].c, t:1});
    return withPos;
  }

  function hex2rgb(hx){ const x=hx.replace("#",""); const n=parseInt(x,16); return {r:(n>>16)&255,g:(n>>8)&255,b:n&255}; }
  function rgb2hsl(r,g,b){
    r/=255; g/=255; b/=255;
    const max=Math.max(r,g,b), min=Math.min(r,g,b);
    let h=0,s=0,l=(max+min)/2;
    if(max!==min){
      const d=max-min;
      s=l>0.5? d/(2-max-min): d/(max+min);
      switch(max){case r:h=(g-b)/d+(g<b?6:0);break;case g:h=(b-r)/d+2;break;case b:h=(r-g)/d+4;break;}
      h/=6;
    }
    return {h,s,l};
  }
  function hsl2rgb(h,s,l){
    function f(p,q,t){ if(t<0)t+=1; if(t>1)t-=1; if(t<1/6)return p+(q-p)*6*t; if(t<1/2)return q; if(t<2/3)return p+(q-p)*(2/3-t)*6; return p; }
    let r,g,b;
    if(s===0){ r=g=b=l; }
    else{
      const q = l < 0.5 ? l*(1+s) : l+s-l*s;
      const p = 2*l-q;
      r=f(p,q,h+1/3); g=f(p,q,h); b=f(p,q,h-1/3);
    }
    return {r:Math.round(r*255),g:Math.round(g*255),b:Math.round(b*255)};
  }
  function rgb2hex(r,g,b){ return "#"+((1<<24)+(r<<16)+(g<<8)+b).toString(16).slice(1).toUpperCase(); }
  function mix2(c1,c2,t){
    const a=hex2rgb(c1), b=hex2rgb(c2);
    const ah=rgb2hsl(a.r,a.g,a.b), bh=rgb2hsl(b.r,b.g,b.b);
    const h=ah.h*(1-t)+bh.h*t, s=ah.s*(1-t)+bh.s*t, l=ah.l*(1-t)+bh.l*t;
    const rr=hsl2rgb(h,s,l); return rgb2hex(rr.r,rr.g,rr.b);
  }
  function sampleGradient(stops, t){
    t = clamp01(t);
    for (let i=0;i<stops.length-1;i++){
      const a=stops[i], b=stops[i+1];
      if (t>=a.t && t<=b.t){
        const k = (t - a.t) / Math.max(1e-6, (b.t - a.t));
        return mix2(a.c, b.c, k);
      }
    }
    return stops[stops.length-1].c;
  }

  // bruit value 3D simple
  function hash3(ix,iy,iz){
    let n = ix*15731 + iy*789221 + iz*1376312589;
    n = (n<<13) ^ n;
    return (1.0 - ((n*(n*n*15731+789221)+1376312589) & 0x7fffffff) / 1073741824.0) * 0.5 + 0.5; // [0,1]
  }
  function valueNoise3(x,y,z){
    const xi=Math.floor(x), yi=Math.floor(y), zi=Math.floor(z);
    const xf=x-xi, yf=y-yi, zf=z-zi;
    function lerp(a,b,t){ return a + (b-a)*t; }
    function smooth(t){ return t*t*(3-2*t); }
    const c000=hash3(xi,yi,zi),     c100=hash3(xi+1,yi,zi);
    const c010=hash3(xi,yi+1,zi),   c110=hash3(xi+1,yi+1,zi);
    const c001=hash3(xi,yi,zi+1),   c101=hash3(xi+1,yi,zi+1);
    const c011=hash3(xi,yi+1,zi+1), c111=hash3(xi+1,yi+1,zi+1);
    const u=smooth(xf), v=smooth(yf), w=smooth(zf);
    const x00=lerp(c000,c100,u), x10=lerp(c010,c110,u), x01=lerp(c001,c101,u), x11=lerp(c011,c111,u);
    const y0=lerp(x00,x10,v), y1=lerp(x01,x11,v);
    return lerp(y0,y1,w);
  }

  function sphericalFromCartesian(x,y,z){
    const r = Math.hypot(x,y,z) || 1;
    const theta = Math.acos(y / r);                          // [0,π]
    const phi = (Math.atan2(z, x) + 2*Math.PI) % (2*Math.PI);// [0,2π)
    return {theta, phi};
  }

  // --------- Distribution poids + dmin écran
  function keepByDistribution(p3){
    const pr = state.distribution.pr || "uniform_area";
    if (pr==="uniform_area") return true;
    const R = state.geometry.R || 1;
    if (pr==="power_edge"){
      const rn = clamp01(Math.hypot(p3.x,p3.z)/Math.max(1e-6,R));
      return Math.random() <= rn;
    }
    if (pr==="gaussian_center"){
      const rn = clamp01(Math.hypot(p3.x,p3.z)/Math.max(1e-6,R));
      const s=0.4; const w=Math.exp(-(rn*rn)/(2*s*s));
      return Math.random() <= w;
    }
    const sph = sphericalFromCartesian(p3.x,p3.y,p3.z);
    if (pr==="by_lat"){
      const w = Math.sin(sph.theta); // max à l'équateur
      return Math.random() <= w;
    }
    if (pr==="by_lon"){
      const w = 0.5*(1+Math.cos(sph.phi)); // proche de phi=0
      return Math.random() <= w;
    }
    return true;
  }

  // --------- Animation
  let camThetaDeg = 0; let lastT = performance.now();

  function frame(now){
    const dt = Math.min(0.1, Math.max(0, (now - lastT)/1000)); lastT = now;
    camThetaDeg = (camThetaDeg + (state.camera.omegaDegPerSec||0)*dt) % 360;

    resize();
    const w=window.innerWidth, h=window.innerHeight, cx=w/2, cy=h/2;
    ctx.clearRect(0,0,w,h);
    ctx.globalCompositeOperation = state.appearance.blendMode || "source-over";

    if (state.system.transparent){ document.documentElement.style.background="transparent"; document.body.style.background="transparent"; }
    else { document.documentElement.style.background="#000"; document.body.style.background="#000"; }

    // Caméra
    const theta = toRad(camThetaDeg);
    const elev  = toRad(state.camera.camHeightDeg||0);
    const tilt  = toRad(state.camera.camTiltDeg||0);
    const Rcam  = state.camera.camRadius||3.2;
    const fov   = state.camera.fov||600;
    const cosT=Math.cos(theta), sinT=Math.sin(theta);
    const cosP=Math.cos(elev),  sinP=Math.cos(Math.PI/2 - elev) ? Math.sin(elev) : Math.sin(elev);
    const cosL=Math.cos(tilt),  sinL=Math.sin(tilt);
    const SCALE = 0.45*Math.min(w,h);

    const rotPhaseAmp = toRad(state.dynamics.rotPhaseDeg||0);
    const pulseA = state.dynamics.pulseA||0;
    const pulseW = state.dynamics.pulseW||0;
    const pulsePhi0 = toRad(state.dynamics.pulsePhaseDeg||0);

    const dmin = state.distribution.dmin_px || 0;
    const cell = Math.max(1, dmin);
    const grid = new Map();
    function screenKeep(sx, sy){
      if (dmin<=0) return true;
      const ix = Math.floor(sx/cell), iy = Math.floor(sy/cell);
      for(let dx=-1;dx<=1;dx++){
        for(let dy=-1;dy<=1;dy++){
          const k=(ix+dx)+"_"+(iy+dy);
          const arr=grid.get(k);
          if(!arr) continue;
          for(const q of arr){ if((sx-q.x)**2+(sy-q.y)**2 < dmin*dmin) return false; }
        }
      }
      const k=ix+"_"+iy;
      if(!grid.has(k)) grid.set(k,[]);
      grid.get(k).push({x:sx,y:sy});
      return true;
    }

    // items
    let items=[];
    for (let i=0;i<basePoints.length;i++){
      const bp = basePoints[i];
      if (!keepByDistribution(bp)) continue;

      // phase rot/pulse
      let phaseFactor = 0;
      if (state.dynamics.rotPhaseMode==="by_index"){
        phaseFactor = basePoints.length>1 ? i/(basePoints.length-1) : 0;
      } else if (state.dynamics.rotPhaseMode==="by_radius"){
        const R = state.geometry.R || 1; phaseFactor = clamp01(Math.hypot(bp.x,bp.z)/Math.max(1e-6,R));
      }
      const pulse = 1 + pulseA*Math.sin(pulseW*now*0.001 + pulsePhi0 + 2*Math.PI*phaseFactor);

      const angX = toRad(state.dynamics.rotX||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const angY = toRad(state.dynamics.rotY||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const angZ = toRad(state.dynamics.rotZ||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const cX=Math.cos(angX), sX=Math.sin(angX);
      const cY=Math.cos(angY), sY=Math.sin(angY);
      const cZ=Math.cos(angZ), sZ=Math.sin(angZ);

      let x = bp.x*pulse, y=bp.y*pulse, z=bp.z*pulse;
      // Rz, Rx, Ry
      let Xz=cZ*x - sZ*y; let Yz=sZ*x + cZ*y; let Zz=z;
      let Xx=Xz; let Yx=cX*Yz - sX*Zz; let Zx=sX*Yz + cX*Zz;
      let Xy=cY*Xx + sY*Zx; let Zy=-sY*Xx + cY*Zx; let Yy=Yx;

      // Caméra inverse
      let Xc=cosT*Xy - sinT*Zy; let Zc=sinT*Xy + cosT*Zy; let Yc=Yy;
      let Yc2=cosP*Yc - sinP*Zc; let Zc2=sinP*Yc + cosP*Zc;
      let Xc3=cosL*Xc - sinL*Yc2; let Yc3=sinL*Xc + cosL*Yc2; let Zc3=Zc2;

      const zcam = Zc3 + Rcam;
      const s = fov/(fov+zcam*SCALE);
      const sx = cx + Xc3*SCALE*s;
      const sy = cy - Yc3*SCALE*s;

      if (!screenKeep(sx, sy)) continue;

      // taille modulée
      let pxpf = 0;
      if (state.appearance.pxModMode==="by_index"){
        pxpf = basePoints.length>1 ? i/(basePoints.length-1) : 0;
      } else if (state.appearance.pxModMode==="by_radius"){
        const R = state.geometry.R || 1; pxpf = clamp01(Math.hypot(bp.x,bp.z)/Math.max(1e-6,R));
      }
      const basePx = state.appearance.px||2;
      const ampPx  = state.appearance.pxModAmp||0;
      const freqPx = state.appearance.pxModFreq||0;
      const phiPx0 = toRad(state.appearance.pxModPhaseDeg||0);
      const pxMod  = ampPx*Math.sin(2*Math.PI*freqPx*now*0.001 + phiPx0 + 2*Math.PI*pxpf);
      const r = Math.max(0.5, 1.2*s) * basePx * (1+pxMod);

      items.push({i, sx, sy, z:zcam, r, X:x, Y:y, Z:z});
    }

    if (state.system.depthSort) items.sort((a,b)=>b.z-a.z);

    // couleurs multi-stops et palettes
    const stops = parseStops(state.appearance.colors);
    function colorFromT(t){ return sampleGradient(stops, t); }

    function wrapHue(h){
      h %= 360;
      if (h < 0) h += 360;
      return h;
    }

    function hslFromParams(ap, factor, now, opts={}){
      const base = ap.h0 || 0;
      const delta = ap.dh || 0;
      const speed = ap.wh || 0;
      const normFactor = Math.max(-1, Math.min(1, factor || 0));
      const includeTime = opts.includeTime || false;
      const timeWeight = opts.timeWeight !== undefined ? opts.timeWeight : 1;
      const temporal = includeTime && speed !== 0 ? (delta * timeWeight * Math.sin(speed * now * 0.001)) : 0;
      const hue = wrapHue(base + delta * normFactor + temporal);
      return `hsl(${hue},75%,70%)`;
    }

    function pickColor(p, now){
      const ap=state.appearance, choice=ap.palette||"uniform";
      if (choice==="uniform") return ap.color || "#00C8FF";
      if (choice==="random_from_list") return stops[Math.floor(Math.random()*stops.length)].c || (ap.color||"#00C8FF");
      if (choice==="every_other"){
        const palette = [stops[0].c, (stops[1]||stops[0]).c];
        return palette[p.i % palette.length];
      }
      if (choice==="every_kth"){
        const K = Math.max(1, ap.paletteK|0);
        const idx = Math.floor(p.i / K) % stops.length;
        return stops[idx].c;
      }
      if (choice==="stripe_longitude"){
        const idx = Math.floor((p.i % 128)/16) % stops.length;
        return stops[idx].c;
      }
      if (choice==="hsl_time"){
        return hslFromParams(ap, 0, now, { includeTime: true });
      }
      if (choice==="directional"){
        const l = clamp01( (canvas.height/2 - p.sy) / Math.max(1,canvas.height) );
        const factor = l*2 - 1;
        return hslFromParams(ap, factor, now, { includeTime: true, timeWeight: 0.5 });
      }
      if (choice==="gradient_radial"){
        const dx=p.sx - canvas.width/2, dy=p.sy - canvas.height/2;
        const rn = clamp01(Math.hypot(dx,dy)/(0.5*Math.min(canvas.width,canvas.height)));
        return colorFromT(rn);
      }
      if (choice==="gradient_linear"){
        const t = clamp01( (p.sx - (canvas.width*0.25)) / Math.max(1,canvas.width*0.5) );
        return colorFromT(t);
      }
      if (choice==="by_lat" || choice==="by_lon"){
        const sph = sphericalFromCartesian(p.X, p.Y, p.Z);
        if (choice==="by_lat"){
          const t = 1 - (sph.theta/Math.PI); // 0 sud .. 1 nord
          const factor = t*2 - 1;
          return hslFromParams(ap, factor, now, { includeTime: true, timeWeight: 0.5 });
        } else {
          const t = (sph.phi)/(2*Math.PI);   // 0..1
          const factor = t*2 - 1;
          return hslFromParams(ap, factor, now, { includeTime: true, timeWeight: 0.5 });
        }
      }
      if (choice==="by_noise"){
        const sc = Math.max(0.05, ap.noiseScale||1);
        const sp = ap.noiseSpeed||0;
        const n = valueNoise3(p.X*sc + sp*now*0.001, p.Y*sc, p.Z*sc);
        return colorFromT(n);
      }
      return ap.color || "#00C8FF";
    }

    // masque géométrique (alpha multiplicatif)
    function maskWeight(p){
      const m = state.mask||{}; if (!m.enabled || m.mode==="none") return 1.0;
      const sph = sphericalFromCartesian(p.X, p.Y, p.Z);
      const deg = 180/Math.PI;
      const thetaDeg = sph.theta*deg;                    // 0..180
      let w = 1.0;
      if (m.mode==="north_cap"){
        const a=m.angleDeg||30, s=m.softDeg||10;
        const d = thetaDeg; // 0 au pôle nord
        w = 1 - smoothstep(a, a+s, d);
      } else if (m.mode==="south_cap"){
        const a=m.angleDeg||30, s=m.softDeg||10;
        const d = 180 - thetaDeg;
        w = 1 - smoothstep(a, a+s, d);
      } else if (m.mode==="equatorial_band"){
        const half=m.bandHalfDeg||20, s=m.softDeg||10;
        const d = Math.abs(thetaDeg - 90);
        w = 1 - smoothstep(half, half+s, d);
      } else if (m.mode==="longitudinal_band"){
        const center=(m.lonCenterDeg||0)*Math.PI/180, width=(m.lonWidthDeg||30)*Math.PI/180, s=(m.softDeg||10)*Math.PI/180;
        const dp = angDist(sph.phi, (center+2*Math.PI)%(2*Math.PI)); // distance angulaire à center
        w = 1 - smoothstep(width/2, width/2 + s, dp);
      }
      if (m.invert) w = 1 - w;
      return clamp01(w);
    }
    function smoothstep(e0,e1,x){ const t=clamp01((x-e0)/Math.max(1e-6,(e1-e0))); return t*t*(3-2*t); }
    function angDist(a,b){ let d=Math.abs(a-b); if (d>Math.PI) d=2*Math.PI-d; return d; }

    // alpha depth helper
    function depthAlpha(z){
      const ad = clamp01(state.appearance.alphaDepth||0);
      if (ad<=0) return 1.0;
      // s ∝ 1/(const + z), on réutilise projection s approximée via r déjà calculée → utiliser 1/(1+z_norm)
      // appro: map z à t in [0,1] via arctan
      const t = clamp01( Math.atan(Math.max(0,z))/ (Math.PI/2) );
      return (1-ad) + ad*(1 - t); // proche=1, loin→1-ad
    }

    // rendu
    for (const p of items){
      const col = pickColor(p, now);
      const aMask = maskWeight(p);
      const aDepth = depthAlpha(p.z);
      ctx.globalAlpha = clamp01((state.appearance.opacity||1) * aMask * aDepth);
      ctx.fillStyle = col;
      if ((state.appearance.shape||"circle")==="square"){
        const s = p.r;
        ctx.fillRect(p.sx - s, p.sy - s, 2*s, 2*s);
      } else {
        ctx.beginPath(); ctx.arc(p.sx,p.sy,p.r,0,Math.PI*2); ctx.fill();
      }
    }

    requestAnimationFrame(frame);
  }

  window.setDyxtenParams = function(obj){
    for (const k of Object.keys(obj)){
      if (state[k] && typeof obj[k] === "object") Object.assign(state[k], obj[k]);
    }
    if (state.system.transparent){ document.documentElement.style.background="transparent"; document.body.style.background="transparent"; }
    else { document.documentElement.style.background="#000"; document.body.style.background="#000"; }
    rebuildGeometry();
  };

  resize(); rebuildGeometry(); requestAnimationFrame(frame);
})();
