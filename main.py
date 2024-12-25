# -*- coding: utf-8 -*-
import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, PhotoImage, Label, filedialog
from tkinter.font import Font
from PIL import Image, ImageTk

import sys
sys.path.append(r"C:\Users\Administrator\PycharmProjects\pythonProject3")
# import clrclr.AddReference("krcc64")
# import KRcc
import socket
from tkinter import PhotoImage

# 初始化日志记录
logging.basicConfig(
    filename="robotic_arm.log",  # 日志文件名
    level=logging.INFO,          # 日志级别
    format="%(asctime)s - %(levelname)s - %(message)s",  # 日志格式：时间戳 - 日志级别 - 消息
    encoding='utf-8'             # 指定日志文件编码为 utf-8
)

class TCPServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.daemon = True
        self.server_socket = None
        self.app = app  # 引用主应用实例

    def run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.server_socket.bind(('192.168.1.186', 8888))
        self.server_socket.bind(('localhost', 8888))
        self.server_socket.listen(5)
        logging.info("TCP server started and waiting for connections...")
        print("TCP 服务器已启动，等待连接...")

        while True:
            client_socket, addr = self.server_socket.accept()
            logging.info(f"Connection established from: {addr}")
            print(f"连接来自: {addr}")
            self.app.client_connected = True
            self.app.update_on_air_status(True)

            try:
                while True:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    logging.info(f"Received command: {data}")
                    print(f"接收到数据: {data}")
                    # 处理数据
            except ConnectionResetError:
                logging.warning(f"Connection forcibly closed by remote host: {addr}")
                print(f"连接被远程主机强制关闭: {addr}")
            finally:
                self.app.client_connected = False
                self.app.update_on_air_status(False)
                client_socket.close()  # 确保在退出循环时关闭客户端socket
                logging.info(f"Connection closed: {addr}")
                print("客户端连接已关闭，等待新的连接...")


class App:
    def __init__(self, root):
        self.win_width = 640
        self.win_height = 800
        self.root = root
        self.root.title("Auto Play")
        self.root.geometry(f"{self.win_width}x{self.win_height}")
        self.root.configure(bg="#2F2F2F")

        self.server_active = False  # 跟踪服务端是否活跃
        self.client_connected = False  # 跟踪客户端是否连接

        self.TCP_HOST = '192.168.1.186'  # 监听所有网络接口
        self.TCP_PORT = 8888  # TCP 服务器端口
        # self.comm = KRcc.Commu("TCP 192.168.1.120")
        #self.comm = KRcc.Commu("EXECUTE gkamain")
        self.comm = MockComm()

        # 加载并调整图片大小
        original_image = Image.open("header_image.png")
        new_height = int(original_image.height * (self.win_width / original_image.width))
        resize_image = original_image.resize((self.win_width, new_height))
        self.header_image = ImageTk.PhotoImage(resize_image)

        # 创建顶部 Frame 来放置图片
        top_image_frame = tk.Frame(self.root, bg="#2F2F2F")
        top_image_frame.grid(row=0, column=0, sticky="ew")  # 使用 grid
        self.root.grid_columnconfigure(0, weight=1)

        # 创建 Label 来显示图片
        header_label = Label(top_image_frame, image=self.header_image)
        header_label.grid(row=0, column=0, sticky="ew")  # 使用 grid

        # 创建顶部控件的 Frame
        top_frame = tk.Frame(self.root, bg="#2F2F2F")
        top_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.root.grid_columnconfigure(0, weight=1)  # 使 top_frame 水平扩展
        button_width = 10  # 按钮宽度设置为10个字符宽
        bold_font = Font(family="Segoe UI", size=10, weight="bold")  # 创建加粗字体

        # 添加运镜按钮
        self.add_button = tk.Button(top_frame, text="添加运镜", command=self.add_row, bg="gray", width=button_width, fg='white', font=bold_font)
        self.add_button.grid(row=0, column=0, padx=3, pady=3)

        # Vizrt 按钮(启动 TCP 服务器)
        self.start_server_button = tk.Button(top_frame, text="Vizrt", command=self.start_tcp_server, bg="gray", width=button_width, fg='white', font=bold_font)
        self.start_server_button.grid(row=0, column=1, padx=3, pady=3)

        # 连接状态指示器
        self.status_canvas = tk.Canvas(top_frame, width=60, height=60, bg="#2F2F2F", bd=0, highlightthickness=0)
        self.status_canvas.grid(row=0, column=2, padx=3, pady=3)
        self.on_air_indicator = self.status_canvas.create_oval(5, 5, 55, 55, fill='gray', outline='')
        self.on_air_text = self.status_canvas.create_text(30, 30, text="ON AIR", fill='white', font=bold_font)

        # 机械臂控制按钮
        self.pow_on_button = tk.Button(top_frame, text="开启机械臂", command=self.pow_on, bg="gray", width=button_width, fg='white', font=bold_font)
        self.pow_on_button.grid(row=0, column=3, padx=3, pady=3)

        self.pow_off_button = tk.Button(top_frame, text="关闭机械臂", command=self.pow_off, bg="gray", width=button_width, fg='white', font=bold_font)
        self.pow_off_button.grid(row=0, column=4, padx=3, pady=3)

        self.pause_button = tk.Button(top_frame, text="暂停", command=self.pause, bg="gray", width=button_width, fg='white', font=bold_font)
        self.pause_button.grid(row=0, column=5, padx=3, pady=3)

        # 调整列权重以实现居中
        for i in range(6):
            top_frame.grid_columnconfigure(i, weight=1)
        top_frame.grid_columnconfigure(2, weight=2)  # 增加中间列的权重

        # 创建一个 Frame 用于放置动态添加的行
        self.frame = tk.Frame(root)
        self.frame.grid(row=2, column=0, columnspan=5, sticky="nsew")

        # 创建一个 Canvas 用于滚动
        self.canvas = tk.Canvas(self.frame,width=580,height=570)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 创建一个 Scrollbar
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置 Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.configure(bg="#2F2F2F")
        # 创建一个 Frame 用于放置内容
        self.inner_frame = tk.Frame(self.canvas)
        self.inner_frame.configure(bg="#2F2F2F")

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        # 初始化行号
        self.row_count = 1
        self.program_entries = []
        self.speed_entries = []

        # 加载保存的数据（如果存在）
        self.load_data()

        # 添加初始行
        self.add_row()

        # TCP 服务器线程
        self.server_thread = None

        # 存储接收到的数据
        self.received_data = None

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 创建表头
        self.create_table_header()

    def create_table_header(self):
        headers = ["截图", "Vizrt指令", "运镜名", "运行速度", "备注", "控制"]

        # 表头的权重和最小宽度设置
        column_config = [
            {"weight": 1, "minsize": 90},  # 截图列
            {"weight": 1, "minsize": 10},  # Vizrt指令列
            {"weight": 1, "minsize": 10},  # 运镜名列
            {"weight": 1, "minsize": 10},  # 运行速度列
            {"weight": 1, "minsize": 10},  # 备注列
            {"weight": 1, "minsize": 10},  # 控制列
        ]

        # 为每列设置表头
        for index, header in enumerate(headers):
            label = tk.Label(self.inner_frame, text=header, bg="#808080", font=('Segoe UI', 10, 'bold'))
            label.grid(row=0, column=index, padx=5, pady=5, sticky='ew')

            # 配置每列的宽度
            self.inner_frame.grid_columnconfigure(index, weight=column_config[index]["weight"], minsize=column_config[index]["minsize"])

    def add_row(self):
        # 加载上传图标
        upload_icon = Image.open("upload_image.png")
        upload_icon = upload_icon.resize((90, 60))
        upload_icon.thumbnail((90, 60))
        upload_icon_image = ImageTk.PhotoImage(upload_icon)

        # 使用 Label 显示上传图标，并作为上传按钮
        icon_label = tk.Label(self.inner_frame, image=upload_icon_image, bg="#2F2F2F")
        icon_label.image = upload_icon_image  # 保留引用防止被垃圾回收
        icon_label.grid(row=self.row_count, column=0, padx=5, pady=5)

        # 绑定点击事件触发上传图片
        icon_label.bind("<Button-1>", lambda event, row=self.row_count, label=icon_label: self.upload_image(row, label))

        # Vizrt指令 label
        label_vizrt = tk.Label(self.inner_frame, text=f"P0{self.row_count}C01", bg="#2F2F2F", fg="white", width=10)
        label_vizrt.grid(row=self.row_count, column=1, padx=5, pady=5)

        # 运镜名输入框
        entry_program = tk.Entry(self.inner_frame, width=15)
        entry_program.grid(row=self.row_count, column=2, padx=5, pady=5)
        self.program_entries.append(entry_program)

        # 运行速度输入框
        entry_speed = tk.Entry(self.inner_frame, width=10, fg='gray')
        entry_speed.insert(0, "范围:1-50") if not entry_speed.get() else None
        entry_speed.bind("<FocusIn>", lambda event: entry_speed.delete(0, tk.END) if entry_speed.get() == "范围:1-50" else None)
        entry_speed.grid(row=self.row_count, column=3, padx=5, pady=5)
        self.speed_entries.append(entry_speed)

        # 备注输入框
        entry_note = tk.Entry(self.inner_frame, width=15)
        entry_note.grid(row=self.row_count, column=4, padx=5, pady=5)

        # 控制按钮的容器
        control_frame = tk.Frame(self.inner_frame, bg="#2F2F2F")
        control_frame.grid(row=self.row_count, column=5, padx=5, pady=5, sticky="ew")

        # 回到起点按钮
        btn_reset = tk.Button(control_frame, text="回到起点", command=lambda: self.print_program_and_speed(entry_program.get(), entry_speed.get()) if self.validate_speed(entry_speed.get()) else None)
        btn_reset.pack(side=tk.LEFT, padx=3, pady=3)

        # 开始运行按钮
        btn_start = tk.Button(control_frame, text="开始运行", command=lambda: self.print_speed(entry_speed.get()) if self.validate_speed(entry_speed.get()) else None)
        btn_start.pack(side=tk.LEFT, padx=3, pady=3)

        # 更新行号
        self.row_count += 1

        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def validate_speed(self, speed):
        try:
            speed = int(speed)
            if 1 <= speed <= 50:
                return True
            else:
                print("Speed must be between 1 and 50")
                return False
        except ValueError:
            print("Invalid speed value")
            return False

    def start_tcp_server(self):
        if not self.server_active:
            self.server_thread = TCPServerThread(self)
            self.server_thread.start()
            self.server_active = True
            self.start_server_button.config(bg="#00FF00")  # 尝试在线程启动后立即更改颜色
            self.root.update_idletasks()  # 使用 update_idletasks 尝试强制 GUI 刷新
            print("TCP 服务器已启动")
        else:
            print("TCP 服务器已经在运行")

    def pow_on(self):
        # 添加日志记录
        logging.info("Preparing to send commands: ZPOWER ON, EXECUTE gkamain")
        # 打开机械臂
        self.comm.command(f"ZPOWER ON")
        self.comm.command(f"EXECUTE gkamain")

    def pow_off(self):
        # 添加日志记录
        logging.info("Preparing to send command: ZPOWER OFF")
        # 关闭机械臂
        self.comm.command(f"ZPOWER OFF")

    def pause(self):
        # 添加日志记录
        logging.info("Preparing to send command: SWITCH CS for pause or continue check")

        retrun, srun = self.comm.command("SWITCH CS")
        logging.info(f"Received response: {srun}")

        claa='ON'
        all_words_exist = all(word.lower() in srun.lower() for word in claa)
        if all_words_exist:
            self.comm.command("HOLD")
        else:
            self.comm.command("CONTINUE")

    def print_program_and_speed(self, program, speed):
        # 添加日志记录
        logging.info(f"Preparing to send commands: SPEED {speed}, EXECUTE {program}")
        # 发送速度命令
        self.comm.command(f"SPEED {speed}")
        # 发送程序命令
        self.comm.command(f"EXECUTE {program}")

    def print_speed(self, speed):
        # 添加日志记录
        logging.info(f"Preparing to send command: PULSE 2666 with speed {speed}")
        # 发送命令
        self.comm.command(f"PULSE 2666")

    def update_on_air_status(self, is_connected):
        color = 'red' if is_connected else 'gray'
        self.status_canvas.itemconfig(self.on_air_indicator, fill=color)

    def compare_p01c01_content(self):
        # 获取每行 P01C01 程序名中的内容并与 TCP 接收的数据对比
        local_data = ""
        if self.received_data=='P01C01T':
            program_1 = self.program_entries[0].get()
            speed_1 = self.speed_entries[0].get()
            self.comm.command(f"SPEED "+speed_1 )
            self.comm.command(f"EXECUTE "+program_1)
        if self.received_data=='P02C01T':
            program_2 = self.program_entries[1].get()
            speed_2 = self.speed_entries[1].get()
            self.comm.command(f"SPEED "+speed_2 )
            self.comm.command(f"EXECUTE "+program_2)
        if self.received_data=='P03C01T':
            program_3 = self.program_entries[2].get()
            speed_3 = self.speed_entries[2].get()
            self.comm.command(f"SPEED "+speed_3 )
            self.comm.command(f"EXECUTE "+program_3)
        if self.received_data=='P04C01T':
            program_4 = self.program_entries[3].get()
            speed_4 = self.speed_entries[3].get()
            self.comm.command(f"SPEED "+speed_4 )
            self.comm.command(f"EXECUTE "+program_4)
        if self.received_data=='P05C01T':
            program_5 = self.program_entries[4].get()
            speed_5 = self.speed_entries[4].get()
            self.comm.command(f"SPEED "+speed_5 )
            self.comm.command(f"EXECUTE "+program_5)
        if self.received_data=='P06C01T':
            program_6 = self.program_entries[5].get()
            speed_6 = self.speed_entries[5].get()
            self.comm.command(f"SPEED "+speed_6 )
            self.comm.command(f"EXECUTE "+program_6)
        if self.received_data=='P07C01T':
            program_7 = self.program_entries[6].get()
            speed_7 = self.speed_entries[6].get()
            self.comm.command(f"SPEED "+speed_7 )
            self.comm.command(f"EXECUTE "+program_7)
        if self.received_data=='P08C01T':
            program_8 = self.program_entries[7].get()
            speed_8 = self.speed_entries[7].get()
            self.comm.command(f"SPEED "+speed_8 )
            self.comm.command(f"EXECUTE "+program_8)
        if self.received_data=='P09C01T':
            program_9 = self.program_entries[8].get()
            speed_9 = self.speed_entries[8].get()
            self.comm.command(f"SPEED "+speed_9 )
            self.comm.command(f"EXECUTE "+program_9)
        if self.received_data=='P10C01T':
            program_10 = self.program_entries[9].get()
            speed_10 = self.speed_entries[9].get()
            self.comm.command(f"SPEED "+speed_10 )
            self.comm.command(f"EXECUTE "+program_10)
        if self.received_data=='P11C01T':
            program_11 = self.program_entries[10].get()
            speed_11 = self.speed_entries[10].get()
            self.comm.command(f"SPEED "+speed_11 )
            self.comm.command(f"EXECUTE "+program_11)

        if self.received_data=='P99C99T':

            self.comm.command(f"PULSE 2666")

        else:
            print("尚未接收到 TCP 数据")

    def contains_string(sublist):
        """检查子列表是否包含字符串"""
        return any(isinstance(item, str) for item in sublist)

    def load_data(self):
        try:
            with open("program_data.json", "r", encoding="utf-8") as file:
                data = json.load(file)

            # 清除现有行数据
            for widget in self.inner_frame.winfo_children():
                widget.destroy()

            # 重新添加表头
            self.create_table_header()
            self.row_count = 1  # 重置行号

            # 加载每一行数据
            for row_data in data:
                self.add_row()  # 添加新行

                # 设置截图（这里假设截图占位图是 Label）
                screenshot_label = self.inner_frame.grid_slaves(row=self.row_count - 1, column=0)[0]
                screenshot_path = row_data.get("screenshot", "未上传")
                if screenshot_path != "未上传":
                    img = Image.open(screenshot_path)
                    img.thumbnail((90, 60))
                    photo_img = ImageTk.PhotoImage(img)
                    screenshot_label.config(image=photo_img)
                    screenshot_label.image = photo_img
                    screenshot_label.image_path = screenshot_path

                # 设置运镜名
                self.program_entries[self.row_count - 2].delete(0, tk.END)
                self.program_entries[self.row_count - 2].insert(0, row_data["program"])

                # 设置运行速度
                self.speed_entries[self.row_count - 2].delete(0, tk.END)
                self.speed_entries[self.row_count - 2].insert(0, row_data["speed"])

                # 设置备注
                note_entry = self.inner_frame.grid_slaves(row=self.row_count - 1, column=4)[0]
                note_entry.delete(0, tk.END)
                note_entry.insert(0, row_data["note"])

                # 设置 vizrt 指令
                vizrt_label = self.inner_frame.grid_slaves(row=self.row_count - 1, column=1)[0]
                if isinstance(vizrt_label, tk.Label):
                    vizrt_label.config(text=row_data["vizrt"])

        except FileNotFoundError:
            print("未找到保存的数据文件")
        except json.JSONDecodeError:
            print("数据文件格式错误")

    def save_data(self):
        data = []
        for row in range(self.row_count - 1):  # 遍历所有已添加的行
            # 获取截图路径（如果需要保存上传的图像路径）
            screenshot_label = self.inner_frame.grid_slaves(row=row + 1, column=0)[0]
            screenshot = getattr(screenshot_label, "image_path", "未上传")

            # 获取运镜名
            program = self.program_entries[row].get()

            # 获取运行速度
            speed_entry = self.speed_entries[row]
            speed = speed_entry.get()
            if speed == "范围:1-50":
                speed = ""  # 如果是占位符，则将其设置为空

            # 获取备注
            note_entry = self.inner_frame.grid_slaves(row=row + 1, column=4)[0]
            note = note_entry.get()

            # 获取 vizrt 指令
            vizrt_label = self.inner_frame.grid_slaves(row=row + 1, column=1)[0]
            if isinstance(vizrt_label, tk.Label):
                vizrt = vizrt_label.cget("text")
            else:
                vizrt = "Unknown"

            # 保存行数据
            data.append({
                "screenshot": screenshot,
                "program": program,
                "speed": speed,
                "note": note,
                "vizrt": vizrt
            })

        # 保存数据到 JSON 文件
        with open("program_data.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print("数据已保存到 program_data.json")

    def on_close(self):
        # 窗口关闭时保存数据
        self.save_data()
        self.root.destroy()

    def upload_image(self, row, label):
        # 弹出文件选择对话框
        filename = filedialog.askopenfilename(title="选择图片", filetypes=(("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")))
        if filename:
            # 加载选择的图片并调整为缩略图
            img = Image.open(filename)
            img.thumbnail((90, 60))
            photo_img = ImageTk.PhotoImage(img)
    
            # 更新 Label 的图像
            label.config(image=photo_img)
            label.image = photo_img  # 保留引用防止垃圾回收
            label.image_path = filename  # 保存图片路径

# TODO: 用于模拟通信的类, 最后记得删除
class MockComm:
    def __init__(self):
        self.commands = {
            "ZPOWER ON": "Machine powered on",
            "ZPOWER OFF": "Machine powered off",
            "SPEED": lambda speed: f"Speed set to {speed}",
            "EXECUTE": lambda program: f"Executing {program}",
            "PULSE 2666": "Pulse command received",
            "SWITCH CS": "ON AIR"
        }

    def command(self, cmd):
        if cmd in self.commands:
            print(f"Command: {cmd}")
            if cmd == "SWITCH CS":
                return True, self.commands[cmd]
        else:
            print(f"Command not found: {cmd}")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()