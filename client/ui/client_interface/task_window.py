from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QSizePolicy, QFrame, QScrollArea)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QThread
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap
from PySide6.QtCore import QFileInfo
from PySide6.QtWidgets import QFileIconProvider

import os
import urllib.parse

from client.ui.components.progressBar import ProgressBar
from core.font.font_manager import FontManager
from client.ui.components.download_log_dialog import DownloadLogDialog
from client.ui.client_interface.utils.file_icons_get import FileIconGetter

class RoundedTaskFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roundedTaskFrame")
        self.setStyleSheet("""
            #roundedTaskFrame {
                background-color: #171717;
                border-radius: 15px;
                padding: 10px;
            }
        """)

class TaskItemWidget(QFrame):
    """单个下载任务项组件"""
    def __init__(self, parent=None, row_index=0):
        super().__init__(parent)
        self.row_index = row_index
        self.font_manager = FontManager()
        
        # 创建文件图标管理器
        self.file_icon_getter = FileIconGetter()
        
        # 文件类型和图标的映射
        self.file_type_icons = {
            # 文档类型
            'pdf': "ic_fluent_document_pdf_24_regular",
            'doc': "ic_fluent_document_text_24_regular",
            'docx': "ic_fluent_document_text_24_regular",
            'txt': "ic_fluent_document_text_24_regular",
            'odt': "ic_fluent_document_text_24_regular",
            # 图片类型
            'jpg': "ic_fluent_image_24_regular",
            'jpeg': "ic_fluent_image_24_regular",
            'png': "ic_fluent_image_24_regular",
            'gif': "ic_fluent_image_24_regular",
            'svg': "ic_fluent_image_24_regular",
            'webp': "ic_fluent_image_24_regular",
            # 视频类型
            'mp4': "ic_fluent_video_24_regular",
            'mov': "ic_fluent_video_24_regular",
            'avi': "ic_fluent_video_24_regular",
            'mkv': "ic_fluent_video_24_regular",
            'webm': "ic_fluent_video_24_regular",
            # 音频类型
            'mp3': "ic_fluent_music_note_24_regular",
            'wav': "ic_fluent_music_note_24_regular",
            'ogg': "ic_fluent_music_note_24_regular",
            'flac': "ic_fluent_music_note_24_regular",
            'm4a': "ic_fluent_music_note_24_regular",
            # 压缩文件
            'zip': "ic_fluent_archive_24_regular",
            'rar': "ic_fluent_archive_24_regular",
            '7z': "ic_fluent_archive_24_regular",
            'tar': "ic_fluent_archive_24_regular",
            'gz': "ic_fluent_archive_24_regular",
            # 可执行文件 - 为exe文件提供多个备选图标名称
            'exe': ["app", "fluent_app_24_filled", "fluent_app_24_regular", "ic_fluent_app_24_regular", "windows_logo"],
            'msi': ["app", "fluent_app_24_filled", "fluent_app_24_regular", "ic_fluent_app_24_regular", "windows_logo"],
            'apk': ["android", "phone", "fluent_phone_24_filled", "ic_fluent_phone_24_regular", "apps"],
            # 代码文件
            'py': "ic_fluent_code_24_regular",
            'js': "ic_fluent_code_24_regular",
            'html': "ic_fluent_code_24_regular",
            'css': "ic_fluent_code_24_regular",
            'json': "ic_fluent_code_24_regular",
            'xml': "ic_fluent_code_24_regular",
            'java': "ic_fluent_code_24_regular",
            'cpp': "ic_fluent_code_24_regular",
            'c': "ic_fluent_code_24_regular",
        }
        
        # 文件类型对应颜色
        self.file_type_colors = {
            # 图片 - 紫色
            'jpg': "#B39DDB", 'jpeg': "#B39DDB", 'png': "#B39DDB", 
            'gif': "#B39DDB", 'svg': "#B39DDB", 'webp': "#B39DDB",
            # 视频 - 红色
            'mp4': "#FF7043", 'mov': "#FF7043", 'avi': "#FF7043", 
            'mkv': "#FF7043", 'webm': "#FF7043",
            # 音频 - 绿色
            'mp3': "#66BB6A", 'wav': "#66BB6A", 'ogg': "#66BB6A", 
            'flac': "#66BB6A", 'm4a': "#66BB6A",
            # 压缩包 - 黄色
            'zip': "#FFCA28", 'rar': "#FFCA28", '7z': "#FFCA28", 
            'tar': "#FFCA28", 'gz': "#FFCA28",
            # 可执行文件 - 橙色
            'exe': "#FF9800", 'msi': "#FF9800",
            # 安卓应用 - 绿色
            'apk': "#7CB342",
            # 文档 - 蓝色
            'pdf': "#42A5F5", 'doc': "#42A5F5", 'docx': "#42A5F5", 
            'txt': "#42A5F5", 'odt': "#42A5F5",
            # 代码 - 青色
            'py': "#26C6DA", 'js': "#26C6DA", 'html': "#26C6DA", 
            'css': "#26C6DA", 'json': "#26C6DA", 'xml': "#26C6DA", 
            'java': "#26C6DA", 'cpp': "#26C6DA", 'c': "#26C6DA",
            # 默认 - 浅蓝色
            'default': "#4285F4"
        }
        
        # 设置基本样式
        self.setStyleSheet("""
            TaskItemWidget {
                background-color: #1A1A1A;
                border-radius: 5px;
                margin: 3px 0px;
            }
        """)
        
        # 设置固定最大高度，防止卡片过高
        self.setMaximumHeight(120)
        
        # 创建布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)  # 减少上下间距
        main_layout.setSpacing(10)
        
        # 图标区域 - 完全重写
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(50, 50)  # 减小图标尺寸
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # 设置默认图标样式
        self.icon_label.setStyleSheet("""
            QLabel {
                background-color: #2A2A2A;
                color: #4285F4;
                border-radius: 15px;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.icon_label.setText("?")
        
        main_layout.addWidget(self.icon_label)
        
        # 文件信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)  # 减少间距
        
        # 文件名
        self.filename_label = QLabel("准备中...")
        self.filename_label.setStyleSheet("color: #FFFFFF; font-size: 14px;")
        # 设置文本省略模式 - 在中间使用省略号
        self.filename_label.setTextFormat(Qt.PlainText)
        self.filename_label.setWordWrap(False)
        self.filename_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 设置最大宽度和省略模式
        self.original_filename = ""  # 存储原始文件名，用于工具提示
        info_layout.addWidget(self.filename_label)
        
        # 文件大小和下载速度
        size_speed_layout = QHBoxLayout()
        size_speed_layout.setSpacing(15)
        size_speed_layout.setContentsMargins(0, 0, 0, 0)  # 减少间距
        
        # 文件大小标签 - 添加图标
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(5)
        
        # 文件大小图标
        size_icon = QLabel()
        icon_font = self.font_manager.create_icon_font(12)  # 缩小图标
        size_icon.setFont(icon_font)
        size_icon.setText(self.font_manager.get_icon_text("ic_fluent_data_usage_24_regular"))  # 数据使用图标
        size_icon.setStyleSheet("color: #9E9E9E;")
        size_layout.addWidget(size_icon)
        
        # 文件大小文字
        self.size_label = QLabel("文件大小:")
        self.size_label.setStyleSheet("color: #9E9E9E; font-size: 11px;")  # 缩小字体
        size_layout.addWidget(self.size_label)
        
        size_speed_layout.addWidget(size_widget)
        
        # 下载速度标签 - 添加图标
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(5)
        
        # 下载速度图标
        speed_icon = QLabel()
        speed_icon.setFont(icon_font)
        speed_icon.setText(self.font_manager.get_icon_text("ic_fluent_arrow_download_24_regular"))  # 下载图标
        speed_icon.setStyleSheet("color: #9E9E9E;")
        speed_layout.addWidget(speed_icon)
        
        # 下载速度文字
        self.speed_label = QLabel("下载速度: N/A")
        self.speed_label.setStyleSheet("color: #9E9E9E; font-size: 11px;")  # 缩小字体
        speed_layout.addWidget(self.speed_label)
        
        size_speed_layout.addWidget(speed_widget)
        
        size_speed_layout.addStretch()
        info_layout.addLayout(size_speed_layout)
        
        # 进度条区域
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(2)  # 减少间距
        progress_layout.setContentsMargins(0, 0, 0, 0)  # 减少间距
        
        # 进度标签和总进度百分比在同一行
        progress_header_layout = QHBoxLayout()
        progress_header_layout.setSpacing(5)
        progress_header_layout.setContentsMargins(0, 0, 0, 0)  # 减少间距
        
        # 使用Material Icons作为进度标签
        self.progress_label = QLabel()
        # 使用混合字体样式，可以同时显示图标和文字
        self.progress_label.setStyleSheet("color: #9E9E9E; font-size: 11px;")  # 缩小字体
        self.progress_label.setMinimumWidth(120)  # 设置最小宽度以适应"下载完成"文字
        
        # 为progress_label设置图标字体
        icon_font = self.font_manager.create_icon_font(14)  # 缩小图标
        self.progress_label.setFont(icon_font)
        self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_download_24_regular"))  # 使用普通下载图标代替找不到的circle版本
        
        progress_header_layout.addWidget(self.progress_label)
        
        progress_header_layout.addStretch()
        
        # 总进度百分比标签
        self.total_progress_label = QLabel("进度")
        self.total_progress_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")  # 缩小字体
        self.total_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_header_layout.addWidget(self.total_progress_label)
        
        # 添加进度头部布局
        progress_layout.addLayout(progress_header_layout)
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.font_manager.apply_font(self.progress_bar)
        self.progress_bar.setFixedHeight(12)  # 减小高度
        self.progress_bar.setIdmStyle(True)
        self.progress_bar.setShowSegments(True)
        self.progress_bar.setProgress(0)
        progress_layout.addWidget(self.progress_bar)
        
        # 进度条下方增加错误信息标签
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #FF5252; font-size: 10px; padding-left: 2px;")  # 缩小字体
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self.error_label.setMaximumHeight(20)  # 限制错误信息高度
        progress_layout.addWidget(self.error_label)
        
        info_layout.addLayout(progress_layout)
        main_layout.addLayout(info_layout, 1)
        
        # 操作按钮区域
        self.action_widget = QWidget()
        self.action_layout = QHBoxLayout(self.action_widget)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(5)
        self.action_layout.addStretch()  # 确保按钮靠右对齐
        
        # 添加操作区域
        main_layout.addWidget(self.action_widget)
    
    def update_filename(self, filename):
        """更新文件名"""
        if filename:
            # 存储原始/解码后的完整文件名
            self.original_filename = filename
            # 尝试进行URL解码，处理中文文件名
            try:
                decoded_filename = urllib.parse.unquote(filename)
                print(f"解码文件名: {filename} -> {decoded_filename}")
                self.original_filename = decoded_filename  # 存储解码后的文件名
                # 设置文件名和工具提示
                self.filename_label.setToolTip(decoded_filename)  # 鼠标悬停时显示完整文件名
                
                # 使用自定义方法显示文件名
                displayed_text = self.get_formatted_filename(decoded_filename)
                self.filename_label.setText(displayed_text)
                
                # 更新文件图标，使用解码后的文件名
                self.update_file_icon(decoded_filename)
            except Exception as e:
                print(f"文件名解码失败: {e}, 使用原始文件名")
                self.filename_label.setToolTip(filename)  # 鼠标悬停时显示完整文件名
                
                # 使用自定义方法显示文件名
                displayed_text = self.get_formatted_filename(filename)
                self.filename_label.setText(displayed_text)
                
                self.update_file_icon(filename)
    
    def get_formatted_filename(self, filename):
        """自定义文件名格式化显示方法，处理长文件名"""
        # 获取文件扩展名
        name, ext = os.path.splitext(filename)
        
        # 计算可显示的最大宽度
        metrics = self.filename_label.fontMetrics()
        available_width = self.width() - 150
        if available_width < 100:
            available_width = 100
            
        # 如果文件名很长，使用自定义的省略方式
        if metrics.horizontalAdvance(filename) > available_width:
            # 计算文件名和扩展名各自可用的字符数
            name_len = len(name)
            
            if name_len > 30:  # 如果名称部分超过30个字符
                # 取文件名的前10个字符和后8个字符，中间用...连接
                prefix = name[:10]
                suffix = name[-8:]
                formatted_name = f"{prefix}...{suffix}{ext}"
                
                # 如果还是太长，进一步缩短
                if metrics.horizontalAdvance(formatted_name) > available_width:
                    prefix = name[:8]
                    suffix = name[-6:]
                    formatted_name = f"{prefix}...{suffix}{ext}"
                    
                    # 如果依然太长，再缩短
                    if metrics.horizontalAdvance(formatted_name) > available_width:
                        prefix = name[:6]
                        suffix = name[-4:]
                        formatted_name = f"{prefix}...{suffix}{ext}"
            else:
                # 使用Qt的省略功能
                formatted_name = metrics.elidedText(filename, Qt.ElideMiddle, available_width)
                
            return formatted_name
        else:
            return filename  # 如果文件名不长，直接返回
    
    def update_file_icon(self, filename):
        """根据文件名更新文件图标"""
        print(f"正在更新文件图标: {filename}")
        if not filename or filename == "准备中...":
            return
            
        # 获取文件扩展名
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip('.')
        print(f"文件扩展名: {ext}")
        
        # 检查是否有完整的文件路径
        save_path = None
        try:
            # 尝试从父窗口获取保存路径
            parent_widget = self.parent()
            while parent_widget:
                if hasattr(parent_widget, 'get_task_save_path'):
                    save_path = parent_widget.get_task_save_path(self.row_index)
                    break
                parent_widget = parent_widget.parent()
                
            if save_path and os.path.exists(save_path):
                print(f"使用完整的文件路径: {save_path}")
            else:
                # 尝试构造可能的保存路径(用于测试)
                default_download_dirs = [
                    os.path.join(os.path.expanduser("~"), "Downloads"),
                    os.path.join(os.path.expanduser("~"), "Desktop"),
                    os.path.join(os.path.expanduser("~"), "Documents")
                ]
                
                for download_dir in default_download_dirs:
                    potential_path = os.path.join(download_dir, filename)
                    if os.path.exists(potential_path):
                        save_path = potential_path
                        print(f"找到文件路径: {save_path}")
                        break
        except Exception as e:
            print(f"获取保存路径失败: {e}")
            save_path = None
        
        try:
            # 清除之前的任何图标或图片
            self.icon_label.clear()
            
            # 尝试获取系统图标
            icon = None
            if save_path:
                # 如果有完整文件路径，优先使用
                icon = self.file_icon_getter.get_file_icon(file_path=save_path, file_ext=ext)
            else:
                # 否则只使用扩展名
                icon = self.file_icon_getter.get_file_icon(file_ext=ext)
            
            if icon and not icon.isNull():
                # 使用系统图标
                pixmap = icon.pixmap(48, 48)
                if not pixmap.isNull():
                    self.icon_label.setPixmap(pixmap)
                    print(f"使用系统图标成功")
                else:
                    raise ValueError("系统图标无效")
            else:
                # 使用emoji作为替代
                emoji = self.file_icon_getter.get_file_emoji(filename)
                color = self.file_icon_getter.get_file_color(filename)
                
                if emoji != '📄':  # 如果不是默认emoji
                    # 创建带有emoji的图标
                    try:
                        pixmap = self.file_icon_getter.create_pixmap_with_emoji(emoji, 48, color)
                        if not pixmap.isNull():
                            self.icon_label.setPixmap(pixmap)
                            print(f"使用emoji图标: {emoji}")
                        else:
                            raise ValueError("Emoji图标创建失败")
                    except Exception as e:
                        print(f"Emoji图标创建失败: {e}")
                        # 回退到文本
                        raise ValueError("Emoji图标创建失败")
                else:
                    raise ValueError("无适用Emoji")
        except Exception as e:
            print(f"图标设置出错，使用文本替代: {e}")
            # 使用文本替代
            try:
                placeholder = self.file_icon_getter.get_icon_placeholder(filename)
                style = self.file_icon_getter.get_icon_label_style(filename)
                self.icon_label.setText(placeholder)
                self.icon_label.setStyleSheet(style)
                print(f"使用文本图标: {placeholder}")
            except Exception as e2:
                print(f"文本图标也设置失败: {e2}")
                # 最终后备方案
                self.icon_label.setText("?")
                self.icon_label.setStyleSheet("background-color: #333333; color: white; border-radius: 15px;")
        
        # 确保更新
        self.icon_label.update()
    
    def update_size(self, size):
        """更新文件大小"""
        if isinstance(size, (int, float)):
            size_text = self.get_readable_size(size)
            self.size_label.setText(f"文件大小: {size_text}")
        elif isinstance(size, str):
            self.size_label.setText(f"文件大小: {size}")
    
    def update_speed(self, speed_bytes):
        """更新下载速度"""
        speed_text = self.get_readable_size(speed_bytes) + "/s"
        self.speed_label.setText(f"下载速度: {speed_text}")
    
    def update_progress(self, progress_data, file_size=0):
        """更新进度条"""
        if not progress_data and isinstance(file_size, (int, float)) and file_size > 0:
            # 可能是进度百分比
            percentage = int((file_size / 100) * 100)
            self.progress_bar.setProgress(percentage)
            self.progress_bar.setSegments([(0, percentage, "#1FB15F")])
            self.progress_bar.setShowSegments(True)
            self.total_progress_label.setText(f"总进度: {percentage}%")
            return
            
        if file_size > 0 and progress_data:
            # 使用分段功能
            self.progress_bar.updateFromDownloadSegments(progress_data, file_size)
            
            # 计算总进度
            total_progress = 0
            total_size = 0
            total_downloaded = 0
            
            try:
                if isinstance(progress_data[0], dict):
                    # 遍历所有分块计算进度
                    for segment in progress_data:
                        # 兼容新旧字段名
                        start_pos = segment.get('start_position', segment.get('start_pos', segment.get('startPos', 0)))
                        end_pos = segment.get('end_position', segment.get('end_pos', segment.get('endPos', 0)))
                        current = segment.get('current_position', segment.get('progress', start_pos))
                        
                        # 确保值有效
                        start_pos = max(0, start_pos)
                        end_pos = max(start_pos, end_pos)
                        current = max(start_pos, min(end_pos, current))
                        
                        # 计算当前块的下载量和总大小
                        current_downloaded = current - start_pos
                        segment_size = end_pos - start_pos + 1
                        
                        # 累加总下载量和总大小
                        total_downloaded += current_downloaded
                        total_size += segment_size
                        
                    # 防止除零错误
                    if total_size > 0:
                        # 计算进度百分比，四舍五入到整数
                        total_progress_float = (total_downloaded / total_size) * 100
                        total_progress = int(total_progress_float)
                        
                        # 防止因舍入或浮点误差导致显示100%
                        # 只有真正结束才显示100%
                        if total_progress_float >= 99.5 and total_downloaded < total_size:
                            total_progress = 99
                            
                elif isinstance(progress_data[0], (list, tuple)) and len(progress_data[0]) >= 3:
                    # 处理旧格式 [start, current, end]
                    for segment in progress_data:
                        start_pos = segment[0]
                        current = segment[1]
                        end_pos = segment[2]
                        
                        # 确保值有效
                        start_pos = max(0, start_pos)
                        end_pos = max(start_pos, end_pos)
                        current = max(start_pos, min(end_pos, current))
                        
                        # 计算当前块的下载量和总大小
                        current_downloaded = current - start_pos
                        segment_size = end_pos - start_pos + 1
                        
                        # 累加总下载量和总大小
                        total_downloaded += current_downloaded
                        total_size += segment_size
                        
                    # 防止除零错误
                    if total_size > 0:
                        # 计算进度百分比，四舍五入到整数
                        total_progress_float = (total_downloaded / total_size) * 100
                        total_progress = int(total_progress_float)
                        
                        # 防止因舍入或浮点误差导致显示100%
                        # 只有真正结束才显示100%
                        if total_progress_float >= 99.5 and total_downloaded < total_size:
                            total_progress = 99

                # 设置进度标签
                self.total_progress_label.setText(f"进度: {total_progress}%")
                
                # 打印调试信息
                print(f"进度更新: 已下载={total_downloaded}, 总大小={total_size}, 进度={total_progress}%")

            except Exception as e:
                print(f"计算进度错误: {e}")
                import traceback
                traceback.print_exc()
    
    def update_status(self, status_text, is_complete=False, error_info=None):
        """更新任务状态"""
        # 隐藏错误信息标签
        self.error_label.setVisible(False)
        
        if "下载中" in status_text and "%" in status_text:
            try:
                percent = int(status_text.split(":")[1].strip().replace("%", ""))
                self.total_progress_label.setText(f"进度: {percent}%")
                # 设置下载中图标为蓝色
                self.progress_label.setStyleSheet("color: #3478F6; font-size: 11px;")
                self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_download_24_regular"))  # 下载图标
            except:
                self.total_progress_label.setText(status_text)
        elif is_complete:
            # 强制设置进度文本为100%
            self.total_progress_label.setText("进度: 100%")
            # 创建完成图标+文字的混合显示
            try:
                # 先尝试设置字体以显示图标
                icon_font = self.font_manager.create_icon_font(14)  # 缩小图标
                self.progress_label.setFont(icon_font)
                
                # 设置图标和文字
                self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_checkmark_circle_24_regular") + " 下载完成")  # 勾选圆圈图标
                self.progress_label.setStyleSheet("color: #1FB15F; font-size: 11px;")  # 缩小字体
            except Exception as e:
                print(f"设置完成图标出错: {e}")
                # 如果出错，至少显示文字
                self.progress_label.setText("下载完成")
                self.progress_label.setStyleSheet("color: #1FB15F; font-size: 11px;")  # 缩小字体
            
            # 强制设置进度条为100%
            self.progress_bar.setProgress(100)
            self.progress_bar.setSegments([(0, 100, "#1FB15F")])
            
            # 添加完成操作按钮
            self.add_completed_actions()
            
            # 打印确认信息
            print(f"已标记任务为完成状态，添加了操作按钮")
        elif "暂停" in status_text:
            # 设置暂停图标为黄色
            self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_pause_circle_24_regular"))  # 暂停图标
            self.progress_label.setStyleSheet("color: #FFC107; font-size: 11px;")  # 缩小字体
        elif "取消" in status_text or "错误" in status_text or error_info:
            # 设置错误图标为红色
            self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_error_circle_24_regular"))  # 错误图标
            self.progress_label.setStyleSheet("color: #FF3B30; font-size: 11px;")  # 缩小字体
            
            # 显示错误信息（如果提供）
            if error_info:
                # 简化错误信息
                simplified_error = self.simplify_error_message(error_info)
                self.error_label.setText(simplified_error)
                self.error_label.setVisible(True)
                
                # 将图标更新为文件图标
                self.icon_label.setText(self.font_manager.get_icon_text("ic_fluent_document_error_24_regular"))
                self.icon_label.setStyleSheet("color: #FF3B30; background-color: #2A2A2A; border-radius: 15px; font-size: 24px;")
    
    def add_completed_actions(self):
        """添加完成后的操作按钮"""
        # 清空现有布局
        for i in reversed(range(self.action_layout.count())): 
            item = self.action_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # 更新进度标签为"已完成"图标+文字
        try:
            # 先尝试设置字体以显示图标
            icon_font = self.font_manager.create_icon_font(14)  # 缩小图标
            self.progress_label.setFont(icon_font)
            
            # 设置图标和文字
            self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_checkmark_circle_24_regular") + " 下载完成")  # 勾选圆圈图标
            self.progress_label.setStyleSheet("color: #1FB15F; font-size: 11px;")  # 缩小字体
        except Exception as e:
            print(f"设置完成图标出错: {e}")
            # 如果出错，至少显示文字
            self.progress_label.setText("下载完成")
            self.progress_label.setStyleSheet("color: #1FB15F; font-size: 11px;")  # 缩小字体
            
        self.total_progress_label.setText("进度: 100%")
        
        # 如果文件名已经设置，确保图标也已更新
        if hasattr(self, 'filename_label') and self.filename_label.text() != "准备中...":
            self.update_file_icon(self.filename_label.text())
        
        # 创建操作按钮 - 使用QPushButton
        # 打开文件按钮
        open_btn = QPushButton()
        open_btn.setFont(icon_font)
        open_btn.setText(self.font_manager.get_icon_text("ic_fluent_document_arrow_right_24_regular"))
        open_btn.setToolTip("打开文件")
        open_btn.setFixedSize(30, 30)  # 减小按钮尺寸
        open_btn.setProperty("row", self.row_index)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        self.open_btn = open_btn
        
        # 删除按钮
        delete_btn = QPushButton()
        # 配置字体和图标
        delete_btn.setFont(icon_font)
        delete_btn.setText(self.font_manager.get_icon_text("ic_fluent_delete_24_regular"))
        delete_btn.setToolTip("删除")
        delete_btn.setFixedSize(30, 30)  # 减小按钮尺寸
        delete_btn.setProperty("row", self.row_index)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        self.delete_btn = delete_btn
        
        # 打开文件夹按钮
        folder_btn = QPushButton()
        # 配置字体和图标
        folder_btn.setFont(icon_font)
        folder_btn.setText(self.font_manager.get_icon_text("ic_fluent_folder_24_regular"))
        folder_btn.setToolTip("打开文件夹并选中文件")
        folder_btn.setFixedSize(30, 30)  # 减小按钮尺寸
        folder_btn.setProperty("row", self.row_index)
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        self.folder_btn = folder_btn
        
        # 添加按钮到布局
        self.action_layout.addWidget(open_btn)
        self.action_layout.addWidget(delete_btn)
        self.action_layout.addWidget(folder_btn)
    
    @staticmethod
    def get_readable_size(size_in_bytes):
        """将字节数转换为可读的大小表示"""
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        if isinstance(size_in_bytes, (int, float)):
            while size_in_bytes >= 1024 and i < len(size_names) - 1:
                size_in_bytes /= 1024
                i += 1
            return f"{size_in_bytes:.2f} {size_names[i]}"
        return size_in_bytes  # 如果不是数字，返回原值

    def set_failed_status(self, error_message):
        """设置下载失败状态和显示错误信息"""
        # 设置错误图标
        icon_font = self.font_manager.create_icon_font(14)  # 缩小图标
        self.progress_label.setFont(icon_font)
        self.progress_label.setText(self.font_manager.get_icon_text("ic_fluent_error_circle_24_regular"))
        self.progress_label.setStyleSheet("color: #FF3B30; font-size: 11px;")  # 缩小字体
        
        # 设置错误文本
        self.total_progress_label.setText("下载失败")
        
        # 显示错误信息
        if error_message:
            # 简化错误信息，提取关键部分
            simplified_error = TaskItemWidget.simplify_error_message(error_message)
            self.error_label.setText(simplified_error)
            self.error_label.setVisible(True)
        
        # 将进度条设置为红色
        # 由于ProgressBar没有getProgress方法，我们使用固定值表示失败
        current_progress = 5  # 确保至少有一点颜色来表示失败
        self.progress_bar.setProgress(current_progress)
        self.progress_bar.setSegments([(0, current_progress, "#FF3B30")])
        
        # 修改文件图标为错误文件图标
        self.icon_label.setText(self.font_manager.get_icon_text("ic_fluent_document_error_24_regular"))
        self.icon_label.setStyleSheet("color: #FF3B30; background-color: #2A2A2A; border-radius: 15px; font-size: 24px;")
    
    @staticmethod
    def simplify_error_message(error_message):
        """简化错误信息，提取关键部分"""
        if "certificate verify failed" in error_message:
            return "SSL证书验证失败"
        elif "Connection refused" in error_message:
            return "连接被拒绝"
        elif "Timeout" in error_message or "timeout" in error_message:
            return "连接超时"
        elif "SSLError" in error_message:
            return "SSL安全连接错误"
        elif "HTTPError" in error_message:
            # 提取HTTP错误码
            import re
            match = re.search(r"HTTP (\d+)", error_message)
            if match:
                return f"HTTP错误: {match.group(1)}"
            return "HTTP请求错误"
        elif "404" in error_message:
            return "文件不存在 (404)"
        elif "403" in error_message:
            return "无权限访问 (403)"
        elif "500" in error_message:
            return "服务器内部错误 (500)"
        elif "IndexError" in error_message:
            return "文件大小获取失败"
        elif "No space" in error_message:
            return "磁盘空间不足"
        elif "Permission denied" in error_message:
            return "没有写入权限"
        else:
            # 限制显示长度，更严格地限制错误信息长度
            if len(error_message) > 50:  # 减少最大长度
                return error_message[:47] + "..."
            return error_message

    def resizeEvent(self, event):
        """当窗口大小改变时更新文件名显示"""
        super().resizeEvent(event)
        if hasattr(self, 'original_filename') and self.original_filename:
            # 重新应用自定义的文件名显示方法
            displayed_text = self.get_formatted_filename(self.original_filename)
            self.filename_label.setText(displayed_text)

class TaskWindow(QWidget):
    taskPaused = Signal(int)  # 任务暂停信号
    taskResumed = Signal(int)  # 任务恢复信号
    taskCancelled = Signal(int)  # 任务取消信号
    taskCompleted = Signal(int, str)  # 任务完成信号，参数为任务ID和文件路径
    show_log_for_row = Signal(int)  # 显示日志信号
    
    def __init__(self, font_manager=None, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = font_manager if font_manager else FontManager()
        
        # 检查图标字体是否可用
        self.icon_font_available = self._check_icon_font()
        print(f"图标字体可用状态: {self.icon_font_available}")
        
        # 保存更新下载任务ID
        self.update_task_id = -1
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        
        # 标题和控制按钮
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(20, 10, 20, 10)
        self.header_layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("下载任务")
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.title_label)
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch(1)
        
        # 添加控制按钮
        self._setup_control_buttons()
        
        self.main_layout.addLayout(self.header_layout)
        
        # 下载任务列表区域
        self._setup_tasks_area()
        
        # 保存下载任务项的引用
        self.task_items = {}
    
    def _setup_control_buttons(self):
        control_button_style = """
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 5px 10px;
                min-width: 60px;
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
            icon_label = QLabel()
            icon_label.setFixedSize(30, 30)  # 缩小标签控件尺寸
            # 使用字体图标替代SVG
            self.font_manager.apply_icon_font(icon_label, 10)  # 调整字体图标大小，与控件尺寸匹配
            
            # 使用对应的Fluent图标代码
            if icon_name == "pause":
                icon_label.setText(self.font_manager.get_icon_text("ic_fluent_pause_24_regular"))
            elif icon_name == "play":
                icon_label.setText(self.font_manager.get_icon_text("ic_fluent_play_24_regular"))
            elif icon_name == "cancel":
                icon_label.setText(self.font_manager.get_icon_text("ic_fluent_dismiss_circle_24_regular"))
            
            icon_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(text_label)
            
            return btn
        
        # 暂停按钮 - 使用SVG图标
        self.pause_btn = create_control_button("暂停", "pause")
        self.pause_btn.clicked.connect(self.pause_selected_tasks)
        
        # 恢复按钮 - 使用SVG图标
        self.resume_btn = create_control_button("恢复", "play")
        self.resume_btn.clicked.connect(self.resume_selected_tasks)
        
        # 取消按钮 - 使用SVG图标
        self.cancel_btn = create_control_button("取消", "cancel")
        self.cancel_btn.clicked.connect(self.cancel_selected_tasks)
        
        # 添加按钮到布局
        self.header_layout.addWidget(self.pause_btn)
        self.header_layout.addWidget(self.resume_btn)
        self.header_layout.addWidget(self.cancel_btn)
    
    def _setup_tasks_area(self):
        # 下载任务列表区域
        self.tasks_frame = RoundedTaskFrame()
        self.tasks_layout = QVBoxLayout(self.tasks_frame)
        self.tasks_layout.setContentsMargins(15, 15, 15, 15)
        self.tasks_layout.setSpacing(8)
        
        # 使用滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建一个容器widget来包含所有下载项
        self.tasks_container = QWidget()
        self.tasks_container.setStyleSheet("background-color: transparent;")
        self.tasks_container_layout = QVBoxLayout(self.tasks_container)
        self.tasks_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_container_layout.setSpacing(8)
        self.tasks_container_layout.addStretch()  # 添加弹性空间让任务项靠上显示
        
        self.scroll_area.setWidget(self.tasks_container)
        self.tasks_layout.addWidget(self.scroll_area)
        
        self.main_layout.addWidget(self.tasks_frame)
    
    def _check_icon_font(self):
        """检查图标字体是否可用"""
        try:
            # 尝试获取一个图标
            test_icon = self.font_manager.get_icon_text("ic_fluent_document_24_regular")
            # 如果返回的不是空字符串，则认为图标字体可用
            return bool(test_icon)
        except Exception as e:
            print(f"检查图标字体出错: {e}")
            return False
    
    def add_download_task(self, filename="准备中...", size="获取中..."):
        """添加新的下载任务项"""
        print(f"\n======== TaskWindow.add_download_task调用开始 ========")
        print(f"当前线程: {QThread.currentThread().objectName()}")
        print(f"当前对象ID: {id(self)}")
        print(f"调用add_download_task: filename={filename}, size={size}")
        
        # 检查当前对象是否有效
        try:
            print(f"对象类型: {type(self).__name__}")
            print(f"对象可见性: {self.isVisible()}")
            print(f"对象父级: {self.parent()}")
        except Exception as e:
            print(f"检查对象信息失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # 确保task_items已初始化
        if not hasattr(self, 'task_items'):
            print(f"严重问题: task_items属性不存在，正在创建...")
            self.task_items = {}
        elif self.task_items is None:
            print(f"严重问题: task_items为None，正在重新初始化...")
            self.task_items = {}
        else:
            print(f"task_items状态正常: 类型={type(self.task_items)}, 元素数={len(self.task_items)}")
            
        # 检查任务容器
        container_problems = []
        
        if not hasattr(self, 'tasks_container'):
            container_problems.append("tasks_container属性不存在")
        elif self.tasks_container is None:
            container_problems.append("tasks_container为None")
        else:
            print(f"tasks_container状态: 类型={type(self.tasks_container)}, 可见={self.tasks_container.isVisible()}")
        
        if not hasattr(self, 'tasks_container_layout'):
            container_problems.append("tasks_container_layout属性不存在")
        elif self.tasks_container_layout is None:
            container_problems.append("tasks_container_layout为None")
        else:
            print(f"tasks_container_layout状态: 类型={type(self.tasks_container_layout)}, 项目数={self.tasks_container_layout.count()}")
        
        if container_problems:
            print(f"严重错误: {', '.join(container_problems)}")
            print(f"尝试重新创建容器...")
            try:
                # 这里不实际重建，只记录问题
                print(f"需要重建容器，但这里只记录问题")
            except Exception as e:
                print(f"重建容器失败: {str(e)}")
                print(f"======== TaskWindow.add_download_task调用失败 ========\n")
                return -1
        
        # 获取当前行数作为新任务的索引
        row_position = len(self.task_items)
        print(f"将使用行号: {row_position}")
        
        try:
            # 创建新的任务项组件
            print(f"开始创建TaskItemWidget...")
            if self.tasks_container is None:
                raise ValueError("tasks_container为None，无法创建TaskItemWidget")
                
            task_item = TaskItemWidget(parent=self.tasks_container, row_index=row_position)
            print(f"TaskItemWidget创建成功: {id(task_item)}")
            
            # 更新任务项信息
            print(f"更新任务项信息: filename={filename}, size={size}")
            task_item.update_filename(filename)
            task_item.update_size(size)
            
            # 添加到容器布局的顶部
            print(f"开始添加到容器布局...")
            if self.tasks_container_layout is None:
                raise ValueError("tasks_container_layout为None，无法添加任务项")
                
            self.tasks_container_layout.insertWidget(0, task_item)
            print(f"添加到容器布局成功")
            
            # 检查任务项可见性
            print(f"任务项可见性: {task_item.isVisible()}")
            print(f"容器可见性: {self.tasks_container.isVisible()}")
            print(f"滚动区域可见性: {hasattr(self, 'scroll_area') and self.scroll_area.isVisible()}")
            
            # 保存任务项引用
            self.task_items[row_position] = task_item
            print(f"保存任务项引用成功, 当前items数量: {len(self.task_items)}")
            
            # 确保布局更新
            print(f"强制更新布局...")
            self.tasks_container.update()
            if hasattr(self, 'scroll_area'):
                self.scroll_area.update()
            self.update()
            
            print(f"已添加任务: #{row_position}, 文件名: {filename}, 任务项总数: {len(self.task_items)}")
            print(f"======== TaskWindow.add_download_task调用成功 ========\n")
            return row_position
        except Exception as e:
            print(f"添加下载任务出错: {e}")
            import traceback
            traceback.print_exc()
            print(f"======== TaskWindow.add_download_task调用失败 ========\n")
            return -1

    # 添加一个方法别名，确保与add_task方法一致
    def add_task(self, task_data):
        """添加新的下载任务 (与add_download_task兼容的接口)
        
        Args:
            task_data: 包含任务信息的字典，至少需要包含：
                      file_name: 文件名
                      total_size: 文件大小
                      status: 状态
                    
        Returns:
            int: 任务行号
        """
        # 直接打印任务数据以便调试
        print(f"TaskWindow.add_task: 接收到任务数据 {task_data}")
        
        # 直接调用底层方法
        return self.add_download_task(
            filename=task_data.get("file_name", "准备中..."),
            size=task_data.get("total_size", "获取中...")
        )
        
    def update_file_info(self, row, filename=None, size=None):
        print(f"update_file_info: row={row}, filename={filename}, size={size}")
        if row not in self.task_items:
            return
        task_item = self.task_items[row]
        if filename is not None:
            task_item.update_filename(filename)
        if size is not None:
            task_item.update_size(size)
    
    def update_progress(self, row, progress_data, file_size=0):
        """更新进度条显示"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.update_progress(progress_data, file_size)
    
    def update_speed(self, row, speed_bytes):
        """更新下载速度显示"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.update_speed(speed_bytes)
    
    def update_status(self, row, status_text, is_complete=False, error_info=None):
        """更新任务状态
        
        Args:
            row: 任务行号
            status_text: 状态文本
            is_complete: 是否已完成
            error_info: 错误信息（可选）
        """
        if row not in self.task_items:
            print(f"未找到行 {row} 的任务项，无法更新状态")
            return
            
        task_item = self.task_items[row]
        task_item.update_status(status_text, is_complete, error_info)
        
        # 如果任务完成，添加完成操作按钮
        if is_complete:
            task_item.add_completed_actions()
            self._connect_completed_actions(row)
            
    # 添加方法别名
    def set_task_status(self, row, status_text, is_complete=False, error_info=None):
        """设置任务状态（update_status的别名）"""
        self.update_status(row, status_text, is_complete, error_info)
    
    def _connect_completed_actions(self, row):
        """连接完成后的操作按钮信号"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        
        if hasattr(task_item, 'open_btn'):
            # 使用lambda捕获当前的row值
            task_item.open_btn.clicked.connect(lambda checked=False, r=row: self.open_file(r))
        
        if hasattr(task_item, 'delete_btn'):
            # 使用lambda捕获当前的row值
            task_item.delete_btn.clicked.connect(lambda checked=False, r=row: self.delete_file(r))
        
        if hasattr(task_item, 'folder_btn'):
            # 使用lambda捕获当前的row值
            task_item.folder_btn.clicked.connect(lambda checked=False, r=row: self.open_folder(r))
            task_item.folder_btn.setToolTip("打开文件夹并选中文件")
    
    def _add_completed_actions(self, row):
        """为已完成的下载任务添加操作按钮"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.add_completed_actions()
        self._connect_completed_actions(row)
    
    def open_file(self, row=None):
        """打开下载的文件"""
        # 如果没有提供行号，尝试从发送者获取
        if row is None:
            sender = self.sender()
            if sender and hasattr(sender, 'property'):
                row = sender.property("row")
        
        if row is not None:
            print(f"打开文件：行 {row}")
            # 发射信号给主窗口处理
    
    def delete_file(self, row=None):
        """删除下载的文件"""
        # 如果没有提供行号，尝试从发送者获取
        if row is None:
            sender = self.sender()
            if sender and hasattr(sender, 'property'):
                row = sender.property("row")
                
        if row is not None:
            print(f"删除文件：行 {row}")
            # 发射信号给主窗口处理
    
    def open_folder(self, row=None):
        """打开文件所在文件夹并自动选中文件"""
        # 如果没有提供行号，尝试从发送者获取
        if row is None:
            sender = self.sender()
            if sender and hasattr(sender, 'property'):
                row = sender.property("row")
                
        if row is not None:
            print(f"打开文件夹：行 {row}")
            try:
                # 获取文件的实际绝对路径
                file_path = self.get_task_save_path(row)
                if not file_path:
                    print(f"无法获取文件路径，行号: {row}")
                    return
                    
                absolute_file_path = os.path.realpath(file_path)
                print(f"绝对路径: {absolute_file_path}")
                
                # 确保文件夹路径存在
                folder_path = os.path.dirname(absolute_file_path)
                if not os.path.exists(folder_path):
                    print(f"文件夹不存在: {folder_path}")
                    return
                
                # 打开文件夹并选中文件
                import sys
                import subprocess
                
                if sys.platform == 'win32':
                    # Windows下使用explorer /select命令选中文件
                    # 确保路径使用反斜杠并用双引号包裹
                    normalized_path = absolute_file_path.replace('/', '\\')
                    cmd = f'explorer /select,"{normalized_path}"'
                    print(f"执行命令: {cmd}")
                    subprocess.run(cmd, shell=True)
                elif sys.platform == 'darwin':  # macOS
                    # macOS下使用open -R命令选中文件
                    subprocess.call(['open', '-R', absolute_file_path])
                else:  # Linux
                    # Linux下不同的文件管理器有不同的方法，这里尝试几种常见的
                    try:
                        # 尝试使用xdg-open打开文件夹
                        subprocess.call(['xdg-open', folder_path])
                    except:
                        # 如果失败，尝试dbus方法或其他方法
                        try:
                            if os.path.exists('/usr/bin/nautilus'):
                                subprocess.call(['nautilus', absolute_file_path])
                            else:
                                subprocess.call(['xdg-open', folder_path])
                        except Exception as e:
                            print(f"打开文件夹失败: {e}")
            except Exception as e:
                print(f"打开文件夹出错: {e}")
                import traceback
                traceback.print_exc()
    
    def get_selected_rows(self):
        """获取当前选中的行索引"""
        # 这个实现需要修改，因为没有了表格
        # 这里简单返回一个空列表
        return []
    
    def pause_selected_tasks(self):
        """暂停选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskPaused.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已暂停")
    
    def resume_selected_tasks(self):
        """恢复选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskResumed.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已恢复")
    
    def cancel_selected_tasks(self):
        """取消选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskCancelled.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已取消")
    
    def show_download_log(self):
        """显示下载日志对话框"""
        # 获取发送信号的按钮
        sender = self.sender()
        if not sender or not hasattr(sender, 'property'):
            return
            
        # 获取行号
        row = sender.property("row")
        if row is None:
            return
            
        # 发送信号给主窗口处理
        self.show_log_for_row.emit(row)
    
    def show_log_for_row(self, row):
        """显示特定行的下载日志的回调函数，由主窗口连接"""
        pass  # 由主窗口连接实现

    def add_update_download_task(self, url, filename, file_size=None):
        """添加更新下载任务"""
        # 创建一个普通的下载任务
        task_id = self.add_download_task(filename, file_size or "获取中...")
        
        # 标记为更新任务
        self.update_task_id = task_id
        
        # 返回任务ID
        return task_id
    
    def handle_task_completion(self, task_id, file_path):
        """处理任务完成的回调"""
        # 更新UI
        if task_id in self.task_items:
            self.task_items[task_id].update_status("下载完成", True)
        
        # 发出任务完成信号
        self.taskCompleted.emit(task_id, file_path)
        
    def get_task_save_path(self, task_id):
        """获取任务保存路径，由下载引擎实现"""
        # 此处为示例，实际应返回真实的保存路径
        pass

    def create_icon_label(self, icon_name, color="#B39DDB"):
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text(icon_name))
        icon_label.setStyleSheet(f"color: {color}; margin: 0; padding: 0;")
        icon_label.setAlignment(Qt.AlignCenter)
        return icon_label

    def set_task_failed(self, row, error_message):
        """设置任务失败状态"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.set_failed_status(error_message)

    def add_history_task(self, history_item):
        """从历史记录添加一个任务项
        
        Args:
            history_item: 包含任务历史信息的字典，至少需要包含：
                          filename: 文件名
                          save_path: 保存路径
                          file_size: 文件大小
                          download_time: 下载完成时间
                          status: 状态（如'completed'）
        
        Returns:
            int: 任务行号
        """
        # 获取当前行数作为新任务的索引
        row_position = len(self.task_items)
        
        # 创建新的任务项组件
        task_item = TaskItemWidget(parent=self.tasks_container, row_index=row_position)
        
        # 更新任务项信息
        task_item.update_filename(history_item.get('filename', '未知文件'))
        task_item.update_size(history_item.get('file_size', 0))
        
        # 添加到容器布局的顶部
        self.tasks_container_layout.insertWidget(0, task_item)
        
        # 保存任务项引用
        self.task_items[row_position] = task_item
        
        # 设置为已完成状态
        if history_item.get('status') == 'completed':
            task_item.update_status("下载完成", True)
            task_item.add_completed_actions()
            self._connect_completed_actions(row_position)
        elif history_item.get('status') == 'error':
            task_item.set_failed_status(history_item.get('error_message', '下载失败'))
        
        print(f"已添加历史任务: #{row_position}, 文件名: {history_item.get('filename')}")
        return row_position
    
    def get_task_save_path(self, task_id):
        """
        获取任务保存路径
        :param task_id: 任务ID
        :return: 保存路径字符串或None
        """
        # 此方法将被下载引擎重写，此处提供一个基本实现供调试使用
        try:
            # 尝试从被管理的任务项中获取文件名
            if task_id in self.task_items:
                task_item = self.task_items[task_id]
                # 获取文件名
                if hasattr(task_item, 'original_filename') and task_item.original_filename:
                    filename = task_item.original_filename
                    # 构造默认下载路径，确保使用Windows风格的反斜杠
                    download_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
                    # 统一转换为系统适用的路径格式
                    download_path = os.path.normpath(download_path)
                    return download_path
        except Exception as e:
            print(f"获取任务路径失败: {e}")
        
        return None
    
    def clear_all_tasks(self):
        """清除所有任务项"""
        # 清除容器内的所有组件
        for row, task_item in list(self.task_items.items()):
            task_item.setParent(None)
            self.tasks_container_layout.removeWidget(task_item)
        
        # 清空任务项字典
        self.task_items.clear()
        
        print("已清除所有任务项")

class HistoryTaskWindow(TaskWindow):
    """历史记录任务窗口，不显示任务控制按钮"""
    
    # 添加刷新历史信号
    history_refresh_requested = Signal()
    
    def __init__(self, font_manager=None, parent=None):
        # 初始化父类但不调用_setup_control_buttons
        super(TaskWindow, self).__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = font_manager if font_manager else FontManager()
        
        # 检查图标字体是否可用
        self.icon_font_available = self._check_icon_font()
        print(f"图标字体可用状态: {self.icon_font_available}")
        
        # 保存更新下载任务ID
        self.update_task_id = -1
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        
        # 标题和控制按钮
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(20, 10, 20, 10)
        self.header_layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("下载历史")
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.title_label)
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch(1)
        
        # 添加历史页面的操作按钮
        self._setup_history_buttons()
        
        self.main_layout.addLayout(self.header_layout)
        
        # 下载任务列表区域
        self._setup_tasks_area()
        
        # 保存下载任务项的引用
        self.task_items = {}
        
    def _setup_history_buttons(self):
        """设置历史页面的操作按钮"""
        history_button_style = """
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 5px 10px;
                min-width: 60px;
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
        def create_history_button(text, icon_name):
            btn = QPushButton()
            btn.setStyleSheet(history_button_style)
            
            # 使用布局方式设置图标和文本
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(8, 0, 8, 0)
            btn_layout.setSpacing(5)
            
            # 创建图标标签
            icon_label = QLabel()
            icon_label.setFixedSize(12, 12)  # 缩小标签控件尺寸
            # 使用字体图标替代SVG
            self.font_manager.apply_icon_font(icon_label, 10)  # 调整字体图标大小，与控件尺寸匹配
            
            # 使用对应的Fluent图标代码
            if icon_name == "refresh":
                icon_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_sync_24_regular"))
            elif icon_name == "clear":
                icon_label.setText(self.font_manager.get_icon_text("ic_fluent_delete_24_regular"))
            
            icon_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(text_label)
            
            return btn
        
        # 刷新按钮
        self.refresh_btn = create_history_button("刷新", "refresh")
        self.refresh_btn.setToolTip("刷新历史记录")
        self.refresh_btn.clicked.connect(self.request_refresh)
        
        # 清空按钮
        self.clear_btn = create_history_button("清空", "clear")
        self.clear_btn.setToolTip("清空历史记录")
        
        # 添加按钮到布局
        self.header_layout.addWidget(self.refresh_btn)
        self.header_layout.addWidget(self.clear_btn)
    
    def request_refresh(self):
        """请求刷新历史记录"""
        print("请求刷新历史记录")
        # 发送刷新信号给主窗口
        self.history_refresh_requested.emit()
        
    def refresh_display(self):
        """刷新历史记录显示"""
        print("刷新历史记录显示")
        # 先清空所有任务项
        self.clear_all_tasks()
