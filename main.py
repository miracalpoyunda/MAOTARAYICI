import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction, QKeySequence  # QKeySequence kısayollar için eklendi
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QToolBar, 
                             QLineEdit, QMessageBox, QFileDialog, QVBoxLayout, QWidget)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlRequestInterceptor

# Yeni Uzantı Yöneticisini ve Arayüzünü import ediyoruz
from mao_extensions import MaoExtensionManager, ExtensionsUI

class MaoAdBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocked_hosts = [
            "doubleclick.net",
            "googleadservices.com",
            "ads.youtube.com",
            "adsystem.com",
            "analytics.google.com"
        ]

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        for host in self.blocked_hosts:
            if host in url:
                info.block(True)
                return

class MaoBrowserV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAO TARAYICI v2")
        self.setGeometry(100, 100, 1200, 800)

        # Temel Profil ve Interceptor Ayarları
        self.profile = QWebEngineProfile.defaultProfile()
        self.adblocker = MaoAdBlocker()
        self.profile.setUrlRequestInterceptor(self.adblocker)
        
        # Uzantı Yöneticisini Başlat
        self.extension_manager = MaoExtensionManager(self.profile)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.setup_ui()
        self.add_blank_tab() # Başlangıçta ilk sekmeyi aç

    def setup_ui(self):
        nav_bar = QToolBar("Navigasyon")
        self.addToolBar(nav_bar)

        back_btn = QAction("Geri", self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(back_btn)

        forward_btn = QAction("İleri", self)
        forward_btn.triggered.connect(lambda: self.tabs.currentWidget().forward() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(forward_btn)

        refresh_btn = QAction("Yenile", self)
        refresh_btn.triggered.connect(lambda: self.tabs.currentWidget().reload() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(refresh_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        # ➕ YENİ SEKME BUTONU EKLENDİ
        new_tab_btn = QAction("➕ Yeni Sekme", self)
        new_tab_btn.setShortcut(QKeySequence("Ctrl+T")) # Kısayol: Ctrl+T
        new_tab_btn.triggered.connect(self.add_blank_tab)
        nav_bar.addAction(new_tab_btn)

        # YAPBOZ (UZANTILAR) BUTONU
        extensions_btn = QAction("🧩 Uzantılar", self)
        extensions_btn.triggered.connect(self.open_extensions_tab)
        nav_bar.addAction(extensions_btn)

        self.tabs.currentChanged.connect(self.update_url_bar)

        # SEKME KAPATMA KISAYOLU EKLENDİ (Ctrl+W)
        close_tab_shortcut = QAction("Sekmeyi Kapat", self)
        close_tab_shortcut.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_shortcut.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        self.addAction(close_tab_shortcut)

    def add_blank_tab(self):
        # Yeni sekmeye tıklandığında varsayılan olarak Google açılır
        self.add_new_tab(QUrl("https://www.google.com"), "Yeni Sekme")

    def open_extensions_tab(self):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "🧩 Uzantılar":
                self.tabs.setCurrentIndex(i)
                return
        
        ext_ui = ExtensionsUI(self.extension_manager, self)
        i = self.tabs.addTab(ext_ui, "🧩 Uzantılar")
        self.tabs.setCurrentIndex(i)

    def add_new_tab(self, qurl, title):
        browser = QWebEngineView()
        browser.setPage(browser.page())
        browser.setUrl(qurl)
        
        i = self.tabs.addTab(browser, title)
        self.tabs.setCurrentIndex(i)
        
        browser.urlChanged.connect(lambda qurl, browser=browser: 
                                   self.update_tab_title(browser, qurl))
        browser.loadFinished.connect(lambda _, i=i, browser=browser: 
                                     self.tabs.setTabText(i, browser.page().title()))

    def close_tab(self, i):
        # Son sekmeyse kapatma veya pencereyi kapat (şu an son sekmeyi kapatmayı engelliyoruz)
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    def update_tab_title(self, browser, qurl):
        i = self.tabs.indexOf(browser)
        if i != -1:
            self.tabs.setTabText(i, qurl.host())
        if self.tabs.currentWidget() == browser:
            self.update_url_bar()

    def update_url_bar(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, QWebEngineView):
            qurl = current_widget.url()
            self.url_bar.setText(qurl.toString())
            self.url_bar.setCursorPosition(0)
            self.url_bar.setEnabled(True)
        else:
            self.url_bar.setText("mao://uzantilar")
            self.url_bar.setEnabled(False)

    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith("http") and not url.startswith("mao://"):
            url = "https://" + url
            
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, QWebEngineView):
            current_widget.setUrl(QUrl(url))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MaoBrowserV2()
    window.show()
    sys.exit(app.exec())