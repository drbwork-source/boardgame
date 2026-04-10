import { useState, useEffect, useCallback } from "react";
import {
  listCardTemplates,
  createCardTemplate,
  updateCardTemplate,
  updateDeck,
  deleteCardTemplate,
} from "../api";
import type { DeckEntry, CardTemplateEntry } from "../types";

interface CardBuilderProps {
  deck: DeckEntry;
  onClose: () => void;
  onDeckUpdated: () => void;
  /** When true, used on Deck Builder page: larger layout, click row to edit */
  standalone?: boolean;
}

export function CardBuilder({ deck, onClose, onDeckUpdated, standalone }: CardBuilderProps) {
  const [cards, setCards] = useState<CardTemplateEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title: "", body: "", image_url: "", back_text: "" });
  const [saving, setSaving] = useState(false);

  const loadCards = useCallback(() => {
    setLoading(true);
    listCardTemplates(deck.id)
      .then(setCards)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [deck.id]);

  useEffect(() => {
    loadCards();
  }, [loadCards]);

  const handleAddCard = () => {
    setSaving(true);
    createCardTemplate({ title: "New card", body: "" })
      .then((t) => {
        return updateDeck(deck.id, {
          card_template_ids: [...deck.card_template_ids, t.id],
        }).then(() => {
          onDeckUpdated();
          loadCards();
          setEditForm({ title: t.title, body: t.body, image_url: t.image_url ?? "", back_text: t.back_text ?? "" });
          setEditingId(t.id);
        });
      })
      .catch(console.error)
      .finally(() => setSaving(false));
  };

  const handleEdit = (card: CardTemplateEntry) => {
    setEditingId(card.id);
    setEditForm({
      title: card.title,
      body: card.body,
      image_url: card.image_url ?? "",
      back_text: card.back_text ?? "",
    });
  };

  const handleSaveEdit = () => {
    if (!editingId) return;
    setSaving(true);
    updateCardTemplate(editingId, {
      title: editForm.title,
      body: editForm.body,
      image_url: editForm.image_url || null,
      back_text: editForm.back_text || null,
    })
      .then(() => {
        loadCards();
        setEditingId(null);
      })
      .catch(console.error)
      .finally(() => setSaving(false));
  };

  const handleRemove = (templateId: string) => {
    if (!confirm("Remove this card from the deck?")) return;
    setSaving(true);
    deleteCardTemplate(templateId)
      .then(() => {
        onDeckUpdated();
        loadCards();
        if (editingId === templateId) setEditingId(null);
      })
      .catch(console.error)
      .finally(() => setSaving(false));
  };

  const moveCard = (index: number, direction: 1 | -1) => {
    const ids = cards.map((c) => c.id);
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    const newOrder = [...ids];
    [newOrder[index], newOrder[target]] = [newOrder[target], newOrder[index]];
    setSaving(true);
    updateDeck(deck.id, { card_template_ids: newOrder })
      .then(() => {
        onDeckUpdated();
        loadCards();
      })
      .catch(console.error)
      .finally(() => setSaving(false));
  };

  const handleRowClick = (card: CardTemplateEntry) => {
    if (editingId === card.id) {
      setEditingId(null);
      return;
    }
    handleEdit(card);
  };

  return (
    <div className={`card-builder ${standalone ? "card-builder-standalone" : ""}`}>
      <div className="card-builder-header">
        <strong>{deck.name}</strong>
        <button type="button" onClick={onClose} className="exit-play-btn card-builder-close">
          {standalone ? "← Back to list" : "Close"}
        </button>
      </div>
      {loading ? (
        <div className="card-builder-loading">Loading cards…</div>
      ) : (
        <>
          <ul className="card-builder-list">
            {cards.map((card, index) => (
              <li key={card.id} className="card-builder-list-item">
                <div
                  role="button"
                  tabIndex={0}
                  className={`card-builder-row ${editingId === card.id ? "editing" : ""}`}
                  onClick={() => standalone && handleRowClick(card)}
                  onKeyDown={(e) => standalone && (e.key === "Enter" || e.key === " ") && handleRowClick(card)}
                >
                  <span className="card-builder-index">{index + 1}.</span>
                  <span className="card-builder-title">{card.title || "Untitled"}</span>
                  <div className="card-builder-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => moveCard(index, -1)}
                      disabled={saving || index === 0}
                      className="card-builder-btn-sm"
                      title="Move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => moveCard(index, 1)}
                      disabled={saving || index === cards.length - 1}
                      className="card-builder-btn-sm"
                      title="Move down"
                    >
                      ↓
                    </button>
                    {!standalone && (
                      <button type="button" onClick={() => handleEdit(card)} className="card-builder-btn-sm">
                        Edit
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemove(card.id)}
                      disabled={saving}
                      className="card-builder-btn-sm"
                      title="Remove from deck"
                    >
                      Remove
                    </button>
                  </div>
                </div>
                {editingId === card.id && (
                  <div className="card-builder-edit-inline">
                    <div className="card-builder-edit-fields">
                      <label>
                        Title
                        <input
                          type="text"
                          value={editForm.title}
                          onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                        />
                      </label>
                      <label>
                        Body
                        <textarea
                          value={editForm.body}
                          onChange={(e) => setEditForm((f) => ({ ...f, body: e.target.value }))}
                          rows={3}
                        />
                      </label>
                      <label>
                        Image URL (optional)
                        <input
                          type="text"
                          value={editForm.image_url}
                          onChange={(e) => setEditForm((f) => ({ ...f, image_url: e.target.value }))}
                          placeholder="https://…"
                        />
                      </label>
                      <label>
                        Back text (optional)
                        <input
                          type="text"
                          value={editForm.back_text}
                          onChange={(e) => setEditForm((f) => ({ ...f, back_text: e.target.value }))}
                          placeholder="BACK"
                        />
                      </label>
                    </div>
                    <div className="card-builder-edit-buttons">
                      <button type="button" onClick={handleSaveEdit} disabled={saving}>
                        Save
                      </button>
                      <button type="button" onClick={() => setEditingId(null)} className="exit-play-btn">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={handleAddCard}
            disabled={saving}
            className="card-builder-add-card"
          >
            {saving ? "…" : "+ Add card"}
          </button>

          {editingId && !standalone && (
            <div className="card-builder-edit-panel">
              <div className="card-builder-edit-fields">
                <label>
                  Title
                  <input
                    type="text"
                    value={editForm.title}
                    onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                  />
                </label>
                <label>
                  Body
                  <textarea
                    value={editForm.body}
                    onChange={(e) => setEditForm((f) => ({ ...f, body: e.target.value }))}
                    rows={3}
                  />
                </label>
                <label>
                  Image URL (optional)
                  <input
                    type="text"
                    value={editForm.image_url}
                    onChange={(e) => setEditForm((f) => ({ ...f, image_url: e.target.value }))}
                    placeholder="https://…"
                  />
                </label>
                <label>
                  Back text (optional)
                  <input
                    type="text"
                    value={editForm.back_text}
                    onChange={(e) => setEditForm((f) => ({ ...f, back_text: e.target.value }))}
                    placeholder="BACK"
                  />
                </label>
              </div>
              <div className="card-builder-edit-buttons">
                <button type="button" onClick={handleSaveEdit} disabled={saving}>
                  Save
                </button>
                <button type="button" onClick={() => setEditingId(null)} className="exit-play-btn">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
