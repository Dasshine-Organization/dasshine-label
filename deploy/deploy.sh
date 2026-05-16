#!/usr/bin/env bash
# Dasshine Label — Docker Compose 部署脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
PROJECT_NAME="dasshine-label"

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }

usage() {
  cat <<'EOF'
用法: ./deploy.sh <命令> [选项]

命令:
  up          构建并启动生产栈（Nginx + API + PostgreSQL + Redis）
  dev         启动开发栈（Vite :3000 + API 热重载 :8000）
  down        停止并移除容器（保留数据卷）
  down -v     停止并删除数据卷（清空数据库与上传文件）
  build       仅构建镜像
  logs        查看日志（可跟服务名，如 logs backend）
  ps          查看容器状态
  restart     重启服务
  worker      启动 Celery Worker（需生产栈已运行）

示例:
  ./deploy.sh up -d
  ./deploy.sh dev
  ./deploy.sh logs -f backend
  ./deploy.sh worker

环境:
  首次运行前请复制 .env.example 为 .env 并修改 SECRET_KEY、PUBLIC_URL。
EOF
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f .env.example ]]; then
      cp .env.example "$ENV_FILE"
      yellow "已生成 $ENV_FILE，请编辑 SECRET_KEY 与 PUBLIC_URL 后重新执行。"
    else
      red "缺少 $ENV_FILE，请先创建环境配置。"
      exit 1
    fi
  fi
}

compose() {
  docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

compose_dev() {
  docker compose --env-file "$ENV_FILE" -p "${PROJECT_NAME}-dev" -f docker-compose.dev.yml "$@"
}

cmd="${1:-}"
shift || true

case "$cmd" in
  up)
    ensure_env
    green "启动生产环境..."
    compose build "$@"
    compose up -d "$@"
    green "访问: ${PUBLIC_URL:-http://localhost:8080}"
    green "API 文档: ${PUBLIC_URL:-http://localhost:8080}/docs"
    ;;
  dev)
    ensure_env
    green "启动开发环境..."
    compose_dev up -d --build "$@"
    green "前端: http://localhost:3000"
    green "后端: http://localhost:8000  文档: http://localhost:8000/docs"
    ;;
  down)
    if [[ "${1:-}" == "-v" ]]; then
      compose down -v
      compose_dev down -v 2>/dev/null || true
    else
      compose down "$@"
      compose_dev down 2>/dev/null || true
    fi
    ;;
  build)
    ensure_env
    compose build "$@"
    ;;
  logs)
    ensure_env
    if compose_dev ps -q 2>/dev/null | grep -q .; then
      compose_dev logs "$@"
    else
      compose logs "$@"
    fi
    ;;
  ps)
    compose ps "$@" 2>/dev/null || true
    compose_dev ps "$@" 2>/dev/null || true
    ;;
  restart)
    ensure_env
    compose restart "$@"
    ;;
  worker)
    ensure_env
    green "启动 Celery Worker（profile: worker）..."
    compose --profile worker up -d celery "$@"
    ;;
  help|-h|--help|"")
    usage
    ;;
  *)
    red "未知命令: $cmd"
    usage
    exit 1
    ;;
esac
