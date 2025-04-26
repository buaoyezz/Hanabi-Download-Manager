from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, Property
from PySide6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from core.font.font_manager import FontManager

class ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)  # IDM风格的高度
        self._progress = 0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(200)  # 减少动画时间使其更流畅
        self._bg_color = "#2D2D30"  # 深色背景
        self._progress_color = "#0078D7"  # IDM风格蓝色
        
        # 新增：分段支持
        self._segments = []  # 存储分段信息 [(开始位置百分比, 结束位置百分比, 颜色), ...]
        self._show_segments = False  # 是否显示分段
        
        # 设置透明背景属性，保证绘制效果
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 初始化字体管理器
        self.font_manager = FontManager()

    def _get_value(self):
        return self._progress
        
    def _set_value(self, value):
        self._progress = max(0, min(value, 100))
        self.update()
        
    value = Property(float, _get_value, _set_value)
        
    def setProgress(self, value, animated=True):
        if self._animation.state() == QPropertyAnimation.Running:
            self._animation.stop()
            
        target_value = max(0, min(value, 100))
        if animated and abs(target_value - self._progress) > 0.1:
            self._animation.setStartValue(self._progress)
            self._animation.setEndValue(target_value)
            self._animation.start()
        else:
            self._set_value(target_value)
    
    # 设置分段列表
    def setSegments(self, segments):
        """
        设置分段信息
        segments: 列表 [(开始位置百分比, 结束位置百分比, 颜色), ...]
        """
        self._segments = segments
        self.update()
    
    # 启用/禁用分段显示
    def setShowSegments(self, show):
        """启用或禁用分段显示"""
        self._show_segments = show
        self.update()
    
    # 从下载数据创建分段
    def updateFromDownloadSegments(self, segments_data, total_size):
        """
        从下载分段数据更新进度条的分段显示
        segments_data: 下载分段数据，格式为 [{startPos, endPos, progress}, ...] 或 [(startPos, progress, endPos), ...]
        total_size: 总文件大小
        """
        if not segments_data or total_size <= 0:
            return
        
        segments = []
        progress_sum = 0
        
        # IDM风格的蓝色
        base_color = "#0078D7"  # 微软蓝
        
        try:
            # 尝试处理字典格式的分段数据
            if isinstance(segments_data[0], dict):
                for i, segment in enumerate(segments_data):
                    start_pos = segment.get('startPos', 0)
                    end_pos = segment.get('endPos', 0)
                    progress = segment.get('progress', start_pos)
                    
                    # 计算百分比位置
                    start_percent = (start_pos / total_size) * 100
                    end_percent = (end_pos / total_size) * 100
                    progress_percent = (progress / total_size) * 100
                    
                    # 已下载的部分
                    if progress > start_pos:
                        segments.append((start_percent, progress_percent, base_color))
                    
                    # 计算总进度
                    progress_sum += (progress - start_pos)
                
            # 尝试处理元组格式的分段数据
            elif isinstance(segments_data[0], (list, tuple)):
                for i, segment in enumerate(segments_data):
                    if len(segment) >= 3:
                        start_pos = segment[0]
                        progress = segment[1]
                        end_pos = segment[2]
                        
                        # 计算百分比位置
                        start_percent = (start_pos / total_size) * 100
                        end_percent = (end_pos / total_size) * 100
                        progress_percent = (progress / total_size) * 100
                        
                        # 已下载的部分
                        if progress > start_pos:
                            segments.append((start_percent, progress_percent, base_color))
                        
                        # 计算总进度
                        progress_sum += (progress - start_pos)
            
            # 设置分段和总进度
            if segments:
                self.setSegments(segments)
                self.setShowSegments(True)
                
                # 更新总体进度
                overall_progress = (progress_sum / total_size) * 100
                self.setProgress(overall_progress)
                
        except Exception as e:
            print(f"更新分段进度条时出错: {e}")
    
    def setStyleSheet(self, style):
        super().setStyleSheet(style)
        # 尝试从样式表中提取背景颜色和进度条颜色
        try:
            import re
            bg_match = re.search(r'background-color:\s*(#[0-9A-Fa-f]+)', style)
            if bg_match:
                self._bg_color = bg_match.group(1)
            
            chunk_match = re.search(r'::chunk\s*{[^}]*background-color:\s*(#[0-9A-Fa-f]+)', style)
            if chunk_match:
                self._progress_color = chunk_match.group(1)
        except:
            pass
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        width = self.width()
        height = self.height()
        
        # 绘制背景 - 使用深色矩形
        painter.fillRect(0, 0, width, height, QColor(self._bg_color))
        
        # 绘制边框 - IDM风格有细边框
        border_pen = QPen(QColor(60, 60, 60))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRect(0, 0, width-1, height-1)
        
        # 如果启用了分段显示且有分段，绘制IDM风格分段
        if self._show_segments and self._segments:
            # 块的大小和间距
            block_width = 10
            block_margin = 2
            
            # 遍历所有分段
            for start_percent, end_percent, color_str in self._segments:
                if end_percent <= start_percent:
                    continue
                
                # 计算这个分段覆盖的像素范围
                start_pos = int(width * start_percent / 100)
                end_pos = int(width * end_percent / 100)
                segment_width = end_pos - start_pos
                
                # 在这个范围内绘制块
                current_x = start_pos
                while current_x < end_pos:
                    # 确保块不超出分段范围
                    curr_block_width = min(block_width, end_pos - current_x)
                    
                    # 绘制蓝色块
                    painter.fillRect(
                        current_x, 1,  # 左上角坐标
                        curr_block_width, height - 2,  # 宽高，稍微小于总高度
                        QColor(color_str)
                    )
                    
                    # 添加亮色顶部高光 - IDM风格特点
                    highlight_color = QColor(255, 255, 255, 90)  # 半透明白色
                    painter.fillRect(
                        current_x, 1,
                        curr_block_width, height // 4,
                        highlight_color
                    )
                    
                    # 移动到下一个块位置
                    current_x += curr_block_width + block_margin
        
        # 否则绘制普通进度条（不分段时）
        elif self._progress > 0:
            progress_width = int(width * self._progress / 100)
            
            # IDM风格：使用蓝色块
            block_width = 10
            block_margin = 2
            current_x = 0
            
            while current_x < progress_width:
                # 确保不超出进度宽度
                curr_block_width = min(block_width, progress_width - current_x)
                
                # 绘制蓝色块
                painter.fillRect(
                    current_x, 1,
                    curr_block_width, height - 2,
                    QColor(self._progress_color)
                )
                
                # 添加亮色顶部高光
                highlight_color = QColor(255, 255, 255, 90)
                painter.fillRect(
                    current_x, 1,
                    curr_block_width, height // 4,
                    highlight_color
                )
                
                # 移动到下一个块位置
                current_x += curr_block_width + block_margin
        
        painter.end() 