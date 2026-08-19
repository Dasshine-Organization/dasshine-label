# P18 · 企业接入

对照：OIDC / 关公开注册 / 邮件邀请 / 组织 API Key / 出站 Webhook / 只读审计 / 中英界面。

## 交付

| 能力 | 行为 |
|------|------|
| 关注册 | `AUTH_REGISTER_ENABLED=false` → `POST /auth/register` 403；前端隐藏注册链 |
| OIDC | `OIDC_*` 配置后 `GET /auth/oidc/login` → IdP → callback 跳转前端 `?oidc_token=` |
| 公开配置 | `GET /auth/public-config` → `{register_enabled, oidc_enabled}` |
| 邀请 | `POST /orgs/{id}/invites`；邮件或控制台日志；`POST /orgs/invites/accept` |
| API Key | `ds_…`；`Authorization: Bearer` 或 `X-Api-Key`；创建时只返回一次明文 |
| Webhook | 事件 `task.submitted` / `review.decided` / `export.done`；`X-Dasshine-Signature: sha256=` |
| 审计 | `GET /orgs/{id}/audit`（owner/admin）；登录、成员、配额、导出等写入 |
| i18n | 侧栏/登录 中英切换；Ant Design `zh_CN` / `en_US` |

## 迁移

```bash
cd backend && alembic upgrade head
```

表：`org_invites`、`org_api_keys`、`org_webhooks`、`audit_events`；`users.oidc_sub/issuer`。

## 验收

- `pytest tests/test_p18_enterprise.py`
- 关注册后登录页无注册入口
- 组织侧栏「企业设置」可发邀请 / 建 Key / 挂 Webhook / 看审计
