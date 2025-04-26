from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel,
                             QDateEdit, QCheckBox, QSpinBox, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt, QDate
import json
import os
from datetime import datetime

class JsonMaker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HDM Version Json Maker")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 导入导出按钮区域
        io_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("导入JSON")
        self.import_btn.clicked.connect(self.import_json)
        io_layout.addWidget(self.import_btn)
        
        self.import_latest_btn = QPushButton("导入当前版本")
        self.import_latest_btn.clicked.connect(lambda: self.import_json(True))
        io_layout.addWidget(self.import_latest_btn)
        
        io_layout.addStretch()
        layout.addLayout(io_layout)
        
        # 版本信息区域
        version_group = QWidget()
        version_layout = QHBoxLayout(version_group)
        version_layout.setSpacing(10)
        
        # 版本号
        version_layout.addWidget(QLabel("版本号:"))
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("例如: 1.0.0")
        version_layout.addWidget(self.version_edit)
        
        # 发布日期
        version_layout.addWidget(QLabel("发布日期:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        version_layout.addWidget(self.date_edit)
        
        # 是否强制更新
        self.force_update = QCheckBox("强制更新")
        version_layout.addWidget(self.force_update)
        
        version_layout.addStretch()
        layout.addWidget(version_group)
        
        # 下载信息区域
        download_group = QWidget()
        download_layout = QVBoxLayout(download_group)
        
        # Windows下载信息
        win_layout = QHBoxLayout()
        win_layout.addWidget(QLabel("Windows下载链接:"))
        self.win_url = QLineEdit()
        self.win_url.setPlaceholderText("https://zzbuaoye.dpdns.org/HanabiDM/downloads/windows/HanabiDM-x.x.x.exe")
        win_layout.addWidget(self.win_url, 2)
        win_layout.addWidget(QLabel("大小(MB):"))
        self.win_size = QSpinBox()
        self.win_size.setRange(1, 1000)
        self.win_size.setValue(15)
        win_layout.addWidget(self.win_size)
        download_layout.addLayout(win_layout)
        
        # macOS下载信息
        mac_layout = QHBoxLayout()
        mac_layout.addWidget(QLabel("macOS下载链接:"))
        self.mac_url = QLineEdit()
        self.mac_url.setPlaceholderText("https://zzbuaoye.dpdns.org/HanabiDM/downloads/macos/HanabiDM-x.x.x.dmg")
        mac_layout.addWidget(self.mac_url, 2)
        mac_layout.addWidget(QLabel("大小(MB):"))
        self.mac_size = QSpinBox()
        self.mac_size.setRange(1, 1000)
        self.mac_size.setValue(16)
        mac_layout.addWidget(self.mac_size)
        download_layout.addLayout(mac_layout)
        
        layout.addWidget(download_group)
        
        # 更新日志区域
        log_group = QWidget()
        log_layout = QVBoxLayout(log_group)
        
        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("更新标题:"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如: Hanabi下载器 1.0.0 发布")
        title_layout.addWidget(self.title_edit)
        log_layout.addLayout(title_layout)
        
        # 更新内容
        log_layout.addWidget(QLabel("更新内容(每行一条):"))
        self.changes_edit = QTextEdit()
        self.changes_edit.setPlaceholderText("在这里输入更新内容，每行一条")
        log_layout.addWidget(self.changes_edit)
        
        layout.addWidget(log_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("生成并保存")
        self.save_btn.clicked.connect(self.save_json)
        button_layout.addWidget(self.save_btn)
        
        self.preview_btn = QPushButton("预览JSON")
        self.preview_btn.clicked.connect(self.preview_json)
        button_layout.addWidget(self.preview_btn)
        
        layout.addLayout(button_layout)
    
    def import_json(self, latest_only=False):
        try:
            # 打开文件对话框
            if not latest_only:
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "选择JSON文件",
                    "",
                    "JSON文件 (*.json)"
                )
                if not file_path:
                    return
            else:
                file_path = "version.json"
                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "警告", "未找到version.json文件")
                    return
            
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 获取版本信息
            if latest_only:
                if "latest" not in data:
                    QMessageBox.warning(self, "警告", "JSON文件中未找到latest字段")
                    return
                version_data = data["latest"]
            else:
                version_data = data
            
            # 填充表单
            self.version_edit.setText(version_data.get("version", ""))
            
            # 设置日期
            date_str = version_data.get("date", "")
            if date_str:
                try:
                    date = QDate.fromString(date_str, "yyyy-MM-dd")
                    self.date_edit.setDate(date)
                except:
                    pass
            
            # 设置强制更新
            self.force_update.setChecked(version_data.get("force_update", False))
            
            # 设置下载信息
            download_info = version_data.get("download", {})
            win_info = download_info.get("win", {})
            mac_info = download_info.get("mac", {})
            
            self.win_url.setText(win_info.get("url", ""))
            if "size" in win_info:
                size_str = win_info["size"].replace("MB", "").strip()
                try:
                    self.win_size.setValue(int(float(size_str)))
                except:
                    pass
            
            self.mac_url.setText(mac_info.get("url", ""))
            if "size" in mac_info:
                size_str = mac_info["size"].replace("MB", "").strip()
                try:
                    self.mac_size.setValue(int(float(size_str)))
                except:
                    pass
            
            # 设置更新日志
            notes = version_data.get("notes", {})
            self.title_edit.setText(notes.get("title", ""))
            
            content = notes.get("content", [])
            self.changes_edit.setPlainText("\n".join(content))
            
            QMessageBox.information(self, "成功", "JSON导入成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")
    
    def generate_json(self):
        # 获取更新内容列表
        changes = [line.strip() for line in self.changes_edit.toPlainText().split('\n') if line.strip()]
        
        # 构建JSON数据
        data = {
            "version": self.version_edit.text().strip(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "force_update": self.force_update.isChecked(),
            "download": {
                "win": {
                    "url": self.win_url.text().strip(),
                    "size": f"{self.win_size.value()}MB"
                },
                "mac": {
                    "url": self.mac_url.text().strip(),
                    "size": f"{self.mac_size.value()}MB"
                }
            },
            "notes": {
                "title": self.title_edit.text().strip(),
                "content": changes
            }
        }
        
        return data
    
    def save_json(self):
        try:
            # 验证必填字段
            if not self.version_edit.text().strip():
                QMessageBox.warning(self, "警告", "请输入版本号")
                return
                
            if not self.win_url.text().strip() and not self.mac_url.text().strip():
                QMessageBox.warning(self, "警告", "请至少输入一个下载链接")
                return
                
            if not self.title_edit.text().strip():
                QMessageBox.warning(self, "警告", "请输入更新标题")
                return
                
            if not self.changes_edit.toPlainText().strip():
                QMessageBox.warning(self, "警告", "请输入更新内容")
                return
            
            data = self.generate_json()
            
            # 读取现有的version.json文件（如果存在）
            version_file = "version.json"
            existing_data = {
                "latest": {},
                "history": {}
            }
            
            if os.path.exists(version_file):
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except:
                    pass
            
            # 将当前的latest移动到history中
            if "latest" in existing_data and existing_data["latest"]:
                if "history" not in existing_data:
                    existing_data["history"] = {}
                old_version = existing_data["latest"].get("version")
                if old_version:
                    existing_data["history"][old_version] = existing_data["latest"]
            
            # 更新latest
            existing_data["latest"] = data
            
            # 保存更新后的文件
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)
            
            QMessageBox.information(self, "成功", "版本信息已保存到version.json")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def preview_json(self):
        try:
            data = self.generate_json()
            preview = json.dumps(data, ensure_ascii=False, indent=4)
            
            msg = QMessageBox(self)
            msg.setWindowTitle("JSON预览")
            msg.setText(preview)
            msg.setStyleSheet("QLabel{min-width: 600px;}")
            msg.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成预览失败: {str(e)}")

if __name__ == "__main__":
    app = QApplication([])
    window = JsonMaker()
    window.show()
    app.exec()

