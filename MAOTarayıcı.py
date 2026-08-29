"""
================================================================================
MAO TARAYICI V2 - PROFESYONEL TEK DOSYA SÜRÜMÜ
================================================================================
Açıklama: Bu dosya; MVC mimarisine, veritabanı yönetimine, reklam engellemeye,
uzantı desteğine ve indirme yöneticisine sahip tam teşekküllü bir tarayıcıdır.
Tüm modüller (Faz 1, Faz 2 ve Faz 3) tek bir dosyada birleştirilmiştir.
================================================================================
"""

import sys
import os
import json
import uuid
import tempfile
import zipfile
import sqlite3
import logging
import traceback
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl, QSize, pyqtSignal, QTimer, QDateTime
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QMenu, QToolButton,
    QLineEdit, QMessageBox, QFileDialog, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QPushButton, QCheckBox, QScrollArea, QFrame,
    QProgressBar, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QSplitter, QComboBox, QFormLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEngineScript,
    QWebEnginePage
)

# ==========================================
# 1. PROFESYONEL LOGLAMA SİSTEMİ
# ==========================================
def setup_logger():
    """Uygulama hatalarını ve olaylarını kaydeden profesyonel log sistemi."""
    if not os.path.exists("logs"):
        os.makedirs("logs", exist_ok=True)

    log_obj = logging.getLogger("MAOTarayıcı")
    log_obj.setLevel(logging.DEBUG)

    fh = logging.FileHandler("logs/app.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    log_obj.addHandler(fh)
    log_obj.addHandler(ch)

    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log_obj.critical("Kritik Hata Oluştu:", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = handle_exception
    return log_obj

logger = setup_logger()


# ==========================================
# 2. VERİTABANI YÖNETİCİSİ (SQLITE)
# ==========================================
class DatabaseManager:
    """Tarayıcı geçmişi ve yer imlerini yöneten yerel veritabanı."""
    def __init__(self):
        if not os.path.exists("data"):
            os.makedirs("data", exist_ok=True)
        self.db_path = "data/browser_data.db"
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Geçmiş Tablosu
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        visit_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Yer İmleri Tablosu
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT UNIQUE
                    )
                """)
                conn.commit()
            logger.info("Veritabanı başarıyla başlatıldı.")
        except Exception as e:
            logger.error(f"Veritabanı başlatma hatası: {e}")

    def add_history(self, title, url):
        if url.startswith("mao://") or not url: return
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO history (title, url) VALUES (?, ?)", (title, url))
                conn.commit()
        except Exception as e:
            logger.error(f"Geçmiş ekleme hatası: {e}")

    def get_history(self, limit=100):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, url, visit_time FROM history ORDER BY visit_time DESC LIMIT ?", (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Geçmiş okuma hatası: {e}")
            return []

    def clear_history(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history")
                conn.commit()
            logger.info("Tarayıcı geçmişi temizlendi.")
        except Exception as e:
            logger.error(f"Geçmiş temizleme hatası: {e}")


# ==========================================
# 3. GELİŞMİŞ REKLAM ENGELLEYİCİ
# ==========================================
class MaoAdBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocked_keywords = [
            "doubleclick.net", "googleadservices.com", "googlesyndication.com",
            "adservice.google.com", "ads.youtube.com", "s.youtube.com/api/stats/ads",
            "adsystem.com", "amazon-adsystem.com", "adnxs.com",
            "criteo.com", "taboola.com", "outbrain.com", "pubmatic.com",
            "rubiconproject.com", "ads-twitter.com", "analytics.google.com",
            "google-analytics.com", "pixel.facebook.com", "connect.facebook.net",
            "/ads/", "/ad/", "?ad=", "&ad=", "popads.net", "adsterra.com",
            "propellerads.com", "yandex.ru/ads", "ads.yahoo.com"
        ]
        
    def interceptRequest(self, info):
        url = info.requestUrl().toString().lower()
        for keyword in self.blocked_keywords:
            if keyword in url:
                info.block(True)
                return


# ==========================================
# 4. İNDİRME YÖNETİCİSİ
# ==========================================
class DownloadWidget(QFrame):
    def __init__(self, download_item, parent=None):
        super().__init__(parent)
        self.download_item = download_item
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin: 4px; padding: 5px; }")
        
        layout = QVBoxLayout(self)
        self.name_label = QLabel(download_item.downloadFileName())
        self.name_label.setStyleSheet("font-weight: bold; color: #212529;")
        layout.addWidget(self.name_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #bbb; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #0d6efd; width: 10px; }")
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("İndiriliyor...")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self.download_item.receivedBytesChanged.connect(self.update_progress)
        self.download_item.stateChanged.connect(self.update_status)
        
    def update_progress(self):
        if self.download_item.totalBytes() > 0:
            percent = int((self.download_item.receivedBytes() / self.download_item.totalBytes()) * 100)
            self.progress_bar.setValue(percent)
            
    def update_status(self, state):
        if state == self.download_item.DownloadState.DownloadCompleted:
            self.status_label.setText("✅ Başarıyla Tamamlandı")
            self.progress_bar.setValue(100)
        elif state == self.download_item.DownloadState.DownloadCancelled:
            self.status_label.setText("❌ Kullanıcı Tarafından İptal Edildi")
        elif state == self.download_item.DownloadState.DownloadInterrupted:
            self.status_label.setText("⚠️ Bağlantı Koptu / Hata Oluştu")

class DownloadManagerUI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📥 İndirme Yöneticisi")
        self.resize(450, 550)
        
        layout = QVBoxLayout(self)
        
        header = QLabel("Son İndirmeler")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)
        
        clear_btn = QPushButton("Listeyi Temizle")
        clear_btn.clicked.connect(self.clear_list)
        layout.addWidget(clear_btn)
        
    def add_download(self, download_item):
        widget = DownloadWidget(download_item)
        self.container_layout.addWidget(widget)
        
    def clear_list(self):
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)


# ==========================================
# 5. UZANTI YÖNETİCİSİ (EXTENSION MANAGER)
# ==========================================
class MaoExtensionManager:
    def __init__(self, profile):
        self.profile = profile
        self.extensions = {} 

    def load_from_zip(self, zip_path):
        try:
            temp_dir = tempfile.mkdtemp(prefix="mao_ext_")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            return self.load_from_folder(temp_dir)
        except Exception as e:
            logger.error(f"Uzantı ZIP açma hatası: {e}")
            return False, f"Hata: {str(e)}"

    def load_from_folder(self, folder_path):
        manifest_path = os.path.join(folder_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return False, "Klasörde manifest.json bulunamadı!"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            if "content_scripts" not in manifest:
                return False, "Uzantıda 'content_scripts' bulunamadı (Qt sadece arkaplan scriptlerini destekler)."

            ext_id = str(uuid.uuid4()).replace("-", "")[:16] 
            ext_name = manifest.get('name', 'Bilinmeyen Uzantı')
            
            ext_data = {
                "id": ext_id,
                "name": ext_name,
                "version": manifest.get("version", "1.0"),
                "description": manifest.get("description", "Açıklama yok."),
                "path": folder_path,
                "enabled": True,
                "scripts": []
            }

            for script_info in manifest["content_scripts"]:
                for js_file in script_info.get("js", []):
                    js_path = os.path.join(folder_path, js_file)
                    if os.path.exists(js_path):
                        with open(js_path, "r", encoding="utf-8") as js_f:
                            script = QWebEngineScript()
                            script.setName(f"{ext_id}_{js_file}")
                            script.setSourceCode(js_f.read())
                            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                            script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
                            self.profile.scripts().insert(script)
                            ext_data["scripts"].append(script)
            
            self.extensions[ext_id] = ext_data
            logger.info(f"Uzantı yüklendi: {ext_name}")
            return True, f"'{ext_name}' başarıyla yüklendi."
        except Exception as e:
            return False, f"Hata: {str(e)}"

    def toggle_extension(self, ext_id, state):
        if ext_id in self.extensions:
            ext = self.extensions[ext_id]
            ext["enabled"] = state
            for script in ext["scripts"]:
                if state: self.profile.scripts().insert(script)
                else: self.profile.scripts().remove(script)

    def remove_extension(self, ext_id):
        if ext_id in self.extensions:
            for script in self.extensions[ext_id]["scripts"]:
                self.profile.scripts().remove(script)
            del self.extensions[ext_id]

class ExtensionsUI(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 20)
        
        top_bar = QHBoxLayout()
        title = QLabel("🧩 Uzantıları Yönet")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        top_bar.addWidget(title)
        
        load_folder_btn = QPushButton("Geliştirici: Klasörden Yükle")
        load_folder_btn.clicked.connect(self.load_folder)
        load_zip_btn = QPushButton("ZIP Dosyası Yükle")
        load_zip_btn.clicked.connect(self.load_zip)
        
        top_bar.addStretch()
        top_bar.addWidget(load_folder_btn)
        top_bar.addWidget(load_zip_btn)
        
        self.main_layout.addLayout(top_bar)
        
        info = QLabel("<i>Teknik Bilgi: Güvenlik nedeniyle Chrome açılır pencereleri (popup) desteklenmez. Yalnızca reklam engelleyiciler, renk değiştiriciler gibi arkaplan uzantıları tam uyumludur.</i>")
        info.setStyleSheet("color: #666; margin-bottom: 15px;")
        self.main_layout.addWidget(info)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.list_widget)
        self.main_layout.addWidget(self.scroll)

        self.refresh_list()

    def load_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Uzantı Klasörünü Seçin")
        if path:
            success, msg = self.manager.load_from_folder(path)
            QMessageBox.information(self, "Uzantı Kurulumu", msg)
            if success: self.refresh_list()

    def load_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Uzantı ZIP Dosyasını Seçin", "", "ZIP Arşivleri (*.zip)")
        if path:
            success, msg = self.manager.load_from_zip(path)
            QMessageBox.information(self, "Uzantı Kurulumu", msg)
            if success: self.refresh_list()

    def refresh_list(self):
        for i in reversed(range(self.list_layout.count())):
            w = self.list_layout.itemAt(i).widget()
            if w: w.setParent(None)

        if not self.manager.extensions:
            empty_lbl = QLabel("Henüz hiçbir uzantı yüklemediniz.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            return

        for ext_id, ext in self.manager.extensions.items():
            card = QFrame()
            card.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; margin-bottom: 10px; }")
            card_layout = QHBoxLayout(card)

            info_layout = QVBoxLayout()
            title_lbl = QLabel(f"<span style='font-size:16px; font-weight:bold;'>{ext['name']}</span> <span style='color:gray;'>v{ext['version']}</span>")
            desc_lbl = QLabel(ext['description'])
            desc_lbl.setWordWrap(True)
            info_layout.addWidget(title_lbl)
            info_layout.addWidget(desc_lbl)
            card_layout.addLayout(info_layout)
            
            card_layout.addStretch()
            
            controls_layout = QVBoxLayout()
            cb = QCheckBox("Uzantıyı Aktifleştir")
            cb.setChecked(ext["enabled"])
            cb.stateChanged.connect(lambda state, eid=ext_id: self.manager.toggle_extension(eid, bool(state)))
            
            rm_btn = QPushButton("Kaldır")
            rm_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; } QPushButton:hover { background-color: #c82333; }")
            rm_btn.clicked.connect(lambda _, eid=ext_id: (self.manager.remove_extension(eid), self.refresh_list()))
            
            controls_layout.addWidget(cb)
            controls_layout.addWidget(rm_btn)
            
            card_layout.addLayout(controls_layout)
            self.list_layout.addWidget(card)


# ==========================================
# 6. KULLANICI ARAYÜZÜ EKSTRA PENCERELERİ
# ==========================================
class HistoryUI(QWidget):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("🕒 Tarayıcı Geçmişi")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        clear_btn = QPushButton("🗑️ Geçmişi Temizle")
        clear_btn.clicked.connect(self.clear_history)
        header_layout.addWidget(clear_btn)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Başlık", "Bağlantı (URL)", "Ziyaret Zamanı"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        records = self.db.get_history()
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            self.table.setItem(row, 0, QTableWidgetItem(record[0]))
            self.table.setItem(row, 1, QTableWidgetItem(record[1]))
            self.table.setItem(row, 2, QTableWidgetItem(record[2]))

    def clear_history(self):
        reply = QMessageBox.question(self, "Onay", "Tüm tarayıcı geçmişini silmek istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_history()
            self.load_data()

class SettingsUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("⚙️ Tarayıcı Ayarları")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        form = QFormLayout()
        
        self.homepage_input = QLineEdit("https://www.google.com")
        form.addRow("Başlangıç Sayfası:", self.homepage_input)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Aydınlık (Light)", "Karanlık (Dark - Yakında)"])
        form.addRow("Tema Görünümü:", self.theme_combo)
        
        self.search_combo = QComboBox()
        self.search_combo.addItems(["Google", "DuckDuckGo", "Bing", "Yahoo"])
        form.addRow("Varsayılan Arama Motoru:", self.search_combo)
        
        layout.addLayout(form)
        layout.addStretch()
        
        save_btn = QPushButton("Ayarları Kaydet")
        save_btn.clicked.connect(lambda: QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi. (Arama motoru özelliği bir sonraki yamada aktifleşecek)"))
        layout.addWidget(save_btn)

class FindBar(QFrame):
    """Sayfa içi kelime arama (Ctrl+F) çubuğu"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #f1f1f1; border-bottom: 1px solid #ccc; }")
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sayfada bul...")
        self.search_input.textChanged.connect(self.find_next)
        self.search_input.returnPressed.connect(self.find_next)
        
        prev_btn = QPushButton("🔼")
        prev_btn.clicked.connect(self.find_previous)
        
        next_btn = QPushButton("🔽")
        next_btn.clicked.connect(self.find_next)
        
        close_btn = QPushButton("❌")
        close_btn.clicked.connect(self.hide)
        
        layout.addWidget(QLabel("Bul:"))
        layout.addWidget(self.search_input)
        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addWidget(close_btn)
        layout.addStretch()

    def set_browser(self, browser):
        self.browser = browser
        
    def find_next(self):
        if self.browser:
            self.browser.findText(self.search_input.text())
            
    def find_previous(self):
        if self.browser:
            self.browser.findText(self.search_input.text(), QWebEnginePage.FindFlag.FindBackward)


# ==========================================
# 7. ANA BROWSER MİMARİSİ
# ==========================================
class MaoWebPage(QWebEnginePage):
    """Özel sayfa davranışları (Örn: Yeni sekmede açma)"""
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.main_window = parent

    def createWindow(self, _type):
        # Bir linke ortatıklandığında veya target="_blank" olduğunda yeni sekme aç
        browser = QWebEngineView()
        page = MaoWebPage(self.profile(), self.main_window)
        browser.setPage(page)
        self.main_window.add_new_tab(browser, "Yükleniyor...")
        return page

class MaoBrowserV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAO TARAYICI v2 - Profesyonel Sürüm")
        self.setGeometry(100, 100, 1300, 850)
        self.setMinimumSize(800, 600)

        # 1. Altyapı Sistemleri Başlatılıyor
        self.db = DatabaseManager()
        self.profile = QWebEngineProfile.defaultProfile()
        self.adblocker = MaoAdBlocker()
        self.profile.setUrlRequestInterceptor(self.adblocker)
        self.extension_manager = MaoExtensionManager(self.profile)
        
        # 2. İndirme Bağlantıları
        self.profile.downloadRequested.connect(self.on_download_requested)
        self.download_ui = DownloadManagerUI(self)

        # 3. Arayüz Bileşenleri
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True) # Sekmelerin yerini değiştirebilme
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        self.find_bar = FindBar(self)
        
        # Ana Düzen (FindBar + Tabs)
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.find_bar)
        central_layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_shortcuts()
        
        # İlk Sekmeyi Aç
        self.add_blank_tab()
        logger.info("Tarayıcı UI başlatıldı.")

    def setup_menus(self):
        menubar = self.menuBar()
        
        # Dosya Menüsü
        file_menu = menubar.addMenu("Dosya")
        new_tab_action = QAction("Yeni Sekme", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(self.add_blank_tab)
        file_menu.addAction(new_tab_action)
        
        close_tab_action = QAction("Sekmeyi Kapat", self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addAction(close_tab_action)
        
        file_menu.addSeparator()
        exit_action = QAction("Çıkış", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Düzenle Menüsü
        edit_menu = menubar.addMenu("Düzenle")
        find_action = QAction("Sayfada Bul...", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_bar)
        edit_menu.addAction(find_action)

        # Geçmiş Menüsü
        history_menu = menubar.addMenu("Geçmiş")
        show_history_action = QAction("Tüm Geçmişi Göster", self)
        show_history_action.setShortcut("Ctrl+H")
        show_history_action.triggered.connect(self.open_history_tab)
        history_menu.addAction(show_history_action)

        # Araçlar Menüsü
        tools_menu = menubar.addMenu("Araçlar")
        extensions_action = QAction("Uzantıları Yönet", self)
        extensions_action.triggered.connect(self.open_extensions_tab)
        tools_menu.addAction(extensions_action)
        
        settings_action = QAction("Ayarlar", self)
        settings_action.triggered.connect(self.open_settings_tab)
        tools_menu.addAction(settings_action)

    def setup_toolbar(self):
        nav_bar = QToolBar("Navigasyon")
        nav_bar.setMovable(False)
        nav_bar.setIconSize(QSize(24, 24))
        self.addToolBar(nav_bar)

        back_btn = QAction("◀", self)
        back_btn.setToolTip("Geri Dön")
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(back_btn)

        fwd_btn = QAction("▶", self)
        fwd_btn.setToolTip("İleri Git")
        fwd_btn.triggered.connect(lambda: self.tabs.currentWidget().forward() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(fwd_btn)

        rld_btn = QAction("🔄", self)
        rld_btn.setToolTip("Sayfayı Yenile")
        rld_btn.triggered.connect(lambda: self.tabs.currentWidget().reload() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(rld_btn)

        # Gelişmiş URL Çubuğu
        self.url_bar = QLineEdit()
        self.url_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 13px;
                background-color: #f8f9fa;
            }
            QLineEdit:focus { border: 1px solid #0d6efd; background-color: #ffffff; }
        """)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        new_tab_btn = QAction("➕", self)
        new_tab_btn.setToolTip("Yeni Sekme (Ctrl+T)")
        new_tab_btn.triggered.connect(self.add_blank_tab)
        nav_bar.addAction(new_tab_btn)

        dl_btn = QAction("📥", self)
        dl_btn.setToolTip("İndirmeler (Downloads)")
        dl_btn.triggered.connect(self.download_ui.show)
        nav_bar.addAction(dl_btn)

        self.ext_button = QToolButton()
        self.ext_button.setText("🧩")
        self.ext_button.setToolTip("Uzantılar")
        self.ext_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.ext_menu = QMenu()
        manage_action = QAction("⚙️ Uzantıları Yönet...", self)
        manage_action.triggered.connect(self.open_extensions_tab)
        self.ext_menu.addAction(manage_action)
        self.ext_button.setMenu(self.ext_menu)
        nav_bar.addWidget(self.ext_button)

        self.tabs.currentChanged.connect(self.update_url_bar)

    def setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setMaximumHeight(14)
        self.progress_bar.hide()
        self.status.addPermanentWidget(self.progress_bar)

    def setup_shortcuts(self):
        # Kısayollar
        self.shortcut_find = QAction(self)
        self.shortcut_find.setShortcut(QKeySequence("Ctrl+F"))
        self.shortcut_find.triggered.connect(self.show_find_bar)
        self.addAction(self.shortcut_find)
        
        self.shortcut_esc = QAction(self)
        self.shortcut_esc.setShortcut(QKeySequence("Esc"))
        self.shortcut_esc.triggered.connect(self.find_bar.hide)
        self.addAction(self.shortcut_esc)

    def show_find_bar(self):
        if isinstance(self.tabs.currentWidget(), QWebEngineView):
            self.find_bar.set_browser(self.tabs.currentWidget())
            self.find_bar.show()
            self.find_bar.search_input.setFocus()
            self.find_bar.search_input.selectAll()

    # --- TAB YÖNETİMİ ---
    def open_internal_tab(self, widget, title, internal_url):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i), 'internal_url', None) == internal_url:
                self.tabs.setCurrentIndex(i)
                return
        
        widget.internal_url = internal_url
        i = self.tabs.addTab(widget, title)
        self.tabs.setCurrentIndex(i)

    def open_extensions_tab(self):
        self.open_internal_tab(ExtensionsUI(self.extension_manager, self), "🧩 Uzantılar", "mao://uzantilar")

    def open_history_tab(self):
        self.open_internal_tab(HistoryUI(self.db, self), "🕒 Geçmiş", "mao://gecmis")
        
    def open_settings_tab(self):
        self.open_internal_tab(SettingsUI(self), "⚙️ Ayarlar", "mao://ayarlar")

    def add_new_tab(self, browser, title):
        i = self.tabs.addTab(browser, title)
        self.tabs.setCurrentIndex(i)
        
        # Sinyaller
        browser.urlChanged.connect(lambda qurl, b=browser: self.update_tab_title(b, qurl))
        browser.loadFinished.connect(lambda _, index=i, b=browser: self.on_page_loaded(index, b))
        browser.loadProgress.connect(self.update_progress_bar)
        browser.loadStarted.connect(lambda: self.progress_bar.show())
        
        # EKRAN KARARMA SORUNU İÇİN: Çökme (Render Process Terminated) sinyali kurtarıcısı
        browser.page().renderProcessTerminated.connect(
            lambda status, code, b=browser: self.handle_render_crash(b, status, code)
        )

    def handle_render_crash(self, browser, status, code):
        """Web motoru çöktüğünde (siyah ekran) sayfayı otomatik kurtarır."""
        logger.warning(f"Web motoru çöktü! (Siyah Ekran). Durum: {status}, Kod: {code}. Kurtarılıyor...")
        self.status.showMessage("Görüntü motoru çöktü, sayfa otomatik kurtarılıyor...", 4000)
        browser.reload()
        
    def add_blank_tab(self):
        browser = QWebEngineView()
        page = MaoWebPage(self.profile, self)
        browser.setPage(page)
        browser.setUrl(QUrl("https://www.google.com"))
        self.add_new_tab(browser, "Yeni Sekme")

    def close_tab(self, i):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(i)
            self.tabs.removeTab(i)
            widget.deleteLater()
        else:
            self.close()

    def update_tab_title(self, browser, qurl):
        i = self.tabs.indexOf(browser)
        if i != -1: 
            host = qurl.host()
            self.tabs.setTabText(i, host if host else "Yeni Sekme")
        if self.tabs.currentWidget() == browser: 
            self.update_url_bar()

    def on_page_loaded(self, index, browser):
        title = browser.page().title()
        url = browser.url().toString()
        if index != -1 and title:
            self.tabs.setTabText(index, title[:20] + "..." if len(title) > 20 else title)
        
        self.progress_bar.hide()
        self.status.showMessage("Sayfa yüklendi.", 2000)
        
        # Ziyareti Veritabanına (Geçmişe) Kaydet
        if not url.startswith("mao://"):
            self.db.add_history(title, url)

    def update_progress_bar(self, progress):
        self.progress_bar.setValue(progress)

    def update_url_bar(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView):
            self.url_bar.setText(widget.url().toString())
            self.url_bar.setEnabled(True)
        else:
            # İç sekme (Uzantılar, Geçmiş vb.)
            internal_url = getattr(widget, 'internal_url', "mao://bilinmeyen")
            self.url_bar.setText(internal_url)
            self.url_bar.setEnabled(False)

    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not url: return
        
        if not url.startswith("http") and not url.startswith("mao://") and not url.startswith("file://"):
            # Eğer noktalı bir domain ise http ekle, değilse Google'da ara (Arama çubuğu mantığı)
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                url = f"https://www.google.com/search?q={url}"
                
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView):
            widget.setUrl(QUrl(url))
            self.status.showMessage(f"Bağlanılıyor: {url} ...")

    # --- İNDİRME SİSTEMİ BAĞLANTISI ---
    def on_download_requested(self, download_item):
        suggested_name = download_item.suggestedFileName()
        path, _ = QFileDialog.getSaveFileName(self, "Dosyayı Farklı Kaydet", suggested_name)
        
        if path:
            logger.info(f"İndirme işlemi başlatıldı: {path}")
            download_item.setDownloadDirectory(os.path.dirname(path))
            download_item.setDownloadFileName(os.path.basename(path))
            download_item.accept()
            self.download_ui.add_download(download_item)
            self.download_ui.show()


# ==========================================
# 8. UYGULAMAYI BAŞLATMA (ENTRY POINT)
# ==========================================
def main():
    logger.info("="*50)
    logger.info("MAO TARAYICI V2 (PROFESYONEL TEK DOSYA) BAŞLATILIYOR")
    logger.info("="*50)
    
    # --- EKRAN KARARMA (GPU) SORUNU ÇÖZÜMÜ ---
    # Ekran kartı sürücüsü (NVIDIA/AMD vb.) ile Chromium uyuşmazlığını engeller
    sys.argv.extend([
        "--disable-gpu", 
        "--no-sandbox", 
        "--disable-software-rasterizer",
        "--disable-gpu-compositing"
    ])
    
    app = QApplication(sys.argv)
    
    # Modern Qt Fusion Teması Uygulanıyor (Faz 2: Tasarım)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    try:
        window = MaoBrowserV2()
        window.show()
        
        exit_code = app.exec()
        logger.info(f"Uygulama normal şekilde kapatıldı. (Çıkış Kodu: {exit_code})")
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"Beklenmeyen Ölümcül Hata! Uygulama çöktü: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
