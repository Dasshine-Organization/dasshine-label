import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import api from '../services/api'

export default function Login() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // POST /api/v1/auth/login (OAuth2 form)
      const params = new URLSearchParams()
      params.append('username', form.username)
      params.append('password', form.password)
      const { data } = await api.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      // fetch user info
      const { data: user } = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      setAuth(user, data.access_token)
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  // ── dev shortcut: skip auth ───────────────────────────────────────────────
  function devLogin() {
    setAuth(
      {
        id: 1,
        username: 'dev',
        email: 'dev@dasshine.ai',
        level: 'expert',
        role: 'super_admin',
        is_admin: true,
        skill_tags: ['2d_bbox', '3d_box'],
        accuracy_rate: 0.95,
        total_completed: 1200,
        total_earnings: 240,
        active_tasks: 3,
      },
      'dev-token'
    )
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4"
      style={{ backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(0,212,255,0.06) 0%, transparent 60%)' }}>

      {/* grid overlay */}
      <div className="fixed inset-0 pointer-events-none"
        style={{ backgroundImage: 'linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      <div className="w-full max-w-sm relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2.5 mb-3">
            <div className="w-9 h-9 rounded-xl bg-[#00d4ff]/10 border border-[#00d4ff]/30 flex items-center justify-center">
              <div className="w-3.5 h-3.5 rounded-sm bg-[#00d4ff]" />
            </div>
            <span className="text-xl font-semibold tracking-tight">Dasshine Label</span>
          </div>
          <p className="text-sm text-white/30">智能标注与分发平台</p>
        </div>

        {/* Card */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-7"
          style={{ boxShadow: '0 0 40px rgba(0,212,255,0.05)' }}>
          <h2 className="text-base font-medium text-white/80 mb-6">登录账户</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-white/40 mb-1.5">用户名</label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder="输入用户名"
                required
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20
                  focus:outline-none focus:border-[#00d4ff]/50 focus:ring-1 focus:ring-[#00d4ff]/20 transition-all"
              />
            </div>
            <div>
              <label className="block text-xs text-white/40 mb-1.5">密码</label>
              <input
                type="password"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="输入密码"
                required
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20
                  focus:outline-none focus:border-[#00d4ff]/50 focus:ring-1 focus:ring-[#00d4ff]/20 transition-all"
              />
            </div>

            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-sm font-medium transition-all active:scale-[0.98]
                bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30
                hover:bg-[#00d4ff]/25 hover:border-[#00d4ff]/50
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading
                ? <span className="inline-flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border border-[#00d4ff]/30 border-t-[#00d4ff] rounded-full animate-spin" />
                    登录中…
                  </span>
                : '登录'}
            </button>
          </form>

          <div className="mt-4 text-center text-xs text-white/30">
            没有账户？{' '}
            <Link to="/register" className="text-[#00d4ff]/70 hover:text-[#00d4ff] transition-colors">
              注册
            </Link>
          </div>

          {/* Dev skip button */}
          <button
            onClick={devLogin}
            className="mt-4 w-full py-2 rounded-lg text-xs text-white/20 border border-white/5 hover:text-white/40 hover:border-white/10 transition-all"
          >
            开发模式快速进入 →
          </button>
        </div>
      </div>
    </div>
  )
}
