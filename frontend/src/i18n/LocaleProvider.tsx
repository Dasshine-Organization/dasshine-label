import { createContext, useContext, useMemo, useState, useCallback, type ReactNode } from 'react'
import { getStoredLocale, setStoredLocale, t as translate, type Locale, type MessageKey } from '../i18n/messages'

type Ctx = {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: MessageKey) => string
}

const LocaleContext = createContext<Ctx | null>(null)

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale())
  const setLocale = useCallback((l: Locale) => {
    setStoredLocale(l)
    setLocaleState(l)
  }, [])
  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: (key: MessageKey) => translate(key, locale),
    }),
    [locale, setLocale],
  )
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  const ctx = useContext(LocaleContext)
  if (!ctx) {
    return {
      locale: 'zh' as Locale,
      setLocale: () => undefined,
      t: (key: MessageKey) => translate(key, 'zh'),
    }
  }
  return ctx
}
