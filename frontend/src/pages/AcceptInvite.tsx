import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { message } from 'antd'
import { orgApi } from '../services/api'
import useAuthStore from '../store/authStore'

export default function AcceptInvite() {
  const { token = '' } = useParams<{ token: string }>()
  const { token: authToken } = useAuthStore()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'idle' | 'ok' | 'err'>('idle')
  const [detail, setDetail] = useState('')

  useEffect(() => {
    if (!authToken) {
      setDetail('请先登录后再打开此邀请链接')
      setStatus('err')
      return
    }
    if (!token) return
    orgApi
      .acceptInvite(token)
      .then(res => {
        setStatus('ok')
        setDetail(res.data.message || '已加入组织')
        message.success(res.data.message || '已加入组织')
        window.setTimeout(() => navigate('/'), 1200)
      })
      .catch((e: unknown) => {
        const err = e as { response?: { data?: { detail?: string } } }
        setStatus('err')
        setDetail(err.response?.data?.detail ?? '接受邀请失败')
      })
  }, [token, authToken, navigate])

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4 text-white">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-8 max-w-md w-full text-center space-y-4">
        <h1 className="text-lg font-medium">组织邀请</h1>
        <p className="text-sm text-white/50">{status === 'idle' ? '处理中…' : detail}</p>
        {status === 'err' && !authToken && (
          <Link to="/login" className="text-[#00d4ff] text-sm">
            去登录
          </Link>
        )}
      </div>
    </div>
  )
}
