from PyQt5 import QtWidgets, QtCore

from .widgets import row
from .config import DEFAULTS, TOOLTIPS


class DistributionTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        d = DEFAULTS["distribution"]

        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)

        self.cb_density_mode = QtWidgets.QComboBox()
        self.cb_density_mode.addItems(["uniform", "centered", "edges", "noise_field"])
        self.cb_density_mode.setCurrentText(d["densityMode"])

        self.cb_sampler = QtWidgets.QComboBox()
        self.cb_sampler.addItems(["direct", "blue_noise", "weighted_sampling"])
        self.cb_sampler.setCurrentText(d["sampler"])

        self.sp_dmin = QtWidgets.QDoubleSpinBox()
        self.sp_dmin.setRange(0.0, 5.0)
        self.sp_dmin.setDecimals(3)
        self.sp_dmin.setSingleStep(0.05)
        self.sp_dmin.setValue(d["dmin"])

        self.sp_dmin_px = QtWidgets.QDoubleSpinBox()
        self.sp_dmin_px.setRange(0.0, 200.0)
        self.sp_dmin_px.setSingleStep(1.0)
        self.sp_dmin_px.setValue(d["dmin_px"])

        self.cb_mask_mode = QtWidgets.QComboBox()
        self.cb_mask_mode.addItems(["none", "north_cap", "band", "random_patch"])
        self.cb_mask_mode.setCurrentText(d["maskMode"])

        self.sp_mask_soft = QtWidgets.QDoubleSpinBox()
        self.sp_mask_soft.setRange(0.0, 1.0)
        self.sp_mask_soft.setSingleStep(0.05)
        self.sp_mask_soft.setDecimals(3)
        self.sp_mask_soft.setValue(d["maskSoftness"])

        self.sp_mask_animate = QtWidgets.QDoubleSpinBox()
        self.sp_mask_animate.setRange(0.0, 5.0)
        self.sp_mask_animate.setSingleStep(0.1)
        self.sp_mask_animate.setDecimals(3)
        self.sp_mask_animate.setValue(d["maskAnimate"])

        self.sp_noise_distortion = QtWidgets.QDoubleSpinBox()
        self.sp_noise_distortion.setRange(0.0, 1.0)
        self.sp_noise_distortion.setSingleStep(0.01)
        self.sp_noise_distortion.setDecimals(3)
        self.sp_noise_distortion.setValue(d["noiseDistortion"])

        self.sp_density_pulse = QtWidgets.QDoubleSpinBox()
        self.sp_density_pulse.setRange(0.0, 1.0)
        self.sp_density_pulse.setSingleStep(0.01)
        self.sp_density_pulse.setDecimals(3)
        self.sp_density_pulse.setValue(d["densityPulse"])

        self.sp_cluster_count = QtWidgets.QSpinBox()
        self.sp_cluster_count.setRange(1, 128)
        self.sp_cluster_count.setValue(d["clusterCount"])

        self.sp_cluster_spread = QtWidgets.QDoubleSpinBox()
        self.sp_cluster_spread.setRange(0.0, 1.0)
        self.sp_cluster_spread.setSingleStep(0.01)
        self.sp_cluster_spread.setDecimals(3)
        self.sp_cluster_spread.setValue(d["clusterSpread"])

        self.sp_repel_force = QtWidgets.QDoubleSpinBox()
        self.sp_repel_force.setRange(0.0, 1.0)
        self.sp_repel_force.setSingleStep(0.01)
        self.sp_repel_force.setDecimals(3)
        self.sp_repel_force.setValue(d["repelForce"])

        self.sp_noise_warp = QtWidgets.QDoubleSpinBox()
        self.sp_noise_warp.setRange(0.0, 1.0)
        self.sp_noise_warp.setSingleStep(0.01)
        self.sp_noise_warp.setDecimals(3)
        self.sp_noise_warp.setValue(d["noiseWarp"])

        self.sp_field_flow = QtWidgets.QDoubleSpinBox()
        self.sp_field_flow.setRange(0.0, 5.0)
        self.sp_field_flow.setSingleStep(0.1)
        self.sp_field_flow.setDecimals(3)
        self.sp_field_flow.setValue(d["fieldFlow"])

        self.rows = {}
        self.rows["densityMode"] = row(form, "Répartition", self.cb_density_mode, TOOLTIPS["distribution.densityMode"], lambda: self.cb_density_mode.setCurrentText(d["densityMode"]))
        self.rows["sampler"] = row(form, "Échantillonnage", self.cb_sampler, TOOLTIPS["distribution.sampler"], lambda: self.cb_sampler.setCurrentText(d["sampler"]))
        self.rows["dmin"] = row(form, "Distance minimale (3D)", self.sp_dmin, TOOLTIPS["distribution.dmin"], lambda: self.sp_dmin.setValue(d["dmin"]))
        self.rows["dmin_px"] = row(form, "Distance écran (px)", self.sp_dmin_px, TOOLTIPS["distribution.dmin_px"], lambda: self.sp_dmin_px.setValue(d["dmin_px"]))
        self.rows["maskMode"] = row(form, "Masque spatial", self.cb_mask_mode, TOOLTIPS["distribution.maskMode"], lambda: self.cb_mask_mode.setCurrentText(d["maskMode"]))
        self.rows["maskSoftness"] = row(form, "Adoucissement", self.sp_mask_soft, TOOLTIPS["distribution.maskSoftness"], lambda: self.sp_mask_soft.setValue(d["maskSoftness"]))
        self.rows["maskAnimate"] = row(form, "Animation masque", self.sp_mask_animate, TOOLTIPS["distribution.maskAnimate"], lambda: self.sp_mask_animate.setValue(d["maskAnimate"]))
        self.rows["noiseDistortion"] = row(form, "Distorsion bruit", self.sp_noise_distortion, TOOLTIPS["distribution.noiseDistortion"], lambda: self.sp_noise_distortion.setValue(d["noiseDistortion"]))
        self.rows["densityPulse"] = row(form, "Impulsion densité", self.sp_density_pulse, TOOLTIPS["distribution.densityPulse"], lambda: self.sp_density_pulse.setValue(d["densityPulse"]))
        self.rows["clusterCount"] = row(form, "Groupes", self.sp_cluster_count, TOOLTIPS["distribution.clusterCount"], lambda: self.sp_cluster_count.setValue(d["clusterCount"]))
        self.rows["clusterSpread"] = row(form, "Écartement groupes", self.sp_cluster_spread, TOOLTIPS["distribution.clusterSpread"], lambda: self.sp_cluster_spread.setValue(d["clusterSpread"]))
        self.rows["repelForce"] = row(form, "Répulsion locale", self.sp_repel_force, TOOLTIPS["distribution.repelForce"], lambda: self.sp_repel_force.setValue(d["repelForce"]))
        self.rows["noiseWarp"] = row(form, "Warp bruit", self.sp_noise_warp, TOOLTIPS["distribution.noiseWarp"], lambda: self.sp_noise_warp.setValue(d["noiseWarp"]))
        self.rows["fieldFlow"] = row(form, "Champ vectoriel", self.sp_field_flow, TOOLTIPS["distribution.fieldFlow"], lambda: self.sp_field_flow.setValue(d["fieldFlow"]))

        widgets = [
            self.cb_density_mode, self.cb_sampler, self.sp_dmin, self.sp_dmin_px,
            self.cb_mask_mode, self.sp_mask_soft, self.sp_mask_animate,
            self.sp_noise_distortion, self.sp_density_pulse,
            self.sp_cluster_count, self.sp_cluster_spread,
            self.sp_repel_force, self.sp_noise_warp, self.sp_field_flow,
        ]
        for w in widgets:
            if isinstance(w, QtWidgets.QDoubleSpinBox):
                w.valueChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QSpinBox):
                w.valueChanged.connect(self.emit_delta)
            else:
                w.currentIndexChanged.connect(self.emit_delta)

        self.cb_mask_mode.currentIndexChanged.connect(self._update_row_states)
        self.sp_cluster_count.valueChanged.connect(self._update_row_states)
        self.cb_sampler.currentIndexChanged.connect(self._update_row_states)

        self._update_row_states()

    def collect(self):
        return dict(
            densityMode=self.cb_density_mode.currentText(),
            sampler=self.cb_sampler.currentText(),
            dmin=self.sp_dmin.value(),
            dmin_px=self.sp_dmin_px.value(),
            maskMode=self.cb_mask_mode.currentText(),
            maskSoftness=self.sp_mask_soft.value(),
            maskAnimate=self.sp_mask_animate.value(),
            noiseDistortion=self.sp_noise_distortion.value(),
            densityPulse=self.sp_density_pulse.value(),
            clusterCount=self.sp_cluster_count.value(),
            clusterSpread=self.sp_cluster_spread.value(),
            repelForce=self.sp_repel_force.value(),
            noiseWarp=self.sp_noise_warp.value(),
            fieldFlow=self.sp_field_flow.value(),
        )

    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["distribution"]
        mapping = {
            self.cb_density_mode: cfg.get("densityMode", d["densityMode"]),
            self.cb_sampler: cfg.get("sampler", d["sampler"]),
            self.sp_dmin: cfg.get("dmin", d["dmin"]),
            self.sp_dmin_px: cfg.get("dmin_px", d["dmin_px"]),
            self.cb_mask_mode: cfg.get("maskMode", d["maskMode"]),
            self.sp_mask_soft: cfg.get("maskSoftness", d["maskSoftness"]),
            self.sp_mask_animate: cfg.get("maskAnimate", d["maskAnimate"]),
            self.sp_noise_distortion: cfg.get("noiseDistortion", d["noiseDistortion"]),
            self.sp_density_pulse: cfg.get("densityPulse", d["densityPulse"]),
            self.sp_cluster_count: cfg.get("clusterCount", d["clusterCount"]),
            self.sp_cluster_spread: cfg.get("clusterSpread", d["clusterSpread"]),
            self.sp_repel_force: cfg.get("repelForce", d["repelForce"]),
            self.sp_noise_warp: cfg.get("noiseWarp", d["noiseWarp"]),
            self.sp_field_flow: cfg.get("fieldFlow", d["fieldFlow"]),
        }
        for widget, value in mapping.items():
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                else:
                    widget.setValue(float(value))
        self._update_row_states()

    def set_enabled(self, context: dict):
        pass

    def emit_delta(self, *args):
        self.changed.emit({"distribution": self.collect()})

    def _update_row_states(self, *args):
        mask_active = self.cb_mask_mode.currentText() != "none"
        for key in ("maskSoftness", "maskAnimate"):
            row_widget = self.rows[key]
            row_widget.setVisible(mask_active)
            label = getattr(row_widget, "_form_label", None)
            if label is not None:
                label.setVisible(mask_active)
        cluster_active = self.sp_cluster_count.value() > 1
        row_widget = self.rows["clusterSpread"]
        row_widget.setEnabled(cluster_active)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setEnabled(cluster_active)
        sampler = self.cb_sampler.currentText()
        show_dmin = sampler in ("blue_noise", "direct", "weighted_sampling")
        row_widget = self.rows["dmin"]
        row_widget.setVisible(show_dmin)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setVisible(show_dmin)
