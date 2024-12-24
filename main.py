# -*- coding: utf-8 -*-
import json
import threading
import tkinter as tk
from tkinter import ttk
import sys
sys.path.append(r"C:\Users\Administrator\PycharmProjects\pythonProject3")
import clr
clr.AddReference("krcc64")
import KRcc
import socket
from tkinter import PhotoImage

class TCPServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.daemon = True
        self.server_socket = None
        self.app = app  # 引用主应用实例

    def run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('192.168.1.186', 8888))
        self.server_socket.listen(5)
        print("TCP 服务器已启动，等待连接...")

        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"连接来自: {addr}")
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                data_text = data[:7]
                self.app.received_data = data_text
                print(data_text)# 将接收到的数据存储到主应用实例中
                self.app.compare_p01c01_content()  # 自动对比 P01C01 内容
            client_socket.close()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Play")
        self.root.geometry("530x880")
        self.root.configure(bg="#2F2F2F")

        self.TCP_HOST = '192.168.1.186'  # 监听所有网络接口
        self.TCP_PORT = 8888  # TCP 服务器端口
        self.comm = KRcc.Commu("TCP 192.168.1.120")

        # 创建顶部的按钮
        self.add_button = tk.Button(root, text="添加运镜", command=self.add_row,bg="#808080")
        self.add_button.grid(row=0, column=0, padx=3, pady=3)

        self.connect_button = tk.Button(root, text="开启机械臂", command=self.connect,bg="#808080")
        self.connect_button.grid(row=0, column=1, padx=3, pady=3)

        self.duan_button = tk.Button(root, text="关闭机械臂", command=self.duan,bg="#808080")
        self.duan_button.grid(row=0, column=2, padx=3, pady=3)

        self.position_button = tk.Button(root, text=" 连接vz ", command=self.start_tcp_server,bg="#808080")
        self.position_button.grid(row=0, column=3, padx=3, pady=3)

        # 创建一个 Frame 用于放置动态添加的行
        self.frame = tk.Frame(root)
        self.frame.grid(row=1, column=0, columnspan=4, sticky="nsew")
        self.image = PhotoImage(file="55.png")
        self.label = tk.Label(root, image=self.image)
        self.label.grid(row=2, column=0, columnspan=4, sticky="nsew")


        # 创建一个 Canvas 用于滚动
        self.canvas = tk.Canvas(self.frame,width=510,height=600)
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

    def add_row(self):
        # 创建固定文本和文本输入框
        label_program = tk.Label(self.inner_frame, text=f"P0{self.row_count}C01运镜名:",bg="#808080")
        label_program.grid(row=self.row_count, column=0, padx=5, pady=5)

        entry_program = tk.Entry(self.inner_frame)
        entry_program.grid(row=self.row_count, column=1, padx=5, pady=5)
        self.program_entries.append(entry_program)

        label_speed = tk.Label(self.inner_frame, text="运行速度:",bg="#808080")
        label_speed.grid(row=self.row_count, column=2, padx=5, pady=5)

        entry_speed = tk.Entry(self.inner_frame,width=5)
        entry_speed.grid(row=self.row_count, column=3, padx=5, pady=5)
        self.speed_entries.append(entry_speed)

        # 创建按钮
        print_button = tk.Button(self.inner_frame, text="回到起点",bg="#808080", command=lambda: self.print_program_and_speed(entry_program.get(), entry_speed.get()))
        print_button.grid(row=self.row_count, column=4, padx=5, pady=5)

        print_speed_button = tk.Button(self.inner_frame, text="开始运行",bg="#808080", command=lambda: self.print_speed(entry_speed.get()))
        print_speed_button.grid(row=self.row_count, column=5, padx=5, pady=5)

        # 更新行号
        self.row_count += 1

        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def print_program_and_speed(self, program, speed):
        self.comm.command(f"SPEED {speed}")
        self.comm.command(f"EXECUTE {program}")


    def print_speed(self, speed):
        self.comm.command(f"PULSE 2666")

    def connect(self):
        self.comm.command(f"ZPOWER ON")
    def duan(self):
        self.comm.command(f"ZPOWER OFF")

    def start_tcp_server(self):
        # 启动 TCP 服务器线程
        self.server_thread = TCPServerThread(self)
        self.server_thread.start()
        print("TCP 服务器线程已启动")

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
        # 从文件加载保存的数据
        try:
            with open("program_data.json", "r", encoding="utf-8") as file:
                data = json.load(file)



                for program, speed in data:
                    self.add_row()

                    self.program_entries[-1].insert(0, program)
                    self.speed_entries[-1].insert(0, speed)

        except FileNotFoundError:
            print("未找到保存的数据文件")

    def save_data(self):
        # 保存数据到文件
        data = []

        for program_entry, speed_entry in zip(self.program_entries, self.speed_entries):
            data.append((program_entry.get(), speed_entry.get()))
        with open("program_data.json", "w") as file:
            json.dump(data, file)
            print("33:", data)
        with open("program_data.json", "r", encoding="utf-8") as file:
            datax = json.load(file)
            print("11:", datax)
            filtered_data = [sublist for sublist in datax if any(sublist)]
            print("22:",filtered_data)
        with open('program_data.json', 'w', encoding='utf-8') as file:
            json.dump(filtered_data, file, ensure_ascii=False, indent=4)
    def on_close(self):
        # 窗口关闭时保存数据
        self.save_data()
        self.root.destroy()




if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()