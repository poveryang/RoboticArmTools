import os
import subprocess
import shutil

def clean_temp_files():
    """清理临时文件和目录"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['main.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已清理 {dir_name} 目录")
    
    for file_name in files_to_clean:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"已清理 {file_name} 文件")

def main():
    print("开始打包流程...")
    
    # 1. 清理临时文件
    clean_temp_files()
    
    # 2. 使用 PyInstaller 构建单文件
    subprocess.run(['pyinstaller', '--onefile', '--noconsole', 'main.py'], check=True)
    print("已构建 exe 文件")
    
    # 3. 创建 release 目录
    if not os.path.exists('release'):
        os.makedirs('release')
    print("已创建 release 目录")
    
    # 4. 复制文件到 release 目录
    # 复制 exe 文件
    shutil.copy2('dist/main.exe', 'release/RoboticArmTools.exe')
    print("已复制 exe 文件")
    
    # 复制资源目录
    for dir_name in ['assets', 'gkasnap', 'logs']:
        if os.path.exists(dir_name):
            shutil.copytree(dir_name, f'release/{dir_name}', dirs_exist_ok=True)
            print(f"已复制 {dir_name} 目录")
    
    # 5. 再次清理临时文件
    clean_temp_files()
    
    print("打包完成！")

if __name__ == '__main__':
    main() 