import sys
import json
import os
import zipfile
import tempfile
import uuid
import traceback

def hata_yakala(exc_type, exc_value, exc_traceback):
    with open("hata_raporu.txt", "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
sys.excepthook = hata_yakala

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QMenu, QToolButton,
    QLineEdit, QMessageBox, QFileDialog, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QPushButton, QCheckBox, QScrollArea, QFrame,
    QProgressBar, QDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEngineScript
)

# ==========================================
# 1. AD BLOCKER (REKLAM ENGELLEYİCİ)
# ==========================================
class MaoAdBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocked_hosts = [
            "doubleclick.net", "googleadservices.com",
            "ads.youtube.com", "adsystem.com", "analytics.google.com"
        ]
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        for host in self.blocked_hosts:
            if host in url:
                info.block(True)
                return

# ==========================================
# 2. İNDİRME YÖNETİCİSİ (DOWNLOAD MANAGER)
# ==========================================
class DownloadWidget(QFrame):
    def __init__(self, download_item, parent=None):
        super().__init__(parent)
        self.download_item = download_item
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #f1f1f1; border-radius: 5px; margin: 2px; }")
        
        layout = QVBoxLayout(self)
        
        self.name_label = QLabel(download_item.downloadFileName())
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("İndiriliyor...")
        layout.addWidget(self.status_label)
        
        # Sinyalleri bağla
        self.download_item.receivedBytesChanged.connect(self.update_progress)
        self.download_item.stateChanged.connect(self.update_status)
        
    def update_progress(self):
        if self.download_item.totalBytes() > 0:
            percent = int((self.download_item.receivedBytes() / self.download_item.totalBytes()) * 100)
            self.progress_bar.setValue(percent)
            
    def update_status(self, state):
        if state == self.download_item.DownloadState.DownloadCompleted:
            self.status_label.setText("✅ Tamamlandı")
            self.progress_bar.setValue(100)
        elif state == self.download_item.DownloadState.DownloadCancelled:
            self.status_label.setText("❌ İptal Edildi")
        elif state == self.download_item.DownloadState.DownloadInterrupted:
            self.status_label.setText("⚠️ Hata / Kesildi")

class DownloadManagerUI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📥 İndirmeler")
        self.resize(400, 500)
        
        layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)
        
    def add_download(self, download_item):
        widget = DownloadWidget(download_item)
        self.container_layout.addWidget(widget)

# ==========================================
# 3. UZANTI YÖNETİCİSİ (EXTENSION MANAGER)
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
            return False, f"Hata: {str(e)}"

    def load_from_folder(self, folder_path):
        manifest_path = os.path.join(folder_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return False, "Klasörde manifest.json bulunamadı!"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            if "content_scripts" not in manifest:
                return False, "Uzantıda 'content_scripts' bulunamadı (Qt sadece bunu destekler)."

            ext_id = str(uuid.uuid4()).replace("-", "")[:16] 
            ext_name = manifest.get('name', 'Bilinmeyen Uzantı')
            
            ext_data = {
                "id": ext_id,
                "name": ext_name,
                "version": manifest.get("version", "1.0"),
                "description": manifest.get("description", ""),
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
            return True, f"'{ext_name}' yüklendi."
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

# ==========================================
# 4. UZANTI YÖNETİM ARAYÜZÜ SEKRESİ
# ==========================================
class ExtensionsUI(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        top_bar = QHBoxLayout()
        title = QLabel("⚙️ Uzantıları Yönet")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        top_bar.addWidget(title)
        
        load_folder_btn = QPushButton("Klasörden Yükle")
        load_folder_btn.clicked.connect(self.load_folder)
        load_zip_btn = QPushButton("ZIP Yükle")
        load_zip_btn.clicked.connect(self.load_zip)
        
        top_bar.addStretch()
        top_bar.addWidget(load_folder_btn)
        top_bar.addWidget(load_zip_btn)
        
        self.main_layout.addLayout(top_bar)
        
        # Info mesajı (kullanıcı bilsin diye)
        info = QLabel("<i>Not: Qt altyapısı kullandığımız için Chrome uzantılarının açılır (popup) menüleri çalışmaz, sadece arka plan özellikleri etkindir.</i>")
        info.setStyleSheet("color: red;")
        self.main_layout.addWidget(info)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.list_widget)
        self.main_layout.addWidget(self.scroll)

        self.refresh_list()

    def load_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Klasör Seç")
        if path:
            success, msg = self.manager.load_from_folder(path)
            QMessageBox.information(self, "Durum", msg)
            if success: self.refresh_list()

    def load_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "ZIP Seç", "", "ZIP (*.zip)")
        if path:
            success, msg = self.manager.load_from_zip(path)
            QMessageBox.information(self, "Durum", msg)
            if success: self.refresh_list()

    def refresh_list(self):
        for i in reversed(range(self.list_layout.count())):
            self.list_layout.itemAt(i).widget().setParent(None)

        for ext_id, ext in self.manager.extensions.items():
            card = QFrame()
            card.setStyleSheet("background-color:#fff; border:1px solid #ccc; border-radius:5px; padding:10px;")
            card_layout = QHBoxLayout(card)

            info_layout = QVBoxLayout()
            info_layout.addWidget(QLabel(f"<b>{ext['name']}</b>"))
            info_layout.addWidget(QLabel(ext['description']))
            card_layout.addLayout(info_layout)
            
            card_layout.addStretch()
            
            cb = QCheckBox("Aktif")
            cb.setChecked(ext["enabled"])
            cb.stateChanged.connect(lambda state, eid=ext_id: self.manager.toggle_extension(eid, bool(state)))
            
            rm_btn = QPushButton("Sil")
            rm_btn.clicked.connect(lambda _, eid=ext_id: (self.manager.remove_extension(eid), self.refresh_list()))
            
            card_layout.addWidget(cb)
            card_layout.addWidget(rm_btn)
            self.list_layout.addWidget(card)

# ==========================================
# 5. ANA TARAYICI (MAO BROWSER V2)
# ==========================================
class MaoBrowserV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAO TARAYICI v2")
        self.setGeometry(100, 100, 1200, 800)

        self.profile = QWebEngineProfile.defaultProfile()
        self.adblocker = MaoAdBlocker()
        self.profile.setUrlRequestInterceptor(self.adblocker)
        self.extension_manager = MaoExtensionManager(self.profile)
        
        # İndirme Bağlantısı (İndirme İsteği Geldiğinde Yakala)
        self.profile.downloadRequested.connect(self.on_download_requested)
        self.download_ui = DownloadManagerUI(self)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.setup_ui()
        self.add_blank_tab()

    def setup_ui(self):
        nav_bar = QToolBar("Navigasyon")
        self.addToolBar(nav_bar)

        back_btn = QAction("Geri", self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(back_btn)

        fwd_btn = QAction("İleri", self)
        fwd_btn.triggered.connect(lambda: self.tabs.currentWidget().forward() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(fwd_btn)

        rld_btn = QAction("Yenile", self)
        rld_btn.triggered.connect(lambda: self.tabs.currentWidget().reload() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(rld_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        new_tab_btn = QAction("➕", self)
        new_tab_btn.setToolTip("Yeni Sekme")
        new_tab_btn.triggered.connect(self.add_blank_tab)
        nav_bar.addAction(new_tab_btn)

        # İndirmeler Butonu
        dl_btn = QAction("📥", self)
        dl_btn.setToolTip("İndirmeler")
        dl_btn.triggered.connect(self.download_ui.show)
        nav_bar.addAction(dl_btn)

        # Yapboz - Uzantılar Butonu ve Menüsü
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

    def on_download_requested(self, download_item):
        # Dosyayı nereye kaydedeceğini sor
        suggested_name = download_item.suggestedFileName()
        path, _ = QFileDialog.getSaveFileName(self, "Dosyayı Kaydet", suggested_name)
        
        if path:
            download_item.setDownloadDirectory(os.path.dirname(path))
            download_item.setDownloadFileName(os.path.basename(path))
            download_item.accept()
            
            # İndirmeyi yönetici penceresine ekle ve pencereyi aç
            self.download_ui.add_download(download_item)
            self.download_ui.show()

    def open_extensions_tab(self):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "🧩 Uzantılar":
                self.tabs.setCurrentIndex(i)
                return
        ext_ui = ExtensionsUI(self.extension_manager, self)
        i = self.tabs.addTab(ext_ui, "🧩 Uzantılar")
        self.tabs.setCurrentIndex(i)

    def add_blank_tab(self):
        browser = QWebEngineView()
        browser.setUrl(QUrl("https://www.google.com"))
        i = self.tabs.addTab(browser, "Yeni Sekme")
        self.tabs.setCurrentIndex(i)
        
        browser.urlChanged.connect(lambda qurl, b=browser: self.update_tab_title(b, qurl))
        browser.loadFinished.connect(lambda _, index=i, b=browser: self.tabs.setTabText(index, b.page().title()))

    def close_tab(self, i):
        if self.tabs.count() > 1:
            self.tabs.removeTab(i)

    def update_tab_title(self, browser, qurl):
        i = self.tabs.indexOf(browser)
        if i != -1: self.tabs.setTabText(i, qurl.host())
        if self.tabs.currentWidget() == browser: self.update_url_bar()

    def update_url_bar(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView):
            self.url_bar.setText(widget.url().toString())
            self.url_bar.setEnabled(True)
        else:
            self.url_bar.setText("mao://uzantilar")
            self.url_bar.setEnabled(False)

    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith("http") and not url.startswith("mao://"):
            url = "https://" + url
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView):
            widget.setUrl(QUrl(url))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MaoBrowserV2()
    window.show()
    sys.exit(app.exec())
