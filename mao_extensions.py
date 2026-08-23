import json
import os
import zipfile
import tempfile
import uuid
import shutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QScrollArea, QFrame, 
                             QMessageBox, QFileDialog, QSizePolicy)
from PyQt6.QtGui import QFont
from PyQt6.QtWebEngineCore import QWebEngineScript

class MaoExtensionManager:
    def __init__(self, profile):
        self.profile = profile
        self.extensions = {} # Yüklü uzantıları burada tutacağız

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
                return False, "Uzantı yüklendi fakat 'content_scripts' bulunamadı (Pop-up/Background şimdilik desteklenmiyor)."

            ext_id = str(uuid.uuid4()).replace("-", "")[:16] # Rastgele 16 haneli benzersiz kimlik
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
            # Önce aktif scriptleri kaldır
            for script in ext["scripts"]:
                self.profile.scripts().remove(script)
            # Sözlükten sil
            del self.extensions[ext_id]


class ExtensionsUI(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 20)

        # 1. ÜST BAR (Başlık ve Geliştirici Modu)
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

        # 2. GELİŞTİRİCİ ARAÇLARI (Gizli başlar)
        self.dev_tools_widget = QWidget()
        dev_tools_layout = QHBoxLayout(self.dev_tools_widget)
        dev_tools_layout.setContentsMargins(0, 0, 0, 0)
        
        load_folder_btn = QPushButton("Klasöre Çıkarılmış Uzantıyı Yükle")
        load_folder_btn.clicked.connect(self.load_folder)
        
        load_zip_btn = QPushButton("ZIP Uzantısı Yükle")
        load_zip_btn.clicked.connect(self.load_zip)
        
        info_label = QLabel("<i>Uzantı mı geliştiriyorsunuz? Haberiniz olsun: Chrome Web Mağazası API'leri QtWebEngine tarafından kısıtlanmıştır, ancak .zip ve klasör ile tüm içerik scriptlerinizi test edebilirsiniz.</i>")
        info_label.setStyleSheet("color: gray;")
        
        dev_tools_layout.addWidget(load_folder_btn)
        dev_tools_layout.addWidget(load_zip_btn)
        dev_tools_layout.addWidget(info_label)
        dev_tools_layout.addStretch()
        self.dev_tools_widget.setVisible(False) # Başlangıçta gizli
        self.main_layout.addWidget(self.dev_tools_widget)

        # Ayracı
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(line)

        # 3. UZANTILAR LİSTESİ (Scroll Area)
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
        # Önceki listeyi temizle
        for i in reversed(range(self.list_layout.count())): 
            widget_to_remove = self.list_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        if not self.manager.extensions:
            empty_lbl = QLabel("Henüz bir uzantı yüklenmedi.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            return

        # Uzantıları karta dönüştür
        for ext_id, ext in self.manager.extensions.items():
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("QFrame { background-color: #f9f9f9; border-radius: 8px; margin-bottom: 10px; }")
            card_layout = QHBoxLayout(card)

            # Sol Bilgi
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

            # Sağ Butonlar
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