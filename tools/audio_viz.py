# Disalbed module

# import sys
# import numpy as np
# import traceback
# from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
#                              QComboBox, QLabel, QMessageBox, QFrame)
# from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
# from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient

# # Attempt import of pyaudiowpatch
# try:
#     import pyaudiowpatch as pyaudio
# except ImportError:
#     pyaudio = None

# from components.styles import (
#     C_BG_MAIN, C_BG_SURFACE, C_BG_INPUT, C_BORDER, 
#     C_PRIMARY, C_SECONDARY, C_TEXT_MAIN
# )

# # --- CONFIGURATION ---
# CHUNK_SIZE = 1024  # Samples per frame (determines responsiveness vs frequency resolution)
# BAR_COUNT = 60     # How many bars to draw

# class AudioWorker(QThread):
#     """
#     Captures system audio via WASAPI Loopback and processes FFT.
#     Does NOT record to file.
#     """
#     # Emits normalized array (0.0 to 1.0) of size BAR_COUNT
#     data_processed = pyqtSignal(np.ndarray)
#     error_occurred = pyqtSignal(str)
#     status_update = pyqtSignal(str)

#     def __init__(self, device_index=None):
#         super().__init__()
#         self.device_index = device_index
#         self.running = False
#         self.p = None
#         self.stream = None

#     def run(self):
#         if not pyaudio:
#             self.error_occurred.emit("pyaudiowpatch is not installed.")
#             return

#         self.running = True
        
#         # Context manager style for PyAudio instance
#         with pyaudio.PyAudio() as self.p:
#             try:
#                 target_device = None
                
#                 # 1. Select Device
#                 if self.device_index is not None:
#                     # User selected a specific device
#                     target_device = self.p.get_device_info_by_index(self.device_index)
#                 else:
#                     # Try to get the Default WASAPI Loopback (System Audio)
#                     try:
#                         target_device = self.p.get_default_wasapi_loopback()
#                     except OSError:
#                         self.error_occurred.emit("WASAPI Loopback not found. Are you on Windows?")
#                         return

#                 self.status_update.emit(f"Listening to: {target_device['name']}")

#                 # 2. Configure Stream Parameters
#                 rate = int(target_device["defaultSampleRate"])
#                 channels = target_device["maxInputChannels"]
                
#                 # 3. Open Stream
#                 self.stream = self.p.open(
#                     format=pyaudio.paInt16,
#                     channels=channels,
#                     rate=rate,
#                     input=True,
#                     input_device_index=target_device["index"],
#                     frames_per_buffer=CHUNK_SIZE
#                 )

#                 # 4. Processing Loop
#                 while self.running:
#                     # Read raw data (non-blocking if possible, but standard read is blocking)
#                     # We use exception_on_overflow=False to prevent crashes if CPU lags
#                     try:
#                         raw_data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
#                     except OSError:
#                         # Sometimes happens on device switch or buffer issue
#                         continue

#                     # Convert bytes to Numpy array (Int16)
#                     audio_data = np.frombuffer(raw_data, dtype=np.int16)
                    
#                     # Handle Stereo (or multi-channel) -> Average to Mono
#                     if channels > 1:
#                         audio_data = audio_data.reshape(-1, channels)
#                         audio_data = audio_data.mean(axis=1)

#                     # --- FFT PROCESSING ---
                    
#                     # 1. Apply Window Function (Hanning) to smooth signal edges
#                     # This reduces spectral leakage
#                     window = np.hanning(len(audio_data))
#                     audio_data = audio_data * window

#                     # 2. Compute FFT (Fast Fourier Transform)
#                     # rfft gives us the positive frequency components
#                     fft_spectrum = np.abs(np.fft.rfft(audio_data))
                    
#                     # 3. Resample/Binning to BAR_COUNT
#                     # We split the spectrum into BAR_COUNT chunks and take the max/avg of each
#                     n_bins = len(fft_spectrum)
                    
#                     # We generally care about 0 to ~20kHz. 
#                     # For visualizers, lower frequencies (bass) are often more interesting,
#                     # so a logarithmic index spacing is often used, but we'll use linear for simplicity here.
#                     indices = np.linspace(0, n_bins - 10, BAR_COUNT + 1, dtype=int)
                    
#                     bar_data = np.zeros(BAR_COUNT)
                    
#                     for i in range(BAR_COUNT):
#                         start_i = indices[i]
#                         end_i = indices[i+1]
#                         if end_i == start_i: end_i += 1
                        
#                         # Use max value in this frequency bin
#                         bar_data[i] = np.max(fft_spectrum[start_i:end_i])

#                     # 4. Normalization (Log Scale for Decibels)
#                     # Add 1 to avoid log(0)
#                     bar_data = np.log10(bar_data + 1)
                    
#                     # Scale down roughly (experimentally, 16-bit FFT peaks around 5.0 - 7.0 log value)
#                     bar_data = bar_data / 6.5
#                     bar_data = np.clip(bar_data, 0, 1)

#                     self.data_processed.emit(bar_data)

#             except Exception as e:
#                 # traceback.print_exc()
#                 self.error_occurred.emit(str(e))
#             finally:
#                 # Clean up stream
#                 if self.stream:
#                     self.stream.stop_stream()
#                     self.stream.close()

#     def stop(self):
#         self.running = False
#         self.wait()

# class VisualizerCanvas(QWidget):
#     """
#     Renders the audio data as bars.
#     """
#     def __init__(self):
#         super().__init__()
#         self.bars = np.zeros(BAR_COUNT)
#         self.peaks = np.zeros(BAR_COUNT)
#         self.setMinimumHeight(250)
#         self.setStyleSheet(f"background-color: {C_BG_MAIN}; border: 1px solid {C_BORDER};")
        
#         # Animation physics
#         self.decay = 0.3       # How fast bars fall
#         self.peak_decay = 0.01 # How fast peak dots fall

#     def update_data(self, new_data):
#         if len(new_data) != len(self.bars):
#             return

#         # Smooth interpolation
#         self.bars = self.bars * (1 - self.decay) + new_data * self.decay
        
#         # Calculate peaks
#         for i in range(len(self.bars)):
#             if self.bars[i] > self.peaks[i]:
#                 self.peaks[i] = self.bars[i]
#             else:
#                 self.peaks[i] -= self.peak_decay
#                 if self.peaks[i] < 0: self.peaks[i] = 0
        
#         self.update() # Schedule repaint

#     def paintEvent(self, event):
#         painter = QPainter(self)
#         painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
#         w = self.width()
#         h = self.height()
        
#         # Calculate width of a single bar
#         bar_width = w / len(self.bars)
        
#         for i, val in enumerate(self.bars):
#             # Calculate Height
#             bar_h = val * h
            
#             x = i * bar_width
#             y = h - bar_h
            
#             # --- Draw Bar with Gradient ---
#             gradient = QLinearGradient(x, h, x, 0)
#             gradient.setColorAt(0, QColor(C_SECONDARY)) # Bottom color (Dark Orange)
#             gradient.setColorAt(1, QColor(C_PRIMARY))   # Top color (Bright Orange)
            
#             # Draw rect (add small padding for separation)
#             rect = QRectF(x + 1, y, bar_width - 2, bar_h)
#             painter.fillRect(rect, QBrush(gradient))
            
#             # --- Draw Peak Line ---
#             peak_y = h - (self.peaks[i] * h)
#             painter.setPen(QPen(QColor(C_TEXT_MAIN), 2))
#             painter.drawLine(int(x + 1), int(peak_y), int(x + bar_width - 2), int(peak_y))

# class AudioVisualizerTool(QWidget):
#     statusMessage = pyqtSignal(str)

#     def __init__(self):
#         super().__init__()
#         self.worker = None
#         self.init_ui()
#         # Scan on load
#         self.scan_devices()

#     def init_ui(self):
#         layout = QVBoxLayout(self)
#         layout.setSpacing(10)
        
#         # Header Controls
#         control_bar = QHBoxLayout()
        
#         lbl = QLabel("SOURCE:")
#         lbl.setStyleSheet(f"font-weight:bold; color:{C_TEXT_MAIN};")
        
#         self.combo = QComboBox()
#         self.combo.setMinimumWidth(350)
#         self.combo.setToolTip("Select a Loopback device to capture system audio")
        
#         btn_refresh = QPushButton("REFRESH")
#         btn_refresh.clicked.connect(self.scan_devices)
        
#         self.btn_toggle = QPushButton("START VISUALIZER")
#         self.btn_toggle.setCheckable(True)
#         self.btn_toggle.clicked.connect(self.toggle_capture)
        
#         control_bar.addWidget(lbl)
#         control_bar.addWidget(self.combo)
#         control_bar.addWidget(btn_refresh)
#         control_bar.addWidget(self.btn_toggle)
#         control_bar.addStretch()
        
#         layout.addLayout(control_bar)
        
#         # Canvas
#         self.canvas = VisualizerCanvas()
#         layout.addWidget(self.canvas, stretch=1)

#     def scan_devices(self):
#         """
#         Populate ComboBox with WASAPI Loopback devices.
#         """
#         if not pyaudio:
#             self.combo.addItem("Error: pyaudiowpatch missing")
#             self.combo.setEnabled(False)
#             return

#         self.combo.clear()
#         self.combo.addItem("Default System Audio (Auto)", None)
        
#         p = pyaudio.PyAudio()
#         try:
#             # We specifically look for the WASAPI host API
#             try:
#                 wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
#                 host_index = wasapi_info['index']
#             except OSError:
#                 self.combo.addItem("WASAPI not found", None)
#                 return

#             # Iterate all devices to find those belonging to WASAPI
#             for i in range(p.get_device_count()):
#                 dev = p.get_device_info_by_index(i)
#                 if dev['hostApi'] == host_index:
#                     # In WASAPI, Loopback devices usually appear as input sources, 
#                     # but pyaudiowpatch exposes loopback capability on output devices too.
#                     # We list output devices because we want to capture what is playing OUT.
#                     if dev['maxOutputChannels'] > 0:
#                         self.combo.addItem(f"{dev['name']} [Loopback]", i)

#         except Exception as e:
#             self.statusMessage.emit(f"Scan error: {e}")
#         finally:
#             p.terminate()

#     def toggle_capture(self):
#         if self.btn_toggle.isChecked():
#             # Start
#             device_data = self.combo.currentData() # returns device index or None
            
#             self.start_worker(device_data)
            
#             self.btn_toggle.setText("STOP VISUALIZER")
#             self.btn_toggle.setStyleSheet(f"background-color: {C_PRIMARY}; color: {C_BG_MAIN};")
#             self.combo.setEnabled(False)
#         else:
#             # Stop
#             self.stop_worker()
            
#             self.btn_toggle.setText("START VISUALIZER")
#             self.btn_toggle.setStyleSheet("")
#             self.combo.setEnabled(True)

#     def start_worker(self, device_index):
#         if self.worker:
#             self.worker.stop()
        
#         self.worker = AudioWorker(device_index)
#         self.worker.data_processed.connect(self.canvas.update_data)
#         self.worker.error_occurred.connect(self.handle_error)
#         self.worker.status_update.connect(self.statusMessage.emit)
#         self.worker.start()

#     def stop_worker(self):
#         if self.worker:
#             self.worker.stop()
#             self.worker = None
#         # Clear canvas
#         self.canvas.update_data(np.zeros(BAR_COUNT))
#         self.statusMessage.emit("Visualizer stopped.")

#     def handle_error(self, msg):
#         self.statusMessage.emit(f"Error: {msg}")
#         QMessageBox.critical(self, "Audio Error", msg)
#         self.btn_toggle.setChecked(False)
#         self.toggle_capture()

#     def cleanup(self):
#         """Safe cleanup when tab is closed"""
#         self.stop_worker()