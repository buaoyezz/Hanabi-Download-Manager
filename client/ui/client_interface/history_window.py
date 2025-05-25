from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QSizePolicy, QFrame, QScrollArea, QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap

import os
import datetime
import functools

from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.client_interface.task_window import TaskItemWidget, RoundedTaskFrame
from core.history.history_manager import HistoryManager
from client.ui.components.customNotify import NotifyManager
from client.I18N.i18n import i18n

class HistoryWindow(QWidget):
    """下载历史记录窗口"""
    
    # 定义信号
    history_item_clicked = Signal(dict)  # 历史项被点击
    history_cleared = Signal()  # 历史被清空
    
    def __init__(self, font_manager=None, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = font_manager if font_manager else FontManager()
        
        # 初始化历史记录管理器
        self.history_manager = HistoryManager()
        
        # 保存历史任务项的引用
        self.history_items = {}
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        
        # 标题和控制按钮
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(20, 10, 20, 10)
        self.header_layout.setSpacing(10)
        
        # 标题布局
        title_layout = QHBoxLayout()
        title_layout.setSpacing(5)
        
        # 标题图标
        title_icon = QLabel()
        title_icon.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(title_icon, 24)
        title_icon.setText(self.font_manager.get_icon_text("ic_fluent_history_16_regular"))
        title_icon.setStyleSheet("color: #B39DDB;")
        title_layout.addWidget(title_icon)
        
        # 标题文本
        self.title_label = QLabel(i18n.get_text("download_history"))
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold;")
        self.font_manager.apply_font(self.title_label)
        title_layout.addWidget(self.title_label)
        
        self.header_layout.addLayout(title_layout)
        
        self.header_layout.addStretch(1)
        
        # 添加历史页面的操作按钮
        self._setup_control_buttons()
        
        self.main_layout.addLayout(self.header_layout)
        
        # 历史记录列表区域
        self._setup_history_area()
        
        # 加载历史记录
        self.load_history()
        
        # 连接语言变更信号
        i18n.language_changed.connect(self.update_ui_texts)
    
    def update_ui_texts(self):
        """更新UI上的所有文本以匹配当前语言"""
        # 标题
        self.title_label.setText(i18n.get_text("download_history"))
        
        # 按钮文本
        self.refresh_text_label.setText(i18n.get_text("refresh"))
        self.clear_text_label.setText(i18n.get_text("clear"))
        
        # 更新刷新按钮提示
        self.refresh_btn.setToolTip(i18n.get_text("refresh_history"))
        
        # 更新清空按钮提示
        self.clear_btn.setToolTip(i18n.get_text("clear_history"))
        
        # 更新空历史提示（如果存在）
        for i in range(self.history_container_layout.count()):
            item = self.history_container_layout.itemAt(i)
            if item and item.widget() and item.widget().objectName() == "emptyHistoryLabel":
                item.widget().setText(i18n.get_text("no_download_history"))
                break
    
    def _setup_control_buttons(self):
        """设置历史页面的操作按钮"""
        control_button_style = """
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """
        
        # 创建带图标按钮的辅助函数
        def create_control_button(text, icon_name):
            btn = QPushButton()
            btn.setStyleSheet(control_button_style)
            
            # 使用布局方式设置图标和文本
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(8, 0, 8, 0)
            btn_layout.setSpacing(5)
            
            # 创建图标标签
            icon_label = self.font_manager.create_icon_label(
                btn,
                icon_name,
                size=14,
                color="#FFFFFF"
            )
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            return btn, text_label, btn_layout
        
        # 刷新按钮
        self.refresh_btn, self.refresh_text_label, refresh_btn_layout = create_control_button(
            i18n.get_text("refresh"), 
            "ic_fluent_arrow_sync_24_regular"
        )
        refresh_btn_layout.addWidget(self.refresh_text_label)
        self.refresh_btn.setToolTip(i18n.get_text("refresh_history"))
        self.refresh_btn.clicked.connect(self.load_history)
        
        # 清空按钮
        self.clear_btn, self.clear_text_label, clear_btn_layout = create_control_button(
            i18n.get_text("clear"), 
            "ic_fluent_delete_24_regular"
        )
        clear_btn_layout.addWidget(self.clear_text_label)
        self.clear_btn.setToolTip(i18n.get_text("clear_history"))
        self.clear_btn.clicked.connect(self.clear_history)
        
        # 添加按钮到布局
        self.header_layout.addWidget(self.refresh_btn)
        self.header_layout.addWidget(self.clear_btn)
    
    def _setup_history_area(self):
        """设置历史记录区域"""
        # 创建圆角容器框架
        self.history_frame = RoundedTaskFrame()
        history_frame_layout = QVBoxLayout(self.history_frame)
        history_frame_layout.setContentsMargins(10, 10, 10, 10)
        history_frame_layout.setSpacing(0)
        
        # 创建滚动区域
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QScrollArea.NoFrame)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(self.history_scroll, "dark")
        
        # 创建历史记录容器
        self.history_container = QWidget()
        self.history_container.setObjectName("historyContainer")
        self.history_container.setStyleSheet("""
            #historyContainer {
                background-color: transparent;
            }
        """)
        
        # 创建垂直布局用于放置任务项
        self.history_container_layout = QVBoxLayout(self.history_container)
        self.history_container_layout.setContentsMargins(0, 0, 0, 0)
        self.history_container_layout.setSpacing(10)
        self.history_container_layout.addStretch()  # 添加弹性空间，使任务项靠顶部对齐
        
        # 设置滚动区域的内容
        self.history_scroll.setWidget(self.history_container)
        
        # 添加滚动区域到任务框架
        history_frame_layout.addWidget(self.history_scroll)
        
        # 将任务框架添加到主布局
        self.main_layout.addWidget(self.history_frame)
    
    def load_history(self):
        """加载历史记录"""
        # 显示加载状态
        print(i18n.get_text("reloading_history"))
        
        # 清空现有历史项
        self.clear_history_items()
        
        # 获取历史记录 - 确保强制从文件重新加载
        history_records = self.history_manager.get_all_records(force_reload=True)
        
        print(f"{i18n.get_text('loaded_history_count')}: {len(history_records)}")
        
        if not history_records:
            # 显示无历史记录提示
            self._show_empty_history_message()
            return
        
        # 添加历史记录项
        for record in history_records:
            self.add_history_item(record)
    
    def clear_history_items(self):
        """清空历史项组件（不删除实际历史记录）"""
        # 清除容器内的所有组件
        for row, history_item in list(self.history_items.items()):
            history_item.setParent(None)
            self.history_container_layout.removeWidget(history_item)
        
        # 清空历史项字典
        self.history_items.clear()
        
        # 移除空历史提示（如果存在）
        for i in range(self.history_container_layout.count()):
            item = self.history_container_layout.itemAt(i)
            if item and item.widget() and item.widget().objectName() == "emptyHistoryLabel":
                item.widget().setParent(None)
                break
    
    def clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(
            self, 
            i18n.get_text("confirm_clear"), 
            i18n.get_text("clear_history_confirm"),
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清空历史记录
            self.history_manager.clear_history()
            
            # 清空界面
            self.clear_history_items()
            
            # 显示空历史提示
            self._show_empty_history_message()
            
            # 添加简洁的通知
            try:
                NotifyManager.warning(i18n.get_text("all_history_cleared"))
            except Exception as e:
                print(f"{i18n.get_text('show_notify_failed')}: {e}")
            
            # 发送信号
            self.history_cleared.emit()
    
    def _show_empty_history_message(self):
        """显示无历史记录提示"""
        empty_label = QLabel(i18n.get_text("no_download_history"))
        empty_label.setObjectName("emptyHistoryLabel")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #9E9E9E; font-size: 14px; padding: 20px;")
        self.font_manager.apply_font(empty_label)
        
        # 将提示添加到布局
        self.history_container_layout.insertWidget(0, empty_label)
    
    def add_history_item(self, history_record):
        """添加一个历史记录项
        
        Args:
            history_record: 包含历史信息的字典，包含以下字段:
                          filename: 文件名
                          save_path: 保存路径
                          file_size: 文件大小
                          download_time: 下载时间
                          status: 状态
        
        Returns:
            int: 历史项索引
        """
        # 获取当前行数作为新历史项的索引
        row_position = len(self.history_items)
        
        # 创建新的历史项组件
        history_item = TaskItemWidget(parent=self.history_container, row_index=row_position)
        
        # 更新历史项信息
        history_item.update_filename(history_record.get('filename', i18n.get_text("unknown_file")))
        history_item.update_size(history_record.get('file_size', 0))
        
        # 设置下载时间
        download_time = history_record.get('download_time', '')
        if download_time:
            history_item.update_speed(f"{i18n.get_text('downloaded_at')}: {download_time}")
        
        # 添加到容器布局的顶部
        self.history_container_layout.insertWidget(0, history_item)
        
        # 保存历史项引用
        self.history_items[row_position] = history_item
        
        # 在历史项上存储历史记录数据
        history_item.history_data = history_record
        history_item.row_index = row_position
        
        # 设置鼠标悬停样式，提示卡片可点击
        history_item.setStyleSheet("""
            TaskItemWidget {
                background-color: #1A1A1A;
                border-radius: 5px;
                margin: 3px 0px;
            }
            TaskItemWidget:hover {
                background-color: #252525;
                border: 1px solid #3E3E42;
            }
        """)
        
        # 使用mousePressEvent捕获鼠标点击
        history_item.mousePressEvent = lambda event, record=history_record: self._on_history_item_clicked(event, record)
        
        # 设置鼠标指针形状为手形，提示可点击
        history_item.setCursor(Qt.PointingHandCursor)
        
        # 设置状态
        if history_record.get('status') == 'completed':
            history_item.update_status(i18n.get_text("download_completed"), True)
            history_item.add_completed_actions()
            
            # 添加重新下载按钮
            self._add_redownload_button(history_item, history_record)
            
            # 连接其他操作按钮
            self._connect_completed_actions(row_position, history_record)
        elif history_record.get('status') == 'error':
            history_item.set_failed_status(history_record.get('error_message', i18n.get_text("download_failed")))
            
            # 对于失败的下载，也添加重新下载按钮
            self._add_redownload_button(history_item, history_record)
        
        return row_position
    
    def _on_history_item_clicked(self, event, history_record):
        """处理历史项被点击的事件"""
        # 只处理左键点击
        if event.button() == Qt.LeftButton:
            # 检查点击是否发生在按钮区域
            sender = self.sender()
            if sender:
                # 获取按钮区域的位置
                buttons_area = None
                if hasattr(sender, 'action_widget'):
                    buttons_area = sender.action_widget.geometry()
                
                # 如果点击不在按钮区域，则触发重新下载
                if not buttons_area or not buttons_area.contains(event.pos()):
                    self._redownload_file(history_record)
    
    def _add_redownload_button(self, history_item, history_record):
        """添加重新下载按钮到历史项"""
        # 检查是否已有操作按钮区域
        if not hasattr(history_item, 'actions_layout'):
            return
        
        # 创建重新下载按钮
        redownload_btn = QPushButton()
        redownload_btn.setToolTip(i18n.get_text("redownload"))
        redownload_btn.setCursor(Qt.PointingHandCursor)
        redownload_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 120, 215, 0.8);
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 215, 1.0);
            }
            QPushButton:pressed {
                background-color: rgba(0, 90, 170, 1.0);
            }
        """)
        
        # 使用布局设置图标和文本
        btn_layout = QHBoxLayout(redownload_btn)
        btn_layout.setContentsMargins(4, 0, 4, 0)
        btn_layout.setSpacing(3)
        
        # 创建图标标签
        icon_label = QLabel()
        self.font_manager.apply_icon_font(icon_label, 12)
        icon_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_download_24_regular"))
        icon_label.setStyleSheet("color: white; background-color: transparent;")
        btn_layout.addWidget(icon_label)
        
        # 创建文本标签
        text_label = QLabel(i18n.get_text("redownload"))
        text_label.setStyleSheet("color: white; background-color: transparent;")
        btn_layout.addWidget(text_label)
        
        # 添加按钮到操作区域
        history_item.actions_layout.addWidget(redownload_btn)
        
        # 存储按钮引用
        history_item.redownload_btn = redownload_btn
        
        # 连接点击事件
        redownload_btn.clicked.connect(functools.partial(self._redownload_file, history_record))
    
    def _redownload_file(self, history_record):
        """重新下载文件"""
        # 获取下载URL
        url = history_record.get('url')
        if not url:
            QMessageBox.warning(self, i18n.get_text("error"), i18n.get_text("cannot_redownload_missing_url"))
            return
        
        # 创建下载请求参数
        download_params = {
            'url': url,
            'filename': history_record.get('filename'),
            # 可以添加其他需要的参数
        }
        
        # 这里需要查找主窗口并调用其开始下载方法
        # 由于HistoryWindow不直接知道主窗口，发送一个信号更合适
        self.history_item_clicked.emit(history_record)
    
    def _connect_completed_actions(self, row, history_record):
        """连接历史项的操作按钮"""
        if row not in self.history_items:
            return
            
        history_item = self.history_items[row]
        
        # 在这里保存历史记录信息，以便在点击时使用
        history_item.history_data = history_record
        history_item.row_index = row
        
        # 连接打开文件操作
        if hasattr(history_item, 'open_btn'):
            history_item.open_btn.clicked.connect(
                functools.partial(self._on_open_file_clicked, row)
            )
        
        # 连接打开文件夹操作
        if hasattr(history_item, 'folder_btn'):
            history_item.folder_btn.clicked.connect(
                functools.partial(self._on_open_folder_clicked, row)
            )
        
        # 连接删除记录操作
        if hasattr(history_item, 'delete_btn'):
            # 修改按钮文字为"删除记录"（只影响工具提示）
            history_item.delete_btn.setToolTip(i18n.get_text("delete_record"))
                    
            history_item.delete_btn.clicked.connect(
                functools.partial(self._on_delete_record_clicked, row)
            )
    
    def _on_open_file_clicked(self, row):
        """打开文件按钮点击处理"""
        if row in self.history_items:
            history_item = self.history_items[row]
            if hasattr(history_item, 'history_data'):
                file_path = history_item.history_data.get('save_path')
                print(f"{i18n.get_text('trying_open_file')}: {file_path}")
                self.open_file(file_path)
    
    def _on_open_folder_clicked(self, row):
        """打开文件夹按钮点击处理"""
        if row in self.history_items:
            history_item = self.history_items[row]
            if hasattr(history_item, 'history_data'):
                file_path = history_item.history_data.get('save_path', '')
                
                # 确保路径格式正确
                file_path = os.path.normpath(file_path)
                folder_path = os.path.dirname(file_path)
                
                print(f"{i18n.get_text('trying_open_folder')}: {folder_path}, {i18n.get_text('file_path')}: {file_path}")
                
                # 判断是否是Windows系统，如果是则选中文件
                import sys
                if sys.platform == 'win32':
                    # 检查文件是否存在
                    if os.path.exists(file_path):
                        import subprocess
                        try:
                            # 确保路径使用双引号包裹，防止空格问题，使用反斜杠分隔
                            # explorer命令对参数格式很敏感
                            file_path = file_path.replace('/', '\\')
                            cmd = f'explorer /select,"{file_path}"'
                            print(f"{i18n.get_text('executing_command')}: {cmd}")
                            subprocess.run(cmd, shell=True)
                        except Exception as e:
                            print(f"{i18n.get_text('select_file_failed')}: {str(e)}")
                            # 如果选中文件失败，回退到打开文件夹
                            os.startfile(folder_path)
                    else:
                        # 如果文件不存在，只打开文件夹
                        print(f"{i18n.get_text('file_not_exist_open_folder')}: {folder_path}")
                        if os.path.exists(folder_path):
                            os.startfile(folder_path)
                        else:
                            QMessageBox.warning(self, i18n.get_text("error"), f"{i18n.get_text('folder_not_exist')}: {folder_path}")
                elif sys.platform == 'darwin':  # macOS
                    if os.path.exists(file_path):
                        subprocess.call(['open', '-R', file_path])
                    else:
                        subprocess.call(['open', folder_path])
                else:  # Linux
                    try:
                        # 尝试使用xdg-open打开文件夹
                        subprocess.call(['xdg-open', folder_path])
                    except:
                        # 如果失败，尝试其他方法
                        try:
                            # 尝试nautilus选中文件
                            if os.path.exists('/usr/bin/nautilus') and os.path.exists(file_path):
                                subprocess.call(['nautilus', file_path])
                            else:
                                subprocess.call(['xdg-open', folder_path])
                        except:
                            QMessageBox.warning(self, i18n.get_text("error"), i18n.get_text("cannot_open_folder"))
    
    def _on_delete_record_clicked(self, row):
        """删除记录按钮点击处理"""
        if row in self.history_items:
            history_item = self.history_items[row]
            if hasattr(history_item, 'history_data'):
                print(f"{i18n.get_text('trying_delete_record')}: {row}")
                self.delete_history_record(row, history_item.history_data)
    
    def open_file(self, file_path):
        """打开下载的文件"""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, i18n.get_text("error"), f"{i18n.get_text('file_not_exist')}: {file_path}")
            return
            
        try:
            # 使用系统默认程序打开文件
            import subprocess
            import sys
            
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])
                
            print(f"{i18n.get_text('file_opened')}: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, i18n.get_text("error"), f"{i18n.get_text('cannot_open_file')}: {str(e)}")
    
    def delete_history_record(self, row, history_record):
        """删除历史记录"""
        filename = history_record.get('filename', i18n.get_text("unknown_file"))
        save_path = history_record.get('save_path', '')
        
        reply = QMessageBox.question(
            self, 
            i18n.get_text("confirm_delete"), 
            i18n.get_text("delete_record_confirm").format(filename=filename),
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从历史记录管理器中删除记录
            result = self.history_manager.remove_record(filename, save_path)
            
            if result:
                # 从界面移除历史项
                if row in self.history_items:
                    history_item = self.history_items[row]
                    history_item.setParent(None)
                    self.history_container_layout.removeWidget(history_item)
                    del self.history_items[row]
                    
                    # 如果没有历史记录了，显示空历史提示
                    if not self.history_items:
                        self._show_empty_history_message()
                    
                # 显示简洁的通知
                try:
                    NotifyManager.success(i18n.get_text("record_deleted"))
                except Exception as e:
                    print(f"{i18n.get_text('show_notify_failed')}: {e}")
                
                QMessageBox.information(self, i18n.get_text("success"), i18n.get_text("record_deleted_msg").format(filename=filename))
            else:
                try:
                    NotifyManager.error(i18n.get_text("delete_record_failed"))
                except Exception as e:
                    print(f"{i18n.get_text('show_notify_failed')}: {e}")
                    
                QMessageBox.warning(self, i18n.get_text("error"), i18n.get_text("delete_record_failed"))
