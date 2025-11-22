"""
SignalScan PRO - Main GUI Window (PyQt5)
Professional stock scanner interface with real-time data updates
Trading Channels: Live-only from Tier3 signals
News & Halts: Vault system (persistent storage + live updates)
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QStatusBar, QHeaderView, QFrame
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtMultimedia import QSound
from PyQt5.QtGui import QColor, QFont, QPixmap
from datetime import datetime
import pytz
import json
import os


class SoundAlertManager:
    """Manages sound alerts for trading channels"""
    
    def __init__(self, logger):
        self.log = logger
        self.sound_folder = "sounds"
        
        # Load sound files
        self.sounds = {
            'morse_code': QSound(os.path.join(self.sound_folder, "morse_code_alert.wav")),
            'news_flash': QSound(os.path.join(self.sound_folder, "iphone_news_flash.wav")),
            'halt_resume': QSound(os.path.join(self.sound_folder, "halt_resume.wav")),
            'nyse_bell': QSound(os.path.join(self.sound_folder, "nyse_bell.wav")),
            'pregap': QSound(os.path.join(self.sound_folder, "woke_up_this_morning.wav"))
        }
        self.log.scanner("[SOUND] Alert system initialized")
    
    def play_sound(self, sound_name):
        """Play a sound file"""
        if sound_name in self.sounds:
            self.sounds[sound_name].play()
            self.log.scanner(f"[SOUND] Playing {sound_name}")
        else:
            self.log.warning(f"[SOUND] Unknown sound: {sound_name}")

class MainWindow(QMainWindow):
    """Main application window for SignalScan PRO"""
    
    def __init__(self, file_manager, logger, tier1=None, tier3=None, momo_vector=None, momo_squeeze=None, momo_trend=None):
        super().__init__()
        self.fm = file_manager
        self.tier1 = tier1
        self.tier3 = tier3
        self.momo_vector = momo_vector  
        self.momo_squeeze = momo_squeeze  
        self.momo_trend = momo_trend
        self.log = logger
        self.log.scanner("[GUI-DEBUG] MainWindow.__init__ started")
        
        # Window setup - Made wider to fit all tabs
        self.setWindowTitle("SignalScan PRO - US Stock Market Scanner")
        self.setGeometry(50, 50, 500, 500)
        
        # Initialize sound alert manager
        self.sound_alerts = SoundAlertManager(self.log)

        # Initialize UI
        self._init_ui()
        
        # Set up vault refresh timer (update every 5 seconds for news/halts)
        self.vault_refresh_timer = QTimer()
        self.vault_refresh_timer.timeout.connect(self._refresh_vaults)
        self.vault_refresh_timer.start(5000)  # 5000ms = 5 seconds
        
    def _init_ui(self):
        """Initialize the user interface"""
        self.log.scanner("[GUI-DEBUG] _init_ui started")
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Top status bar
        self.status_panel = self._create_status_panel()
        main_layout.addWidget(self.status_panel)
        
        # Tab widget for channels
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setUsesScrollButtons(False)  # Disable scroll buttons to show all tabs
        self.tabs.setElideMode(Qt.ElideNone)   # Don't truncate tab text
        self.tabs.tabBar().setExpanding(True)  # Make tabs expand to fill width
        self.tabs.tabBar().setDrawBase(False)  # Remove base line for cleaner look
        main_layout.addWidget(self.tabs)
        
        # Create channel tabs
        self.pregap_table = self._create_channel_tab("PreGap", ["Symbol", "Price", "Change%", "Time", "Gap%", "Volume", "RVOL", "Float", "News"])
        self.tabs.addTab(self.pregap_table, "PreGap")

        self.hod_table = self._create_channel_tab("HOD", ["Symbol", "Price", "Change%", "Time", "HOD", "Volume", "RVOL", "Float", "News"])
        self.tabs.addTab(self.hod_table, "HOD")

        self.runup_table = self._create_channel_tab("RunUP", ["Symbol", "Price", "Change%", "Time", "5min%", "Volume", "RVOL", "Float", "News"])
        self.tabs.addTab(self.runup_table, "RunUP") 

        self.rvsl_table = self._create_channel_tab("Reversal", ["Symbol", "Price", "Change%", "Time", "Gap%", "Volume", "RVOL", "News"])
        self.tabs.addTab(self.rvsl_table, "Rvsl")

        self.vectortable = self._create_channel_tab("Vector", ["Symbol", "Price", "Change%", "Time", "V-Score", "MTF", "Vol Quality", "VWAP Dist", "Signal"])
        idx = self.tabs.addTab(self.vectortable, "Vector")
        self.tabs.setStyleSheet(self.tabs.styleSheet() + f"""
            QTabBar::tab:nth-child({idx+1}) {{ background-color: #808080; color: #000000; }}
            QTabBar::tab:nth-child({idx+1}):selected {{ background-color: #808080; color: #000000; font-weight: bold; }}
        """)

        self.squeeze_table = self._create_channel_tab("Squeeze", ["Symbol", "Price", "Change%", "Time", "Status", "Intensity", "Histogram", "TF Align", "Setup"])
        idx = self.tabs.addTab(self.squeeze_table, "Squeeze")
        self.tabs.setStyleSheet(self.tabs.styleSheet() + f"""
            QTabBar::tab:nth-child({idx+1}) {{ background-color: #808080; color: #000000; }}
            QTabBar::tab:nth-child({idx+1}):selected {{ background-color: #808080; color: #000000; font-weight: bold; }}
        """)

        self.trend_table = self._create_channel_tab("Trend", ["Symbol", "Price", "Change%", "Time", "Trend STR", "Model", "Confidence", "Direction", "Signal"])
        idx = self.tabs.addTab(self.trend_table, "Trend")
        self.tabs.setStyleSheet(self.tabs.styleSheet() + f"""
            QTabBar::tab:nth-child({idx+1}) {{ background-color: #808080; color: #000000; }}
            QTabBar::tab:nth-child({idx+1}):selected {{ background-color: #808080; color: #000000; font-weight: bold; }}
        """)
        
        self.news_table = self._create_channel_tab("Breaking News", ["Symbol", "Price", "Change%", "Time", "Age", "Headline"])
        self.tabs.addTab(self.news_table, "News")

        self.halt_table = self._create_channel_tab("Halts", ["Symbol", "Status", "Price", "Reason", "Halt Time", "Resume Time"])
        self.tabs.addTab(self.halt_table, "Halts")
        
        # Connect cell click handlers for news popups
        self.pregap_table.cellClicked.connect(self._on_cell_clicked)
        self.hod_table.cellClicked.connect(self._on_cell_clicked)
        self.runup_table.cellClicked.connect(self._on_cell_clicked)
        self.rvsl_table.cellClicked.connect(self._on_cell_clicked)

        # Bottom status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("SignalScan PRO initialized - waiting for data...")
        
        # Apply dark theme styling
        self._apply_stylesheet()
        
    def _create_status_panel(self):
        """Create top status panel"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        panel.setLayout(layout)
        
                # Top row: Logo + Title | NYC time | Market Status | LOCAL time | Buttons
        top_row = QHBoxLayout()
        
        # Left section: Logo + Title
        left_section = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        logo_paths = [
            "logo.jpeg",
            "logo.jpg",
            "logo.png",
            "assets/logo.jpeg",
            "assets/logo.png"
        ]
        
        logo_loaded = False
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                try:
                    logo_pixmap = QPixmap(logo_path)
                    if not logo_pixmap.isNull():
                        logo_pixmap = logo_pixmap.scaled(45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_label.setPixmap(logo_pixmap)
                        logo_label.setStyleSheet("margin-right: 12px;")
                        left_section.addWidget(logo_label)
                        logo_loaded = True
                        self.log.scanner(f"[GUI] Logo loaded from: {logo_path}")
                        break
                except Exception as e:
                    self.log.crash(f"[GUI] Error loading logo from {logo_path}: {e}")
        
        if not logo_loaded:
            self.log.scanner("[GUI] No logo found - continuing without logo")
        
        title = QLabel("SignalScan PRO")
        title.setStyleSheet("font-size: 30px; font-weight: bold; color: #4169E1; margin-right: 20px;")
        left_section.addWidget(title)
        
        top_row.addLayout(left_section)
        top_row.addStretch()
        
        # LOCAL time
        self.local_time_label = QLabel()
        self.local_time_label.setStyleSheet("font-size: 28px; font-weight: bold; padding: 5px; margin-left: 20px; color: #4169E1;")
        top_row.addWidget(self.local_time_label)
        
        top_row.addStretch()
        
        # Center: Market Session
        self.market_session = QLabel("Market: CLOSED")
        self.market_session.setStyleSheet("font-weight: bold; padding: 5px; font-size: 36px;")
        top_row.addWidget(self.market_session)
        
        top_row.addStretch()
        
        # NYC time
        self.nyc_time_label = QLabel()
        self.nyc_time_label.setStyleSheet("font-size: 28px; font-weight: bold; padding: 5px; margin-right: 20px; color: #FFFFFF;")
        top_row.addWidget(self.nyc_time_label)
        
        top_row.addStretch()
        
        # Right section: Control buttons
        buttons_container = QHBoxLayout()
        buttons_container.setSpacing(10)
        
        # NEWS button
        news_btn = QPushButton("📰 NEWS")
        news_btn.setMinimumHeight(35)
        news_btn.setStyleSheet("""
            QPushButton {
                background-color: #0969da;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1158c7;
            }
            QPushButton:pressed {
                background-color: #0550ae;
            }
        """)
        news_btn.clicked.connect(self.on_news_clicked)
        buttons_container.addWidget(news_btn)
        
        # UPDATE button
        update_btn = QPushButton("🔄 UPDATE")
        update_btn.setMinimumHeight(35)
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
        """)
        update_btn.clicked.connect(self.on_update_clicked)
        buttons_container.addWidget(update_btn)
        
        # KIOSK button
        kiosk_btn = QPushButton("🖥️ KIOSK")
        kiosk_btn.setMinimumHeight(35)
        kiosk_btn.setStyleSheet("""
            QPushButton {
                background-color: #6e7681;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #6e7681;
            }
        """)
        kiosk_btn.clicked.connect(self._on_kiosk_clicked)
        buttons_container.addWidget(kiosk_btn)
        
        top_row.addLayout(buttons_container)
        
        layout.addLayout(top_row)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #58a6ff;")
        layout.addWidget(separator)
        
        # Bottom row: Market Indices (horizontal layout)
        indices_row = QHBoxLayout()
        
        indices_row.addStretch()
        
        self.sp500_label = QLabel("S&P 500: --")
        self.sp500_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px;")
        indices_row.addWidget(self.sp500_label)
        
        indices_row.addStretch()
        
        self.nasdaq_label = QLabel("NASDAQ: --")
        self.nasdaq_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px;")
        indices_row.addWidget(self.nasdaq_label)
        
        indices_row.addStretch()
        
        self.dow_label = QLabel("DOW: --")
        self.dow_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px;")
        indices_row.addWidget(self.dow_label)
        
        indices_row.addStretch()
        
        layout.addLayout(indices_row)

        # Update time immediately
        self._update_time()
        
        # Time update timer
        time_timer = QTimer(self)
        time_timer.timeout.connect(self._update_time)
        time_timer.start(1000)
        
        # Indices update timer (every 5 seconds)
        indices_timer = QTimer(self)
        indices_timer.timeout.connect(self._update_indices)
        indices_timer.start(30000)
        
        panel.setStyleSheet("background-color: #000000; padding: 10px;")
        return panel
    
    # =========================================================================
    # LIVE DATA FEED SLOTS - Receive real-time updates from scanners
    # =========================================================================
    
    @pyqtSlot(dict)
    def on_pregap_update(self, stock_data):
        """Receive PreGap channel update (LIVE ONLY)"""
        self.log.scanner(f"[GUI<-TIER3] Received PREGAP signal: {stock_data.get('symbol')}")
        self.log.scanner(f"[GUI-SLOT] OK PREGAP received: {stock_data.get('symbol')}")
        self.sound_alerts.play_sound('pregap')
        self._add_or_update_stock(self.pregap_table, stock_data, [
            'symbol', 'price', 'change_pct', 'timestamp', 'gap_pct', 'volume', 'rvol', 'float', 'news'
        ])
    
        symbol = stock_data.get('symbol')
        row = self._find_row(self.pregap_table, symbol)
        if row >= 0:
            news_data = self._get_news_for_symbol(symbol)
            if news_data:
                news_item = QTableWidgetItem("📰 News")
                news_item.setForeground(QColor(0, 100, 255))
                news_item.setData(Qt.UserRole, news_data)
                self.pregap_table.setItem(row, 8, news_item)
            else:
                self.pregap_table.setItem(row, 8, QTableWidgetItem("-"))

    @pyqtSlot(dict)
    def on_hod_update(self, stock_data):
        """Receive HOD channel update (LIVE ONLY)"""
        self.log.scanner(f"[GUI<-TIER3] Received HOD signal: {stock_data.get('symbol')}")
        self.log.scanner(f"[GUI-SLOT] OK HOD received: {stock_data.get('symbol')}")
        self._add_or_update_stock(self.hod_table, stock_data, [
            'symbol', 'price', 'change_pct', 'timestamp', 'hod_price', 'volume', 'rvol', 'float', 'news'
        ])
        
        symbol = stock_data.get('symbol')
        row = self._find_row(self.hod_table, symbol)
        if row >= 0:
            news_data = self._get_news_for_symbol(symbol)
            if news_data:
                news_item = QTableWidgetItem("📰 News")
                news_item.setForeground(QColor(0, 100, 255))
                news_item.setData(Qt.UserRole, news_data)
                self.hod_table.setItem(row, 8, news_item)
            else:
                self.hod_table.setItem(row, 8, QTableWidgetItem("-"))

    @pyqtSlot(dict)
    def on_runup_update(self, stock_data):
        """Receive RunUP channel update (LIVE ONLY)"""
        self.log.scanner(f"[GUI<-TIER3] Received RUNUP signal: {stock_data.get('symbol')}")
        self.log.scanner(f"[GUI-SLOT] OK RUNUP received: {stock_data.get('symbol')}")
        self._add_or_update_stock(self.runup_table, stock_data, [
            'symbol', 'price', 'change_pct', 'timestamp', 'change_5min', 'volume', 'rvol', 'float', 'news'
        ])
    
        symbol = stock_data.get('symbol')
        row = self._find_row(self.runup_table, symbol)
        if row >= 0:
            news_data = self._get_news_for_symbol(symbol)
            if news_data:
                news_item = QTableWidgetItem("📰 News")
                news_item.setForeground(QColor(0, 100, 255))
                news_item.setData(Qt.UserRole, news_data)
                self.runup_table.setItem(row, 8, news_item)
            else:
                self.runup_table.setItem(row, 8, QTableWidgetItem("-"))

    @pyqtSlot(dict)
    def on_reversal_update(self, stock_data):
        """Receive Reversal channel update (LIVE ONLY)"""
        self.log.scanner(f"[GUI<-TIER3] Received REVERSAL signal: {stock_data.get('symbol')}")
        self.log.scanner(f"[GUI-SLOT] OK REVERSAL received: {stock_data.get('symbol')}")
        self._add_or_update_stock(self.rvsl_table, stock_data, [
            'symbol', 'price', 'change_pct', 'timestamp', 'gap_pct', 'volume', 'rvol', 'float', 'news'
        ])
    
        symbol = stock_data.get('symbol')
        row = self._find_row(self.rvsl_table, symbol)
        if row >= 0:
            news_data = self._get_news_for_symbol(symbol)
            if news_data:
                news_item = QTableWidgetItem("📰 News")
                news_item.setForeground(QColor(0, 100, 255))
                news_item.setData(Qt.UserRole, news_data)
                self.rvsl_table.setItem(row, 7, news_item)  # Column 7 for Reversal
            else:
                self.rvsl_table.setItem(row, 7, QTableWidgetItem("-"))

    @pyqtSlot(dict)
    def on_vector_update(self, data):
        """Handle MOMO Vector updates"""
        try:
            symbol = data.get("symbol", "N/A")
            self.sound_alerts.play_sound('morse_code')
            row = self.find_row(self.vectortable, symbol)
            if row == -1:
                row = self.vectortable.rowCount()
                self.vectortable.insertRow(row)
            
            # Column 0: Symbol
            self.vectortable.setItem(row, 0, QTableWidgetItem(symbol))
            
            # Column 1: Price
            price = data.get("price", 0)
            price_item = QTableWidgetItem(f"{price:.2f}")

            # Column 2: Change%
            changepct = 0
            if self.tier3 and hasattr(self.tier3, 'livedata'):
                livedata = self.tier3.livedata.get(symbol, {})
                changepct = livedata.get("changepct", 0)

            # Apply same color to both price and change
            color = QColor(0, 255, 0) if changepct > 0 else QColor(255, 0, 0)
            price_item.setForeground(color)
            self.vectortable.setItem(row, 1, price_item)

            change_item = QTableWidgetItem(f"{changepct:.2f}%")
            change_item.setForeground(color)
            self.vectortable.setItem(row, 2, change_item)
            
            # Column 3: Time
            timestamp = data.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                est = pytz.timezone("US/Eastern")
                dt_est = dt.astimezone(est)
                time_display = dt_est.strftime("%I:%M%p").lower()
                self.vectortable.setItem(row, 3, QTableWidgetItem(time_display))
            except:
                self.vectortable.setItem(row, 3, QTableWidgetItem("--"))
            
            # Column 4: V-Score
            v_score = data.get("v_score", 0)
            v_item = QTableWidgetItem(f"{v_score:.1f}")
            v_item.setForeground(QColor(0, 255, 0) if v_score > 0 else QColor(255, 0, 0))
            self.vectortable.setItem(row, 4, v_item)
            
            # Column 5: MTF
            mtf = data.get("mtf_alignment", "")
            self.vectortable.setItem(row, 5, QTableWidgetItem(mtf))
            
            # Column 6: Vol Quality
            vol_quality = data.get("vol_quality", 0)
            self.vectortable.setItem(row, 6, QTableWidgetItem(f"{vol_quality:.2f}"))
            
            # Column 7: VWAP Dist
            vwap_dist = data.get("vwap_dist", 0)
            self.vectortable.setItem(row, 7, QTableWidgetItem(f"{vwap_dist:.2f}σ"))
            
            # Column 8: Signal
            signal = data.get("signal", "WATCH")
            signal_item = QTableWidgetItem(signal)
            signal_item.setFont(QFont("Arial", 10, QFont.Bold))
            if "BUY" in signal:
                signal_item.setForeground(QColor(0, 255, 0))
            elif "SELL" in signal:
                signal_item.setForeground(QColor(255, 0, 0))
            self.vectortable.setItem(row, 8, signal_item)
            
        except Exception as e:
            self.log.crash(f"[GUI] Error handling Vector update: {e}")

    @pyqtSlot(dict)
    def on_squeeze_update(self, data):
        """Handle MOMO Squeeze updates"""
        try:
            symbol = data.get("symbol", "N/A")
            self.sound_alerts.play_sound('morse_code')
            row = self.find_row(self.squeezetable, symbol)
            if row == -1:
                row = self.squeezetable.rowCount()
                self.squeezetable.insertRow(row)
            
            # Column 0: Symbol
            self.squeezetable.setItem(row, 0, QTableWidgetItem(symbol))
            
            # Column 1: Price
            price = data.get("price", 0)
            price_item = QTableWidgetItem(f"{price:.2f}")

            # Column 2: Change%
            changepct = 0
            if self.tier3 and hasattr(self.tier3, 'livedata'):
                livedata = self.tier3.livedata.get(symbol, {})
                changepct = livedata.get("changepct", 0)

            # Apply same color to both price and change
            color = QColor(0, 255, 0) if changepct > 0 else QColor(255, 0, 0)
            price_item.setForeground(color)
            self.squeezetable.setItem(row, 1, price_item)

            change_item = QTableWidgetItem(f"{changepct:.2f}%")
            change_item.setForeground(color)
            self.squeezetable.setItem(row, 2, change_item)
            
            # Column 3: Time
            timestamp = data.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                est = pytz.timezone("US/Eastern")
                dt_est = dt.astimezone(est)
                time_display = dt_est.strftime("%I:%M%p").lower()
                self.squeezetable.setItem(row, 3, QTableWidgetItem(time_display))
            except:
                self.squeezetable.setItem(row, 3, QTableWidgetItem("--"))

                        # Column 4: Status
            status = data.get("status", "IDLE")
            status_item = QTableWidgetItem(status)
            if status == "COILING":
                status_item.setForeground(QColor(255, 165, 0))
            elif status == "FIRED":
                status_item.setForeground(QColor(0, 255, 0))
                status_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.squeezetable.setItem(row, 4, status_item)
            
            # Column 5: Intensity
            intensity = data.get("intensity", 0)
            self.squeezetable.setItem(row, 5, QTableWidgetItem(f"{intensity:.2f}"))
            
            # Column 6: Histogram
            histogram = data.get("histogram", 0)
            hist_item = QTableWidgetItem(f"{histogram:.3f}")
            hist_item.setForeground(QColor(0, 255, 0) if histogram > 0 else QColor(255, 0, 0))
            self.squeezetable.setItem(row, 6, hist_item)
            
            # Column 7: TF Align
            self.squeezetable.setItem(row, 7, QTableWidgetItem("✓" if status == "FIRED" else "--"))
            
            # Column 8: Setup
            setup = data.get("setup", "WAIT")
            setup_item = QTableWidgetItem(setup)
            setup_item.setFont(QFont("Arial", 10, QFont.Bold))
            if "LONG" in setup:
                setup_item.setForeground(QColor(0, 255, 0))
            elif "SHORT" in setup:
                setup_item.setForeground(QColor(255, 0, 0))
            self.squeezetable.setItem(row, 8, setup_item)
            
        except Exception as e:
            self.log.crash(f"[GUI] Error handling Squeeze update: {e}")

    @pyqtSlot(dict)
    def on_trend_update(self, data):
        """Handle MOMO Trend updates"""
        try:
            symbol = data.get("symbol", "N/A")
            self.sound_alerts.play_sound('morse_code')
            row = self.find_row(self.trend_table, symbol)
            if row == -1:
                row = self.trend_table.rowCount()
                self.trend_table.insertRow(row)
            
            # Column 0: Symbol
            self.trend_table.setItem(row, 0, QTableWidgetItem(symbol))
            
            # Column 1: Price
            price = data.get("price", 0)
            price_item = QTableWidgetItem(f"{price:.2f}")
            
            # Column 2: Change%
            changepct = 0
            if self.tier3 and hasattr(self.tier3, 'livedata'):
                livedata = self.tier3.livedata.get(symbol, {})
                changepct = livedata.get("changepct", 0)
            
            # Apply same color to both price and change
            color = QColor(0, 255, 0) if changepct > 0 else QColor(255, 0, 0)
            price_item.setForeground(color)
            self.trend_table.setItem(row, 1, price_item)
            
            change_item = QTableWidgetItem(f"{changepct:.2f}%")
            change_item.setForeground(color)
            self.trend_table.setItem(row, 2, change_item)
            
            # Column 3: Time
            timestamp = data.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                est = pytz.timezone("US/Eastern")
                dt_est = dt.astimezone(est)
                time_display = dt_est.strftime("%I:%M%p").lower()
                self.trend_table.setItem(row, 3, QTableWidgetItem(time_display))
            except:
                self.trend_table.setItem(row, 3, QTableWidgetItem("--"))
            
            # Column 4: Trend STR (Strength)
            trend_str = data.get("trend_strength", 0)
            self.trend_table.setItem(row, 4, QTableWidgetItem(f"{trend_str:.2f}"))
            
            # Column 5: Model
            model = data.get("model", "")
            self.trend_table.setItem(row, 5, QTableWidgetItem(model))
            
            # Column 6: Confidence
            confidence = data.get("confidence", 0)
            self.trend_table.setItem(row, 6, QTableWidgetItem(f"{confidence:.1f}%"))
            
            # Column 7: Direction
            direction = data.get("direction", "NEUTRAL")
            direction_item = QTableWidgetItem(direction)
            if direction == "UP":
                direction_item.setForeground(QColor(0, 255, 0))
            elif direction == "DOWN":
                direction_item.setForeground(QColor(255, 0, 0))
            self.trend_table.setItem(row, 7, direction_item)
            
            # Column 8: Signal
            signal = data.get("signal", "WATCH")
            signal_item = QTableWidgetItem(signal)
            signal_item.setFont(QFont("Arial", 10, QFont.Bold))
            if "BUY" in signal:
                signal_item.setForeground(QColor(0, 255, 0))
            elif "SELL" in signal:
                signal_item.setForeground(QColor(255, 0, 0))
            self.trend_table.setItem(row, 8, signal_item)
            
        except Exception as e:
            self.log.crash(f"[GUI] Error handling Trend update: {e}")

    @pyqtSlot(dict)
    def on_news_update(self, news_data):
        """Receive News update (VAULT + LIVE)"""
        symbol = news_data.get('symbol', 'N/A')
        #self.sound_alerts.play_sound('news_flash')
        headline = news_data.get('headline', 'No headline')
        
        # Check if this exact headline already exists to avoid duplicates
        for i in range(self.news_table.rowCount()):
            if (self.news_table.item(i, 0) and 
                self.news_table.item(i, 5) and  # Changed from 3 to 5 (Headline column)
                self.news_table.item(i, 0).text() == symbol and
                self.news_table.item(i, 5).text() == headline):
                return  # Already exists, skip
        
        # Add new row at the top
        row = 0
        self.news_table.insertRow(row)
        
        # Column 0: Symbol
        symbol_item = QTableWidgetItem(symbol)
        self.news_table.setItem(row, 0, symbol_item)
        
        # Column 1: Price
        price = news_data.get('price', 0.0)
        price_item = QTableWidgetItem(f"${price:.2f}" if isinstance(price, (int, float)) and price > 0 else "--")

        # Column 2: Change%
        change = news_data.get('change_pct', 0.0)
        change_item = QTableWidgetItem(f"{change:+.2f}%" if isinstance(change, (int, float)) and change != 0 else "--")

        # Apply same color to both price and change
        if isinstance(change, (int, float)):
            color = QColor(0, 255, 0) if change > 0 else QColor(255, 0, 0)
            price_item.setForeground(color)
            change_item.setForeground(color)

        self.news_table.setItem(row, 1, price_item)
        self.news_table.setItem(row, 2, change_item)
        
        # Column 3: Time (Timestamp)
        timestamp = news_data.get('timestamp', 'N/A')
        # Format timestamp if it's a datetime string
        if isinstance(timestamp, str) and timestamp != 'N/A':
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%H:%M:%S')
            except:
                pass
        self.news_table.setItem(row, 3, QTableWidgetItem(str(timestamp)))
        
        # Column 4: Age
        age = news_data.get('age', 'N/A')
        self.news_table.setItem(row, 4, QTableWidgetItem(str(age)))
        
        # Column 5: Headline
        self.news_table.setItem(row, 5, QTableWidgetItem(headline))


    @pyqtSlot(dict)
    def on_halt_update(self, halt_data):
        """Receive Halt update (VAULT + LIVE)"""
        symbol = halt_data.get('symbol', 'N/A')
        
        # Find if symbol already exists
        row = -1
        for i in range(self.halt_table.rowCount()):
            if self.halt_table.item(i, 0) and self.halt_table.item(i, 0).text() == symbol:
                row = i
                break
        
        # Add new row if not found
        if row == -1:
            row = self.halt_table.rowCount()
            self.halt_table.insertRow(row)
        
        # Column 0: Symbol
        symbol_item = QTableWidgetItem(symbol)
        self.halt_table.setItem(row, 0, symbol_item)
        
        # Column 1: Status
        status = halt_data.get('status', 'Unknown')
        status_item = QTableWidgetItem(status)
        if status == "Halted":
            status_item.setForeground(QColor(255, 0, 0))
        elif status == "Resumed":
            status_item.setForeground(QColor(0, 255, 0))
            self.sound_alerts.play_sound('halt_resume')
        self.halt_table.setItem(row, 1, status_item)
        
        # Column 2: Price
        price = halt_data.get('price', 'N/A')
        self.halt_table.setItem(row, 2, QTableWidgetItem(f"${price:.2f}" if isinstance(price, (int, float)) else str(price)))
        
        # Column 3: Reason
        self.halt_table.setItem(row, 3, QTableWidgetItem(str(halt_data.get('reason', 'N/A'))))
        
        # Column 4: Halt Time
        halt_time = halt_data.get('halt_time', 'N/A')
        if isinstance(halt_time, str) and halt_time != 'N/A':
            try:
                from dateutil import parser
                import pytz
                dt = parser.parse(halt_time)  # Parse any format
                # Convert to EST
                est = pytz.timezone('US/Eastern')
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)  # Assume UTC if no timezone
                dt_est = dt.astimezone(est)
                halt_time_display = dt_est.strftime('%I:%M%p - %a, %d %b').lower()  # 3:57pm - Tue, 11 Nov
            except Exception as e:
                halt_time_display = halt_time  # Fallback to raw string
        else:
            halt_time_display = 'N/A'
        self.halt_table.setItem(row, 4, QTableWidgetItem(halt_time_display))
        
        # Column 5: Resume Time
        resume_time = halt_data.get('resume_time', 'N/A')
        if isinstance(resume_time, str) and resume_time != 'N/A' and resume_time:
            try:
                from dateutil import parser
                dt = parser.parse(resume_time)  # Handles both ISO and RSS pubDate formats
                resume_time_display = dt.strftime('%m/%d %H:%M')  # Shows: 11/11 11:45
            except:
                resume_time_display = resume_time
        else:
            resume_time_display = '-'  # Not resumed yet
        self.halt_table.setItem(row, 5, QTableWidgetItem(resume_time_display))

    def _add_or_update_stock(self, table, stock_data, columns):
        """Add or update a stock in a table (for live trading channels)"""
        symbol = stock_data.get('symbol', 'N/A')
        
        # Find if symbol already exists
        row = -1
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).text() == symbol:
                row = i
                break
        
        # Add new row if not found
        if row == -1:
            row = table.rowCount()
            table.insertRow(row)
        
        # Update each column
        for col_idx, col_name in enumerate(columns):
            value = stock_data.get(col_name, 'N/A')
            
            # Format the value
            if col_name == 'symbol':
                item = QTableWidgetItem(str(value))
                item.setFont(QFont("Arial", 10, QFont.Bold))
            elif col_name == 'price' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"${value:.2f}")
                # Apply color based on change_pct
                change_pct = stock_data.get('change_pct', 0)
                if isinstance(change_pct, (int, float)):
                    if change_pct > 0:
                        item.setForeground(QColor(0, 255, 0))
                    elif change_pct < 0:
                        item.setForeground(QColor(255, 0, 0))

            elif 'pct' in col_name or 'change' in col_name:
                if isinstance(value, (int, float)):
                    item = QTableWidgetItem(f"{value:+.2f}%")
                    if value > 0:
                        item.setForeground(QColor(0, 255, 0))
                    elif value < 0:
                        item.setForeground(QColor(255, 0, 0))
                else:
                    item = QTableWidgetItem(str(value))
            elif col_name == 'volume' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"{int(value):,}")
            elif col_name == 'float' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"{value/1e6:.1f}M")
            elif isinstance(value, float):
                item = QTableWidgetItem(f"{value:.2f}")
            else:
                item = QTableWidgetItem(str(value))
            
            table.setItem(row, col_idx, item)
    
    def _find_row(self, table, symbol):
        """Find row index for symbol in table"""
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).text() == symbol:
                return i
        return -1
    
    # =========================================================================
    # VAULT SYSTEM - News & Halts persistent storage
    # =========================================================================
    
    def connect_scanner_signals(self, tier3, news, halts):
        """Connect scanner signals to GUI slots for live updates"""
        self.log.scanner("[GUI-DEBUG] Entering connect_scanner_signals function")
        self.log.scanner(f"[GUI-DEBUG] tier3={tier3}, news={news}, halts={halts}")
        self.log.scanner("[GUI] Connecting live data feeds...")

        # Store tier3 reference for price lookups
        self.tier3 = tier3

        # Connect Tier3 channel signals (LIVE ONLY)
        if tier3 and hasattr(tier3, 'pregap_signal'):
            tier3.pregap_signal.connect(self.on_pregap_update)
            self.log.scanner("[GUI] OK PreGap feed connected (LIVE)")
        
        if tier3 and hasattr(tier3, 'hod_signal'):
            tier3.hod_signal.connect(self.on_hod_update)
            self.log.scanner("[GUI] OK HOD feed connected (LIVE)")
            self.log.scanner(f"[GUI-DEBUG] Signal check - HOD signal exists: {hasattr(tier3, 'hod_signal')}, Slot exists: {hasattr(self, 'on_hod_update')}")

        if tier3 and hasattr(tier3, 'runup_signal'):
            tier3.runup_signal.connect(self.on_runup_update)
            self.log.scanner("[GUI] OK RunUP feed connected (LIVE)")
        
        if tier3 and hasattr(tier3, 'reversal_signal'):
            tier3.reversal_signal.connect(self.on_reversal_update)
            self.log.scanner("[GUI] OK Reversal feed connected (LIVE)")
        
        # Connect MOMO signals
        if self.momo_vector:
            self.momo_vector.vectorsignal.connect(self.on_vector_update)
            self.log.scanner("[GUI] MOMO Vector signal connected")

        if self.momo_squeeze:
            self.momo_squeeze.squeezesignal.connect(self.on_squeeze_update)
            self.log.scanner("[GUI] MOMO Squeeze signal connected")

        if self.momo_trend:
            self.momo_trend.trendsignal.connect(self.on_trend_update)
            self.log.scanner("[GUI] MOMO Trend signal connected")
        
        # Connect News signal (VAULT + LIVE)
        if news and hasattr(news, 'news_signal'):
            news.news_signal.connect(self.on_news_update)
            self.log.scanner("[GUI] OK News feed connected (VAULT + LIVE)")
        
        # Connect Halt signal (VAULT + LIVE)
        if halts and hasattr(halts, 'halt_signal'):
            halts.halt_signal.connect(self.on_halt_update)
            self.log.scanner("[GUI] OK Halt feed connected (VAULT + LIVE)")
        
        # Load existing news and halts from vault on startup
        self._load_existing_news()
        self._load_existing_halts()
    
    def _load_existing_news(self):
        """Load news vault on startup"""
        try:
            self.log.scanner("[GUI] Loading news vault...")
            self._refresh_news_vault()
        except Exception as e:
            self.log.crash(f"[GUI] Error loading news vault: {e}")
    
    def _load_existing_halts(self):
        """Load halt vault on startup"""
        try:
            self.log.scanner("[GUI] Loading halt vault...")
            self._refresh_halt_vault()
        except Exception as e:
            self.log.crash(f"[GUI] Error loading halt vault: {e}")
    
    def _refresh_vaults(self):
        """Auto-refresh vaults every 5 seconds"""
        self._refresh_news_vault()
        self._refresh_halt_vault()
    
    def _refresh_news_vault(self):
        """Refresh news table from vault files (bkgnews.json + news.json), with breaking news age filter."""
        try:
            self.log.scanner("=" * 80)
            self.log.scanner("[GUI-DEBUG] _refresh_news_vault() CALLED")
            self.log.scanner("=" * 80)
            
            self.news_table.setRowCount(0)

            # Load breaking news (bkgnews.json)
            bkgnews = self.fm.load_bkgnews()
            self.log.scanner(f"[GUI-DEBUG] Loaded bkgnews: {len(bkgnews)} items")
            
            # Load general news (news.json)
            news = self.fm.load_news()
            self.log.scanner(f"[GUI-DEBUG] Loaded news: {len(news)} items")

            # Combine all news
            all_news = {}
            all_news.update(bkgnews)
            #all_news.update(news)
            self.log.scanner(f"[GUI-DEBUG] Combined news: {len(all_news)} items")
            
            if self.tier3 and hasattr(self.tier3, 'live_data'):
                news_symbols = [item.get('symbol') for item in all_news.values()]
                missing = [s for s in news_symbols if s not in self.tier3.live_data]
                self.log.scanner(f"[GUI-DEBUG] News symbols MISSING from Tier3: {missing[:10]}")

            if self.tier3 and hasattr(self.tier3, 'live_data'):
                self.log.scanner(f"[GUI-DEBUG] Tier3 has live_data for {len(self.tier3.live_data)} symbols")
                self.log.scanner(f"[GUI-DEBUG] Tier3 live_data keys: {list(self.tier3.live_data.keys())[:20]}")  # Show first 20
                # Check if news symbols are in there
                news_symbols = [item.get('symbol') for item in all_news.values()]
                subscribed_news = [s for s in news_symbols if s in self.tier3.live_data]
                self.log.scanner(f"[GUI-DEBUG] News symbols subscribed to Tier3: {subscribed_news}")
            else:
                self.log.scanner(f"[GUI-DEBUG] Tier3 live_data NOT AVAILABLE")

            # Sort by timestamp - newest first (only showing breaking news)
            sorted_news = sorted(
                all_news.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=False  # Newest first
            )

            from datetime import timezone
            now = datetime.now(timezone.utc)
            self.log.scanner(f"[GUI-DEBUG] Current time (UTC): {now}")
            
            shown = 0
            filtered_breaking = 0
            filtered_general = 0
            
            for news_id, news_item in sorted_news:
                # Calculate age
                try:
                    timestamp = datetime.fromisoformat(news_item['timestamp'].replace('Z', '+00:00'))
                    age_hours = (now - timestamp).total_seconds() / 3600
                    # Format age: minutes if < 1 hour, hours if < 24 hours, days otherwise
                    if age_hours < 1:
                        age_str = f"{int(age_hours * 60)}m"
                    elif age_hours < 24:
                        age_str = f"{int(age_hours)}h"
                    else:
                        age_str = f"{int(age_hours/24)}d"
                    self.log.scanner(f"[GUI-DEBUG] {news_item.get('symbol')}: age={age_hours:.2f}h, category={news_item.get('category')}")
                except Exception as e:
                    self.log.scanner(f"[GUI-DEBUG] ERROR calculating age for {news_id}: {e}")
                    age_hours = 999
                    age_str = "N/A"

                # Only show breaking news ≤2hr, general news ≤72hr
                category = news_item.get('category', '')
                if category == 'breaking' and age_hours > 2:
                    filtered_breaking += 1
                    self.log.scanner(f"[GUI-DEBUG] FILTERED OUT (breaking too old): {news_item.get('symbol')} - {age_hours:.2f}h")
                    continue
                if category == 'general' and age_hours > 72:
                    filtered_general += 1
                    self.log.scanner(f"[GUI-DEBUG] FILTERED OUT (general too old): {news_item.get('symbol')} - {age_hours:.2f}h")
                    continue

                self.log.scanner(f"[GUI-DEBUG] SHOWING: {news_item.get('symbol')} - {news_item.get('headline')[:50]}")

                # Look up live price from tier3
                price = 0.0
                change_pct = 0.0
                if self.tier3 and hasattr(self.tier3, 'live_data'):
                    live = self.tier3.live_data.get(news_item.get('symbol'), {})
                    price = live.get('price', 0.0)
                    # Calculate %change if we have price
                    if price > 0:
                        # Try to get prev_close from tier3's tracking
                        prev_close = self.tier3.prev_closes.get(news_item.get('symbol'), 0)
                        if prev_close > 0:
                            change_pct = ((price - prev_close) / prev_close) * 100

                gui_data = {
                    'symbol': news_item.get('symbol', 'N/A'),
                    'price': price,
                    'change_pct': change_pct,
                    'headline': news_item.get('headline', 'No headline'),
                    'age': age_str,
                    'timestamp': news_item.get('timestamp', 'N/A')
                }
                self.on_news_update(gui_data)
                shown += 1

            self.log.scanner(f"[GUI-DEBUG] SUMMARY: shown={shown}, filtered_breaking={filtered_breaking}, filtered_general={filtered_general}")
            self.log.scanner(f"[GUI] OK News vault loaded: {shown} fresh items")

        except Exception as e:
            self.log.scanner(f"[GUI-DEBUG] EXCEPTION in _refresh_news_vault: {e}")
            import traceback
            self.log.scanner(traceback.format_exc())
            self.log.crash(f"[GUI] Error refreshing news vault: {e}")
    
    def _refresh_halt_vault(self):
        """Refresh halt table from vault files (active_halts.json + halts.json)"""
        try:
            self.log.scanner("=" * 80)
            self.log.scanner("[GUI-DEBUG] _refresh_halt_vault() CALLED")
            self.log.scanner("=" * 80)
        
            # Clear existing table
            self.halt_table.setRowCount(0)
        
            # Load active halts (HALTED status)
            active_halts = self.fm.load_active_halts()
            self.log.scanner(f"[GUI-DEBUG] Loaded active_halts: {len(active_halts)} items")
        
            # Load historical halts (RESUMED status)
            historical_halts = self.fm.load_halts()
            self.log.scanner(f"[GUI-DEBUG] Loaded historical_halts: {len(historical_halts)} items")
        
            # Filter to last 72 hours only
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=72)
        
            filtered_halts = {}
            for halt_id, halt_data in historical_halts.items():
                halt_time_str = halt_data.get('halt_time', halt_data.get('timestamp', ''))
                try:
                    from dateutil import parser
                    halt_time = parser.parse(halt_time_str)
                    if halt_time.replace(tzinfo=None) >= cutoff_time:
                        filtered_halts[halt_id] = halt_data
                except:
                    # If can't parse time, keep it (fail-open)
                    filtered_halts[halt_id] = halt_data
        
            historical_halts = filtered_halts
            self.log.scanner(f"[GUI-DEBUG] Filtered to last 72hrs: {len(historical_halts)} items")
        
            # Debug tier3 connection
            if self.tier3 and hasattr(self.tier3, 'live_data'):
                self.log.scanner(f"[GUI-DEBUG] Tier3 has {len(self.tier3.live_data)} symbols with live data")
            else:
                self.log.scanner(f"[GUI-DEBUG] Tier3 live_data NOT AVAILABLE")
        
            # Helper function to convert time strings to sortable timestamps
            def parse_time(time_str):
                """Convert RSS pubDate or ISO timestamp to Unix timestamp for sorting"""
                try:
                    from dateutil import parser
                    dt = parser.parse(time_str)
                    return dt.timestamp()
                except:
                    return 0  # If parse fails, put at end
            
            # Sort active halts by halt_time (newest first)
            sorted_active = sorted(
                active_halts.items(),
                key=lambda x: parse_time(x[1].get('halt_time', x[1].get('timestamp', ''))),
                reverse=True  # Newest halt first
            )
            
            # Sort historical halts by halt_time (newest HALT first, not resume time)
            sorted_historical = sorted(
                historical_halts.items(),
                key=lambda x: parse_time(x[1].get('halt_time', x[1].get('timestamp', ''))),
                reverse=True  # Newest halt first
            )
            
            # Combine: active halts first (newest to oldest), then historical halts (newest to oldest)
            combined_halts = sorted_active + sorted_historical
            
            self.log.scanner(f"[GUI-DEBUG] Combined halt list: {len(sorted_active)} active + {len(sorted_historical)} historical (sorted by halt_time)")
        
            # Populate table with live price lookup
            for halt_id, halt_data in combined_halts:
                symbol = halt_data.get('symbol')
                
                # Look up live price from tier3
                price = halt_data.get('price', 0.0)  # Use stored price as fallback
            
                if self.tier3 and hasattr(self.tier3, 'live_data'):
                    live = self.tier3.live_data.get(symbol, {})
                    prev_close = self.tier3.prev_closes.get(symbol, 0.0)
                    
                    # Get price data - Tier3 may return strings
                    live_price = live.get('price', 0.0)
                    bid = live.get('bid', 0.0)
                    ask = live.get('ask', 0.0)
                    
                    # Convert all to float
                    try:
                        live_price = float(live_price) if live_price else 0.0
                        bid = float(bid) if bid else 0.0
                        ask = float(ask) if ask else 0.0

                    except (ValueError, TypeError):
                        bid = 0.0
                        ask = 0.0
                        live_price = (bid + ask) / 2 if bid and ask else 0.0
                    
                    if live_price > 0:

                        price = live_price
                        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        halt_data['price'] = price
                        halt_data['prev_close'] = prev_close
                        halt_data['change_pct'] = change_pct
                        self.log.scanner(f"[GUI-DEBUG] Updated {symbol} halt price from Tier3: ${price:.2f} ({change_pct:+.2f}%)")
                    else:
                        self.log.scanner(f"[GUI-DEBUG] No Tier3 price data for {symbol}")
            
                # Send to table display
                self.on_halt_update(halt_data)
        
            if len(combined_halts) > 0:
                self.log.scanner(f"[GUI] OK Halt vault refreshed: {len(combined_halts)} items ({len(sorted_active)} active, {len(sorted_historical)} historical)")
        
        except Exception as e:
            self.log.scanner(f"[GUI-DEBUG] EXCEPTION in _refresh_halt_vault: {e}")
            import traceback
            self.log.scanner(traceback.format_exc())
            self.log.crash(f"[GUI] Error refreshing halt vault: {e}")

    # =========================================================================
    # Button Handlers
    # =========================================================================
    
    def on_news_clicked(self):
        """Handle NEWS button click - Force refresh from multiple providers"""
        self.log.scanner("[GUI] NEWS button clicked - fetching from GDELT + Alpaca + yFinance...")
        
        # Gather symbols from all active channels
        active_symbols = set()
        for table in [self.pregap_table, self.hod_table, self.runup_table, self.rvsl_table]:
            for row in range(table.rowCount()):
                symbol_item = table.item(row, 0)
                if symbol_item:
                    active_symbols.add(symbol_item.text())
        
        if not active_symbols:
            self.log.scanner("[GUI] No active symbols in channels, using default list")
            active_symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']  # Default symbols
        
        # Fetch from multi-provider aggregator
        from scanners.multi_news_aggregator import MultiNewsAggregator
        aggregator = MultiNewsAggregator(self.fm, self.log)
        multi_news = aggregator.fetch_news_for_symbols(list(active_symbols))
        
        # Load existing vault news and merge
        vault_news = self.fm.load_news()
        vault_news.update(multi_news)
        
        # Save merged news back to vault
        self.fm.save_news(vault_news)
        
        # Refresh the news table display
        self._refresh_news_vault()
        
        # Switch to News tab
        self.tabs.setCurrentIndex(4)
        self.log.scanner(f"[GUI] NEWS refresh complete: {len(multi_news)} new articles from 3 providers")
    
    def on_update_clicked(self):
        """Handle UPDATE button - Background nuclear refresh with live overwrite"""
        self.log.scanner("[GUI] UPDATE button clicked - Background refresh initiated...")
        
        # Run refresh in background thread to keep UI responsive
        from threading import Thread
        refresh_thread = Thread(target=self._background_nuclear_refresh, daemon=True)
        refresh_thread.start()
        
        self.log.scanner("[GUI] OK Background refresh thread started")
    
    def _background_nuclear_refresh(self):
        """Background thread: Force all scanners to refresh and overwrite existing data"""
        try:
            self.log.scanner("[BACKGROUND-REFRESH] Starting nuclear refresh...")
            
            # 1. Force Tier1 prefilter scan
            if self.tier1:
                self.log.scanner("[BACKGROUND-REFRESH] Triggering Tier1 prefilter scan...")
                self.tier1.force_scan()
            
            # 2. Force News aggregator refresh
            if hasattr(self, 'news') and self.news:
                self.log.scanner("[BACKGROUND-REFRESH] Forcing news aggregator refresh...")
                self.news.force_scan()
            
            # 3. Force Halt monitor refresh
            if hasattr(self, 'halts') and self.halts:
                self.log.scanner("[BACKGROUND-REFRESH] Forcing halt monitor refresh...")
                # HaltMonitor runs on timer, trigger immediate fetch
                # If no force method exists, this will just log
            
            # 4. Trigger Tier3 to re-subscribe to updated symbol list
            if self.tier3:
                self.log.scanner("[BACKGROUND-REFRESH] Triggering Tier3 re-subscription...")
                # Tier3 automatically picks up changes from validated.json
            
            # 5. Update market indices
            self.log.scanner("[BACKGROUND-REFRESH] Updating market indices...")
            self.update_indices()
            
            self.log.scanner("[BACKGROUND-REFRESH] OK Nuclear refresh complete - data will overwrite as it streams in")
            
        except Exception as e:
            self.log.scanner(f"[BACKGROUND-REFRESH] ERROR: {e}")
            import traceback
            self.log.scanner(traceback.format_exc())

    def _on_kiosk_clicked(self):
        """Handle KIOSK button click"""
        self.log.scanner("[GUI] KIOSK mode activated")
        # Toggle fullscreen mode
        if self.isFullScreen():
            self.showNormal()
            self.status_bar.showMessage("Exited Kiosk mode")
        else:
            self.showFullScreen()
            self.status_bar.showMessage("Entered Kiosk mode (press ESC to exit)")
        
    def _create_channel_tab(self, channel_name, columns):
        """Create a table widget for a channel"""
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # Table styling
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        
        # Set specific column widths
        header = table.horizontalHeader()

        if channel_name == "Breaking News":
            # Symbol, Price, Change%, Time, Age, Headline
            widths = [150, 150, 150, 150, 100, 1450]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)
                
        elif channel_name == "Halts":
            # Symbol, Status, Halt Time, Resume Time, Reason, Price
            widths = [150, 300, 150, 200, 550, 550]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)
                
        elif channel_name == "PreGap":
            # Symbol, Price, Change%, Time, Gap%, Volume, RVOL, Float, News
            widths = [150, 150, 150, 150, 150, 250, 200, 200, 500]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)
                
        elif channel_name == "HOD":
            # Symbol, Price, Change%, Time, HOD Price, Volume, RVOL, Float, News
            widths = [150, 150, 150, 150, 150, 250, 200, 200, 500]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)
                
        elif channel_name == "RunUP":
            # Symbol, Price, Change%, Time, 5min%, Volume, RVOL, Float, News
            widths = [150, 150, 150, 150, 150, 250, 200, 200, 500]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)
                
        elif channel_name == "Reversal":
            # Symbol, Price, Change%, time, Gap%, Volume, RVOL, News
            widths = [150, 150, 150, 150, 150, 250, 250, 650]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)

        elif channel_name == "Vector":
        # Symbol, Price, Change%, Time, V-Score, MTF, Vol Quality, VWAP Dist, Signal
            widths = [150, 150, 150, 150, 250, 250, 250, 250, 300]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)

        elif channel_name == "Squeeze":
            # Symbol, Price, Change%, Time, Status, Intensity, Histogram, TF Align, Setup
            widths = [150, 150, 150, 150, 250, 250, 250, 250, 300]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)

        elif channel_name == "Trend":
        # Symbol, Price, Change%, Time, Trend STR, Model, Confidence, Direction, Signal
            widths = [150, 150, 150, 150, 250, 250, 250, 250, 300]
            for i, width in enumerate(widths):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                table.setColumnWidth(i, width)

        return table
        
    def _update_time(self):
        """Update the time display (12-hour format, no date)"""
        # Local time
        local_time = datetime.now()
        self.local_time_label.setText(f"Local: {local_time.strftime('%I:%M %p')}")
        
        # NYC time (ET)
        nyc_tz = pytz.timezone('America/New_York')
        nyc_time = datetime.now(nyc_tz)
        self.nyc_time_label.setText(f"NYC: {nyc_time.strftime('%I:%M %p')}")
        
        # Update market session based on NYC time
        hour = nyc_time.hour
        minute = nyc_time.minute
        
        if 4 <= hour < 9 or (hour == 9 and minute < 30):
            self.market_session.setText("Market: PREMARKET")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ffaa00; font-size: 36px;")
        elif (hour == 9 and minute >= 30) or (9 < hour < 16):
            self.market_session.setText("Market: OPEN")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #00ff00; font-size: 36px;")
        elif 16 <= hour < 20:
            self.market_session.setText("Market: AFTERHOURS")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ffaa00; font-size: 36px;")
        else:
            self.market_session.setText("Market: CLOSED")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ff0000; font-size: 36px;")
    
    def _update_indices(self):
        """Update market indices (S&P 500, NASDAQ, DOW)"""
        try:
            import yfinance as yf
            
            # S&P 500 (SPY ETF as proxy)
            spy = yf.Ticker("SPY")
            spy_price = spy.info.get('regularMarketPrice', spy.info.get('currentPrice', 0))
            spy_change = spy.info.get('regularMarketChangePercent', 0)
            
            # NASDAQ (QQQ ETF as proxy)
            qqq = yf.Ticker("QQQ")
            qqq_price = qqq.info.get('regularMarketPrice', qqq.info.get('currentPrice', 0))
            qqq_change = qqq.info.get('regularMarketChangePercent', 0)
            
            # DOW (DIA ETF as proxy)
            dia = yf.Ticker("DIA")
            dia_price = dia.info.get('regularMarketPrice', dia.info.get('currentPrice', 0))
            dia_change = dia.info.get('regularMarketChangePercent', 0)
            
            # Update S&P 500
            sp500_color = "#00ff00" if spy_change >= 0 else "#ff0000"
            self.sp500_label.setText(f"S&P 500: ${spy_price:.2f} ({spy_change:+.2f}%)")
            self.sp500_label.setStyleSheet(f"font-size: 20px; font-weight: bold; padding: 5px; color: {sp500_color};")
            
            # Update NASDAQ
            nasdaq_color = "#00ff00" if qqq_change >= 0 else "#ff0000"
            self.nasdaq_label.setText(f"NASDAQ: ${qqq_price:.2f} ({qqq_change:+.2f}%)")
            self.nasdaq_label.setStyleSheet(f"font-size: 20px; font-weight: bold; padding: 5px; color: {nasdaq_color};")
            
            # Update DOW
            dow_color = "#00ff00" if dia_change >= 0 else "#ff0000"
            self.dow_label.setText(f"DOW: ${dia_price:.2f} ({dia_change:+.2f}%)")
            self.dow_label.setStyleSheet(f"font-size: 20px; font-weight: bold; padding: 5px; color: {dow_color};")
            
        except Exception as e:
            self.log.crash(f"[GUI] Error updating indices: {e}")

    def _get_news_for_symbol(self, symbol):
        """Look up most recent news for symbol from bkgnews.json"""
        try:
            all_news = self.fm.load_breaking_news()
            
            # Find news matching this symbol (most recent first)
            symbol_news = []
            for news_id, news_data in all_news.items():
                if news_data.get('symbol') == symbol:
                    symbol_news.append(news_data)
            
            if symbol_news:
                return symbol_news[0]
        except Exception as e:
            self.log.scanner(f"[GUI] Error loading news for {symbol}: {e}")
        
        return None

    def _on_cell_clicked(self, row, col):
        """Handle cell clicks - open news popup if News column clicked"""
        sender = self.sender()
        
        # Determine which table and news column index
        news_col = None
        if sender == self.pregap_table:
            news_col = 8
        elif sender == self.hod_table:
            news_col = 8
        elif sender == self.runup_table:
            news_col = 8
        elif sender == self.rvsl_table:
            news_col = 7
        
        # Check if News column was clicked
        if col == news_col:
            item = sender.item(row, col)
            if item:
                news_data = item.data(Qt.UserRole)
                if news_data:
                    from gui.news_popup import NewsPopup
                    popup = NewsPopup(news_data, self)
                    popup.exec_()

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self.status_bar.showMessage("Exited Kiosk mode")
            
    def _apply_stylesheet(self):
        """Apply dark theme stylesheet to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
            }
            QWidget {
                background-color: #000000;
                color: #c9d1d9;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 24px;
            }
            QTabWidget::pane {
                border: 1px solid #58a6ff;
                background-color: #000000;
            }
            QTabBar {
                qproperty-expanding: true;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background-color: #000000;
                color: #967bb6;
                padding: 10px 25px;
                margin-right: 2px;
                border: 1px solid #58a6ff;
                border-bottom: none;
                font-size: 28px;
                min-width: 150px;
                min-height: 24px;
            }
            QTabBar::tab:selected {
                background-color: #967bb6;
                color: #000000;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #000000;
                alternate-background-color: #0d1117;
                gridline-color: #58a6ff;
                border: 1px solid #967bb6;
            }
            QTableWidget::item {
                padding: 16px;
                font-size: 24px;
            }
            QHeaderView::section {
                background-color: #000000;
                color: #58a6ff;
                padding: 6px;
                border: 1px solid #58a6ff;
                font-weight: bold;
                font-size: 24px;
            }
            QStatusBar {
                background-color: #000000;
                color: #967bb6;
                border-top: 1px solid #58a6ff;
            }
        """)
    
    def _format_time_est(self, timestamp_str):
        """Format timestamp to 12h EST time (HH:MM AM/PM)"""
        try:
            # Parse timestamp (assuming ISO format)
            if isinstance(timestamp_str, str):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return "--"
            
            # Convert to EST
            est_tz = pytz.timezone('America/New_York')
            dt_est = dt.astimezone(est_tz)
            
            # Format as 12h time (HH:MM AM/PM)
            return dt_est.strftime('%I:%M %p')
        except Exception as e:
            return "--"

