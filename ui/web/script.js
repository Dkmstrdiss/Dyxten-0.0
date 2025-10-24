// === Dyxten JS Controller ===
// Gère la communication QWebChannel ↔ Host.py et la synchronisation des sliders

let Host = null;
let state = { rotationSpeed: 0, pulse: 0 };

function updateUI() {
  const rot = document.getElementById("rotationSpeed");
  const rotv = document.getElementById("rotationValue");
  const pulse = document.getElementById("pulse");
  const pulsev = document.getElementById("pulseValue");

  rot.value = state.rotationSpeed;
  rotv.textContent = state.rotationSpeed.toFixed(2);

  pulse.value = state.pulse;
  pulsev.textContent = state.pulse.toFixed(2);
}

// Appliquer l'état au modèle visuel (à compléter selon ton code Three.js)
function applyToModel() {
  // Exemple si tu as une variable globale "sphere" dans ton modèle Three.js :
  // sphere.material.uniforms.uRotationSpeed.value = state.rotationSpeed;
  // sphere.material.uniforms.uPulse.value = state.pulse;
  // Ici, on se contente de logguer :
  console.log("Apply to model:", state);
}

function applyState(s) {
  state = s;
  updateUI();
  applyToModel();
}

function initUI() {
  const rot = document.getElementById("rotationSpeed");
  const pulse = document.getElementById("pulse");
  const reset = document.getElementById("reset");

  rot.addEventListener("input", () => {
    state.rotationSpeed = parseFloat(rot.value);
    document.getElementById("rotationValue").textContent = rot.value;
    if (Host) Host.setParam("rotationSpeed", state.rotationSpeed);
    applyToModel();
  });

  pulse.addEventListener("input", () => {
    state.pulse = parseFloat(pulse.value);
    document.getElementById("pulseValue").textContent = pulse.value;
    if (Host) Host.setParam("pulse", state.pulse);
    applyToModel();
  });

  reset.addEventListener("click", () => {
    if (Host) Host.reset();
  });
}

function initChannel() {
  if (!window.qt || !qt.webChannelTransport) {
    console.warn("Qt WebChannel non initialisé");
    return;
  }

  new QWebChannel(qt.webChannelTransport, (channel) => {
    Host = channel.objects.Host;

    // Récupère l’état initial depuis Python
    Host.getState().then(applyState);

    // Écoute les changements pushés depuis Python
    Host.stateChanged.connect(applyState);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  initChannel();
});
