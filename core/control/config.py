
from PyQt5 import QtCore

DEFAULTS = dict(
    camera=dict(camRadius=3.2, camHeightDeg=15, camTiltDeg=0, omegaDegPerSec=20, fov=600),
    geometry=dict(
        topology="uv_sphere",
        R=1.0, lat=64, lon=64, N=4096, phi_g=3.88322,
        R_major=1.2, r_minor=0.45,
        eps1=1.0, eps2=1.0, ax=1.0, ay=1.0, az=1.0,
        geo_level=1, mobius_w=0.4
    ),
    appearance=dict(
        color="#00C8FF", colors="#00C8FF@0,#FFFFFF@1", opacity=1.0, px=2.0,
        palette="uniform", paletteK=2,
        h0=200.0, dh=0.0, wh=0.0,
        blendMode="source-over", shape="circle",
        alphaDepth=0.0,
        noiseScale=1.0, noiseSpeed=0.0,
        pxModMode="none", pxModAmp=0.0, pxModFreq=0.0, pxModPhaseDeg=0.0,
    ),
    dynamics=dict(
        rotX=0.0, rotY=0.0, rotZ=0.0, pulseA=0.0, pulseW=1.0,
        pulsePhaseDeg=0.0, rotPhaseDeg=0.0, rotPhaseMode="none"
    ),
    distribution=dict(
        pr="uniform_area", dmin_px=0.0
    ),
    mask=dict(
        enabled=False, mode="none", angleDeg=30.0,
        bandHalfDeg=20.0, lonCenterDeg=0.0, lonWidthDeg=30.0,
        softDeg=10.0, invert=False
    ),
    system=dict(Nmax=50000, dprClamp=2.0, depthSort=True, transparent=True)
)

TOOLTIPS = {
    "camera.camRadius":"Distance caméra",
    "camera.camHeightDeg":"Hauteur d’orbite (°)",
    "camera.camTiltDeg":"Inclinaison (°)",
    "camera.omegaDegPerSec":"Vitesse d’orbite (°/s)",
    "camera.fov":"Champ de vision",
    "geometry.topology":"Choix de topologie",
    "geometry.R":"Échelle globale",
    "geometry.lat":"Anneaux / v-samples",
    "geometry.lon":"Segments / u-samples",
    "geometry.N":"Nombre total (génératifs)",
    "geometry.phi_g":"Angle doré",
    "geometry.R_major":"Tore grand rayon",
    "geometry.r_minor":"Tore petit rayon",
    "geometry.eps1":"Superquadric exp-1",
    "geometry.eps2":"Superquadric exp-2",
    "geometry.ax":"Axe X",
    "geometry.ay":"Axe Y",
    "geometry.az":"Axe Z",
    "geometry.geo_level":"Icosa subdiv level",
    "geometry.mobius_w":"Largeur ruban",
    "appearance.color":"Couleur principale",
    "appearance.colors":"Liste de stops: #hex@pos",
    "appearance.opacity":"Opacité globale",
    "appearance.px":"Taille particule (px)",
    "appearance.palette":"Palette",
    "appearance.paletteK":"K pour every_kth",
    "appearance.blendMode":"Mode de fusion",
    "appearance.shape":"Forme particule",
    "appearance.alphaDepth":"Fondu avec distance",
    "appearance.h0":"Teinte base",
    "appearance.dh":"Amplitude teinte",
    "appearance.wh":"Vitesse teinte",
    "appearance.noiseScale":"Échelle bruit",
    "appearance.noiseSpeed":"Vitesse bruit",
    "appearance.pxModMode":"Mode mod taille",
    "appearance.pxModAmp":"Amp mod taille",
    "appearance.pxModFreq":"Freq mod taille",
    "appearance.pxModPhaseDeg":"Phase mod taille",
    "dynamics.rotX":"Rotation locale X (°/s)",
    "dynamics.rotY":"Rotation locale Y (°/s)",
    "dynamics.rotZ":"Rotation locale Z (°/s)",
    "dynamics.pulseA":"Amplitude pulsation",
    "dynamics.pulseW":"Fréquence pulsation",
    "dynamics.pulsePhaseDeg":"Phase pulsation",
    "dynamics.rotPhaseMode":"Mode déphasage rot",
    "dynamics.rotPhaseDeg":"Amplitude déphasage rot (°)",
    "distribution.pr":"Biais de conservation",
    "distribution.dmin_px":"Espacement min écran (px)",
    "mask.enabled":"Activer le masque",
    "mask.mode":"Type de masque",
    "mask.angleDeg":"Angle cap (°)",
    "mask.bandHalfDeg":"Demi-largeur bande (°)",
    "mask.lonCenterDeg":"Longitude centre (°)",
    "mask.lonWidthDeg":"Largeur longitude (°)",
    "mask.softDeg":"Lissage (°)",
    "mask.invert":"Inverser",
    "system.Nmax":"Budget points max",
    "system.dprClamp":"Clamp DPI",
    "system.depthSort":"Tri profondeur",
    "system.transparent":"Transparence"
}
