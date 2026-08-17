import sys

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QToolBar,
)

from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineUrlRequestInterceptor,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


# =========================================================
# REKLAM / İZLEYİCİ ENGELLEME
# =========================================================

BLOCKED_HOSTS = {
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "adservice.google.com",
    "adnxs.com",
    "adsrvr.org",
    "scorecardresearch.com",
    "outbrain.com",
    "taboola.com",
    "criteo.com",
    "zedo.com",
}

BLOCKED_URL_WORDS = [
    "/ads/",
    "/ad/",
    "/advert/",
    "/advertising/",
    "/banner/",
    "/tracking/",
    "/tracker/",
    "doubleclick",
    "googlesyndication",
    "googleadservices",
    "adservice",
    "pagead",
]


class AdBlocker(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl().toString().lower()
        host = info.requestUrl().host().lower()

        # Alan adı engelleme
        for blocked_host in BLOCKED_HOSTS:
            if host == blocked_host or host.endswith("." + blocked_host):
                info.block(True)
                return

        # URL anahtar kelimesi engelleme
        for word in BLOCKED_URL_WORDS:
            if word in url:
                info.block(True)
                return


# =========================================================
# TARAYICI SEKME
# =========================================================

class BrowserTab(QWidget):
    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.profile = profile

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ---------------- ARAÇ ÇUBUĞU ----------------

        toolbar = QHBoxLayout()

        self.back_button = QPushButton("←")
        self.forward_button = QPushButton("→")
        self.refresh_button = QPushButton("⟳")

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Adres veya site yazın...")

        self.go_button = QPushButton("Git")

        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.forward_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.url_bar, 1)
        toolbar.addWidget(self.go_button)

        layout.addLayout(toolbar)

        # ---------------- WEB SAYFASI ----------------

        self.browser = QWebEngineView()

        # Ortak profile kullan
        self.browser.page().setUrlRequestInterceptor(None)

        layout.addWidget(self.browser)

        # ---------------- OLAYLAR ----------------

        self.back_button.clicked.connect(self.browser.back)
        self.forward_button.clicked.connect(self.browser.forward)
        self.refresh_button.clicked.connect(self.browser.reload)

        self.go_button.clicked.connect(self.go_to_url)
        self.url_bar.returnPressed.connect(self.go_to_url)

        self.browser.urlChanged.connect(self.update_url)
        self.browser.titleChanged.connect(self.update_title)

        # Ana sayfa
        self.browser.setUrl(QUrl("https://www.google.com"))

    def go_to_url(self):
        text = self.url_bar.text().strip()

        if not text:
            return

        if not text.startswith(("http://", "https://")):
            text = "https://" + text

        self.browser.setUrl(QUrl(text))

    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def update_title(self, title):
        if title:
            main_window = self.window()

            if hasattr(main_window, "set_tab_title"):
                main_window.set_tab_title(self, title)


# =========================================================
# MAOTARAYICI
# =========================================================

class MAOTARAYICI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MAOTARAYICI")
        self.setGeometry(100, 100, 1200, 800)

        # =================================================
        # PROFİL
        # =================================================

        self.profile = QWebEngineProfile("MAOTARAYICI", self)

        # Kalıcı çerezleri kapat
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )

        # Reklam engelleyici
        self.adblocker = AdBlocker(self)
        self.profile.setUrlRequestInterceptor(self.adblocker)

        # =================================================
        # UZANTI YÖNETİCİSİ
        # =================================================

        try:
            self.extension_manager = self.profile.extensionManager()

            # Kurulum tamamlandığında çalışır
            self.extension_manager.installFinished.connect(
                self.extension_install_finished
            )

            # Açılmış uzantı tamamlandığında çalışır
            self.extension_manager.loadFinished.connect(
                self.extension_load_finished
            )

        except AttributeError:
            self.extension_manager = None

        # =================================================
        # ÜST ARAÇ ÇUBUĞU
        # =================================================

        self.top_toolbar = QToolBar("MAOTARAYICI")
        self.top_toolbar.setMovable(False)

        self.addToolBar(
            Qt.ToolBarArea.TopToolBarArea,
            self.top_toolbar
        )

        self.extension_button = QPushButton("Uzantı Yükle")
        self.extension_button.clicked.connect(
            self.install_extension
        )

        self.top_toolbar.addWidget(
            self.extension_button
        )

        # =================================================
        # SEKME SİSTEMİ
        # =================================================

        self.tabs = QTabWidget()

        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)

        self.tabs.tabCloseRequested.connect(
            self.close_tab
        )

        self.setCentralWidget(self.tabs)

        # + butonu
        self.new_tab_button = QPushButton("+")
        self.new_tab_button.setToolTip("Yeni Sekme")

        self.new_tab_button.clicked.connect(
            self.new_tab
        )

        self.tabs.setCornerWidget(
            self.new_tab_button,
            Qt.Corner.TopRightCorner
        )

        # İlk sekme
        self.new_tab()

        # Ctrl + T
        self.shortcut_new = QShortcut(
            QKeySequence("Ctrl+T"),
            self
        )

        self.shortcut_new.activated.connect(
            self.new_tab
        )

        # Ctrl + W
        self.shortcut_close = QShortcut(
            QKeySequence("Ctrl+W"),
            self
        )

        self.shortcut_close.activated.connect(
            self.close_current_tab
        )

    # =====================================================
    # UZANTI YÜKLE
    # =====================================================

    def install_extension(self):
        if self.extension_manager is None:
            QMessageBox.critical(
                self,
                "MAOTARAYICI",
                "Uzantı desteği bulunamadı.\n\n"
                "Qt WebEngine 6.10 veya daha yeni "
                "bir sürüm gerekiyor."
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chrome / Chromium Uzantısı Seç",
            "",
            "Uzantı ZIP (*.zip);;Tüm Dosyalar (*.*)"
        )

        if not path:
            return

        try:
            # ZIP uzantıyı profile kur
            self.extension_manager.installExtension(path)

            QMessageBox.information(
                self,
                "MAOTARAYICI",
                "Uzantı kurulum işlemi başlatıldı.\n\n"
                "Kurulum tamamlandığında sonuç gösterilecek."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Uzantı Hatası",
                f"Uzantı kurulamadı:\n\n{e}"
            )

    # =====================================================
    # UZANTI KURULUM SONUCU
    # =====================================================

    def extension_install_finished(self, extension):
        try:
            if extension.isInstalled():
                # Kurulan uzantılar varsayılan olarak kapalı gelir
                self.extension_manager.setExtensionEnabled(
                    extension,
                    True
                )

                QMessageBox.information(
                    self,
                    "MAOTARAYICI",
                    "Uzantı başarıyla kuruldu ve etkinleştirildi.\n\n"
                    f"Ad: {extension.name()}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Uzantı Hatası",
                    "Uzantı kurulamadı.\n\n"
                    f"Hata: {extension.error()}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Uzantı Hatası",
                f"Uzantı sonucu işlenirken hata oluştu:\n\n{e}"
            )

    # =====================================================
    # UZANTI YÜKLEME SONUCU
    # =====================================================

    def extension_load_finished(self, extension):
        try:
            if extension.isLoaded():
                self.extension_manager.setExtensionEnabled(
                    extension,
                    True
                )

                print(
                    "Uzantı yüklendi:",
                    extension.name()
                )
            else:
                print(
                    "Uzantı yüklenemedi:",
                    extension.error()
                )

        except Exception as e:
            print(
                "Uzantı etkinleştirme hatası:",
                e
            )

    # =====================================================
    # YENİ SEKME
    # =====================================================

    def new_tab(self):
        tab = BrowserTab(self.profile, self)

        index = self.tabs.addTab(
            tab,
            "Yeni Sekme"
        )

        self.tabs.setCurrentIndex(index)

    # =====================================================
    # SEKME KAPAT
    # =====================================================

    def close_tab(self, index):
        if self.tabs.count() <= 1:
            return

        widget = self.tabs.widget(index)

        self.tabs.removeTab(index)

        widget.deleteLater()

    def close_current_tab(self):
        index = self.tabs.currentIndex()

        if index >= 0:
            self.close_tab(index)

    # =====================================================
    # SEKME BAŞLIĞI
    # =====================================================

    def set_tab_title(self, widget, title):
        index = self.tabs.indexOf(widget)

        if index < 0:
            return

        if not title:
            title = "Yeni Sekme"

        if len(title) > 25:
            title = title[:25] + "..."

        self.tabs.setTabText(
            index,
            title
        )


# =========================================================
# PROGRAMI BAŞLAT
# =========================================================

app = QApplication(sys.argv)

window = MAOTARAYICI()
window.show()

sys.exit(app.exec())
