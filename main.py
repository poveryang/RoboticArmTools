# -*- coding: utf-8 -*-
import json
import logging
import os
from datetime import datetime
# import clr
# clr.AddReference("krcc64")
# import KRcc
import socket
import threading
import tkinter as tk
from tkinter import ttk, Label, filedialog, PhotoImage, messagebox
from tkinter.font import Font
import time

from PIL import Image, ImageTk
from gkasnap.gkasnap_client import GKASnap

# 加载配置文件
def load_config():
    try:
        with open('ip_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        messagebox.showerror("错误", "未找到配置文件 ip_config.json")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("错误", "配置文件格式错误")
        return None

# 获取配置
config = load_config()
if config is None:
    exit(1)

# Get the current date to use in the log file name
current_date = datetime.now().strftime('%Y-%m-%d')
log_filename = f'./logs/robotic_arm_{current_date}.log'

# Check if the log file already exists
filemode = 'a' if os.path.exists(log_filename) else 'w'


# Initialize logging
logging.basicConfig(
    filename=log_filename,       # Log file name
    level=logging.INFO,          # Log level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log format: timestamp - log level - message
    encoding='utf-8',            # Specify log file encoding as utf-8
    filemode=filemode            # Open the log file in write mode to overwrite existing content
)

class TCPServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.daemon = True
        self.server_socket = None
        self.app = app  # 引用主应用实例

    def run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((config['tcp_server']['ip'], config['tcp_server']['port']))
        self.server_socket.listen(5)
        logging.info("TCP server started and waiting for connections...")
        self.app.update_vizrt_button("listening")

        while True:
            client_socket, addr = self.server_socket.accept()
            logging.info(f"Connection established from: {addr}")
            self.app.update_vizrt_button("connected")

            try:
                while True:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break

                    logging.info(f"Received command: {data}")
                    data_text = data[:7]
                    self.app.received_data = data_text
                    self.app.compare_p01c01_content()  # 自动对比 P01C01 内容
            except ConnectionResetError:
                logging.warning(f"Connection forcibly closed by remote host: {addr}")
            finally:
                client_socket.close()
                logging.info(f"Connection closed: {addr}")
                self.app.update_vizrt_button("listening")

class App:
    def __init__(self, root):
        self.win_width = 700
        self.win_height = 800
        self.root = root
        self.root.title("Auto Play")
        self.root.geometry(f"{self.win_width}x{self.win_height}")
        self.root.resizable(False, False)
        self.root.configure(bg="#252525")

        # 创建菜单栏
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # 创建文件菜单
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="打开", command=self.open_file)
        self.file_menu.add_command(label="保存", command=self.save_data)
        self.file_menu.add_command(label="另存为", command=self.save_as_file)

        # 加载 Reset 按钮图标
        reset_icon = Image.open("assets/Reset.png")
        reset_icon = reset_icon.resize((60, 32))
        self.reset_icon_image = ImageTk.PhotoImage(reset_icon)
        
        # 创建灰色版本的 Reset 图标
        reset_gray_icon = reset_icon.copy()
        reset_gray_icon = reset_gray_icon.convert('LA')  # 转换为灰度图
        reset_gray_icon = reset_gray_icon.resize((60, 32))
        self.reset_gray_icon_image = ImageTk.PhotoImage(reset_gray_icon)

        self.server_active = False  # 跟踪服务端是否活跃
        self.on_air = False         # 跟踪 on-air 状态

        # TODO: 实例化 KRcc.Commu 类，用于与机械臂通信；示例中先用 MockComm
        self.comm = MockComm()
        # self.comm = KRcc.Commu(f"TCP {config['robotic_arm']['ip']}")

        # 初始化采集卡
        self.save_path = "./captured_images"
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        self.gka_snap = GKASnap(self.save_path)
        # 启动采集卡
        if not self.gka_snap.start():
            messagebox.showwarning("警告", "采集卡启动失败，图片上传功能将不可用")

        # 1. 创建顶部 Frame 来放置图片
        self.top_image_frame = tk.Frame(self.root, bg="#252525")
        self.top_image_frame.grid(row=0, column=0, sticky="ew")

        # Load and resize the header image to the window width
        header_image_path = "assets/header_image.png"
        header_image = Image.open(header_image_path)
        header_image = header_image.resize(
            (self.win_width, int(header_image.height * (self.win_width / header_image.width))))
        self.header_image = ImageTk.PhotoImage(header_image)

        # Create Label to display the header image
        self.header_label = Label(self.top_image_frame, image=self.header_image, borderwidth=0)
        self.header_label.grid(row=0, column=0, sticky="ew")

        # 2.创建顶部控件的 Frame
        self.top_frame = tk.Frame(self.root, bg="#252525")
        self.top_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=20)
        button_width = 120   # 按钮宽度设置为8个字符宽
        button_height = 50  # 按钮高度设置为2个字符高

        # 2.1. Vizrt 按钮(启动 TCP 服务器)
        self.vizrt_on_icon = Image.open("assets/Vizrt-G.png")
        self.vizrt_on_icon = self.vizrt_on_icon.resize((button_width, button_height))
        self.vizrt_on_icon_image = ImageTk.PhotoImage(self.vizrt_on_icon)

        self.vizrt_off_icon = Image.open("assets/Vizrt-W.png")
        self.vizrt_off_icon = self.vizrt_off_icon.resize((button_width, button_height))
        self.vizrt_off_icon_image = ImageTk.PhotoImage(self.vizrt_off_icon)

        self.vizrt_listening_icon = Image.open("assets/Vizrt-R.png")
        self.vizrt_listening_icon = self.vizrt_listening_icon.resize((button_width, button_height))
        self.vizrt_listening_icon_image = ImageTk.PhotoImage(self.vizrt_listening_icon)

        # button of Vizrt
        self.btn_vizrt = tk.Button(
            self.top_frame,
            image=self.vizrt_off_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.start_tcp_server
        )
        self.btn_vizrt.image = self.vizrt_off_icon_image  # 保留引用
        self.btn_vizrt.grid(row=0, column=0)

        # 2.2. ON AIR 按钮
        self.on_air_on_icon = Image.open("assets/OnAir-R.png")
        self.on_air_on_icon = self.on_air_on_icon.resize((button_width, button_height))
        self.on_air_on_icon_image = ImageTk.PhotoImage(self.on_air_on_icon)

        self.on_air_off_icon = Image.open("assets/OnAir-W.png")
        self.on_air_off_icon = self.on_air_off_icon.resize((button_width, button_height))
        self.on_air_off_icon_image = ImageTk.PhotoImage(self.on_air_off_icon)

        # button of ON AIR
        self.btn_on_air = tk.Button(
            self.top_frame,
            image=self.on_air_off_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.update_on_air_status
        )
        self.btn_on_air.image = self.on_air_off_icon_image
        self.btn_on_air.grid(row=0, column=1)

        # 2.3. Pause 按钮
        # Load the play and pause icons
        play_icon = Image.open("assets/Play.png")
        play_icon = play_icon.resize((button_height, button_height))
        self.play_icon_image = ImageTk.PhotoImage(play_icon)

        pause_icon = Image.open("assets/Pause.png")
        pause_icon = pause_icon.resize((button_height, button_height))
        self.pause_icon_image = ImageTk.PhotoImage(pause_icon)

        # button of Pause/Play
        self.btn_pause = tk.Button(
            self.top_frame,
            image=self.pause_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.pause
        )
        self.btn_pause.image = self.pause_icon_image
        self.btn_pause.grid(row=0, column=2)

        # 2.4. 添加运镜按钮
        add_icon = Image.open("assets/Add.png")
        add_icon = add_icon.resize((button_width, button_height))
        add_icon_image = ImageTk.PhotoImage(add_icon)

        # button of Add
        self.add_button = tk.Button(
            self.top_frame,
            image=add_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.add_row
        )
        self.add_button.image = add_icon_image
        self.add_button.grid(row=0, column=3)

        # 2.5. Home 按钮
        home_icon = Image.open("assets/Home.png")
        home_icon = home_icon.resize((button_width, button_height))
        home_icon_image = ImageTk.PhotoImage(home_icon)

        # button of Home
        self.home_button = tk.Button(
            self.top_frame,
            image=home_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.home
        )
        self.home_button.image = home_icon_image
        self.home_button.grid(row=0, column=4)

        # 2.6. 统一开始运行按钮
        start_all_icon = Image.open("assets/Start-All.png")
        start_all_icon = start_all_icon.resize((button_width, button_height))
        self.start_all_icon_image = ImageTk.PhotoImage(start_all_icon)  # 保存为实例变量
        
        # 创建灰色版本的 Start-All 图标
        start_all_gray_icon = start_all_icon.copy()
        start_all_gray_icon = start_all_gray_icon.convert('LA')  # 转换为灰度图
        start_all_gray_icon = start_all_gray_icon.resize((button_width, button_height))
        self.start_all_gray_icon_image = ImageTk.PhotoImage(start_all_gray_icon)

        # button of Start All
        self.start_all_button = tk.Button(
            self.top_frame,
            image=self.start_all_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=self.start_all,
            state=tk.DISABLED  # 初始状态设为禁用
        )
        self.start_all_button.image = self.start_all_icon_image
        self.start_all_button.grid(row=0, column=5)

        # 调整列权重以实现居中
        for i in range(5):
            self.top_frame.grid_columnconfigure(i, weight=1)
        self.top_frame.grid_columnconfigure(2, weight=2)

        # 3. Create a frame to hold the canvas and scrollbar
        self.program_frame = tk.Frame(root, bg="#252525")
        self.program_frame.grid(row=2, column=0, columnspan=5, sticky="ew")

        # Create a canvas
        self.canvas = tk.Canvas(
            self.program_frame,
            width=self.win_width-20,
            bg="#252525",
            height=525,
            borderwidth=0,
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create a scrollbar
        style = ttk.Style()   # Create a style
        style.theme_use('default')

        # Customize the scrollbar background and slider (thumb) background
        style.configure("Vertical.TScrollbar", background="#252525", troughcolor="#252525")
        style.map("Vertical.TScrollbar",
                  background=[('active', '#404040'), ('!active', '#252525')],
                  troughcolor=[('active', '#404040'), ('!active', '#252525')])
        self.scrollbar = ttk.Scrollbar(self.program_frame,
                                       orient="vertical",
                                       command=self.canvas.yview,
                                        style="Vertical.TScrollbar"
                                       )
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the canvas to use the scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Create a frame inside the canvas(program rows will be placed inside this frame)
        self.inner_frame = tk.Frame(self.canvas, bg="#252525")
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        # Register the validation function
        self.validate_speed_cmd = root.register(self.validate_speed_input)

        # 配置列宽
        self.column_config = [
            {"weight": 1, "minsize": 10, "width": 13},  # 截图列
            {"weight": 1, "minsize": 8, "width": 10},    # Vizrt指令列
            {"weight": 1, "minsize": 10, "width": 15},  # 运镜名列
            {"weight": 1, "minsize": 10, "width": 10},   # 运行速度列
            {"weight": 1, "minsize": 10, "width": 15},  # 备注列
            {"weight": 1, "minsize": 10, "width": 8},  # 控制列
            {"weight": 1, "minsize": 5, "width": 5},    # 清除列
            {"weight": 1, "minsize": 5, "width": 5},    # 删除列
        ]

        # 创建表头
        self.create_table_header()

        # 4. 创建底部锁定按钮
        # Load the lock and unlock icons
        self.lock_icon = Image.open("assets/Lock.png")
        self.lock_icon = self.lock_icon.resize((30, 30))
        self.lock_icon_image = ImageTk.PhotoImage(self.lock_icon)

        self.unlock_icon = Image.open("assets/Unlock.png")
        self.unlock_icon = self.unlock_icon.resize((30, 30))
        self.unlock_icon_image = ImageTk.PhotoImage(self.unlock_icon)

        # Create the lock button
        self.lock_button = tk.Button(
            self.root,
            image=self.unlock_icon_image,
            command=self.toggle_lock_screen,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
        )
        self.lock_button.place(relx=0, rely=1, anchor='sw')

        # Load the upload icon
        upload_icon = Image.open("assets/Upload-image.png")
        icon_width, icon_height = 30, 20  # Set the desired size for the icon
        upload_icon = upload_icon.resize((icon_width, icon_height))
        new_image = Image.new("RGBA", (90, 60), (0, 0, 0, 0))
        x = (90 - icon_width) // 2
        y = (60 - icon_height) // 2
        new_image.paste(upload_icon, (x, y), upload_icon)
        self.upload_icon_image = ImageTk.PhotoImage(new_image)

        # 初始化行号
        self.row_count = 1

        # 存储输入框的引用
        self.program_entries = []
        self.speed_entries = []

        # 加载保存的数据（如果存在）
        self.load_data()

        # 如果没有加载到任何数据，则添加初始行
        if self.row_count == 1:
            self.add_row()

        # TCP 服务器线程
        self.server_thread = None

        # 存储接收到的数据
        self.received_data = None

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # Vizrt 按钮的回调函数
    def start_tcp_server(self):
        if not self.server_active:
            self.server_thread = TCPServerThread(self)
            self.server_thread.start()
            self.server_active = True
            self.update_vizrt_button("listening")
            self.root.update_idletasks()  # 强制 GUI 刷新
            print("TCP 服务器已启动")
        else:
            print("TCP 服务器已经在运行")

    def update_vizrt_button(self, state):
        if state == "listening":
            self.btn_vizrt.config(image=self.vizrt_listening_icon_image)
        elif state == "connected":
            self.btn_vizrt.config(image=self.vizrt_on_icon_image)
        else:
            self.btn_vizrt.config(image=self.vizrt_off_icon_image)

    def update_on_air_status(self):
        if self.on_air:
            # Turn off the robotic arm
            logging.info("Preparing to send command: ZPOWER OFF")
            self.comm.command("ZPOWER OFF")
            self.on_air = False
            self.btn_on_air.config(image=self.on_air_off_icon_image)  # Change to "off" image
            # 禁用按钮
            self.start_all_button.config(state=tk.DISABLED, image=self.start_all_gray_icon_image)
            # 禁用所有 Reset 按钮
            for row in range(self.row_count - 1):
                control_frame = self.inner_frame.grid_slaves(row=row + 1, column=5)[0]
                for widget in control_frame.winfo_children():
                    if isinstance(widget, tk.Button):
                        widget.config(state=tk.DISABLED, image=self.reset_gray_icon_image)
        else:
            # Turn on the robotic arm
            logging.info("Preparing to send commands: ZPOWER ON, EXECUTE gkamain")
            self.comm.command("ZPOWER ON")
            self.comm.command("EXECUTE gkamain")
            self.on_air = True
            self.btn_on_air.config(image=self.on_air_on_icon_image)  # Change to "on" image
            # 启用按钮
            self.start_all_button.config(state=tk.NORMAL, image=self.start_all_icon_image)
            # 启用所有 Reset 按钮
            for row in range(self.row_count - 1):
                control_frame = self.inner_frame.grid_slaves(row=row + 1, column=5)[0]
                for widget in control_frame.winfo_children():
                    if isinstance(widget, tk.Button):
                        widget.config(state=tk.NORMAL, image=self.reset_icon_image)

    # 暂停按钮的回调函数
    def pause(self):
        logging.info("Preparing to send command: SWITCH CS for pause or continue check")
        retrun, srun = self.comm.command("SWITCH CS")
        logging.info(f"Received response: {srun}")

        # 判断返回里是否含有 'ON'
        claa = 'ON'
        all_words_exist = all(word.lower() in srun.lower() for word in claa)
        if all_words_exist:
            self.comm.command("HOLD")
            self.btn_pause.config(image=self.play_icon_image)
            self.btn_pause.image = self.play_icon_image
        else:
            self.comm.command("CONTINUE")
            self.btn_pause.config(image=self.pause_icon_image)
            self.btn_pause.image = self.pause_icon_image

    # 添加运镜按钮的回调函数
    def add_row(self):
        current_index = len(self.program_entries)

        # 1. 上传图标按钮
        icon_label = tk.Label(self.inner_frame, image=self.upload_icon_image, bg="#252525", width=self.column_config[0]["width"])
        icon_label.image = self.upload_icon_image
        icon_label.grid(row=self.row_count, column=0, padx=2, pady=2, sticky='ew')
        icon_label.bind("<Button-1>", lambda event, row=self.row_count, label=icon_label: self.upload_image(row, label))

        # 2. Vizrt指令 label
        label_vizrt = tk.Label(
            self.inner_frame,
            text=f"P0{self.row_count}C01",
            bg="#252525",
            fg="white",
            font=Font(family="Microsoft YaHei", size=10),
            width=self.column_config[1]["width"]
        )
        label_vizrt.grid(row=self.row_count, column=1, padx=0, pady=2, sticky='ew')

        # 3. 运镜名输入框
        entry_program = tk.Entry(
            self.inner_frame,
            font=Font(family="Microsoft YaHei", size=9),
            highlightthickness=0,
            bd=0,
            bg="#303238",
            fg="white",
            width=self.column_config[2]["width"]
        )
        entry_program.grid(row=self.row_count, column=2, padx=2, pady=2, sticky='ew', ipady=4)
        self.program_entries.append(entry_program)

        # 4. 运行速度输入框 with validation
        entry_speed = tk.Entry(
            self.inner_frame,
            font=Font(family="Microsoft YaHei", size=9),
            highlightthickness=0,
            bd=0,
            bg="#303238",
            fg="white",
            width=self.column_config[3]["width"],
            validate="key",
            validatecommand=(self.validate_speed_cmd, '%P', '%W')
        )
        entry_speed.grid(row=self.row_count, column=3, padx=2, pady=2, sticky='ew', ipady=4)
        self.speed_entries.append(entry_speed)

        # 5. 备注输入框
        entry_note = tk.Entry(
            self.inner_frame,
            font=Font(family="Microsoft YaHei", size=9),
            highlightthickness=0,
            bd=0,
            bg="#303238",
            fg="white",
            width=self.column_config[4]["width"]
        )
        entry_note.grid(row=self.row_count, column=4, padx=2, pady=2, sticky='ew', ipady=4)

        # 6. 控制按钮的容器
        control_frame = tk.Frame(self.inner_frame, bg="#252525", width=self.column_config[5]["width"])
        control_frame.grid(row=self.row_count, column=5, padx=2, pady=2, sticky="ew")

        # 6.1 回到起点按钮
        btn_reset = tk.Button(
            control_frame,
            text='Reset',  # Set the text property
            image=self.reset_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=lambda: self.print_program_and_speed(entry_program.get(), entry_speed.get()),
            state=tk.DISABLED  # 初始状态设为禁用
        )
        btn_reset.image = self.reset_icon_image
        btn_reset.pack(side=tk.LEFT, padx=1, pady=2, anchor='center')

        # 7. 清除按钮
        clear_icon = Image.open("assets/Clear.png")
        clear_icon = clear_icon.resize((24, 24))
        clear_icon_image = ImageTk.PhotoImage(clear_icon)

        btn_clear = tk.Button(
            self.inner_frame,
            image=clear_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=lambda i=current_index: self.clear_row(i),
            width=self.column_config[6]["width"]
        )
        btn_clear.image = clear_icon_image
        btn_clear.grid(row=self.row_count, column=6, padx=1, pady=2, sticky='ew')

        # 8. 删除按钮
        delete_icon = Image.open("assets/Delete.png")
        delete_icon = delete_icon.resize((50, 32))
        delete_icon_image = ImageTk.PhotoImage(delete_icon)

        btn_delete = tk.Button(
            self.inner_frame,
            image=delete_icon_image,
            bg="#252525",
            activebackground="#252525",
            highlightthickness=0,
            highlightbackground="#252525",
            highlightcolor="#252525",
            borderwidth=0,
            relief=tk.FLAT,
            command=lambda i=current_index: self.delete_row(i),
            width=self.column_config[7]["width"]
        )
        btn_delete.image = delete_icon_image
        btn_delete.grid(row=self.row_count, column=7, padx=1, pady=2, sticky='ew')

        # 更新行号
        self.row_count += 1

        for index, config in enumerate(self.column_config):
            self.inner_frame.grid_columnconfigure(index, weight=config["weight"], minsize=config["minsize"])

        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # Home 按钮的回调函数
    # TODO: Wait for the actual command to be implemented
    def home(self):
        raise NotImplementedError("Home button functionality not implemented yet")

    def create_table_header(self):
        headers = ["截图", "Vizrt指令", "运镜名", "运行速度", "备注", "控制", "清除", "删除"]
        for index, header in enumerate(headers):
            label = tk.Label(
                self.inner_frame,
                text=header,
                bg="#252525",
                fg="white",
                font=('Microsoft YaHei', 10),
                width=self.column_config[index]["width"]
            )
            label.grid(row=0, column=index, sticky='nsew')
            self.inner_frame.grid_columnconfigure(index, weight=self.column_config[index]["weight"], minsize=self.column_config[index]["minsize"])

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

    def delete_row(self, row):
        # 获取当前所有行的原始Vizrt指令，以便后续重新分配
        original_vizrt_indices = []
        for r in range(1, self.row_count):
            vizrt_labels = [w for w in self.inner_frame.grid_slaves(row=r, column=1) if isinstance(w, tk.Label)]
            if vizrt_labels:
                text = vizrt_labels[0].cget("text")
                # 提取P后面的数字，例如从"P01C01"提取"01"
                try:
                    idx = int(text[1:3])
                    original_vizrt_indices.append(idx)
                except ValueError:
                    original_vizrt_indices.append(r)

        # 排除要删除的行
        if 0 <= row < len(original_vizrt_indices):
            del original_vizrt_indices[row]

        # 1) 删除UI
        for widget in self.inner_frame.grid_slaves(row=row + 1):
            widget.grid_forget()

        # 2) 从列表里 pop
        self.row_count -= 1
        self.program_entries.pop(row)
        self.speed_entries.pop(row)

        # 3) 把后续行的所有控件往上挪
        for r in range(row + 1, self.row_count + 1):
            for widget in self.inner_frame.grid_slaves(row=r + 1):
                widget.grid(row=r)

        # 4) 重新给后续行的"删除"和"清除"按钮更新 command
        for r in range(row, self.row_count):
            # 更新删除按钮
            delete_buttons = [w for w in self.inner_frame.grid_slaves(row=r + 1, column=7) if isinstance(w, tk.Button)]
            for btn in delete_buttons:
                btn.config(command=lambda i=r: self.delete_row(i))
            
            # 更新清除按钮
            clear_buttons = [w for w in self.inner_frame.grid_slaves(row=r + 1, column=6) if isinstance(w, tk.Button)]
            for btn in clear_buttons:
                btn.config(command=lambda i=r: self.clear_row(i))

        # 5) 更新 Vizrt 指令标签 - 保持原有编号顺序
        for r in range(row, self.row_count):
            vizrt_labels = [w for w in self.inner_frame.grid_slaves(row=r + 1, column=1) if isinstance(w, tk.Label)]
            for lbl in vizrt_labels:
                idx = r
                if idx < len(original_vizrt_indices):
                    # 使用原始编号，但保持格式统一
                    num = original_vizrt_indices[idx]
                    if num < 10:
                        lbl.config(text=f"P0{num}C01")
                    else:
                        lbl.config(text=f"P{num}C01")
                else:
                    # 如果没有原始编号可用，则使用当前行号
                    lbl.config(text=f"P0{r + 1}C01")

        # 6) 再次配置列宽 + 刷新 scrollregion
        for index, config in enumerate(self.column_config):
            self.inner_frame.grid_columnconfigure(index, weight=config["weight"], minsize=config["minsize"])
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def clear_row(self, row):
        # 确保 row 索引与实际位置匹配
        grid_row = row + 1
        
        # Clear the program entry
        if 0 <= row < len(self.program_entries):
            self.program_entries[row].delete(0, tk.END)

        # Clear the speed entry
        if 0 <= row < len(self.speed_entries):
            self.speed_entries[row].delete(0, tk.END)

        # Clear the note entry
        note_entries = [w for w in self.inner_frame.grid_slaves(row=grid_row, column=4) if isinstance(w, tk.Entry)]
        for entry in note_entries:
            entry.delete(0, tk.END)

        # Clear the screenshot label
        screenshot_labels = [w for w in self.inner_frame.grid_slaves(row=grid_row, column=0) if isinstance(w, tk.Label)]
        for label in screenshot_labels:
            label.config(image=self.upload_icon_image)
            label.image = self.upload_icon_image
            label.image_path = "未上传"

    def compare_p01c01_content(self):
        # 获取每行 P01C01 程序名中的内容并与 TCP 接收的数据对比
        local_data = ""
        if self.received_data == 'P01C01T':
            program_1 = self.program_entries[0].get()
            speed_1 = self.speed_entries[0].get()
            self.comm.command(f"SPEED " + speed_1)
            self.comm.command(f"EXECUTE " + program_1)
        if self.received_data == 'P02C01T':
            program_2 = self.program_entries[1].get()
            speed_2 = self.speed_entries[1].get()
            self.comm.command(f"SPEED " + speed_2)
            self.comm.command(f"EXECUTE " + program_2)
        if self.received_data == 'P03C01T':
            program_3 = self.program_entries[2].get()
            speed_3 = self.speed_entries[2].get()
            self.comm.command(f"SPEED " + speed_3)
            self.comm.command(f"EXECUTE " + program_3)
        if self.received_data == 'P04C01T':
            program_4 = self.program_entries[3].get()
            speed_4 = self.speed_entries[3].get()
            self.comm.command(f"SPEED " + speed_4)
            self.comm.command(f"EXECUTE " + program_4)
        if self.received_data == 'P05C01T':
            program_5 = self.program_entries[4].get()
            speed_5 = self.speed_entries[4].get()
            self.comm.command(f"SPEED " + speed_5)
            self.comm.command(f"EXECUTE " + program_5)
        if self.received_data == 'P06C01T':
            program_6 = self.program_entries[5].get()
            speed_6 = self.speed_entries[5].get()
            self.comm.command(f"SPEED " + speed_6)
            self.comm.command(f"EXECUTE " + program_6)
        if self.received_data == 'P07C01T':
            program_7 = self.program_entries[6].get()
            speed_7 = self.speed_entries[6].get()
            self.comm.command(f"SPEED " + speed_7)
            self.comm.command(f"EXECUTE " + program_7)
        if self.received_data == 'P08C01T':
            program_8 = self.program_entries[7].get()
            speed_8 = self.speed_entries[7].get()
            self.comm.command(f"SPEED " + speed_8)
            self.comm.command(f"EXECUTE " + program_8)
        if self.received_data == 'P09C01T':
            program_9 = self.program_entries[8].get()
            speed_9 = self.speed_entries[8].get()
            self.comm.command(f"SPEED " + speed_9)
            self.comm.command(f"EXECUTE " + program_9)
        if self.received_data == 'P10C01T':
            program_10 = self.program_entries[9].get()
            speed_10 = self.speed_entries[9].get()
            self.comm.command(f"SPEED " + speed_10)
            self.comm.command(f"EXECUTE " + program_10)
        if self.received_data == 'P11C01T':
            program_11 = self.program_entries[10].get()
            speed_11 = self.speed_entries[10].get()
            self.comm.command(f"SPEED " + speed_11)
            self.comm.command(f"EXECUTE " + program_11)
        if self.received_data == 'P99C99T':

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

            self.create_table_header()  # 重新创建表头
            self.row_count = 1  # 重置行号

            # 加载每一行数据
            for row_data in data:
                self.add_row()  # 添加新行

                # 设置截图
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
        top_image_frame_width = self.top_image_frame.winfo_width()
        top_image_frame_height = self.top_image_frame.winfo_height()
        top_frame_width = self.top_frame.winfo_width()
        top_frame_height = self.top_frame.winfo_height()

        width = self.root.winfo_width()
        height = self.root.winfo_height()
        # 提示用户是否保存数据
        if messagebox.askyesno("保存数据", "是否要保存当前参数？"):
            self.save_data()
        self.root.destroy()

    def upload_image(self, row, label):
        if getattr(self, 'locked', False):
            return  # Do nothing if the screen is locked

        # 使用采集卡进行采图
        if self.gka_snap.snap():
            # 等待图片保存完成
            time.sleep(0.5)
            # 构建图片路径
            filename = os.path.join(self.save_path, "snap.jpg")
            
            if os.path.exists(filename):
                # 加载采集的图片并调整为缩略图
                img = Image.open(filename)
                img.thumbnail((90, 60))
                photo_img = ImageTk.PhotoImage(img)

                # 更新 Label 的图像
                label.config(image=photo_img)
                label.image = photo_img  # 保留引用防止垃圾回收
                label.image_path = filename  # 保存图片路径
            else:
                messagebox.showerror("错误", "采图失败，未找到采集卡保存的图片")
        else:
            messagebox.showerror("错误", "采集卡采图失败")

    def toggle_lock_screen(self):
        self.locked = not getattr(self, 'locked', False)
        state = tk.DISABLED if self.locked else tk.NORMAL
        self.set_widgets_state(self.root, state)

        if self.locked:
            self.lock_button.config(image=self.lock_icon_image)
        else:
            self.lock_button.config(image=self.unlock_icon_image)

    def set_widgets_state(self, widget, state):
        skip_widgets = (
        self.lock_button, self.btn_vizrt, self.btn_on_air, self.btn_pause, self.add_button, self.home_button)
        for child in widget.winfo_children():
            if child not in skip_widgets and not isinstance(child, tk.Label):
                try:
                    if isinstance(child, tk.Button) and child.cget('text') == 'Reset':
                        continue  # Skip the reset buttons
                    child.config(state=state)
                except tk.TclError:
                    pass
            self.set_widgets_state(child, state)

    def validate_speed_input(self, new_value, widget_name):
        entry = self.root.nametowidget(widget_name)
        if new_value.isdigit():
            value = int(new_value)
            if value < 1:
                self.root.after(0, lambda: self.set_entry_value(entry, '1'))
                return False
            elif value > 50:
                self.root.after(0, lambda: self.set_entry_value(entry, '50'))
                return False
            return True
        elif new_value == "":
            return True
        else:
            return False

    def set_entry_value(self, entry, value):
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def start_all(self):
        for program_entry, speed_entry in zip(self.program_entries, self.speed_entries):
            program = program_entry.get()
            speed = speed_entry.get()
            self.print_program_and_speed(program, speed)

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)

                # 清除现有行数据
                for widget in self.inner_frame.winfo_children():
                    widget.destroy()

                self.create_table_header()  # 重新创建表头
                self.row_count = 1  # 重置行号
                self.program_entries = []  # 清空程序条目列表
                self.speed_entries = []    # 清空速度条目列表

                # 加载每一行数据
                for row_data in data:
                    self.add_row()  # 添加新行

                    # 设置截图
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

                messagebox.showinfo("成功", "配置文件加载成功")
            except Exception as e:
                messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")

    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(
            title="保存配置文件",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                data = []
                for row in range(self.row_count - 1):  # 遍历所有已添加的行
                    # 获取截图路径
                    screenshot_label = self.inner_frame.grid_slaves(row=row + 1, column=0)[0]
                    screenshot = getattr(screenshot_label, "image_path", "未上传")

                    # 获取运镜名
                    program = self.program_entries[row].get()

                    # 获取运行速度
                    speed_entry = self.speed_entries[row]
                    speed = speed_entry.get()
                    if speed == "范围:1-50":
                        speed = ""

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
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                messagebox.showinfo("成功", "配置文件保存成功")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置文件失败: {str(e)}")

# TODO: 用于模拟通信的类, 最后记得删除
class MockComm:
    def __init__(self):
        self.commands = {
            "ZPOWER ON": "Machine powered on",
            "ZPOWER OFF": "Machine powered off",
            "SPEED": lambda speed: f"Speed set to {speed}",
            "EXECUTE": lambda program: f"Executing {program}",
            "EXECUTE gkamain": "Executing gkamain",
            "PULSE 2666": "Pulse command received",
            "HOLD": "Holding",
            "SWITCH CS": "Switching CS",
            "CONTINUE": "Continuing"
        }
        self.switch_cs_state = "ON AIR"

    def command(self, cmd):
        if cmd in self.commands:
            print(f"Robotic arm command: {cmd}")
            if cmd == "SWITCH CS":
                response = self.switch_cs_state
                self.switch_cs_state = "OFF AIR" if self.switch_cs_state == "ON AIR" else "ON AIR"
                return True, response
            elif callable(self.commands[cmd]):
                return True, self.commands[cmd](cmd.split()[-1])
            else:
                return True, self.commands[cmd]
        else:
            print(f"Command not found: {cmd}")
            return False, ""

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()