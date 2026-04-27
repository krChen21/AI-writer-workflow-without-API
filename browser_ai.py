# -*- coding: utf-8 -*-
"""
AI交互模块：封装DeepSeek/通义千问的浏览器自动化交互逻辑
支持扩展新模型：只需实现 ask_模型名(prompt, status_callback, output_callback, new_chat, port) 函数并注册到 MODEL_FUNCS
"""
from playwright.sync_api import sync_playwright
import config

# ---------- 模型调用函数注册表 ----------
MODEL_FUNCS = {}

def register_model(name):
    """装饰器：注册模型调用函数"""
    def decorator(func):
        MODEL_FUNCS[name] = func
        return func
    return decorator

# ---------- DeepSeek 实现 ----------
@register_model("DeepSeek")
def ask_deepseek(prompt, status_callback, output_callback, new_chat=False, port=config.DEFAULT_PORT):
    """
    向DeepSeek提问并返回回复内容
    :param prompt: 提问的提示词
    :param status_callback: 状态回调函数（用于更新日志/状态）
    :param output_callback: 输出回调函数（用于显示回复内容）
    :param new_chat: 是否新建对话
    :param port: Chrome调试端口
    :return: AI回复内容（失败返回None）
    """
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            status_callback("DeepSeek: 已连接浏览器")
            context = browser.contexts[0]
            page = None
            for existing_page in context.pages:
                if "deepseek.com" in existing_page.url:
                    page = existing_page
                    break
            if not page:
                status_callback("错误: 未找到DeepSeek标签页")
                return None

            page.bring_to_front()

            if new_chat:
                try:
                    new_chat_btn = page.locator("div[tabindex='0']:has(span:has-text('开启新对话'))")
                    if not new_chat_btn.count():
                        new_chat_btn = page.locator("div, button").filter(has_text="开启新对话").first
                    if new_chat_btn.count():
                        new_chat_btn.click()
                        page.wait_for_timeout(1000)
                        status_callback("新对话已创建（按钮）")
                    else:
                        status_callback("未找到新建对话按钮，继续执行")
                except Exception as e2:
                    status_callback(f"按钮点击失败: {str(e2)[:30]}，继续执行")

            # 定位输入框
            input_selectors = [
                "textarea[placeholder*='提问']",
                "textarea[placeholder*='消息']",
                "textarea[placeholder*='输入']",
                "textarea[placeholder*='发消息']",
                "textarea.ds-textarea",
                "textarea",
            ]
            textarea = None
            for selector in input_selectors:
                loc = page.locator(selector).first
                if loc.count():
                    try:
                        loc.wait_for(state="visible", timeout=3000)
                        textarea = loc
                        break
                    except:
                        pass
            if not textarea:
                status_callback("未找到输入框")
                return None

            status_callback("正在输入提示词...")
            textarea.click()
            textarea.fill(prompt)
            page.evaluate("""
                (el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.focus();
                }
            """, textarea.element_handle())
            page.wait_for_timeout(300)

            status_callback("正在发送...")
            page.evaluate("""
                (el) => {
                    const keydown = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true });
                    const keypress = new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', bubbles: true });
                    const keyup = new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true });
                    el.dispatchEvent(keydown);
                    el.dispatchEvent(keypress);
                    el.dispatchEvent(keyup);
                    const beforeInput = new InputEvent('beforeinput', { inputType: 'insertLineBreak', bubbles: true });
                    el.dispatchEvent(beforeInput);
                }
            """, textarea.element_handle())
            page.wait_for_timeout(500)

            if textarea.input_value().strip():
                status_callback("回车未清空，尝试点击发送按钮...")
                send_selectors = [
                    "button[aria-label='发送']",
                    "button[aria-label='Send']",
                    "button.ds-icon-button:not(.ds-icon-button--disabled)",
                    "button[type='submit']"
                ]
                for sel in send_selectors:
                    btn = page.locator(sel).first
                    if btn.count():
                        try:
                            btn.click(timeout=2000)
                            break
                        except:
                            pass

            status_callback("等待 AI 回复...")
            assistant_reply = ""

            stop_btn = page.locator("button:has-text('停止'), button:has-text('Stop')")
            try:
                stop_btn.wait_for(state="visible", timeout=30000)
                status_callback("生成中...")
                stop_btn.wait_for(state="hidden", timeout=config.AI_REPLY_TIMEOUT * 1000)
                status_callback("生成完成")
            except:
                status_callback("监测内容变化...")
                last_text = ""
                stable = 0
                for _ in range(120):
                    msg = page.locator(".ds-markdown, .ds-message, .answer-content, .assistant-message").last
                    if msg.count():
                        current = msg.inner_text().strip()
                        if len(current) > 20:
                            if current == last_text:
                                stable += 1
                                if stable >= 3:
                                    break
                            else:
                                stable = 0
                                last_text = current
                    page.wait_for_timeout(1000)

            status_callback("读取回复内容...")
            reply = page.locator(".ds-markdown").last
            if not reply.count():
                reply = page.locator(".ds-message, .assistant-message, .answer-content").last
            if reply.count():
                assistant_reply = reply.inner_text().strip()
                if prompt in assistant_reply and len(assistant_reply) > len(prompt) + 10:
                    parts = assistant_reply.split(prompt)
                    if len(parts) > 1:
                        assistant_reply = parts[-1].strip()
            else:
                assistant_reply = "未能提取到回复"

            output_callback(f"【DeepSeek 回复】\n{assistant_reply}")
            status_callback("完成")
            return assistant_reply

        except Exception as e:
            status_callback(f"DeepSeek 出错: {str(e)[:30]}")
            return None

# ---------- 通义千问实现 ----------
@register_model("通义千问")
def ask_qianwen(prompt, status_callback, output_callback, new_chat=False, port=config.DEFAULT_PORT):
    """
    向通义千问提问并返回回复内容
    """
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            status_callback("千问: 已连接浏览器")
            context = browser.contexts[0]
            page = None
            for existing_page in context.pages:
                if "qianwen" in existing_page.url or "tongyi" in existing_page.url:
                    page = existing_page
                    break
            if not page:
                status_callback("错误: 未找到通义千问标签页")
                return None

            page.bring_to_front()

            if new_chat:
                try:
                    new_chat_btn = page.locator("button:has-text('新建对话')")
                    if new_chat_btn.count():
                        status_callback("新建对话中...")
                        new_chat_btn.first.click()
                        page.wait_for_timeout(1000)
                        status_callback("新对话已创建")
                    else:
                        status_callback("未找到新建对话按钮，可能已在新对话中")
                except Exception as e:
                    status_callback(f"新建对话失败: {str(e)[:50]}，继续执行")
            else:
                status_callback("千问: 保持当前对话...")

            input_selectors = [
                "textarea[placeholder*='输入']",
                "textarea[placeholder*='提问']",
                "textarea[placeholder*='消息']",
                "div[contenteditable='true']",
                "textarea",
            ]
            textarea = None
            for selector in input_selectors:
                loc = page.locator(selector).first
                if loc.count():
                    try:
                        loc.wait_for(state="visible", timeout=3000)
                        textarea = loc
                        break
                    except:
                        pass
            if not textarea:
                status_callback("未找到输入框")
                return None

            status_callback("正在输入提示词...")
            textarea.click()
            textarea.fill(prompt)
            page.evaluate("""
                (el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.focus();
                }
            """, textarea.element_handle())
            page.wait_for_timeout(300)

            status_callback("正在发送...")
            page.evaluate("""
                (el) => {
                    const keydown = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true });
                    const keypress = new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', bubbles: true });
                    const keyup = new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true });
                    el.dispatchEvent(keydown);
                    el.dispatchEvent(keypress);
                    el.dispatchEvent(keyup);
                    const beforeInput = new InputEvent('beforeinput', { inputType: 'insertLineBreak', bubbles: true });
                    el.dispatchEvent(beforeInput);
                }
            """, textarea.element_handle())
            page.wait_for_timeout(500)

            try:
                is_empty = page.evaluate("(el) => el.innerText?.trim() === '' || el.value?.trim() === ''", textarea.element_handle())
            except:
                is_empty = True
            if not is_empty:
                status_callback("回车未清空，尝试点击发送按钮...")
                send_selectors = [
                    "button[aria-label='发送']",
                    "button[aria-label='Send']",
                    "button:has-text('发送')",
                    "button[type='submit']",
                    ".send-btn",
                    ".chat-panel-send-btn"
                ]
                for sel in send_selectors:
                    btn = page.locator(sel).first
                    if btn.count():
                        try:
                            btn.click(timeout=2000)
                            break
                        except:
                            pass

            status_callback("等待千问回复...")
            assistant_reply = ""

            stop_btn = page.locator("button:has-text('停止')")
            try:
                if stop_btn.count():
                    stop_btn.first.wait_for(state="visible", timeout=30000)
                    status_callback("生成中...")
                    stop_btn.first.wait_for(state="hidden", timeout=config.AI_REPLY_TIMEOUT * 1000)
                    status_callback("生成完成（停止按钮消失）")
                else:
                    raise Exception("无停止按钮")
            except Exception:
                status_callback("未检测到停止按钮，使用内容稳定检测...")
                last_len = 0
                stable_count = 0
                for _ in range(180):
                    cur_elem = page.locator(".qk-markdown").last
                    if not cur_elem.count():
                        page.wait_for_timeout(3000)
                        continue
                    cur_text = cur_elem.inner_text().strip()
                    cur_len = len(cur_text)
                    if cur_len > 20:
                        if cur_len == last_len:
                            stable_count += 1
                            if stable_count >= config.STABLE_CHECK_TIMES:
                                status_callback("生成完成（内容稳定）")
                                break
                        else:
                            stable_count = 0
                            last_len = cur_len
                    else:
                        stable_count = 0
                        last_len = cur_len
                    page.wait_for_timeout(1000)
                else:
                    status_callback("等待超时，强制读取")

            status_callback("读取回复内容...")
            assistant_reply = page.locator(".qk-markdown").last.inner_text().strip()
            if not assistant_reply:
                assistant_reply = "未能提取到回复内容"

            output_callback(f"【通义千问 回复】\n{assistant_reply}")
            status_callback("完成")
            return assistant_reply

        except Exception as e:
            status_callback(f"千问 出错: {str(e)[:30]}")
            return None

# ---------- 通用调用接口 ----------
def ask_model(model_name, prompt, status_callback, output_callback, new_chat=False, port=config.DEFAULT_PORT):
    """
    通用模型调用函数
    :param model_name: 模型名称（需在 MODEL_FUNCS 中注册）
    :return: AI回复内容或None
    """
    if model_name not in MODEL_FUNCS:
        status_callback(f"错误: 未注册的模型 '{model_name}'，可用模型: {list(MODEL_FUNCS.keys())}")
        return None
    return MODEL_FUNCS[model_name](prompt, status_callback, output_callback, new_chat, port)