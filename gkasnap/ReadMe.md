## 1.调用方式
使用subprocess.Popen打开,参数包括gkasnap.exe路径，以及图片保存路径，需要使用父子进程分离方式启动。gkasnap.exe会在没有检测到心跳时自动退出。
加入设置图像保存路径为，D:/gka_snap，则会在该目录会生成logs文件夹，记录日志，同时当有snap指令时会保存snap.jpg文件。

## 2.通信方式
通信方式采用命名管道，管道名称为\\.\pipe\GkSnapPipe，指令有两个：
1. heartbeat，周期性发送，让软件知道python主线程处于alive状态。
2. snap,需要时调用，会保存snap.jpg在指定路径，没有snap.jpg则会创建，有则覆盖。

## 3.例程
见gkasnap_client.py