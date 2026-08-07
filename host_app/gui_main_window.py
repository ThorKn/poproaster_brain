import sys
import time
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QSlider, QSpinBox, QGroupBox, 
    QTextEdit, QSplitter, QCheckBox, QFileDialog, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QColor, QFont

import pyqtgraph as pg
import serial.tools.list_ports

from config_loader import ConfigLoader
from modbus_worker import ModbusWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_loader = ConfigLoader()
        self.worker = None
        self.start_time = time.time()

        # Data buffers for pyqtgraph
        self.time_buffer = []
        self.sensor_buffers = {}
        self.actor_buffers = {}
        self.sensor_curves = {}
        self.actor_curves = {}

        self.actor_controls = {}
        self.sensor_labels = {}
        self.sensor_badges = {}
        self.heater_led_label = None

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle(f"PopRoaster App - {self.config_loader.system.get('device_name', 'PopRoaster Brain')}")
        self.resize(1100, 750)

        # Apply Modern Dark Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
            QGroupBox { font-weight: bold; border: 1px solid #45475a; border-radius: 6px; margin-top: 10px; padding-top: 10px; color: #89b4fa; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:pressed { background-color: #585b70; }
            QComboBox, QSpinBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px; }
            QSlider::groove:horizontal { border: 1px solid #45475a; height: 8px; background: #313244; border-radius: 4px; }
            QSlider::handle:horizontal { background: #89b4fa; border: 1px solid #89b4fa; width: 16px; margin-top: -4px; margin-bottom: -4px; border-radius: 8px; }
            QTextEdit { background-color: #11111b; color: #a6adc8; font-family: monospace; border: 1px solid #313244; }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. Top Connection Header
        header_box = QGroupBox("Connection & Status")
        header_layout = QHBoxLayout(header_box)

        header_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        header_layout.addWidget(self.port_combo)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        header_layout.addWidget(self.btn_refresh)

        header_layout.addWidget(QLabel("Slave ID:"))
        self.spin_slave_id = QSpinBox()
        self.spin_slave_id.setRange(1, 247)
        self.spin_slave_id.setValue(self.config_loader.slave_id)
        header_layout.addWidget(self.spin_slave_id)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)
        header_layout.addWidget(self.btn_connect)

        header_layout.addStretch()

        # Color-Blind Accessible Connection Status Badge
        self.status_badge = QLabel("[✗] DISCONNECTED")
        self.status_badge.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.update_status_badge("[✗] DISCONNECTED", "disconnected")
        header_layout.addWidget(self.status_badge)

        main_layout.addWidget(header_box)

        # 2. Main Content Splitter (Left Sidebar Controls + Center Plot)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Sidebar (Controls & Telemetry)
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # Actors Control Box
        actors_box = QGroupBox("Actors Control")
        actors_layout = QVBoxLayout(actors_box)

        for actor in self.config_loader.actors:
            actor_id = actor.get("id")
            actor_name = actor.get("name")
            holding_reg = actor.get("modbus_holding_reg")
            has_led = actor.get("status_led_pin") is not None and actor.get("status_led_pin") >= 0

            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(4, 4, 4, 4)

            title_row = QHBoxLayout()
            title_label = QLabel(f"<b>{actor_name}</b> (Reg {holding_reg})")
            title_row.addWidget(title_label)

            if has_led:
                self.heater_led_label = QLabel("LED: OFF ⚪")
                self.heater_led_label.setStyleSheet("color: #a6adc8;")
                title_row.addWidget(self.heater_led_label)

            card_layout.addLayout(title_row)

            ctrl_row = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setSuffix("%")

            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            spin.valueChanged.connect(lambda val, r=holding_reg: self.on_actor_value_changed(r, val))

            ctrl_row.addWidget(slider)
            ctrl_row.addWidget(spin)
            card_layout.addLayout(ctrl_row)

            actors_layout.addWidget(card)
            self.actor_controls[actor_id] = (slider, spin)
            self.actor_buffers[actor_id] = []

        sidebar_layout.addWidget(actors_box)

        # Sensors Readout Box
        sensors_box = QGroupBox("Sensors Telemetry")
        sensors_layout = QVBoxLayout(sensors_box)

        for sensor in self.config_loader.sensors:
            sensor_id = sensor.get("id")
            sensor_name = sensor.get("name")
            input_reg = sensor.get("modbus_input_reg")

            card = QWidget()
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(4, 4, 4, 4)

            lbl_name = QLabel(f"<b>{sensor_name}</b>:")
            lbl_val = QLabel("--.- °C")
            lbl_val.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            lbl_val.setStyleSheet("color: #a6e3a1;")

            badge = QLabel("[✓] NORMAL")
            badge.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")

            card_layout.addWidget(lbl_name)
            card_layout.addWidget(lbl_val)
            card_layout.addStretch()
            card_layout.addWidget(badge)

            sensors_layout.addWidget(card)
            self.sensor_labels[sensor_id] = lbl_val
            self.sensor_badges[sensor_id] = badge
            self.sensor_buffers[sensor_id] = []

        sidebar_layout.addWidget(sensors_box)
        sidebar_layout.addStretch()

        content_splitter.addWidget(sidebar_widget)

        # Center Real-Time Graph View (pyqtgraph)
        graph_box = QGroupBox("Real-Time Telemetry Graph")
        graph_layout = QVBoxLayout(graph_box)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#11111b')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', 'Elapsed Time (s)')
        self.plot_widget.setLabel('left', 'Temperature (°C)', color='#a6e3a1')

        # Custom secondary ViewBox for Actor duty cycles %
        self.actor_view = pg.ViewBox()
        self.plot_widget.scene().addItem(self.actor_view)
        self.plot_widget.getAxis('right').linkToView(self.actor_view)
        self.actor_view.setXLink(self.plot_widget.getViewBox())
        self.plot_widget.showAxis('right')
        self.plot_widget.setLabel('right', 'Actor Duty Cycle (%)', color='#89b4fa')
        self.actor_view.setYRange(0, 100)

        # Connect view resize
        self.plot_widget.getViewBox().sigResized.connect(self.update_actor_view_geometry)

        # Create plot curves
        colors = ['#f38ba8', '#fab387', '#f9e2af', '#94e2d5']
        for idx, sensor in enumerate(self.config_loader.sensors):
            sid = sensor.get("id")
            pen = pg.mkPen(color=colors[idx % len(colors)], width=2)
            self.sensor_curves[sid] = self.plot_widget.plot(name=sensor.get("name"), pen=pen)

        actor_colors = ['#89b4fa', '#cba6f7', '#74c7ec']
        for idx, actor in enumerate(self.config_loader.actors):
            aid = actor.get("id")
            pen = pg.mkPen(color=actor_colors[idx % len(actor_colors)], width=1.5, style=Qt.PenStyle.DashLine)
            curve = pg.PlotCurveItem(pen=pen)
            self.actor_view.addItem(curve)
            self.actor_curves[aid] = curve

        graph_layout.addWidget(self.plot_widget)

        graph_ctrl_row = QHBoxLayout()
        btn_reset_graph = QPushButton("Reset Graph View")
        btn_reset_graph.clicked.connect(self.reset_graph)
        graph_ctrl_row.addWidget(btn_reset_graph)
        graph_ctrl_row.addStretch()
        graph_layout.addLayout(graph_ctrl_row)

        content_splitter.addWidget(graph_box)
        content_splitter.setSizes([350, 750])

        # 3. Bottom Modbus Packet Inspector Console
        log_box = QGroupBox("Modbus Packet Inspector")
        log_layout = QVBoxLayout(log_box)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(140)
        log_layout.addWidget(self.log_console)

        log_btn_row = QHBoxLayout()
        self.chk_pause_log = QCheckBox("Pause Auto-scroll")
        log_btn_row.addWidget(self.chk_pause_log)

        btn_clear_log = QPushButton("Clear Console")
        btn_clear_log.clicked.connect(self.log_console.clear)
        log_btn_row.addWidget(btn_clear_log)

        btn_export_log = QPushButton("Export Log...")
        btn_export_log.clicked.connect(self.export_log)
        log_btn_row.addWidget(btn_export_log)

        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        # Outer Layout Assembly
        outer_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_splitter.addWidget(content_splitter)
        outer_splitter.addWidget(log_box)
        outer_splitter.setSizes([550, 180])

        main_layout.addWidget(outer_splitter)

        self.refresh_ports()

    def update_actor_view_geometry(self):
        self.actor_view.setGeometry(self.plot_widget.getViewBox().sceneBoundingRect())

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(f"{p.device} ({p.description})", p.device)

    def update_status_badge(self, text, state):
        self.status_badge.setText(text)
        if state == "connected":
            self.status_badge.setStyleSheet("background-color: #a6e3a1; color: #11111b; border-radius: 4px; padding: 4px 10px;")
        elif state == "warning":
            self.status_badge.setStyleSheet("background-color: #f9e2af; color: #11111b; border-radius: 4px; padding: 4px 10px;")
        else:
            self.status_badge.setStyleSheet("background-color: #f38ba8; color: #11111b; border-radius: 4px; padding: 4px 10px;")

    def toggle_connection(self):
        if self.worker and self.worker.is_running:
            self.worker.stop()
            self.worker = None
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("")
            self.update_status_badge("[✗] DISCONNECTED", "disconnected")
        else:
            port = self.port_combo.currentData() or self.port_combo.currentText()
            if not port:
                self.append_log(time.strftime("%H:%M:%S"), "", 0, "No serial port selected!")
                return

            self.worker = ModbusWorker(self.config_loader)
            self.worker.set_connection_params(port=port, slave_id=self.spin_slave_id.value())
            self.worker.connection_status_changed.connect(self.on_connection_status_changed)
            self.worker.sensor_data_received.connect(self.on_sensor_data_received)
            self.worker.log_emitted.connect(self.append_log)
            self.worker.start()

            self.btn_connect.setText("Disconnect")
            self.btn_connect.setStyleSheet("background-color: #f38ba8; color: #11111b;")

    def on_connection_status_changed(self, text, state):
        self.update_status_badge(text, state)
        if self.heater_led_label:
            if state == "warning":
                self.heater_led_label.setText("LED: WARN 🟡")
                self.heater_led_label.setStyleSheet("color: #f9e2af;")
            elif state == "disconnected":
                self.heater_led_label.setText("LED: OFF ⚪")
                self.heater_led_label.setStyleSheet("color: #a6adc8;")

    def on_actor_value_changed(self, holding_reg, value):
        if self.worker and self.worker.is_running:
            self.worker.request_write_actor(holding_reg, value)
        
        # Update local actor history
        for aid, actor in enumerate(self.config_loader.actors):
            if actor.get("modbus_holding_reg") == holding_reg:
                actor_id = actor.get("id")
                if actor_id == "heater" and self.heater_led_label:
                    if value > 0:
                        self.heater_led_label.setText("LED: ON 🔴")
                        self.heater_led_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
                    else:
                        self.heater_led_label.setText("LED: OFF ⚪")
                        self.heater_led_label.setStyleSheet("color: #a6adc8;")

    def on_sensor_data_received(self, sensor_id, temp_c, is_fault):
        now_rel = time.time() - self.start_time
        self.time_buffer.append(now_rel)

        # Update readout and badge
        lbl = self.sensor_labels.get(sensor_id)
        badge = self.sensor_badges.get(sensor_id)

        if is_fault:
            if lbl: lbl.setText("ERR °C"); lbl.setStyleSheet("color: #f38ba8;")
            if badge:
                badge.setText("[⚠] FAULT")
                badge.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")
            self.sensor_buffers[sensor_id].append(0.0)
        else:
            if lbl: lbl.setText(f"{temp_c:.1f} °C"); lbl.setStyleSheet("color: #a6e3a1;")
            if badge:
                badge.setText("[✓] NORMAL")
                badge.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")
            self.sensor_buffers[sensor_id].append(temp_c)

        # Append current actor states to history
        for actor in self.config_loader.actors:
            aid = actor.get("id")
            spin = self.actor_controls.get(aid, (None, None))[1]
            val = spin.value() if spin else 0
            self.actor_buffers[aid].append(val)

        # Update curves
        for sid, curve in self.sensor_curves.items():
            if sid in self.sensor_buffers:
                curve.setData(self.time_buffer, self.sensor_buffers[sid])

        for aid, curve in self.actor_curves.items():
            if aid in self.actor_buffers:
                curve.setData(self.time_buffer, self.actor_buffers[aid])

    def append_log(self, timestamp, hex_frame, latency_ms, detail):
        msg = f"[{timestamp}] {detail}"
        if hex_frame:
            msg += f" | Frame: {hex_frame}"
        if latency_ms > 0:
            msg += f" ({latency_ms} ms)"
        
        self.log_console.append(msg)
        if not self.chk_pause_log.isChecked():
            self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())

    def reset_graph(self):
        self.time_buffer.clear()
        for k in self.sensor_buffers: self.sensor_buffers[k].clear()
        for k in self.actor_buffers: self.actor_buffers[k].clear()
        self.start_time = time.time()
        for curve in self.sensor_curves.values(): curve.setData([], [])
        for curve in self.actor_curves.values(): curve.setData([], [])

    def export_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Log", "modbus_log.txt", "Text Files (*.txt);;Log Files (*.log)")
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.log_console.toPlainText())

    def load_settings(self):
        settings = QSettings("PopRoaster", "PopRoasterApp")
        last_port = settings.value("last_port", "")
        idx = self.port_combo.findData(last_port)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)

    def closeEvent(self, event):
        if self.worker and self.worker.is_running:
            self.worker.stop()
        
        settings = QSettings("PopRoaster", "PopRoasterApp")
        port = self.port_combo.currentData() or self.port_combo.currentText()
        settings.setValue("last_port", port)
        event.accept()
