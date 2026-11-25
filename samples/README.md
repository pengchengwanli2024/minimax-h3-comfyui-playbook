# 样片说明

`samples/preview/` 里是**压缩后的预览**（640px、无音频、CRF 30），用于展示效果；原片是 1152×640 / 24fps / H.264 + AAC 32kHz 立体声，体积 5–11 MB，没有放进仓库。

| 预览 | 原片 | 规格 | 权重 / 注意力 | 耗时 |
|---|---|---|---|---|
| [nightmarket.jpg](preview/nightmarket.jpg) · [mp4](preview/sla_long_nightmarket_15s_preview.mp4) | `sla_long_nightmarket_15s.mp4` | 15.08s / 362 帧 | turbo8 + 原生 SLA | 167.4s |
| [subway.jpg](preview/subway.jpg) · [mp4](preview/h3_sla_subway_10s_preview.mp4) | `h3_sla_subway_10s.mp4` | 10.13s / 243 帧 | turbo8 + 原生 SLA | 98.7s |
| [seaside.jpg](preview/seaside.jpg) · [mp4](preview/sla_seaside_sunset_10s_preview.mp4) | `sla_seaside_sunset_10s.mp4` | 10.13s / 243 帧 | turbo8 + 原生 SLA | 101.3s |
| [bookstore.jpg](preview/bookstore.jpg) | `sla_bookstore_rain_10s.mp4` | 10.13s / 243 帧 | turbo8 + 原生 SLA | 102.4s |
| [rainstreet.jpg](preview/rainstreet.jpg) | `h3_10s_1152x640.mp4` | 10.13s / 243 帧 | FastH3 4 步 VSA | 127.9s |
| [pov.jpg](preview/pov.jpg) | `h3_pov_10s_1152x640.mp4` | 10.13s / 243 帧 | FastH3 4 步 VSA | 150.1s |

对应的提示词见 [prompts/examples.json](../prompts/examples.json)，参数见 [docs/parameters.md](../docs/parameters.md)。

> 样片由 MiniMax H3 在本机生成，仅用于展示模型效果；生成内容的责任由使用者承担。
