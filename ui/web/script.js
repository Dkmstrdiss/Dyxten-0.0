(function(){
  // API immédiatement dispo
  window.setDyxtenParams = window.setDyxtenParams || function(_) {};

  const state = {
    camera: { camRadius:3.2, camHeightDeg:15, camTiltDeg:0, omegaDegPerSec:20, fov:600 },
    geometry: {
      topology:"uv_sphere",
      R:1.0, lat:64, lon:64, N:4096, phi_g:3.883222,
      R_major:1.2, R_major2:0.8, r_minor:0.45,
      eps1:1.0, eps2:1.0, ax:1.0, ay:1.0, az:1.0,
      geo_level:1, mobius_w:0.4,
      arch_a:0.0, arch_b:0.6, theta_max:6.28318,
      log_a:0.2, log_b:0.15,
      rose_k:4.0,
      sf2_m:6.0, sf2_a:1.0, sf2_b:1.0, sf2_n1:0.5, sf2_n2:0.5, sf2_n3:0.5,
      density_pdf:"1",
      poisson_dmin:0.05,
      lissajous_a:3, lissajous_b:2, lissajous_phase:0.0,
      vogel_k:2.3999632,
      se_n1:1.0, se_n2:1.0,
      half_height:1.0,
      noisy_amp:0.1, noisy_freq:3.0, noisy_gain:1.0, noisy_omega:0.0,
      sph_terms:"2,0,0.4;3,2,0.2",
      weight_map:"1",
      torus_knot_p:3, torus_knot_q:2,
      strip_w:0.4, strip_n:2,
      blob_noise_amp:0.25, blob_noise_scale:2.0,
      gyroid_scale:1.0, gyroid_thickness:0.05, gyroid_c:0.0,
      schwarz_scale:1.0, schwarz_iso:0.0,
      heart_scale:1.0,
      polyhedron_data:"",
      poly_layers:1,
      poly_link_steps:0,
      metaballs_centers:"0,0,0",
      metaballs_radii:"0.6",
      metaballs_iso:1.0,
      df_ops:"sphere(1.0)",
      sf3_m1:3.0, sf3_m2:3.0, sf3_m3:3.0,
      sf3_n1:0.5, sf3_n2:0.5, sf3_n3:0.5,
      sf3_a:1.0, sf3_b:1.0, sf3_scale:1.0,
      helix_r:0.4, helix_pitch:0.3, helix_turns:3.0,
      lissajous3d_Ax:1.0, lissajous3d_Ay:1.0, lissajous3d_Az:1.0,
      lissajous3d_wx:3, lissajous3d_wy:2, lissajous3d_wz:5,
      lissajous3d_phi:0.0,
      viviani_a:1.0,
      lic_N:12, lic_steps:180, lic_h:0.05,
      stream_N:12, stream_steps:220,
      geo_graph_level:2,
      rgg_nodes:400, rgg_radius:0.2,
      rings_count:5, ring_points:96,
      hex_step:0.2, hex_nx:12, hex_ny:12,
      voronoi_N:50, voronoi_bbox:"-1,1,-1,1"
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
    dynamics: { rotX:0, rotY:0, rotZ:0, rotXMax:360, rotYMax:360, rotZMax:360,
      orientXDeg:0, orientYDeg:0, orientZDeg:0,
      pulseA:0, pulseW:1, pulsePhaseDeg:0, rotPhaseMode:"none", rotPhaseDeg:0 },
    distribution: {
      densityMode:"uniform",
      sampler:"direct",
      dmin:0,
      dmin_px:0,
      maskMode:"none",
      maskSoftness:0.2,
      maskAnimate:0,
      noiseDistortion:0,
      densityPulse:0,
      clusterCount:1,
      clusterSpread:0,
      repelForce:0,
      noiseWarp:0,
      fieldFlow:0,
      pr:"uniform_area"
    },
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

  function clampCount(n){
    const cap = state.system.Nmax;
    return Math.min(n, cap && cap>0 ? cap : n);
  }

  function sgnpow(u, p){ const a=Math.abs(u); const e=2/Math.max(1e-6,p); return Math.sign(u)*Math.pow(a,e); }

  function parseNumberList(str){
    return (str || "").split(/[,;\s]+/).map(v=>parseFloat(v)).filter(v=>Number.isFinite(v));
  }

  function parseVectorList(str){
    const tokens = (str||"").split(/;|\n/).map(s=>s.trim()).filter(Boolean);
    if (tokens.length===0){
      const flat = parseNumberList(str);
      if (flat.length>=3) return [flat.slice(0,3)];
      return [];
    }
    return tokens.map(t=>{
      const vals = t.split(/[,\s]+/).map(v=>parseFloat(v)).filter(v=>Number.isFinite(v));
      while(vals.length<3) vals.push(0);
      return vals.slice(0,3);
    });
  }

  function evalExpression(expr, vars){
    if (!expr || !expr.trim()) return 1;
    try {
      const keys = Object.keys(vars);
      const values = keys.map(k=>vars[k]);
      // eslint-disable-next-line no-new-func
      const fn = new Function(...keys, "with(Math){return (" + expr + ");}");
      const res = fn(...values);
      return Number.isFinite(res) ? res : 0;
    } catch (err) {
      console.warn("Expression error", expr, err);
      return 0;
    }
  }

  function normScale(v, R){ const n=Math.hypot(v[0],v[1],v[2])||1; return [R*v[0]/n, R*v[1]/n, R*v[2]/n]; }

  function gen_uv_sphere(R, lat, lon){
    const out = [];
    const latSteps = Math.max(2, lat|0);
    const lonSteps = Math.max(3, lon|0);
    for(let i=0;i<latSteps;i++){
      const v=i/(latSteps-1); const th=v*Math.PI;
      for(let j=0;j<lonSteps;j++){
        const u=j/lonSteps; const ph=u*2*Math.PI;
        out.push({ x:R*Math.sin(th)*Math.cos(ph), y:R*Math.cos(th), z:R*Math.sin(th)*Math.sin(ph) });
      }
    }
    return out;
  }

  function gen_fibo_sphere(N, R, phi_g){
    const count = clampCount(Math.max(1, N|0));
    const out=[]; const denom=Math.max(1,count-1);
    for(let i=0;i<count;i++){
      const z=1-2*i/denom; const r=Math.sqrt(Math.max(0,1-z*z)); const phi=i*phi_g;
      out.push({ x:R*r*Math.cos(phi), y:R*z, z:R*r*Math.sin(phi) });
    }
    return out;
  }

  function gen_disk_phyllo(N, R, phi_g){
    const count = clampCount(Math.max(1, N|0));
    const out=[];
    for(let k=0;k<count;k++){
      const theta=k*phi_g; const r=R*Math.sqrt(k/Math.max(1,(count-1)));
      out.push({ x:r*Math.cos(theta), y:0, z:r*Math.sin(theta) });
    }
    return out;
  }

  function gen_archimede_spiral(g){
    const count = clampCount(Math.max(2, g.N|0));
    const tmax = Math.max(0.1, g.theta_max || (Math.PI*6));
    const denom = g.arch_a + g.arch_b * tmax;
    const scale = denom !== 0 ? g.R / Math.abs(denom) : g.R;
    const out=[];
    for(let i=0;i<count;i++){
      const t = count===1 ? 0 : (tmax * i/(count-1));
      const r = Math.abs(g.arch_a + g.arch_b * t) * scale;
      out.push({x:r*Math.cos(t), y:0, z:r*Math.sin(t)});
    }
    return out;
  }

  function gen_log_spiral(g){
    const count = clampCount(Math.max(2, g.N|0));
    const tmax = Math.max(0.1, g.theta_max || (Math.PI*6));
    const base = Math.exp(g.log_b * tmax);
    const scale = base !== 0 ? g.R / (g.log_a * base) : g.R;
    const out=[];
    for(let i=0;i<count;i++){
      const t = count===1 ? 0 : (tmax * i/(count-1));
      const r = Math.abs(g.log_a * Math.exp(g.log_b * t)) * scale;
      out.push({x:r*Math.cos(t), y:0, z:r*Math.sin(t)});
    }
    return out;
  }

  function gen_rose_curve(g){
    const count = clampCount(Math.max(2, g.N|0));
    const tmax = Math.max(0.1, g.theta_max || (2*Math.PI));
    const out=[];
    for(let i=0;i<count;i++){
      const t = count===1 ? 0 : (tmax * i/(count-1));
      const r = Math.abs(Math.cos(g.rose_k * t)) * g.R;
      out.push({x:r*Math.cos(t), y:0, z:r*Math.sin(t)});
    }
    return out;
  }

  function superformula2D(theta, m, a, b, n1, n2, n3){
    const t1 = Math.pow(Math.abs(Math.cos((m*theta)/4)/a), n2);
    const t2 = Math.pow(Math.abs(Math.sin((m*theta)/4)/b), n3);
    return Math.pow(t1 + t2, -1/Math.max(1e-6, n1));
  }

  function gen_superformula_2D(g){
    const count = clampCount(Math.max(2, g.N|0));
    const out=[];
    for(let i=0;i<count;i++){
      const t = (i/count)*2*Math.PI;
      const r = g.R * superformula2D(t, g.sf2_m, g.sf2_a, g.sf2_b, g.sf2_n1, g.sf2_n2, g.sf2_n3);
      out.push({x:r*Math.cos(t), y:0, z:r*Math.sin(t)});
    }
    return out;
  }

  function gen_density_warp(g){
    const count = clampCount(Math.max(1, g.N|0));
    const out=[];
    let attempts = 0;
    const maxAttempts = count * 20;
    while(out.length < count && attempts < maxAttempts){
      attempts++;
      const u = Math.random();
      const r = Math.sqrt(u);
      const pdf = Math.max(0, evalExpression(g.density_pdf, {r, u}));
      if (!pdf) continue;
      const accept = Math.random();
      if (accept > clamp01(pdf)) continue;
      const theta = Math.random()*2*Math.PI;
      const radius = g.R * r;
      out.push({x:radius*Math.cos(theta), y:0, z:radius*Math.sin(theta)});
    }
    return out;
  }

  function gen_poisson_disk(g){
    const count = clampCount(Math.max(1, g.N|0));
    const out=[]; const minDist = Math.max(0, g.poisson_dmin) * g.R;
    const radius = g.R;
    let tries = 0; const maxTries = count * 50;
    while(out.length < count && tries < maxTries){
      tries++;
      const r = radius * Math.sqrt(Math.random());
      const theta = Math.random()*2*Math.PI;
      const p = {x:r*Math.cos(theta), y:0, z:r*Math.sin(theta)};
      let ok = true;
      for(const q of out){
        const dx=p.x-q.x, dz=p.z-q.z;
        if (dx*dx + dz*dz < minDist*minDist){ ok=false; break; }
      }
      if (ok) out.push(p);
    }
    return out;
  }

  function gen_lissajous_disk(g){
    const count = clampCount(Math.max(2, g.N|0));
    const out=[];
    const a = Math.max(1, g.lissajous_a|0);
    const b = Math.max(1, g.lissajous_b|0);
    for(let i=0;i<count;i++){
      const t = (i/count)*2*Math.PI;
      const x = Math.cos(a*t + g.lissajous_phase);
      const z = Math.sin(b*t);
      out.push({x:g.R*x, y:0, z:g.R*z});
    }
    return out;
  }

  function gen_torus(Rmaj, rmin, lat, lon, scaleR){
    const out=[];
    const latSteps = Math.max(3, lat|0);
    const lonSteps = Math.max(3, lon|0);
    for(let i=0;i<latSteps;i++){
      const v=i/latSteps; const th=v*2*Math.PI;
      const cth=Math.cos(th), sth=Math.sin(th);
      const ring = Rmaj + rmin*cth;
      for(let j=0;j<lonSteps;j++){
        const u=j/lonSteps; const ph=u*2*Math.PI;
        const cph=Math.cos(ph), sph=Math.sin(ph);
        const x = (ring*cph) * scaleR;
        const y = (rmin*sth) * scaleR;
        const z = (ring*sph) * scaleR;
        out.push({x,y,z});
      }
    }
    return out;
  }

  function gen_superquadric(R, eps1, eps2, ax, ay, az, lat, lon){
    const out=[];
    const latSteps = Math.max(3, lat|0);
    const lonSteps = Math.max(3, lon|0);
    for(let i=0;i<latSteps;i++){
      const t = -0.5*Math.PI + (i/(latSteps-1))*Math.PI;
      for(let j=0;j<lonSteps;j++){
        const ph = -Math.PI + (j/lonSteps)*2*Math.PI;
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

  function gen_superellipsoid(g){
    return gen_superquadric(g.R, g.se_n1, g.se_n2, g.ax, g.ay, g.az, g.lat, g.lon);
  }

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
    for(let l=0;l<(level|0);l++){
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

  function gen_vogel_sphere(g){
    const count = clampCount(Math.max(1, g.N|0));
    const out=[];
    for(let i=0;i<count;i++){
      const z = 1 - 2*(i+0.5)/count;
      const r = Math.sqrt(Math.max(0,1-z*z));
      const phi = i * g.vogel_k;
      out.push({x:g.R*r*Math.cos(phi), y:g.R*z, z:g.R*r*Math.sin(phi)});
    }
    return out;
  }

  function gen_half_sphere(g){
    const pts = gen_uv_sphere(g.R, g.lat, g.lon);
    return pts.filter(p=>p.y>=0).map(p=>({x:p.x, y:p.y*g.half_height, z:p.z}));
  }

  function gen_noisy_sphere(g){
    const latSteps = Math.max(3, g.lat|0);
    const lonSteps = Math.max(3, g.lon|0);
    const out=[];
    for(let i=0;i<latSteps;i++){
      const theta = i/(latSteps-1)*Math.PI;
      for(let j=0;j<lonSteps;j++){
        const phi = j/lonSteps*2*Math.PI;
        const noise = g.noisy_amp * (Math.sin(g.noisy_freq*theta + g.noisy_omega) + g.noisy_gain*Math.cos(g.noisy_freq*phi));
        const radius = g.R * (1 + noise);
        out.push({
          x:radius*Math.sin(theta)*Math.cos(phi),
          y:radius*Math.cos(theta),
          z:radius*Math.sin(theta)*Math.sin(phi)
        });
      }
    }
    return out;
  }

  function associatedLegendre(l, m, x){
    m = Math.abs(m);
    let pmm = 1.0;
    if (m>0){
      const somx2 = Math.sqrt((1-x)*(1+x));
      let fact = 1.0;
      for(let i=1;i<=m;i++){
        pmm *= -fact * somx2;
        fact += 2;
      }
    }
    if (l===m) return pmm;
    let pmmp1 = x*(2*m+1)*pmm;
    if (l===m+1) return pmmp1;
    let pll = 0;
    for(let ll=m+2; ll<=l; ll++){
      pll = ((2*ll-1)*x*pmmp1 - (ll+m-1)*pmm)/(ll-m);
      pmm = pmmp1;
      pmmp1 = pll;
    }
    return pll;
  }

  function sphericalHarmonicReal(l, m, theta, phi){
    const absM = Math.abs(m);
    const norm = Math.sqrt(((2*l+1)/(4*Math.PI)) * (factorial(l-absM)/factorial(l+absM)));
    const plm = associatedLegendre(l, absM, Math.cos(theta));
    if (m>0) return Math.sqrt(2) * norm * plm * Math.cos(absM*phi);
    if (m<0) return Math.sqrt(2) * norm * plm * Math.sin(absM*phi);
    return norm * plm;
  }

  function factorial(n){
    let v = 1;
    for(let i=2;i<=n;i++) v*=i;
    return v;
  }

  function parseSphericalTerms(str){
    return (str||"").split(/;|\n/).map(s=>s.trim()).filter(Boolean).map(part=>{
      const vals = part.split(/[,\s]+/).map(Number).filter(Number.isFinite);
      if (vals.length>=2) return {l:vals[0]|0, m:vals[1]|0, a:vals[2]||0, p:vals[3]||0};
      return null;
    }).filter(Boolean);
  }

  function gen_spherical_harmonics(g){
    const latSteps = Math.max(8, g.lat|0);
    const lonSteps = Math.max(8, g.lon|0);
    const terms = parseSphericalTerms(g.sph_terms);
    const out=[];
    for(let i=0;i<latSteps;i++){
      const theta = i/(latSteps-1)*Math.PI;
      for(let j=0;j<lonSteps;j++){
        const phi = j/lonSteps*2*Math.PI;
        let r = g.R;
        for(const term of terms){
          const h = sphericalHarmonicReal(term.l, term.m, theta, phi);
          r += g.R * term.a * h;
        }
        out.push({
          x:r*Math.sin(theta)*Math.cos(phi),
          y:r*Math.cos(theta),
          z:r*Math.sin(theta)*Math.sin(phi)
        });
      }
    }
    return out;
  }

  function gen_weighted_sphere(g){
    const count = clampCount(Math.max(1, g.N|0));
    const samples = 200;
    let maxW = 0;
    for(let i=0;i<samples;i++){
      const theta = Math.random()*Math.PI;
      const phi = Math.random()*2*Math.PI;
      const w = Math.max(0, evalExpression(g.weight_map, {theta, phi}));
      if (w>maxW) maxW = w;
    }
    maxW = maxW || 1;
    const out=[];
    let attempts = 0;
    const maxAttempts = count * 40;
    while(out.length < count && attempts < maxAttempts){
      attempts++;
      const theta = Math.random()*Math.PI;
      const phi = Math.random()*2*Math.PI;
      const w = Math.max(0, evalExpression(g.weight_map, {theta, phi})) / maxW;
      if (Math.random() > clamp01(w)) continue;
      out.push({
        x:g.R*Math.sin(theta)*Math.cos(phi),
        y:g.R*Math.cos(theta),
        z:g.R*Math.sin(theta)*Math.sin(phi)
      });
    }
    return out;
  }

  function gen_double_torus(g){
    const primary = gen_torus(g.R_major, g.r_minor, g.lat, g.lon, g.R);
    const secondary = gen_torus(g.R_major2, g.r_minor, g.lat, g.lon, g.R);
    return primary.concat(secondary);
  }

  function gen_torus_knot(g){
    const count = clampCount(Math.max(50, g.N|0));
    const p = Math.max(1, g.torus_knot_p|0);
    const q = Math.max(1, g.torus_knot_q|0);
    const out=[];
    const total = 2*Math.PI*p;
    for(let i=0;i<count;i++){
      const t = total * i/count;
      const cosq = Math.cos(q*t/p);
      const sinq = Math.sin(q*t/p);
      const x = (g.R_major + g.r_minor * cosq) * Math.cos(t);
      const y = (g.R_major + g.r_minor * cosq) * Math.sin(t);
      const z = g.r_minor * sinq;
      out.push({x:x*g.R, y:y*g.R, z:z*g.R});
    }
    return out;
  }

  function gen_strip_twist(g){
    const latSteps = Math.max(3, g.lat|0);
    const lonSteps = Math.max(20, g.lon|0);
    const out=[];
    const halfW = g.strip_w/2;
    for(let i=0;i<lonSteps;i++){
      const u = i/lonSteps * 2*Math.PI;
      for(let j=0;j<latSteps;j++){
        const v = -halfW + (j/(latSteps-1))*g.strip_w;
        const angle = g.strip_n * u / 2;
        const x = (g.R + v*Math.cos(angle)) * Math.cos(u);
        const y = v * Math.sin(angle);
        const z = (g.R + v*Math.cos(angle)) * Math.sin(u);
        out.push({x,y,z});
      }
    }
    return out;
  }

  function gen_klein_bottle(g){
    const latSteps = Math.max(3, g.lat|0);
    const lonSteps = Math.max(3, g.lon|0);
    const out=[];
    for(let i=0;i<lonSteps;i++){
      const v = i/lonSteps * 2*Math.PI;
      for(let j=0;j<latSteps;j++){
        const u = j/latSteps * 2*Math.PI;
        const x = (g.R_major + g.r_minor*Math.cos(u/2)*Math.sin(v) - g.r_minor*Math.sin(u/2)*Math.sin(2*v)) * Math.cos(u);
        const y = (g.R_major + g.r_minor*Math.cos(u/2)*Math.sin(v) - g.r_minor*Math.sin(u/2)*Math.sin(2*v)) * Math.sin(u);
        const z = g.r_minor*Math.sin(u/2)*Math.sin(v) + g.r_minor*Math.cos(u/2)*Math.sin(2*v);
        out.push({x,y,z});
      }
    }
    return out;
  }

  const platonic = {
    tetrahedron: () => {
      const s = Math.sqrt(2/3);
      return [
        [ s,  0, -1/Math.sqrt(3)],
        [-s,  0, -1/Math.sqrt(3)],
        [0,  s,  1/Math.sqrt(3)],
        [0, -s,  1/Math.sqrt(3)],
      ];
    },
    cube: () => {
      const pts=[];
      for(const sx of [-1,1]) for(const sy of [-1,1]) for(const sz of [-1,1]) pts.push([sx,sy,sz]);
      return pts;
    },
    octahedron: () => [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],
    icosahedron: () => {
      const t = (1 + Math.sqrt(5)) / 2;
      return [
        [-1,  t,  0],[ 1,  t,  0],[-1, -t,  0],[ 1, -t,  0],
        [ 0, -1,  t],[ 0,  1,  t],[ 0, -1, -t],[ 0,  1, -t],
        [ t,  0, -1],[ t,  0,  1],[-t,  0, -1],[-t,  0,  1]
      ];
    },
    dodecahedron: () => {
      const phi = (1 + Math.sqrt(5))/2;
      const a = 1/phi; const b = 1;
      const pts=[];
      for(const sx of [-1,1]) for(const sy of [-1,1]) for(const sz of [-1,1]) pts.push([sx, sy, sz]);
      for(const sx of [-1,1]) for(const sy of [-1,1]){
        pts.push([0, sx*a, sy*phi]);
        pts.push([sx*a, sy*phi, 0]);
        pts.push([sx*phi, 0, sy*a]);
      }
      return pts;
    }
  };

  function scaleVectors(list, R){
    return list.map(v=>{ const p=normScale(v,R); return {x:p[0],y:p[1],z:p[2]}; });
  }

  function gen_truncated_icosa(g){
    const icoVerts = platonic.icosahedron();
    const edges = new Set();
    const faces = [
      [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
      [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
      [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
      [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]
    ];
    const mix = (a,b,t) => a + (b-a)*t;
    const ratio = Math.min(0.45, Math.max(0.05, g.trunc_ratio ?? 0.333));
    for(const [a,b,c] of faces){
      const add = (u,v) => {
        const key = u<v ? `${u}-${v}` : `${v}-${u}`;
        edges.add(key);
      };
      add(a,b); add(b,c); add(c,a);
    }
    const pts=[];
    for(const key of edges){
      const [a,b] = key.split("-").map(n=>parseInt(n,10));
      const va = icoVerts[a];
      const vb = icoVerts[b];
      const p1 = [mix(va[0], vb[0], ratio), mix(va[1], vb[1], ratio), mix(va[2], vb[2], ratio)];
      const p2 = [mix(vb[0], va[0], ratio), mix(vb[1], va[1], ratio), mix(vb[2], va[2], ratio)];
      pts.push(normScale(p1, g.R));
      pts.push(normScale(p2, g.R));
    }
    return pts.map(p=>({x:p[0],y:p[1],z:p[2]}));
  }

  function gen_stellated_icosa(g){
    const faces = [
      [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
      [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
      [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
      [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]
    ];
    const verts = platonic.icosahedron();
    const spike = Math.min(2.5, Math.max(0.8, g.stellated_scale ?? 1.4));
    const centers = faces.map(face=>{
      const A=verts[face[0]], B=verts[face[1]], C=verts[face[2]];
      const cx=(A[0]+B[0]+C[0])/3, cy=(A[1]+B[1]+C[1])/3, cz=(A[2]+B[2]+C[2])/3;
      return normScale([cx,cy,cz], g.R * spike);
    });
    return centers.map(p=>({x:p[0],y:p[1],z:p[2]}));
  }

  function parsePolyhedronData(str, R){
    if (!str) return [];
    try{
      const data = JSON.parse(str);
      if (Array.isArray(data.vertices)){
        return data.vertices.map(v=>({x:(v[0]||0)*R, y:(v[1]||0)*R, z:(v[2]||0)*R}));
      }
    }catch(err){ console.warn("Invalid polyhedron data", err); }
    return [];
  }

  function linkPolyPoints(points, steps){
    const count = Math.max(0, steps|0);
    if (!Array.isArray(points) || points.length < 2 || count <= 0) return points;
    let minDist = Infinity;
    for (let i=0;i<points.length;i++){
      const a = points[i];
      for (let j=i+1;j<points.length;j++){
        const b = points[j];
        const dx=a.x-b.x, dy=a.y-b.y, dz=a.z-b.z;
        const dist = Math.hypot(dx, dy, dz);
        if (dist > 1e-5 && dist < minDist) minDist = dist;
      }
    }
    if (!Number.isFinite(minDist) || minDist <= 0) return points;
    const threshold = minDist * 1.2;
    const extras = [];
    const seen = new Set();
    for (let i=0;i<points.length;i++){
      const a = points[i];
      for (let j=i+1;j<points.length;j++){
        const b = points[j];
        const dx=a.x-b.x, dy=a.y-b.y, dz=a.z-b.z;
        const dist = Math.hypot(dx, dy, dz);
        if (dist <= threshold){
          const key = i+"-"+j;
          if (seen.has(key)) continue;
          seen.add(key);
          for (let s=1;s<=count;s++){
            const t = s/(count+1);
            extras.push({
              x: a.x + (b.x - a.x)*t,
              y: a.y + (b.y - a.y)*t,
              z: a.z + (b.z - a.z)*t,
            });
          }
        }
      }
    }
    if (!extras.length) return points;
    return points.concat(extras);
  }

  function expandPolyLayers(points, layers){
    if (!Array.isArray(points)) return [];
    const count = Math.max(1, layers|0);
    const out = [];
    if (count <= 1){
      for (const p of points){
        out.push({ x:p.x||0, y:p.y||0, z:p.z||0 });
      }
      return out;
    }
    for (let layer=1; layer<=count; layer++){
      const t = layer / count;
      for (const p of points){
        out.push({ x:(p.x||0)*t, y:(p.y||0)*t, z:(p.z||0)*t });
      }
    }
    return out;
  }

  function buildPolyGeometry(points, g){
    const layered = expandPolyLayers(points, g.poly_layers);
    return linkPolyPoints(layered, g.poly_link_steps);
  }

  function gen_blob(g){
    const latSteps = Math.max(3, g.lat|0);
    const lonSteps = Math.max(3, g.lon|0);
    const out=[];
    for(let i=0;i<latSteps;i++){
      const theta = i/(latSteps-1)*Math.PI;
      for(let j=0;j<lonSteps;j++){
        const phi = j/lonSteps*2*Math.PI;
        const noise = g.blob_noise_amp * Math.sin(g.blob_noise_scale*theta) * Math.cos(g.blob_noise_scale*phi);
        const r = g.R * (1 + noise);
        out.push({x:r*Math.sin(theta)*Math.cos(phi), y:r*Math.cos(theta), z:r*Math.sin(theta)*Math.sin(phi)});
      }
    }
    return out;
  }

  function sampleImplicit(count, scale, evalFn, threshold){
    const out=[];
    const maxAttempts = count * 50;
    let attempts = 0;
    const eps = threshold !== undefined ? Math.max(1e-4, Math.abs(threshold)) : 0.02 * Math.max(1e-3, scale);
    while(out.length < count && attempts < maxAttempts){
      attempts++;
      const x = (Math.random()*2-1) * scale;
      const y = (Math.random()*2-1) * scale;
      const z = (Math.random()*2-1) * scale;
      const v = evalFn(x,y,z);
      if (Math.abs(v) < eps){ out.push({x,y,z}); }
    }
    return out;
  }

  function gen_gyroid(g){
    const count = clampCount(Math.max(100, g.N|0));
    const freq = Math.max(0.1, g.gyroid_scale);
    const scale = Math.max(0.1, g.R);
    const evalFn = (x,y,z) => Math.sin(freq*x)*Math.cos(freq*y) + Math.sin(freq*y)*Math.cos(freq*z) + Math.sin(freq*z)*Math.cos(freq*x) - g.gyroid_c;
    const pts = sampleImplicit(count, scale, evalFn, g.gyroid_thickness);
    return pts;
  }

  function gen_schwarz(g, mode){
    const count = clampCount(Math.max(100, g.N|0));
    const scale = Math.max(0.1, g.R * g.schwarz_scale);
    const evalFn = mode === "P" ?
      (x,y,z) => Math.cos(x/ g.schwarz_scale) + Math.cos(y/ g.schwarz_scale) + Math.cos(z/ g.schwarz_scale) - g.schwarz_iso :
      (x,y,z) => (Math.sin(x/ g.schwarz_scale)*Math.cos(y/ g.schwarz_scale) + Math.sin(y/ g.schwarz_scale)*Math.cos(z/ g.schwarz_scale) + Math.sin(z/ g.schwarz_scale)*Math.cos(x/ g.schwarz_scale)) - g.schwarz_iso;
    return sampleImplicit(count, scale, evalFn, 0.05*scale);
  }

  function gen_heart(g){
    const count = clampCount(Math.max(200, g.N|0));
    const scale = Math.max(0.1, g.R * g.heart_scale);
    const evalFn = (x,y,z) => Math.pow((x/scale)*(x/scale) + (9/4)*(y/scale)*(y/scale) + (z/scale)*(z/scale) - 1, 3) - (x/scale)*(x/scale)*(z/scale)*(z/scale)*(z/scale) - (9/80)*(y/scale)*(y/scale)*(z/scale)*(z/scale)*(z/scale);
    return sampleImplicit(count, scale, evalFn, 0.03*scale);
  }

  function gen_metaballs(g){
    const centers = parseVectorList(g.metaballs_centers);
    const radii = parseNumberList(g.metaballs_radii);
    const count = clampCount(Math.max(200, g.N|0));
    const evalFn = (x,y,z) => {
      let sum = 0;
      for(let i=0;i<centers.length;i++){
        const c = centers[i];
        const r = radii[i] || radii[0] || 1;
        const dx=x-c[0], dy=y-c[1], dz=z-c[2];
        sum += r*r / (dx*dx + dy*dy + dz*dz + 1e-6);
      }
      return sum - g.metaballs_iso;
    };
    return sampleImplicit(count, g.R, evalFn, 0.05*g.R);
  }

  function sdfEvaluator(expr){
    // eslint-disable-next-line no-new-func
    return new Function("x","y","z","with(Math){const sphere=r=>Math.sqrt(x*x+y*y+z*z)-r;const box=(bx,by,bz)=>{const dx=Math.abs(x)-bx;const dy=Math.abs(y)-by;const dz=Math.abs(z)-bz;const ax=Math.max(dx,0),ay=Math.max(dy,0),az=Math.max(dz,0);return Math.min(Math.max(dx,Math.max(dy,dz)),0)+Math.hypot(ax,ay,az);};const torus=(R,r)=>{const q=Math.hypot(x,y)-R;return Math.hypot(q,z)-r;};const union=(a,b)=>Math.min(a,b);const sub=(a,b)=>Math.max(-a,b);const inter=(a,b)=>Math.max(a,b);return ("+expr+");}");
  }

  function gen_distance_field(g){
    const count = clampCount(Math.max(200, g.N|0));
    let fn;
    try { fn = sdfEvaluator(g.df_ops || "sphere(1.0)"); }
    catch(err){ console.warn("Invalid df", err); return []; }
    const scale = g.R || 1;
    return sampleImplicit(count, scale, (x,y,z)=>fn(x,y,z));
  }

  function superformula3D(theta, m, a, b, n1, n2, n3){
    const part1 = Math.pow(Math.abs(Math.cos(m*theta/4)/a), n2);
    const part2 = Math.pow(Math.abs(Math.sin(m*theta/4)/b), n3);
    return Math.pow(part1 + part2, -1/Math.max(1e-6, n1));
  }

  function gen_superformula3D(g){
    const latSteps = Math.max(4, g.lat|0);
    const lonSteps = Math.max(4, g.lon|0);
    const out=[];
    for(let i=0;i<latSteps;i++){
      const theta = -Math.PI/2 + i/(latSteps-1)*Math.PI;
      const r1 = superformula3D(theta, g.sf3_m1, g.sf3_a, g.sf3_b, g.sf3_n1, g.sf3_n2, g.sf3_n3);
      for(let j=0;j<lonSteps;j++){
        const phi = j/lonSteps * 2*Math.PI;
        const r2 = superformula3D(phi, g.sf3_m2, g.sf3_a, g.sf3_b, g.sf3_n1, g.sf3_n2, g.sf3_n3);
        const r3 = superformula3D(phi, g.sf3_m3, g.sf3_a, g.sf3_b, g.sf3_n1, g.sf3_n2, g.sf3_n3);
        const r = g.sf3_scale * g.R * r1 * r2;
        const x = r * Math.cos(theta) * Math.cos(phi);
        const y = r * Math.sin(theta);
        const z = r * Math.cos(theta) * Math.sin(phi) * r3;
        out.push({x,y,z});
      }
    }
    return out;
  }

  function gen_helix(g){
    const count = clampCount(Math.max(10, g.N|0));
    const out=[];
    const turns = g.helix_turns;
    const total = 2*Math.PI*turns;
    for(let i=0;i<count;i++){
      const t = total * i/(count-1);
      out.push({
        x:g.R*g.helix_r*Math.cos(t),
        y:g.R*g.helix_pitch * t/(2*Math.PI),
        z:g.R*g.helix_r*Math.sin(t)
      });
    }
    return out;
  }

  function gen_lissajous3D(g){
    const count = clampCount(Math.max(20, g.N|0));
    const out=[];
    for(let i=0;i<count;i++){
      const t = 2*Math.PI * i/count;
      const x = g.lissajous3d_Ax * Math.sin(g.lissajous3d_wx * t + g.lissajous3d_phi);
      const y = g.lissajous3d_Ay * Math.sin(g.lissajous3d_wy * t);
      const z = g.lissajous3d_Az * Math.sin(g.lissajous3d_wz * t + g.lissajous3d_phi/2);
      out.push({x:x*g.R, y:y*g.R, z:z*g.R});
    }
    return out;
  }

  function gen_viviani(g){
    const count = clampCount(Math.max(20, g.N|0));
    const out=[];
    for(let i=0;i<count;i++){
      const t = 2*Math.PI * i/count;
      const x = g.viviani_a * (1 + Math.cos(t));
      const y = 2*g.viviani_a * Math.sin(t);
      const z = 2*g.viviani_a * Math.sin(t/2);
      out.push({x:x*g.R, y:y*g.R, z:z*g.R});
    }
    return out;
  }

  function gen_lic_sphere(g){
    const lines = Math.max(1, g.lic_N|0);
    const steps = Math.max(1, g.lic_steps|0);
    const h = g.lic_h;
    const out=[];
    for(let i=0;i<lines;i++){
      let theta = Math.random()*Math.PI;
      let phi = Math.random()*2*Math.PI;
      for(let s=0;s<steps;s++){
        const x = g.R*Math.sin(theta)*Math.cos(phi);
        const y = g.R*Math.cos(theta);
        const z = g.R*Math.sin(theta)*Math.sin(phi);
        out.push({x,y,z});
        const uTheta = Math.sin(phi);
        const uPhi = Math.cos(theta);
        theta = Math.min(Math.PI-1e-4, Math.max(1e-4, theta + h*uTheta));
        phi += h*uPhi;
      }
    }
    return out;
  }

  function gen_stream_torus(g){
    const lines = Math.max(1, g.stream_N|0);
    const steps = Math.max(1, g.stream_steps|0);
    const out=[];
    for(let i=0;i<lines;i++){
      let u = Math.random()*2*Math.PI;
      let v = Math.random()*2*Math.PI;
      for(let s=0;s<steps;s++){
        const cth=Math.cos(v), sth=Math.sin(v);
        const ring = g.R_major + g.r_minor*cth;
        out.push({
          x:g.R*ring*Math.cos(u),
          y:g.R*(g.r_minor*sth),
          z:g.R*ring*Math.sin(u)
        });
        u += 0.02 + 0.01*Math.sin(v);
        v += 0.015 + 0.02*Math.cos(u*0.5);
      }
    }
    return out;
  }

  function gen_geodesic_graph(g){
    return gen_geodesic(g.R, g.geo_graph_level|0);
  }

  function gen_random_geometric_graph(g){
    const count = clampCount(Math.max(10, g.rgg_nodes|0));
    const out=[];
    for(let i=0;i<count;i++){
      const theta = Math.acos(2*Math.random()-1);
      const phi = Math.random()*2*Math.PI;
      out.push({
        x:g.R*Math.sin(theta)*Math.cos(phi),
        y:g.R*Math.cos(theta),
        z:g.R*Math.sin(theta)*Math.sin(phi)
      });
    }
    return out;
  }

  function gen_concentric_rings(g){
    const rings = Math.max(1, g.rings_count|0);
    const pts = Math.max(3, g.ring_points|0);
    const out=[];
    for(let i=1;i<=rings;i++){
      const radius = g.R * (i/rings);
      for(let j=0;j<pts;j++){
        const ang = j/pts * 2*Math.PI;
        out.push({x:radius*Math.cos(ang), y:0, z:radius*Math.sin(ang)});
      }
    }
    return out;
  }

  function gen_hex_packing(g){
    const out=[];
    const step = g.hex_step;
    const nx = Math.max(1, g.hex_nx|0);
    const ny = Math.max(1, g.hex_ny|0);
    for(let ix=0; ix<nx; ix++){
      for(let iy=0; iy<ny; iy++){
        const x = (ix + 0.5*(iy%2)) * step;
        const z = iy * step * Math.sin(Math.PI/3);
        out.push({x: x - (nx-1)*step*0.5, y:0, z: z - (ny-1)*step*Math.sin(Math.PI/3)*0.5});
      }
    }
    return out;
  }

  function gen_voronoi_seeds(g){
    const nums = parseNumberList(g.voronoi_bbox);
    const xmin = nums[0] ?? -1;
    const xmax = nums[1] ?? 1;
    const zmin = nums[2] ?? -1;
    const zmax = nums[3] ?? 1;
    const count = Math.max(1, g.voronoi_N|0);
    const out=[];
    for(let i=0;i<count;i++){
      const x = xmin + Math.random()*(xmax-xmin);
      const z = zmin + Math.random()*(zmax-zmin);
      out.push({x, y:0, z});
    }
    return out;
  }

  const generators = {
    uv_sphere: g => gen_uv_sphere(g.R, g.lat, g.lon),
    fibo_sphere: g => gen_fibo_sphere(g.N, g.R, g.phi_g),
    disk_phyllotaxis: g => gen_disk_phyllo(g.N, g.R, g.phi_g),
    archimede_spiral: g => gen_archimede_spiral(g),
    log_spiral: g => gen_log_spiral(g),
    rose_curve: g => gen_rose_curve(g),
    superformula_2D: g => gen_superformula_2D(g),
    density_warp_disk: g => gen_density_warp(g),
    poisson_disk: g => gen_poisson_disk(g),
    lissajous_disk: g => gen_lissajous_disk(g),
    geodesic_sphere: g => gen_geodesic(g.R, g.geo_level|0),
    geodesic: g => gen_geodesic(g.R, g.geo_level|0),
    vogel_sphere_spiral: g => gen_vogel_sphere(g),
    superquadric: g => gen_superquadric(g.R, g.eps1, g.eps2, g.ax, g.ay, g.az, g.lat, g.lon),
    superellipsoid: g => gen_superellipsoid(g),
    half_sphere: g => gen_half_sphere(g),
    noisy_sphere: g => gen_noisy_sphere(g),
    spherical_harmonics: g => gen_spherical_harmonics(g),
    weighted_sphere: g => gen_weighted_sphere(g),
    torus: g => gen_torus(g.R_major, g.r_minor, g.lat, g.lon, g.R),
    double_torus: g => gen_double_torus(g),
    horn_torus: g => gen_torus(g.R_major, g.r_minor, g.lat, g.lon, g.R),
    spindle_torus: g => gen_torus(g.R_major, g.r_minor, g.lat, g.lon, g.R),
    torus_knot: g => gen_torus_knot(g),
    mobius: g => gen_strip_twist({...g, strip_w:g.mobius_w, strip_n:1}),
    strip_twist: g => gen_strip_twist(g),
    klein_bottle: g => gen_klein_bottle(g),
    icosahedron: g => buildPolyGeometry(scaleVectors(platonic.icosahedron(), g.R), g),
    dodecahedron: g => buildPolyGeometry(scaleVectors(platonic.dodecahedron(), g.R), g),
    octahedron: g => buildPolyGeometry(scaleVectors(platonic.octahedron(), g.R), g),
    tetrahedron: g => buildPolyGeometry(scaleVectors(platonic.tetrahedron(), g.R), g),
    cube: g => buildPolyGeometry(scaleVectors(platonic.cube(), g.R), g),
    truncated_icosa: g => buildPolyGeometry(gen_truncated_icosa(g), g),
    stellated_icosa: g => buildPolyGeometry(gen_stellated_icosa(g), g),
    polyhedron: g => buildPolyGeometry(parsePolyhedronData(g.polyhedron_data, g.R), g),
    blob: g => gen_blob(g),
    gyroid: g => gen_gyroid(g),
    schwarz_P: g => gen_schwarz(g, "P"),
    schwarz_D: g => gen_schwarz(g, "D"),
    heart_implicit: g => gen_heart(g),
    metaballs: g => gen_metaballs(g),
    distance_field_shape: g => gen_distance_field(g),
    superformula_3D: g => gen_superformula3D(g),
    helix: g => gen_helix(g),
    lissajous3D: g => gen_lissajous3D(g),
    viviani_curve: g => gen_viviani(g),
    line_integral_convolution_sphere: g => gen_lic_sphere(g),
    stream_on_torus: g => gen_stream_torus(g),
    geodesic_graph: g => gen_geodesic_graph(g),
    random_geometric_graph: g => gen_random_geometric_graph(g),
    concentric_rings: g => gen_concentric_rings(g),
    hex_packing_plane: g => gen_hex_packing(g),
    voronoi_seeds: g => gen_voronoi_seeds(g)
  };

  function rebuildGeometry(){
    const g = state.geometry;
    const gen = generators[g.topology] || generators.uv_sphere;
    let pts;
    try {
      pts = gen(g);
    } catch(err){
      console.error("Geometry build failed", g.topology, err);
      pts = generators.uv_sphere(g);
    }
    if (!Array.isArray(pts)) pts = [];
    pts = pts.map((p, idx) => ({ x:p.x||0, y:p.y||0, z:p.z||0, seed: idx }));
    pts = applySampler(pts);
    basePoints = pts.map((p, idx) => ({ x:p.x, y:p.y, z:p.z, seed: p.seed ?? idx }));
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

  function randForIndex(i, salt=0){
    const s = i * 12.9898 + salt * 78.233;
    const x = Math.sin(s) * 43758.5453;
    return x - Math.floor(x);
  }

  function smoothStep(edge0, edge1, x){
    if (edge1 === edge0) return x < edge0 ? 0 : 1;
    const t = clamp01((x - edge0) / (edge1 - edge0));
    return t * t * (3 - 2 * t);
  }

  function sphericalFromCartesian(x,y,z){
    const r = Math.hypot(x,y,z) || 1;
    const theta = Math.acos(y / r);                          // [0,π]
    const phi = (Math.atan2(z, x) + 2*Math.PI) % (2*Math.PI);// [0,2π)
    return {theta, phi};
  }

  function shuffleArray(arr){
    for (let i=arr.length-1;i>0;i--){
      const j = Math.floor(Math.random()*(i+1));
      const tmp = arr[i]; arr[i]=arr[j]; arr[j]=tmp;
    }
    return arr;
  }

  function enforceMinDistance(points, minDist){
    if (!Array.isArray(points)) return [];
    if (minDist <= 0) return points.slice();
    const order = points.slice();
    shuffleArray(order);
    const cell = minDist;
    const offsets = [];
    for (let dx=-1; dx<=1; dx++){
      for (let dy=-1; dy<=1; dy++){
        for (let dz=-1; dz<=1; dz++) offsets.push([dx,dy,dz]);
      }
    }
    const min2 = minDist * minDist;
    const grid = new Map();
    const selected = [];
    for (const p of order){
      const ix = Math.floor(p.x / cell);
      const iy = Math.floor(p.y / cell);
      const iz = Math.floor(p.z / cell);
      let keep = true;
      for (const [dx,dy,dz] of offsets){
        const key = (ix+dx)+"_"+(iy+dy)+"_"+(iz+dz);
        const bucket = grid.get(key);
        if (!bucket) continue;
        for (const q of bucket){
          const dxp = p.x - q.x;
          const dyp = p.y - q.y;
          const dzp = p.z - q.z;
          if (dxp*dxp + dyp*dyp + dzp*dzp < min2){ keep = false; break; }
        }
        if (!keep) break;
      }
      if (!keep) continue;
      selected.push(p);
      const key = ix+"_"+iy+"_"+iz;
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(p);
    }
    return selected;
  }

  function blueNoiseSample(points, minDist){
    const out = enforceMinDistance(points, minDist);
    return out.length>0 ? out : points.slice();
  }

  function weightForPoint(p){
    const g = state.geometry || {};
    const r = Math.hypot(p.x, p.y, p.z);
    const sph = sphericalFromCartesian(p.x, p.y, p.z);
    const vars = { x:p.x, y:p.y, z:p.z, r, theta:sph.theta, phi:sph.phi };
    const expr = g.weight_map;
    if (typeof expr === "string" && expr.trim()){
      const w = evalExpression(expr, vars);
      if (Number.isFinite(w)) return Math.max(0, w);
    }
    const R = g.R || Math.max(r, 1);
    return clamp01(1 - r/Math.max(1e-6, R));
  }

  function weightedSample(points){
    if (!Array.isArray(points) || points.length===0) return [];
    const weights = [];
    let maxW = 0;
    for (const p of points){
      const w = weightForPoint(p);
      weights.push(w);
      if (w > maxW) maxW = w;
    }
    if (maxW <= 0) return points.slice();
    const out = [];
    for (let i=0;i<points.length;i++){
      const norm = weights[i] / maxW;
      if (norm >= 1 || randForIndex((points[i].seed ?? i)+1) <= norm){
        out.push(points[i]);
      }
    }
    return out.length>0 ? out : points.slice();
  }

  function applySampler(points){
    if (!Array.isArray(points)) return [];
    const dist = state.distribution || {};
    const dyn = state.dynamics || {};
    let working = points.slice();
    const minDist = Math.max(0, dist.dmin || 0);
    const sampler = dist.sampler || "direct";
    if (sampler === "blue_noise"){
      working = blueNoiseSample(working, minDist);
    } else if (sampler === "weighted_sampling"){
      working = weightedSample(working);
      if (minDist > 0) working = enforceMinDistance(working, minDist);
    } else if (minDist > 0){
      working = enforceMinDistance(working, minDist);
    }
    return working;
  }

  function applyPointModifiers(bp, seed, now){
    const dist = state.distribution || {};
    const dyn = state.dynamics || {};
    const baseR = Math.max(Math.hypot(bp.x, bp.y, bp.z), 1e-6);
    const R = state.geometry.R || baseR;
    const t = now * 0.001;
    let x = bp.x;
    let y = bp.y;
    let z = bp.z;

    const clusterCount = Math.max(1, (dist.clusterCount||0)|0);
    const spread = clamp01(dist.clusterSpread || 0);
    if (clusterCount > 1 && spread > 0){
      const cid = seed % clusterCount;
      const fy = 1 - 2 * ((cid + 0.5) / clusterCount);
      const fr = Math.sqrt(Math.max(0, 1 - fy * fy));
      const ang = cid * 2.39996322972865332;
      const cx = fr * Math.cos(ang);
      const cz = fr * Math.sin(ang);
      const cy = fy;
      x = (1 - spread) * x + spread * R * cx;
      y = (1 - spread) * y + spread * R * cy;
      z = (1 - spread) * z + spread * R * cz;
    }

    const nd = dist.noiseDistortion || 0;
    if (nd){
      const amp = nd * R * 0.5;
      const freq = 1.7;
      x += amp * (valueNoise3((bp.x+5.3)*freq, (bp.y-2.1)*freq, (bp.z+3.7)*freq) * 2 - 1);
      y += amp * (valueNoise3((bp.x-8.2)*freq, (bp.y+4.4)*freq, (bp.z+1.1)*freq) * 2 - 1);
      z += amp * (valueNoise3((bp.x+2.6)*freq, (bp.y+0.9)*freq, (bp.z-6.5)*freq) * 2 - 1);
    }

    const nw = dist.noiseWarp || 0;
    if (nw){
      const amp = nw * R * 0.4;
      const freq = 1.3;
      const anim = t * 0.6;
      x += amp * (valueNoise3((bp.x+anim)*freq, (bp.y-anim)*freq, (bp.z+2+anim)*freq) * 2 - 1);
      y += amp * (valueNoise3((bp.x-anim)*freq, (bp.y+anim)*freq, (bp.z-anim)*freq) * 2 - 1);
      z += amp * (valueNoise3((bp.x+anim*0.5)*freq, (bp.y+2*anim)*freq, (bp.z-anim*0.25)*freq) * 2 - 1);
    }

    const flow = dist.fieldFlow || 0;
    if (flow){
      const ang = (flow * 0.4 * t) + (flow * 0.3 * (y / Math.max(1e-6, R)));
      const c = Math.cos(ang), s = Math.sin(ang);
      const X = c * x - s * z;
      const Z = s * x + c * z;
      x = X; z = Z;
    }

    const repel = dist.repelForce || 0;
    if (repel){
      const r = Math.hypot(x, y, z) || 1;
      const diff = R - r;
      const k = repel * 0.6;
      x += diff * k * (x / r);
      y += diff * k * (y / r);
      z += diff * k * (z / r);
    }

    const pulse = dist.densityPulse || 0;
    if (pulse){
      const scale = 1 + 0.3 * pulse * Math.sin(t * 2 * Math.PI);
      x *= scale; y *= scale; z *= scale;
    }

    const oxDeg = dyn.orientXDeg !== undefined ? dyn.orientXDeg : (dist.orientXDeg || 0);
    const ox = toRad(oxDeg || 0);
    if (ox){
      const c = Math.cos(ox), s = Math.sin(ox);
      const Y = c * y - s * z;
      const Z = s * y + c * z;
      y = Y; z = Z;
    }
    const oyDeg = dyn.orientYDeg !== undefined ? dyn.orientYDeg : (dist.orientYDeg || 0);
    const oy = toRad(oyDeg || 0);
    if (oy){
      const c = Math.cos(oy), s = Math.sin(oy);
      const X = c * x + s * z;
      const Z = -s * x + c * z;
      x = X; z = Z;
    }
    const ozDeg = dyn.orientZDeg !== undefined ? dyn.orientZDeg : (dist.orientZDeg || 0);
    const oz = toRad(ozDeg || 0);
    if (oz){
      const c = Math.cos(oz), s = Math.sin(oz);
      const X = c * x - s * y;
      const Y = s * x + c * y;
      x = X; y = Y;
    }

    return { x, y, z };
  }

  function computeMaskWeight(p3, now){
    const dist = state.distribution || {};
    const mode = dist.maskMode || "none";
    if (mode === "none") return 1;
    const softness = Math.max(0.001, dist.maskSoftness || 0);
    const sph = sphericalFromCartesian(p3.x, p3.y, p3.z);
    const speed = dist.maskAnimate || 0;
    const anim = speed ? Math.sin(now * 0.001 * 2 * Math.PI * speed) : 0;

    if (mode === "north_cap"){
      const cutoff = Math.PI/3 + anim * 0.2;
      const soft = softness * Math.PI/2 + 0.05;
      const w = smoothStep(cutoff, cutoff + soft, sph.theta);
      return 1 - w;
    }
    if (mode === "band"){
      const baseHalf = Math.PI/6 + softness * Math.PI/4;
      const soft = softness * Math.PI/3 + 0.05;
      const center = Math.PI/2 + anim * Math.PI/3;
      const diff = Math.abs(sph.theta - center);
      const w = smoothStep(baseHalf, baseHalf + soft, diff);
      return 1 - w;
    }
    if (mode === "random_patch"){
      const soft = softness * Math.PI/6 + 0.05;
      const radius = Math.PI/8 + softness * Math.PI/5;
      const t = now * 0.001 * Math.max(0.1, speed || 0.1);
      const ct = valueNoise3(t*2+3.1, t*0.5+1.7, 2.3) * Math.PI;
      const cp = valueNoise3(t*0.7+8.6, t*1.3+4.4, 5.2) * 2*Math.PI;
      const cosDist = Math.sin(sph.theta)*Math.sin(ct)*Math.cos(sph.phi-cp) + Math.cos(sph.theta)*Math.cos(ct);
      const ang = Math.acos(Math.max(-1, Math.min(1, cosDist)));
      const w = smoothStep(radius, radius + soft, ang);
      return 1 - w;
    }
    return 1;
  }

  // --------- Distribution poids + dmin écran
  function keepByDistribution(p3, seed, now){
    const dist = state.distribution || {};
    const mode = dist.densityMode || dist.pr || "uniform";
    const R = state.geometry.R || Math.max(Math.hypot(p3.x, p3.y, p3.z), 1);
    let weight = 1;
    if (mode === "centered"){
      const r = Math.hypot(p3.x, p3.y, p3.z) / Math.max(1e-6, R);
      weight *= Math.exp(-3 * r * r);
    } else if (mode === "edges"){
      const r = Math.hypot(p3.x, p3.y, p3.z) / Math.max(1e-6, R);
      weight *= clamp01(Math.pow(r, 0.75));
    } else if (mode === "noise_field"){
      const n = valueNoise3(p3.x*1.6 + 11.1, p3.y*1.6 + 22.2, p3.z*1.6 + 33.3);
      weight *= clamp01(n);
    }
    weight *= computeMaskWeight(p3, now);
    weight = clamp01(weight);
    if (weight <= 0) return false;
    if (weight >= 1) return true;
    const rand = randForIndex((seed||0)+1);
    return rand <= weight;
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
      const seed = bp && bp.seed !== undefined ? bp.seed : i;
      const mod = applyPointModifiers(bp, seed, now);
      if (!keepByDistribution(mod, seed, now)) continue;

      // phase rot/pulse
      const phaseMode = state.dynamics.rotPhaseMode || "none";
      let phaseFactor = 0;
      if (phaseMode === "by_index"){
        phaseFactor = basePoints.length>1 ? i/(basePoints.length-1) : 0;
      } else if (phaseMode === "by_radius"){
        const R = state.geometry.R || 1; phaseFactor = clamp01(Math.hypot(mod.x,mod.z)/Math.max(1e-6,R));
      } else if (phaseMode === "by_longitude"){
        const phi = Math.atan2(mod.z, mod.x);
        const norm = (phi / (2*Math.PI)) % 1;
        phaseFactor = norm < 0 ? norm + 1 : norm;
      } else if (phaseMode === "by_latitude"){
        const R = state.geometry.R || 1;
        phaseFactor = clamp01((mod.y / Math.max(1e-6, R) + 1) * 0.5);
      } else if (phaseMode === "checkerboard"){
        phaseFactor = (i % 2) ? 0.5 : 0.0;
      } else if (phaseMode === "alternate_rings"){
        const R = state.geometry.R || 1;
        const latNorm = clamp01((mod.y / Math.max(1e-6, R) + 1) * 0.5);
        const band = Math.floor(latNorm * 6);
        phaseFactor = (band % 2) ? 0.5 : 0.0;
      } else if (phaseMode === "lat_lon_checker"){
        const R = state.geometry.R || 1;
        const latNorm = clamp01((mod.y / Math.max(1e-6, R) + 1) * 0.5);
        const phi = Math.atan2(mod.z, mod.x);
        let lonNorm = (phi / (2*Math.PI)) % 1;
        if (lonNorm < 0) lonNorm += 1;
        const latBand = Math.floor(latNorm * 6);
        const lonBand = Math.floor(lonNorm * 12);
        phaseFactor = ((latBand + lonBand) % 2) ? 0.5 : 0.0;
      } else if (phaseMode === "random"){
        phaseFactor = randForIndex(seed || i, 77);
      } else if (phaseMode === "noise3d"){
        const n = valueNoise3(mod.x*0.9 + 5.1, mod.y*0.9 + 7.7, mod.z*0.9 + 9.9);
        phaseFactor = clamp01(0.5 + 0.5*n);
      } else if (phaseMode === "golden_spiral"){
        let g = (i * 0.6180339887498949) % 1;
        if (g < 0) g += 1;
        phaseFactor = g;
      } else if (phaseMode === "cluster_wave"){
        const clusters = Math.max(1, (state.distribution && state.distribution.clusterCount) || 1);
        if (clusters <= 1){
          phaseFactor = 0;
        } else {
          const clusterIndex = Math.abs(seed || i) % clusters;
          phaseFactor = clusterIndex / (clusters - 1);
        }
      }
      const pulse = 1 + pulseA*Math.sin(pulseW*now*0.001 + pulsePhi0 + 2*Math.PI*phaseFactor);

      const angX = toRad(state.dynamics.rotX||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const angY = toRad(state.dynamics.rotY||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const angZ = toRad(state.dynamics.rotZ||0)*(now*0.001) + rotPhaseAmp*phaseFactor;
      const cX=Math.cos(angX), sX=Math.sin(angX);
      const cY=Math.cos(angY), sY=Math.sin(angY);
      const cZ=Math.cos(angZ), sZ=Math.sin(angZ);

      let x = mod.x*pulse, y=mod.y*pulse, z=mod.z*pulse;
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
        const R = state.geometry.R || 1; pxpf = clamp01(Math.hypot(mod.x,mod.z)/Math.max(1e-6,R));
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
