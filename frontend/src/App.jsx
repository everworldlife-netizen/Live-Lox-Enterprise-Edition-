import { useEffect, useMemo, useState } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws/live-gamecast'

export default function App() {
  const [players, setPlayers] = useState([])
  const [selectedGameId, setSelectedGameId] = useState(null)
  const [status, setStatus] = useState('Connecting...')

  useEffect(() => {
    const socket = new WebSocket(WS_URL)

    socket.onopen = () => setStatus('Live')
    socket.onerror = () => setStatus('Connection error')
    socket.onclose = () => setStatus('Disconnected')

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      if (!Array.isArray(payload)) return

      setPlayers(payload)
      if (!selectedGameId && payload.length > 0) {
        setSelectedGameId(payload[0].game_id)
      }
    }

    return () => socket.close()
  }, [selectedGameId])

  const games = useMemo(() => {
    const index = new Map()
    for (const player of players) {
      if (!index.has(player.game_id)) {
        index.set(player.game_id, {
          gameId: player.game_id,
          matchup: player.matchup,
          status: player.game_status,
          playerCount: 0,
        })
      }
      index.get(player.game_id).playerCount += 1
    }
    return [...index.values()]
  }, [players])

  const selectedPlayers = useMemo(
    () => players.filter((player) => player.game_id === selectedGameId),
    [players, selectedGameId],
  )

  return (
    <main className="app-shell">
      <header className="topbar">
        <h1>NBA Live Projections</h1>
        <span className={`pill ${status === 'Live' ? 'pill-live' : ''}`}>{status}</span>
      </header>

      <section className="layout">
        <aside className="games-panel">
          <h2>Games</h2>
          {games.map((game) => (
            <button
              key={game.gameId}
              className={`game-item ${selectedGameId === game.gameId ? 'active' : ''}`}
              onClick={() => setSelectedGameId(game.gameId)}
            >
              <strong>{game.matchup}</strong>
              <small>{game.status} · {game.playerCount} tracked players</small>
            </button>
          ))}
        </aside>

        <section className="cards-panel">
          {selectedPlayers.map((player) => (
            <article key={player.id} className="player-card">
              <div className="card-head">
                <div>
                  <h3>{player.name}</h3>
                  <p>{player.team}</p>
                </div>
                <div>
                  <p className="label">Minutes</p>
                  <p>{player.minutes}</p>
                </div>
              </div>

              <div className="stats-grid">
                <Stat label="PTS" value={player.actual_pts} />
                <Stat label="REB" value={player.actual_reb} />
                <Stat label="AST" value={player.actual_ast} />
                <Stat label="Live Proj PTS" value={player.projected_pts} highlight />
              </div>

              {player.fouls >= 3 && <p className="warning">Foul trouble: {player.fouls} PF</p>}
            </article>
          ))}
        </section>
      </section>
    </main>
  )
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`stat ${highlight ? 'highlight' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
