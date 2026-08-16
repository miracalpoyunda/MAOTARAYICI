import sys

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QKeySequence, QShortcut


class BrowserTab(QWidget):
    def __init__(self, url="https://www.google.com"):
        super().__init__()

        layout = QVBoxLayout(self)

        # Araç çubuğu
        toolbar = QHBoxLayout()

        self.back_button = QPushButton("←")
        self.forward_button = QPushButton("→")
        self.refresh_button = QPushButton("⟳")

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Adres yazın...")

        self.go_button = QPushButton("Git")

        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.forward_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.url_bar)
        toolbar.addWidget(self.go_button)

        layout.addLayout(toolbar)

        # Web sayfası
        self.browser = QWebEngineView()

        # Çerezleri engelle
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )

        layout.addWidget(self.browser)

        # Bağlantılar
        self.back_button.clicked.connect(self.browser.back)
        self.forward_button.clicked.connect(self.browser.forward)
        self.refresh_button.clicked.connect(self.browser.reload)
        self.go_button.clicked.connect(self.go_to_url)
        self.url_bar.returnPressed.connect(self.go_to_url)

        self.browser.urlChanged.connect(self.update_url)
        self.browser.titleChanged.connect(self.update_title)

        self.browser.setUrl(QUrl(url))

    def go_to_url(self):
        url = self.url_bar.text().strip()

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.browser.setUrl(QUrl(url))

    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def update_title(self, title):
        if title:
            self.window().set_tab_title(self, title)


class KlydoBrowser(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MAOTARAYICI")
        self.setGeometry(100, 100, 1200, 800)

        self.tabs = QTabWidget()

        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.tabs.setMovable(True)

        self.setCentralWidget(self.tabs)

        # Yeni sekme butonu
        self.new_tab_button = QPushButton("+")
        self.new_tab_button.clicked.connect(self.new_tab)

        self.tabs.setCornerWidget(
            self.new_tab_button,
            Qt.Corner.TopRightCorner
        )

        # İlk sekme
        self.new_tab()

        # Ctrl+T = Yeni sekme
        self.shortcut_new = QShortcut(
            QKeySequence("Ctrl+T"),
            self
        )
        self.shortcut_new.activated.connect(self.new_tab)

        # Ctrl+W = Sekmeyi kapat
        self.shortcut_close = QShortcut(
            QKeySequence("Ctrl+W"),
            self
        )
        self.shortcut_close.activated.connect(self.close_current_tab)

    def new_tab(self):
        tab = BrowserTab()

        index = self.tabs.addTab(tab, "Yeni Sekme")
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            widget.deleteLater()

    def close_current_tab(self):
        index = self.tabs.currentIndex()

        if index >= 0:
            self.close_tab(index)

    def set_tab_title(self, widget, title):
        index = self.tabs.indexOf(widget)

        if index >= 0:
            # Çok uzun başlıkları kısalt
            if len(title) > 20:
                title = title[:20] + "..."

            self.tabs.setTabText(index, title)


app = QApplication(sys.argv)

window = KlydoBrowser()
window.show()

sys.exit(app.exec())