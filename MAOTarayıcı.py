import sys
import json
import os
import zipfile
import tempfile
import uuid

# --- HATA YAKALAMA (Sessiz Çökmeleri Önlemek ve Raporlamak İçin) ---
import traceback
def hata_yakala(exc_type, exc_value, exc_traceback):
    with open("hata_raporu.txt", "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
sys.excepthook = hata_yakala

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QKeySequence, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar,
    QLineEdit, QMessageBox, QFileDialog, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QPushButton, QCheckBox, QScrollArea, QFrame
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEngineScript
)

# ==========================================
# 1. AD BLOCKER (REKLAM ENGELLEYİCİ) SINIFI
# ==========================================
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


# ==========================================
# 2. UZANTI YÖNETİCİSİ (EXTENSION MANAGER)
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
        except zipfile.BadZipFile:
            return False, "Geçersiz ZIP dosyası."
        except Exception as e:
            return False, f"ZIP Çıkarma Hatası: {str(e)}"

    def load_from_folder(self, folder_path):
        manifest_path = os.path.join(folder_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return False, "Klasörde manifest.json bulunamadı!"

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            if "content_scripts" not in manifest:
                return False, "Uzantı yüklendi fakat 'content_scripts' bulunamadı."

            ext_id = str(uuid.uuid4()).replace("-", "")[:16] 
            ext_name = manifest.get('name', 'Bilinmeyen Uzantı')
            
            ext_data = {
                "id": ext_id,
                "name": ext_name,
                "version": manifest.get("version", "1.0"),
                "description": manifest.get("description", "Açıklama bulunmuyor."),
                "path": folder_path,
                "enabled": True,
                "scripts": []
            }

            for script_info in manifest["content_scripts"]:
                for js_file in script_info.get("js", []):
                    js_path = os.path.join(folder_path, js_file)
                    if os.path.exists(js_path):
                        with open(js_path, "r", encoding="utf-8") as js_f:
                            script_source = js_f.read()
                            
                            script = QWebEngineScript()
                            script.setName(f"{ext_id}_{js_file}")
                            script.setSourceCode(script_source)
                            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                            script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
                            
                            self.profile.scripts().insert(script)
                            ext_data["scripts"].append(script)
            
            self.extensions[ext_id] = ext_data
            return True, f"'{ext_name}' başarıyla yüklendi."
            
        except json.JSONDecodeError:
            return False, "manifest.json dosyası bozuk (Geçersiz JSON)."
        except Exception as e:
            return False, f"Bilinmeyen Uzantı Hatası: {str(e)}"

    def toggle_extension(self, ext_id, state):
        if ext_id in self.extensions:
            ext = self.extensions[ext_id]
            ext["enabled"] = state
            for script in ext["scripts"]:
                if state:
                    self.profile.scripts().insert(script)
                else:
                    self.profile.scripts().remove(script)

    def remove_extension(self, ext_id):
        if ext_id in self.extensions:
            ext = self.extensions[ext_id]
            for script in ext["scripts"]:
                self.profile.scripts().remove(script)
            del self.extensions[ext_id]


# ==========================================
# 3. UZANTI ARAYÜZÜ (EXTENSIONS UI)
# ==========================================
class ExtensionsUI(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 20)

        # Üst Bar
        top_bar = QHBoxLayout()
        title_label = QLabel("🧩 Uzantılar")
        title_font = QFont("Arial", 20, QFont.Weight.Bold)
        title_label.setFont(title_font)
        
        self.dev_mode_cb = QCheckBox("Geliştirici modu")
        self.dev_mode_cb.stateChanged.connect(self.toggle_dev_mode)
        
        self.shortcut_btn = QPushButton("⌨️ Klavye Kısayolları")
        self.shortcut_btn.clicked.connect(lambda: QMessageBox.information(self, "Kısayollar", "Uzantı kısayolları yakında eklenecektir."))
        
        top_bar.addWidget(title_label)
        top_bar.addStretch()
        top_bar.addWidget(self.shortcut_btn)
        top_bar.addWidget(self.dev_mode_cb)
        self.main_layout.addLayout(top_bar)

        # Geliştirici Araçları
        self.dev_tools_widget = QWidget()
        dev_tools_layout = QHBoxLayout(self.dev_tools_widget)
        dev_tools_layout.setContentsMargins(0, 0, 0, 0)
        
        load_folder_btn = QPushButton("Klasöre Çıkarılmış Uzantıyı Yükle")
        load_folder_btn.clicked.connect(self.load_folder)
        
        load_zip_btn = QPushButton("ZIP Uzantısı Yükle")
        load_zip_btn.clicked.connect(self.load_zip)
        
        info_label = QLabel("<i>Uzantı mı geliştiriyorsunuz? Haberiniz olsun: Chrome Web Mağazası API'leri QtWebEngine tarafından kısıtlanmıştır...</i>")
        info_label.setStyleSheet("color: gray;")
        
        dev_tools_layout.addWidget(load_folder_btn)
        dev_tools_layout.addWidget(load_zip_btn)
        dev_tools_layout.addWidget(info_label)
        dev_tools_layout.addStretch()
        self.dev_tools_widget.setVisible(False) 
        self.main_layout.addWidget(self.dev_tools_widget)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(line)

        # Uzantılar Listesi (Scroll Area)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.list_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.refresh_list()

    def toggle_dev_mode(self, state):
        self.dev_tools_widget.setVisible(bool(state))

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Uzantı Klasörünü Seçin")
        if folder_path:
            success, msg = self.manager.load_from_folder(folder_path)
            QMessageBox.information(self, "Durum", msg)
            if success: self.refresh_list()

    def load_zip(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Uzantı ZIP Dosyasını Seçin", "", "ZIP Files (*.zip)")
        if file_path:
            success, msg = self.manager.load_from_zip(file_path)
            QMessageBox.information(self, "Durum", msg)
            if success: self.refresh_list()

    def refresh_list(self):
        for i in reversed(range(self.list_layout.count())): 
            widget_to_remove = self.list_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        if not self.manager.extensions:
            empty_lbl = QLabel("Henüz bir uzantı yüklenmedi.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            return

        for ext_id, ext in self.manager.extensions.items():
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("QFrame { background-color: #f9f9f9; border-radius: 8px; margin-bottom: 10px; }")
            card_layout = QHBoxLayout(card)

            info_layout = QVBoxLayout()
            name_lbl = QLabel(f"<b>{ext['name']}</b> <span style='color:gray;'>{ext['version']}</span>")
            desc_lbl = QLabel(ext['description'])
            desc_lbl.setWordWrap(True)
            id_lbl = QLabel(f"<small>Kimlik: {ext['id']}</small>")
            id_lbl.setStyleSheet("color: #666;")
            
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            info_layout.addWidget(id_lbl)
            card_layout.addLayout(info_layout)
            
            card_layout.addStretch()

            btn_layout = QVBoxLayout()
            
            toggle_cb = QCheckBox("Aktif")
            toggle_cb.setChecked(ext["enabled"])
            toggle_cb.stateChanged.connect(lambda state, eid=ext_id: self.manager.toggle_extension(eid, bool(state)))
            
            details_btn = QPushButton("Ayrıntılar")
            details_btn.clicked.connect(lambda _, e=ext: QMessageBox.information(self, "Ayrıntılar", f"İsim: {e['name']}\nSürüm: {e['version']}\nKimlik: {e['id']}\nYol: {e['path']}"))
            
            remove_btn = QPushButton("Kaldır")
            remove_btn.setStyleSheet("color: red;")
            remove_btn.clicked.connect(lambda _, eid=ext_id: self.remove_ext_ui(eid))

            btn_layout.addWidget(toggle_cb)
            btn_layout.addWidget(details_btn)
            btn_layout.addWidget(remove_btn)
            
            card_layout.addLayout(btn_layout)
            self.list_layout.addWidget(card)

    def remove_ext_ui(self, ext_id):
        reply = QMessageBox.question(self, "Kaldır", "Bu uzantıyı kaldırmak istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.remove_extension(ext_id)
            self.refresh_list()


# ==========================================
# 4. ANA TARAYICI SINIFI (MAO BROWSER V2)
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

        forward_btn = QAction("İleri", self)
        forward_btn.triggered.connect(lambda: self.tabs.currentWidget().forward() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(forward_btn)

        refresh_btn = QAction("Yenile", self)
        refresh_btn.triggered.connect(lambda: self.tabs.currentWidget().reload() if isinstance(self.tabs.currentWidget(), QWebEngineView) else None)
        nav_bar.addAction(refresh_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        new_tab_btn = QAction("➕ Yeni Sekme", self)
        new_tab_btn.setShortcut(QKeySequence("Ctrl+T")) 
        new_tab_btn.triggered.connect(self.add_blank_tab)
        nav_bar.addAction(new_tab_btn)

        extensions_btn = QAction("🧩 Uzantılar", self)
        extensions_btn.triggered.connect(self.open_extensions_tab)
        nav_bar.addAction(extensions_btn)

        self.tabs.currentChanged.connect(self.update_url_bar)

        close_tab_shortcut = QAction("Sekmeyi Kapat", self)
        close_tab_shortcut.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_shortcut.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        self.addAction(close_tab_shortcut)

    def add_blank_tab(self):
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