# 外部平台注册指南

## DeepSeek API

1. 打开 https://platform.deepseek.com/api_keys
2. 注册/登录 → API Keys → 创建新 key
3. 复制 `sk-` 开头的 key
4. 运行 `bash scripts/credential-setup.sh` 填入

## Volc Engine (豆包)

1. 打开 https://console.volcengine.com/ark
2. 创建 API Key → 复制
3. 模型: Doubao-pro-32k (content_gen), Doubao-lite-128k (analysis/classification)
4. 在 credential-setup.sh 中填入

## Stripe 支付

1. 打开 https://dashboard.stripe.com/apikeys
2. 复制 `sk_live_` 或 `sk_test_` 密钥
3. Webhook: Dashboard → Webhooks → Add endpoint
   - URL: `https://your-domain.com/api/v1/stripe/webhook`
   - Events: `checkout.session.completed`
   - 复制 `whsec_` signing secret
4. 运行 `python hq/setup_stripe.py` 创建产品/Pricing

## SMTP 邮件

推荐 SendGrid:
1. 打开 https://app.sendgrid.com/settings/api_keys
2. Create API Key → 复制 `SG.` 开头的 key
3. SMTP 设置: Host=smtp.sendgrid.net, Port=587, User=apikey

备选: Mailgun, AWS SES, Resend

## Upwork MCP

1. 打开 https://www.upwork.com/developer/keys/apply
2. 填写应用 → 获取 Client ID + Client Secret
3. OAuth 回调 URL: `http://localhost` (本地开发)
4. 在 credential-setup.sh 中填入

## 猪八戒开放平台

1. 打开 https://open.zbj.com/
2. 注册开发者 → 创建应用 → 获取 App Key + App Secret
3. API 签名: MD5(AppKey + timestamp + AppSecret)
4. 在 credential-setup.sh 中填入

## 验证

所有凭证配置后，重启服务:

```bash
bash hq/hq-manager.sh restart all
```

检查日志:
```bash
ls ~/.crosswave/run/*.log
```
