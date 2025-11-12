"""
SignalScan PRO - News Article Popup Dialog
Shows article summary with link to full source
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, 
    QTextEdit, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import webbrowser

class NewsPopup(QDialog):
    """Popup dialog to display news article details"""
    
    def __init__(self, news_data, parent=None):
        super().__init__(parent)
        self.news_data = news_data
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the popup UI"""
        self.setWindowTitle("News Article")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Symbol
        symbol_label = QLabel(f"Symbol: {self.news_data.get('symbol', 'N/A')}")
        symbol_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(symbol_label)
        
        # Headline
        headline_label = QLabel(self.news_data.get('headline', 'No headline'))
        headline_label.setFont(QFont("Arial", 11, QFont.Bold))
        headline_label.setWordWrap(True)
        layout.addWidget(headline_label)
        
        # Timestamp
        timestamp = self.news_data.get('timestamp', 'N/A')
        time_label = QLabel(f"Published: {timestamp}")
        time_label.setFont(QFont("Arial", 9))
        layout.addWidget(time_label)
        
        # Summary/Description
        summary_label = QLabel("Summary:")
        summary_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(summary_label)
        
        summary_text = QTextEdit()
        summary_text.setReadOnly(True)
        summary_text.setText(self.news_data.get('summary', 'No summary available'))
        summary_text.setMaximumHeight(200)
        layout.addWidget(summary_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Open Full Article button
        url = self.news_data.get('url', '')
        if url:
            open_btn = QPushButton("Open Full Article")
            open_btn.clicked.connect(lambda: webbrowser.open(url))
            button_layout.addWidget(open_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
