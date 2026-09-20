import type { BuildError } from '../types'

interface Props {
  error: BuildError
  onPick: (name: string) => void
}

export function ErrorPanel({ error, onPick }: Props) {
  const { message, input, highlight, suggestions } = error
  return (
    <div className="error-panel" role="alert">
      <p className="error-msg">{message}</p>
      {input && highlight && (
        <p className="error-echo">
          <span>{input.slice(0, highlight[0])}</span>
          <mark>{input.slice(highlight[0], highlight[1])}</mark>
          <span>{input.slice(highlight[1])}</span>
        </p>
      )}
      {suggestions.length > 0 && (
        <div className="suggestions">
          <span className="muted">Did you mean</span>
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => onPick(s)}>{s}</button>
          ))}
        </div>
      )}
    </div>
  )
}
