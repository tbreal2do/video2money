# video2money
##解解说词不准确，没有风格
  优化提示词-找到提示词模板
  
  转发yotube bwf tv的视频，转发其他视频平台的视频
  选取-下载-视频理解-选取精彩部分-解说-生成剪影脚本-合成视频-生成标题-生成封面-生成文案-生成话题-邮件提醒-一键转发
  添加软广告
  转发：定时发布
  v1 监听bwf的视频更新-选取中国选手短视频-下载-邮件提醒-手动转发
  v2 根据标题，封面文字，评论，文案分析热点内容-下载-视频理解-选取精彩部分-简单合成视频-邮件提醒-手动转发
  v3 生成标题-生成封面-生成文案-生成话题
  
  
  方案：
  goole pubsub +google 频道通知 + dify 网络钩子 
  
  google 频道通知 ：https://developers.google.com/youtube/v3/guides/push_notifications?hl=zh-cn
  
  先订阅：https://pubsubhubbub.appspot.com/subscribe 使用同步验证确保验证成功
  render.com 部署一个webhook 服务，转发到dify 网络勾子
  使用 github action 保活 render 服务。
