# 对象存储（S3 兼容）

Dasshine 支持将导入文件写入 **S3 兼容**对象存储（MinIO / AWS S3 / 阿里云 OSS S3 网关等）。

## 开关

```bash
STORAGE_BACKEND=s3   # 默认 local
```

`local`：写入 `UPLOAD_DIR`，`data_url = {FILE_SERVER_BASE_URL}/uploads/...`  
`s3`：`put_object` 到桶，`data_url = {S3_PUBLIC_BASE_URL}/{key}`

## 环境变量

| 变量 | 说明 |
|------|------|
| `S3_ENDPOINT_URL` | MinIO 等自定义端点，如 `http://127.0.0.1:9000`；AWS 可留空 |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | 访问密钥 |
| `S3_BUCKET` | 桶名 |
| `S3_REGION` | 默认 `us-east-1` |
| `S3_PREFIX` | 键前缀，默认 `dasshine` → `dasshine/projects/{id}/…` |
| `S3_PUBLIC_BASE_URL` | 浏览器可访问前缀（CDN 或 `http://minio:9000/bucket`） |
| `S3_FORCE_PATH_STYLE` | MinIO 建议 `true` |
| `S3_VERIFY_SSL` | HTTPS 证书校验 |

## MinIO 示例

```bash
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://127.0.0.1:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=dasshine-label
S3_FORCE_PATH_STYLE=true
S3_PUBLIC_BASE_URL=http://127.0.0.1:9000/dasshine-label
```

桶需对标注端浏览器可读（公开读或反代）；写权限给服务端密钥。

## API

- `GET /api/v1/storage/config` — 非敏感配置（供导入 UI）
- `GET /api/v1/storage/health` — `head_bucket` 探测
- `/ready` 会检查存储后端

导入弹窗「公开访问前缀」在 S3 模式下可覆盖 `S3_PUBLIC_BASE_URL`（仅影响本次导入的 `data_url` 拼装，对象仍写入配置桶）。
