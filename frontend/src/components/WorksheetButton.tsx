import { useState } from 'react'
import { api } from '../api'

interface Props {
  title: string
  items: { name: string; smiles: string }[]
}

export function WorksheetButton({ title, items }: Props) {
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)

  const make = async (showNames: boolean) => {
    setBusy(true)
    try {
      const blob = await api.worksheet(title, items, showNames)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title.replace(/[^A-Za-z0-9]+/g, '_') || 'worksheet'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setBusy(false)
      setOpen(false)
    }
  }

  if (items.length === 0) return null
  return (
    <span className="ws-btn">
      <button type="button" onClick={() => setOpen((o) => !o)} disabled={busy} title="Printable PDF of these structures">Worksheet</button>
      {open && (
        <span className="ws-menu">
          <button type="button" onClick={() => void make(false)} disabled={busy}>Structures only (with answer key)</button>
          <button type="button" onClick={() => void make(true)} disabled={busy}>Structures with names</button>
        </span>
      )}
    </span>
  )
}
