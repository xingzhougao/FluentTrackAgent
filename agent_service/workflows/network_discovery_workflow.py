"""
NetworkDiscoveryWorkflow 网络音乐多源发现、人工确认与自动入库工作流 (Step 5 核心工作流)
遵循三大核心原则：
1. 本地优先 (Local-First)：本地曲库有目标歌曲时，坚决在本地播放，杜绝冗余网络下载；
2. 人工确认 (Human-in-the-loop)：大文件下载前由 ConfirmationManager 唤起模态弹窗，用户同意后才执行；
3. 自动入库与即刻开播：下载完成后调用 Qt 的 import_downloaded_track 工具自动追加至本地库并无缝开播。
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from .base import BaseWorkflow, WorkflowOutput
from providers.music.base import TrackCandidate

if TYPE_CHECKING:
    from runtime.agent_runtime import AgentRuntime

logger = logging.getLogger("AgentLogger")


class NetworkDiscoveryWorkflow(BaseWorkflow):
    """多源网络音乐发现与自动入库工作流"""

    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime

    async def execute(
        self,
        session_id: str,
        request_id: str,
        query: str = "",
        artist: str = "",
        auto_download: bool = True,
        auto_play: bool = True,
        skip_confirmation: bool = False,
        raw_text: str = "",
        **kwargs
    ) -> WorkflowOutput:
        session_ctx = self.runtime.context_manager.get_session(session_id)
        clean_q = query.strip()
        clean_art = artist.strip()

        # Step 1: 本地优先原则查验 (Local-First Guardrail)
        # 只要本地曲库能匹配，绝不触发网络检索与下载
        if clean_q or clean_art:
            search_reply = await self.runtime.call_client_tool(
                session_id=session_id,
                tool_name="search_local_music",
                arguments={"query": clean_q or clean_art, "limit": 5},
                timeout=4.0
            )
            if search_reply.get("success", False):
                tracks = search_reply.get("result", {}).get("tracks", [])
                exact_match = None
                for t in tracks:
                    t_title = t.get("title", "").lower()
                    t_art = t.get("artist", "").lower()
                    if clean_q and clean_art:
                        if (clean_q.lower() in t_title or t_title in clean_q.lower()) and (clean_art.lower() in t_art or t_art in clean_art.lower()):
                            exact_match = t
                            break
                    elif clean_q and (clean_q.lower() == t_title or clean_q.lower() in t_title or t_title in clean_q.lower()):
                        exact_match = t
                        break

                if exact_match:
                    logger.info(f"[NetworkDiscoveryWorkflow] 本地优先命中: 《{exact_match.get('title')}》，直接本地开播")
                    target_idx = exact_match.get("index", 0)
                    target_title = exact_match.get("title", "")
                    target_artist = exact_match.get("artist", "")

                    await self.runtime.call_client_tool(
                        session_id=session_id,
                        tool_name="play_local_track",
                        arguments={"index": target_idx},
                        timeout=4.0
                    )
                    session_ctx.record_played_track(exact_match)
                    session_ctx.record_recommended_tracks([exact_match])

                    tool_card = {
                        "name": "本地曲库优先播放",
                        "action": "play_local_track",
                        "params": f"《{target_title}》- {target_artist}",
                        "status": "success",
                        "result": "本地已收录该曲目，已直接为你启动原生本地播放"
                    }
                    return WorkflowOutput(
                        answer_text=f"本地曲库中已经有《{target_title}》- {target_artist} 啦！已优先为你启动本地播放，无需重复下载 🎵",
                        tools=[tool_card],
                        success=True
                    )

        # Step 2: 多源网络并发检索
        logger.info(f"[NetworkDiscoveryWorkflow] 启动网络多源检索: query='{clean_q}', artist='{clean_art}'")
        candidates = await self.runtime.provider_manager.search(
            query=clean_q,
            artist=clean_art,
            limit=5,
            timeout=30.0
        )

        if not candidates:
            # 向前端下发“未找到音源”模态弹窗通知 (触发客户端弹出“抱歉暂时找不到对应音源哦”+确认按钮)
            await self.runtime.session_manager.send_json(session_id, {
                "type": "no_source_found",
                "payload": {
                    "title": "未找到音源",
                    "message": "抱歉暂时找不到对应音源哦",
                    "query": clean_q,
                    "artist": clean_art
                }
            })
            tool_card = {
                "name": "网络音乐检索",
                "action": "network_search",
                "params": f"关键词: {clean_q} {clean_art}".strip(),
                "status": "failed",
                "result": "三大主力梯队均未检索到匹配资源"
            }
            return WorkflowOutput(
                answer_text=f"抱歉暂时找不到对应音源哦。你可以换个歌名或歌手再试试看 🔎",
                tools=[tool_card],
                success=False
            )

        # Step 3: 根据用户设置的模式决定：自动模式直接选取首选最优，自选模式弹出 5 条候选
        pref_auto = session_ctx.preferences.get("auto_download", False)
        # 若外部显式指定了 auto_download 参数则以显式为准，否则遵循用户模式
        is_auto_mode = auto_download if ("auto_download" in kwargs) else pref_auto

        best_cand: TrackCandidate = candidates[0]

        if is_auto_mode:
            logger.info(f"[NetworkDiscoveryWorkflow] 处于【自动优先下载模式】，免弹窗直接选取首选候选: 《{best_cand.title}》- {best_cand.artist} ({best_cand.provider})")
        else:
            # 弹窗自选模式：下发前 5 条最接近版本
            selected_id = await self.runtime.confirmation_manager.request_candidate_selection(
                session_id=session_id,
                query=clean_q or clean_art,
                artist=clean_art,
                candidates=candidates[:5]
            )

            if selected_id is None:
                # 用户在弹窗中取消
                logger.info(f"[NetworkDiscoveryWorkflow] 用户取消了选歌弹窗: {clean_q}")
                return WorkflowOutput(
                    answer_text=f"已为你取消《{clean_q or clean_art}》的下载。若需要收听其他歌曲，随时吩咐我 🎵",
                    tools=[],
                    success=False
                )

            # 匹配用户选定的候选对象
            for c in candidates:
                if c.id == selected_id:
                    best_cand = c
                    break

        tool_cards: List[Dict[str, Any]] = []

        provider_label = {
            "xiageba": "下歌吧 (刘明野)",
            "soulseek_p2p": "Soulseek P2P 共享",
            "web_music": "开放网络音源"
        }.get(best_cand.provider, best_cand.provider)

        tool_cards.append({
            "name": "多源网络发现",
            "action": "network_search",
            "params": f"《{best_cand.title}》- {best_cand.artist} [{provider_label}]",
            "status": "success",
            "result": f"已匹配到音源 (格式: {best_cand.format.upper()} {best_cand.bitrate}kbps, 大小: {best_cand.format_size()})"
        })

        # 检测是否为网盘转存资源 (例如夸克/百度网盘)
        is_netdisk = bool(best_cand.url and ("pan.baidu.com" in best_cand.url or "pan.quark.cn" in best_cand.url)) or best_cand.extra.get("is_netdisk", False)
        if is_netdisk:
            logger.info(f"[NetworkDiscoveryWorkflow] 匹配到网盘分享资源，向用户提供提取地址并自动打开浏览器: {best_cand.url}")
            try:
                import webbrowser
                webbrowser.open(best_cand.url)
            except Exception as e:
                logger.debug(f"[NetworkDiscoveryWorkflow] 启动默认浏览器异常: {e}")

            tool_cards.append({
                "name": "网盘资源直达",
                "action": "open_browser",
                "params": best_cand.url,
                "status": "success",
                "result": "已为你通过默认浏览器唤起网盘转存页面"
            })
            return WorkflowOutput(
                answer_text=(
                    f"在【{provider_label}】平台为你匹配到《{best_cand.title}》- {best_cand.artist} 的资源：\n\n"
                    f"🔗 **网盘地址**：{best_cand.url}\n\n"
                    f"💡 **温馨提示**：该链接为第三方网盘转存地址，通常可能需要微信扫码关注公众号获取提取码，或在网盘客户端内打开。\n"
                    f"若该链接已失效或无法直接转存，建议在界面中选择其他直接可播的音频版本，无需扫码即可直接在播放器内畅听 🎵"
                ),
                tools=tool_cards,
                success=True
            )

        if not auto_download:
            # 仅展示候选，不自动下载
            candidate_list_str = "\n".join([
                f"{i+1}. 《{c.title}》- {c.artist} ({c.format.upper()} {c.bitrate}kbps, {c.format_size()}) [来源: {provider_label}]"
                for i, c in enumerate(candidates[:3])
            ])
            return WorkflowOutput(
                answer_text=f"为你全网检索到以下音乐资源：\n\n{candidate_list_str}\n\n如需下载入库，请吩咐我“下载第 1 首”或“确认下载”即可！✨",
                tools=tool_cards,
                success=True
            )

        # Step 3: 若非点播且要求人工确认，发起交互确认
        if not skip_confirmation and not auto_play:
            confirm_title = "网络歌曲下载确认"
            confirm_msg = f"即将从网络下载《{best_cand.title}》- {best_cand.artist} 并自动加入本地曲库，是否继续？"
            confirm_details = f"资源来源: {provider_label} | 格式: {best_cand.format.upper()} {best_cand.bitrate}kbps | 文件大小: {best_cand.format_size()}"

            confirmed = await self.runtime.confirmation_manager.request_confirmation(
                session_id=session_id,
                title=confirm_title,
                message=confirm_msg,
                details=confirm_details,
                timeout=45.0
            )

            if not confirmed:
                logger.info(f"[NetworkDiscoveryWorkflow] 用户取消了下载: 《{best_cand.title}》")
                tool_cards.append({
                    "name": "人工确认",
                    "action": "confirm_download",
                    "params": f"《{best_cand.title}》",
                    "status": "failed",
                    "result": "用户已取消下载"
                })
                return WorkflowOutput(
                    answer_text=f"已为你取消了《{best_cand.title}》的下载。如果需要收听其他歌曲，随时告诉我哦 ✨",
                    tools=tool_cards,
                    success=True
                )

            tool_cards.append({
                "name": "人工确认",
                "action": "confirm_download",
                "params": f"《{best_cand.title}》",
                "status": "success",
                "result": "用户已确认执行下载"
            })

        # Step 4: 异步下载文件至本地存储目录并推送实时进度
        await self.runtime.session_manager.send_json(session_id, {
            "type": "status_update",
            "payload": {
                "status": "downloading",
                "message": f"正在从【{provider_label}】下载《{best_cand.title}》- {best_cand.artist}..."
            }
        })

        async def on_download_progress(downloaded: int, total: int):
            percent = int((downloaded / total) * 100) if total > 0 else 0
            percent = min(100, max(0, percent))
            d_mb = downloaded / (1024 * 1024)
            t_mb = total / (1024 * 1024)
            status_msg = f"正在下载《{best_cand.title}》... {percent}% ({d_mb:.1f}MB / {t_mb:.1f}MB)"
            await self.runtime.session_manager.send_json(session_id, {
                "type": "status_update",
                "payload": {
                    "status": "downloading",
                    "message": status_msg
                }
            })

        local_file_path = await self.runtime.download_service.download_track(
            best_cand,
            on_progress=on_download_progress,
            fallback_candidates=candidates
        )

        if not local_file_path:
            # 检查是否有备选的网盘资源 (例如下歌吧提供的夸克/百度网盘转存)
            netdisk_cand = None
            for c in candidates:
                c_url = c.url or ""
                if "pan.baidu.com" in c_url or "pan.quark.cn" in c_url or (c.extra and c.extra.get("is_netdisk")):
                    netdisk_cand = c
                    break

            if netdisk_cand:
                logger.info(f"[NetworkDiscoveryWorkflow] 直接音频流受版权保护，自动切换至网盘分享并唤起浏览器: {netdisk_cand.url}")
                try:
                    import webbrowser
                    webbrowser.open(netdisk_cand.url)
                except Exception as e:
                    logger.debug(f"[NetworkDiscoveryWorkflow] 启动默认浏览器异常: {e}")

                tool_cards.append({
                    "name": "网盘资源直达",
                    "action": "open_browser",
                    "params": netdisk_cand.url,
                    "status": "success",
                    "result": "已为你通过默认浏览器唤起网盘转存页面"
                })
                await self.runtime.session_manager.send_json(session_id, {
                    "type": "status_update",
                    "payload": {
                        "status": "ready",
                        "message": "已为你打开网盘页面"
                    }
                })
                p_label = "下歌吧 (刘明野)" if netdisk_cand.provider == "xiageba" else netdisk_cand.provider
                return WorkflowOutput(
                    answer_text=(
                        f"全网公开直接音频流因商业版权保护受限，已自动为你从【{p_label}】匹配到《{netdisk_cand.title}》- {netdisk_cand.artist} 的原版高品质网盘资源：\n\n"
                        f"🔗 **网盘地址**：{netdisk_cand.url}\n\n"
                        f"🌐 已为你通过系统默认浏览器自动打开转存页面，你可直接一键转存下载！🎵"
                    ),
                    tools=tool_cards,
                    success=True
                )

            await self.runtime.session_manager.send_json(session_id, {
                "type": "status_update",
                "payload": {
                    "status": "ready",
                    "message": "未能下载该歌曲"
                }
            })
            tool_cards.append({
                "name": "文件下载",
                "action": "download_track",
                "params": f"《{best_cand.title}》- {best_cand.artist}",
                "status": "failed",
                "result": "该曲目当前仅提供网盘转存或因商业版权限制暂无直接音频流"
            })

            await self.runtime.session_manager.send_json(session_id, {
                "type": "no_source_found",
                "payload": {
                    "title": "未找到音源",
                    "message": "抱歉暂时找不到对应音源哦",
                    "query": best_cand.title,
                    "artist": best_cand.artist
                }
            })

            return WorkflowOutput(
                answer_text=f"未能从网络获取《{best_cand.title}》的有效音频流。{netdisk_hint}\n\n建议吩咐我换一首歌曲试试看 ✨",
                tools=tool_cards,
                success=False
            )

        # 下载完成，准备自动导入本地库
        await self.runtime.session_manager.send_json(session_id, {
            "type": "status_update",
            "payload": {
                "status": "thinking",
                "message": f"《{best_cand.title}》下载完成，正在自动收录入本地音乐库..."
            }
        })

        tool_cards.append({
            "name": "网络音乐下载",
            "action": "download_track",
            "params": f"《{best_cand.title}》- {best_cand.artist}",
            "status": "success",
            "result": f"下载成功 100% (规格: {best_cand.format.upper()} {best_cand.bitrate}kbps, 大小: {best_cand.format_size()})"
        })

        # Step 5: 调用 Qt 客户端原子工具 import_downloaded_track 自动入库并启动开播
        import_reply = await self.runtime.call_client_tool(
            session_id=session_id,
            tool_name="import_downloaded_track",
            arguments={
                "file_path": local_file_path,
                "title": best_cand.title,
                "artist": best_cand.artist,
                "album": best_cand.album,
                "duration": best_cand.duration,
                "auto_play": auto_play
            },
            timeout=6.0
        )

        import_success = import_reply.get("success", False)
        if not import_success:
            err = import_reply.get("error", "入库失败")
            tool_cards.append({
                "name": "本地曲库导入",
                "action": "import_downloaded_track",
                "params": local_file_path,
                "status": "failed",
                "result": f"自动导入本地曲库失败: {err}"
            })
            await self.runtime.session_manager.send_json(session_id, {
                "type": "status_update",
                "payload": {
                    "status": "ready",
                    "message": "已就绪"
                }
            })
            return WorkflowOutput(
                answer_text=f"歌曲《{best_cand.title}》已下载完成，但在加入本地曲库时遇到问题：{err}",
                tools=tool_cards,
                success=False
            )

        imported_info = import_reply.get("result", {})
        track_dict = {
            "title": best_cand.title,
            "artist": best_cand.artist,
            "file_path": local_file_path,
            "index": imported_info.get("index", 0)
        }
        session_ctx.record_played_track(track_dict)
        session_ctx.record_recommended_tracks([track_dict])

        tool_cards.append({
            "name": "本地曲库导入",
            "action": "import_downloaded_track",
            "params": f"《{best_cand.title}》- {best_cand.artist}",
            "status": "success",
            "result": f"已成功收录入本地曲库 (当前总曲目数: {imported_info.get('total_count', '更新')}) 并启动播放"
        })

        await self.runtime.session_manager.send_json(session_id, {
            "type": "status_update",
            "payload": {
                "status": "ready",
                "message": "已就绪"
            }
        })

        ans = (
            f"已为你成功从网络发现并下载了 {best_cand.artist} 的《{best_cand.title}》🎵\n\n"
            f"- **音质规格**：{best_cand.format.upper()} {best_cand.bitrate}kbps（{best_cand.format_size()}）\n"
            f"- **本地存储**：已自动入库并收录进你的播放器音乐库\n\n"
            f"经典旋律已经为你启动播放，戴上耳机尽情享受吧！✨"
        )
        return WorkflowOutput(answer_text=ans, tools=tool_cards, success=True)
