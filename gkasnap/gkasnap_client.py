import subprocess
import time
import win32pipe
import win32file
import os
from threading import Thread

class GKASnap:
    def __init__(self, save_path):
        self.save_path = save_path
        self.pipe = None
        self.process = None
        self.running = False
        
    def start(self):
        # 启动gkasnap.exe
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            exe_path = os.path.join(current_dir, 'gkasnap.exe')
            print(f"当前工作目录: {os.getcwd()}")
            print(f"检查文件是否存在: {os.path.exists(exe_path)}")
            print(f"完整文件路径: {exe_path}")
        
            self.process = subprocess.Popen([exe_path, self.save_path], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            if self.process.poll() is not None:
                print(f"进程启动失败，返回码: {self.process.returncode}")
                return False
            max_retries = 5
            for i in range(max_retries):
                try:
                    time.sleep(1)  # 每次尝试前等待1秒
                    print(f"尝试连接管道，第 {i+1} 次...")
                    self.pipe = win32file.CreateFile(
                        r'\\.\pipe\GkSnapPipe',
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        0, None,
                        win32file.OPEN_EXISTING,
                        0, None
                    )
                    break
                except Exception as e:
                    print(f"连接失败: {e}")
                    if i == max_retries - 1:  # 最后一次尝试
                        raise
                    continue
            
            self.running = True
            # 启动心跳线程
            Thread(target=self._heartbeat_thread, daemon=True).start()
            return True
        except Exception as e:
            print(f"启动失败: {e}")
            self.stop()
            return False
            
    def _heartbeat_thread(self):
        while self.running:
            try:
                win32file.WriteFile(self.pipe, b'heartbeat')
                time.sleep(0.5)
            except:
                self.running = False
                break
                
    def snap(self):
        if self.running:
            try:
                win32file.WriteFile(self.pipe, b'snap')
                return True
            except:
                return False
        return False
        
    def stop(self):
        self.running = False
        if self.pipe:
            try:
                win32file.CloseHandle(self.pipe)
            except:
                pass

if __name__ == "__main__":
    # 如果文件夹不存在则创建文件夹
    save_path = "D:/gka_capture/"
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    snap = GKASnap(save_path)
    if snap.start():
        try:
            # 抓图
            # snap.snap()
            # time.sleep(1)  # 等待抓图完成
            
            for i in range(10):
                snap.snap()
                time.sleep(1)
            
        finally:
            snap.stop()


