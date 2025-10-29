from PyQt5 import QtWidgets, QtCore

from .widgets import row, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget


class DistributionTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        d = DEFAULTS["distribution"]
        m = DEFAULTS["mask"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil distribution")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self.rows = {}

        # Distribution options -------------------------------------------------
        self.cb_density_mode = QtWidgets.QComboBox()
        self.cb_density_mode.addItems(["uniform", "centered", "edges", "noise_field"])
        self.cb_density_mode.setCurrentText(d["densityMode"])
        self.rows["densityMode"] = row(
            form,
            "Répartition",
            self.cb_density_mode,
            TOOLTIPS["distribution.densityMode"],
            lambda: self.cb_density_mode.setCurrentText(d["densityMode"]),
        )

        self.cb_sampler = QtWidgets.QComboBox()
        self.cb_sampler.addItems(["direct", "blue_noise", "weighted_sampling"])
        self.cb_sampler.setCurrentText(d["sampler"])
        self.rows["sampler"] = row(
            form,
            "Échantillonnage",
            self.cb_sampler,
            TOOLTIPS["distribution.sampler"],
            lambda: self.cb_sampler.setCurrentText(d["sampler"]),
        )

        self.sp_dmin = QtWidgets.QDoubleSpinBox()
        self.sp_dmin.setRange(0.0, 5.0)
        self.sp_dmin.setDecimals(3)
        self.sp_dmin.setSingleStep(0.05)
        self.sp_dmin.setValue(d["dmin"])
        self.rows["dmin"] = row(
            form,
            "Distance minimale (3D)",
            self.sp_dmin,
            TOOLTIPS["distribution.dmin"],
            lambda: self.sp_dmin.setValue(d["dmin"]),
        )

        self.sp_dmin_px = QtWidgets.QDoubleSpinBox()
        self.sp_dmin_px.setRange(0.0, 200.0)
        self.sp_dmin_px.setSingleStep(1.0)
        self.sp_dmin_px.setValue(d["dmin_px"])
        self.rows["dmin_px"] = row(
            form,
            "Distance écran (px)",
            self.sp_dmin_px,
            TOOLTIPS["distribution.dmin_px"],
            lambda: self.sp_dmin_px.setValue(d["dmin_px"]),
        )

        self.cb_dist_mask_mode = QtWidgets.QComboBox()
        self.cb_dist_mask_mode.addItems(["none", "north_cap", "band", "random_patch"])
        self.cb_dist_mask_mode.setCurrentText(d["maskMode"])
        self.rows["maskMode"] = row(
            form,
            "Masque spatial",
            self.cb_dist_mask_mode,
            TOOLTIPS["distribution.maskMode"],
            lambda: self.cb_dist_mask_mode.setCurrentText(d["maskMode"]),
        )

        self.sp_dist_mask_soft = QtWidgets.QDoubleSpinBox()
        self.sp_dist_mask_soft.setRange(0.0, 1.0)
        self.sp_dist_mask_soft.setSingleStep(0.05)
        self.sp_dist_mask_soft.setDecimals(3)
        self.sp_dist_mask_soft.setValue(d["maskSoftness"])
        self.rows["maskSoftness"] = row(
            form,
            "Adoucissement",
            self.sp_dist_mask_soft,
            TOOLTIPS["distribution.maskSoftness"],
            lambda: self.sp_dist_mask_soft.setValue(d["maskSoftness"]),
        )

        self.sp_dist_mask_animate = QtWidgets.QDoubleSpinBox()
        self.sp_dist_mask_animate.setRange(0.0, 5.0)
        self.sp_dist_mask_animate.setSingleStep(0.1)
        self.sp_dist_mask_animate.setDecimals(3)
        self.sp_dist_mask_animate.setValue(d["maskAnimate"])
        self.rows["maskAnimate"] = row(
            form,
            "Animation masque",
            self.sp_dist_mask_animate,
            TOOLTIPS["distribution.maskAnimate"],
            lambda: self.sp_dist_mask_animate.setValue(d["maskAnimate"]),
        )

        self.sp_noise_distortion = QtWidgets.QDoubleSpinBox()
        self.sp_noise_distortion.setRange(0.0, 1.0)
        self.sp_noise_distortion.setSingleStep(0.01)
        self.sp_noise_distortion.setDecimals(3)
        self.sp_noise_distortion.setValue(d["noiseDistortion"])
        self.rows["noiseDistortion"] = row(
            form,
            "Distorsion bruit",
            self.sp_noise_distortion,
            TOOLTIPS["distribution.noiseDistortion"],
            lambda: self.sp_noise_distortion.setValue(d["noiseDistortion"]),
        )

        self.sp_density_pulse = QtWidgets.QDoubleSpinBox()
        self.sp_density_pulse.setRange(0.0, 1.0)
        self.sp_density_pulse.setSingleStep(0.01)
        self.sp_density_pulse.setDecimals(3)
        self.sp_density_pulse.setValue(d["densityPulse"])
        self.rows["densityPulse"] = row(
            form,
            "Impulsion densité",
            self.sp_density_pulse,
            TOOLTIPS["distribution.densityPulse"],
            lambda: self.sp_density_pulse.setValue(d["densityPulse"]),
        )

        self.sp_cluster_count = QtWidgets.QSpinBox()
        self.sp_cluster_count.setRange(1, 128)
        self.sp_cluster_count.setValue(d["clusterCount"])
        self.rows["clusterCount"] = row(
            form,
            "Groupes",
            self.sp_cluster_count,
            TOOLTIPS["distribution.clusterCount"],
            lambda: self.sp_cluster_count.setValue(d["clusterCount"]),
        )

        self.sp_cluster_spread = QtWidgets.QDoubleSpinBox()
        self.sp_cluster_spread.setRange(0.0, 1.0)
        self.sp_cluster_spread.setSingleStep(0.01)
        self.sp_cluster_spread.setDecimals(3)
        self.sp_cluster_spread.setValue(d["clusterSpread"])
        self.rows["clusterSpread"] = row(
            form,
            "Écartement groupes",
            self.sp_cluster_spread,
            TOOLTIPS["distribution.clusterSpread"],
            lambda: self.sp_cluster_spread.setValue(d["clusterSpread"]),
        )

        self.sp_repel_force = QtWidgets.QDoubleSpinBox()
        self.sp_repel_force.setRange(0.0, 1.0)
        self.sp_repel_force.setSingleStep(0.01)
        self.sp_repel_force.setDecimals(3)
        self.sp_repel_force.setValue(d["repelForce"])
        self.rows["repelForce"] = row(
            form,
            "Répulsion locale",
            self.sp_repel_force,
            TOOLTIPS["distribution.repelForce"],
            lambda: self.sp_repel_force.setValue(d["repelForce"]),
        )

        self.sp_noise_warp = QtWidgets.QDoubleSpinBox()
        self.sp_noise_warp.setRange(0.0, 1.0)
        self.sp_noise_warp.setSingleStep(0.01)
        self.sp_noise_warp.setDecimals(3)
        self.sp_noise_warp.setValue(d["noiseWarp"])
        self.rows["noiseWarp"] = row(
            form,
            "Warp bruit",
            self.sp_noise_warp,
            TOOLTIPS["distribution.noiseWarp"],
            lambda: self.sp_noise_warp.setValue(d["noiseWarp"]),
        )

        self.sp_field_flow = QtWidgets.QDoubleSpinBox()
        self.sp_field_flow.setRange(0.0, 5.0)
        self.sp_field_flow.setSingleStep(0.1)
        self.sp_field_flow.setDecimals(3)
        self.sp_field_flow.setValue(d["fieldFlow"])
        self.rows["fieldFlow"] = row(
            form,
            "Champ vectoriel",
            self.sp_field_flow,
            TOOLTIPS["distribution.fieldFlow"],
            lambda: self.sp_field_flow.setValue(d["fieldFlow"]),
        )

        # Mask rendering options ----------------------------------------------
        self.chk_mask_enabled = QtWidgets.QCheckBox()
        self.chk_mask_enabled.setChecked(m["enabled"])
        self.rows["renderMaskEnabled"] = row(
            form,
            "Masque visuel",
            self.chk_mask_enabled,
            TOOLTIPS["mask.enabled"],
            lambda: self.chk_mask_enabled.setChecked(m["enabled"]),
        )

        self.cb_mask_visual_mode = QtWidgets.QComboBox()
        self.cb_mask_visual_mode.addItems(
            ["none", "north_cap", "south_cap", "equatorial_band", "longitudinal_band"]
        )
        self.cb_mask_visual_mode.setCurrentText(m["mode"])
        self.rows["renderMaskMode"] = row(
            form,
            "Type de masque",
            self.cb_mask_visual_mode,
            TOOLTIPS["mask.mode"],
            lambda: self.cb_mask_visual_mode.setCurrentText(m["mode"]),
        )

        self.sp_mask_angle = QtWidgets.QDoubleSpinBox()
        self.sp_mask_angle.setRange(0.0, 90.0)
        self.sp_mask_angle.setSingleStep(1.0)
        self.sp_mask_angle.setValue(m["angleDeg"])
        self.rows["maskAngleDeg"] = row(
            form,
            "Angle de coupe (°)",
            self.sp_mask_angle,
            TOOLTIPS["mask.angleDeg"],
            lambda: self.sp_mask_angle.setValue(m["angleDeg"]),
        )

        self.sp_mask_band = QtWidgets.QDoubleSpinBox()
        self.sp_mask_band.setRange(0.0, 90.0)
        self.sp_mask_band.setSingleStep(1.0)
        self.sp_mask_band.setValue(m["bandHalfDeg"])
        self.rows["maskBandHalfDeg"] = row(
            form,
            "Largeur demi-bande (°)",
            self.sp_mask_band,
            TOOLTIPS["mask.bandHalfDeg"],
            lambda: self.sp_mask_band.setValue(m["bandHalfDeg"]),
        )

        self.sp_mask_lon_center = QtWidgets.QDoubleSpinBox()
        self.sp_mask_lon_center.setRange(-180.0, 180.0)
        self.sp_mask_lon_center.setSingleStep(1.0)
        self.sp_mask_lon_center.setValue(m["lonCenterDeg"])
        self.rows["maskLonCenterDeg"] = row(
            form,
            "Longitude centrée (°)",
            self.sp_mask_lon_center,
            TOOLTIPS["mask.lonCenterDeg"],
            lambda: self.sp_mask_lon_center.setValue(m["lonCenterDeg"]),
        )

        self.sp_mask_lon_width = QtWidgets.QDoubleSpinBox()
        self.sp_mask_lon_width.setRange(0.0, 180.0)
        self.sp_mask_lon_width.setSingleStep(1.0)
        self.sp_mask_lon_width.setValue(m["lonWidthDeg"])
        self.rows["maskLonWidthDeg"] = row(
            form,
            "Largeur en longitude (°)",
            self.sp_mask_lon_width,
            TOOLTIPS["mask.lonWidthDeg"],
            lambda: self.sp_mask_lon_width.setValue(m["lonWidthDeg"]),
        )

        self.sp_mask_soft_deg = QtWidgets.QDoubleSpinBox()
        self.sp_mask_soft_deg.setRange(0.0, 45.0)
        self.sp_mask_soft_deg.setSingleStep(1.0)
        self.sp_mask_soft_deg.setValue(m["softDeg"])
        self.rows["maskSoftDeg"] = row(
            form,
            "Bord doux (°)",
            self.sp_mask_soft_deg,
            TOOLTIPS["mask.softDeg"],
            lambda: self.sp_mask_soft_deg.setValue(m["softDeg"]),
        )

        self.chk_mask_invert = QtWidgets.QCheckBox()
        self.chk_mask_invert.setChecked(m["invert"])
        self.rows["maskInvert"] = row(
            form,
            "Inverser la sélection",
            self.chk_mask_invert,
            TOOLTIPS["mask.invert"],
            lambda: self.chk_mask_invert.setChecked(m["invert"]),
        )

        widgets = [
            self.cb_density_mode,
            self.cb_sampler,
            self.sp_dmin,
            self.sp_dmin_px,
            self.cb_dist_mask_mode,
            self.sp_dist_mask_soft,
            self.sp_dist_mask_animate,
            self.sp_noise_distortion,
            self.sp_density_pulse,
            self.sp_cluster_count,
            self.sp_cluster_spread,
            self.sp_repel_force,
            self.sp_noise_warp,
            self.sp_field_flow,
            self.chk_mask_enabled,
            self.cb_mask_visual_mode,
            self.sp_mask_angle,
            self.sp_mask_band,
            self.sp_mask_lon_center,
            self.sp_mask_lon_width,
            self.sp_mask_soft_deg,
            self.chk_mask_invert,
        ]

        for w in widgets:
            if isinstance(w, QtWidgets.QDoubleSpinBox):
                w.valueChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QSpinBox):
                w.valueChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QSlider):
                w.valueChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QComboBox):
                w.currentIndexChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QCheckBox):
                w.stateChanged.connect(self.emit_delta)

        self.cb_dist_mask_mode.currentIndexChanged.connect(self._update_row_states)
        self.sp_cluster_count.valueChanged.connect(self._update_row_states)
        self.cb_sampler.currentIndexChanged.connect(self._update_row_states)
        self.cb_density_mode.currentIndexChanged.connect(self._update_row_states)
        self.chk_mask_enabled.stateChanged.connect(self._update_row_states)
        self.cb_mask_visual_mode.currentIndexChanged.connect(self._update_row_states)

        for widget, section, key in [
            (self.sp_dmin, "distribution", "dmin"),
            (self.sp_dmin_px, "distribution", "dmin_px"),
            (self.sp_dist_mask_soft, "distribution", "maskSoftness"),
            (self.sp_dist_mask_animate, "distribution", "maskAnimate"),
            (self.sp_noise_distortion, "distribution", "noiseDistortion"),
            (self.sp_density_pulse, "distribution", "densityPulse"),
            (self.sp_cluster_count, "distribution", "clusterCount"),
            (self.sp_cluster_spread, "distribution", "clusterSpread"),
            (self.sp_repel_force, "distribution", "repelForce"),
            (self.sp_noise_warp, "distribution", "noiseWarp"),
            (self.sp_field_flow, "distribution", "fieldFlow"),
            (self.sp_mask_angle, "mask", "angleDeg"),
            (self.sp_mask_band, "mask", "bandHalfDeg"),
            (self.sp_mask_lon_center, "mask", "lonCenterDeg"),
            (self.sp_mask_lon_width, "mask", "lonWidthDeg"),
            (self.sp_mask_soft_deg, "mask", "softDeg"),
        ]:
            register_linkable_widget(widget, section=section, key=key, tab="Distribution")

        self._update_row_states()
        self._sync_subprofile_state()

    # ------------------------------------------------------------------ public
    def collect_distribution(self) -> dict:
        return dict(
            densityMode=self.cb_density_mode.currentText(),
            sampler=self.cb_sampler.currentText(),
            dmin=self.sp_dmin.value(),
            dmin_px=self.sp_dmin_px.value(),
            maskMode=self.cb_dist_mask_mode.currentText(),
            maskSoftness=self.sp_dist_mask_soft.value(),
            maskAnimate=self.sp_dist_mask_animate.value(),
            noiseDistortion=self.sp_noise_distortion.value(),
            densityPulse=self.sp_density_pulse.value(),
            clusterCount=self.sp_cluster_count.value(),
            clusterSpread=self.sp_cluster_spread.value(),
            repelForce=self.sp_repel_force.value(),
            noiseWarp=self.sp_noise_warp.value(),
            fieldFlow=self.sp_field_flow.value(),
        )

    def collect_mask(self) -> dict:
        return dict(
            enabled=self.chk_mask_enabled.isChecked(),
            mode=self.cb_mask_visual_mode.currentText(),
            angleDeg=self.sp_mask_angle.value(),
            bandHalfDeg=self.sp_mask_band.value(),
            lonCenterDeg=self.sp_mask_lon_center.value(),
            lonWidthDeg=self.sp_mask_lon_width.value(),
            softDeg=self.sp_mask_soft_deg.value(),
            invert=self.chk_mask_invert.isChecked(),
        )

    def collect(self) -> dict:
        return self.collect_distribution()

    def set_defaults(self, distribution_cfg=None, mask_cfg=None):
        if isinstance(distribution_cfg, dict) and (
            "distribution" in distribution_cfg or "mask" in distribution_cfg
        ) and mask_cfg is None:
            combined = distribution_cfg
            distribution_cfg = combined.get("distribution", {})
            mask_cfg = combined.get("mask")

        distribution_cfg = distribution_cfg or {}
        mask_cfg = mask_cfg or {}
        d = DEFAULTS["distribution"]
        m = DEFAULTS["mask"]

        mapping = {
            self.cb_density_mode: distribution_cfg.get("densityMode", d["densityMode"]),
            self.cb_sampler: distribution_cfg.get("sampler", d["sampler"]),
            self.sp_dmin: distribution_cfg.get("dmin", d["dmin"]),
            self.sp_dmin_px: distribution_cfg.get("dmin_px", d["dmin_px"]),
            self.cb_dist_mask_mode: distribution_cfg.get("maskMode", d["maskMode"]),
            self.sp_dist_mask_soft: distribution_cfg.get("maskSoftness", d["maskSoftness"]),
            self.sp_dist_mask_animate: distribution_cfg.get("maskAnimate", d["maskAnimate"]),
            self.sp_noise_distortion: distribution_cfg.get("noiseDistortion", d["noiseDistortion"]),
            self.sp_density_pulse: distribution_cfg.get("densityPulse", d["densityPulse"]),
            self.sp_cluster_count: distribution_cfg.get("clusterCount", d["clusterCount"]),
            self.sp_cluster_spread: distribution_cfg.get("clusterSpread", d["clusterSpread"]),
            self.sp_repel_force: distribution_cfg.get("repelForce", d["repelForce"]),
            self.sp_noise_warp: distribution_cfg.get("noiseWarp", d["noiseWarp"]),
            self.sp_field_flow: distribution_cfg.get("fieldFlow", d["fieldFlow"]),
        }

        for widget, value in mapping.items():
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QtWidgets.QSlider):
                    widget.setValue(int(value))
                else:
                    widget.setValue(float(value))

        mask_mapping = {
            self.chk_mask_enabled: mask_cfg.get("enabled", m["enabled"]),
            self.cb_mask_visual_mode: mask_cfg.get("mode", m["mode"]),
            self.sp_mask_angle: mask_cfg.get("angleDeg", m["angleDeg"]),
            self.sp_mask_band: mask_cfg.get("bandHalfDeg", m["bandHalfDeg"]),
            self.sp_mask_lon_center: mask_cfg.get("lonCenterDeg", m["lonCenterDeg"]),
            self.sp_mask_lon_width: mask_cfg.get("lonWidthDeg", m["lonWidthDeg"]),
            self.sp_mask_soft_deg: mask_cfg.get("softDeg", m["softDeg"]),
            self.chk_mask_invert: mask_cfg.get("invert", m["invert"]),
        }

        for widget, value in mask_mapping.items():
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentText(str(value))
                else:
                    widget.setValue(float(value))

        self._update_row_states()
        self._sync_subprofile_state()

    def set_enabled(self, context: dict):
        pass

    def emit_delta(self, *args):
        self._update_row_states()
        payload = {
            "distribution": self.collect_distribution(),
            "mask": self.collect_mask(),
        }
        self._sync_subprofile_state()
        self.changed.emit(payload)

    # ------------------------------------------------------------------ helpers
    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="distribution",
            defaults=DEFAULTS["distribution"],
            collect_cb=self.collect,
            apply_cb=self._apply_distribution_subprofile,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _apply_distribution_subprofile(self, payload):
        if not isinstance(payload, dict):
            payload = {}
        self.set_defaults(payload)

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())

    def _set_row_visible(self, key: str, visible: bool):
        row_widget = self.rows.get(key)
        if row_widget is None:
            return
        row_widget.setVisible(visible)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setVisible(visible)

    def _update_row_states(self, *args):
        dist_mask_active = self.cb_dist_mask_mode.currentText() != "none"
        for key in ("maskSoftness", "maskAnimate"):
            self._set_row_visible(key, dist_mask_active)
        self.sp_dist_mask_soft.setEnabled(dist_mask_active)
        self.sp_dist_mask_animate.setEnabled(dist_mask_active)

        cluster_active = self.sp_cluster_count.value() > 1
        self._set_row_visible("clusterSpread", cluster_active)
        self.sp_cluster_spread.setEnabled(cluster_active)

        sampler = self.cb_sampler.currentText()
        show_dmin = sampler in ("blue_noise", "direct", "weighted_sampling")
        self._set_row_visible("dmin", show_dmin)
        self.sp_dmin.setEnabled(show_dmin)

        density_mode = self.cb_density_mode.currentText()
        show_noise = density_mode == "noise_field"
        self._set_row_visible("noiseDistortion", show_noise)
        self.sp_noise_distortion.setEnabled(show_noise)

        render_enabled = self.chk_mask_enabled.isChecked()
        self._set_row_visible("renderMaskMode", render_enabled)
        self.cb_mask_visual_mode.setEnabled(render_enabled)

        mode = self.cb_mask_visual_mode.currentText() if render_enabled else "none"
        show_angle = mode in ("north_cap", "south_cap")
        show_band = mode == "equatorial_band"
        show_lon = mode == "longitudinal_band"
        show_soft = mode != "none"
        show_invert = mode != "none"

        self._set_row_visible("maskAngleDeg", render_enabled and show_angle)
        self.sp_mask_angle.setEnabled(render_enabled and show_angle)
        self._set_row_visible("maskBandHalfDeg", render_enabled and show_band)
        self.sp_mask_band.setEnabled(render_enabled and show_band)
        self._set_row_visible("maskLonCenterDeg", render_enabled and show_lon)
        self.sp_mask_lon_center.setEnabled(render_enabled and show_lon)
        self._set_row_visible("maskLonWidthDeg", render_enabled and show_lon)
        self.sp_mask_lon_width.setEnabled(render_enabled and show_lon)
        self._set_row_visible("maskSoftDeg", render_enabled and show_soft)
        self.sp_mask_soft_deg.setEnabled(render_enabled and show_soft)
        self._set_row_visible("maskInvert", render_enabled and show_invert)
        self.chk_mask_invert.setEnabled(render_enabled and show_invert)

    def _install_angle_snap(self, *_args, **_kwargs):  # pragma: no cover - compat
        """Méthode conservée pour compatibilité avec d’anciens profils."""

    def _snap_slider(self, *_args, **_kwargs):  # pragma: no cover - compat
        """Méthode conservée pour compatibilité avec d’anciens profils."""
