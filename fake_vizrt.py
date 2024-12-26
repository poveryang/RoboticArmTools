import socket

def client_program():
    host = 'localhost'  # 服务器的主机名或IP地址
    port = 8888  # 服务器的端口号

    client_socket = socket.socket()  # 实例化一个新的socket
    try:
        client_socket.connect((host, port))  # 连接到服务端
        print("连接到服务器成功！")

        message = 'P01C01T'  # 需要发送给服务端的信息
        while message.lower().strip() != '再见':
            client_socket.send(message.encode())  # 发送数据
            data = client_socket.recv(1024).decode()  # 接收响应

            print('从服务器接收到的数据：' + data)  # 显示接收到的数据

            message = input(" -> ")  # 再次输入要发送的数据

    except ConnectionRefusedError:
        print("无法连接到服务器，请确保服务端已经启动")
    finally:
        client_socket.close()  # 关闭连接

if __name__ == '__main__':
    client_program()