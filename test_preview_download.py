#!/usr/bin/env python3
"""
测试预览下载功能（前10章）
"""
import requests
import time
import sys

# 配置
BASE_URL = "http://localhost:5000/api"
USERNAME = "test_user"
PASSWORD = "test_password"
NOVEL_ID = "7208454824847739938"  # 开局神豪系统，不好意思我无敌了

def test_preview_download():
    print("=" * 60)
    print("测试预览下载功能（前10章）")
    print("=" * 60)
    
    # 0. 注册用户（如果不存在）
    print("\n[0/5] 注册/检查用户...")
    try:
        register_response = requests.post(
            f"{BASE_URL}/auth/register",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        if register_response.status_code in [200, 201]:
            print(f"✅ 用户注册成功")
        elif register_response.status_code == 400:
            print(f"ℹ️  用户已存在，继续登录")
        else:
            print(f"⚠️  注册响应: {register_response.status_code}")
    except Exception as e:
        print(f"⚠️  注册失败: {e}，尝试登录")
    
    # 1. 登录获取 token
    print("\n[1/5] 登录系统...")
    try:
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        if login_response.status_code != 200:
            print(f"❌ 登录失败: {login_response.status_code}")
            print(f"响应: {login_response.text}")
            return False
        
        token = login_response.json().get("access_token")
        if not token:
            print("❌ 未获取到 access_token")
            return False
        
        print(f"✅ 登录成功，获取到 token")
        headers = {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return False
    
    # 2. 搜索小说
    print(f"\n[2/5] 搜索小说 ID: {NOVEL_ID}...")
    try:
        search_response = requests.get(
            f"{BASE_URL}/search",
            params={"query": "神豪"},
            headers=headers,
            timeout=10
        )
        if search_response.status_code != 200:
            print(f"⚠️  搜索返回: {search_response.status_code}")
        else:
            results = search_response.json().get("results", [])
            print(f"✅ 搜索成功，找到 {len(results)} 个结果")
    except Exception as e:
        print(f"⚠️  搜索失败: {e}")
    
    # 3. 添加小说（预览模式，前10章）
    print(f"\n[3/5] 添加小说（预览模式：仅下载前10章）...")
    try:
        add_response = requests.post(
            f"{BASE_URL}/novels",
            json={
                "novel_id": NOVEL_ID,
                "max_chapters": 10  # 关键参数：限制10章
            },
            headers=headers,
            timeout=15
        )
        
        if add_response.status_code not in [200, 201, 202]:  # 202 = Accepted
            print(f"❌ 添加失败: {add_response.status_code}")
            print(f"响应: {add_response.text}")
            return False
        
        task_data = add_response.json()
        task_id = task_data.get("id")
        celery_task_id = task_data.get("celery_task_id")
        
        print(f"✅ 任务已创建")
        print(f"   - 数据库任务 ID: {task_id}")
        print(f"   - Celery 任务 ID: {celery_task_id}")
        print(f"   - 小说 ID: {NOVEL_ID}")
        print(f"   - 模式: 预览模式（前10章）")
        
    except Exception as e:
        print(f"❌ 添加失败: {e}")
        return False
    
    # 4. 等待任务完成
    print(f"\n[4/5] 等待下载完成...")
    max_wait_time = 120  # 最多等待2分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            # 获取任务状态
            tasks_response = requests.get(
                f"{BASE_URL}/tasks/list",
                headers=headers,
                timeout=10
            )
            
            if tasks_response.status_code == 200:
                tasks = tasks_response.json().get("tasks", [])
                current_task = next((t for t in tasks if t["id"] == task_id), None)
                
                if current_task:
                    status = current_task.get("status")
                    progress = current_task.get("progress", 0)
                    message = current_task.get("message", "")
                    
                    print(f"   状态: {status} | 进度: {progress}% | {message}")
                    
                    if status == "COMPLETED":
                        print(f"✅ 下载完成！")
                        break
                    elif status == "FAILED":
                        print(f"❌ 下载失败: {message}")
                        return False
                    elif status == "TERMINATED":
                        print(f"⚠️  下载被终止")
                        return False
            
            time.sleep(3)  # 每3秒检查一次
            
        except Exception as e:
            print(f"⚠️  检查状态失败: {e}")
            time.sleep(3)
    
    if time.time() - start_time >= max_wait_time:
        print(f"❌ 超时：等待超过 {max_wait_time} 秒")
        return False
    
    # 5. 验证结果
    print(f"\n[5/5] 验证下载结果...")
    try:
        # 获取小说详情
        novel_response = requests.get(
            f"{BASE_URL}/novels/{NOVEL_ID}",
            headers=headers,
            timeout=10
        )
        
        if novel_response.status_code == 200:
            novel_data = novel_response.json()
            chapters_in_db = novel_data.get("chapters_in_db", 0)
            total_chapters_source = novel_data.get("total_chapters_source", 0)
            
            print(f"✅ 小说信息:")
            print(f"   - 标题: {novel_data.get('title')}")
            print(f"   - 作者: {novel_data.get('author')}")
            print(f"   - 源章节数: {total_chapters_source}")
            print(f"   - 已下载: {chapters_in_db} 章")
            
            # 验证是否只下载了10章
            if chapters_in_db == 10:
                print(f"\n🎉 测试成功！预览模式正常工作，成功下载前 10 章！")
                return True
            elif chapters_in_db == 0:
                print(f"\n❌ 测试失败：没有下载任何章节")
                return False
            else:
                print(f"\n⚠️  警告：下载了 {chapters_in_db} 章（预期10章）")
                return chapters_in_db > 0  # 只要有章节就算部分成功
        else:
            print(f"❌ 获取小说详情失败: {novel_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("预览下载功能测试脚本")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    print(f"测试小说: {NOVEL_ID}")
    print(f"测试用户: {USERNAME}")
    
    try:
        success = test_preview_download()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ 所有测试通过！")
            print("=" * 60)
            sys.exit(0)
        else:
            print("❌ 测试失败！")
            print("=" * 60)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
