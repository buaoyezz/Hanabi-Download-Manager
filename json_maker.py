from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel,
                             QDateEdit, QCheckBox, QSpinBox, QMessageBox, QFileDialog,
                             QDialog, QListWidget, QDialogButtonBox, QDoubleSpinBox)
from PySide6.QtCore import Qt, QDate
import json
import os
import socket
import sys
from datetime import datetime

class SingletonApp:
    _instance = None
    _socket = None
    _port = 52764  # 选择一个不常用的端口号
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def is_running(self):
        try:
            # 尝试绑定到本地端口
            self._socket.bind(('127.0.0.1', self._port))
            return False  # 成功绑定，说明是首次运行
        except socket.error:
            return True  # 绑定失败，说明已经有实例在运行
    
    def activate_existing_window(self):
        # 在Windows系统上使用powershell查找并激活现有窗口
        if sys.platform == "win32":
            try:
                os.system('powershell -command "$p = Get-Process | Where-Object {$_.MainWindowTitle -like \'*版本信息生成器*\'} | Select-Object -First 1; if ($p) { [void][System.Reflection.Assembly]::LoadWithPartialName(\'System.Windows.Forms\'); [System.Windows.Forms.SetForegroundWindow]::Invoke($p.MainWindowHandle) }"')
            except:
                pass

class VersionSelectDialog(QDialog):
    def __init__(self, versions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择版本")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # 版本列表
        self.version_list = QListWidget()
        for version in versions:
            self.version_list.addItem(version)
        layout.addWidget(self.version_list)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_selected_version(self):
        if self.version_list.currentItem():
            return self.version_list.currentItem().text()
        return None

class JsonMaker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZZBuaoye 的Json Maker Dev By ZZBuAoYe")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # 当前编辑的版本类型（latest或history中的特定版本）
        self.editing_version_type = "latest"
        self.editing_version_key = None
        
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
        
        self.select_history_btn = QPushButton("选择历史版本")
        self.select_history_btn.clicked.connect(self.select_history_version)
        io_layout.addWidget(self.select_history_btn)
        
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
        
        win_size_layout = QHBoxLayout()
        win_size_layout.addWidget(QLabel("大小(MB):"))
        self.win_size = QDoubleSpinBox()
        self.win_size.setRange(0.01, 9999.99)
        self.win_size.setDecimals(2)
        self.win_size.setValue(15.00)
        win_size_layout.addWidget(self.win_size)
        
        self.win_size_btn = QPushButton("读取大小")
        self.win_size_btn.clicked.connect(lambda: self.read_file_size("win"))
        win_size_layout.addWidget(self.win_size_btn)
        
        win_layout.addLayout(win_size_layout)
        download_layout.addLayout(win_layout)
        
        # macOS下载信息
        mac_layout = QHBoxLayout()
        mac_layout.addWidget(QLabel("macOS下载链接:"))
        self.mac_url = QLineEdit()
        self.mac_url.setPlaceholderText("https://zzbuaoye.dpdns.org/HanabiDM/downloads/macos/HanabiDM-x.x.x.dmg")
        mac_layout.addWidget(self.mac_url, 2)
        
        mac_size_layout = QHBoxLayout()
        mac_size_layout.addWidget(QLabel("大小(MB):"))
        self.mac_size = QDoubleSpinBox()
        self.mac_size.setRange(0.01, 9999.99)
        self.mac_size.setDecimals(2)
        self.mac_size.setValue(16.00)
        mac_size_layout.addWidget(self.mac_size)
        
        self.mac_size_btn = QPushButton("读取大小")
        self.mac_size_btn.clicked.connect(lambda: self.read_file_size("mac"))
        mac_size_layout.addWidget(self.mac_size_btn)
        
        mac_layout.addLayout(mac_size_layout)
        download_layout.addLayout(mac_layout)
        
        layout.addWidget(download_group)
        
        # 更新日志区域
        log_group = QWidget()
        log_layout = QVBoxLayout(log_group)
        
        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("更新标题:"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如: Hanabi下载器 1.0.0 正式发布")
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
    
    def select_history_version(self):
        try:
            # 读取version.json文件
            if not os.path.exists("version.json"):
                QMessageBox.warning(self, "警告", "未找到version.json文件")
                return
                
            with open("version.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 获取历史版本列表
            if "history" not in data or not data["history"]:
                QMessageBox.information(self, "提示", "没有历史版本记录")
                return
                
            # 创建版本选择对话框
            versions = list(data["history"].keys())
            dialog = VersionSelectDialog(versions, self)
            
            if dialog.exec() == QDialog.Accepted:
                selected_version = dialog.get_selected_version()
                if selected_version:
                    self.load_version_data(data["history"][selected_version], "history", selected_version)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择历史版本失败: {str(e)}")
    
    def load_version_data(self, version_data, version_type="latest", version_key=None):
        try:
            # 记录当前正在编辑的版本类型和键
            self.editing_version_type = version_type
            self.editing_version_key = version_key
            
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
                    self.win_size.setValue(float(size_str))
                except:
                    pass
            
            self.mac_url.setText(mac_info.get("url", ""))
            if "size" in mac_info:
                size_str = mac_info["size"].replace("MB", "").strip()
                try:
                    self.mac_size.setValue(float(size_str))
                except:
                    pass
            
            # 设置更新日志
            notes = version_data.get("notes", {})
            self.title_edit.setText(notes.get("title", ""))
            
            content = notes.get("content", [])
            self.changes_edit.setPlainText("\n".join(content))
            
            # 更新窗口标题显示当前编辑的版本
            if version_type == "latest":
                self.setWindowTitle("版本信息生成器 - 编辑最新版本")
            else:
                self.setWindowTitle(f"版本信息生成器 - 编辑历史版本 {version_key}")
            
            QMessageBox.information(self, "成功", f"版本 {version_data.get('version', '')} 数据加载成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载版本数据失败: {str(e)}")
    
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
                self.load_version_data(version_data, "latest")
            else:
                version_data = data
                self.load_version_data(version_data)
            
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
                    "size": f"{self.win_size.value():.2f}MB"
                },
                "mac": {
                    "url": self.mac_url.text().strip(),
                    "size": f"{self.mac_size.value():.2f}MB"
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
            current_version = data["version"]
            
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
            
            # 根据编辑的版本类型决定如何保存
            if self.editing_version_type == "history" and self.editing_version_key:
                # 如果是编辑历史版本，直接更新该版本
                existing_data["history"][self.editing_version_key] = data
                
                # 如果版本号改变了，还需要更新键
                if self.editing_version_key != current_version:
                    # 创建新键，复制数据，然后删除旧键
                    existing_data["history"][current_version] = data
                    del existing_data["history"][self.editing_version_key]
                    
                    # 更新编辑状态
                    self.editing_version_key = current_version
                
                message = f"历史版本 {current_version} 已更新"
            else:
                # 检查是否正在编辑当前最新版本或历史版本
                editing_latest = (
                    "latest" in existing_data and 
                    existing_data["latest"].get("version") == current_version
                )
                
                editing_history = (
                    "history" in existing_data and
                    current_version in existing_data["history"]
                )
                
                # 如果不是编辑已存在的版本，则将当前latest移至history
                if not editing_latest and "latest" in existing_data and existing_data["latest"]:
                    if "history" not in existing_data:
                        existing_data["history"] = {}
                    old_version = existing_data["latest"].get("version")
                    if old_version:
                        existing_data["history"][old_version] = existing_data["latest"]
                
                # 如果正在编辑历史版本，则从历史记录中移除
                if editing_history:
                    # 临时保存，以便在需要时可以恢复
                    history_entry = existing_data["history"][current_version]
                    
                    # 如果编辑的是历史版本而不是最新版本，将其从历史记录中移除
                    if not editing_latest:
                        del existing_data["history"][current_version]
                
                # 更新latest
                existing_data["latest"] = data
                
                # 重置编辑状态为latest
                self.editing_version_type = "latest"
                self.editing_version_key = None
                
                message = "版本信息已保存为最新版本"
            
            # 更新窗口标题
            if self.editing_version_type == "latest":
                self.setWindowTitle("版本信息生成器 - 编辑最新版本")
            else:
                self.setWindowTitle(f"版本信息生成器 - 编辑历史版本 {self.editing_version_key}")
            
            # 保存更新后的文件
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)
            
            QMessageBox.information(self, "成功", message)
            
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

    def read_file_size(self, platform):
        """读取文件大小并更新到对应的大小输入框"""
        try:
            # 打开文件选择对话框
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                f"选择{platform.upper()}安装包文件",
                "",
                "所有文件 (*.*)"
            )
            
            if not file_path:
                return
                
            # 检查文件是否存在
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", f"文件不存在: {file_path}")
                return
                
            # 获取文件大小（字节）
            file_size_bytes = os.path.getsize(file_path)
            
            # 转换为MB并保留2位小数
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            # 更新对应的输入框
            if platform.lower() == "win":
                self.win_size.setValue(file_size_mb)
                
                # 如果URL为空，自动设置为文件名
                if not self.win_url.text().strip():
                    file_name = os.path.basename(file_path)
                    self.win_url.setText(f"https://github.com/buaoyezz/Hanabi-Download-Manager/releases/download/V{self.version_edit.text()}/{file_name}")
                    
            elif platform.lower() == "mac":
                self.mac_size.setValue(file_size_mb)
                
                # 如果URL为空，自动设置为文件名
                if not self.mac_url.text().strip():
                    file_name = os.path.basename(file_path)
                    self.mac_url.setText(f"https://github.com/buaoyezz/Hanabi-Download-Manager/releases/download/V{self.version_edit.text()}/{file_name}")
            
            QMessageBox.information(self, "成功", f"文件大小: {file_size_mb:.2f} MB")
            
        except Exception as e:
            QMessageBox.warning(self, "警告", f"读取文件大小失败: {str(e)}")

if __name__ == "__main__":
    # 检查是否已有实例在运行
    singleton = SingletonApp.get_instance()
    
    if singleton.is_running():
        # 如果已经有实例在运行，激活已有窗口并退出
        singleton.activate_existing_window()
        
        # 创建一个临时QApplication实例来显示消息框
        temp_app = QApplication(sys.argv)
        QMessageBox.information(None, "提示", "版本信息生成器已经在运行中")
        sys.exit(0)
    else:
        # 正常启动应用程序
        app = QApplication([])
        window = JsonMaker()
        window.show()
        app.exec()

