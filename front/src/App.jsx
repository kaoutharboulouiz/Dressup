import { useEffect, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

const SLOTS = ["haut", "bas", "robe", "veste", "chaussures"];

export default function App() {
  const [garments, setGarments] = useState([]);
  const [ancres, setAncres] = useState([]);
  const [outfits, setOutfits] = useState([]);
  const [chargement, setChargement] = useState(false);
  const [quota, setQuota] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    fetch(`${API}/garments`)
      .then((r) => r.json())
      .then(setGarments)
      .catch(() => setErreur("API injoignable. Le serveur FastAPI tourne ?"));
    fetch(`${API}/quota`)
      .then((r) => r.json())
      .then((d) => setQuota(d.restant))
      .catch(() => {});
  }, []);

  function basculerAncre(id) {
    setAncres((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  async function proposer() {
    if (ancres.length === 0) return;
    setChargement(true);
    setErreur(null);
    try {
      const r = await fetch(`${API}/outfits/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ancre_ids: ancres, n: 5 }),
      });
      if (!r.ok) throw new Error(await r.text());
      setOutfits(await r.json());
    } catch (e) {
      setErreur(String(e.message).slice(0, 200));
    } finally {
      setChargement(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Dressup</h1>
        {quota !== null && <span className="quota">{quota} rendus restants</span>}
      </header>

      {erreur && <p className="erreur">{erreur}</p>}

      <section>
        <h2>Que veux-tu porter ?</h2>
        {SLOTS.map((slot) => {
          const items = garments.filter((g) => g.slot === slot);
          if (items.length === 0) return null;
          return (
            <div key={slot} className="rangee">
              <h3>{slot}</h3>
              <div className="grille">
                {items.map((g, n) => (
              <button
                key={`${slot}-${g.id}-${n}`}
                className={`vignette ${ancres.includes(g.id) ? "actif" : ""}`}
                onClick={() => basculerAncre(g.id)}
              >
                    <img src={`${API}/garments/${g.id}/image`} alt={g.categorie} />
                    <span>{g.categorie}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}

        <button
          className="principal"
          disabled={ancres.length === 0 || chargement}
          onClick={proposer}
        >
          {chargement ? "Recherche…" : `Proposer des tenues (${ancres.length})`}
        </button>
      </section>

      <section className="feed">
        {outfits.map((o) => (
          <CarteTenue key={o.id} outfit={o} onQuota={setQuota} />
        ))}
      </section>
    </div>
  );
}

function CarteTenue({ outfit, onQuota }) {
  const [statut, setStatut] = useState(outfit.render_status);
  const [renderId, setRenderId] = useState(outfit.render_id);

  useEffect(() => {
    if (statut !== "pending") return;
    const timer = setInterval(async () => {
      const r = await fetch(`${API}/outfits/${outfit.id}/render`);
      const d = await r.json();
      setStatut(d.status);
      if (d.id) setRenderId(d.id);
      if (d.status !== "pending") {
        clearInterval(timer);
        fetch(`${API}/quota`).then((r) => r.json()).then((q) => onQuota(q.restant));
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [statut, outfit.id, onQuota]);

  async function generer() {
    setStatut("pending");
    const r = await fetch(`${API}/outfits/${outfit.id}/render`, { method: "POST" });
    if (!r.ok) setStatut("erreur");
  }

  return (
    <article className="carte">
      <div className="entete">
        <span className="score">{(outfit.score * 100).toFixed(0)}</span>
        {outfit.occasion && <span className="occasion">{outfit.occasion}</span>}
      </div>

      {statut === "ok" && renderId ? (
        <img className="rendu" src={`${API}/renders/${renderId}/image`} alt="" />
      ) : (
        <div className="pieces">
          {outfit.items.map((i, n) => (
            <img
              key={`${i.garment_id}-${n}`}
              src={`${API}/garments/${i.garment_id}/image`}
              alt={i.categorie}
              title={i.port || i.categorie}
            />
          ))}
        </div>
      )}

      <ul className="details">
          {outfit.items.map((i, n) => (
            <li key={`${i.garment_id}-${n}`}>
            <span className="puce" style={{ background: i.couleur_hex }} />
            {i.categorie}
            {i.is_anchor && <em> imposé</em>}
            {i.port && <small>{i.port}</small>}
          </li>
        ))}
      </ul>

      {outfit.justification && <p className="pourquoi">{outfit.justification}</p>}

      {statut !== "ok" && (
        <button onClick={generer} disabled={statut === "pending"}>
          {statut === "pending" ? "Génération en cours…" : "Voir sur moi"}
        </button>
      )}
      {statut === "erreur" && <p className="erreur">Échec de la génération</p>}
    </article>
  );
}