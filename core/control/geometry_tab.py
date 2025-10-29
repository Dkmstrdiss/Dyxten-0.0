from PyQt5 import QtWidgets, QtCore

from .widgets import row
from .config import DEFAULTS, TOOLTIPS


TOPOLOGIES = [
    "disk_phyllotaxis", "archimede_spiral", "log_spiral", "rose_curve", "superformula_2D",
    "density_warp_disk", "poisson_disk", "lissajous_disk",
    "uv_sphere", "fibo_sphere", "geodesic_sphere", "geodesic", "vogel_sphere_spiral", "superquadric",
    "superellipsoid", "half_sphere", "noisy_sphere", "spherical_harmonics", "weighted_sphere",
    "torus", "double_torus", "horn_torus", "spindle_torus", "torus_knot", "mobius",
    "strip_twist", "klein_bottle",
    "icosahedron", "dodecahedron", "octahedron", "tetrahedron", "cube",
    "truncated_icosa", "stellated_icosa", "polyhedron",
    "blob", "gyroid", "schwarz_P", "schwarz_D", "heart_implicit", "metaballs",
    "distance_field_shape", "superformula_3D",
    "helix", "lissajous3D", "viviani_curve",
    "line_integral_convolution_sphere", "stream_on_torus", "geodesic_graph", "random_geometric_graph",
    "concentric_rings", "hex_packing_plane", "voronoi_seeds"
]


TOPOLOGY_PARAMS = {
    "disk_phyllotaxis": ["R", "N", "phi_g"],
    "archimede_spiral": ["R", "N", "arch_a", "arch_b", "theta_max"],
    "log_spiral": ["R", "N", "log_a", "log_b", "theta_max"],
    "rose_curve": ["R", "N", "rose_k", "theta_max"],
    "superformula_2D": ["R", "N", "sf2_m", "sf2_a", "sf2_b", "sf2_n1", "sf2_n2", "sf2_n3"],
    "density_warp_disk": ["R", "N", "density_pdf"],
    "poisson_disk": ["R", "N", "poisson_dmin"],
    "lissajous_disk": ["R", "N", "lissajous_a", "lissajous_b", "lissajous_phase"],

    "uv_sphere": ["R", "lat", "lon"],
    "fibo_sphere": ["R", "N", "phi_g"],
    "geodesic_sphere": ["R", "geo_level"],
    "geodesic": ["R", "geo_level"],
    "vogel_sphere_spiral": ["R", "N", "vogel_k"],
    "superquadric": ["R", "lat", "lon", "eps1", "eps2", "ax", "ay", "az"],
    "superellipsoid": ["R", "lat", "lon", "ax", "ay", "az", "se_n1", "se_n2"],
    "half_sphere": ["R", "lat", "lon", "half_height"],
    "noisy_sphere": ["R", "lat", "lon", "noisy_amp", "noisy_freq", "noisy_gain", "noisy_omega"],
    "spherical_harmonics": ["R", "lat", "lon", "sph_terms"],
    "weighted_sphere": ["R", "N", "weight_map"],

    "torus": ["R", "lat", "lon", "R_major", "r_minor"],
    "double_torus": ["R", "lat", "lon", "R_major", "R_major2", "r_minor"],
    "horn_torus": ["R", "lat", "lon", "R_major", "r_minor"],
    "spindle_torus": ["R", "lat", "lon", "R_major", "r_minor"],
    "torus_knot": ["R", "N", "R_major", "r_minor", "torus_knot_p", "torus_knot_q"],
    "mobius": ["R", "lat", "lon", "mobius_w"],
    "strip_twist": ["R", "lat", "lon", "strip_w", "strip_n"],
    "klein_bottle": ["R", "lat", "lon", "R_major", "r_minor"],

    "icosahedron": ["R"],
    "dodecahedron": ["R"],
    "octahedron": ["R"],
    "tetrahedron": ["R"],
    "cube": ["R"],
    "truncated_icosa": ["R"],
    "stellated_icosa": ["R"],
    "polyhedron": ["R", "polyhedron_data"],

    "blob": ["R", "lat", "lon", "blob_noise_amp", "blob_noise_scale"],
    "gyroid": ["R", "N", "gyroid_scale", "gyroid_thickness", "gyroid_c"],
    "schwarz_P": ["R", "N", "schwarz_scale", "schwarz_iso"],
    "schwarz_D": ["R", "N", "schwarz_scale", "schwarz_iso"],
    "heart_implicit": ["R", "N", "heart_scale"],
    "metaballs": ["R", "N", "metaballs_centers", "metaballs_radii", "metaballs_iso"],
    "distance_field_shape": ["R", "N", "df_ops"],
    "superformula_3D": ["R", "lat", "lon", "sf3_m1", "sf3_m2", "sf3_m3", "sf3_n1", "sf3_n2", "sf3_n3", "sf3_a", "sf3_b", "sf3_scale"],

    "helix": ["R", "N", "helix_r", "helix_pitch", "helix_turns"],
    "lissajous3D": ["R", "N", "lissajous3d_Ax", "lissajous3d_Ay", "lissajous3d_Az", "lissajous3d_wx", "lissajous3d_wy", "lissajous3d_wz", "lissajous3d_phi"],
    "viviani_curve": ["R", "N", "viviani_a"],
    "line_integral_convolution_sphere": ["R", "lic_N", "lic_steps", "lic_h"],
    "stream_on_torus": ["R", "stream_N", "stream_steps", "R_major", "r_minor"],
    "geodesic_graph": ["R", "geo_graph_level"],
    "random_geometric_graph": ["R", "rgg_nodes", "rgg_radius"],

    "concentric_rings": ["R", "rings_count", "ring_points"],
    "hex_packing_plane": ["R", "hex_step", "hex_nx", "hex_ny"],
    "voronoi_seeds": ["R", "voronoi_N", "voronoi_bbox"],
}


TOPOLOGY_DESCRIPTIONS = {
    "disk_phyllotaxis": "Spirale dorée plane où les points suivent l’angle de Fibonacci pour une répartition organique.",
    "archimede_spiral": "Courbe plane en spirale dont l’écartement entre spires reste constant.",
    "log_spiral": "Spirale à croissance exponentielle, similaire à de nombreuses formes naturelles.",
    "rose_curve": "Rosace polaire générée par une fonction cosinus multipliant l’angle.",
    "superformula_2D": "Courbe paramétrique très polyvalente qui permet de reproduire de nombreux profils.",
    "density_warp_disk": "Disque dont la densité radiale est contrôlée par une fonction personnalisée.",
    "poisson_disk": "Échantillonnage sur disque assurant un espacement minimal entre chaque point.",
    "lissajous_disk": "Courbe plane résultant de deux oscillations orthogonales harmonisées.",

    "uv_sphere": "Maillage classique latitude/longitude d’une sphère complète.",
    "fibo_sphere": "Points quasi-uniformes sur la sphère grâce à la spirale de Fibonacci.",
    "geodesic_sphere": "Subdivision d’un icosaèdre pour approcher une sphère géodésique.",
    "geodesic": "Réseau géodésique basé sur l’icosaèdre subdivisé.",
    "vogel_sphere_spiral": "Spirale sphérique continue couvrant la surface avec une progression régulière.",
    "superquadric": "Surface généralisée permettant de passer du cube à la sphère via des exposants.",
    "superellipsoid": "Superquadrique normalisée à paramètres séparés pour latitude et longitude.",
    "half_sphere": "Dôme sphérique tronqué avec contrôle de la hauteur.",
    "noisy_sphere": "Sphère dont le rayon varie selon un bruit procédural pour un effet organique.",
    "spherical_harmonics": "Déformation de la sphère par combinaison d’harmoniques sphériques.",
    "weighted_sphere": "Échantillonnage pondéré sur la sphère à l’aide d’une carte personnalisée.",

    "torus": "Tore standard défini par un rayon majeur et un rayon mineur.",
    "double_torus": "Deux tores concentriques pour créer un anneau doublé.",
    "horn_torus": "Tore limite où le rayon majeur approche le rayon mineur.",
    "spindle_torus": "Tore auto-intersecté lorsque le rayon majeur est inférieur au mineur.",
    "torus_knot": "Courbe fermée enroulée sur un tore selon deux entiers (p,q).",
    "mobius": "Ruban de Möbius généré comme bande torsadée non orientable.",
    "strip_twist": "Ruban plat torsadé un nombre configurable de fois.",
    "klein_bottle": "Immersion d’une bouteille de Klein fermée.",

    "icosahedron": "Polyèdre régulier à 20 faces triangulaires.",
    "dodecahedron": "Polyèdre régulier à 12 faces pentagonales.",
    "octahedron": "Polyèdre régulier à 8 faces triangulaires.",
    "tetrahedron": "Polyèdre régulier minimal composé de 4 faces.",
    "cube": "Polyèdre régulier à 6 faces carrées.",
    "truncated_icosa": "Polyèdre de type ballon de football formé de pentagones et hexagones.",
    "stellated_icosa": "Version étoilée de l’icosaèdre avec pointes extrêmes.",
    "polyhedron": "Chargement d’un polyèdre personnalisé via une description JSON.",

    "blob": "Sphère déformée par un bruit fractal pour créer une masse organique.",
    "gyroid": "Surface implicite périodique à triple périodicité.",
    "schwarz_P": "Surface minimale périodique de type P.",
    "schwarz_D": "Surface minimale périodique de type D.",
    "heart_implicit": "Surface implicite dessinant un cœur en volume.",
    "metaballs": "Iso-surface issue de la somme de potentiels sphériques.",
    "distance_field_shape": "Forme définie par combinaisons d’opérations sur des SDF.",
    "superformula_3D": "Extension spatiale de la superformule avec paramètres multiples.",

    "helix": "Hélice régulière en 3D enroulée autour d’un axe.",
    "lissajous3D": "Courbe harmonique combinant trois oscillations orthogonales.",
    "viviani_curve": "Courbe tracée sur l’intersection d’une sphère et d’un cylindre.",
    "line_integral_convolution_sphere": "Trajectoires suivant un champ tangent sur la sphère.",
    "stream_on_torus": "Lignes de flux intégrées sur la surface d’un tore.",
    "geodesic_graph": "Graphe de géodésiques basé sur subdivisions d’icosaèdre.",
    "random_geometric_graph": "Graphes aléatoires connectant les points proches dans l’espace.",

    "concentric_rings": "Plusieurs anneaux concentriques disposés sur un plan.",
    "hex_packing_plane": "Pavage plan en grille hexagonale régulière.",
    "voronoi_seeds": "Jeu de graines pour générer un diagramme de Voronoï plan.",
}


PARAM_SPECS = {
    "R": dict(type="double", label="Taille générale", tip="geometry.R", min=0.05, max=10.0, step=0.05, decimals=3),
    "lat": dict(type="int", label="Anneaux horizontaux", tip="geometry.lat", min=3, max=1024),
    "lon": dict(type="int", label="Colonnes verticales", tip="geometry.lon", min=3, max=1024),
    "N": dict(type="int", label="Nombre de points", tip="geometry.N", min=10, max=500000),
    "phi_g": dict(type="double", label="Rotation progressive", tip="geometry.phi_g", min=0.0, max=6.283185, step=0.0001, decimals=5),
    "R_major": dict(type="double", label="Rayon externe (tore)", tip="geometry.R_major", min=0.05, max=10.0, step=0.05, decimals=3),
    "R_major2": dict(type="double", label="Rayon externe 2 (tore)", tip="geometry.R_major2", min=0.05, max=10.0, step=0.05, decimals=3),
    "r_minor": dict(type="double", label="Épaisseur du tore", tip="geometry.r_minor", min=0.01, max=5.0, step=0.05, decimals=3),
    "eps1": dict(type="double", label="Arrondi horizontal", tip="geometry.eps1", min=0.2, max=6.0, step=0.05, decimals=3),
    "eps2": dict(type="double", label="Arrondi vertical", tip="geometry.eps2", min=0.2, max=6.0, step=0.05, decimals=3),
    "ax": dict(type="double", label="Étirer X", tip="geometry.ax", min=0.1, max=5.0, step=0.05, decimals=3),
    "ay": dict(type="double", label="Étirer Y", tip="geometry.ay", min=0.1, max=5.0, step=0.05, decimals=3),
    "az": dict(type="double", label="Étirer Z", tip="geometry.az", min=0.1, max=5.0, step=0.05, decimals=3),
    "geo_level": dict(type="int", label="Niveau géodésique", tip="geometry.geo_level", min=0, max=6),
    "mobius_w": dict(type="double", label="Largeur du ruban", tip="geometry.mobius_w", min=0.05, max=2.0, step=0.01, decimals=3),

    "arch_a": dict(type="double", label="Archimède a", tip="geometry.arch_a", min=0.0, max=5.0, step=0.05, decimals=3),
    "arch_b": dict(type="double", label="Archimède b", tip="geometry.arch_b", min=0.0, max=5.0, step=0.05, decimals=3),
    "theta_max": dict(type="double", label="Angle maximum", tip="geometry.theta_max", min=0.1, max=50.0, step=0.1, decimals=3),
    "log_a": dict(type="double", label="Log a", tip="geometry.log_a", min=0.01, max=5.0, step=0.01, decimals=3),
    "log_b": dict(type="double", label="Log b", tip="geometry.log_b", min=-2.0, max=2.0, step=0.01, decimals=3),
    "rose_k": dict(type="double", label="Rosace k", tip="geometry.rose_k", min=1.0, max=24.0, step=0.1, decimals=3),
    "sf2_m": dict(type="double", label="Superformule m", tip="geometry.sf2_m", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf2_a": dict(type="double", label="Superformule a", tip="geometry.sf2_a", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_b": dict(type="double", label="Superformule b", tip="geometry.sf2_b", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n1": dict(type="double", label="Superformule n1", tip="geometry.sf2_n1", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n2": dict(type="double", label="Superformule n2", tip="geometry.sf2_n2", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n3": dict(type="double", label="Superformule n3", tip="geometry.sf2_n3", min=0.01, max=10.0, step=0.01, decimals=3),
    "density_pdf": dict(type="text", label="Densité radiale", tip="geometry.density_pdf"),
    "poisson_dmin": dict(type="double", label="Distance min", tip="geometry.poisson_dmin", min=0.0, max=2.0, step=0.01, decimals=3),
    "lissajous_a": dict(type="int", label="Lissajous a", tip="geometry.lissajous_a", min=1, max=64),
    "lissajous_b": dict(type="int", label="Lissajous b", tip="geometry.lissajous_b", min=1, max=64),
    "lissajous_phase": dict(type="double", label="Phase (rad)", tip="geometry.lissajous_phase", min=-6.283185, max=6.283185, step=0.01, decimals=3),

    "vogel_k": dict(type="double", label="Spirale k", tip="geometry.vogel_k", min=0.1, max=4.5, step=0.001, decimals=6),
    "se_n1": dict(type="double", label="Superellipsoïde n1", tip="geometry.se_n1", min=0.1, max=10.0, step=0.05, decimals=3),
    "se_n2": dict(type="double", label="Superellipsoïde n2", tip="geometry.se_n2", min=0.1, max=10.0, step=0.05, decimals=3),
    "half_height": dict(type="double", label="Écrasement vertical", tip="geometry.half_height", min=0.1, max=2.0, step=0.05, decimals=3),
    "noisy_amp": dict(type="double", label="Bruit amplitude", tip="geometry.noisy_amp", min=0.0, max=2.0, step=0.01, decimals=3),
    "noisy_freq": dict(type="double", label="Bruit fréquence", tip="geometry.noisy_freq", min=0.1, max=32.0, step=0.1, decimals=3),
    "noisy_gain": dict(type="double", label="Bruit gain", tip="geometry.noisy_gain", min=0.0, max=10.0, step=0.1, decimals=3),
    "noisy_omega": dict(type="double", label="Bruit phase", tip="geometry.noisy_omega", min=0.0, max=6.283185, step=0.01, decimals=3),
    "sph_terms": dict(type="text", label="Harmoniques (l,m,a)", tip="geometry.sph_terms"),
    "weight_map": dict(type="text", label="Carte pondérée", tip="geometry.weight_map"),

    "torus_knot_p": dict(type="int", label="Nœud p", tip="geometry.torus_knot_p", min=1, max=64),
    "torus_knot_q": dict(type="int", label="Nœud q", tip="geometry.torus_knot_q", min=1, max=64),
    "strip_w": dict(type="double", label="Largeur ruban", tip="geometry.strip_w", min=0.05, max=2.0, step=0.01, decimals=3),
    "strip_n": dict(type="int", label="Nombre de torsions", tip="geometry.strip_n", min=1, max=20),

    "blob_noise_amp": dict(type="double", label="Blob amplitude", tip="geometry.blob_noise_amp", min=0.0, max=3.0, step=0.05, decimals=3),
    "blob_noise_scale": dict(type="double", label="Blob échelle", tip="geometry.blob_noise_scale", min=0.1, max=10.0, step=0.05, decimals=3),
    "gyroid_scale": dict(type="double", label="Gyroid échelle", tip="geometry.gyroid_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "gyroid_thickness": dict(type="double", label="Gyroid épaisseur", tip="geometry.gyroid_thickness", min=0.005, max=1.0, step=0.005, decimals=3),
    "gyroid_c": dict(type="double", label="Gyroid décalage", tip="geometry.gyroid_c", min=-2.0, max=2.0, step=0.01, decimals=3),
    "schwarz_scale": dict(type="double", label="Schwarz échelle", tip="geometry.schwarz_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "schwarz_iso": dict(type="double", label="Schwarz iso", tip="geometry.schwarz_iso", min=-2.0, max=2.0, step=0.01, decimals=3),
    "heart_scale": dict(type="double", label="Échelle cœur", tip="geometry.heart_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "polyhedron_data": dict(type="text", label="Polyèdre JSON", tip="geometry.polyhedron_data"),
    "metaballs_centers": dict(type="text", label="Centres métaballes", tip="geometry.metaballs_centers"),
    "metaballs_radii": dict(type="text", label="Rayons métaballes", tip="geometry.metaballs_radii"),
    "metaballs_iso": dict(type="double", label="Iso métaballes", tip="geometry.metaballs_iso", min=0.0, max=5.0, step=0.05, decimals=3),
    "df_ops": dict(type="text", label="Opérations SDF", tip="geometry.df_ops"),
    "sf3_m1": dict(type="double", label="Superformule m1", tip="geometry.sf3_m1", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_m2": dict(type="double", label="Superformule m2", tip="geometry.sf3_m2", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_m3": dict(type="double", label="Superformule m3", tip="geometry.sf3_m3", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_n1": dict(type="double", label="Superformule n1", tip="geometry.sf3_n1", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_n2": dict(type="double", label="Superformule n2", tip="geometry.sf3_n2", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_n3": dict(type="double", label="Superformule n3", tip="geometry.sf3_n3", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_a": dict(type="double", label="Superformule a", tip="geometry.sf3_a", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_b": dict(type="double", label="Superformule b", tip="geometry.sf3_b", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_scale": dict(type="double", label="Superformule échelle", tip="geometry.sf3_scale", min=0.1, max=5.0, step=0.05, decimals=3),

    "helix_r": dict(type="double", label="Rayon hélice", tip="geometry.helix_r", min=0.05, max=5.0, step=0.05, decimals=3),
    "helix_pitch": dict(type="double", label="Pas hélice", tip="geometry.helix_pitch", min=0.01, max=2.0, step=0.01, decimals=3),
    "helix_turns": dict(type="double", label="Tours hélice", tip="geometry.helix_turns", min=1.0, max=64.0, step=0.1, decimals=3),
    "lissajous3d_Ax": dict(type="double", label="Amplitude X", tip="geometry.lissajous3d_Ax", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_Ay": dict(type="double", label="Amplitude Y", tip="geometry.lissajous3d_Ay", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_Az": dict(type="double", label="Amplitude Z", tip="geometry.lissajous3d_Az", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_wx": dict(type="int", label="Fréquence X", tip="geometry.lissajous3d_wx", min=1, max=64),
    "lissajous3d_wy": dict(type="int", label="Fréquence Y", tip="geometry.lissajous3d_wy", min=1, max=64),
    "lissajous3d_wz": dict(type="int", label="Fréquence Z", tip="geometry.lissajous3d_wz", min=1, max=64),
    "lissajous3d_phi": dict(type="double", label="Phase globale", tip="geometry.lissajous3d_phi", min=0.0, max=6.283185, step=0.01, decimals=3),
    "viviani_a": dict(type="double", label="Paramètre a", tip="geometry.viviani_a", min=0.1, max=5.0, step=0.05, decimals=3),
    "lic_N": dict(type="int", label="Lignes LIC", tip="geometry.lic_N", min=1, max=256),
    "lic_steps": dict(type="int", label="Étapes LIC", tip="geometry.lic_steps", min=1, max=5000),
    "lic_h": dict(type="double", label="Pas LIC", tip="geometry.lic_h", min=0.001, max=1.0, step=0.001, decimals=4),
    "stream_N": dict(type="int", label="Lignes tore", tip="geometry.stream_N", min=1, max=256),
    "stream_steps": dict(type="int", label="Étapes tore", tip="geometry.stream_steps", min=1, max=5000),
    "geo_graph_level": dict(type="int", label="Niveau graphe", tip="geometry.geo_graph_level", min=0, max=6),
    "rgg_nodes": dict(type="int", label="Noeuds graphe", tip="geometry.rgg_nodes", min=10, max=200000),
    "rgg_radius": dict(type="double", label="Rayon graphe", tip="geometry.rgg_radius", min=0.01, max=5.0, step=0.01, decimals=3),
    "rings_count": dict(type="int", label="Nombre d’anneaux", tip="geometry.rings_count", min=1, max=128),
    "ring_points": dict(type="int", label="Points par anneau", tip="geometry.ring_points", min=3, max=4096),
    "hex_step": dict(type="double", label="Pas hexagonal", tip="geometry.hex_step", min=0.01, max=5.0, step=0.01, decimals=3),
    "hex_nx": dict(type="int", label="Colonnes hex", tip="geometry.hex_nx", min=1, max=256),
    "hex_ny": dict(type="int", label="Lignes hex", tip="geometry.hex_ny", min=1, max=256),
    "voronoi_N": dict(type="int", label="Graines Voronoï", tip="geometry.voronoi_N", min=2, max=5000),
    "voronoi_bbox": dict(type="text", label="Boîte Voronoï", tip="geometry.voronoi_bbox"),
}


class GeometryTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    topologyChanged = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        defaults = DEFAULTS["geometry"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                width: 0px;
                background: transparent;
            }
            QScrollBar::handle:vertical,
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: transparent;
                border: none;
                height: 0px;
                margin: 0;
            }
        """)

        container = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(container)
        outer.addWidget(scroll)

        desc_frame = QtWidgets.QFrame()
        desc_frame.setObjectName("TopologyDescriptionFrame")
        desc_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        desc_layout = QtWidgets.QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(12, 8, 12, 8)
        desc_layout.setSpacing(4)
        desc_title = QtWidgets.QLabel("Description")
        desc_title.setObjectName("TopologyDescriptionTitle")
        desc_title.setStyleSheet("font-weight:600;color:#1f3a52;")
        self._desc_label = QtWidgets.QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setObjectName("TopologyDescriptionLabel")
        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(self._desc_label)
        outer.addWidget(desc_frame)

        desc_frame.setStyleSheet("""
            QFrame#TopologyDescriptionFrame {
                border:1px solid #d6e2ed;
                border-radius:6px;
                background:#ffffff;
            }
            QLabel#TopologyDescriptionLabel {
                color:#2b3f55;
            }
        """)

        self._scroll = scroll
        self._form_layout = layout

        self.param_widgets = {}
        self.param_rows = {}

        self.cb_topology = QtWidgets.QComboBox()
        self.cb_topology.addItems(TOPOLOGIES)
        self.cb_topology.setCurrentText(defaults.get("topology", TOPOLOGIES[0]))
        row(layout, "Forme de base", self.cb_topology, TOOLTIPS["geometry.topology"],
            lambda: self.cb_topology.setCurrentText(defaults.get("topology", TOPOLOGIES[0])))

        for name, spec in PARAM_SPECS.items():
            widget = self._create_widget(name, spec, defaults)
            tip_key = spec.get("tip") or f"geometry.{name}"
            tip = TOOLTIPS.get(tip_key, spec.get("tip_text", ""))
            reset_cb = self._reset_factory(name)
            row_widget = row(layout, spec["label"], widget, tip, reset_cb)
            self.param_widgets[name] = widget
            self.param_rows[name] = row_widget
            self._connect_widget(name, widget, spec)

        self.cb_topology.currentIndexChanged.connect(self.on_topology_changed)
        self._apply_topology_state(emit=False)

    # ------------------------------------------------------------------ utils
    def _create_widget(self, name, spec, defaults):
        if spec["type"] == "double":
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(spec.get("min", -1e9), spec.get("max", 1e9))
            w.setDecimals(spec.get("decimals", 3))
            w.setSingleStep(spec.get("step", 0.1))
            w.setValue(float(defaults.get(name, spec.get("default", 0.0))))
            return w
        if spec["type"] == "int":
            w = QtWidgets.QSpinBox()
            w.setRange(spec.get("min", -1000000), spec.get("max", 1000000))
            w.setValue(int(defaults.get(name, spec.get("default", 0))))
            return w
        if spec["type"] == "text":
            w = QtWidgets.QLineEdit()
            w.setText(str(defaults.get(name, spec.get("default", ""))))
            w.setClearButtonEnabled(True)
            return w
        raise ValueError(f"Type de paramètre inconnu: {spec['type']}")

    def _reset_factory(self, name):
        def _reset():
            defaults = DEFAULTS["geometry"]
            widget = self.param_widgets[name]
            value = defaults.get(name)
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QtWidgets.QSpinBox):
                widget.setValue(int(value))
            else:
                widget.setText(str(value or ""))
            self.emit_delta()
        return _reset

    def _connect_widget(self, name, widget, spec):
        if isinstance(widget, QtWidgets.QDoubleSpinBox) or isinstance(widget, QtWidgets.QSpinBox):
            widget.valueChanged.connect(self.emit_delta)
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.editingFinished.connect(self.emit_delta)

    # ---------------------------------------------------------------- interface
    def _apply_topology_state(self, emit=True):
        topology = self.cb_topology.currentText()
        active = set(self._active_param_names(topology))
        for name, row_widget in self.param_rows.items():
            visible = name in active
            row_widget.setVisible(visible)
            label = getattr(row_widget, "_form_label", None)
            if label is not None:
                label.setVisible(visible)
            widget = self.param_widgets[name]
            widget.setEnabled(visible)
        if emit:
            self.topologyChanged.emit(topology)
            self.emit_delta()
        self._update_description(topology)

    def on_topology_changed(self, *args):
        self._apply_topology_state(True)

    def collect(self):
        data = {"topology": self.cb_topology.currentText()}
        for name, widget in self.param_widgets.items():
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                data[name] = widget.value()
            elif isinstance(widget, QtWidgets.QSpinBox):
                data[name] = widget.value()
            else:
                data[name] = widget.text()
        return data

    def _active_param_names(self, topology=None):
        if topology is None:
            topology = self.cb_topology.currentText()
        return TOPOLOGY_PARAMS.get(topology, [])

    def set_defaults(self, cfg):
        cfg = cfg or {}
        defaults = DEFAULTS["geometry"]
        with QtCore.QSignalBlocker(self.cb_topology):
            self.cb_topology.setCurrentText(cfg.get("topology", defaults.get("topology", TOPOLOGIES[0])))
        for name, widget in self.param_widgets.items():
            val = cfg.get(name, defaults.get(name))
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(val))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(val))
                else:
                    widget.setText(str(val or ""))
        self._apply_topology_state(emit=False)

    def set_enabled(self, context: dict):
        pass

    def emit_delta(self, *args):
        self.changed.emit({"geometry": self.collect()})

    def _update_description(self, topology: str):
        text = TOPOLOGY_DESCRIPTIONS.get(topology, "")
        if not text:
            text = "Sélectionnez une topologie pour afficher son descriptif."
        self._desc_label.setText(text)
