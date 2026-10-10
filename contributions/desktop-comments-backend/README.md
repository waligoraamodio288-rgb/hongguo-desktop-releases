# 只读评论、回复与互动统计接口

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

不依赖弹幕渲染包。签名请求通过宿主 provider.api 复用；/danmaku 与评论共用数据通道，渲染由独立包负责。可选 emoji_catalog 由表情包注入。

## 接入与行为

把 src/desktop_social.py 放入宿主后端模块目录。provider 需要提供 CFG["base_query"]["aid"]、get_episodes(sid)、api(method,path,body=...,max_retries=1)、_episodes_body(sid)、_parse_episode_detail(sid,video)。这些方法由原有签名、账号和超时 owner 实现，本包不重建它们。

```python
from desktop_social import make_router
app.include_router(make_router(provider, authorize=existing_api_key_dependency,
                               emoji_catalog=lambda: {}))
```

authorize 是必填 FastAPI dependency；所有五个路由都复用它。宿主只监听回环并限制可信桌面 origin，保持原 CORS 规则，不将接口暴露到局域网。上游列表协议虽然使用 POST，功能仅为读取；本地路由仅 GET，不注册写评论/点赞/收藏路由。

| 路由 | 口径 |
| --- | --- |
| /desktop/social/comments | kind=episode 本集评论；kind=series 整剧剧评 |
| /desktop/social/replies | 本集评论的分页回复，保留 Common 大写字段 |
| /desktop/social/metrics | 本集 digged_count/comment_count、整剧 followed_cnt；独立 30 秒 TTL、最多 64 剧 |
| /desktop/social/danmaku | comment_type=20、source=601、channel=1000；offset_ms 是视频毫秒 |
| /desktop/social/emojis | 注入的本地 PNG catalog；未注入返回空字典 |

评论 type/source/channel 分别为本集 4/4/18、剧评 2/1/46；回复 source=504。长 ID 与不透明游标始终为字符串。接口错误返回可重试 502，内部异常细节不返回给前端。不要用收藏总数表示用户个人收藏状态。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
python -X utf8 -m unittest discover -s contributions/desktop-comments-backend/tests -v
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。
