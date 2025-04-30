import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from download_kernel import TransferManager
from core.config import cfg

class TestDownloadKernel(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.download_dir = Path(self.temp_dir.name)
        self.test_url = "https://speed.hetzner.de/100MB.bin"  # Sample test file
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_download_initialization(self):
        transfer = TransferManager(
            url=self.test_url,
            headers=self.headers,
            maxThreads=4,
            savePath=str(self.download_dir),
            filename="test_file.bin"
        )
        
        # 此时不应该开始下载，而是等待初始化完成的信号
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer.url, self.test_url)
        self.assertEqual(transfer.filename, "test_file.bin")
        self.assertEqual(transfer.savePath, self.download_dir)
        self.assertEqual(transfer.threadCount, 4)
    
    def test_download_with_custom_threads(self):
        # 这个测试通常需要mock网络请求
        # 这里我们只是验证传入的参数是否正确设置
        transfer = TransferManager(
            url=self.test_url, 
            headers=self.headers,
            maxThreads=2,
            savePath=str(self.download_dir)
        )
        
        self.assertEqual(transfer.threadCount, 2)
        self.assertEqual(transfer.dynamicThreads, False)
    
    def test_dynamic_threads_enabled(self):
        transfer = TransferManager(
            url=self.test_url,
            headers=self.headers,
            maxThreads=4,
            savePath=str(self.download_dir),
            dynamicThreads=True
        )
        
        self.assertTrue(transfer.dynamicThreads)
    
   

if __name__ == "__main__":
    unittest.main() 