from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, Property
from PySide6.QtGui import QPainter, QColor, QPainterPath

class ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(15)  # 增加高度以容纳IDM风格分段显示
        self._progress = 0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(200)
        self._segments = [(0, 100, "#1FB15F")]  # 默认的分段信息(起始点, 结束点, 颜色)
        self._showSegments = True
        self._idmStyle = True  # 启用IDM风格
        
        # 各种颜色
        self.progressColor = "#1FB15F"  # 绿色
        self.downloadingColor = "#3478F6"  # 蓝色
        self.pendingColor = "#999999"  # 灰色
        self.errorColor = "#FF3B30"  # 红色
        
        self.setStyleSheet("""
            QWidget {
                background: #F0F0F0;
                border-radius: 3px;
            }
        """)

    def _get_value(self):
        return self._progress
        
    def _set_value(self, value):
        self._progress = max(0, min(value, 100))
        self.update()
        
    value = Property(float, _get_value, _set_value)
    
    def setSegments(self, segments):
        self._segments = segments
        self.update()
        
    def setShowSegments(self, show):
        self._showSegments = show
        self.update()
        
    def setIdmStyle(self, enable):
        self._idmStyle = enable
        self.update()
        
    def updateFromDownloadSegments(self, progress_data, file_size):
        """根据下载管理器提供的分段数据更新进度条显示"""
        if not progress_data or file_size <= 0:
            return
            
        # 打印进度数据用于调试
        print(f"[DEBUG] ProgressBar接收到的进度数据: {progress_data[:2]}, 文件大小: {file_size}")
            
        segments = []
        total_downloaded = 0
        total_size = 0
        
        # 处理不同格式的进度数据
        try:
            if isinstance(progress_data[0], dict):
                for segment in progress_data:
                    # 兼容多种可能的字段名称
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
                    
                    # 累加已下载和总大小
                    total_downloaded += current_downloaded
                    total_size += segment_size
                    
                    # 避免除零错误
                    if end_pos > start_pos and file_size > 0:
                        start_percent = (start_pos / file_size) * 100
                        end_percent = ((end_pos + 1) / file_size) * 100
                        current_percent = (current / file_size) * 100
                        
                        # 添加已下载部分(绿色)
                        if current > start_pos:
                            segments.append((start_percent, current_percent, self.progressColor))
                        
                        # 添加未下载部分(灰色)
                        if current < end_pos:
                            segments.append((current_percent, end_percent, self.pendingColor))
                            
                    # 打印调试信息
                    print(f"块 {start_pos}-{end_pos}, 当前={current}, 进度={((current-start_pos)/(end_pos-start_pos+1))*100:.1f}%")
                    
            elif isinstance(progress_data[0], (list, tuple)) and len(progress_data[0]) >= 3:
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
                    
                    # 累加已下载和总大小
                    total_downloaded += current_downloaded
                    total_size += segment_size
                    
                    # 避免除零错误
                    if end_pos > start_pos and file_size > 0:
                        start_percent = (start_pos / file_size) * 100
                        end_percent = ((end_pos + 1) / file_size) * 100
                        current_percent = (current / file_size) * 100
                        
                        # 添加已下载部分(绿色)
                        if current > start_pos:
                            segments.append((start_percent, current_percent, self.progressColor))
                        
                        # 添加未下载部分(灰色)
                        if current < end_pos:
                            segments.append((current_percent, end_percent, self.pendingColor))
                            
                    # 打印调试信息
                    print(f"块 {start_pos}-{end_pos}, 当前={current}, 进度={((current-start_pos)/(end_pos-start_pos+1))*100:.1f}%")
            
            # 使用直接计算的方式获取总进度
            total_progress = 0
            if total_size > 0:
                # 确保使用浮点数计算
                total_progress = (float(total_downloaded) / float(total_size)) * 100.0
                print(f"[DEBUG] 进度条计算总进度: {total_progress:.2f}%, 已下载: {total_downloaded}, 总大小: {total_size}")
                
                # 确保进度大于0且不超过100
                # 如果接近完成但未完全完成，限制在99%
                if total_progress >= 99.5 and total_downloaded < total_size:
                    total_progress = 99.0
                else:
                    total_progress = max(0.1, min(100.0, total_progress))
            
            # 设置分段和总进度
            if segments:
                self.setSegments(segments)
            self.setProgress(total_progress, False)
            
        except Exception as e:
            import traceback
            print(f"[ERROR] 更新进度条出错: {e}")
            traceback.print_exc()
            # 强制设置一个小进度值
            self.setProgress(1, False)
            
            # 如果所有块的进度都等于结束位置，说明完成了
            completed = True
            try:
                for seg in progress_data:
                    if isinstance(seg, dict):
                        end = seg.get('end_position', seg.get('end_pos', seg.get('endPos', 0)))
                        current = seg.get('current_position', seg.get('progress', 0))
                        if current < end:
                            completed = False
                            break
                    elif isinstance(seg, (list, tuple)) and len(seg) >= 3:
                        if seg[1] < seg[2]:  # current < end
                            completed = False
                            break
                            
                if completed:
                    self.setProgress(100, False)
                    print("[INFO] 检测到所有块已完成，设置进度为100%")
            except Exception as e2:
                print(f"[ERROR] 检查完成状态出错: {e2}")
        
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        bar_height = 5  # 主进度条高度
        segments_height = 3  # 分段指示器高度
        segments_top = rect.top() + bar_height + 2  # 分段指示器顶部位置
        
        # 绘制背景（主进度条）
        main_bar_rect = rect.adjusted(0, 0, 0, -(rect.height() - bar_height))
        path = QPainterPath()
        path.addRoundedRect(main_bar_rect, 3, 3)
        painter.fillPath(path, QColor("#F0F0F0"))
        
        # 绘制主进度
        if self._progress > 0:
            progress_width = int(rect.width() * self._progress / 100)
            progress_path = QPainterPath()
            progress_path.addRoundedRect(0, 0, progress_width, bar_height, 3, 3)
            painter.fillPath(progress_path, QColor(self.progressColor))

        # 绘制IDM风格的分段指示器
        if self._idmStyle and self._showSegments:
            # 绘制分段指示器背景
            seg_bg_path = QPainterPath()
            seg_bg_path.addRoundedRect(0, segments_top, rect.width(), segments_height, 2, 2)
            painter.fillPath(seg_bg_path, QColor("#E0E0E0"))
            
            # 绘制各个下载分段
            if self._segments:
                # 首先绘制背景色的小段
                for start_percent, end_percent, color in self._segments:
                    if end_percent > start_percent and color == self.pendingColor:  # 未下载部分用灰色
                        start_x = int((start_percent / 100) * rect.width())
                        end_x = int((end_percent / 100) * rect.width())
                        width = max(2, end_x - start_x)  # 确保至少有2像素宽度
                        
                        segment_path = QPainterPath()
                        segment_path.addRoundedRect(start_x, segments_top, width, segments_height, 2, 2)
                        painter.fillPath(segment_path, QColor(color))
                
                # 然后绘制已下载部分
                for start_percent, end_percent, color in self._segments:
                    if end_percent > start_percent and color == self.progressColor:  # 已下载部分用主色
                        start_x = int((start_percent / 100) * rect.width())
                        end_x = int((end_percent / 100) * rect.width())
                        width = max(2, end_x - start_x)  # 确保至少有2像素宽度
                        
                        segment_path = QPainterPath()
                        segment_path.addRoundedRect(start_x, segments_top, width, segments_height, 2, 2)
                        painter.fillPath(segment_path, QColor(color))

        painter.end() 