import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import App from './App'
import { LocaleProvider, useLocale } from './i18n/LocaleProvider'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const theme = {
  token: {
    colorPrimary: '#00d4ff',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#00d4ff',
    colorBgBase: '#0a0a0f',
    colorBgContainer: '#12121a',
    colorBgElevated: '#1a1a25',
    colorBorder: '#1e1e2e',
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    borderRadius: 8,
    wireframe: false,
  },
}

function AntdLocaleBridge({ children }: { children: React.ReactNode }) {
  const { locale } = useLocale()
  return (
    <ConfigProvider locale={locale === 'en' ? enUS : zhCN} theme={theme}>
      {children}
    </ConfigProvider>
  )
}

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('Root element #root not found')
ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <AntdLocaleBridge>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AntdLocaleBridge>
      </LocaleProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
