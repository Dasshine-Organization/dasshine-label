/** 轻量中英界面包（P18） */
export type Locale = 'zh' | 'en'

const messages = {
  zh: {
    'nav.dashboard': '工作台',
    'nav.projects': '项目',
    'nav.tasks': '任务',
    'nav.review': '审核',
    'nav.leaderboard': '排行榜',
    'nav.profile': '账户',
    'nav.logout': '退出登录',
    'login.title': '登录账户',
    'login.username': '用户名',
    'login.password': '密码',
    'login.submit': '登录',
    'login.register': '没有账户？注册',
    'login.sso': '企业 SSO 登录',
    'login.subtitle': '智能标注与分发平台',
    'register.disabled': '公开注册已关闭，请使用邀请链接或 SSO',
    'org.enterprise': '企业设置',
    'org.invite': '邀请成员',
    'org.apiKeys': 'API Key',
    'org.webhooks': 'Webhook',
    'org.audit': '审计日志',
  },
  en: {
    'nav.dashboard': 'Dashboard',
    'nav.projects': 'Projects',
    'nav.tasks': 'Tasks',
    'nav.review': 'Review',
    'nav.leaderboard': 'Leaderboard',
    'nav.profile': 'Account',
    'nav.logout': 'Sign out',
    'login.title': 'Sign in',
    'login.username': 'Username',
    'login.password': 'Password',
    'login.submit': 'Sign in',
    'login.register': 'Need an account? Register',
    'login.sso': 'Enterprise SSO',
    'login.subtitle': 'Annotation & dispatch platform',
    'register.disabled': 'Public registration is disabled. Use an invite or SSO.',
    'org.enterprise': 'Enterprise',
    'org.invite': 'Invite',
    'org.apiKeys': 'API Keys',
    'org.webhooks': 'Webhooks',
    'org.audit': 'Audit log',
  },
} as const

export type MessageKey = keyof typeof messages.zh

const STORAGE_KEY = 'dasshine_locale'

export function getStoredLocale(): Locale {
  const v = localStorage.getItem(STORAGE_KEY)
  return v === 'en' ? 'en' : 'zh'
}

export function setStoredLocale(locale: Locale) {
  localStorage.setItem(STORAGE_KEY, locale)
}

export function t(key: MessageKey, locale?: Locale): string {
  const loc = locale ?? getStoredLocale()
  return messages[loc][key] ?? messages.zh[key] ?? key
}

export { messages }
