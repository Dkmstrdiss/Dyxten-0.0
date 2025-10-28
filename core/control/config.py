
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
    "camera.camRadius":"Détermine la distance entre la caméra et le centre de la scène.",
    "camera.camHeightDeg":"Place la caméra plus haut ou plus bas sur son orbite.",
    "camera.camTiltDeg":"Incline la caméra vers le haut ou vers le bas.",
    "camera.omegaDegPerSec":"Fait tourner automatiquement la caméra autour de la scène.",
    "camera.fov":"Contrôle l’angle de vue : petit pour zoomer, grand pour élargir.",
    "geometry.topology":"Sélectionne la forme de base utilisée pour disposer les particules.",
    "geometry.R":"Agrandit ou réduit toute la forme sans changer sa structure.",
    "geometry.lat":"Nombre de bandes horizontales utilisées pour dessiner la forme.",
    "geometry.lon":"Nombre de colonnes verticales utilisées pour dessiner la forme.",
    "geometry.N":"Nombre total de points générés pour les distributions spirales.",
    "geometry.phi_g":"Décalage progressif entre les points pour les spirales naturelles.",
    "geometry.R_major":"Rayon extérieur du tore.",
    "geometry.r_minor":"Épaisseur du tube du tore.",
    "geometry.eps1":"Arrondi la forme superquadrique sur l’axe horizontal.",
    "geometry.eps2":"Arrondi la forme superquadrique sur l’axe vertical.",
    "geometry.ax":"Étire la superquadrique sur l’axe X.",
    "geometry.ay":"Étire la superquadrique sur l’axe Y.",
    "geometry.az":"Étire la superquadrique sur l’axe Z.",
    "geometry.geo_level":"Affinage du maillage de l’icosaèdre.",
    "geometry.mobius_w":"Largeur du ruban pour la bande de Möbius.",
    "appearance.color":"Couleur principale des particules.",
    "appearance.colors":"Couleurs listées avec leur position pour créer un dégradé personnalisé.",
    "appearance.opacity":"Rend les particules plus ou moins transparentes.",
    "appearance.px":"Taille moyenne des particules en pixels.",
    "appearance.palette":"Mode d’attribution des couleurs.",
    "appearance.paletteK":"Fréquence de répétition du motif dans les palettes répétées.",
    "appearance.blendMode":"Définit comment les particules se mélangent entre elles et avec le fond.",
    "appearance.shape":"Choix de la forme de chaque particule.",
    "appearance.alphaDepth":"Atténue la visibilité des particules éloignées.",
    "appearance.h0":"Couleur de départ pour les palettes HSL animées.",
    "appearance.dh":"Amplitude de variation de la couleur pour les palettes HSL.",
    "appearance.wh":"Vitesse à laquelle la couleur HSL change.",
    "appearance.noiseScale":"Taille des détails colorés générés par le bruit.",
    "appearance.noiseSpeed":"Vitesse d’animation de ces détails colorés.",
    "appearance.pxModMode":"Active les variations automatiques de taille.",
    "appearance.pxModAmp":"Amplitude maximale des variations de taille.",
    "appearance.pxModFreq":"Rythme de répétition des variations de taille.",
    "appearance.pxModPhaseDeg":"Décalage du motif de variation de taille.",
    "dynamics.rotX":"Fait tourner le nuage autour de l’axe horizontal X.",
    "dynamics.rotY":"Fait tourner le nuage autour de l’axe vertical Y.",
    "dynamics.rotZ":"Fait tourner le nuage autour de l’axe longitudinal Z.",
    "dynamics.pulseA":"Amplitude de l’effet de respiration.",
    "dynamics.pulseW":"Vitesse de l’effet de respiration.",
    "dynamics.pulsePhaseDeg":"Décalage initial de l’animation de respiration.",
    "dynamics.rotPhaseMode":"Répartit un décalage de rotation selon l’index ou le rayon des particules.",
    "dynamics.rotPhaseDeg":"Amplitude maximale du décalage de rotation.",
    "distribution.pr":"Choisit comment les nouvelles particules sont réparties.",
    "distribution.dmin_px":"Évite que deux particules ne se projettent trop proches l’une de l’autre.",
    "mask.enabled":"Active ou désactive le masquage des particules.",
    "mask.mode":"Définit la zone conservée ou masquée.",
    "mask.angleDeg":"Ouvre plus ou moins le masque en forme de calotte.",
    "mask.bandHalfDeg":"Largeur d’une demi-bande autour de l’équateur.",
    "mask.lonCenterDeg":"Centre le masque longitudinal.",
    "mask.lonWidthDeg":"Largeur totale du masque longitudinal.",
    "mask.softDeg":"Adoucit le bord du masque pour un fondu progressif.",
    "mask.invert":"Inverse la zone masquée et visible.",
    "system.Nmax":"Nombre maximum de particules autorisées simultanément.",
    "system.dprClamp":"Limite la résolution utilisée pour protéger les performances.",
    "system.depthSort":"Trie les particules pour un affichage correct avec la transparence.",
    "system.transparent":"Permet de rendre la fenêtre de prévisualisation transparente."
}
