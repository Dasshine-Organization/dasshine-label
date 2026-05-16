#!/bin/bash
# Dasshine Label 前端启动修复脚本

echo "🔧 前端启动问题修复"
echo "===================="

# 检查 Node.js 版本
echo ""
echo "📋 检查 Node.js 版本..."
NODE_VERSION=$(node --version 2>/dev/null || echo "未安装")
echo "当前 Node.js 版本: $NODE_VERSION"

# 检查版本号
if [[ "$NODE_VERSION" =~ ^v([0-9]+) ]]; then
    MAJOR_VERSION="${BASH_REMATCH[1]}"
    if [ "$MAJOR_VERSION" -lt 18 ]; then
        echo "⚠️  Node.js 版本过低！需要 v18+"
        echo ""
        echo "请升级 Node.js:"
        echo "  使用 nvm: nvm install 20 && nvm use 20"
        echo "  或访问: https://nodejs.org/ 下载 LTS 版本"
        exit 1
    else
        echo "✅ Node.js 版本符合要求"
    fi
else
    echo "❌ 无法检测 Node.js 版本"
    exit 1
fi

# 清理缓存
echo ""
echo "🧹 清理缓存..."
rm -rf node_modules
rm -rf .vite
rm -f package-lock.json
rm -f yarn.lock
rm -f pnpm-lock.yaml

# 安装依赖
echo ""
echo "📦 重新安装依赖..."
npm install

# 检查安装结果
if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    exit 1
fi

echo ""
echo "✅ 修复完成！"
echo ""
echo "现在可以尝试启动:"
echo "  npm run dev"
