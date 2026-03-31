"""
检查服务器上的文件是否正确
"""
import os
import paramiko
import sys

def check_server_files():
    host = os.getenv("HUB_SERVER_IP", "localhost")
    username = "root"
    
    print("=" * 60)
    print(f"检查服务器文件: {host}")
    print("=" * 60)
    
    try:
        # 连接服务器
        print("\n连接服务器...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试使用密钥或密码连接
        try:
            client.connect(host, username=username, timeout=10)
        except:
            print("请手动输入密码:")
            import getpass
            password = getpass.getpass()
            client.connect(host, username=username, password=password, timeout=10)
        
        print("✅ 连接成功")
        
        # 检查文件内容
        files_to_check = [
            "/www/wwwroot/hub/hub_server/api/routes.py",
            "/www/wwwroot/hub/hub_server/config.py",
            "/www/wwwroot/hub/.env"
        ]
        
        for filepath in files_to_check:
            print(f"\n检查: {filepath}")
            stdin, stdout, stderr = client.exec_command(f"cat {filepath}")
            content = stdout.read().decode('utf-8', errors='replace')
            
            if "cosine_similarity" in content:
                print("  ✅ 包含 cosine_similarity 函数")
            elif "GLM_API_KEY" in content:
                print("  ✅ 包含 API Key 配置")
                # 检查是否使用新的 API Key
                if "GLM_API_KEY" not in content:
                    print("  ✅ 使用新的 API Key")
                else:
                    print("  ⚠️  可能使用旧的 API Key")
            elif "EMBEDDING_DIMENSIONS" in content and "2048" in content:
                print("  ✅ 支持 2048 维")
            else:
                print("  ⚠️  请手动检查")
        
        # 检查进程
        print("\n检查服务进程...")
        stdin, stdout, stderr = client.exec_command("ps aux | grep uvicorn")
        processes = stdout.read().decode('utf-8')
        if "uvicorn" in processes:
            print("  ✅ uvicorn 进程正在运行")
            for line in processes.split('\n'):
                if 'uvicorn' in line and 'grep' not in line:
                    print(f"     {line[:80]}...")
        else:
            print("  ❌ uvicorn 进程未运行")
        
        # 检查日志
        print("\n检查最近日志...")
        stdin, stdout, stderr = client.exec_command("cd /www/wwwroot/hub && tail -20 hub.log 2>/dev/null || echo '日志文件不存在'")
        logs = stdout.read().decode('utf-8', errors='replace')
        if logs and '不存在' not in logs:
            print("  最近日志:")
            for line in logs.split('\n')[-10:]:
                if line.strip():
                    print(f"     {line}")
        else:
            print("  ⚠️  无法读取日志")
        
        client.close()
        print("\n✅ 检查完成")
        
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print("\n请手动 SSH 到服务器检查:")
        print(f"  ssh root@{host}")
        print(f"  cd /www/wwwroot/hub")
        print(f"  cat hub_server/api/routes.py | grep cosine_similarity")

if __name__ == "__main__":
    check_server_files()
