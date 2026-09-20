import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { api } from '../api'
import type { CheckResult } from '../types'

interface Props {
  value: string
  onChange: (v: string) => void
  onSubmit: (v: string) => void
  loading: boolean
  showHint?: boolean
}

export function NameInput({ value, onChange, onSubmit, loading, showHint = true }: Props) {
  const [check, setCheck] = useState<CheckResult | null>(null)
  const [names, setNames] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const checked = useRef('')

  // Live validity check and autocomplete, debounced.
  useEffect(() => {
    const text = value.trim()
    if (!text) {
      setCheck(null)
      setNames([])
      return
    }
    const t = window.setTimeout(() => {
      if (text !== checked.current) {
        checked.current = text
        api.check(text).then(setCheck).catch(() => setCheck(null))
      }
      api
        .suggest(text)
        .then((r) => {
          const list = r.names.filter((n) => n.toLowerCase() !== text.toLowerCase())
          setNames(list)
          setActive(-1)
        })
        .catch(() => setNames([]))
    }, 350)
    return () => window.clearTimeout(t)
  }, [value])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setOpen(false)
    if (value.trim()) onSubmit(value.trim())
  }

  const pick = (name: string) => {
    onChange(name)
    setOpen(false)
    setActive(-1)
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || names.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => (a + 1) % names.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a - 1 + names.length) % names.length)
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault()
      pick(names[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const status = value.trim() && check
    ? check.ok ? (check.warnings && check.warnings.length ? 'warn' : 'ok') : check.lookup ? 'lookup' : 'bad'
    : null
  const LOOKUP_HINT = 'Not a systematic IUPAC name. Build will look it up in PubChem.'

  return (
    <form className="name-input" onSubmit={submit} autoComplete="off">
      <div className="input-wrap">
        <input
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKey}
          placeholder="IUPAC name or SMILES"
          aria-label="IUPAC name or SMILES"
          aria-autocomplete="list"
          aria-expanded={open && names.length > 0}
          autoFocus
          spellCheck={false}
          className={status ? `status-${status}` : ''}
        />
        {status && (
          <span className={`status-icon status-${status}`} title={status === 'lookup' ? LOOKUP_HINT : check?.reason ?? check?.warnings?.[0] ?? 'Looks good'}>
            {status === 'ok' ? '\u2713' : status === 'warn' ? '!' : status === 'lookup' ? '?' : '\u2717'}
          </span>
        )}
        {open && names.length > 0 && (
          <ul className="autocomplete" role="listbox">
            {names.map((n, i) => (
              <li
                key={n}
                role="option"
                aria-selected={i === active}
                className={i === active ? 'active' : ''}
                onMouseDown={(e) => {
                  e.preventDefault()
                  pick(n)
                }}
              >
                {n}
              </li>
            ))}
          </ul>
        )}
      </div>
      <button type="submit" disabled={loading || !value.trim()}>
        {loading ? 'Building...' : 'Build'}
      </button>
      {showHint && status === 'bad' && check?.reason && <p className="hint hint-bad">{check.reason}</p>}
      {showHint && status === 'warn' && check?.warnings?.[0] && <p className="hint hint-warn">{check.warnings[0]}</p>}
      {showHint && status === 'lookup' && <p className="hint hint-lookup">{LOOKUP_HINT}</p>}
    </form>
  )
}
