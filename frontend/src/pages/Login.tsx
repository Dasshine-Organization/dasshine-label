import { useEffect, useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { authApi } from '../services/api'
import { useLocale } from '../i18n/LocaleProvider'

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setAuth } = useAuthStore()
  const { t, locale, setLocale } = useLocale()
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [registerEnabled, setRegisterEnabled] = useState(true)
  const [oidcEnabled, setOidcEnabled] = useState(false)

  useEffect(() => {
    authApi
      .publicConfig()
      .then(res => {
        setRegisterEnabled(Boolean(res.data.register_enabled))
        setOidcEnabled(Boolean(res.data.oidc_enabled))
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    const oidcToken = searchParams.get('oidc_token')
    const oidcError = searchParams.get('oidc_error')
    if (oidcError) {
      setError(`SSO 失败: ${oidcError}`)
      return
    }
    if (!oidcToken) return
    ;(async () => {
      try {
        setAuth({ id: 0, username: '', email: '', level: 'novice', role: 'annotator', is_admin: false }, oidcToken)
        const { data: me } = await authApi.getMe()
        setAuth(
          {
            id: me.id,
            username: me.username,
            email: me.email,
            level: me.level,
            role: me.role,
            is_admin: me.is_admin,
          },
          oidcToken,
        )
        navigate('/')
      } catch {
        setError('SSO 登录完成但获取用户失败')
      }
    })()
  }, [searchParams, setAuth, navigate])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await authApi.login(form.username, form.password)
      setAuth(
        {
          id: data.user.id,
          username: data.user.username,
          email: data.user.email ?? '',
          level: data.user.level ?? 'novice',
          role: data.user.role,
          is_admin: data.user.is_admin,
        },
        data.access_token,
      )
      const { data: me } = await authApi.getMe()
      setAuth(
        {
          id: me.id,
          username: me.username,
          email: me.email,
          level: me.level,
          role: me.role,
          is_admin: me.is_admin,
        },
        data.access_token,
      )
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

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

      <div className="fixed inset-0 pointer-events-none"
        style={{ backgroundImage: 'linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      <div className="w-full max-w-sm relative z-10">
        <div className="absolute right-0 -top-8 flex gap-1 text-[10px]">
          <button
            type="button"
            onClick={() => setLocale('zh')}
            className={locale === 'zh' ? 'text-[#00d4ff]' : 'text-white/30'}
          >
            中文
          </button>
          <span className="text-white/20">/</span>
          <button
            type="button"
            onClick={() => setLocale('en')}
            className={locale === 'en' ? 'text-[#00d4ff]' : 'text-white/30'}
          >
            EN
          </button>
        </div>

        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2.5 mb-3">
            <div className="w-9 h-9 rounded-xl bg-[#00d4ff]/10 border border-[#00d4ff]/30 flex items-center justify-center">
              <div className="w-3.5 h-3.5 rounded-sm bg-[#00d4ff]" />
            </div>
            <span className="text-xl font-semibold tracking-tight">Dasshine Label</span>
          </div>
          <p className="text-sm text-white/30">{t('login.subtitle')}</p>
        </div>

        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-7"
          style={{ boxShadow: '0 0 40px rgba(0,212,255,0.05)' }}>
          <h2 className="text-base font-medium text-white/80 mb-6">{t('login.title')}</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-white/40 mb-1.5">{t('login.username')}</label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                required
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20
                  focus:outline-none focus:border-[#00d4ff]/50 focus:ring-1 focus:ring-[#00d4ff]/20 transition-all"
              />
            </div>
            <div>
              <label className="block text-xs text-white/40 mb-1.5">{t('login.password')}</label>
              <input
                type="password"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
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
              {loading ? '…' : t('login.submit')}
            </button>
          </form>

          {oidcEnabled && (
            <a
              href={authApi.oidcLoginUrl()}
              className="mt-3 block w-full text-center py-2.5 rounded-lg text-sm border border-white/15 text-white/60 hover:text-white/90"
            >
              {t('login.sso')}
            </a>
          )}

          {registerEnabled ? (
            <div className="mt-4 text-center text-xs text-white/30">
              <Link to="/register" className="text-[#00d4ff]/70 hover:text-[#00d4ff] transition-colors">
                {t('login.register')}
              </Link>
            </div>
          ) : (
            <div className="mt-4 text-center text-xs text-white/25">{t('register.disabled')}</div>
          )}

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
