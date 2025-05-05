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
            
        try:
            # 初始计算
            total_downloaded = 0
            total_size = 0
            
            # 收集所有块信息
            segments = []
            for seg in progress_data:
                if isinstance(seg, dict):
                    # 新格式：字典形式
                    start = seg.get('start_position', seg.get('start_pos', seg.get('startPos', 0)))
                    end = seg.get('end_position', seg.get('end_pos', seg.get('endPos', 0)))
                    current = seg.get('current_position', seg.get('progress', start))
                elif isinstance(seg, (list, tuple)) and len(seg) >= 3:
                    # 旧格式：列表形式
                    start, current, end = seg[:3]
                else:
                    continue
                
                # 确保数值类型
                try:
                    start = int(start)
                    current = int(current)
                    end = int(end)
                except (ValueError, TypeError):
                    continue
                
                # 确保逻辑正确
                if start < 0 or end < start or current < start:
                    continue
                    
                # 限制最大值
                current = min(current, end)
                
                # 计算当前块的下载量和总大小
                current_downloaded = current - start
                segment_size = end - start + 1
                
                # 累加已下载和总大小
                total_downloaded += current_downloaded
                total_size += segment_size
                
                # 避免除零错误
                if end > start and file_size > 0:
                    start_percent = (start / file_size) * 100
                    end_percent = ((end + 1) / file_size) * 100
                    current_percent = (current / file_size) * 100
                    
                    # 添加已下载部分(绿色)
                    if current > start:
                        segments.append((start_percent, current_percent, self.progressColor))
                    
                    # 添加未下载部分(灰色)
                    if current < end:
                        segments.append((current_percent, end_percent, self.pendingColor))
                        
                # 打印调试信息
                print(f"块 {start}-{end}, 当前={current}, 进度={((current-start)/(end-start+1))*100:.1f}%")
            
            # 计算进度百分比
            if total_size > 0:
                percentage = (total_downloaded / total_size) * 100
                
                # 处理接近完成情况
                if percentage > 99.9 and percentage < 100:
                    percentage = 100
                
                # 限制范围
                percentage = max(0, min(100, percentage))
                
                # 调试输出
                print(f"[DEBUG] 进度条计算总进度: {percentage:.2f}%, 已下载: {total_downloaded}, 总大小: {total_size}")
            
            # 设置分段和总进度
            if segments:
                self.setSegments(segments)
            self.setProgress(percentage, False)
            
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