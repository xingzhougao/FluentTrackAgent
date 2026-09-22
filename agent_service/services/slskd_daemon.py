"""
SlskdDaemonManager 伴生守护进程管理服务
负责 slskd.exe 的自动部署、免感启动、静默后台运行与生命周期维护。
"""
import os
import sys
import time
import uuid
import zipfile
import logging
import asyncio
import subprocess
import httpx
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AgentLogger")


class SlskdDaemonManager:
    """slskd 伴生后台服务生命周期管理器"""

    def __init__(self, port: int = 5030):
        self.port = port
        self.api_url = f"http://127.0.0.1:{self.port}/api/v0"
        
        # 路径规划
        self.proj_root = Path(__file__).resolve().parent.parent.parent
        self.tools_dir = self.proj_root / "tools" / "slskd"
        self.exe_path = self.tools_dir / "slskd.exe"
        self.data_dir = self.tools_dir / "data"
        self.config_path = self.data_dir / "slskd.yml"
        self.download_dir = self.proj_root / "qml" / "music_resource" / "loadmusic_by_default"
        self.incomplete_dir = self.tools_dir / "incomplete"
        self.share_dir = self.download_dir

        self._process: Optional[subprocess.Popen] = None
        self._download_url = "https://github.com/slskd/slskd/releases/download/0.26.0/slskd-0.26.0-win-x64.zip"
        self._mirror_url = "https://ghproxy.net/https://github.com/slskd/slskd/releases/download/0.26.0/slskd-0.26.0-win-x64.zip"

    async def is_running(self) -> bool:
        """探针检测本地 5030 端口的 slskd 是否已在提供服务"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.api_url}/application")
                return resp.status_code == 200
        except Exception:
            return False

    async def ensure_installed(self) -> bool:
        """检查并自动安装绿色免安装版 slskd，支持 HTTP Range 断点续传"""
        if self.exe_path.exists():
            return True

        self.tools_dir.mkdir(parents=True, exist_ok=True)
        zip_file = self.tools_dir / "slskd-temp.zip"
        expected_size = 60777709
        url = self._download_url

        # 如果已有完整的 zip 文件，直接解压
        if zip_file.exists() and zip_file.stat().st_size >= expected_size:
            logger.info("[SlskdDaemon] 检测到完整安装包，准备解压...")
        else:
            logger.info(f"[SlskdDaemon] 正在静默下载 slskd 运行时 (支持断点续传)...")
            max_retries = 30
            for attempt in range(max_retries):
                downloaded = zip_file.stat().st_size if zip_file.exists() else 0
                if downloaded >= expected_size:
                    break

                headers = {"Range": f"bytes={downloaded}-"}
                try:
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        async with client.stream("GET", url, headers=headers) as resp:
                            if resp.status_code == 206:
                                with open(zip_file, "ab") as f:
                                    async for chunk in resp.aiter_bytes(chunk_size=131072):
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if downloaded % (1024 * 1024 * 5) < 131072:
                                            logger.info(f"[SlskdDaemon] 下载进度: {downloaded / expected_size * 100:.1f}% ({downloaded // (1024*1024)}MB / {expected_size // (1024*1024)}MB)")
                            elif resp.status_code == 200:
                                with open(zip_file, "wb") as f:
                                    downloaded = 0
                                    async for chunk in resp.aiter_bytes(chunk_size=131072):
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if downloaded % (1024 * 1024 * 5) < 131072:
                                            logger.info(f"[SlskdDaemon] 下载进度: {downloaded / expected_size * 100:.1f}% ({downloaded // (1024*1024)}MB / {expected_size // (1024*1024)}MB)")
                            else:
                                logger.warning(f"[SlskdDaemon] HTTP 状态异常: {resp.status_code}")
                except Exception as e:
                    cur_mb = downloaded // (1024 * 1024)
                    logger.info(f"[SlskdDaemon] 触发断点续传重试 (当前进度: {cur_mb}MB / 57MB): {e}")
                    await asyncio.sleep(1.0)

        if not zip_file.exists() or zip_file.stat().st_size < 10000000:
            logger.error("[SlskdDaemon] 无法完整下载 slskd 运行时，请检查网络连通性")
            return False

        # 解压
        try:
            logger.info("[SlskdDaemon] 正在静默解压 slskd 运行时...")
            with zipfile.ZipFile(zip_file, "r") as z:
                z.extractall(self.tools_dir)
            
            # 清理临时压缩包
            if zip_file.exists():
                zip_file.unlink()
            
            logger.info(f"[SlskdDaemon] slskd 绿色运行时部署完成: {self.exe_path}")
            return self.exe_path.exists()
        except Exception as e:
            logger.error(f"[SlskdDaemon] 解压 slskd 失败: {e}")
            return False

    def ensure_configured(self):
        """预置免验证 slskd.yml 配置，完全免除用户手动配置负担"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.incomplete_dir.mkdir(parents=True, exist_ok=True)

        # Windows 路径转为安全 YAML 格式 (使用反斜杠且双反斜杠转义)
        downloads_str = str(self.download_dir).replace("/", "\\").replace("\\", "\\\\")
        incomplete_str = str(self.incomplete_dir).replace("/", "\\").replace("\\", "\\\\")

        # 若已存在配置，校验其路径是否为当前机器路径，若换了电脑/目录则自动纠正
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if downloads_str not in content:
                    import re
                    content = re.sub(r'downloads:\s*".*?"', f'downloads: "{downloads_str}"', content)
                    content = re.sub(r'incomplete:\s*".*?"', f'incomplete: "{incomplete_str}"', content)
                    content = re.sub(r'shares:\s*\n\s*directories:\s*\n\s*-\s*".*?"', f'shares:\n  directories:\n    - "{downloads_str}"', content)
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info("[SlskdDaemon] slskd 配置文件路径已自动同步为当前机器真实路径")
            except Exception as e:
                logger.debug(f"[SlskdDaemon] 校验/纠正配置路径异常: {e}")
            return

        # 随机分配一个免冲突的游客账户 (Soulseek 在初次登录时若用户名未注册会自动为其激活创建)
        random_suffix = uuid.uuid4().hex[:6]
        guest_user = f"fluent_guest_{random_suffix}"
        guest_pass = f"pass_{uuid.uuid4().hex[:8]}"

        yaml_content = f"""# slskd 自动生成的内置伴生配置 (由 Fluent Music AI Agent 管理)
soulseek:
  address: vps.slsknet.org
  port: 2271
  username: {guest_user}
  password: {guest_pass}

web:
  port: {self.port}
  logging: false
  authentication:
    disabled: true

directories:
  downloads: "{downloads_str}"
  incomplete: "{incomplete_str}"

shares:
  directories:
    - "{downloads_str}"
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        logger.info(f"[SlskdDaemon] 预置 slskd 配置文件已就绪: 用户名={guest_user}")

    async def start(self) -> bool:
        """静默启动伴生 slskd 守护进程"""
        # 1. 如果端口已经有服务在跑，直接复用
        if await self.is_running():
            logger.info(f"[SlskdDaemon] 检测到 slskd 服务已在 127.0.0.1:{self.port} 运行，直接复用连接")
            return True

        # 2. 确保环境与配置就绪
        installed = await self.ensure_installed()
        if not installed:
            logger.error("[SlskdDaemon] 无法启动: slskd.exe 未就绪")
            return False

        self.ensure_configured()

        # 3. 构造启动命令，隐藏黑框
        cmd = [str(self.exe_path), "--app-dir", str(self.data_dir)]
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW

        try:
            logger.info(f"[SlskdDaemon] 正在静默拉起 slskd 伴生服务: {cmd[0]} (端口: {self.port})")
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.tools_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )

            # 4. 轮询等待接口 200 OK (最多等待 10 秒)
            max_wait = 10.0
            elapsed = 0.0
            step = 0.5
            while elapsed < max_wait:
                await asyncio.sleep(step)
                elapsed += step
                if await self.is_running():
                    logger.info(f"[SlskdDaemon] slskd 守护进程已成功启动并就绪 (PID={self._process.pid})")
                    return True

            logger.warning("[SlskdDaemon] slskd 启动超时，可能仍在初始化中")
            return False
        except Exception as e:
            logger.error(f"[SlskdDaemon] 启动 slskd 进程失败: {e}")
            return False

    def stop(self):
        """优雅关闭伴生进程"""
        if self._process:
            try:
                logger.info(f"[SlskdDaemon] 正在终止伴生服务 (PID={self._process.pid})...")
                self._process.terminate()
                try:
                    self._process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                logger.info("[SlskdDaemon] slskd 伴生服务已安全退出")
            except Exception as e:
                logger.debug(f"[SlskdDaemon] 终止进程异常: {e}")
            finally:
                self._process = None


# 全局单例管理器
slskd_daemon = SlskdDaemonManager()
